"""
tests/test_webhook.py - Webhook HMAC, dedup, and ledger tests (offline).
"""
import hashlib, hmac, json, os, time, pytest
from fastapi.testclient import TestClient


@pytest.fixture
def client():
    from apps.api.main import app
    return TestClient(app)


def _sig(body: bytes, secret: str) -> str:
    return hmac.new(secret.encode(), body, hashlib.sha256).hexdigest()


def _event(order_id="ord_test1", status="captured", amount=10000):
    return json.dumps({
        "event": "payment.captured",
        "payload": {
            "payment": {
                "entity": {
                    "id": "pay_test001",
                    "order_id": order_id,
                    "status": status,
                    "amount": amount,
                }
            }
        }
    }).encode("utf-8")


def test_webhook_valid_signature_accepted(client):
    secret = os.environ["RAZORPAY_WEBHOOK_SECRET"]
    body = _event()
    resp = client.post(
        "/webhook",
        content=body,
        headers={
            "Content-Type": "application/json",
            "X-Razorpay-Signature": _sig(body, secret),
            "X-Razorpay-Event-Id": "evt-001",
        },
    )
    assert resp.status_code == 200
    data = resp.json()
    assert data["status"] == "ok"
    assert data["event_id"] == "evt-001"


def test_webhook_bad_signature_rejected(client):
    body = _event()
    resp = client.post(
        "/webhook",
        content=body,
        headers={
            "Content-Type": "application/json",
            "X-Razorpay-Signature": "badbadbadbad",
            "X-Razorpay-Event-Id": "evt-002",
        },
    )
    assert resp.status_code == 400
    detail = resp.json()["detail"]
    assert detail["error"]["error_code"] == "WEBHOOK_BAD_SIGNATURE"


def test_webhook_duplicate_is_idempotent(client):
    secret = os.environ["RAZORPAY_WEBHOOK_SECRET"]
    body = _event(order_id="ord_dup1")
    sig = _sig(body, secret)
    headers = {
        "Content-Type": "application/json",
        "X-Razorpay-Signature": sig,
        "X-Razorpay-Event-Id": "evt-dup-1",
    }
    r1 = client.post("/webhook", content=body, headers=headers)
    r2 = client.post("/webhook", content=body, headers=headers)
    assert r1.status_code == 200
    assert r2.status_code == 200
    assert r2.json().get("duplicate") is True


def test_webhook_missing_secret_fails_closed(client, monkeypatch):
    monkeypatch.delenv("RAZORPAY_WEBHOOK_SECRET", raising=False)
    body = _event()
    resp = client.post(
        "/webhook",
        content=body,
        headers={
            "Content-Type": "application/json",
            "X-Razorpay-Signature": "irrelevant",
        },
    )
    assert resp.status_code == 503
    assert resp.json()["detail"]["error"]["error_code"] == "WEBHOOK_SECRET_MISSING"


def test_webhook_event_persisted_to_ledger(client):
    secret = os.environ["RAZORPAY_WEBHOOK_SECRET"]
    body = _event(order_id="ord_ledger1", status="captured", amount=55000)
    resp = client.post(
        "/webhook",
        content=body,
        headers={
            "Content-Type": "application/json",
            "X-Razorpay-Signature": _sig(body, secret),
            "X-Razorpay-Event-Id": "evt-ledger-1",
        },
    )
    assert resp.status_code == 200
    # Check it appears in the ledger
    ledger_resp = client.get("/ledger")
    assert ledger_resp.status_code == 200
    ledger = ledger_resp.json()
    assert "ord_ledger1" in ledger
    assert ledger["ord_ledger1"]["status"] == "captured"
    assert ledger["ord_ledger1"]["amount_paise"] == 55000
