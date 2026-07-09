from __future__ import annotations

from dataclasses import asdict
from typing import Dict

from fastapi import FastAPI, HTTPException
from pydantic import BaseModel, Field

from kr_core.orders import OrderBlocked, OrderConfig, create_order_preview, validate_order_submission
from kr_core.risk import RiskConfig
from kr_core.strategy import evaluate_candidates
from kr_core.universe import ETF_TARGETS, LEAD_INDICATORS

from .config import settings
from .kiwoom import build_kiwoom_client
from .sample_data import sample_quality, sample_signals, sample_snapshots

app = FastAPI(title="kr-quante API", version="0.1.0")


class PreviewRequest(BaseModel):
    account_equity: float = Field(default=10_000_000, gt=0)
    reference_prices: Dict[str, float] = Field(default_factory=dict)
    raw_stop_pct: float = Field(default=0.01, gt=0)


class SubmitRequest(BaseModel):
    preview: Dict
    approved_by: str = ""
    order_type: str = "LMT"


@app.get("/health")
def health() -> Dict:
    return {
        "status": "ok",
        "mode": settings.kiwoom_mode,
        "live_enabled": settings.allow_live_trading,
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


@app.get("/strategy/today")
def strategy_today() -> Dict:
    decisions = evaluate_candidates(sample_signals(), sample_snapshots(), sample_quality())
    return {
        "strategy": "Korea Overnight Lead-Lag 3 ETF Strategy v3",
        "decisions": [asdict(decision) for decision in decisions],
        "selected": [asdict(decision) for decision in decisions if decision.selected],
    }


@app.post("/orders/preview")
def orders_preview(payload: PreviewRequest) -> Dict:
    decisions = evaluate_candidates(sample_signals(), sample_snapshots(), sample_quality())
    selected = next((decision for decision in decisions if decision.selected), None)
    if selected is None:
        return {"status": "no_trade", "reason": "no candidate passed filters", "decisions": [asdict(d) for d in decisions]}

    snapshots = sample_snapshots()
    reference_price = payload.reference_prices.get(selected.code) or snapshots[selected.code].price_0905
    preview = create_order_preview(
        selected,
        account_equity=payload.account_equity,
        reference_price=reference_price,
        raw_stop_pct=payload.raw_stop_pct,
        risk_config=RiskConfig(risk_per_trade=settings.risk_per_trade),
    )
    return {"status": "preview", "preview": asdict(preview), "decision": asdict(selected)}


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


@app.get("/kiwoom/quote/{code}")
async def kiwoom_quote(code: str) -> Dict:
    client = build_kiwoom_client(
        settings.kiwoom_mode,
        settings.kiwoom_base_url,
        settings.kiwoom_app_key,
        settings.kiwoom_secret_key,
    )
    return await client.quote(code)
