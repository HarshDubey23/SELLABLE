#!/usr/bin/env python3
"""Generate docs/generated/truth.json — the only source of numbers.

RULE: if a number appears in the README, the UI, or a slide, it is either
produced by this script from a real run, or it does not appear.

Everything here is measured now, on this checkout, by executing the thing
being measured. Nothing is transcribed from a previous run and nothing is
aspirational. Where a number cannot be measured in this environment (a
live Razorpay call, a live web search), the file records that it was not
measured rather than substituting a plausible figure.

    python scripts/generate_truth.py
"""
from __future__ import annotations

import datetime as dt
import json
import os
import platform
import re
import statistics
import subprocess
import sys
import tempfile
import time
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO))
OUT = REPO / "docs" / "generated" / "truth.json"


def _run(cmd: list[str], timeout: int = 900) -> subprocess.CompletedProcess:
    return subprocess.run(cmd, cwd=REPO, capture_output=True, text=True,
                          timeout=timeout)


def git_facts() -> dict:
    def g(*args: str) -> str:
        p = _run(["git", *args], timeout=30)
        return p.stdout.strip() if p.returncode == 0 else "unavailable"

    status = g("status", "--porcelain")
    return {
        "commit": g("rev-parse", "HEAD"),
        "commit_short": g("rev-parse", "--short", "HEAD"),
        "branch": g("rev-parse", "--abbrev-ref", "HEAD"),
        "commit_count": g("rev-list", "--count", "HEAD"),
        "working_tree_clean": status == "",
        "uncommitted_files": len([ln for ln in status.splitlines() if ln.strip()]),
    }


def test_facts() -> dict:
    """Run the suite for real and parse the outcome."""
    proc = _run([sys.executable, "-m", "pytest", "-q", "--tb=no"], timeout=1800)
    tail = (proc.stdout + proc.stderr).strip().splitlines()
    summary = next((ln for ln in reversed(tail)
                    if re.search(r"\d+ (passed|failed|error)", ln)), "")
    clean = re.sub(r"\x1b\[[0-9;]*m", "", summary)

    def grab(word: str) -> int:
        m = re.search(rf"(\d+) {word}", clean)
        return int(m.group(1)) if m else 0

    passed, failed = grab("passed"), grab("failed")
    errors, skipped = grab("error"), grab("skipped")

    # Per-area counts, so the README can say what is actually covered.
    areas: dict[str, int] = {}
    collect = _run([sys.executable, "-m", "pytest", "--collect-only", "-q"],
                   timeout=600)
    for line in collect.stdout.splitlines():
        if "::" not in line:
            continue
        path = line.split("::")[0]
        parts = Path(path).parts
        area = parts[1] if len(parts) > 2 else Path(path).stem
        areas[area] = areas.get(area, 0) + 1

    return {
        "command": "python -m pytest -q",
        "passed": passed,
        "failed": failed,
        "errors": errors,
        "skipped": skipped,
        "total_collected": passed + failed + errors + skipped,
        "exit_code": proc.returncode,
        "all_green": proc.returncode == 0 and failed == 0 and errors == 0,
        "summary_line": clean,
        "tests_by_area": dict(sorted(areas.items(), key=lambda kv: -kv[1])),
    }


# Named explicitly, so a new virtualenv or vendored dependency cannot
# quietly join the count.
FIRST_PARTY_SOURCE_DIRS = ("apps", "tests", "scripts", "eval",
                           "external_buyer", "mcp_server")


def codebase_facts() -> dict:
    from apps.api import execution as ex
    from apps.api.gateway.registry import RULE_REGISTRY
    from apps.api.products import CATALOG

    # Count first-party source by naming the directories, not by excluding
    # the ones we happen to remember. An earlier version filtered ".venv"
    # and then counted a second virtualenv at "venv/", reporting 1.3 million
    # lines of "our" code. A metric that large is obviously wrong; a metric
    # only twice as large as it should be would not have been caught.
    py_files = [
        f
        for d in FIRST_PARTY_SOURCE_DIRS
        for f in (REPO / d).rglob("*.py")
        if "__pycache__" not in f.parts
    ]
    py_files += [f for f in REPO.glob("*.py")]
    loc = sum(len(f.read_text(encoding="utf-8", errors="ignore").splitlines())
              for f in py_files)

    return {
        "python_files": len(py_files),
        "python_lines": loc,
        "counted_from": sorted(FIRST_PARTY_SOURCE_DIRS) + ["*.py at the repo root"],
        "gateway_rules": len(RULE_REGISTRY),
        "gateway_rule_ids": [r["rule_id"] for r in RULE_REGISTRY],
        "catalog_skus": len(CATALOG),
        "execution_states": list(ex.ALL_STATES),
        "execution_terminal_states": sorted(ex.TERMINAL_STATES),
        "money_boundary_module": "apps/api/razorpay_client.py",
        "provider_boundary_module": "apps/api/execution_provider.py",
        "audit_hash_algorithm": "SHA-256",
    }


def gateway_latency_facts(iterations: int = 2000) -> dict:
    """Measure the deterministic gateway. No network, no LLM, no I/O."""
    from apps.api.gateway.engine import evaluate
    from apps.api.gateway.types import Mission, Proposal, ProposalItem
    from apps.api.products import CATALOG

    now = int(time.time())
    blob = {
        "mission_id": "BENCH-001", "intent": "benchmark",
        "budget_paise": 500000, "allowed_categories": ("cricket",),
        "forbidden_categories": (), "upsell_cap": 1.0,
        "expires_at": now + 3600,
    }
    mission = Mission(signature="bench", **blob)
    proposal = Proposal(mission_id="BENCH-001",
                        items=(ProposalItem(sku="BAT-001", qty=1,
                                            price_paise=149900),))

    samples: list[float] = []
    for _ in range(iterations):
        t0 = time.perf_counter()
        evaluate(mission=mission, proposal=proposal, catalog=CATALOG,
                 verify_fn=lambda blob, sig: True, state={}, now_ts=now,
                 chain_ok=True)
        samples.append((time.perf_counter() - t0) * 1000.0)

    samples.sort()

    def pct(p: float) -> float:
        return round(samples[min(int(len(samples) * p), len(samples) - 1)], 4)

    return {
        "iterations": iterations,
        "p50_ms": pct(0.50),
        "p95_ms": pct(0.95),
        "p99_ms": pct(0.99),
        "mean_ms": round(statistics.mean(samples), 4),
        "max_ms": round(samples[-1], 4),
        "measured_on": f"{platform.system()} python{sys.version_info.major}."
                       f"{sys.version_info.minor}",
        "note": ("in-process evaluation of R1-R12 only; excludes HTTP, "
                 "persistence and the audit append. Machine-dependent."),
    }


def attack_facts() -> dict:
    """Actually run every adversarial scenario and record the real verdicts."""
    from fastapi.testclient import TestClient

    from apps.api import money
    from apps.api.main import app

    money.reset()
    client = TestClient(app)
    resp = client.post("/attack/run_all")
    if resp.status_code != 200:
        return {"ran": False, "reason": f"HTTP {resp.status_code}"}

    data = resp.json()
    snapshot = money.snapshot()
    results = data.get("results", data.get("scenarios", []))
    return {
        "ran": True,
        "scenarios_total": data.get("scenarios_total"),
        "scenarios_blocked": data.get("scenarios_blocked"),
        "block_rate": data.get("block_rate"),
        "money_boundary_calls_during_attacks": snapshot["boundary_calls"],
        "money_call_invariant_held": snapshot["boundary_calls"] == 0,
        "per_scenario": [
            {"id": r.get("id"),
             "label": r.get("label"),
             "blocked_by": r.get("blocked_by"),
             "gateway_decision": r.get("decision"),
             "gateway_rule": r.get("rule_id"),
             "money_calls": r.get("money_calls"),
             "safe": r.get("safe")}
            for r in results
        ] if isinstance(results, list) else [],
    }


def runtime_facts() -> dict:
    from apps.api import execution_provider as prov
    from apps.api.config import get as cfg

    c = cfg()
    return {
        "payment_provider": prov.provider_name(),
        "payment_provider_description": prov.mode_description(),
        "razorpay_credentials_present": prov.razorpay_credentials_present(),
        "llm_configured": c.llm_configured,
        "llm_model": c.gemini_model if c.llm_configured
                     else "deterministic fallback (no LLM key configured)",
        "policy_version": c.policy_version,
        "mandate_version": c.mandate_version,
        "note": ("describes the environment this file was generated in. A "
                 "clone with Razorpay test keys reports payment_provider="
                 "razorpay_test instead."),
    }


NOT_MEASURED_HERE = {
    "live_razorpay_order_creation": (
        "requires RAZORPAY_KEY_ID / RAZORPAY_KEY_SECRET and outbound network "
        "access to api.razorpay.com. Not exercised in this generation run."),
    "live_web_discovery_results": (
        "depends on a third-party search endpoint being reachable; result "
        "counts are not reproducible and are therefore never quoted as a "
        "metric. The pipeline reports SEARCH_UNAVAILABLE when providers fail."),
    "live_llm_agent_behaviour": (
        "requires an LLM API key. With none configured the buyer agent uses a "
        "deterministic picker; either way it holds no money authority."),
}

KNOWN_LIMITATIONS = [
    "Missions and user mandates are signed out-of-band by scripts/sign_mission.py "
    "and scripts/mandate.py. The browser demo path signs them in-process via "
    "apps/api/issuer.py, which proves integrity but not custody; this is "
    "disclosed in every response it produces as authorization_issued_by.",
    "The merchant catalog is a fixed in-repo dataset. External discovery is "
    "market evidence only — SELLABLE can only sell SKUs it stocks.",
    "eval/ is a seeded simulation of the policy gateway over synthetic "
    "missions. It is not a live-model benchmark and its numbers are not "
    "quoted as headline claims.",
    "Reconciliation matches remote orders on correlation fields written into "
    "the order notes, because Razorpay exposes no public fetch-by-"
    "idempotency-key lookup. A provider that drops notes would defeat it.",
    "Single-node SQLite. Concurrency safety is enforced by conditional UPDATE "
    "statements within one process and one database file; a multi-node "
    "deployment would need the same guards at the database level.",
]


def main() -> int:
    os.environ.setdefault("SELLABLE_DB_PATH",
                          str(Path(tempfile.mkdtemp()) / "truth.db"))
    os.environ.setdefault("MISSION_HMAC_KEY", "truthgen" * 4)
    os.environ.setdefault("APP_API_KEY", "truthgen-api-key")
    os.environ.setdefault("USER_MANDATE_KEY", "truthgen" * 4)

    print("[truth] measuring codebase ...")
    codebase = codebase_facts()
    print("[truth] benchmarking gateway ...")
    latency = gateway_latency_facts()
    print("[truth] running adversarial scenarios ...")
    attacks = attack_facts()
    print("[truth] running the test suite (this takes a moment) ...")
    tests = test_facts()

    payload = {
        "$schema_note": ("Generated by scripts/generate_truth.py. Do not edit "
                         "by hand — regenerate. Every number in the README "
                         "comes from this file."),
        "generated_at": dt.datetime.now(dt.timezone.utc).isoformat(),
        "git": git_facts(),
        "tests": tests,
        "codebase": codebase,
        "gateway_latency": latency,
        "adversarial": attacks,
        "runtime": runtime_facts(),
        "not_measured_in_this_run": NOT_MEASURED_HERE,
        "known_limitations": KNOWN_LIMITATIONS,
    }

    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")
    print(f"[truth] wrote {OUT.relative_to(REPO)}")
    print(f"[truth] tests: {tests['passed']} passed, {tests['failed']} failed, "
          f"{tests['skipped']} skipped")
    print(f"[truth] gateway p95: {latency['p95_ms']} ms")
    print(f"[truth] attacks: {attacks.get('scenarios_blocked')}/"
          f"{attacks.get('scenarios_total')} blocked, "
          f"{attacks.get('money_boundary_calls_during_attacks')} money calls")
    return 0 if tests["all_green"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
