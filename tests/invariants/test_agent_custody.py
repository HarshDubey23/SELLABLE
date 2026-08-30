"""INV-3 mandate custody — the buyer agent never holds the user's mandate key.
The agent proposes; only the human-side executor signs.

Part (a): structural — no file under apps/api/agent may reference the wallet key
or the mandate-signing functions.
Part (b): executor-level — order creation without a verified cart mandate is
refused, even with a valid APPROVE verdict.

Added Phase 2 — closes the gap where mandates.py's docstring cited this test
but it did not exist (found during Phase 0 reconciliation).

Executor reality (apps/api/tools.py, verified Phase 2): /tools/create_order
requires intent + cart mandates (422 MANDATE_REQUIRED when either is absent,
403 MANDATE_REJECTED with the machine code when verification fails), AFTER the
INV-1 approve-binding gate.
"""
import os
import pathlib
import time

os.environ.setdefault("MISSION_HMAC_KEY", "test-custody-mission-key")
os.environ.setdefault("RAZORPAY_KEY_ID", "test-rzp-key-id")
os.environ.setdefault("USER_MANDATE_KEY", "test-custody-user-mandate-key")

import pytest  # noqa: E402
from fastapi.testclient import TestClient  # noqa: E402

from apps.api.gateway.mission_verify import sign_mission  # noqa: E402
from apps.api.main import app  # noqa: E402
from apps.api.mandates.mandates import (  # noqa: E402
    CartMandate,
    IntentMandate,
    sign_cart,
    sign_intent,
)
from apps.api.store import db as store  # noqa: E402

AGENT_DIR = pathlib.Path(__file__).resolve().parents[2] / "apps" / "api" / "agent"

# ADAPT (FACT 2): the wallet-key env name and the REAL sign function names
# from apps/api/mandates/mandates.py: sign_intent / sign_cart.
FORBIDDEN_SUBSTRINGS = [
    "USER_MANDATE_KEY",
    "sign_intent",
    "sign_cart",
]

USER_KEY = os.environ["USER_MANDATE_KEY"]  # sign and verify MUST use the
# same live env value — _key() reads os.environ at verify time


@pytest.fixture(autouse=True)
def _fresh_audit_chain():
    """tests/gateway/test_chain_tamper.py (T30) intentionally corrupts the
    IN-MEMORY audit chain; SQLite holds the true bytes. Reload to restore
    memory = disk before driving the real executor path (same pattern as
    tests/gateway/test_inv1_binding.py)."""
    import importlib

    import apps.api.audit.chain as chain
    importlib.reload(chain)
    assert chain.verify() is True
    yield


def test_agent_source_never_references_mandate_key_or_signing():
    """Part (a): custody is structural, not conventional."""
    violations = []
    for p in sorted(AGENT_DIR.rglob("*.py")):
        src = p.read_text(encoding="utf-8")
        for needle in FORBIDDEN_SUBSTRINGS:
            if needle in src:
                violations.append(f"{p.name}: contains {needle!r}")
    assert not violations, (
        "Agent custody violated — the agent must never read the wallet key or "
        f"sign mandates itself: {violations}"
    )


def _signed_mission(mission_id: str) -> dict:
    fields = {
        "mission_id": mission_id,
        "intent": "custody test",
        "budget_paise": 200000,
        "allowed_categories": ["cricket"],
        "forbidden_categories": [],
        "upsell_cap": 1.3,
        "expires_at": int(time.time()) + 3600,
    }
    return {**fields, "signature": sign_mission(fields)}


def _approved_binding(client: TestClient, mission_id: str) -> tuple[int, str]:
    """Clean proposal through the real HTTP path -> (approve_seq, hash)."""
    r = client.post(
        "/tools/submit_proposal",
        json={"mission": _signed_mission(mission_id),
              "items": [{"sku": "BAT-001", "qty": 1}]},
    )
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["data"]["decision"] == "APPROVE", body["data"]
    return body["seq"], body["data"]["proposal_hash"]


def _quote(client: TestClient, mission_id: str) -> dict:
    r = client.post(
        "/tools/quote",
        json={"items": [{"sku": "BAT-001", "qty": 1}],
              "mission_id": mission_id},
    )
    assert r.status_code == 200, r.text
    return r.json()


def _order_ids() -> set[str]:
    return {row["order_id"] for row in store.query("SELECT order_id FROM orders")}


def test_order_creation_refused_without_verified_cart_mandate():
    """Part (b): the executor refuses order creation when the cart mandate is
    missing or fails verification, even with a valid APPROVE verdict — and no
    order row is created in either case."""
    client = TestClient(app)
    mission_id = "MSN-CUSTODY-GATE"
    seq, approved_hash = _approved_binding(client, mission_id)
    quote = _quote(client, mission_id)
    orders_before = _order_ids()

    # 1. NO mandates at all -> 422 MANDATE_REQUIRED (INV-3 gate, real shape)
    r = client.post(
        "/tools/create_order",
        json={"quote_id": quote["quote_id"],
              "proposal_hash": approved_hash,
              "approve_seq": seq},
        headers={"X-Idempotency-Key": "idem-custody-nomandate"},
    )
    assert r.status_code == 422, r.text
    detail = r.json()["detail"]
    assert detail["error"] == "MANDATE_REQUIRED"
    assert detail["code"] == "MANDATE_MISSING"

    # 2. TAMPERED cart mandate: properly signed, then the payload is mutated
    #    after signing (amount bumped) -> signature no longer verifies.
    now = int(time.time())
    intent = sign_intent(
        IntentMandate(mission_id=mission_id, user_id=f"user_{mission_id}",
                      ceiling_paise=quote["total_paise"],
                      expires_at=now + 3600),
        USER_KEY,
    )
    cart = sign_cart(
        CartMandate(mission_id=mission_id, cart_hash=approved_hash,
                    amount_paise=quote["total_paise"], signed_at=now),
        USER_KEY,
    )
    tampered = {"payload": dict(cart["payload"]), "sig": cart["sig"]}
    tampered["payload"]["amount_paise"] += 1

    r2 = client.post(
        "/tools/create_order",
        json={"quote_id": quote["quote_id"],
              "proposal_hash": approved_hash,
              "approve_seq": seq,
              "intent_mandate": intent,
              "cart_mandate": tampered},
        headers={"X-Idempotency-Key": "idem-custody-tampered"},
    )
    assert r2.status_code == 403, r2.text
    detail2 = r2.json()["detail"]
    assert detail2["error"] == "MANDATE_REJECTED"
    assert detail2["code"] == "MANDATE_BAD_SIGNATURE"

    # 3. A cart mandate whose signed cart_hash does NOT match the approved
    #    proposal -> refused with MANDATE_CART_MISMATCH.
    wrong_cart = sign_cart(
        CartMandate(mission_id=mission_id, cart_hash="a" * 64,
                    amount_paise=quote["total_paise"], signed_at=now),
        USER_KEY,
    )
    r3 = client.post(
        "/tools/create_order",
        json={"quote_id": quote["quote_id"],
              "proposal_hash": approved_hash,
              "approve_seq": seq,
              "intent_mandate": intent,
              "cart_mandate": wrong_cart},
        headers={"X-Idempotency-Key": "idem-custody-wronghash"},
    )
    assert r3.status_code == 403, r3.text
    assert r3.json()["detail"]["code"] == "MANDATE_CART_MISMATCH"

    # 4. No order row was created by any of the refusals.
    assert _order_ids() == orders_before
