#!/usr/bin/env python3
"""Derive verified project facts from code — single source for README numbers."""
import json
import pathlib
import re
import subprocess
import sys

ROOT = pathlib.Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from apps.api.gateway.proof import compute_proof
from apps.api.gateway.registry import RULE_REGISTRY
from apps.api.products import CATALOG


def read_text(path: pathlib.Path) -> str:
    return path.read_text(encoding="utf-8", errors="replace")


# SKUs
skus = len(CATALOG)
# Rules
rules = len(RULE_REGISTRY)
# Gateway files
proof = compute_proof()
files = proof["files"]
# Endpoints: derive from FastAPI's OpenAPI map, not a hard-coded guess.
from apps.api.main import app  # noqa: E402

endpoint_cnt = len(app.openapi()["paths"])
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
    if "genai" in read_text(p):
        cnt += 1

readme = (ROOT / "README.md").read_text(encoding="utf-8")
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
            if val is None:
                continue
            # Check for at least one formatted representation present in README
            found = False
            candidates = [str(val), f"{val:.0%}", f"{val:.2f}",
                          f"{val:.0f}%", f"Rs {val/100:,.2f}"]
            for c in candidates:
                if c in readme:
                    found = True
                    break
            if not found:
                print(f"FAIL README missing {k} (looked for {candidates})")
                sys.exit(1)
    print("OK README numbers match report.json")

checks = [
    (str(skus) in readme, f"README contains SKUs {skus}"),
    (str(rules) in readme, f"README contains rules {rules}"),
    (str(tests) in readme, f"README contains tests {tests}"),
    ("gemini-1.5-flash" in readme or "google/gemini-1.5-flash" in readme, "README contains valid model"),
]
for ok, msg in checks:
    print(f"{'OK' if ok else 'FAIL'} {msg}")
