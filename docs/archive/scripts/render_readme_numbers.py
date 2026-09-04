#!/usr/bin/env python3
"""Render the README numbers strip from eval/report.json."""
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
rpt = ROOT / "eval/report.json"

if not rpt.exists():
    print("eval/report.json not found — run python -m eval.run first", file=sys.stderr)
    sys.exit(1)

rp = json.loads(rpt.read_text(encoding="utf-8"))
m = rp.get("metrics", {})

def g(k):
    v = m.get(k)
    if isinstance(v, dict):
        return v.get("value")
    return v

lines = [
    f"{g('acceptance_rate'):.0%}  acceptance rate",
    f"{g('aov_uplift'):.0f}%  AOV uplift",
    f"Rs {g('false_block_cost')/100:,.2f}  false block cost",
    f"{g('llm_fooled_rate'):.0%}  LLM fooled",
    f"{g('money_loss_rate'):.0%}  money loss",
    f"{g('negotiation_margin'):.0f}%  negotiation margin",
    f"{g('p95_latency'):.1f} ms  p95 latency",
    f"{g('protocol_pass_rate'):.0%}  protocol pass rate",
]
print(" | ".join(lines))
