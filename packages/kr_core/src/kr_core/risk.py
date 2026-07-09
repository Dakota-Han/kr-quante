from __future__ import annotations

from dataclasses import dataclass

from .models import EtfTarget


@dataclass(frozen=True)
class RiskConfig:
    risk_per_trade: float = 0.003
    daily_loss_limit: float = -0.006
    weekly_loss_limit: float = -0.015
    monthly_loss_limit: float = -0.04
    initial_mode: bool = True


def clamp_stop_pct(raw_stop_pct: float, target: EtfTarget) -> float:
    return min(max(raw_stop_pct, target.min_stop_pct), target.max_stop_pct)


def position_weight(stop_pct: float, target: EtfTarget, config: RiskConfig = RiskConfig()) -> float:
    if stop_pct <= 0:
        return 0.0
    raw_weight = config.risk_per_trade / stop_pct
    cap = target.max_weight_initial if config.initial_mode else target.max_weight_normal
    return min(raw_weight, cap)


def should_halt_strategy(
    daily_return: float,
    weekly_return: float,
    monthly_return: float,
    config: RiskConfig = RiskConfig(),
) -> bool:
    return (
        daily_return <= config.daily_loss_limit
        or weekly_return <= config.weekly_loss_limit
        or monthly_return <= config.monthly_loss_limit
    )
