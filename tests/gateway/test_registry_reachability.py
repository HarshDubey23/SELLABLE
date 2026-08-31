"""Registry reachability guard (F-06, Phase 3).

F-06 was a try/except ImportError around the R11 import in engine.py: if the
module vanished, the engine silently skipped the rule. This test makes that
class of defect impossible forever:
  (a) every RULE_REGISTRY rule must have a call site in engine.py
  (b) the rules_r11 import must be at module top (column 0), never inside a block
  (c) no `except ImportError` may ever appear in the engine again
  (d) the registry count is pinned to EXPECTED_RULE_COUNT

Phase 4 registers R12 (and R13): bump EXPECTED_RULE_COUNT — one line, one place.
"""
import pathlib

from apps.api.gateway.registry import RULE_REGISTRY

EXPECTED_RULE_COUNT = 12  # Phase 4: R12_PROTOCOL_SCOPE. (R13 cut — cut-line-able; see docs/log/day08.md)

ENGINE_SRC = pathlib.Path("apps/api/gateway/engine.py").read_text()


def _callable_name(entry) -> str:
    """Registry entries are dicts keyed 'rule_id' (FACT 2, e.g. 'R1_BUDGET');
    the engine calls plain functions named rule_<rule_id lowercased>:
    R11_NEGOTIATION_BOUND -> rule_r11_negotiation_bound."""
    return "rule_" + entry["rule_id"].lower()


def test_no_silent_import_degradation_in_engine():
    """(c) The engine must never swallow an ImportError. Fail-open is banned."""
    assert "except ImportError" not in ENGINE_SRC


def test_rules_r11_imported_at_module_top():
    """(b) The R11 import exists and is at column 0 — module level, outside any
    try block."""
    lines = ENGINE_SRC.splitlines()
    hits = [line for line in lines if "rules_r11" in line and "import" in line]
    assert hits, "no import of rules_r11 found in engine.py"
    for line in hits:
        assert not line.startswith((" ", "\t")), (
            f"rules_r11 import is indented (inside a block?): {line!r}"
        )


def test_registry_count_matches_expected():
    """(d) Registry size is pinned; adding a rule is a deliberate act."""
    assert len(RULE_REGISTRY) == EXPECTED_RULE_COUNT


def test_every_registry_rule_has_engine_call_site():
    """(a) A registered rule with no call site is unreachable — the F-06 bug
    class. The engine dispatches via explicit calls (verified Phase 3), so the
    call-name check is the correct reachability assertion."""
    missing = []
    for entry in RULE_REGISTRY:
        name = _callable_name(entry)
        if f"{name}(" not in ENGINE_SRC:
            missing.append(name)
    assert not missing, f"Registered rules with NO call site in engine.py: {missing}"
