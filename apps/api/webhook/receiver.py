"""
Razorpay Webhook Receiver.

Key behaviors:
1. RAW body HMAC verification before json.loads().
2. Event deduplication keyed strictly on X-Razorpay-Event-Id header.
3. Out-of-order tolerant payment status ledger (created < authorized < captured < refunded).
4. Append-only logging to events.log and audit chain on payment.captured.
"""

import datetime
import hashlib
import hmac
import json
import os

from fastapi import APIRouter, Header, HTTPException, Request

from ..audit import chain as audit_chain

router = APIRouter()

processed_event_ids: set[str] = set()
payment_ledger: dict[str, dict] = {}

STATUS_RANK = {
    "created": 0,
    "authorized": 1,
    "captured": 2,
    "refunded": 3,
}


def log_line(msg: str):
    ts = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    line = f"[{ts}] {msg}"
    print(line)
    try:
        with open("events.log", "a", encoding="utf-8") as f:
            f.write(line + "\n")
    except Exception:
        pass


@router.post("/webhook")
async def webhook(
    request: Request,
    x_razorpay_signature: str = Header(default=""),
    x_razorpay_event_id: str = Header(default=""),
):
    webhook_secret = os.environ.get("RAZORPAY_WEBHOOK_SECRET", "")
    body = await request.body()

    # ---- PHASE 0: HMAC verification (FATAL) ----
    expected = hmac.new(
        webhook_secret.encode("utf-8"), body, hashlib.sha256
    ).hexdigest()

    if not hmac.compare_digest(expected, x_razorpay_signature):
        log_line(f"[SECURITY] BAD SIGNATURE rejected. len={len(body)}")
        raise HTTPException(
            status_code=400,
            detail={
                "ok": False,
                "error": {
                    "error_code": "WEBHOOK_BAD_SIGNATURE",
                    "rule_id": None,
                    "message": "invalid razorpay webhook signature",
                    "retryable": False,
                },
            },
        )

    # ---- PHASE 1: Idempotency (duplicate -> ack 200, NO-OP) ----
    event_id = x_razorpay_event_id.strip()
    if not event_id:
        event_id = "no-header-" + hashlib.sha256(body).hexdigest()[:16]

    if event_id in processed_event_ids:
        log_line(f"[DUPLICATE] {event_id} already processed -> ack 200, no-op")
        return {"status": "ok", "duplicate": True, "event_id": event_id}

    processed_event_ids.add(event_id)

    # ---- PHASE 2: Parse payload ----
    try:
        event = json.loads(body)
    except Exception as e:
        raise HTTPException(
            status_code=400,
            detail={
                "ok": False,
                "error": {
                    "error_code": "WEBHOOK_MALFORMED_JSON",
                    "rule_id": None,
                    "message": f"malformed json: {str(e)}",
                    "retryable": False,
                },
            },
        )

    event_name = event.get("event", "unknown")
    payment = (
        event.get("payload", {}).get("payment", {}).get("entity", {})
        or event.get("payload", {}).get("payment_link", {}).get("entity", {})
    )
    order_id = payment.get("order_id", "no-order")
    payment_id = payment.get("id", "")
    amount = payment.get("amount", 0)
    status = payment.get("status", "unknown")

    # ---- PHASE 3: Update ledger (hierarchy enforcement) ----
    if order_id not in payment_ledger:
        payment_ledger[order_id] = {
            "order_id": order_id,
            "payment_id": payment_id,
            "status": status,
            "amount_paise": amount,
            "events": [],
            "last_event_id": event_id,
        }

    entry = payment_ledger[order_id]
    if payment_id and not entry.get("payment_id"):
        entry["payment_id"] = payment_id

    entry["events"].append({
        "event": event_name,
        "event_id": event_id,
        "payment_id": payment_id,
        "status": status,
        "ts": datetime.datetime.now().isoformat(),
    })

    new_rank = STATUS_RANK.get(status, -1)
    old_rank = STATUS_RANK.get(entry["status"], -1)

    if new_rank > old_rank:
        entry["status"] = status
        entry["amount_paise"] = amount
        entry["last_event_id"] = event_id
        log_line(
            f"[LEDGER] {order_id} -> {status} (Rs {amount/100:,.0f}) event={event_name} id={event_id}"
        )
    else:
        log_line(
            f"[LEDGER-SKIP] {order_id} {event_name} (stale, current={entry['status']})"
        )

    # ---- PHASE 4: Audit Chain append on payment.captured ----
    if event_name == "payment.captured" or status == "captured":
        try:
            audit_chain.append(
                "webhook",
                "payment_captured",
                {
                    "order_id": order_id,
                    "payment_id": payment_id,
                    "amount_paise": amount,
                    "event_id": event_id,
                },
            )
        except Exception as e:
            log_line(f"[AUDIT-WARN] failed to append payment_captured to chain: {e}")

    return {"status": "ok", "event_id": event_id, "event": event_name, "order_id": order_id}


@router.get("/ledger")
def get_ledger():
    return payment_ledger
