"""Generate a markdown report from eval results.

USAGE:
  python -m eval.run --out eval/results.json
  python -m eval.report --in eval/results.json --out eval/report.md
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path


def render(results: dict) -> str:
    lines = ["# SELLABLE Eval Report\n"]
    lines.append("## Headline\n")
    h = results["headline"]
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

    lines.append("## Per-Arm Metrics\n")
    lines.append("| Metric | Static | Ungated | Gated |")
    lines.append("|---|---|---|---|")
    arms = {a["arm"]: a for a in results["arms"]}
    metrics = [
        ("Missions run", "missions_run"),
        ("Approved", "approved"),
        ("Rejected", "rejected"),
        ("Acceptance rate", "acceptance_rate"),
        ("Injections attempted", "injections_attempted"),
        ("Injections blocked", "injections_blocked"),
        ("Injection resistance", "injection_resistance"),
        ("Gross revenue (Rs.)", "gross_revenue_paise"),
        ("Fraud loss (Rs.)", "fraud_loss_paise"),
        ("Recovery revenue (Rs.)", "recovery_revenue_paise"),
        ("Recovery cost (Rs.)", "recovery_cost_paise"),
        ("Trust-adjusted revenue (Rs.)", "trust_adjusted_revenue_paise"),
        ("Avg turns/negotiation", "avg_turns_per_negotiation"),
        ("p95 latency (ms)", "p95_latency_ms"),
    ]
    for label, key in metrics:
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
    lines.append("**Static arm** is the baseline: fixed catalog prices, no agent. "
                 "It earns gross revenue but has zero injection resistance and "
                 "zero recovery capability.")
    lines.append("")
    lines.append("**Ungated arm** simulates the naive 'just let the LLM decide' "
                 "approach. Every injected price slips through, causing fraud "
                 "loss equal to the catalog price minus the injected price. "
                 "This is the cost of not having a gateway.")
    lines.append("")
    lines.append("**Gated arm** is SELLABLE. The gateway reads prices server-side "
                 "(R3 price drift), so injections in the justification have NO "
                 "effect on the transaction. Injection resistance is ~100% by "
                 "construction. Recovery revenue from failed-then-link flows "
                 "adds trust-adjusted revenue the other arms cannot match.")
    return "\n".join(lines) + "\n"


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--in", dest="infile", default="eval/results.json")
    ap.add_argument("--out", default="eval/report.md")
    args = ap.parse_args()
    results = json.loads(Path(args.infile).read_text())
    Path(args.out).write_text(render(results))
    print(f"[eval] report -> {args.out}")


if __name__ == "__main__":
    main()
