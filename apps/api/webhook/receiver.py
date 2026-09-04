"""
Razorpay Webhook Receiver.

Key behaviors:
1. RAW body HMAC verification before json.loads().
2. Event deduplication keyed strictly on X-Razorpay-Event-Id header,
   backed by a DURABLE processing lifecycle (RECEIVED -> APPLIED) rather
   than by "a row exists". A crash between persistence and audit must
   leave the event replayable, not silently complete.
3. Out-of-order tolerant payment status ledger (created < authorized < captured < refunded).
4. Append-only logging to events.log and audit chain on payment.captured.
5. Every event is persisted to SQLite; the dedup set and payment ledger
   are rebuilt from disk at boot, so restarts lose nothing.

WHY THE LIFECYCLE COLUMN EXISTS
-------------------------------
The obvious implementation persists the event, then audits it, then
returns 200 — and rebuilds the dedup set at boot from "every event_id in
the table". That is wrong. If the process dies after the INSERT and
before the audit append, the next boot sees the row, calls the event
already-processed, and Razorpay's retry is answered with a cheerful
duplicate-ack. The capture is now permanently missing from the audit
chain and nothing ever notices.

So an event is only *processed* once it reaches APPLIED. Rows stuck in
RECEIVED are surfaced at boot and at GET /webhook/pending, and a retry
of one is reprocessed rather than acked away.
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


RECEIVED = "RECEIVED"
APPLIED = "APPLIED"


def pending_events() -> list[dict]:
    """Events that were persisted but never fully applied.

    A non-empty list means a process died mid-handling. Razorpay retries
    will resolve them; until then they are visible rather than hidden.
    """
    return store.query(
        "SELECT event_id, event_type, order_id, payment_id, status, received_at "
        "FROM webhook_events WHERE processing_state IS NOT ? ORDER BY received_at",
        (APPLIED,),
    )


def _load_persisted_state() -> None:
    """Rebuild the dedup set and payment ledger from the DB on boot.

    Only APPLIED events count as processed. An event still in RECEIVED
    was interrupted, so it stays replayable.
    """
    global processed_event_ids, payment_ledger

    for row in store.query(
            "SELECT event_id FROM webhook_events WHERE processing_state = ?",
            (APPLIED,)):
        processed_event_ids.add(row["event_id"])

    stuck = pending_events()
    if stuck:
        print(f"[BOOT] webhook recovery: {len(stuck)} event(s) persisted but "
              f"not applied; they remain replayable "
              f"{[e['event_id'] for e in stuck]}")

    # Rebuild ledger by replaying persisted events through the same
    # status hierarchy the live handler uses (stale events never win).
    for ev in store.query(
        "SELECT order_id, event_type, payment_id, amount_paise, status "
        "FROM webhook_events WHERE order_id IS NOT NULL "
        "AND order_id != 'no-order' AND processing_state = ? "
        "ORDER BY received_at", (APPLIED,)
    ):
        entry = payment_ledger.setdefault(ev["order_id"], {
            "order_id": ev["order_id"],
            "payment_id": ev["payment_id"] or "",
            "status": "created",
            "amount_paise": ev["amount_paise"] or 0,
            "events": [],
            "last_event_id": "",
        })
        if ev["payment_id"] and not entry.get("payment_id"):
            entry["payment_id"] = ev["payment_id"]
        new_rank = STATUS_RANK.get(ev["status"], -1)
        old_rank = STATUS_RANK.get(entry["status"], -1)
        if new_rank > old_rank:
            entry["status"] = ev["status"]
            entry["amount_paise"] = ev["amount_paise"] or 0
        entry["events"].append({
            "event": ev["event_type"], "event_id": "(persisted)",
            "payment_id": ev["payment_id"] or "", "status": ev["status"],
            "ts": "(pre-boot)",
        })


_load_persisted_state()


@router.post("/webhook")
async def webhook(
    request: Request,
    x_razorpay_signature: str = Header(default=""),
    x_razorpay_event_id: str = Header(default=""),
):
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

    # ---- PHASE 1: Idempotency (duplicate -> ack 200, NO-OP) ----
    event_id = x_razorpay_event_id.strip()
    if not event_id:
        event_id = "no-header-" + hashlib.sha256(body).hexdigest()[:16]

    if event_id in processed_event_ids:
        log_line(f"[DUPLICATE] {event_id} already processed -> ack 200, no-op")
        return {"status": "ok", "duplicate": True, "event_id": event_id}

    # Do NOT mark as seen before persistence — if DB fails, retry must be allowed

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

    # ---- PERSIST: the event hits disk before any state mutation ----
    # If persistence fails, do NOT mark as seen — allow Razorpay retry
    try:
        store.execute(
            "INSERT OR IGNORE INTO webhook_events "
            "(event_id, event_type, order_id, payment_id, amount_paise, status, "
            " received_at, processing_state) VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
            (event_id, event_name, order_id, payment_id, amount, status,
             int(time.time()), RECEIVED)
        )
    except Exception as e:
        log_line(f"[PERSIST-FAIL] event {event_id} not persisted: {e} — will allow retry")
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
        # PERSIST: reflect capture onto the durable order row.
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
            log_line(f"[AUDIT-FAIL] failed to append payment_captured to chain: {e} — failing closed")
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

    # ---- PHASE 5: commit the lifecycle ------------------------------
    # Persistence, ledger application and audit have all succeeded. Only
    # now does the event become durably "processed": the APPLIED marker is
    # what a future boot trusts, not the mere existence of the row.
    store.execute(
        "UPDATE webhook_events SET processing_state = ?, applied_at = ? "
        "WHERE event_id = ?",
        (APPLIED, int(time.time()), event_id),
    )
    processed_event_ids.add(event_id)
    return {"status": "ok", "event_id": event_id, "event": event_name,
            "order_id": order_id, "processing_state": APPLIED}


@router.get("/webhook/pending")
def webhook_pending():
    """Events persisted but not yet applied — the crash-window surface."""
    stuck = pending_events()
    return {"pending_count": len(stuck), "pending": stuck,
            "applied_count": len(processed_event_ids),
            "lifecycle": [RECEIVED, APPLIED]}


@router.get("/ledger")
def get_ledger():
    return payment_ledger
