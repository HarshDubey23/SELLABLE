"""Generate a markdown + JSON report from eval results.

USAGE:
  python -m eval.run --out eval/results.json
  python -m eval.report --in eval/results.json --md eval/report.md --json eval/report.json
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path


def _metric_dict(value: object) -> dict:
    return {"value": value} if value is not None else {}


def render(results: dict) -> str:
    lines = ["# SELLABLE Eval Report\n"]
    h = results["headline"]
    lines.append("## Headline\n")
    lines.append(f"- **Gated vs Ungated revenue delta**: "
                 f"Rs. {h['gated_vs_ungated_revenue_delta_paise']/100:,.2f}")
    lines.append(f"- **Gated vs Static revenue delta**: "
                 f"Rs. {h['gated_vs_static_revenue_delta_paise']/100:,.2f}")
    lines.append(f"- **Gated injection resistance**: "
                 f"{h['gated_injection_resistance']:.1%}")
    lines.append(f"- **Ungated injection resistance**: "
                 f"{h['ungated_injection_resistance']:.1%}")
    lines.append(f"- **Fraud prevented (ungated loss)**: "
                 f"Rs. {h['fraud_prevented_paise']/100:,.2f}\n")

    metrics = results.get("metrics", {})
    lines.append("## V2 Metrics\n")
    lines.append("| Metric | Value |")
    lines.append("|---|---|")
    labels = {
        "acceptance_rate": "Acceptance rate",
        "aov_uplift": "AOV uplift (%)",
        "false_block_cost": "False block cost (₹)",
        "llm_fooled_rate": "LLM fooled rate",
        "money_loss_rate": "Ungated hypothetical money loss rate",
        "gated_actual_money_loss_rate": "Gated actual money loss rate",
        "negotiation_margin": "Negotiation margin (%)",
        "p95_latency": "p95 latency (ms)",
        "protocol_pass_rate": "Protocol pass rate",
    }
    for k, v in metrics.items():
        val = v.get("value") if isinstance(v, dict) else v
        if isinstance(val, float) and abs(val) < 1:
            disp = f"{val:.1%}"
        else:
            disp = f"{val}"
        lines.append(f"| {labels.get(k, k)} | {disp} |")

    lines.append("\n## Per-Arm Metrics\n")
    lines.append("| Metric | Static | Ungated | Gated |")
    lines.append("|---|---|---|---|")
    arms = {a["arm"]: a for a in results["arms"]}
    for label, key in [("Missions run", "missions_run"),
                        ("Approved", "approved"),
                        ("Rejected", "rejected"),
                        ("Acceptance rate", "acceptance_rate"),
                        ("Injections attempted", "injections_attempted"),
                        ("Injections blocked", "injections_blocked"),
                        ("Injection resistance", "injection_resistance"),
                        ("Gross revenue (Rs.)", "gross_revenue_paise"),
                        ("Fraud loss (Rs.)", "fraud_loss_paise"),
                        ("Trust-adj revenue (Rs.)", "trust_adjusted_revenue_paise"),
                        ("p95 latency (ms)", "p95_latency_ms"),
                        ("Llm fooled count", "llm_fooled_count"),
                        ("Llm fooled rate", "llm_fooled_rate"),
                        ("Gated actual money loss rate", "gated_actual_money_loss_rate")]:
        row = f"| {label} "
        for arm in ("static", "ungated", "gated"):
            v = arms.get(arm, {}).get(key, 0)
            if "revenue" in key or "loss" in key or "cost" in key:
                row += f"| Rs. {v/100:,.2f} "
            elif "rate" in key or "resistance" in key:
                row += f"| {v:.1%} " if isinstance(v, float) else f"| {v} "
            else:
                row += f"| {v} "
        row += "|"
        lines.append(row)

    lines.append("\n## Interpretation\n")
    lines.append("**Static arm** is the baseline: fixed catalog prices, no agent.")
    lines.append("**Ungated arm** simulates the naive 'just let the LLM decide' approach.")
    lines.append("**Gated arm** is SELLABLE — the gateway reads prices server-side.")
    lines.append("**behavioral_ungated_llm** and **behavioral_gated_llm** track "
                 "model-fooling vs money-loss separately.")
    return "\n".join(lines) + "\n"


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--in", dest="infile", default="eval/results.json")
    ap.add_argument("--out", default="eval/report.md")
    ap.add_argument("--json", default="eval/report.json")
    args = ap.parse_args()
    results = json.loads(Path(args.infile).read_text())

    md = render(results)
    Path(args.out).write_text(md, encoding="utf-8")

    # Build report.json with the exact required structure.
    metrics = results.get("metrics", {})
    report_metrics = {}
    for k in ("acceptance_rate", "aov_uplift", "false_block_cost",
              "llm_fooled_rate", "money_loss_rate", "negotiation_margin",
              "p95_latency", "protocol_pass_rate"):
        v = metrics.get(k)
        report_metrics[k] = v if isinstance(v, dict) else _metric_dict(v)

    report = {
        "metrics": report_metrics,
        "methodology": results.get("methodology", {}),
    }
    Path(args.json).write_text(json.dumps(report, indent=2),
                                encoding="utf-8")
    print(f"[report] {args.out}")
    print(f"[report] {args.json}")


if __name__ == "__main__":
    main()
