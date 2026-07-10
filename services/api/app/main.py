from __future__ import annotations

from dataclasses import asdict
from typing import Dict, Optional

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field

from .auto_trader import AutoTradeStore, AutoTrader
from kr_core.market_data import normalize_kiwoom_quote
from kr_core.models import StrategyDecision
from kr_core.orders import OrderBlocked, OrderConfig, create_order_preview, validate_order_submission
from kr_core.risk import RiskConfig
from kr_core.universe import ETF_TARGETS, LEAD_INDICATORS

from .config import settings
from .kiwoom import build_kiwoom_client
from .live_strategy import live_strategy_payload, sample_strategy_payload
from .sample_data import sample_snapshots

app = FastAPI(title="kr-quante API", version="0.1.0")
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3000", "http://127.0.0.1:3000"],
    allow_credentials=False,
    allow_methods=["*"],
    allow_headers=["*"],
)


class PreviewRequest(BaseModel):
    account_equity: float = Field(default=10_000_000, gt=0)
    reference_prices: Dict[str, float] = Field(default_factory=dict)
    raw_stop_pct: float = Field(default=0.01, gt=0)


class SubmitRequest(BaseModel):
    preview: Dict
    approved_by: str = ""
    order_type: str = "LMT"


class SellLimitRequest(BaseModel):
    code: str = Field(min_length=6, max_length=12)
    quantity: int = Field(gt=0)
    limit_price: int = Field(gt=0)
    approved_by: str = ""


class AutoSettingsRequest(BaseModel):
    enabled: Optional[bool] = None
    daily_budget_krw: Optional[int] = Field(default=None, ge=0)


auto_store = AutoTradeStore()
auto_trader: Optional[AutoTrader] = None


def build_auto_trader() -> AutoTrader:
    return AutoTrader(
        auto_store,
        strategy_payload,
        strategy_client,
        mode=settings.kiwoom_mode,
        account_no=settings.kiwoom_account_no,
        allow_live_trading=settings.allow_live_trading,
        disallow_market_orders=settings.disallow_market_orders,
        poll_seconds=settings.auto_trader_poll_seconds,
    )


@app.on_event("startup")
async def startup_auto_trader() -> None:
    global auto_trader
    auto_trader = build_auto_trader()
    if settings.auto_trader_background:
        auto_trader.start()


@app.on_event("shutdown")
async def shutdown_auto_trader() -> None:
    if auto_trader:
        await auto_trader.stop()


@app.get("/health")
def health() -> Dict:
    return {
        "status": "ok",
        "mode": settings.kiwoom_mode,
        "live_enabled": settings.allow_live_trading,
        "auto_background": settings.auto_trader_background,
        "targets": list(ETF_TARGETS.keys()),
    }


@app.get("/universe")
def universe() -> Dict:
    return {
        code: {
            "name": target.name,
            "theme": target.theme,
            "lead_indicators": LEAD_INDICATORS[code],
            "initial_cap": target.max_weight_initial,
            "normal_cap": target.max_weight_normal,
        }
        for code, target in ETF_TARGETS.items()
    }


def strategy_client():
    return build_kiwoom_client(
        settings.kiwoom_mode,
        settings.kiwoom_base_url,
        settings.kiwoom_app_key,
        settings.kiwoom_secret_key,
    )


async def strategy_payload() -> Dict:
    if settings.kiwoom_mode in {"mock", "local", "sample", "fake"} or not settings.kiwoom_app_key:
        return sample_strategy_payload()
    return await live_strategy_payload(strategy_client())


@app.get("/strategy/today")
async def strategy_today() -> Dict:
    return await strategy_payload()


@app.post("/orders/preview")
async def orders_preview(payload: PreviewRequest) -> Dict:
    strategy = await strategy_payload()
    decisions = strategy.get("decisions", [])
    selected = next((decision for decision in decisions if decision.get("selected")), None)
    if selected is None:
        return {
            "status": "no_trade",
            "reason": "no candidate passed filters",
            "data_mode": strategy.get("data_mode"),
            "warnings": strategy.get("warnings", []),
            "decisions": decisions,
        }

    selected_decision = StrategyDecision(**selected)
    live_snapshots = strategy.get("snapshots", {})
    sample_snapshot = sample_snapshots().get(selected_decision.code)
    selected_quote = strategy.get("quotes", {}).get(selected_decision.code, {})
    reference_price = (
        payload.reference_prices.get(selected_decision.code)
        or selected_quote.get("ask")
        or selected_quote.get("mid")
        or live_snapshots.get(selected_decision.code, {}).get("price_0905")
        or (sample_snapshot.price_0905 if sample_snapshot else 0)
    )
    preview = create_order_preview(
        selected_decision,
        account_equity=payload.account_equity,
        reference_price=reference_price,
        raw_stop_pct=payload.raw_stop_pct,
        risk_config=RiskConfig(risk_per_trade=settings.risk_per_trade),
    )
    return {"status": "preview", "preview": asdict(preview), "decision": selected}


@app.post("/orders/submit")
async def orders_submit(payload: SubmitRequest) -> Dict:
    from kr_core.models import OrderPreview

    preview_data = dict(payload.preview)
    preview_data["approved"] = bool(payload.approved_by)
    preview = OrderPreview(**preview_data)
    try:
        validate_order_submission(
            [preview],
            order_type=payload.order_type,
            config=OrderConfig(
                allow_live_trading=settings.allow_live_trading,
                require_manual_approval=settings.require_manual_approval,
                disallow_market_orders=settings.disallow_market_orders,
            ),
            live=settings.kiwoom_mode == "live",
        )
    except OrderBlocked as exc:
        raise HTTPException(status_code=403, detail=str(exc)) from exc

    client = build_kiwoom_client(
        settings.kiwoom_mode,
        settings.kiwoom_base_url,
        settings.kiwoom_app_key,
        settings.kiwoom_secret_key,
    )
    response = await client.buy_limit(
        code=preview.code,
        quantity=preview.quantity,
        limit_price=preview.limit_price,
        account_no=settings.kiwoom_account_no,
    )
    return {"status": "submitted", "kiwoom": response}


@app.post("/orders/sell-limit")
async def orders_sell_limit(payload: SellLimitRequest) -> Dict:
    from kr_core.models import OrderPreview

    preview = OrderPreview(
        code=payload.code,
        side="SELL",
        quantity=payload.quantity,
        limit_price=payload.limit_price,
        position_weight=0.0,
        max_loss_pct=0.0,
        stop_pct=0.0,
        client_order_id=f"manual-sell-{payload.code}",
        reason="manual end-of-day or risk exit",
        approved=bool(payload.approved_by),
    )
    try:
        validate_order_submission(
            [preview],
            order_type="LMT",
            config=OrderConfig(
                allow_live_trading=settings.allow_live_trading,
                require_manual_approval=settings.require_manual_approval,
                disallow_market_orders=settings.disallow_market_orders,
            ),
            live=settings.kiwoom_mode == "live",
        )
    except OrderBlocked as exc:
        raise HTTPException(status_code=403, detail=str(exc)) from exc

    client = build_kiwoom_client(
        settings.kiwoom_mode,
        settings.kiwoom_base_url,
        settings.kiwoom_app_key,
        settings.kiwoom_secret_key,
    )
    response = await client.sell_limit(
        code=preview.code,
        quantity=preview.quantity,
        limit_price=preview.limit_price,
        account_no=settings.kiwoom_account_no,
    )
    return {"status": "submitted", "kiwoom": response}


def get_auto_trader() -> AutoTrader:
    global auto_trader
    if auto_trader is None:
        auto_trader = build_auto_trader()
    return auto_trader


@app.get("/auto/status")
async def auto_status() -> Dict:
    return await get_auto_trader().status()


@app.get("/auto/logs")
async def auto_logs(limit: int = 100) -> Dict:
    return await get_auto_trader().logs(limit=limit)


@app.post("/auto/settings")
async def auto_settings(payload: AutoSettingsRequest) -> Dict:
    if payload.enabled is None and payload.daily_budget_krw is None:
        raise HTTPException(status_code=400, detail="no settings provided")
    return await get_auto_trader().update_settings(
        enabled=payload.enabled,
        daily_budget_krw=payload.daily_budget_krw,
    )


@app.post("/auto/tick")
async def auto_tick() -> Dict:
    return await get_auto_trader().tick(triggered_by="manual")


@app.get("/kiwoom/quote/{code}")
async def kiwoom_quote(code: str) -> Dict:
    client = build_kiwoom_client(
        settings.kiwoom_mode,
        settings.kiwoom_base_url,
        settings.kiwoom_app_key,
        settings.kiwoom_secret_key,
    )
    return await client.quote(code)


@app.get("/market/quote/{code}")
async def market_quote(code: str) -> Dict:
    client = build_kiwoom_client(
        settings.kiwoom_mode,
        settings.kiwoom_base_url,
        settings.kiwoom_app_key,
        settings.kiwoom_secret_key,
    )
    raw = await client.quote(code)
    return asdict(normalize_kiwoom_quote(code, raw))


@app.get("/market/quotes")
async def market_quotes() -> Dict:
    client = build_kiwoom_client(
        settings.kiwoom_mode,
        settings.kiwoom_base_url,
        settings.kiwoom_app_key,
        settings.kiwoom_secret_key,
    )
    quotes = []
    for code in ETF_TARGETS:
        raw = await client.quote(code)
        quotes.append(asdict(normalize_kiwoom_quote(code, raw)))
    return {"quotes": quotes}


@app.get("/kiwoom/token/check")
async def kiwoom_token_check() -> Dict:
    client = build_kiwoom_client(
        settings.kiwoom_mode,
        settings.kiwoom_base_url,
        settings.kiwoom_app_key,
        settings.kiwoom_secret_key,
    )
    data = await client.issue_token()
    return {
        "mode": settings.kiwoom_mode,
        "base_url": settings.kiwoom_base_url,
        "has_token": bool(data.get("token") or data.get("access_token")),
        "token_type": data.get("token_type"),
        "expires_dt": data.get("expires_dt"),
        "return_code": data.get("return_code"),
        "return_msg": data.get("return_msg"),
    }
