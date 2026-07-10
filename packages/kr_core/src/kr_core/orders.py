from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from typing import Iterable, List

from .models import OrderPreview, StrategyDecision
from .risk import RiskConfig, clamp_stop_pct, position_weight
from .universe import ETF_TARGETS


class OrderBlocked(RuntimeError):
    pass


@dataclass(frozen=True)
class OrderConfig:
    allow_live_trading: bool = False
    require_manual_approval: bool = True
    disallow_market_orders: bool = True
    max_orders: int = 1


def create_order_preview(
    decision: StrategyDecision,
    account_equity: float,
    reference_price: float,
    raw_stop_pct: float,
    risk_config: RiskConfig = RiskConfig(),
) -> OrderPreview:
    target = ETF_TARGETS[decision.code]
    stop_pct = clamp_stop_pct(raw_stop_pct, target)
    weight = position_weight(stop_pct, target, risk_config)
    budget = account_equity * weight
    quantity = int(budget / reference_price) if reference_price > 0 else 0
    limit_price = int(round(reference_price * (1.0 + target.max_slippage_pct)))
    return OrderPreview(
        code=decision.code,
        side="BUY",
        quantity=max(0, quantity),
        limit_price=limit_price,
        position_weight=weight,
        max_loss_pct=weight * stop_pct,
        stop_pct=stop_pct,
        client_order_id=f"kol-{decision.code}-{datetime.utcnow().strftime('%Y%m%d%H%M%S%f')}",
        reason="Korea overnight lead-lag v3 selected candidate",
    )


def validate_order_submission(
    previews: Iterable[OrderPreview],
    order_type: str,
    config: OrderConfig = OrderConfig(),
    live: bool = False,
) -> None:
    preview_list: List[OrderPreview] = list(previews)
    if live and not config.allow_live_trading:
        raise OrderBlocked("live trading is disabled")
    if config.disallow_market_orders and order_type.upper() == "MKT":
        raise OrderBlocked("market orders are not allowed")
    if config.require_manual_approval:
        unapproved = [preview.client_order_id for preview in preview_list if not preview.approved]
        if unapproved:
            raise OrderBlocked("manual approval required")
    if len(preview_list) > config.max_orders:
        raise OrderBlocked(f"too many orders: max {config.max_orders}")
    for preview in preview_list:
        if preview.quantity <= 0:
            raise OrderBlocked("quantity must be positive")
