import os, datetime
from pathlib import Path
from dotenv import load_dotenv

# .env from project root (2 levels up from apps/api/main.py)
load_dotenv(Path(__file__).resolve().parents[2] / ".env")

from fastapi import FastAPI, Request, HTTPException, Header
import hmac, hashlib, json

from .manifest import router as manifest_router
from .tools import router as tools_router

app = FastAPI()

app.include_router(manifest_router)
app.include_router(tools_router)

WEBHOOK_SECRET = os.environ["RAZORPAY_WEBHOOK_SECRET"]

# ============================================================
# IN-MEMORY STORES (audit hash-chain replaces these on Day 3)
# ============================================================
processed_event_ids = set()          # idempotency: seen event IDs
payment_ledger = {}                  # order_id -> current state


def log_line(msg: str):
    """Append to events.log AND print to console."""
    ts = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    line = f"[{ts}] {msg}"
    print(line)
    with open("events.log", "a", encoding="utf-8") as f:
        f.write(line + "\n")


# Status can only move UP this ladder, never down.
# (Razorpay can deliver payment.captured BEFORE payment.authorized)
STATUS_RANK = {
    "created": 0,
    "authorized": 1,
    "captured": 2,
    "refunded": 3,
}


@app.post("/webhook")
async def webhook(
    request: Request,
    x_razorpay_signature: str = Header(default=""),
    x_razorpay_event_id: str = Header(default=""),
):
    # ---- PHASE 0: HMAC verification (FATAL) ----
    body = await request.body()  # RAW body, never parse before verify
    expected = hmac.new(
        WEBHOOK_SECRET.encode(), body, hashlib.sha256
    ).hexdigest()

    if not hmac.compare_digest(expected, x_razorpay_signature):
        log_line(f"[SECURITY] BAD SIGNATURE rejected. len={len(body)}")
        raise HTTPException(status_code=400, detail="invalid signature")

    # ---- PHASE 1: Idempotency (duplicate -> ack 200, NO-OP) ----
    event_id = x_razorpay_event_id  # FIX: id lives in HEADER, not payload
    if not event_id:
        event_id = "no-header-" + hashlib.sha256(body).hexdigest()[:16]

    if event_id in processed_event_ids:
        log_line(f"[DUPLICATE] {event_id} already processed -> ack 200, no-op")
        return {"status": "ok", "duplicate": True, "event_id": event_id}

    processed_event_ids.add(event_id)

    # ---- PHASE 2: Parse (out-of-order tolerant) ----
    event = json.loads(body)
    event_name = event.get("event", "unknown")

    payment = (
        event.get("payload", {}).get("payment", {}).get("entity", {})
        or event.get("payload", {}).get("payment_link", {}).get("entity", {})
    )
    order_id = payment.get("order_id", "no-order")
    amount = payment.get("amount", 0)
    status = payment.get("status", "unknown")

    # ---- PHASE 3: Update ledger (status only moves UP) ----
    if order_id not in payment_ledger:
        payment_ledger[order_id] = {
            "status": status,
            "amount_paise": amount,
            "events": [],
            "last_event_id": event_id,
        }

    entry = payment_ledger[order_id]
    entry["events"].append({
        "event": event_name,
        "event_id": event_id,
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
            f"[LEDGER] {order_id} -> {status} "
            f"(Rs {amount/100:,.0f}) event={event_name} id={event_id}"
        )
    else:
        log_line(
            f"[LEDGER-SKIP] {order_id} {event_name} (stale, current={entry['status']})"
        )

    return {"status": "ok", "event_id": event_id, "event": event_name}


@app.get("/health")
def health():
    return {
        "status": "alive",
        "events_processed": len(processed_event_ids),
        "orders_tracked": len(payment_ledger),
    }


@app.get("/ledger")
def get_ledger():
    """Current payment state — the eval harness reads this."""
    return payment_ledger
