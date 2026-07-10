from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from typing import List


@dataclass(frozen=True)
class EtfTarget:
    code: str
    name: str
    theme: str
    risk_bucket: str
    max_weight_initial: float
    max_weight_normal: float
    min_stop_pct: float
    max_stop_pct: float
    max_slippage_pct: float
    stricter: bool = False


@dataclass(frozen=True)
class FairGapInput:
    code: str
    overseas_theme_signal: float
    kospi200_night: float = 0.0
    ewy: float = 0.0
    nasdaq100: float = 0.0
    usdkrw: float = 0.0
    vix_change: float = 0.0
    risk_regime: float = 0.0


@dataclass(frozen=True)
class OpeningSnapshot:
    code: str
    previous_close: float
    open_price: float
    price_0905: float
    vwap_0905: float
    volume_0905: float
    average_volume_0905: float
    bid: float
    ask: float
    premium_pct: float
    high_since_open: float


@dataclass(frozen=True)
class MarketQuality:
    vix_change_z: float = 0.0
    usdkrw_change_z: float = 0.0
    vix_level: float = 0.0
    overseas_equity_shock: float = 0.0
    risk_off_score: float = 0.0
    kospi200_0905_return: float = 0.0
    theme_0905_return: float = 0.0
    spread_avg_ratio: float = 1.0
    data_ok: bool = True


@dataclass(frozen=True)
class StrategyDecision:
    code: str
    name: str
    fair_gap: float
    actual_gap: float
    gap_residual: float
    gap_residual_z: float
    score: float
    selected: bool
    no_trade_reasons: List[str] = field(default_factory=list)


@dataclass(frozen=True)
class OrderPreview:
    code: str
    side: str
    quantity: int
    limit_price: int
    position_weight: float
    max_loss_pct: float
    stop_pct: float
    client_order_id: str
    reason: str
    approved: bool = False
    created_at: datetime = field(default_factory=datetime.utcnow)
