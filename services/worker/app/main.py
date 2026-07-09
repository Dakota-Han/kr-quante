from __future__ import annotations

from dataclasses import asdict

from kr_core.orders import create_order_preview
from kr_core.risk import RiskConfig
from kr_core.strategy import evaluate_candidates

from app.sample_data import sample_quality, sample_signals, sample_snapshots


def run_signal_preview(account_equity: float = 10_000_000):
    decisions = evaluate_candidates(sample_signals(), sample_snapshots(), sample_quality())
    selected = next((decision for decision in decisions if decision.selected), None)
    if selected is None:
        return {"status": "no_trade", "decisions": [asdict(decision) for decision in decisions]}

    snapshot = sample_snapshots()[selected.code]
    preview = create_order_preview(
        selected,
        account_equity=account_equity,
        reference_price=snapshot.price_0905,
        raw_stop_pct=0.01,
        risk_config=RiskConfig(),
    )
    return {"status": "preview", "decision": asdict(selected), "preview": asdict(preview)}


if __name__ == "__main__":
    print(run_signal_preview())
