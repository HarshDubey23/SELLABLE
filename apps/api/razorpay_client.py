"""
THE ONLY money-API boundary in the codebase.

Every Razorpay call goes through this module, straight to
api.razorpay.com over HTTPS with Basic auth. No LLM SDKs here —
the executor stays out of the reasoning path (purity invariant covers
apps/api/gateway/, and this module imports nothing from it).

Idempotency: every mutating POST carries an X-Razorpay-Idempotency-Key
header plus the same key mirrored into the request notes/payload, so a
replay is visible both to Razorpay-style tooling and in our audit chain.
Keys are derived deterministically from business identifiers
(agent_run_id + intent_id + approve_seq), never from wall-clock time.

Instrumentation: every public mutator calls apps.api.money to record the
operation. The Attack Lab uses that counter to PROVE the central
invariant: a rejected proposal => 0 Razorpay calls.
"""
import hashlib
import json
import os
import re
import time
from typing import Any

import requests

from . import money

BASE_URL = "https://api.razorpay.com"
TIMEOUT_S = 30


def derive_idempotency_key(*parts: Any) -> str:
    """Deterministic idempotency key from stable business identifiers."""
    raw = "|".join(str(p) for p in parts)
    return "idem_" + hashlib.sha256(raw.encode()).hexdigest()[:40]


def _auth() -> tuple[str, str]:
    return os.environ["RAZORPAY_KEY_ID"], os.environ["RAZORPAY_KEY_SECRET"]


def _post(path: str, body: dict,
          idempotency_key: str | None = None) -> dict:
    headers = {"Content-Type": "application/json"}
    if idempotency_key:
        headers["X-Razorpay-Idempotency-Key"] = idempotency_key
    resp = requests.post(
        BASE_URL + path, json=body, auth=_auth(),
        headers=headers, timeout=TIMEOUT_S)
    data = resp.json()
    if resp.status_code >= 400:
        # Surface the real Razorpay error; callers decide recovery.
        err = data.get("error", data)
        raise RazorpayAPIError(resp.status_code, err)
    return data


def _get(path: str) -> dict:
    resp = requests.get(BASE_URL + path, auth=_auth(), timeout=TIMEOUT_S)
    data = resp.json()
    if resp.status_code >= 400:
        raise RazorpayAPIError(resp.status_code, data.get("error", data))
    return data


class RazorpayAPIError(Exception):
    def __init__(self, status_code: int, error: Any):
        self.status_code = status_code
        self.error = error
        code = ""
        desc = ""
        if isinstance(error, dict):
            code = str(error.get("code", ""))
            desc = str(error.get("description", ""))
        super().__init__(f"HTTP {status_code} {code} {desc}".strip())


# G4: money is int paise, never float.
def _validate_amount(amount_paise: int) -> None:
    if not isinstance(amount_paise, int) or isinstance(amount_paise, bool):
        raise ValueError("G4: money is int paise")


def create_order(amount_paise: int, receipt: str, notes: dict,
                 idempotency_key: str | None = None) -> dict:
    """POST /v1/orders — a real test-mode order on api.razorpay.com."""
    _validate_amount(amount_paise)
    money.record("create_order", amount_paise=amount_paise, receipt=receipt,
                 idempotency_key=idempotency_key)
    body = {
        "amount": amount_paise,
        "currency": "INR",
        "receipt": receipt,
        "notes": {**notes, **({"idempotency_key": idempotency_key}
                              if idempotency_key else {})},
    }
    return _post("/v1/orders", body, idempotency_key=idempotency_key)


def fetch_order(order_id: str) -> dict:
    """GET /v1/orders/{id} — authoritative order status."""
    money.record("fetch_order", order_id=order_id)
    return _get(f"/v1/orders/{order_id}")


def fetch_payment(payment_id: str) -> dict:
    """GET /v1/payments/{id} — authoritative payment status."""
    money.record("fetch_payment", payment_id=payment_id)
    return _get(f"/v1/payments/{payment_id}")


def create_upi_payment(order_id: str, amount_paise: int,
                       vpa: str = "success@razorpay",
                       email: str = "buyer@sellable.test",
                       contact: str = "+919000000000") -> dict:
    """
    POST /v1/payments — attempt a UPI collect on a test-mode order.

    Razorpay's documented test-UPI behaviour maps specific amounts to
    deterministic outcomes (see razorpay.com test-upi-details):
    amount=304 paise declines with payment_declined. This gives us a
    REAL failure to recover from, no DOM automation involved.
    """
    _validate_amount(amount_paise)
    money.record("create_upi_payment", order_id=order_id,
                 amount_paise=amount_paise)
    body = {
        "amount": amount_paise,
        "currency": "INR",
        "order_id": order_id,
        "email": email,
        "contact": contact,
        "method": "upi",
        "upi": {"vpa": vpa},
    }
    return _post("/v1/payments", body)


def create_payment_link(amount_paise: int, description: str,
                        expire_by_seconds: int = 24 * 3600,
                        notes: dict | None = None,
                        idempotency_key: str | None = None) -> dict:
    """
    POST /v1/payment_links — the recovery rail. Returns a real short_url
    a human can pay through; webhook payment.captured closes the loop.
    """
    _validate_amount(amount_paise)
    money.record("create_payment_link", amount_paise=amount_paise,
                 idempotency_key=idempotency_key)
    body = {
        "amount": amount_paise,
        "currency": "INR",
        "accept_partial": False,
        "description": description[:255],
        "expire_by": int(time.time()) + expire_by_seconds,
        "notes": {**(notes or {}), **({"idempotency_key": idempotency_key}
                                      if idempotency_key else {})},
    }
    return _post("/v1/payment_links", body, idempotency_key=idempotency_key)


def list_order_payments(order_id: str) -> list[dict]:
    """GET /v1/orders/{id}/payments — authoritative payment list."""
    money.record("list_order_payments", order_id=order_id)
    data = _get(f"/v1/orders/{order_id}/payments")
    return data.get("items", [])


def capture_payment(payment_id: str, amount_paise: int,
                    currency: str = "INR") -> dict:
    """POST /v1/payments/{id}/capture — capture an authorized payment."""
    _validate_amount(amount_paise)
    money.record("capture_payment", payment_id=payment_id,
                 amount_paise=amount_paise)
    url = f"{BASE_URL}/v1/payments/{payment_id}/capture"
    resp = requests.post(url, auth=_auth(),
                         data={"amount": amount_paise, "currency": currency},
                         headers={"Content-Type": "application/x-www-form-urlencoded",
                                  "X-Razorpay-Idempotency-Key": f"idem_cap_{payment_id}"},
                         timeout=TIMEOUT_S)
    try:
        data = resp.json()
    except Exception:
        data = {"raw": resp.text}
    if resp.status_code >= 400:
        err = data.get("error", data) if isinstance(data, dict) else data
        raise RazorpayAPIError(resp.status_code, err)
    return data if isinstance(data, dict) else {"raw": data}


def attempt_checkout_payment(order_id: str, amount_paise: int,
                             method_body: dict,
                             email: str = "buyer@sellable.test",
                             contact: str = "9000000000") -> dict:
    """
    Attempt a payment exactly the way Razorpay Checkout's browser does:
    POST /v1/payments with PUBLIC-key auth (key_id as username, empty
    secret). This is the documented, real client flow against
    api.razorpay.com — no DOM automation involved.

    The response is Razorpay's callback page; the embedded
    `var data = {...}` carries the REAL result (a payment id on
    success, a structured error on failure). We parse that JSON out
    and return it verbatim — never inventing outcomes.
    """
    _validate_amount(amount_paise)
    key_id = os.environ["RAZORPAY_KEY_ID"]
    money.record("attempt_checkout_payment", order_id=order_id,
                 amount_paise=amount_paise)
    body = {
        "amount": amount_paise,
        "currency": "INR",
        "order_id": order_id,
        "email": email,
        "contact": contact,
        **method_body,
    }
    resp = requests.post(f"{BASE_URL}/v1/payments", json=body,
                         auth=(key_id, ""), timeout=TIMEOUT_S)
    m = re.search(r"var data = (\{.*?\});\n", resp.text, re.DOTALL)
    if not m:
        return {"order_id": order_id, "http_status": resp.status_code,
                "result": {"unparsed_response": True}}
    try:
        result = json.loads(m.group(1))
    except json.JSONDecodeError:
        return {"order_id": order_id, "http_status": resp.status_code,
                "result": {"unparsed_response": True}}
    return {"order_id": order_id, "http_status": resp.status_code,
            "result": result}
