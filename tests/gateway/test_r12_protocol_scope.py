"""R12_PROTOCOL_SCOPE tests (Phase 4).

R12 binds protocol artifacts (merchant scope, category scope, amount
ceiling, validity window) at the gateway — rejecting with the drifted
field path. It is Phase 3 FATAL, sits after R11 in the evaluation order,
is fail-closed on malformed scope, and is skipped when scope is None
(native sellable-v1 traffic carries no protocol artifacts).
"""
import hashlib
import hmac
import json
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from apps.api.gateway.engine import evaluate
from apps.api.gateway.registry import RULE_BY_ID
from apps.api.gateway.types import Decision, Mission, Proposal, ProposalItem
from apps.api.gateway.rules_r12 import rule_r12_protocol_scope
from apps.api.products import CATALOG

TEST_KEY = "test-hmac-r12-key-only-for-tests"

NOW = 1_900_000_000


def _sign_blob(blob: dict) -> str:
    canonical = json.dumps(blob, sort_keys=True, separators=(",", ":"))
    return hmac.new(TEST_KEY.encode(), canonical.encode(), hashlib.sha256).hexdigest()


def _verify(blob: str, sig: str) -> bool:
    expected = hmac.new(TEST_KEY.encode(), blob.encode(), hashlib.sha256).hexdigest()
    return hmac.compare_digest(expected, sig)


def _mission(mission_id: str = "MSN-R12-001") -> Mission:
    m = Mission(
        mission_id=mission_id,
        intent="r12 scope test",
        budget_paise=500000,
        allowed_categories=("cricket",),
        forbidden_categories=(),
        upsell_cap=1.3,
        expires_at=NOW + 3600,
        signature="",
    )
    object.__setattr__(m, "signature", _sign_blob(
        {k: v for k, v in vars(m).items() if k != "signature"}))
    return m


def _proposal(skus: list[tuple[str, int]], mission_id: str = "MSN-R12-001") -> Proposal:
    items = tuple(ProposalItem(sku=s, qty=q, price_paise=CATALOG[s]["price_paise"])
                  for s, q in skus)
    return Proposal(mission_id=mission_id, items=items)


def _evaluate(proposal: Proposal, scope: dict | None, now_ts: int = NOW):
    return evaluate(mission=_mission(proposal.mission_id), proposal=proposal,
                    catalog=CATALOG, verify_fn=_verify, state={},
                    now_ts=now_ts, chain_ok=True, protocol_scope=scope)


def test_registry_entry_phase3_fatal():
    entry = RULE_BY_ID["R12_PROTOCOL_SCOPE"]
    assert entry["phase"] == 3 and entry["severity"] == "FATAL"


def test_scope_none_is_skipped_native_traffic():
    """No protocol artifacts -> R12 skipped; native 11-rule behavior intact."""
    v = _evaluate(_proposal([("BAT-001", 1)]), None)
    assert v.decision == Decision.APPROVE


def test_merchant_scope_drift_rejected_with_field_path():
    v = _evaluate(_proposal([("BAT-001", 1)]), {"merchant_id": "OTHER-SHOP"})
    assert v.decision == Decision.REJECT and v.rule_id == "R12_PROTOCOL_SCOPE"
    assert "OTHER-SHOP" in v.reason


def test_category_scope_drift_rejected_with_item_path():
    """I8 analog at the protocol layer: item outside the session's categories."""
    bat = CATALOG["BAT-001"]
    v = _evaluate(_proposal([("BAT-001", 1)]), {"category_scope": ["books"]})
    assert v.decision == Decision.REJECT and v.rule_id == "R12_PROTOCOL_SCOPE"
    assert f"items[0]" in v.reason and bat["category"] in v.reason


def test_amount_ceiling_drift_rejected():
    """Total above the protocol session's ceiling -> rejected with the path."""
    total = CATALOG["BAT-001"]["price_paise"] * 2
    v = _evaluate(_proposal([("BAT-001", 2)]),
                  {"amount_ceiling_paise": total - 1})
    assert v.decision == Decision.REJECT and v.rule_id == "R12_PROTOCOL_SCOPE"
    assert "amount ceiling" in v.reason


def test_amount_ceiling_respected_passes():
    total = CATALOG["BAT-001"]["price_paise"] * 2
    v = _evaluate(_proposal([("BAT-001", 2)]),
                  {"amount_ceiling_paise": total})
    assert v.decision == Decision.APPROVE


def test_validity_window_expired_rejected():
    """now >= valid_until -> rejected, citing the validity window."""
    v = _evaluate(_proposal([("BAT-001", 1)]), {"valid_until": NOW})
    assert v.decision == Decision.REJECT and v.rule_id == "R12_PROTOCOL_SCOPE"
    assert "expired" in v.reason


def test_validity_window_future_passes():
    v = _evaluate(_proposal([("BAT-001", 1)]), {"valid_until": NOW + 60})
    assert v.decision == Decision.APPROVE


def test_malformed_scope_fails_closed():
    """A non-object scope is a violation, never a pass."""
    v = _evaluate(_proposal([("BAT-001", 1)]), "not-a-dict")
    assert v.decision == Decision.REJECT and v.rule_id == "R12_PROTOCOL_SCOPE"


def test_malformed_scope_field_fails_closed():
    """Wrongly-typed artifact fields fail closed too."""
    for bad in ({"merchant_id": 42}, {"category_scope": "cricket"},
                {"amount_ceiling_paise": True}, {"valid_until": "soon"}):
        v = _evaluate(_proposal([("BAT-001", 1)]), bad)
        assert v.decision == Decision.REJECT, bad
        assert v.rule_id == "R12_PROTOCOL_SCOPE", bad


def test_full_scope_happy_path():
    scope = {"merchant_id": "SELLABLE-DEMO",
             "category_scope": ["cricket"],
             "amount_ceiling_paise": CATALOG["BAT-001"]["price_paise"] * 5,
             "valid_until": NOW + 600}
    v = _evaluate(_proposal([("BAT-001", 2)]), scope)
    assert v.decision == Decision.APPROVE


def test_r12_fires_after_r3_first_violation_wins():
    """R12 sits after R11: a price-drift proposal must cite R3, not R12."""
    drifted = Proposal(mission_id="MSN-R12-001", items=(
        ProposalItem(sku="BAT-001", qty=1,
                     price_paise=CATALOG["BAT-001"]["price_paise"] + 1),))
    v = _evaluate(drifted, {"merchant_id": "OTHER-SHOP"})
    assert v.decision == Decision.REJECT
    assert v.rule_id == "R3_PRICE_DRIFT", "first violation wins: R3 before R12"


def test_rule_function_unit_skip_and_violation():
    """Unit level: rule_r12_protocol_scope returns None on None scope."""
    p = _proposal([("BAT-001", 1)])
    assert rule_r12_protocol_scope(p, CATALOG, None,
                                   merchant_id="SELLABLE-DEMO",
                                   now_ts=NOW) is None
    v = rule_r12_protocol_scope(p, CATALOG, {"merchant_id": "X"},
                                merchant_id="SELLABLE-DEMO", now_ts=NOW)
    assert v is not None and v.rule_id == "R12_PROTOCOL_SCOPE"
