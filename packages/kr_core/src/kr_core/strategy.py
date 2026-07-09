from __future__ import annotations

from dataclasses import dataclass
from typing import Dict, Iterable, List, Optional

from .models import FairGapInput, MarketQuality, OpeningSnapshot, StrategyDecision
from .universe import ETF_TARGETS


@dataclass(frozen=True)
class StrategyConfig:
    min_gap_residual: float = 0.0025
    min_gap_residual_z: float = 0.8
    min_theme_signal_z: float = 0.6
    min_score: float = 1.0
    battery_min_gap_residual_z: float = 1.0
    battery_min_score: float = 1.2
    max_open_drawdown: float = -0.0025
    max_premium_pct: float = 0.0015
    battery_max_premium_pct: float = 0.0010
    max_spread_avg_ratio: float = 2.0


FAIR_GAP_COEFFICIENTS = {
    "069500": {
        "alpha": 0.0000,
        "overseas_theme_signal": 0.20,
        "kospi200_night": 0.45,
        "ewy": 0.20,
        "nasdaq100": 0.08,
        "usdkrw": -0.10,
        "vix_change": -0.05,
        "risk_regime": -0.05,
    },
    "091160": {
        "alpha": 0.0000,
        "overseas_theme_signal": 0.48,
        "kospi200_night": 0.15,
        "ewy": 0.05,
        "nasdaq100": 0.18,
        "usdkrw": -0.05,
        "vix_change": -0.06,
        "risk_regime": -0.04,
    },
    "305720": {
        "alpha": 0.0000,
        "overseas_theme_signal": 0.42,
        "kospi200_night": 0.12,
        "ewy": 0.03,
        "nasdaq100": 0.18,
        "usdkrw": -0.07,
        "vix_change": -0.06,
        "risk_regime": -0.06,
    },
}


def zscore(value: float, mean: float = 0.0, std: float = 1.0) -> float:
    if std <= 0:
        return 0.0
    return (value - mean) / std


def compute_fair_gap(signal: FairGapInput) -> float:
    coefs = FAIR_GAP_COEFFICIENTS[signal.code]
    return (
        coefs["alpha"]
        + coefs["overseas_theme_signal"] * signal.overseas_theme_signal
        + coefs["kospi200_night"] * signal.kospi200_night
        + coefs["ewy"] * signal.ewy
        + coefs["nasdaq100"] * signal.nasdaq100
        + coefs["usdkrw"] * signal.usdkrw
        + coefs["vix_change"] * signal.vix_change
        + coefs["risk_regime"] * signal.risk_regime
    )


def actual_gap(snapshot: OpeningSnapshot) -> float:
    if snapshot.previous_close <= 0:
        return 0.0
    return snapshot.open_price / snapshot.previous_close - 1.0


def first_five_min_return(snapshot: OpeningSnapshot) -> float:
    if snapshot.open_price <= 0:
        return 0.0
    return snapshot.price_0905 / snapshot.open_price - 1.0


def volume_ratio(snapshot: OpeningSnapshot) -> float:
    if snapshot.average_volume_0905 <= 0:
        return 1.0
    return snapshot.volume_0905 / snapshot.average_volume_0905


def score_candidate(
    signal: FairGapInput,
    snapshot: OpeningSnapshot,
    quality: MarketQuality,
    residual_std: float,
) -> StrategyDecision:
    target = ETF_TARGETS[signal.code]
    fair = compute_fair_gap(signal)
    actual = actual_gap(snapshot)
    residual = fair - actual
    residual_z = zscore(residual, std=residual_std)
    five_min = first_five_min_return(snapshot)
    vol_z = zscore(volume_ratio(snapshot), mean=1.0, std=0.5)
    spread_z = zscore(quality.spread_avg_ratio, mean=1.0, std=0.5)
    tape = 0.5 * quality.kospi200_0905_return + 0.5 * quality.theme_0905_return

    score = (
        0.30 * residual_z
        + 0.20 * zscore(signal.overseas_theme_signal, std=0.01)
        + 0.20 * zscore(five_min, std=0.002)
        + 0.10 * vol_z
        + 0.10 * zscore(tape, std=0.002)
        - 0.05 * spread_z
        - 0.05 * zscore(snapshot.premium_pct, std=0.001)
    )

    reasons = no_trade_reasons(signal, snapshot, quality, fair, actual, residual, residual_z, score)
    return StrategyDecision(
        code=signal.code,
        name=target.name,
        fair_gap=fair,
        actual_gap=actual,
        gap_residual=residual,
        gap_residual_z=residual_z,
        score=score,
        selected=False,
        no_trade_reasons=reasons,
    )


def no_trade_reasons(
    signal: FairGapInput,
    snapshot: OpeningSnapshot,
    quality: MarketQuality,
    fair_gap: float,
    actual_gap_value: float,
    residual: float,
    residual_z: float,
    score: float,
    config: StrategyConfig = StrategyConfig(),
) -> List[str]:
    target = ETF_TARGETS[signal.code]
    reasons: List[str] = []
    five_min = first_five_min_return(snapshot)
    open_drawdown = snapshot.price_0905 / snapshot.open_price - 1.0 if snapshot.open_price > 0 else -1.0

    if not quality.data_ok:
        reasons.append("data quality check failed")
    if fair_gap <= 0:
        reasons.append("fair_gap <= 0")
    if actual_gap_value >= fair_gap:
        reasons.append("actual_gap >= fair_gap")
    if residual <= config.min_gap_residual:
        reasons.append("gap_residual below minimum")
    if residual_z <= (config.battery_min_gap_residual_z if target.stricter else config.min_gap_residual_z):
        reasons.append("gap_residual_z below threshold")
    if zscore(signal.overseas_theme_signal, std=0.01) <= config.min_theme_signal_z:
        reasons.append("overseas theme signal too weak")
    if score <= (config.battery_min_score if target.stricter else config.min_score):
        reasons.append("score below threshold")
    if five_min < 0:
        reasons.append("first five minute return negative")
    if open_drawdown < config.max_open_drawdown:
        reasons.append("price broke down after open")
    if snapshot.price_0905 < snapshot.vwap_0905 * 0.999:
        reasons.append("price below five minute VWAP")
    if quality.spread_avg_ratio > config.max_spread_avg_ratio:
        reasons.append("spread wider than normal")
    max_premium = config.battery_max_premium_pct if target.stricter else config.max_premium_pct
    if snapshot.premium_pct >= max_premium:
        reasons.append("ETF premium too high")
    if quality.vix_change_z >= 1.28 and quality.usdkrw_change_z >= 1.28:
        reasons.append("simultaneous VIX and USD/KRW stress")
    return reasons


def evaluate_candidates(
    signals: Iterable[FairGapInput],
    snapshots: Dict[str, OpeningSnapshot],
    quality: MarketQuality,
    residual_stds: Optional[Dict[str, float]] = None,
) -> List[StrategyDecision]:
    residual_stds = residual_stds or {}
    decisions: List[StrategyDecision] = []
    for signal in signals:
        snapshot = snapshots.get(signal.code)
        if snapshot is None:
            decisions.append(
                StrategyDecision(
                    code=signal.code,
                    name=ETF_TARGETS[signal.code].name,
                    fair_gap=0.0,
                    actual_gap=0.0,
                    gap_residual=0.0,
                    gap_residual_z=0.0,
                    score=0.0,
                    selected=False,
                    no_trade_reasons=["missing opening snapshot"],
                )
            )
            continue
        decisions.append(score_candidate(signal, snapshot, quality, residual_stds.get(signal.code, 0.005)))
    return select_best_candidate(decisions)


def select_best_candidate(decisions: List[StrategyDecision]) -> List[StrategyDecision]:
    tradable = [decision for decision in decisions if not decision.no_trade_reasons]
    if not tradable:
        return decisions
    winner = max(tradable, key=lambda item: item.score)
    return [
        StrategyDecision(
            code=decision.code,
            name=decision.name,
            fair_gap=decision.fair_gap,
            actual_gap=decision.actual_gap,
            gap_residual=decision.gap_residual,
            gap_residual_z=decision.gap_residual_z,
            score=decision.score,
            selected=decision.code == winner.code,
            no_trade_reasons=decision.no_trade_reasons,
        )
        for decision in decisions
    ]
