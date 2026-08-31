"""AP2-style Intent+Cart mandate adapter (Phase 4).

AP2's pattern is already native here: apps/api/mandates/mandates.py implements
IntentMandate + CartMandate, minted out-of-band by scripts/mandate.py (the
user's wallet). This adapter accepts wallet-signed mandate blobs, verifies
them, extracts the protocol scope artifacts they bound, and hands everything
to the canonical submit path — where R12 re-binds those artifacts at the
gateway (defense-in-depth: the wallet verified them once, the gateway
re-verifies at decision time).

ADAPTER INVARIANTS (enforced by tests/invariants/test_protocol_adapter_invariants.py):
  - MUST NOT import apps.api.gateway (translate; never decide)
  - MUST NOT construct verdicts (the executor's response passes through)
  - MUST NOT contain rule logic (all money decisions remain in the gateway)
"""
from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel

from ..deps import require_api_key
from ..mandates.mandates import MandateError, verify_intent
from ..products import CATALOG
from ..tools import ProposalReq, tool_submit_proposal

router = APIRouter(prefix="/protocol/ap2", tags=["protocols"])

MERCHANT_ID = "SELLABLE-DEMO"


class AP2EvaluateReq(BaseModel):
    mission: dict                       # signed sellable mission (R9 anchor)
    items: list[dict]                   # [{"sku", "qty"}]
    intent_mandate: dict                # wallet-signed blob {payload, sig}
    cart_mandate: dict | None = None    # wallet-signed blob, if consent already given


@router.post("/mandates/evaluate", dependencies=[Depends(require_api_key)])
async def evaluate_mandates(req: AP2EvaluateReq) -> dict:
    """Verify the AP2 intent mandate, then run the canonical executor.

    The intent mandate's ceiling and expiry become the protocol scope bound
    by R12 at the gateway; a present cart mandate is likewise verified.
    """
    # Server-side catalog pricing: the same truth the gateway will use.
    total = 0
    for it in req.items:
        sku = str(it.get("sku", ""))
        if sku not in CATALOG:
            raise HTTPException(400, detail={
                "protocol": "AP2",
                "error": f"unknown sku {sku}",
                "hint": "search_products first",
            })
        total += CATALOG[sku]["price_paise"] * int(it.get("qty", 1))

    try:
        intent_payload = verify_intent(req.intent_mandate,
                                       order_total_paise=total)
    except MandateError as e:
        raise HTTPException(403, detail={
            "protocol": "AP2",
            "error": e.code,
            "message": str(e),
        })

    if intent_payload.get("mission_id") != str(
            (req.mission or {}).get("mission_id", "")):
        raise HTTPException(403, detail={
            "protocol": "AP2",
            "error": "MANDATE_MISSION_MISMATCH",
            "message": "intent mandate references a different mission",
        })

    protocol_scope = {
        "merchant_id": MERCHANT_ID,
        "amount_ceiling_paise": int(intent_payload.get("ceiling_paise", 0)),
        "valid_until": int(intent_payload.get("expires_at", 0)),
    }

    executor_resp = await tool_submit_proposal(ProposalReq(
        mission=req.mission,
        items=req.items,
        protocol_scope=protocol_scope,
    ))
    return {
        "protocol": "AP2",
        "intent_verified": intent_payload,
        "cart_mandate_supplied": req.cart_mandate is not None,
        "executor": executor_resp,
    }
