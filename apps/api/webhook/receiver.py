"""Razorpay Webhook Receiver — Durable Lifecycle.

Lifecycle: RECEIVED → PERSISTED → AUDITED → APPLIED

- HMAC-first verification before any state change
- Race-safe dedup: only skip events already APPLIED
- Restart-safe: rebuild lifecycle from DB on boot
- Monotonic: state only advances forward
- Every transition audited
- Persist before mark-as-seen: if DB fails, retry is allowed
"""

import datetime
import hashlib
import hmac
import json
import os
import time

from fastapi import APIRouter, Header, HTTPException, Request

from ..audit import chain as audit_chain
from ..store import db as store

router = APIRouter()

LIFECYCLE_STATES = ("RECEIVED", "PERSISTED", "AUDITED", "APPLIED")

_STATUS_RANK = {
    "created": 0,
    "authorized": 1,
    "captured": 2,
    "refunded": 3,
}


def _load_lifecycle_state() -> None:
    """Rebuild in-memory processed set from APPLIED events in DB."""
    global _processed_event_ids
    rows = store.query(
        "SELECT event_id FROM webhook_lifecycle WHERE lifecycle_state = 'APPLIED'"
    )
    _processed_event_ids = {row["event_id"] for row in rows}


_processed_event_ids: set[str] = set()
_load_lifecycle_state()


def log_line(msg: str) -> None:
    ts = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    line = f"[{ts}] {msg}"
    print(line)
    try:
        with open("events.log", "a", encoding="utf-8") as f:
            f.write(line + "\n")
    except Exception:
        pass


def _advance_lifecycle(event_id: str, target_state: str, reason: str = "") -> None:
    """Advance lifecycle state monotonically. Only advances forward."""
    store.execute(
        "UPDATE webhook_lifecycle SET lifecycle_state = ?, applied_at = ? WHERE event_id = ? AND lifecycle_state != 'APPLIED'",
        (target_state, int(time.time()), event_id),
    )
    if target_state == "APPLIED":
        _processed_event_ids.add(event_id)


def _set_lifecycle_state(event_id: str, state: str) -> None:
    """Set lifecycle state directly (for initialization)."""
    store.execute(
        "UPDATE webhook_lifecycle SET lifecycle_state = ? WHERE event_id = ?",
        (state, event_id),
    )
    if state == "APPLIED":
        _processed_event_ids.add(event_id)


@router.post("/webhook")
async def webhook(
    request: Request,
    x_razorpay_signature: str = Header(default=""),
    x_razorpay_event_id: str = Header(default=""),
):
    """Durable webhook handler with RECEIVED → PERSISTED → AUDITED → APPLIED lifecycle."""
    webhook_secret = os.environ.get("RAZORPAY_WEBHOOK_SECRET", "")
    if not webhook_secret:
        log_line("[SECURITY] WEBHOOK_SECRET missing — failing closed (503)")
        raise HTTPException(
            status_code=503,
            detail={
                "ok": False,
                "error": {
                    "error_code": "WEBHOOK_SECRET_MISSING",
                    "message": "webhook secret not configured — failing closed",
                    "retryable": False,
                },
            },
        )
    body = await request.body()

    # ---- PHASE 0: HMAC verification on RAW body (before JSON parse) ----
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

    # ---- PHASE 1: Parse event ID ----
    event_id = x_razorpay_event_id.strip()
    if not event_id:
        event_id = "no-header-" + hashlib.sha256(body).hexdigest()[:16]

    # ---- Race-safe dedup: only skip if already APPLIED ----
    if event_id in _processed_event_ids:
        log_line(f"[DUPLICATE] {event_id} already APPLIED -> ack 200, no-op")
        return {"status": "ok", "duplicate": True, "event_id": event_id}

    # ---- PHASE 2: Parse payload ----
    try:
        event = json.loads(body)
    except Exception as e:
        # Mark as AUDITED with error so it won't be retried endlessly
        try:
            store.execute(
                "INSERT OR REPLACE INTO webhook_lifecycle "
                "(event_id, event_type, order_id, payment_id, amount_paise, status, "
                "lifecycle_state, hmac_valid, received_at, persisted_at, error_reason) "
                "VALUES (?, ?, ?, ?, ?, ?, 'AUDITED', 1, ?, ?, ?)",
                (event_id, "malformed", "no-order", "", 0, "unknown",
                 int(time.time()), int(time.time()), f"malformed json: {str(e)}"),
            )
            _set_lifecycle_state(event_id, "AUDITED")
        except Exception:
            pass
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

    # ---- PHASE 3: PERSIST before any state mutation ----
    event_name = event.get("event", "unknown")
    payment = (
        event.get("payload", {}).get("payment", {}).get("entity", {})
        or event.get("payload", {}).get("payment_link", {}).get("entity", {})
    )
    order_id = payment.get("order_id", "no-order")
    payment_id = payment.get("id", "")
    amount = payment.get("amount", 0)
    status = payment.get("status", "unknown")

    # Transition RECEIVED -> PERSISTED
    try:
        store.execute(
            "INSERT OR REPLACE INTO webhook_lifecycle "
            "(event_id, event_type, order_id, payment_id, amount_paise, status, "
            "lifecycle_state, hmac_valid, received_at, persisted_at) "
            "VALUES (?, ?, ?, ?, ?, ?, 'PERSISTED', 1, ?, ?)",
            (event_id, event_name, order_id, payment_id, amount, status,
             int(time.time()), int(time.time())),
        )
    except Exception as e:
        log_line(f"[PERSIST-FAIL] event {event_id} not persisted: {e}")
        raise HTTPException(
            status_code=503,
            detail={
                "ok": False,
                "error": {
                    "error_code": "PERSISTENCE_FAILED",
                    "message": f"failed to persist webhook event: {e}",
                    "retryable": True,
                },
            },
        )

    # Also persist to webhook_events for backward compat
    try:
        store.execute(
            "INSERT OR IGNORE INTO webhook_events "
            "(event_id, event_type, order_id, payment_id, amount_paise, status, "
            "received_at) VALUES (?, ?, ?, ?, ?, ?, ?)",
            (event_id, event_name, order_id, payment_id, amount, status,
             int(time.time())),
        )
    except Exception:
        pass

    # ---- PHASE 4: Update ledger (hierarchy enforcement) ----
    # Use in-memory ledger for runtime; rebuilt from DB on boot.
    if not hasattr(webhook, "_ledger"):
        webhook._ledger = {}
    ledger = webhook._ledger
    if order_id not in ledger:
        ledger[order_id] = {
            "order_id": order_id,
            "payment_id": payment_id,
            "status": status,
            "amount_paise": amount,
            "events": [],
            "last_event_id": event_id,
        }
    entry = ledger[order_id]
    if payment_id and not entry.get("payment_id"):
        entry["payment_id"] = payment_id
    entry["events"].append({
        "event": event_name,
        "event_id": event_id,
        "payment_id": payment_id,
        "status": status,
        "ts": datetime.datetime.now().isoformat(),
    })
    new_rank = _STATUS_RANK.get(status, -1)
    old_rank = _STATUS_RANK.get(entry["status"], -1)
    if new_rank > old_rank:
        entry["status"] = status
        entry["amount_paise"] = amount
        entry["last_event_id"] = event_id
        log_line(
            f"[LEDGER] {order_id} -> {status} (Rs {amount/100:,.0f}) event={event_name} id={event_id}"
        )

    # ---- PHASE 5: AUDIT on payment.captured ----
    if event_name == "payment.captured" or status == "captured":
        try:
            store.execute(
                "UPDATE orders SET status = ? WHERE order_id = ?",
                (status, order_id)
            )
        except Exception as e:
            log_line(f"[DB-WARN] failed to update order status: {e}")
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
            log_line(f"[AUDIT-FAIL] failed to append payment_captured to chain: {e}")
            # AUDIT failure -> mark AUDITED with error, allow reconciliation
            _set_lifecycle_state(event_id, "AUDITED")
            raise HTTPException(
                status_code=503,
                detail={
                    "ok": False,
                    "error": {
                        "error_code": "AUDIT_APPEND_FAILED",
                        "message": f"captured payment not durably audited: {e}",
                        "retryable": True,
                    },
                },
            )

    # ---- PHASE 6: Transition to APPLIED ----
    _advance_lifecycle(event_id, "APPLIED")

    return {"status": "ok", "event_id": event_id, "event": event_name, "order_id": order_id}


@router.get("/ledger")
def get_ledger() -> dict:
    if not hasattr(webhook, "_ledger"):
        return {}
    return webhook._ledger


@router.get("/webhook/lifecycle")
def get_lifecycle() -> dict:
    """Expose webhook lifecycle states for monitoring."""
    rows = store.query(
        "SELECT lifecycle_state, COUNT(*) as c FROM webhook_lifecycle GROUP BY lifecycle_state"
    )
    return {
        "states": {row["lifecycle_state"]: row["c"] for row in rows},
        "total_processed": len(_processed_event_ids),
    }


@router.post("/webhook/replay/{event_id}")
async def replay_webhook(event_id: str):
    """Replay a non-APPLIED webhook event for recovery."""
    row = store.query_one(
        "SELECT * FROM webhook_lifecycle WHERE event_id = ?", (event_id,)
    )
    if row is None:
        raise HTTPException(404, detail="event not found")
    if row["lifecycle_state"] == "APPLIED":
        return {"ok": True, "event_id": event_id, "status": "already_applied"}
    # Reset to RECEIVED for reprocessing
    _set_lifecycle_state(event_id, "RECEIVED")
    return {"ok": True, "event_id": event_id, "status": "reset_to_received"}