"""Every field of the approval binding must be load-bearing.

A binding that only checks the amount lets an attacker swap the cart. One
that only checks the cart lets them swap the mission. The point of
binding "every economically relevant value" is that changing ANY of them
breaks authorization, so this test walks the whole matrix and asserts the
specific refusal code for each.

Replaces two script-style files that sat uncollected at the repository
root (pytest's testpaths is `tests`), one of which had rotted against the
current mandate API and carried a hardcoded Windows path.
"""
import time

import pytest

from apps.api import approval

BASE = {
    "mission_id": "mission-matrix",
    "proposal_hash": "a" * 64,
    "cart_hash": "a" * 64,
    "quote_id": "",
    "amount_paise": 149900,
    "currency": "INR",
    "skus": [("BAT-001", 1)],
}


def _register(seq: int, **overrides):
    args = {**BASE, **overrides}
    return approval.register(seq=seq, now_ts=int(time.time()), **args)


def _verify(seq: int, **overrides):
    args = {**BASE, **overrides}
    args["quote_id"] = overrides.get("quote_id", "Q-EXEC")
    return approval.verify(seq=seq, now_ts=int(time.time()) + 1, **args)


def test_matching_binding_authorizes_once():
    _register(1)
    ok, code, _ = _verify(1)
    assert (ok, code) == (True, "OK")

    # Single use: the second attempt finds it consumed.
    ok2, code2, _ = _verify(1)
    assert ok2 is False
    assert code2 == "BINDING_CONSUMED"


@pytest.mark.parametrize("field,value,expected_code", [
    ("mission_id", "different-mission", "MISSION_MISMATCH"),
    ("proposal_hash", "b" * 64, "PROPOSAL_HASH_MISMATCH"),
    ("cart_hash", "c" * 64, "CART_HASH_MISMATCH"),
    ("amount_paise", 100, "AMOUNT_MISMATCH"),
    ("currency", "USD", "CURRENCY_MISMATCH"),
    ("skus", [("BAT-002", 1)], "SKU_SET_MISMATCH"),
    ("skus", [("BAT-001", 2)], "SKU_SET_MISMATCH"),
    ("skus", [("BAT-001", 1), ("BALL-001", 1)], "SKU_SET_MISMATCH"),
])
def test_changing_any_bound_field_refuses_authorization(field, value,
                                                        expected_code):
    seq = 100 + abs(hash((field, str(value)))) % 10000
    _register(seq)
    ok, code, _ = _verify(seq, **{field: value})
    assert ok is False, f"changing {field} must not authorize money"
    assert code == expected_code


def test_unknown_sequence_is_refused():
    ok, code, binding = approval.verify(seq=999999, **BASE)
    assert (ok, code, binding) == (False, "BINDING_NOT_FOUND", None)


def test_expired_binding_is_refused():
    now = int(time.time())
    approval.register(seq=777, now_ts=now, ttl_seconds=1, **BASE)
    ok, code, _ = approval.verify(seq=777, now_ts=now + 5,
                                  **{**BASE, "quote_id": "Q-EXEC"})
    assert ok is False
    assert code == "BINDING_EXPIRED"


def test_prebound_quote_cannot_be_substituted():
    """A binding pinned to a quote must reject a different one."""
    approval.register(seq=888, now_ts=int(time.time()),
                      **{**BASE, "quote_id": "Q-ORIGINAL"})
    ok, code, _ = _verify(888, quote_id="Q-SUBSTITUTED")
    assert ok is False
    assert code == "QUOTE_MISMATCH"


def test_a_refused_binding_is_not_consumed():
    """A failed check must not burn the authorization."""
    _register(555)
    ok, code, _ = _verify(555, amount_paise=1)
    assert (ok, code) == (False, "AMOUNT_MISMATCH")

    # The legitimate call still works.
    ok2, code2, _ = _verify(555)
    assert (ok2, code2) == (True, "OK")
