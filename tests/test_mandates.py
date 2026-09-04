"""
test_mandates.py - Mandate signature and expiry tests.
"""
import os
import time

import pytest

from apps.api.mandates.mandates import (
    CartMandate,
    IntentMandate,
    MandateError,
    sign_cart,
    sign_intent,
    verify_cart,
    verify_intent,
)


def _key():
    return os.environ["USER_MANDATE_KEY"]


def test_intent_mandate_sign_verify():
    now = int(time.time())
    m = IntentMandate(mission_id="m1", user_id="u1", ceiling_paise=100000, expires_at=now + 3600)
    blob = sign_intent(m, _key())
    result = verify_intent(blob, now=now, order_total_paise=50000, expected_mission_id="m1")
    assert result["mission_id"] == "m1"


def test_intent_mandate_expired():
    now = int(time.time())
    m = IntentMandate(mission_id="m1", user_id="u1", ceiling_paise=100000, expires_at=now - 1)
    blob = sign_intent(m, _key())
    with pytest.raises(MandateError) as exc_info:
        verify_intent(blob, now=now)
    assert exc_info.value.code == "MANDATE_EXPIRED"


def test_intent_mandate_ceiling_exceeded():
    now = int(time.time())
    m = IntentMandate(mission_id="m1", user_id="u1", ceiling_paise=1000, expires_at=now + 3600)
    blob = sign_intent(m, _key())
    with pytest.raises(MandateError) as exc_info:
        verify_intent(blob, now=now, order_total_paise=2000)
    assert exc_info.value.code == "MANDATE_CEILING_EXCEEDED"


def test_intent_mandate_mission_mismatch():
    now = int(time.time())
    m = IntentMandate(mission_id="m1", user_id="u1", ceiling_paise=100000, expires_at=now + 3600)
    blob = sign_intent(m, _key())
    with pytest.raises(MandateError) as exc_info:
        verify_intent(blob, now=now, expected_mission_id="m999")
    assert exc_info.value.code == "MANDATE_MISSION_MISMATCH"


def test_cart_mandate_sign_verify():
    now = int(time.time())
    cart_hash = "a" * 64
    m = CartMandate(mission_id="m1", cart_hash=cart_hash, amount_paise=5000,
                    signed_at=now, expires_at=now + 3600)
    blob = sign_cart(m, _key())
    result = verify_cart(blob, proposal_hash=cart_hash, amount_paise=5000, expected_mission_id="m1")
    assert result["mission_id"] == "m1"


def test_cart_mandate_expired():
    now = int(time.time())
    cart_hash = "b" * 64
    m = CartMandate(mission_id="m1", cart_hash=cart_hash, amount_paise=5000,
                    signed_at=now - 100, expires_at=now - 1)
    blob = sign_cart(m, _key())
    with pytest.raises(MandateError) as exc_info:
        verify_cart(blob, proposal_hash=cart_hash, amount_paise=5000)
    assert exc_info.value.code == "MANDATE_EXPIRED"


def test_cart_mandate_hash_mismatch():
    now = int(time.time())
    m = CartMandate(mission_id="m1", cart_hash="a" * 64, amount_paise=5000,
                    signed_at=now, expires_at=now + 3600)
    blob = sign_cart(m, _key())
    with pytest.raises(MandateError) as exc_info:
        verify_cart(blob, proposal_hash="b" * 64, amount_paise=5000)
    assert exc_info.value.code == "MANDATE_CART_MISMATCH"


def test_cart_mandate_amount_mismatch():
    now = int(time.time())
    cart_hash = "c" * 64
    m = CartMandate(mission_id="m1", cart_hash=cart_hash, amount_paise=5000,
                    signed_at=now, expires_at=now + 3600)
    blob = sign_cart(m, _key())
    with pytest.raises(MandateError) as exc_info:
        verify_cart(blob, proposal_hash=cart_hash, amount_paise=9999)
    assert exc_info.value.code == "MANDATE_AMOUNT_MISMATCH"


def test_bad_signature_rejected():
    now = int(time.time())
    m = IntentMandate(mission_id="m1", user_id="u1", ceiling_paise=100000, expires_at=now + 3600)
    blob = sign_intent(m, _key())
    blob["sig"] = "invalidsignature"
    with pytest.raises(MandateError) as exc_info:
        verify_intent(blob, now=now)
    assert exc_info.value.code == "MANDATE_BAD_SIGNATURE"


# ─────────────────────────────────────────────────────────────────────
# Ported from the root-level `tests_mandates.py` scratch script before it
# was deleted. That file sat outside `testpaths = ["tests"]`, so pytest
# never collected it and these two checks had never actually run. The
# rest of its list was already covered above; only version and currency
# were missing.
# ─────────────────────────────────────────────────────────────────────

def test_an_unsupported_mandate_version_is_refused():
    """Version is checked before the signature, and fails closed.

    A mandate schema change must never be accepted by an old verifier that
    happens to find the signature valid over fields it does not understand.
    """
    now = int(time.time())
    m = IntentMandate(mission_id="m1", user_id="u1",
                      ceiling_paise=100000, expires_at=now + 3600)
    blob = sign_intent(m, _key())
    blob["payload"]["version"] = 99

    with pytest.raises(MandateError) as exc:
        verify_intent(blob, now=now, order_total_paise=50000,
                      expected_mission_id="m1")
    assert exc.value.code == "MANDATE_BAD_VERSION"


def test_an_unsupported_currency_is_refused():
    """INR only. An unknown currency is a refusal, not a conversion."""
    now = int(time.time())
    m = IntentMandate(mission_id="m1", user_id="u1",
                      ceiling_paise=100000, expires_at=now + 3600)
    blob = sign_intent(m, _key())
    blob["payload"]["currency"] = "XAU"

    with pytest.raises(MandateError) as exc:
        verify_intent(blob, now=now, order_total_paise=50000,
                      expected_mission_id="m1")
    assert exc.value.code == "MANDATE_BAD_CURRENCY"
