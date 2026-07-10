from __future__ import annotations

import asyncio
import json
from dataclasses import asdict
from datetime import datetime, time
from pathlib import Path
from typing import Any, Awaitable, Callable, Dict, List, Optional
from uuid import uuid4
from zoneinfo import ZoneInfo

from kr_core.models import OrderPreview, StrategyDecision
from kr_core.orders import OrderBlocked, OrderConfig, validate_order_submission
from kr_core.universe import ETF_TARGETS


KST = ZoneInfo("Asia/Seoul")
BUY_START = time(9, 6)
BUY_END = time(9, 12)
SELL_START = time(14, 50)
SELL_END = time(15, 10)
DEFAULT_STORE_PATH = Path("work/auto_trader_state.json")
MAX_EVENTS = 500
MAX_AUTO_ORDERS = 4
MAX_SINGLE_BUDGET_WEIGHT = 0.40


StrategyLoader = Callable[[], Awaitable[Dict[str, Any]]]
ClientFactory = Callable[[], Any]


def _now_kst() -> datetime:
    return datetime.now(KST)


def _trading_day(now: datetime) -> str:
    return now.strftime("%Y-%m-%d")


def _in_window(now: datetime, start: time, end: time) -> bool:
    if now.weekday() >= 5:
        return False
    current = now.time()
    return start <= current <= end


def _default_store() -> Dict[str, Any]:
    return {
        "settings": {
            "enabled": False,
            "daily_budget_krw": 10_000,
            "buy_window": "09:06-09:12",
            "sell_window": "14:50-15:10",
            "max_daily_trades": 1,
        },
        "state": {
            "active_position": None,
            "days": {},
            "last_tick_at": None,
            "last_status": "idle",
        },
        "events": [],
    }


class AutoTradeStore:
    def __init__(self, path: Path = DEFAULT_STORE_PATH):
        self.path = path
        self._lock = asyncio.Lock()

    def _read_sync(self) -> Dict[str, Any]:
        if not self.path.exists():
            return _default_store()
        try:
            with self.path.open("r", encoding="utf-8") as handle:
                loaded = json.load(handle)
        except (json.JSONDecodeError, OSError):
            return _default_store()
        base = _default_store()
        base["settings"].update(loaded.get("settings", {}))
        base["state"].update(loaded.get("state", {}))
        base["events"] = list(loaded.get("events", []))
        return base

    def _write_sync(self, data: Dict[str, Any]) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        temp_path = self.path.with_suffix(".tmp")
        with temp_path.open("w", encoding="utf-8") as handle:
            json.dump(data, handle, ensure_ascii=False, indent=2, default=str)
        temp_path.replace(self.path)

    async def read(self) -> Dict[str, Any]:
        async with self._lock:
            return self._read_sync()

    async def write(self, data: Dict[str, Any]) -> None:
        async with self._lock:
            data["events"] = list(data.get("events", []))[-MAX_EVENTS:]
            self._write_sync(data)

    async def update(self, updater: Callable[[Dict[str, Any]], None]) -> Dict[str, Any]:
        async with self._lock:
            data = self._read_sync()
            updater(data)
            data["events"] = list(data.get("events", []))[-MAX_EVENTS:]
            self._write_sync(data)
            return data


def _append_event(
    data: Dict[str, Any],
    event_type: str,
    message: str,
    *,
    level: str = "info",
    code: Optional[str] = None,
    side: Optional[str] = None,
    quantity: Optional[int] = None,
    limit_price: Optional[int] = None,
    budget_krw: Optional[int] = None,
    estimated_pnl_krw: Optional[int] = None,
    details: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    now = _now_kst()
    event = {
        "id": uuid4().hex,
        "ts": now.isoformat(),
        "trading_day": _trading_day(now),
        "type": event_type,
        "level": level,
        "message": message,
        "code": code,
        "side": side,
        "quantity": quantity,
        "limit_price": limit_price,
        "budget_krw": budget_krw,
        "estimated_pnl_krw": estimated_pnl_krw,
        "details": details or {},
    }
    data.setdefault("events", []).append(event)
    return event


def _daily_state(data: Dict[str, Any], day: str) -> Dict[str, Any]:
    days = data.setdefault("state", {}).setdefault("days", {})
    daily = days.setdefault(day, {"flags": [], "buy_order": None, "sell_order": None})
    daily.setdefault("flags", [])
    return daily


def _flag_once(daily: Dict[str, Any], key: str) -> bool:
    flags = daily.setdefault("flags", [])
    if key in flags:
        return False
    flags.append(key)
    return True


def _reference_price(strategy: Dict[str, Any], code: str) -> float:
    quote = strategy.get("quotes", {}).get(code, {})
    snapshot = strategy.get("snapshots", {}).get(code, {})
    return float(quote.get("ask") or quote.get("mid") or snapshot.get("price_0905") or 0)


def _sell_reference_price(strategy: Dict[str, Any], code: str) -> float:
    quote = strategy.get("quotes", {}).get(code, {})
    snapshot = strategy.get("snapshots", {}).get(code, {})
    return float(quote.get("bid") or quote.get("mid") or snapshot.get("price_0905") or 0)


def _order_no(response: Dict[str, Any]) -> Optional[str]:
    for key in ("ord_no", "odno", "order_no", "ordNo", "ODNO"):
        value = response.get(key)
        if value:
            return str(value)
    return None


def _status_payload(data: Dict[str, Any], live_enabled: bool, mode: str) -> Dict[str, Any]:
    events = list(data.get("events", []))
    realized = sum(int(event.get("estimated_pnl_krw") or 0) for event in events if event.get("type") == "sell_submitted")
    return {
        "settings": data.get("settings", {}),
        "state": data.get("state", {}),
        "events": events[-50:][::-1],
        "summary": {
            "estimated_realized_pnl_krw": realized,
            "event_count": len(events),
            "last_event": events[-1] if events else None,
        },
        "runtime": {
            "live_enabled": live_enabled,
            "mode": mode,
            "buy_window": "09:06-09:12",
            "sell_window": "14:50-15:10",
            "max_auto_orders": MAX_AUTO_ORDERS,
            "max_single_budget_weight": MAX_SINGLE_BUDGET_WEIGHT,
        },
    }


class AutoTrader:
    def __init__(
        self,
        store: AutoTradeStore,
        strategy_loader: StrategyLoader,
        client_factory: ClientFactory,
        *,
        mode: str,
        account_no: str,
        allow_live_trading: bool,
        disallow_market_orders: bool = True,
        poll_seconds: int = 5,
    ):
        self.store = store
        self.strategy_loader = strategy_loader
        self.client_factory = client_factory
        self.mode = mode
        self.account_no = account_no
        self.allow_live_trading = allow_live_trading
        self.disallow_market_orders = disallow_market_orders
        self.poll_seconds = poll_seconds
        self._task: Optional[asyncio.Task] = None
        self._stopping = asyncio.Event()

    async def status(self) -> Dict[str, Any]:
        return _status_payload(await self.store.read(), self.allow_live_trading, self.mode)

    async def logs(self, limit: int = 100) -> Dict[str, Any]:
        data = await self.store.read()
        events = list(data.get("events", []))[-max(1, min(limit, MAX_EVENTS)) :][::-1]
        return {"events": events}

    async def update_settings(self, enabled: Optional[bool] = None, daily_budget_krw: Optional[int] = None) -> Dict[str, Any]:
        def updater(data: Dict[str, Any]) -> None:
            settings = data.setdefault("settings", {})
            if enabled is not None:
                settings["enabled"] = bool(enabled)
            if daily_budget_krw is not None:
                settings["daily_budget_krw"] = max(0, int(daily_budget_krw))
            _append_event(
                data,
                "settings_updated",
                "자동매매 설정 변경",
                details={"enabled": settings.get("enabled"), "daily_budget_krw": settings.get("daily_budget_krw")},
            )

        data = await self.store.update(updater)
        return _status_payload(data, self.allow_live_trading, self.mode)

    async def tick(self, triggered_by: str = "manual") -> Dict[str, Any]:
        data = await self.store.read()
        now = _now_kst()
        day = _trading_day(now)
        settings = data.get("settings", {})
        state = data.setdefault("state", {})
        state["last_tick_at"] = now.isoformat()

        if not settings.get("enabled"):
            state["last_status"] = "disabled"
            await self.store.write(data)
            return {"status": "disabled", "reason": "auto trading is off", "now": now.isoformat()}

        daily = _daily_state(data, day)
        if _in_window(now, BUY_START, BUY_END):
            result = await self._buy_tick(data, daily, day, now)
        elif _in_window(now, SELL_START, SELL_END):
            result = await self._sell_tick(data, daily, day, now)
        else:
            state["last_status"] = "waiting"
            result = {"status": "waiting", "reason": "outside automation windows", "now": now.isoformat()}
            if triggered_by == "manual":
                _append_event(data, "manual_tick", "자동매매 시간대가 아니어서 대기", details={"now": now.isoformat()})

        await self.store.write(data)
        return result

    async def _buy_tick(self, data: Dict[str, Any], daily: Dict[str, Any], day: str, now: datetime) -> Dict[str, Any]:
        if daily.get("buy_order"):
            data["state"]["last_status"] = "buy_already_submitted"
            return {"status": "skipped", "reason": "buy already submitted today"}

        strategy = await self.strategy_loader()
        selected_rows = [decision for decision in strategy.get("selected", []) if decision.get("selected")]
        if not selected_rows:
            data["state"]["last_status"] = "no_candidate"
            if _flag_once(daily, "no_candidate"):
                _append_event(data, "no_candidate", "매수 시간대지만 조건 통과 후보가 없음", details={"generated_at": strategy.get("generated_at")})
            return {"status": "no_trade", "reason": "no candidate passed filters"}

        budget_krw = int(data.get("settings", {}).get("daily_budget_krw") or 0)
        decisions = [StrategyDecision(**row) for row in selected_rows]
        plan = self._build_buy_plan(strategy, decisions, budget_krw, now)
        if not plan:
            cheapest = min(
                [
                    int(round(_reference_price(strategy, decision.code) * (1.0 + ETF_TARGETS[decision.code].max_slippage_pct)))
                    for decision in decisions
                    if _reference_price(strategy, decision.code) > 0
                ]
                or [0]
            )
            data["state"]["last_status"] = "budget_too_small"
            if _flag_once(daily, "budget_too_small_multi"):
                _append_event(
                    data,
                    "budget_too_small",
                    "하루 예산이 통과 후보의 1주 지정가보다 작아서 자동매수 안 함",
                    level="warning",
                    side="BUY",
                    quantity=0,
                    limit_price=cheapest,
                    budget_krw=budget_krw,
                )
            return {"status": "blocked", "reason": "daily budget is below one-share limit price"}
        try:
            validate_order_submission(
                plan,
                order_type="LMT",
                config=OrderConfig(
                    allow_live_trading=self.allow_live_trading,
                    require_manual_approval=False,
                    disallow_market_orders=self.disallow_market_orders,
                    max_orders=MAX_AUTO_ORDERS,
                ),
                live=self.mode == "live",
            )
        except OrderBlocked as exc:
            data["state"]["last_status"] = "buy_blocked"
            if _flag_once(daily, f"buy_blocked_{str(exc)}"):
                _append_event(
                    data,
                    "buy_blocked",
                    str(exc),
                    level="warning",
                    side="BUY",
                    budget_krw=budget_krw,
                )
            return {"status": "blocked", "reason": str(exc)}

        orders: List[Dict[str, Any]] = []
        positions: List[Dict[str, Any]] = []
        client = self.client_factory()
        decision_by_code = {decision.code: decision for decision in decisions}
        for preview in plan:
            response = await client.buy_limit(
                code=preview.code,
                quantity=preview.quantity,
                limit_price=preview.limit_price,
                account_no=self.account_no,
            )
            decision = decision_by_code[preview.code]
            order = {
                **asdict(preview),
                "submitted_at": now.isoformat(),
                "trading_day": day,
                "budget_krw": budget_krw,
                "order_no": _order_no(response),
                "kiwoom": response,
                "fill_status": "submitted_unconfirmed",
            }
            position = {
                "code": preview.code,
                "name": decision.name,
                "quantity": preview.quantity,
                "entry_limit_price": preview.limit_price,
                "entry_order_no": order.get("order_no"),
                "entry_at": now.isoformat(),
                "trading_day": day,
                "fill_status": "submitted_unconfirmed",
            }
            orders.append(order)
            positions.append(position)
            _append_event(
                data,
                "buy_submitted",
                "자동 분산 지정가 매수 주문 제출",
                code=preview.code,
                side="BUY",
                quantity=preview.quantity,
                limit_price=preview.limit_price,
                budget_krw=budget_krw,
                details={"order_no": order.get("order_no"), "kiwoom": response},
            )

        daily["buy_orders"] = orders
        daily["buy_order"] = orders[0] if orders else None
        data["state"]["active_positions"] = positions
        data["state"]["active_position"] = positions[0] if positions else None
        data["state"]["last_status"] = "buy_submitted"
        return {"status": "submitted", "side": "BUY", "orders": orders}

    async def _sell_tick(self, data: Dict[str, Any], daily: Dict[str, Any], day: str, now: datetime) -> Dict[str, Any]:
        positions = list(data.get("state", {}).get("active_positions") or [])
        if not positions and data.get("state", {}).get("active_position"):
            positions = [data["state"]["active_position"]]
        open_positions = [position for position in positions if not position.get("exit_order_no")]
        if not open_positions:
            data["state"]["last_status"] = "no_position"
            if _flag_once(daily, "no_position_to_sell"):
                _append_event(data, "no_position", "청산 시간대지만 자동 보유 포지션 없음")
            return {"status": "skipped", "reason": "no active auto position"}
        if daily.get("sell_orders") or daily.get("sell_order"):
            data["state"]["last_status"] = "sell_already_submitted"
            return {"status": "skipped", "reason": "sell already submitted"}

        strategy = await self.strategy_loader()
        plan: List[OrderPreview] = []
        estimated_by_code: Dict[str, int] = {}
        for position in open_positions:
            code = str(position["code"])
            reference_price = _sell_reference_price(strategy, code)
            limit_price = int(round(reference_price)) or int(position["entry_limit_price"])
            quantity = int(position["quantity"])
            estimated_by_code[code] = int(round((limit_price - int(position["entry_limit_price"])) * quantity))
            plan.append(
                OrderPreview(
                    code=code,
                    side="SELL",
                    quantity=quantity,
                    limit_price=limit_price,
                    position_weight=0.0,
                    max_loss_pct=0.0,
                    stop_pct=0.0,
                    client_order_id=f"auto-sell-{code}-{now.strftime('%Y%m%d%H%M%S')}",
                    reason="auto end-of-day exit",
                    approved=True,
                )
            )
        try:
            validate_order_submission(
                plan,
                order_type="LMT",
                config=OrderConfig(
                    allow_live_trading=self.allow_live_trading,
                    require_manual_approval=False,
                    disallow_market_orders=self.disallow_market_orders,
                    max_orders=MAX_AUTO_ORDERS,
                ),
                live=self.mode == "live",
            )
        except OrderBlocked as exc:
            data["state"]["last_status"] = "sell_blocked"
            if _flag_once(daily, f"sell_blocked_{code}_{str(exc)}"):
                _append_event(
                    data,
                    "sell_blocked",
                    str(exc),
                    level="warning",
                    side="SELL",
                )
            return {"status": "blocked", "reason": str(exc)}

        orders: List[Dict[str, Any]] = []
        client = self.client_factory()
        position_by_code = {str(position["code"]): position for position in open_positions}
        for preview in plan:
            response = await client.sell_limit(
                code=preview.code,
                quantity=preview.quantity,
                limit_price=preview.limit_price,
                account_no=self.account_no,
            )
            estimated_pnl = estimated_by_code.get(preview.code, 0)
            order = {
                **asdict(preview),
                "submitted_at": now.isoformat(),
                "trading_day": day,
                "order_no": _order_no(response),
                "kiwoom": response,
                "estimated_pnl_krw": estimated_pnl,
                "fill_status": "submitted_unconfirmed",
            }
            orders.append(order)
            position = position_by_code[preview.code]
            position["exit_limit_price"] = preview.limit_price
            position["exit_order_no"] = order.get("order_no")
            position["exit_at"] = now.isoformat()
            position["estimated_pnl_krw"] = estimated_pnl
            position["fill_status"] = "exit_submitted_unconfirmed"
            _append_event(
                data,
                "sell_submitted",
                "자동 분산 포지션 지정가 매도 청산 주문 제출",
                code=preview.code,
                side="SELL",
                quantity=preview.quantity,
                limit_price=preview.limit_price,
                estimated_pnl_krw=estimated_pnl,
                details={"order_no": order.get("order_no"), "kiwoom": response},
            )

        daily["sell_orders"] = orders
        daily["sell_order"] = orders[0] if orders else None
        data["state"]["active_positions"] = positions
        data["state"]["active_position"] = positions[0] if positions else None
        data["state"]["last_status"] = "sell_submitted"
        return {"status": "submitted", "side": "SELL", "orders": orders}

    def _build_buy_plan(
        self,
        strategy: Dict[str, Any],
        decisions: List[StrategyDecision],
        budget_krw: int,
        now: datetime,
    ) -> List[OrderPreview]:
        ranked = sorted(decisions, key=lambda item: item.score, reverse=True)[:MAX_AUTO_ORDERS]
        candidates: List[Dict[str, Any]] = []
        for decision in ranked:
            reference_price = _reference_price(strategy, decision.code)
            target = ETF_TARGETS[decision.code]
            limit_price = int(round(reference_price * (1.0 + target.max_slippage_pct)))
            if limit_price <= 0:
                continue
            max_budget = max(limit_price, int(budget_krw * MAX_SINGLE_BUDGET_WEIGHT))
            max_quantity = max(1, max_budget // limit_price)
            candidates.append({"decision": decision, "limit_price": limit_price, "max_quantity": max_quantity})

        remaining = budget_krw
        quantities = {candidate["decision"].code: 0 for candidate in candidates}
        for candidate in candidates:
            code = candidate["decision"].code
            limit_price = candidate["limit_price"]
            if remaining >= limit_price:
                quantities[code] += 1
                remaining -= limit_price

        while True:
            affordable = [
                candidate
                for candidate in candidates
                if remaining >= candidate["limit_price"]
                and quantities[candidate["decision"].code] < candidate["max_quantity"]
            ]
            if not affordable:
                break
            candidate = max(affordable, key=lambda item: item["decision"].score)
            code = candidate["decision"].code
            quantities[code] += 1
            remaining -= candidate["limit_price"]

        plan: List[OrderPreview] = []
        for candidate in candidates:
            decision = candidate["decision"]
            quantity = quantities[decision.code]
            if quantity <= 0:
                continue
            plan.append(
                OrderPreview(
                    code=decision.code,
                    side="BUY",
                    quantity=quantity,
                    limit_price=candidate["limit_price"],
                    position_weight=0.0,
                    max_loss_pct=0.0,
                    stop_pct=0.0,
                    client_order_id=f"auto-buy-{decision.code}-{now.strftime('%Y%m%d%H%M%S')}",
                    reason="auto diversified Korea overnight lead-lag v3",
                    approved=True,
                )
            )
        return plan

    def start(self) -> None:
        if self._task and not self._task.done():
            return
        self._stopping.clear()
        self._task = asyncio.create_task(self._loop())

    async def stop(self) -> None:
        self._stopping.set()
        if self._task:
            self._task.cancel()
            try:
                await self._task
            except asyncio.CancelledError:
                pass

    async def _loop(self) -> None:
        while not self._stopping.is_set():
            try:
                await self.tick(triggered_by="scheduler")
            except Exception as exc:
                def updater(data: Dict[str, Any]) -> None:
                    data.setdefault("state", {})["last_status"] = "error"
                    _append_event(data, "error", f"자동매매 오류: {exc}", level="error")

                await self.store.update(updater)
            await asyncio.sleep(self.poll_seconds)
