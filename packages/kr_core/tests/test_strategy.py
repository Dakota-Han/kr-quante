import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1] / "src"
sys.path.insert(0, str(ROOT))

from kr_core.models import FairGapInput, MarketQuality, OpeningSnapshot  # noqa: E402
from kr_core.orders import OrderBlocked, OrderConfig, create_order_preview, validate_order_submission  # noqa: E402
from kr_core.strategy import compute_fair_gap, evaluate_candidates  # noqa: E402


class StrategyTests(unittest.TestCase):
    def test_fair_gap_is_positive_for_strong_semiconductor_signal(self):
        fair_gap = compute_fair_gap(
            FairGapInput(
                code="091160",
                overseas_theme_signal=0.02,
                kospi200_night=0.004,
                nasdaq100=0.01,
                usdkrw=-0.001,
                vix_change=-0.02,
            )
        )
        self.assertGreater(fair_gap, 0.01)

    def test_under_reacted_semiconductor_can_be_selected(self):
        signals = [
            FairGapInput(code="091160", overseas_theme_signal=0.02, kospi200_night=0.004, nasdaq100=0.01),
            FairGapInput(code="069500", overseas_theme_signal=0.002, kospi200_night=0.001),
            FairGapInput(code="305720", overseas_theme_signal=0.003, nasdaq100=0.002),
        ]
        snapshots = {
            "091160": OpeningSnapshot(
                code="091160",
                previous_close=45000,
                open_price=45200,
                price_0905=45350,
                vwap_0905=45330,
                volume_0905=300000,
                average_volume_0905=160000,
                bid=45340,
                ask=45350,
                premium_pct=0.0003,
                high_since_open=45400,
            ),
            "069500": OpeningSnapshot(
                code="069500",
                previous_close=40000,
                open_price=40010,
                price_0905=39980,
                vwap_0905=40000,
                volume_0905=200000,
                average_volume_0905=200000,
                bid=39975,
                ask=39980,
                premium_pct=0.0002,
                high_since_open=40040,
            ),
            "305720": OpeningSnapshot(
                code="305720",
                previous_close=12800,
                open_price=12820,
                price_0905=12810,
                vwap_0905=12818,
                volume_0905=80000,
                average_volume_0905=120000,
                bid=12805,
                ask=12815,
                premium_pct=0.0012,
                high_since_open=12830,
            ),
        }
        decisions = evaluate_candidates(
            signals,
            snapshots,
            MarketQuality(kospi200_0905_return=0.001, theme_0905_return=0.002),
            residual_stds={"091160": 0.004, "069500": 0.004, "305720": 0.004},
        )
        selected = [decision for decision in decisions if decision.selected]
        self.assertEqual(len(selected), 1)
        self.assertEqual(selected[0].code, "091160")

    def test_market_orders_and_unapproved_submit_are_blocked(self):
        decision = evaluate_candidates(
            [FairGapInput(code="091160", overseas_theme_signal=0.02, kospi200_night=0.004, nasdaq100=0.01)],
            {
                "091160": OpeningSnapshot(
                    code="091160",
                    previous_close=45000,
                    open_price=45200,
                    price_0905=45350,
                    vwap_0905=45330,
                    volume_0905=300000,
                    average_volume_0905=160000,
                    bid=45340,
                    ask=45350,
                    premium_pct=0.0003,
                    high_since_open=45400,
                )
            },
            MarketQuality(kospi200_0905_return=0.001, theme_0905_return=0.002),
            residual_stds={"091160": 0.004},
        )[0]
        preview = create_order_preview(decision, 10_000_000, 45350, 0.01)
        with self.assertRaises(OrderBlocked):
            validate_order_submission([preview], order_type="MKT", config=OrderConfig())
        with self.assertRaises(OrderBlocked):
            validate_order_submission([preview], order_type="LMT", config=OrderConfig())


if __name__ == "__main__":
    unittest.main()
