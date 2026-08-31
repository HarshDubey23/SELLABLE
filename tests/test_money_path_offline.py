"""Offline end-to-end money path (NO network): signed mission -> agent run ->
gateway APPROVE -> order row in SQLite -> audit chain entries with parent
linkage -> timeline readable. Added Phase 2.

Real components: buyer agent loop, wallet CLI subprocess (mandate custody),
HTTP handlers (manifest/search/submit_proposal/quote/create_order/check_payment),
policy gateway, audit chain, SQLite store.
Mocked (the ONLY permitted mock): the outbound Razorpay HTTP boundary —
apps/api/razorpay_client.* — including its deterministic test-mode UPI refusal,
which drives the recovery flow exactly as the real rail does.

Discovery adaptations (STEP 0, recorded in the Phase 2 log):
- GET /audit/timeline takes NO query params (HTML card list); the ordered
  sequence is asserted via GET /audit (JSON entries) and the timeline is
  asserted for 200 + verified footer.
- Chain entries store payload_hash, not raw payloads; mission linkage is
  asserted through the SQLite verdicts/orders tables (mission_id columns)
  and chain seq alignment.
"""
import asyncio
import os

import httpx
import pytest
from fastapi.testclient import TestClient
from httpx import ASGITransport

os.environ.setdefault("MISSION_HMAC_KEY", "test-offline-mission-key")
os.environ.setdefault("RAZORPAY_KEY_ID", "test-rzp-key-id")
os.environ.setdefault("USER_MANDATE_KEY", "test-offline-user-mandate-key")

import apps.api.agent.buyer as buyer  # noqa: E402
import apps.api.audit.chain as audit_chain  # noqa: E402
from apps.api.main import app  # noqa: E402
from apps.api.store import db as store  # noqa: E402
from scripts.sign_mission import MISSION_TEMPLATES, sign_blob  # noqa: E402

# F-08: inject X-API-Key into the buyer's HTTP client so protected routes
# are exercised successfully in the test environment.
_orig_asyncclient_init = buyer.httpx.AsyncClient.__init__
def _patched_asyncclient_init(self, *args, **kwargs):
    kwargs.setdefault("headers", {}).__setitem__(
        "X-API-Key", os.environ.get("APP_API_KEY", "")
    )
    _orig_asyncclient_init(self, *args, **kwargs)
buyer.httpx.AsyncClient.__init__ = _patched_asyncclient_init

FAKE_ORDER_ID = "order_test_offline_001"


def _signed_mission() -> dict:
    """Unique-id happy-path mission signed with the custody-split signer's
    own sign_blob (same algorithm as build_signed_mission, fresh TTL)."""
    import time as _time

    mission = dict(MISSION_TEMPLATES["happy_path"])
    mission["mission_id"] = f"MSN-OFFLINE-E2E-{_time.time_ns()}"
    mission["expires_at"] = int(_time.time()) + 24 * 3600
    mission["signature"] = sign_blob(mission)
    return mission


@pytest.fixture(autouse=True)
def _fresh_audit_chain():
    """T30 corrupts the in-memory chain session-wide; restore from SQLite."""
    import importlib

    importlib.reload(audit_chain)
    assert audit_chain.verify() is True
    yield


def _patch_llm_outage(monkeypatch):
    def _outage(*_a, **_k):
        return {"text": "", "latency_ms": 0, "model": "outage-stub",
                "error": "llm down (simulated outage)"}
    monkeypatch.setattr("apps.api.llm.gemini.ask", _outage)


def _patch_razorpay_boundary(monkeypatch):
    monkeypatch.setattr(
        "apps.api.razorpay_client.create_order",
        lambda **kwargs: {"id": FAKE_ORDER_ID, "status": "created"})
    monkeypatch.setattr(
        "apps.api.razorpay_client.attempt_checkout_payment",
        lambda order_id, amount_paise, method_body, **kw: {
            "order_id": order_id, "http_status": 400,
            "result": {"error": {
                "code": "BAD_REQUEST_ERROR",
                "description": "UPI is not enabled for this test account",
                "step": "payment_initiation"}}})
    monkeypatch.setattr(
        "apps.api.razorpay_client.list_order_payments",
        lambda order_id: [])
    monkeypatch.setattr(
        "apps.api.razorpay_client.fetch_order",
        lambda order_id: {"id": order_id, "status": "created"})


def _patch_agent_transport(monkeypatch):
    transport = ASGITransport(app=app)

    class _Client(httpx.AsyncClient):
        def __init__(self, *args, **kwargs):
            kwargs.setdefault("transport", transport)
            kwargs.setdefault("base_url", "http://testserver")
            super().__init__(*args, **kwargs)

    monkeypatch.setattr(buyer.httpx, "AsyncClient", _Client)


def test_offline_money_path_end_to_end(monkeypatch):
    _patch_llm_outage(monkeypatch)
    _patch_razorpay_boundary(monkeypatch)
    _patch_agent_transport(monkeypatch)
    monkeypatch.setattr(buyer.time, "sleep", lambda s: None)

    # 1+2. Signed mission from the custody-split signer (fresh TTL, real key,
    #      unique mission id so session-wide verdict rows can't interfere).
    mission = _signed_mission()
    mission_id = mission["mission_id"]

    # 3. Run the REAL buyer agent against the REAL app over in-process HTTP.
    result = asyncio.run(buyer.run_mission(mission, base_url="http://testserver"))

    # 4. The gateway verdict is APPROVE and is recorded in the verdicts table.
    assert result["order_id"] == FAKE_ORDER_ID, result.get("trace")
    verdict_rows = store.query(
        "SELECT seq, decision, mission_id FROM verdicts WHERE mission_id = ?",
        (mission_id,))
    approve_rows = [r for r in verdict_rows if r["decision"] == "APPROVE"]
    assert approve_rows, f"no APPROVE verdict recorded for {mission_id}"

    # 5. The order row exists in the REAL persistence with the fake order id.
    order_rows = store.query(
        "SELECT order_id, mission_id, proposal_hash, approve_seq, amount_paise "
        "FROM orders WHERE order_id = ?", (FAKE_ORDER_ID,))
    assert len(order_rows) == 1
    order_row = order_rows[0]
    assert order_row["mission_id"] == mission_id
    assert order_row["approve_seq"] == approve_rows[0]["seq"]
    assert order_row["amount_paise"] > 0

    # 6. Audit chain: verdict + order entries exist for this run and the
    #    recovery branch links failure -> diagnosis via parent_action_id.
    assert audit_chain.verify() is True
    entries = audit_chain.entries()
    by_seq = {e["seq"]: e for e in entries}
    assert approve_rows[0]["seq"] in by_seq
    assert by_seq[approve_rows[0]["seq"]]["action"] == "verdict_emitted"

    order_created = [e for e in entries if e["action"] == "order_created"]
    assert order_created, "executor never appended order_created"

    fail_entries = [e for e in entries
                    if e["action"] == "payment_attempt_failed"]
    assert fail_entries, "UPI refusal was never recorded in the chain"
    # The most recent failure is THIS run's (an earlier agent test in the
    # same session may have appended one; note _load_from_db does not
    # re-select parent_action_id, so only post-reload entries carry it).
    fail_aid = audit_chain.action_id(fail_entries[-1]["seq"])
    linked = [e for e in entries
              if e["action"] == "recovery_reasoned"
              and e.get("parent_action_id") == fail_aid]
    assert linked, "recovery reasoning does not link to the failure entry"

    # 7. Timeline: GET /audit/timeline (HTML, no params) renders the chain
    #    with a verified footer; GET /audit returns the JSON chain verified.
    client = TestClient(app)
    tl = client.get("/audit/timeline")
    assert tl.status_code == 200
    assert "Chain verified:" in tl.text
    assert '<span class="ok">True</span>' in tl.text
    audit = client.get("/audit")
    assert audit.status_code == 200
    assert audit.json()["verified"] is True

    # Honest-completion check: offline the payment did NOT complete; the run
    # must report order-created/pending or payment-failed, never a fake
    # "captured".
    assert result["status"] in ("order_created_payment_pending",
                                "payment_failed")
    assert result["final_payment_status"] != "captured"
