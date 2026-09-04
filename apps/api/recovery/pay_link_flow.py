"""Issue a Razorpay payment link and optionally drive the hosted page.

Honesty: this module never marks a payment captured. The caller polls
the webhook ledger / payments API.
"""
from __future__ import annotations

from typing import Any

from .. import razorpay_client as rp
from ..audit import chain
from ..guardrails.dark_patterns import DarkPatternBlocked, assert_allows


def issue_payment_link(order_id: str, amount_paise: int, mission_id: str,
                       purpose: str = "captured_payment") -> dict[str, Any]:
    description = (
        f"SELLABLE payment for order {order_id}. "
        f"This payment link expires in 24 hours as per policy."
    )
    try:
        scan = assert_allows(description)
    except DarkPatternBlocked as exc:
        chain.append(
            "guardrail", "copy_blocked",
            {"mission_id": mission_id, "order_id": order_id,
             "scan": exc.scan, "copy": description},
            review_state="blocked_dark_pattern",
        )
        raise

    idem = rp.derive_idempotency_key("payment_link", mission_id, order_id, purpose)
    link = rp.create_payment_link(
        amount_paise,
        description=description,
        expire_by_seconds=24 * 3600,
        notes={"order_id": order_id, "mission_id": mission_id, "purpose": purpose},
        idempotency_key=idem,
    )
    seq = chain.append(
        "executor", "payment_link_issued",
        {"order_id": order_id, "link_id": link.get("id"),
         "short_url": link.get("short_url"), "amount_paise": amount_paise,
         "mission_id": mission_id, "copy_scan": scan},
        idempotency_key=idem,
        review_state="pending_merchant",
    )
    return {
        "id": link.get("id"),
        "short_url": link.get("short_url"),
        "expire_by": link.get("expire_by"),
        "idempotency_key": idem,
        "action_id": chain.action_id(seq),
    }
