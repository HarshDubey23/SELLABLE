#!/usr/bin/env python3
"""Fail if the README claims a number the evidence file does not support.

The rule this enforces: every number in the README comes from
`docs/generated/truth.json`, which `scripts/generate_truth.py` produces
by running the thing being measured. Documentation drifts silently;
a build step that fails when it does is the only thing that stops it.

    python scripts/verify_readme.py

Exit code 0 when the README agrees with the evidence, 1 when it does not.
"""
from __future__ import annotations

import json
import re
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
README = REPO / "README.md"
TRUTH = REPO / "docs" / "generated" / "truth.json"


def main() -> int:
    if not TRUTH.exists():
        print(f"FAIL  {TRUTH.relative_to(REPO)} is missing — run "
              f"'python scripts/generate_truth.py'")
        return 1

    truth = json.loads(TRUTH.read_text(encoding="utf-8"))
    readme = README.read_text(encoding="utf-8")
    tests = truth["tests"]
    code = truth["codebase"]
    adv = truth["adversarial"]
    lat = truth["gateway_latency"]

    failures: list[str] = []
    checks: list[tuple[str, bool, str]] = []

    def expect(label: str, needle: str, why: str = "") -> None:
        ok = needle in readme
        checks.append((label, ok, needle))
        if not ok:
            failures.append(f"README does not contain {needle!r} ({label}). {why}")

    expect("test pass count", f"**{tests['passed']} passed**")
    expect("skipped count", f"{tests['skipped']} skipped")
    expect("policy rule count", f"| {code['gateway_rules']}, in one canonical registry")
    expect("catalog size", f"| {code['catalog_skus']} SKUs |")
    expect("adversarial result",
           f"**{adv['scenarios_blocked']} of {adv['scenarios_total']} blocked**")
    expect("p95 latency", f"p95 {lat['p95_ms']:.3f} ms")

    # Nothing may claim a passing suite while the suite is red.
    if not tests["all_green"]:
        failures.append(
            f"the evidence file records a failing suite "
            f"({tests['failed']} failed, {tests['errors']} errors) — "
            f"regenerate it against a green run before publishing numbers")

    # Numbers that used to be hardcoded in the README and must never return.
    for banned, reason in [
        ("142 Passed", "stale badge from an earlier test count"),
        ("Attacks Blocked-20", "there are 8 adversarial scenarios, not 20"),
        ("Money Loss Rate-0%", "not a measured quantity in this repository"),
        ("45.02", "eval AOV figure whose provenance did not survive review"),
    ]:
        if banned in readme:
            failures.append(f"README still contains {banned!r} — {reason}")

    # Every bare percentage should be traceable; flag the shapes that used to
    # appear as unsupported marketing.
    for pattern, reason in [
        (r"\b100% (secure|safe|unhackable)", "unfalsifiable security claim"),
        (r"\bzero vulnerabilit", "unfalsifiable security claim"),
    ]:
        if re.search(pattern, readme, re.IGNORECASE):
            failures.append(f"README contains an unfalsifiable claim ({reason})")

    width = max(len(label) for label, _, _ in checks)
    for label, ok, needle in checks:
        print(f"  [ {'PASS' if ok else 'FAIL'} ] {label:<{width}}  {needle}")

    if failures:
        print()
        for f in failures:
            print(f"FAIL  {f}")
        print("\nRegenerate the evidence and update the README:")
        print("  python scripts/generate_truth.py")
        return 1

    print(f"\nREADME agrees with docs/generated/truth.json "
          f"(generated {truth['generated_at']}, commit "
          f"{truth['git']['commit_short']}).")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
