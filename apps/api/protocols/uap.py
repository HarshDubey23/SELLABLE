"""NPCI Universal Agent Protocol (UAP v1.0) adapter (Track 01 Core).

Translates an Indian NPCI-standard Agent Commerce intent + UPI delegated mandate
into the SELLABLE canonical proposal structure.

NPCI UAP specifies:
- uap_agent_id: The certified buyer agent identity
- mandate_token: Digital e-mandate containing max_amount_paise, purpose_code, expiry
- consent_handle: UPI delegated consent identifier
- intent_payload: Line items with merchant SKUs and quantities

ADAPTER INVARIANTS:
  - MUST NOT import apps.api.gateway (translate; never decide)
  - MUST NOT construct verdicts (the executor's response passes through)
  - MUST NOT contain rule logic (all money decisions remain in the gateway)
"""
from __future__ import annotations

import time
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field

from ..deps import require_api_key
from ..products import CATALOG
from ..tools import ProposalReq, tool_submit_proposal

router = APIRouter(prefix="/protocol/uap", tags=["protocols"])


class UAPLineItem(BaseModel):
    sku: str = Field(..., description="Merchant SKU identifier")
    qty: int = Field(1, ge=1, description="Item quantity")


class UAPMandate(BaseModel):
    mandate_id: str = Field(..., description="NPCI UAP mandate reference")
    max_amount_paise: int = Field(..., gt=0, description="Spending limit in paise")
    purpose_code: str = Field("COMMERCE_PURCHASE", description="NPCI mandate purpose")
    valid_until: int = Field(..., description="Unix timestamp expiration")
    signature: str = Field(..., description="Cryptographic mandate signature")


class UAPTransactionReq(BaseModel):
    uap_agent_id: str = Field(..., description="Certified NPCI Agent ID")
    consent_handle: str = Field(..., description="Consumer UPI delegated consent handle")
    mandate: UAPMandate
    items: list[UAPLineItem]
    mission: dict = Field(..., description="Signed sellable mission (R9 anchor)")


@router.post("/transact", dependencies=[Depends(require_api_key)])
async def npci_uap_transact(req: UAPTransactionReq) -> dict:
    """Translate an NPCI UAP order intent and execute through SELLABLE's deterministic gateway."""
    now_ts = int(time.time())
    if req.mandate.valid_until < now_ts:
        raise HTTPException(400, detail={
            "protocol": "NPCI_UAP",
            "error": "MANDATE_EXPIRED",
            "message": f"UAP mandate expired at {req.mandate.valid_until} (current: {now_ts})",
        })

    # Validate SKU existence against catalog truth
    total_paise = 0
    items_list = []
    for it in req.items:
        if it.sku not in CATALOG:
            raise HTTPException(400, detail={
                "protocol": "NPCI_UAP",
                "error": "UNKNOWN_SKU",
                "message": f"SKU {it.sku} does not exist in merchant catalog",
            })
        item_data = CATALOG[it.sku]
        total_paise += int(item_data.get("price_paise", 0)) * it.qty
        items_list.append({"sku": it.sku, "qty": it.qty})

    if total_paise > req.mandate.max_amount_paise:
        raise HTTPException(400, detail={
            "protocol": "NPCI_UAP",
            "error": "MANDATE_CEILING_EXCEEDED",
            "message": f"Total {total_paise} paise exceeds UAP mandate ceiling {req.mandate.max_amount_paise} paise",
        })

    protocol_scope = {
        "protocol": "NPCI_UAP_v1.0",
        "uap_agent_id": req.uap_agent_id,
        "mandate_id": req.mandate.mandate_id,
        "consent_handle": req.consent_handle,
        "purpose_code": req.mandate.purpose_code,
        "ceiling_paise": req.mandate.max_amount_paise,
        "valid_until": req.mandate.valid_until,
    }

    executor_resp = await tool_submit_proposal(ProposalReq(
        mission=req.mission,
        items=items_list,
        protocol_scope=protocol_scope,
    ))

    verdict_data = executor_resp.get("data", {}) if isinstance(executor_resp, dict) else {}
    decision = verdict_data.get("decision", "REJECT")

    return {
        "protocol": "NPCI_UAP_v1.0",
        "uap_agent_id": req.uap_agent_id,
        "consent_handle": req.consent_handle,
        "settlement_rail": "UPI_DELEGATED_MANDATE",
        "translated_items": items_list,
        "total_paise": total_paise,
        "executor": executor_resp,
        "uap_receipt": {
            "status": "AUTHORIZED" if decision == "APPROVE" else "REJECTED",
            "proposal_hash": verdict_data.get("proposal_hash"),
            "seq": executor_resp.get("seq"),
            "timestamp": now_ts,
        },
    }
