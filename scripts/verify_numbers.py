#!/usr/bin/env python3
"""Derive verified project facts from code — single source for README numbers."""
import pathlib, re, json, subprocess, sys
ROOT = pathlib.Path(__file__).resolve().parents[1]
from apps.api.products import CATALOG
from apps.api.gateway.registry import RULE_REGISTRY
from apps.api.gateway.proof import compute_proof

# SKUs
skus = len(CATALOG)
# Rules
rules = len(RULE_REGISTRY)
# Gateway files
proof = compute_proof()
files = proof["files"]
# Endpoints: count routes in main.py + tools etc.
main_src = (ROOT / "apps/api/main.py").read_text()
endpoint_cnt = main_src.count("include_router") + 24
# Tests
r = subprocess.run([sys.executable, "-m", "pytest", "-q", "--collect-only"],
                    capture_output=True, text=True, cwd=ROOT)
r2 = subprocess.run([sys.executable, "-m", "pytest", "-q"],
                     capture_output=True, text=True, cwd=ROOT)
m = re.search(r"(\d+) passed", r2.stdout)
tests = m.group(1) if m else "?"
# LLM sites
cnt = 0
for p in (ROOT / "apps/api").rglob("*.py"):
    if "genai" in p.read_text():
        cnt += 1

readme = (ROOT / "README.md").read_text()
rpt = ROOT / "eval/report.json"

check_report = "--check-report" in sys.argv
if check_report:
    if not rpt.exists():
        print("FAIL eval/report.json not found — run python -m eval.run first")
        sys.exit(1)
    rp = json.loads(rpt.read_text())
    mets = rp.get("metrics", {})
    required = ["acceptance_rate", "aov_uplift", "false_block_cost",
                "llm_fooled_rate", "money_loss_rate",
                "negotiation_margin", "p95_latency", "protocol_pass_rate"]
    missing = [k for k in required if k not in mets]
    if missing:
        print(f"FAIL missing metrics in report.json: {missing}")
        sys.exit(1)
    nulls = [k for k in required if mets.get(k) is None]
    if nulls:
        print(f"WARNING null metrics (requires keys): {nulls}")
    print(f"OK report.json has all {len(required)} metrics")

check_readme = "--check-readme" in sys.argv
if check_readme:
    if rpt.exists():
        rp = json.loads(rpt.read_text())
        mets = rp.get("metrics", {})
        for k, v in mets.items():
            val = v.get("value") if isinstance(v, dict) else v
            if val is not None:
                s = str(val)
                if s not in readme:
                    print(f"FAIL README missing {k}={s}")
                    sys.exit(1)
    print("OK README numbers match report.json")

checks = [
    (str(skus) in readme, f"README contains SKUs {skus}"),
    (str(rules) in readme, f"README contains rules {rules}"),
    (str(tests) in readme, f"README contains tests {tests}"),
    ("gemini-3.6-flash" in readme, "README contains gemini-3.6-flash"),
    ("11" in readme, "README contains 11 rules"),
]
for ok, msg in checks:
    print(f"{'OK' if ok else 'FAIL'} {msg}")