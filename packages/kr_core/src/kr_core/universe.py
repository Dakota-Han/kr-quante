from __future__ import annotations

from .models import EtfTarget


ETF_TARGETS = {
    "069500": EtfTarget(
        code="069500",
        name="KODEX 200",
        theme="market_beta",
        max_weight_initial=0.20,
        max_weight_normal=0.30,
        min_stop_pct=0.0050,
        max_stop_pct=0.0090,
        max_slippage_pct=0.0006,
    ),
    "091160": EtfTarget(
        code="091160",
        name="KODEX Semiconductors",
        theme="semiconductor",
        max_weight_initial=0.20,
        max_weight_normal=0.28,
        min_stop_pct=0.0070,
        max_stop_pct=0.0120,
        max_slippage_pct=0.0010,
    ),
    "305720": EtfTarget(
        code="305720",
        name="KODEX Secondary Battery Industry",
        theme="battery",
        max_weight_initial=0.15,
        max_weight_normal=0.20,
        min_stop_pct=0.0080,
        max_stop_pct=0.0140,
        max_slippage_pct=0.0012,
        stricter=True,
    ),
}


LEAD_INDICATORS = {
    "069500": ["KOSPI200_NIGHT", "EWY", "SPX", "NDX", "USDKRW", "VIX"],
    "091160": ["SOX", "SOXX", "SMH", "NVDA", "MU", "AMD", "TSM", "NDX"],
    "305720": ["TSLA", "LIT", "BATT", "ALB", "SQM", "NDX", "USDKRW"],
}
