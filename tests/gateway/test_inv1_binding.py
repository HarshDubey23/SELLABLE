"""INV-1: order creation is bound to a recorded APPROVE verdict for the EXACT
proposal bytes. Tampering with the proposal (or its recorded verdict) after the
verdict must make order creation refuse. Added Phase 1.

Executor reality (apps/api/tools.py, read and verified in Phase 1 — no
enforcement was added this phase, it already existed):
  - POST /tools/create_order is the single money boundary.
  - Its G1 gate (tools.py ~line 357) requires
    approved_bindings.get(approve_seq) == proposal_hash, else HTTP 403 with
    error.error_code == "ORDER_HASH_MISMATCH".
  - approved_bindings is written ONLY by submit_proposal on a gateway APPROVE
    (tools.py ~line 294): seq -> verdict.proposal_hash, where the hash is
    sha256_hex(canonical_json(proposal)) (gateway/engine.py).
Tests here drive the real HTTP surface offline: the Razorpay boundary is
monkeypatched at apps/api.razorpay_client (the single money-API module).
"""
import os
import time

import pytest

os.environ.setdefault("MISSION_HMAC_KEY", "test-inv1-mission-key")
os.environ.setdefault("RAZORPAY_KEY_ID", "test-rzp-key-id")
os.environ.setdefault("USER_MANDATE_KEY", "test-inv1-user-mandate-key")


@pytest.fixture(autouse=True)
def _fresh_audit_chain():
    """tests/gateway/test_chain_tamper.py (T30) intentionally corrupts the
    IN-MEMORY audit chain and leaves it that way. The audit_chain table in
    SQLite still holds the true bytes (append writes DB first), so reload
    the module — the repo's own reset pattern — to restore memory = disk
    before driving the real executor path, which gates on chain.verify()."""
    import importlib

    import apps.api.audit.chain as chain
    importlib.reload(chain)
    assert chain.verify() is True
    yield

from fastapi.testclient import TestClient  # noqa: E402

from apps.api.gateway.mission_verify import sign_mission  # noqa: E402
from apps.api.gateway.types import (  # noqa: E402
    Proposal,
    ProposalItem,
    canonical_json,
    sha256_hex,
)
from apps.api.main import app  # noqa: E402
from apps.api.mandates.mandates import (  # noqa: E402
    CartMandate,
    IntentMandate,
    sign_cart,
    sign_intent,
)
from apps.api.products import CATALOG  # noqa: E402

USER_KEY = "test-inv1-user-mandate-key"


def _signed_mission(mission_id: str) -> dict:
    """Mission fields + HMAC signature, exactly as rule_r9 verifies it:
    HMAC over canonical_json(mission fields minus signature)."""
    fields = {
        "mission_id": mission_id,
        "intent": "INV-1 binding test",
        "budget_paise": 200000,
        "allowed_categories": ["cricket"],
        "forbidden_categories": [],
        "upsell_cap": 1.3,
        "expires_at": int(time.time()) + 3600,
    }
    return {**fields, "signature": sign_mission(fields)}


def _approved_binding(client: TestClient, mission_id: str) -> tuple[int, str]:
    """Submit a clean 1x BAT-001 proposal through the real HTTP path and
    return (approve_seq, proposal_hash) of the recorded APPROVE binding."""
    r = client.post(
        "/tools/submit_proposal",
        json={"mission": _signed_mission(mission_id),
              "items": [{"sku": "BAT-001", "qty": 1}]},
    )
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["ok"] is True
    assert body["data"]["decision"] == "APPROVE", body["data"]

    # The recorded hash must be the canonical hash of the proposal the
    # server actually built (items priced server-side from CATALOG).
    expected = sha256_hex(canonical_json(Proposal(
        mission_id=mission_id,
        items=(ProposalItem(sku="BAT-001", qty=1,
                            price_paise=CATALOG["BAT-001"]["price_paise"]),),
    )))
    assert body["data"]["proposal_hash"] == expected
    return body["seq"], body["data"]["proposal_hash"]


def _quote(client: TestClient, mission_id: str) -> dict:
    r = client.post(
        "/tools/quote",
        json={"items": [{"sku": "BAT-001", "qty": 1}],
              "mission_id": mission_id},
    )
    assert r.status_code == 200, r.text
    return r.json()


def test_tampered_proposal_refused():
    """A proposal mutated AFTER its APPROVE verdict is recorded must be
    refused order creation (hash mismatch -> HTTP 403 ORDER_HASH_MISMATCH)."""
    client = TestClient(app, headers={"X-API-Key": os.environ["APP_API_KEY"]})
    mission_id = "MSN-INV1-TAMPER"
    seq, approved_hash = _approved_binding(client, mission_id)
    quote = _quote(client, mission_id)

    # Mutate the proposal: qty 1 -> 2 changes the canonical bytes, hence
    # the hash. The recorded verdict binds only the ORIGINAL proposal.
    mutated = Proposal(
        mission_id=mission_id,
        items=(ProposalItem(sku="BAT-001", qty=2,
                            price_paise=CATALOG["BAT-001"]["price_paise"]),),
    )
    mutated_hash = sha256_hex(canonical_json(mutated))
    assert mutated_hash != approved_hash

    r = client.post(
        "/tools/create_order",
        json={"quote_id": quote["quote_id"],
              "proposal_hash": mutated_hash,
              "approve_seq": seq},
        headers={"X-Idempotency-Key": "idem-inv1-tamper-1"},
    )
    assert r.status_code == 403, r.text
    err = r.json()["detail"]["error"]
    assert err["error_code"] == "ORDER_HASH_MISMATCH"
    assert err["retryable"] is False
    assert str(seq) in err["message"]


def test_valid_binding_proceeds(monkeypatch):
    """Control: the untampered (verdict, proposal) pair passes the binding
    gate and proceeds to the real Razorpay boundary — mocked offline — with
    valid INV-3 mandates, and the order is created from the quote total."""
    monkeypatch.setenv("USER_MANDATE_KEY", USER_KEY)
    client = TestClient(app, headers={"X-API-Key": os.environ["APP_API_KEY"]})
    mission_id = "MSN-INV1-CONTROL"
    seq, approved_hash = _approved_binding(client, mission_id)
    quote = _quote(client, mission_id)

    calls: list[dict] = []

    def fake_create_order(**kwargs):
        calls.append(kwargs)
        return {"id": "order_test_inv1_control"}

    import apps.api.tools as tools
    monkeypatch.setattr(tools.rp_client, "create_order", fake_create_order)

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

    r = client.post(
        "/tools/create_order",
        json={"quote_id": quote["quote_id"],
              "proposal_hash": approved_hash,
              "approve_seq": seq,
              "intent_mandate": intent,
              "cart_mandate": cart},
        headers={"X-Idempotency-Key": "idem-inv1-control-1"},
    )
    assert r.status_code == 200, r.text
    assert r.json()["order_id"] == "order_test_inv1_control"
    assert len(calls) == 1
    assert calls[0]["amount_paise"] == quote["total_paise"]
    assert calls[0]["notes"]["proposal_hash"] == approved_hash
