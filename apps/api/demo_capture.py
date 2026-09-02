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

import os
import time

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field

from .audit import chain as audit
from .deps import require_api_key
from .gateway.mission_verify import dumps as _dumps
from .gateway.mission_verify import sign_mission as _sign
from .mandates.mandates import (
    CartMandate,
    IntentMandate,
    sign_cart,
    sign_intent,
)
from .products import CATALOG
from .razorpay_client import (
    RazorpayAPIError,
    attempt_checkout_payment,
    capture_payment,
    list_order_payments,
)
from .tools import (
    CreateOrderReq,
    ProposalReq,
    QuoteReq,
    tool_create_order,
    tool_quote,
    tool_submit_proposal,
)

router = APIRouter(prefix="/demo", tags=["demo-capture"])


class CaptureReq(BaseModel):
    amount_paise: int = Field(ge=100)
    sku: str = "DEMO-SKU"
    mission_id: str = "MSN-CAPTURE-DEMO"
    use_failing_card: bool = False


@router.post("/capture", dependencies=[Depends(require_api_key)])
async def demo_capture(req: CaptureReq):
    """Run a live captured-payment demo. Returns the audit chain slice.
    Now properly routed through the canonical money gates (INV-1).
    """
    if req.sku not in CATALOG:
        raise HTTPException(400, f"Unknown SKU: {req.sku}")

    # Use real catalog price; ignore requested amount to preserve invariants.
    real_amount = CATALOG[req.sku]["price_paise"]

    parent_seq = audit.append(
        actor="demo", action="demo_capture_started",
        payload={"amount_paise": real_amount, "sku": req.sku,
                 "mission_id": req.mission_id},
        review_state="auto_approved",
    )
    parent_aid = audit.action_id(parent_seq)

    # 1. Sign Mission
    now_ts = int(time.time())
    m_blob = {
        "mission_id": req.mission_id,
        "intent": "demo capture",
        "budget_paise": real_amount + 100000,
        "allowed_categories": [CATALOG[req.sku]["category"]],
        "forbidden_categories": [],
        "upsell_cap": 1.3,
        "expires_at": now_ts + 600,
    }
    m_blob["signature"] = _sign(_dumps(m_blob))

    # 2. Submit Proposal
    proposal_req = ProposalReq(
        mission=m_blob,
        items=[{"sku": req.sku, "qty": 1}]
    )
    verdict_resp = await tool_submit_proposal(proposal_req)
    if not verdict_resp["ok"] or verdict_resp["data"]["decision"] != "APPROVE":
        raise HTTPException(403, f"Gateway rejected: {verdict_resp.get('data')}")

    approve_seq = verdict_resp["seq"]
    proposal_hash = verdict_resp["data"]["proposal_hash"]

    # 3. Get Quote
    quote_req = QuoteReq(items=[{"sku": req.sku, "qty": 1}], mission_id=req.mission_id)
    quote_resp = await tool_quote(quote_req)
    quote_id = quote_resp["quote_id"]

    # 4. Sign Mandates
    intent_mandate = sign_intent(IntentMandate(
        mission_id=req.mission_id, user_id=f"user_{req.mission_id}",
        ceiling_paise=real_amount, expires_at=int(time.time()) + 3600,
    ), os.environ["USER_MANDATE_KEY"])

    cart_mandate = sign_cart(CartMandate(
        mission_id=req.mission_id, cart_hash=proposal_hash or "",
        amount_paise=real_amount, signed_at=int(time.time()),
        expires_at=int(time.time()) + 3600,
    ), os.environ["USER_MANDATE_KEY"])

    # 5. Create Order via CANONICAL path
    order_req = CreateOrderReq(
        quote_id=quote_id,
        proposal_hash=proposal_hash or "",
        approve_seq=approve_seq,
        intent_mandate=intent_mandate,
        cart_mandate=cart_mandate,
    )
    idem_key = f"idem_{req.mission_id}_{time.time_ns()}"

    try:
        order_resp = await tool_create_order(order_req, x_idempotency_key=idem_key)
        order_id = order_resp["order_id"]
        order = {"id": order_id, "amount_paid": order_resp["amount_paise"]}
    except Exception as e:
        audit.append(
            actor="merchant", action="order_create_failed",
            payload={"error": str(e)}, parent_action_id=parent_aid,
            review_state="escalated",
        )
        raise HTTPException(502, f"order create failed: {e}") from e

    # Retrieve seq_order from tail to link parent correctly
    seq_order = audit.tail(1)[0]["seq"] if audit.entries() else parent_seq

    # Step 6: attempt payment via public-key flow (test card)
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
            amount_paise=real_amount,
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
                       audit_tail=audit.tail(15))

    payment_id = None
    status = "unknown"
    if isinstance(pay_resp, dict):
        result = pay_resp.get("result", pay_resp)
        if isinstance(result, dict):
            payment_id = result.get("id") or result.get("payment_id")
            status = result.get("status") or result.get("entity") or "unknown"
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
            cap = capture_payment(payment_id, real_amount)
            status = cap.get("status", status)
            audit.append(
                actor="merchant", action="payment_captured",
                payload={"order_id": order["id"], "payment_id": payment_id,
                         "amount_paise": real_amount,
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

    # Polling...
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
                   audit_tail=audit.tail(15))


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
