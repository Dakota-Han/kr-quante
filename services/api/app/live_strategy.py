from __future__ import annotations

from dataclasses import asdict
from datetime import datetime, time
from typing import Dict, Iterable, List, Tuple
from zoneinfo import ZoneInfo

from kr_core.market_data import normalize_kiwoom_quote, parse_kiwoom_int
from kr_core.models import FairGapInput, MarketQuality, OpeningSnapshot, StrategyDecision
from kr_core.strategy import evaluate_candidates, first_five_min_return
from kr_core.universe import ETF_TARGETS

from .overseas_data import ReturnPoint, fetch_overseas_returns, serialize_returns
from .sample_data import sample_quality, sample_signals, sample_snapshots


KST = ZoneInfo("Asia/Seoul")
ENTRY_START = time(9, 6)
ENTRY_END = time(9, 12)

THEME_WEIGHTS = {
    "069500": {
        "EWY": 0.35,
        "SPY": 0.25,
        "^GSPC": 0.20,
        "QQQ": 0.20,
    },
    "091160": {
        "^SOX": 0.35,
        "SOXX": 0.20,
        "SMH": 0.15,
        "NVDA": 0.10,
        "AMD": 0.07,
        "MU": 0.05,
        "TSM": 0.05,
        "^NDX": 0.03,
    },
    "305720": {
        "TSLA": 0.35,
        "LIT": 0.20,
        "ALB": 0.15,
        "SQM": 0.10,
        "QQQ": 0.10,
        "^NDX": 0.10,
    },
}

KOSPI200_PROXY_WEIGHTS = {
    "EWY": 0.55,
    "SPY": 0.20,
    "^GSPC": 0.15,
    "^NDX": 0.10,
}

OVERSEAS_SYMBOLS = sorted(
    {
        "SPY",
        "QQQ",
        "EWY",
        "^GSPC",
        "^NDX",
        "^VIX",
        "^SOX",
        "SOXX",
        "SMH",
        "NVDA",
        "AMD",
        "MU",
        "TSM",
        "TSLA",
        "LIT",
        "ALB",
        "SQM",
        "USDKRW=X",
    }
)


def sample_strategy_payload() -> Dict:
    decisions = evaluate_candidates(sample_signals(), sample_snapshots(), sample_quality())
    return {
        "strategy": "Korea Overnight Lead-Lag 3 ETF Strategy v3",
        "data_mode": "sample",
        "generated_at": datetime.now(KST).isoformat(),
        "entry_window": "09:06-09:12",
        "data_sources": {
            "overseas": "sample",
            "domestic": "sample",
        },
        "warnings": ["mock mode: strategy uses sample data"],
        "decisions": [asdict(decision) for decision in decisions],
        "selected": [asdict(decision) for decision in decisions if decision.selected],
    }


def in_entry_window(now: datetime) -> bool:
    if now.weekday() >= 5:
        return False
    current = now.time()
    return ENTRY_START <= current <= ENTRY_END


def weighted_return(
    weights: Dict[str, float],
    returns: Dict[str, ReturnPoint],
    warnings: List[str],
    label: str,
    min_coverage: float = 0.60,
) -> Tuple[float, bool]:
    available_weight = sum(weight for symbol, weight in weights.items() if symbol in returns)
    if available_weight < min_coverage:
        warnings.append(f"{label}: overseas coverage too low ({available_weight:.0%})")
        return 0.0, False
    value = sum(weight * returns[symbol].value for symbol, weight in weights.items() if symbol in returns)
    return value / available_weight, True


def build_fair_gap_inputs(returns: Dict[str, ReturnPoint], warnings: List[str]) -> Tuple[List[FairGapInput], bool]:
    kospi200_proxy, kospi_ok = weighted_return(KOSPI200_PROXY_WEIGHTS, returns, warnings, "KOSPI200 proxy")
    ewy = returns.get("EWY").value if "EWY" in returns else kospi200_proxy
    nasdaq100 = returns.get("^NDX").value if "^NDX" in returns else returns.get("QQQ", ReturnPoint("QQQ", 0, 0, 0, "", "", "")).value
    usdkrw = returns.get("USDKRW=X").value if "USDKRW=X" in returns else 0.0
    vix_change = returns.get("^VIX").value if "^VIX" in returns else 0.0
    risk_regime = 1.0 if vix_change > 0.08 and usdkrw > 0.006 else 0.0

    signals: List[FairGapInput] = []
    ok = kospi_ok
    for code, weights in THEME_WEIGHTS.items():
        theme_signal, theme_ok = weighted_return(weights, returns, warnings, f"{code} theme")
        ok = ok and theme_ok
        signals.append(
            FairGapInput(
                code=code,
                overseas_theme_signal=theme_signal,
                kospi200_night=kospi200_proxy,
                ewy=ewy,
                nasdaq100=nasdaq100,
                usdkrw=usdkrw,
                vix_change=vix_change,
                risk_regime=risk_regime,
            )
        )
    return signals, ok


def _rows(raw: Dict, key: str) -> List[Dict]:
    value = raw.get(key)
    return value if isinstance(value, list) else []


def _time_key(row: Dict) -> str:
    return str(row.get("cntr_tm") or "")


def opening_snapshot_from_raw(code: str, daily_raw: Dict, minute_raw: Dict, quote_raw: Dict) -> tuple[OpeningSnapshot, List[str]]:
    warnings: List[str] = []
    daily_rows = _rows(daily_raw, "stk_dt_pole_chart_qry")
    minute_rows = _rows(minute_raw, "stk_min_pole_chart_qry")
    if len(daily_rows) < 2:
        raise ValueError(f"{code}: not enough Kiwoom daily bars")

    today = daily_rows[0]
    previous = daily_rows[1]
    today_date = str(today.get("dt") or "")
    previous_close = parse_kiwoom_int(previous.get("cur_prc"))
    open_price = parse_kiwoom_int(today.get("open_pric"))
    current_price = parse_kiwoom_int(today.get("cur_prc"))
    daily_volume = parse_kiwoom_int(today.get("trde_qty"))
    quote = normalize_kiwoom_quote(code, quote_raw)

    today_minute_rows = [row for row in minute_rows if _time_key(row).startswith(today_date)]
    today_minute_rows.sort(key=_time_key)
    opening_rows = [row for row in today_minute_rows if _time_key(row)[8:14] <= "090500"]
    if not opening_rows:
        opening_rows = today_minute_rows[:6]
    if not opening_rows:
        warnings.append(f"{code}: missing Kiwoom 09:05 minute bars; using current price fallback")

    if opening_rows:
        price_0905 = parse_kiwoom_int(opening_rows[-1].get("cur_prc"))
        weighted_sum = 0.0
        volume_0905 = 0.0
        for row in opening_rows:
            price = parse_kiwoom_int(row.get("cur_prc"))
            volume = parse_kiwoom_int(row.get("trde_qty"))
            if price and volume:
                weighted_sum += price * volume
                volume_0905 += volume
        vwap_0905 = weighted_sum / volume_0905 if volume_0905 else price_0905
    else:
        price_0905 = current_price or quote.mid or open_price
        vwap_0905 = price_0905
        volume_0905 = 0.0

    previous_volumes = [parse_kiwoom_int(row.get("trde_qty")) for row in daily_rows[1:21]]
    previous_volumes = [volume for volume in previous_volumes if volume > 0]
    average_daily_volume = sum(previous_volumes) / len(previous_volumes) if previous_volumes else daily_volume
    average_volume_0905 = max(1.0, average_daily_volume * 6 / 390)
    high_since_open = max(
        [parse_kiwoom_int(row.get("high_pric")) for row in today_minute_rows] or [parse_kiwoom_int(today.get("high_pric"))]
    )

    if previous_close <= 0 or open_price <= 0:
        raise ValueError(f"{code}: invalid Kiwoom open/previous close")

    return (
        OpeningSnapshot(
            code=code,
            previous_close=previous_close,
            open_price=open_price,
            price_0905=price_0905,
            vwap_0905=vwap_0905,
            volume_0905=volume_0905,
            average_volume_0905=average_volume_0905,
            bid=quote.bid,
            ask=quote.ask,
            premium_pct=0.0,
            high_since_open=high_since_open,
        ),
        warnings,
    )


async def build_opening_snapshots(kiwoom_client) -> tuple[Dict[str, OpeningSnapshot], Dict[str, Dict], List[str]]:
    snapshots: Dict[str, OpeningSnapshot] = {}
    raw_quotes: Dict[str, Dict] = {}
    warnings: List[str] = []
    for code in ETF_TARGETS:
        quote_raw = await kiwoom_client.quote(code)
        daily_raw = await kiwoom_client.daily_bars(code)
        minute_raw = await kiwoom_client.minute_bars(code)
        raw_quotes[code] = asdict(normalize_kiwoom_quote(code, quote_raw))
        try:
            snapshot, snapshot_warnings = opening_snapshot_from_raw(code, daily_raw, minute_raw, quote_raw)
            snapshots[code] = snapshot
            warnings.extend(snapshot_warnings)
        except Exception as exc:
            warnings.append(str(exc))
    return snapshots, raw_quotes, warnings


def build_market_quality(
    returns: Dict[str, ReturnPoint],
    snapshots: Dict[str, OpeningSnapshot],
    raw_quotes: Dict[str, Dict],
    data_ok: bool,
) -> MarketQuality:
    first_five_returns = [first_five_min_return(snapshot) for snapshot in snapshots.values()]
    kospi200_0905 = first_five_min_return(snapshots["069500"]) if "069500" in snapshots else 0.0
    theme_0905 = sum(first_five_returns) / len(first_five_returns) if first_five_returns else 0.0
    max_spread_bps = max([quote.get("spread_bps", 0.0) for quote in raw_quotes.values()] or [0.0])
    vix_change = returns.get("^VIX").value if "^VIX" in returns else 0.0
    usdkrw_change = returns.get("USDKRW=X").value if "USDKRW=X" in returns else 0.0
    return MarketQuality(
        vix_change_z=vix_change / 0.08,
        usdkrw_change_z=usdkrw_change / 0.006,
        kospi200_0905_return=kospi200_0905,
        theme_0905_return=theme_0905,
        spread_avg_ratio=max(1.0, max_spread_bps / 5.0),
        data_ok=data_ok,
    )


def apply_live_guards(decisions: Iterable[StrategyDecision], now: datetime, warnings: List[str]) -> List[StrategyDecision]:
    guarded: List[StrategyDecision] = []
    outside_entry = not in_entry_window(now)
    incomplete = bool(warnings)
    for decision in decisions:
        reasons = list(decision.no_trade_reasons)
        if outside_entry and "outside entry window" not in reasons:
            reasons.append("outside entry window")
        if incomplete and "live data warning" not in reasons:
            reasons.append("live data warning")
        guarded.append(
            StrategyDecision(
                code=decision.code,
                name=decision.name,
                fair_gap=decision.fair_gap,
                actual_gap=decision.actual_gap,
                gap_residual=decision.gap_residual,
                gap_residual_z=decision.gap_residual_z,
                score=decision.score,
                selected=decision.selected and not outside_entry and not incomplete,
                no_trade_reasons=reasons,
            )
        )
    return guarded


async def live_strategy_payload(kiwoom_client) -> Dict:
    now = datetime.now(KST)
    warnings: List[str] = []
    returns, overseas_warnings = await fetch_overseas_returns(OVERSEAS_SYMBOLS)
    warnings.extend(overseas_warnings)
    signals, overseas_ok = build_fair_gap_inputs(returns, warnings)
    snapshots, raw_quotes, domestic_warnings = await build_opening_snapshots(kiwoom_client)
    warnings.extend(domestic_warnings)
    data_ok = overseas_ok and len(snapshots) == len(ETF_TARGETS)
    quality = build_market_quality(returns, snapshots, raw_quotes, data_ok)
    decisions = evaluate_candidates(signals, snapshots, quality)
    guarded = apply_live_guards(decisions, now, warnings)
    return {
        "strategy": "Korea Overnight Lead-Lag 3 ETF Strategy v3",
        "data_mode": "live",
        "generated_at": now.isoformat(),
        "entry_window": "09:06-09:12",
        "data_sources": {
            "overseas": "Yahoo chart daily returns, FRED fallback for SP500/NASDAQ100/VIX/USDKRW",
            "domestic": "Kiwoom REST quote, daily chart, minute chart",
        },
        "warnings": warnings,
        "overseas_returns": serialize_returns(returns),
        "market_quality": asdict(quality),
        "snapshots": {code: asdict(snapshot) for code, snapshot in snapshots.items()},
        "quotes": raw_quotes,
        "decisions": [asdict(decision) for decision in guarded],
        "selected": [asdict(decision) for decision in guarded if decision.selected],
    }
