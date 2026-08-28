"""Tests for INV-3 user-signed intent and cart mandates."""
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


def test_intent_and_cart_mandates_verify(monkeypatch):
    monkeypatch.setenv("USER_MANDATE_KEY", "test-user-mandate-key")
    intent = sign_intent(
        IntentMandate(
            mission_id="MSN-MANDATE",
            user_id="user_MSN-MANDATE",
            ceiling_paise=200_000,
            expires_at=int(time.time()) + 3600,
        ),
        "test-user-mandate-key",
    )
    cart = sign_cart(
        CartMandate(
            mission_id="MSN-MANDATE",
            cart_hash="hash_123",
            amount_paise=149_900,
            signed_at=int(time.time()),
        ),
        "test-user-mandate-key",
    )

    assert verify_intent(intent, order_total_paise=149_900)["mission_id"] == "MSN-MANDATE"
    assert verify_cart(cart, proposal_hash="hash_123", amount_paise=149_900)["cart_hash"] == "hash_123"


def test_intent_rejects_spend_above_ceiling(monkeypatch):
    monkeypatch.setenv("USER_MANDATE_KEY", "test-user-mandate-key")
    intent = sign_intent(
        IntentMandate(
            mission_id="MSN-MANDATE",
            user_id="user_MSN-MANDATE",
            ceiling_paise=100_000,
            expires_at=int(time.time()) + 3600,
        ),
        "test-user-mandate-key",
    )

    with pytest.raises(MandateError, match="MANDATE_CEILING_EXCEEDED"):
        verify_intent(intent, order_total_paise=149_900)


def test_cart_rejects_hash_mismatch(monkeypatch):
    monkeypatch.setenv("USER_MANDATE_KEY", "test-user-mandate-key")
    cart = sign_cart(
        CartMandate(
            mission_id="MSN-MANDATE",
            cart_hash="hash_123",
            amount_paise=149_900,
            signed_at=int(time.time()),
        ),
        "test-user-mandate-key",
    )

    with pytest.raises(MandateError, match="MANDATE_CART_MISMATCH"):
        verify_cart(cart, proposal_hash="hash_456", amount_paise=149_900)
