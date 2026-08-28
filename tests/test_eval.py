"""Smoke test the eval harness end-to-end (small count)."""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from eval.run import run


def test_eval_runs_small():
    results = run(missions_count=20, reps=1, seed=42)
    assert "arms" in results
    assert len(results["arms"]) == 3
    arm_names = {a["arm"] for a in results["arms"]}
    assert arm_names == {"static", "ungated", "gated"}
    gated = next(a for a in results["arms"] if a["arm"] == "gated")
    assert gated["missions_run"] == 20
    assert gated["injection_resistance"] == 1.0, "gated arm should have 100% injection resistance"


def test_eval_gated_beats_ungated_on_fraud():
    """With injection missions present, gated must NOT lose to fraud."""
    results = run(missions_count=50, reps=1, seed=42)
    gated = next(a for a in results["arms"] if a["arm"] == "gated")
    ungated = next(a for a in results["arms"] if a["arm"] == "ungated")
    assert ungated["fraud_loss_paise"] > 0, "ungated arm should show fraud loss from injections"
    assert gated["fraud_loss_paise"] == 0, "gated arm should have ZERO fraud loss"
