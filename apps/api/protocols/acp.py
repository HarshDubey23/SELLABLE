"""ACP-style checkout session adapter (Phase 4).

Translates an ACP-shaped checkout session into the sellable-v1 artifacts the
executor already understands, then hands them to the canonical submit path.

ADAPTER INVARIANTS (enforced by tests/invariants/test_protocol_adapter_invariants.py):
  - MUST NOT import apps.api.gateway (translate; never decide)
  - MUST NOT construct verdicts (the executor's response passes through)
  - MUST NOT contain rule logic (all money decisions remain in the gateway)

ACP line items use {id, quantity}; sellable uses {sku, qty}. The session must
embed a signed sellable mission — protocol auth rides the mission HMAC
(R9), the same trust anchor as native traffic.
"""
from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field

from ..deps import require_api_key
from ..tools import ProposalReq, tool_submit_proposal

router = APIRouter(prefix="/protocol/acp", tags=["protocols"])


class ACPLineItem(BaseModel):
    id: str = Field(..., description="ACP item id; mapped to sellable sku")
    quantity: int = Field(1, ge=1, description="ACP quantity; mapped to sellable qty")


class ACPSessionReq(BaseModel):
    mission: dict                          # signed sellable mission (R9 anchor)
    line_items: list[ACPLineItem]
    protocol_scope: dict | None = None     # optional protocol artifacts (R12)


@router.post("/checkout_sessions", dependencies=[Depends(require_api_key)])
async def create_checkout_session(req: ACPSessionReq) -> dict:
    """Translate an ACP checkout session and run the canonical executor.

    The verdict in the response is produced by the gateway — this adapter
    never decides; it only reshapes the request.
    """
    items = [{"sku": li.id, "qty": li.quantity} for li in req.line_items]
    if not items:
        raise HTTPException(400, detail={
            "protocol": "ACP",
            "error": "empty line_items",
            "hint": "an ACP checkout session needs at least one line item",
        })
    executor_resp = await tool_submit_proposal(ProposalReq(
        mission=req.mission,
        items=items,
        protocol_scope=req.protocol_scope,
    ))
    return {
        "protocol": "ACP",
        "translated_items": items,
        "executor": executor_resp,
    }
