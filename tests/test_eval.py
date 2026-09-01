"""Smoke test the eval harness end-to-end (small count)."""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from eval.run import run


def test_eval_runs_small():
    results = run(missions_count=20, reps=1, seed=42)
    assert "arms" in results
    assert len(results["arms"]) == 5
    arm_names = {a["arm"] for a in results["arms"]}
    assert "static" in arm_names
    assert "ungated" in arm_names
    assert "gated" in arm_names
    assert "behavioral_ungated_llm" in arm_names
    assert "behavioral_gated_llm" in arm_names
    gated = next(a for a in results["arms"] if a["arm"] == "gated")
    assert gated["missions_run"] == 20
    assert gated["injections_blocked"] == gated["injections_attempted"]


def test_eval_gated_beats_ungated_on_fraud():
    """With injection missions present, gated must NOT lose to fraud."""
    results = run(missions_count=50, reps=1, seed=42)
    gated = next(a for a in results["arms"] if a["arm"] == "gated")
    ungated = next(a for a in results["arms"] if a["arm"] == "ungated")
    assert ungated["fraud_loss_paise"] > 0, "ungated arm should show fraud loss from injections"
    assert gated["fraud_loss_paise"] == 0, "gated arm should have ZERO fraud loss"


def test_report_json_has_all_8_metrics():
    """eval/report.json must contain the 8 required metric keys."""
    import json
    results = run(missions_count=20, reps=1, seed=42)
    from eval.report import main as report_main
    import tempfile, os
    tmp = tempfile.mkdtemp()
    results_path = os.path.join(tmp, "results.json")
    Path(results_path).write_text(json.dumps(results))
    # Call report_main via argparse (no positional args)
    old_argv = sys.argv
    sys.argv = ["eval.report", "--in", results_path,
                "--out", os.path.join(tmp, "report.md"),
                "--json", os.path.join(tmp, "report.json")]
    try:
        report_main()
    finally:
        sys.argv = old_argv
    rp = json.loads(Path(os.path.join(tmp, "report.json")).read_text())
    required = ["acceptance_rate", "aov_uplift", "false_block_cost",
                 "llm_fooled_rate", "money_loss_rate",
                 "negotiation_margin", "p95_latency", "protocol_pass_rate"]
    for k in required:
        assert k in rp["metrics"], f"missing metric: {k}"
    assert "methodology" in rp
    assert rp["methodology"]["llm_mode"] == "mock"
    assert rp["methodology"]["seed"] == 42


def test_gated_money_loss_rate_is_zero():
    """Gated arm must have 0% money loss — the core guarantee."""
    results = run(missions_count=20, reps=1, seed=42)
    gated = next(a for a in results["arms"] if a["arm"] == "gated")
    records = gated.get("records", [])
    if records:
        rate = sum(1 for r in records if r.get("money_loss")) / len(records)
    else:
        rate = 0.0
    assert rate == 0.0, f"gated money_loss_rate={rate} — must be 0.0"


def test_report_regeneration():
    """Results and report regenerate without error."""
    results = run(missions_count=10, reps=1, seed=42)
    assert "arms" in results
    assert "metrics" in results
    assert "methodology" in results