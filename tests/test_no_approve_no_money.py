"""
test_no_approve_no_money.py

INV-1: No approval binding -> no money flow.
"""
import os
import time

import pytest
from fastapi.testclient import TestClient


@pytest.fixture
def app_client():
    from apps.api.main import app
    return TestClient(app)


def test_create_order_requires_valid_approve_seq(app_client):
    """tool_create_order must reject any request with an invalid approve_seq."""
    import time as _time

    from apps.api.mandates.mandates import CartMandate, IntentMandate, sign_cart, sign_intent

    key = os.environ["USER_MANDATE_KEY"]
    now = int(_time.time())
    mission_id = "test-mission-inv1"
    amount_paise = 100000
    proposal_hash = "a" * 64

    intent_blob = sign_intent(IntentMandate(
        mission_id=mission_id,
        user_id="u1",
        ceiling_paise=amount_paise + 50000,
        expires_at=now + 3600,
    ), key)

    cart_blob = sign_cart(CartMandate(
        mission_id=mission_id,
        cart_hash=proposal_hash,
        amount_paise=amount_paise,
        signed_at=now,
        expires_at=now + 3600,
    ), key)

    # First create a quote in memory by using the quote endpoint
    # (we need a valid quote_id)
    # Without a quote or valid approve_seq, the request must be rejected.
    resp = app_client.post(
        "/tools/create_order",
        json={
            "quote_id": "nonexistent-quote-id",
            "proposal_hash": proposal_hash,
            "approve_seq": 99999,
            "intent_mandate": intent_blob,
            "cart_mandate": cart_blob,
        },
        headers={"X-API-Key": os.environ["APP_API_KEY"],
                 "X-Idempotency-Key": "test-idem-key-001"},
    )
    # Must be rejected — no such quote, no valid binding
    assert resp.status_code in (404, 403, 422), f"Expected rejection, got {resp.status_code}: {resp.text}"


def test_double_spend_binding_rejected(tmp_path, monkeypatch):
    """A consumed binding must not authorize a second order."""
    from apps.api import approval

    now = int(time.time())
    approval.register(
        seq=1001,
        mission_id="m1",
        proposal_hash="h" * 64,
        cart_hash="h" * 64,
        quote_id="",
        amount_paise=5000,
        currency="INR",
        skus=[("SKU-001", 1)],
        now_ts=now,
    )

    # First verify should succeed
    ok1, code1, _ = approval.verify(
        seq=1001,
        mission_id="m1",
        proposal_hash="h" * 64,
        cart_hash="h" * 64,
        quote_id="",
        amount_paise=5000,
        currency="INR",
        skus=[("SKU-001", 1)],
        now_ts=now + 1,
    )
    assert ok1, f"First verify failed: {code1}"

    # Second verify must fail as BINDING_CONSUMED
    ok2, code2, _ = approval.verify(
        seq=1001,
        mission_id="m1",
        proposal_hash="h" * 64,
        cart_hash="h" * 64,
        quote_id="",
        amount_paise=5000,
        currency="INR",
        skus=[("SKU-001", 1)],
        now_ts=now + 2,
    )
    assert not ok2
    assert code2 == "BINDING_CONSUMED"
