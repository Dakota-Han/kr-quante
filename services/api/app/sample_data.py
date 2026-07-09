from __future__ import annotations

from kr_core.models import FairGapInput, MarketQuality, OpeningSnapshot


def sample_signals():
    return [
        FairGapInput(
            code="069500",
            overseas_theme_signal=0.006,
            kospi200_night=0.004,
            ewy=0.005,
            nasdaq100=0.004,
            usdkrw=-0.001,
            vix_change=-0.02,
        ),
        FairGapInput(
            code="091160",
            overseas_theme_signal=0.018,
            kospi200_night=0.004,
            ewy=0.005,
            nasdaq100=0.009,
            usdkrw=-0.001,
            vix_change=-0.02,
        ),
        FairGapInput(
            code="305720",
            overseas_theme_signal=0.012,
            kospi200_night=0.004,
            ewy=0.005,
            nasdaq100=0.009,
            usdkrw=-0.001,
            vix_change=-0.02,
        ),
    ]


def sample_snapshots():
    return {
        "069500": OpeningSnapshot(
            code="069500",
            previous_close=40750,
            open_price=40880,
            price_0905=40920,
            vwap_0905=40900,
            volume_0905=240000,
            average_volume_0905=180000,
            bid=40915,
            ask=40920,
            premium_pct=0.0004,
            high_since_open=40950,
        ),
        "091160": OpeningSnapshot(
            code="091160",
            previous_close=45200,
            open_price=45500,
            price_0905=45620,
            vwap_0905=45580,
            volume_0905=360000,
            average_volume_0905=220000,
            bid=45600,
            ask=45620,
            premium_pct=0.0005,
            high_since_open=45650,
        ),
        "305720": OpeningSnapshot(
            code="305720",
            previous_close=12780,
            open_price=12820,
            price_0905=12830,
            vwap_0905=12832,
            volume_0905=110000,
            average_volume_0905=140000,
            bid=12825,
            ask=12835,
            premium_pct=0.0012,
            high_since_open=12860,
        ),
    }


def sample_quality():
    return MarketQuality(
        vix_change_z=-0.2,
        usdkrw_change_z=-0.1,
        kospi200_0905_return=0.001,
        theme_0905_return=0.002,
        spread_avg_ratio=1.1,
        data_ok=True,
    )
