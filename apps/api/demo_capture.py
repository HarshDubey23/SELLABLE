"""Day 5 - live captured-payment demo endpoint.

POST /demo/capture
  Creates a Razorpay test-mode order, triggers a card payment via the
  public-key POST /v1/payments flow (test card 4111 1111 1111 1111),
  polls until captured (or timeout), and returns the full audit trail.

NOTE: In test mode, card payments via the public-key flow return
'authorized' but Razorpay must auto-capture (if auto-capture is enabled
on the order) OR a separate /v1/payments/{id}/capture call is made.
"""
from __future__ import annotations

import time

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field

from .audit import chain as audit
from .deps import require_api_key
from .razorpay_client import (
    RazorpayAPIError,
    attempt_checkout_payment,
    capture_payment,
    create_order,
    list_order_payments,
)

router = APIRouter(prefix="/demo", tags=["demo-capture"])


class CaptureReq(BaseModel):
    amount_paise: int = Field(ge=100)
    sku: str = "DEMO-SKU"
    mission_id: str = "MSN-CAPTURE-DEMO"
    use_failing_card: bool = False


@router.post("/capture", dependencies=[Depends(require_api_key)])
def demo_capture(req: CaptureReq):
    """Run a live captured-payment demo. Returns the audit chain slice."""
    parent_seq = audit.append(
        actor="demo", action="demo_capture_started",
        payload={"amount_paise": req.amount_paise, "sku": req.sku,
                 "mission_id": req.mission_id},
        review_state="auto_approved",
    )
    parent_aid = audit.action_id(parent_seq)

    # Step 1: create order
    try:
        order = create_order(
            amount_paise=req.amount_paise,
            receipt=f"{req.mission_id}-{int(time.time())}",
            notes={"mission_id": req.mission_id, "sku": req.sku,
                   "demo": "capture_flow"},
        )
    except RazorpayAPIError as e:
        audit.append(
            actor="merchant", action="order_create_failed",
            payload={"error": str(e)}, parent_action_id=parent_aid,
            error_code=str(e.status_code), error_reason=str(e.error),
            review_state="escalated",
        )
        raise HTTPException(502, f"order create failed: {e}") from e
    except Exception as e:
        audit.append(
            actor="merchant", action="order_create_failed",
            payload={"error": str(e)}, parent_action_id=parent_aid,
            review_state="escalated",
        )
        raise HTTPException(502, f"order create failed: {e}") from e

    seq_order = audit.append(
        actor="merchant", action="order_created",
        payload={"order_id": order["id"], "amount_paise": req.amount_paise,
                 "mission_id": req.mission_id},
        parent_action_id=parent_aid,
        idempotency_key=f"idem_{order['id']}",
        review_state="auto_approved",
    )

    # Step 2: attempt payment via public-key flow (test card)
    card_number = "4111111111111112" if req.use_failing_card else "4111111111111111"
    method_body = {
        "method": "card",
        "card": {
            "number": card_number,
            "expiry_month": "12",
            "expiry_year": "30",
            "cvv": "123",
            "name": "Test Buyer",
        },
    }
    try:
        pay_resp = attempt_checkout_payment(
            order_id=order["id"],
            amount_paise=req.amount_paise,
            method_body=method_body,
            email="sellable-demo@test.com",
            contact="9000000000",
        )
    except RazorpayAPIError as e:
        audit.append(
            actor="buyer", action="payment_attempt_failed",
            payload={"order_id": order["id"], "card": card_number[:4] + "****",
                     "error": str(e)},
            parent_action_id=audit.action_id(seq_order),
            error_code=str(e.status_code), error_reason=str(e.error),
            review_state="escalated",
        )
        return _result(order, parent_aid, status="payment_failed",
                       audit_tail=audit.tail(6))

    payment_id = None
    status = "unknown"
    if isinstance(pay_resp, dict):
        # attempt_checkout_payment returns {"order_id":..,"http_status":..,"result":{...}}
        result = pay_resp.get("result", pay_resp)
        if isinstance(result, dict):
            payment_id = result.get("id") or result.get("payment_id")
            status = result.get("status") or result.get("entity") or "unknown"
            # If result contains error
            if result.get("error"):
                status = "failed"

    seq_pay = audit.append(
        actor="buyer", action="payment_attempted",
        payload={"order_id": order["id"], "payment_id": payment_id,
                 "status": status, "card": card_number[:4] + "****"},
        parent_action_id=audit.action_id(seq_order),
        review_state="auto_approved",
    )

    if status == "authorized" and payment_id:
        try:
            cap = capture_payment(payment_id, req.amount_paise)
            status = cap.get("status", status)
            audit.append(
                actor="merchant", action="payment_captured",
                payload={"order_id": order["id"], "payment_id": payment_id,
                         "amount_paise": req.amount_paise,
                         "method": cap.get("method", "card")},
                parent_action_id=audit.action_id(seq_pay),
                review_state="auto_approved",
            )
        except RazorpayAPIError as e:
            audit.append(
                actor="merchant", action="capture_failed",
                payload={"payment_id": payment_id, "error": str(e)},
                parent_action_id=audit.action_id(seq_pay),
                error_code=str(e.status_code), error_reason=str(e.error),
                review_state="escalated",
            )
            status = "capture_failed"
        except Exception as e:
            audit.append(
                actor="merchant", action="capture_failed",
                payload={"payment_id": payment_id, "error": str(e)},
                parent_action_id=audit.action_id(seq_pay),
                review_state="escalated",
            )
            status = "capture_failed"

    # Step 4: poll order payments for final authority (max 10s)
    final_status = status
    for _ in range(10):
        time.sleep(1)
        try:
            payments = list_order_payments(order["id"])
            for p in payments:
                if isinstance(p, dict) and p.get("status") == "captured":
                    final_status = "captured"
                    audit.append(
                        actor="merchant", action="payment_captured_polled",
                        payload={"order_id": order["id"],
                                 "payment_id": p.get("id"),
                                 "amount_paise": p.get("amount")},
                        parent_action_id=audit.action_id(seq_pay),
                        review_state="auto_approved",
                    )
                    break
            if final_status == "captured":
                break
        except (RazorpayAPIError, Exception):
            continue

    return _result(order, parent_aid, status=final_status,
                   audit_tail=audit.tail(8))


def _result(order, parent_aid, status, audit_tail):
    return {
        "order_id": order["id"],
        "amount_paise": order.get("amount_paid") or order.get("amount"),
        "final_status": status,
        "captured": status == "captured",
        "parent_action_id": parent_aid,
        "audit_tail": [
            {"seq": e["seq"], "actor": e["actor"], "action": e["action"],
             "action_id": audit.action_id(e["seq"]),
             "parent_action_id": e.get("parent_action_id"),
             "error_code": e.get("error_code"),
             "review_state": e.get("review_state")}
            for e in audit_tail
        ],
    }
