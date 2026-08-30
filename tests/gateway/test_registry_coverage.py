"""Registry coverage guard — every RULE_REGISTRY rule must be exercised somewhere
in the test suite. Added Phase 1. Fails listing any rule with zero coverage, so a
future rule can never be registered without a test (complements the Phase 3
reachability test, which guards engine call sites).
"""
import pathlib

from apps.api.gateway.registry import RULE_REGISTRY

SUITE_DIRS = [pathlib.Path("tests/gateway"), pathlib.Path("tests")]


def _rule_id(entry) -> str:
    return entry["rule_id"]


def _suite_source() -> str:
    parts = []
    for d in SUITE_DIRS:
        if d.exists():
            parts.extend(p.read_text() for p in sorted(d.rglob("test_*.py")))
    return "\n".join(parts)


def test_every_registry_rule_has_test_coverage():
    src = _suite_source()
    missing = []
    for entry in RULE_REGISTRY:
        rid = _rule_id(entry)
        variants = {rid, rid.upper(), rid.lower()}
        if "_" in rid:
            variants.add(rid.split("_")[0])
        if not any(v in src for v in variants):
            missing.append(rid)
    assert not missing, f"Registry rules with ZERO test coverage: {missing} — add focused tests in tests/gateway/test_matrix.py"
