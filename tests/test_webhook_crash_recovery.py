"""The webhook crash window: persisted-but-not-applied must stay replayable.

The failure this guards against is silent and permanent. A process that
dies between "event written to disk" and "capture appended to the audit
chain" leaves a row in the table. If the boot-time dedup set is built
from "every row in the table", that event is treated as done forever and
Razorpay's retry is answered with a duplicate-ack. The payment is
captured, the audit chain never records it, and nothing raises an alarm.
"""
import hashlib
import hmac
import json
import os

import pytest
from fastapi.testclient import TestClient

from apps.api.audit import chain as audit_chain
from apps.api.store import db as store
from apps.api.webhook import receiver


@pytest.fixture
def client():
    from apps.api.main import app
    return TestClient(app)


def _sig(body: bytes) -> str:
    secret = os.environ["RAZORPAY_WEBHOOK_SECRET"]
    return hmac.new(secret.encode(), body, hashlib.sha256).hexdigest()


def _event(order_id="ord_crash", payment_id="pay_crash", amount=149900):
    return json.dumps({
        "event": "payment.captured",
        "payload": {"payment": {"entity": {
            "id": payment_id, "order_id": order_id,
            "status": "captured", "amount": amount}}},
    }).encode("utf-8")


def _post(client, body: bytes, event_id: str):
    return client.post("/webhook", content=body, headers={
        "Content-Type": "application/json",
        "X-Razorpay-Signature": _sig(body),
        "X-Razorpay-Event-Id": event_id,
    })


def _simulate_restart():
    """Rebuild in-process state exactly the way a fresh boot does."""
    receiver.processed_event_ids.clear()
    receiver.payment_ledger.clear()
    receiver._load_persisted_state()


def test_event_is_marked_applied_only_after_audit_succeeds(client):
    body = _event()
    resp = _post(client, body, "evt-lifecycle")
    assert resp.status_code == 200
    assert resp.json()["processing_state"] == "APPLIED"

    row = store.query_one(
        "SELECT processing_state, applied_at FROM webhook_events WHERE event_id = ?",
        ("evt-lifecycle",))
    assert row["processing_state"] == "APPLIED"
    assert row["applied_at"] is not None
    assert receiver.pending_events() == []


def test_crash_between_persist_and_audit_leaves_event_replayable(client):
    body = _event()

    # The process dies while appending the capture to the audit chain.
    def boom(*args, **kwargs):
        raise RuntimeError("simulated crash during audit append")

    real_append = audit_chain.append
    audit_chain.append = boom
    try:
        crashed = _post(client, body, "evt-crash")
        assert crashed.status_code == 503
        assert crashed.json()["detail"]["error"]["error_code"] == "AUDIT_APPEND_FAILED"
    finally:
        audit_chain.append = real_append

    # The row exists on disk but was never applied.
    row = store.query_one(
        "SELECT processing_state FROM webhook_events WHERE event_id = ?",
        ("evt-crash",))
    assert row is not None, "the event must have hit disk"
    assert row["processing_state"] == "RECEIVED"

    # ---- the process restarts ----
    _simulate_restart()

    assert "evt-crash" not in receiver.processed_event_ids, \
        "an un-applied event must NOT be treated as processed after a restart"
    assert [e["event_id"] for e in receiver.pending_events()] == ["evt-crash"]

    # Razorpay retries. This time it must actually be processed.
    retry = _post(client, body, "evt-crash")
    assert retry.status_code == 200
    assert retry.json().get("duplicate") is not True, \
        "the retry must be processed, not acked away as a duplicate"
    assert retry.json()["processing_state"] == "APPLIED"

    captured = [e for e in audit_chain.entries()
                if e["action"] == "payment_captured"]
    assert captured, "the capture must reach the audit chain after recovery"
    assert receiver.pending_events() == []


def test_applied_event_is_still_deduplicated_across_restart(client):
    body = _event(order_id="ord_dedup", payment_id="pay_dedup")
    assert _post(client, body, "evt-dedup").status_code == 200

    _simulate_restart()

    again = _post(client, body, "evt-dedup")
    assert again.status_code == 200
    assert again.json()["duplicate"] is True

    captured = [e for e in audit_chain.entries()
                if e["action"] == "payment_captured"
                and e.get("payload_hash")]
    # Exactly one capture audit entry for one real capture.
    assert len(captured) == 1


def test_pending_endpoint_exposes_the_crash_window(client):
    def boom(*args, **kwargs):
        raise RuntimeError("crash")

    real_append = audit_chain.append
    audit_chain.append = boom
    try:
        _post(client, _event(order_id="ord_pend", payment_id="pay_pend"),
              "evt-pend")
    finally:
        audit_chain.append = real_append

    resp = client.get("/webhook/pending")
    assert resp.status_code == 200
    body = resp.json()
    assert body["pending_count"] == 1
    assert body["pending"][0]["event_id"] == "evt-pend"
    assert body["lifecycle"] == ["RECEIVED", "APPLIED"]
