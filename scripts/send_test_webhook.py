"""
Send signed fake webhooks to localhost:8000 to test idempotency.
Usage:
    python tests/send_test_webhook.py once
    python tests/send_test_webhook.py replay       # same event-id 3x
    python tests/send_test_webhook.py outoforder   # captured then authorized
    python tests/send_test_webhook.py badsig
"""
import hashlib
import hmac
import json
import os
import sys
from pathlib import Path

import requests
from dotenv import load_dotenv

load_dotenv(Path(__file__).resolve().parents[1] / ".env")
SECRET = os.environ["RAZORPAY_WEBHOOK_SECRET"].encode()
URL = "http://localhost:8000/webhook"


def send(event_name: str, event_id: str, order_id: str, status: str, amount: int):
    body = json.dumps({
        "event": event_name,
        "payload": {"payment": {"entity": {
            "id": "pay_fake123", "order_id": order_id,
            "status": status, "amount": amount,
        }}},
    }).encode()
    sig = hmac.new(SECRET, body, hashlib.sha256).hexdigest()
    r = requests.post(URL, data=body, headers={
        "Content-Type": "application/json",
        "X-Razorpay-Signature": sig,
        "X-Razorpay-Event-Id": event_id,
    })
    print(f"{event_name:25s} id={event_id[:12]:12s} -> {r.status_code} {r.json()}")


if __name__ == "__main__":
    mode = sys.argv[1] if len(sys.argv) > 1 else "once"

    if mode == "once":
        send("payment.authorized", "evt_AAA111", "order_test1", "authorized", 179800)
    elif mode == "replay":
        send("payment.captured", "evt_BBB222", "order_test1", "captured", 179800)
        send("payment.captured", "evt_BBB222", "order_test1", "captured", 179800)  # DUPLICATE
        send("payment.captured", "evt_BBB222", "order_test1", "captured", 179800)  # DUPLICATE
    elif mode == "outoforder":
        send("payment.captured", "evt_CCC333", "order_test2", "captured", 49900)
        send("payment.authorized", "evt_DDD444", "order_test2", "authorized", 49900)  # stale
    elif mode == "badsig":
        r = requests.post(URL, data=b'{"event":"hack"}', headers={
            "X-Razorpay-Signature": "deadbeef",
            "X-Razorpay-Event-Id": "evt_FAKE",
        })
        print(f"bad signature -> {r.status_code} (expect 400)")
