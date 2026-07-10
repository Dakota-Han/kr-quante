from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Dict, Optional

from .universe import ETF_TARGETS


@dataclass(frozen=True)
class NormalizedQuote:
    code: str
    name: str
    bid: int
    ask: int
    bid_size: int
    ask_size: int
    mid: float
    spread: int
    spread_bps: float
    timestamp: str
    return_code: Optional[int] = None
    return_msg: Optional[str] = None


def parse_kiwoom_int(value: Any) -> int:
    if value is None:
        return 0
    text = str(value).strip().replace(",", "")
    if not text:
        return 0
    # Kiwoom often prefixes prices with +/- as a direction marker. Prices and
    # order sizes should be normalized as positive magnitudes for quote math.
    if text[0] in {"+", "-"}:
        text = text[1:]
    if not text:
        return 0
    try:
        return abs(int(float(text)))
    except ValueError:
        return 0


def normalize_kiwoom_quote(code: str, raw: Dict[str, Any]) -> NormalizedQuote:
    bid = parse_kiwoom_int(raw.get("buy_fpr_bid") or raw.get("buy_1th_pre_bid"))
    ask = parse_kiwoom_int(raw.get("sel_fpr_bid") or raw.get("sel_1th_pre_bid"))
    bid_size = parse_kiwoom_int(raw.get("buy_fpr_req") or raw.get("buy_1th_pre_req"))
    ask_size = parse_kiwoom_int(raw.get("sel_fpr_req") or raw.get("sel_1th_pre_req"))
    mid = (bid + ask) / 2.0 if bid and ask else 0.0
    spread = ask - bid if bid and ask else 0
    spread_bps = spread / mid * 10_000 if mid > 0 else 0.0
    target = ETF_TARGETS.get(code)
    return NormalizedQuote(
        code=code,
        name=target.name if target else code,
        bid=bid,
        ask=ask,
        bid_size=bid_size,
        ask_size=ask_size,
        mid=mid,
        spread=spread,
        spread_bps=spread_bps,
        timestamp=str(raw.get("bid_req_base_tm") or ""),
        return_code=raw.get("return_code"),
        return_msg=raw.get("return_msg"),
    )
