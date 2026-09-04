"""FastAPI routes for the negotiation engine.

POST /negotiation/start      - open a negotiation for a SKU
POST /negotiation/{id}/turn  - run one turn (buyer offer + merchant counter)
POST /negotiation/{id}/run   - run to completion (max_turns or terminal)
GET  /negotiation/{id}       - fetch current state
GET  /negotiation/mission/{mid} - list negotiations for a mission
POST /negotiation/{id}/accept_at - merchant manually accepts a buyer offer
                                   (human-in-the-loop override; audit-chained)

Every route chains to the audit log. The final agreed price from any
negotiation STILL must flow through /tools/submit_proposal -> gateway
evaluate() -> /tools/create_order (INV-1). Negotiation never shortcuts money.
"""
from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field

from ..audit import chain as audit
from ..deps import require_api_key
from . import engine as E
from . import persist as P
from .types import NegotiationStatus

router = APIRouter(prefix="/negotiation", tags=["negotiation"])


class StartReq(BaseModel):
    mission_id: str
    sku: str
    qty: int = Field(ge=1, le=99)
    floor_paise: int = Field(ge=0)
    ceiling_paise: int = Field(ge=0)
    buyer_budget_paise: int = Field(ge=0)
    max_turns: int = Field(default=5, ge=1, le=10)
    walk_away_gap_paise: int = Field(default=500, ge=0)
    ttl_seconds: int = Field(default=600, ge=60, le=3600)
    llm_enabled: bool = True
    parent_action_id: str | None = None


class TurnReq(BaseModel):
    llm_enabled: bool = True


class AcceptAtReq(BaseModel):
    """Human-in-the-loop: merchant manually accepts a buyer's last offer."""
    reviewer: str
    reason: str


@router.post("/start", dependencies=[Depends(require_api_key)])
def start(req: StartReq):
    if req.floor_paise > req.ceiling_paise:
        raise HTTPException(400, "floor_paise must be <= ceiling_paise")
    state = E.start_negotiation(
        mission_id=req.mission_id, sku=req.sku, qty=req.qty,
        floor_paise=req.floor_paise, ceiling_paise=req.ceiling_paise,
        buyer_budget_paise=req.buyer_budget_paise,
        max_turns=req.max_turns,
        walk_away_gap_paise=req.walk_away_gap_paise,
        ttl_seconds=req.ttl_seconds,
        parent_action_id=req.parent_action_id,
        llm_enabled=req.llm_enabled,
    )
    return _state_dict(state)


@router.post("/{nid}/turn", dependencies=[Depends(require_api_key)])
def run_turn(nid: str, req: TurnReq):
    state = P.load(nid)
    if not state:
        raise HTTPException(404, "negotiation not found")
    state = E.run_turn(state, llm_enabled=req.llm_enabled)
    return _state_dict(state)


@router.post("/{nid}/run", dependencies=[Depends(require_api_key)])
def run_to_completion(nid: str, req: TurnReq):
    state = P.load(nid)
    if not state:
        raise HTTPException(404, "negotiation not found")
    state = E.run_to_completion(state, llm_enabled=req.llm_enabled)
    return _state_dict(state)


@router.get("/{nid}")
def get(nid: str):
    state = P.load(nid)
    if not state:
        raise HTTPException(404, "negotiation not found")
    return _state_dict(state)


@router.get("/{nid}/transcript")
def transcript(nid: str):
    """The negotiation as a readable transcript, with the arithmetic done here.

    `savings_paise` is computed server-side from stored offers and the
    stored ceiling. A browser that subtracts two numbers it was handed can
    be made to show any saving you like; a number the server derived from
    its own rows cannot.

    `clamped` on a turn means the model asked for a price outside the
    merchant's floor/ceiling and the bounds layer pulled it back. That is
    the whole negotiation safety story in one boolean, so it is reported
    per turn rather than summarised away.
    """
    state = P.load(nid)
    if not state:
        raise HTTPException(404, "negotiation not found")

    base = _state_dict(state)
    ceiling = state.bounds.ceiling_paise
    final = state.final_price_paise

    turns = []
    for t in base["turns"]:
        for side in ("buyer_offer", "merchant_offer"):
            offer = t.get(side)
            if offer is not None:
                offer["clamped"] = offer["price_paise"] != offer["raw_price_paise"]
                offer["clamp_delta_paise"] = (
                    offer["raw_price_paise"] - offer["price_paise"])
        turns.append(t)

    return {
        **base,
        "turns": turns,
        "original_price_paise": ceiling,
        "final_price_paise": final,
        "savings_paise": max(0, ceiling - final) if final is not None else None,
        "clamped_turn_count": sum(
            1 for t in turns for side in ("buyer_offer", "merchant_offer")
            if (t.get(side) or {}).get("clamped")),
        "bounds_note": ("floor and ceiling come from the merchant's server-side "
                        "bounds; no model output can move them, and any offer "
                        "outside them is clamped before it is recorded"),
    }


@router.get("/mission/{mid}")
def list_for_mission(mid: str):
    states = P.list_for_mission(mid)
    return {"mission_id": mid, "count": len(states),
            "negotiations": [_state_dict(s) for s in states]}


@router.post("/{nid}/accept_at", dependencies=[Depends(require_api_key)])
def accept_at(nid: str, req: AcceptAtReq):
    """Merchant (human reviewer) accepts the buyer's last offer.

    This is the human-in-the-loop gate. The agreed price = buyer's last offer
    price (the merchant concedes). Audit-chained with review_state=approved
    and the reviewer's identity. STILL must go through gateway + create_order.
    """
    state = P.load(nid)
    if not state:
        raise HTTPException(404, "negotiation not found")
    if not state.turns:
        raise HTTPException(409, "no turns yet - nothing to accept")
    last = state.turns[-1]
    if last.buyer_offer is None:
        raise HTTPException(409, "last turn has no buyer offer")
    state.status = NegotiationStatus.ACCEPTED
    state.final_offer = last.buyer_offer
    state.final_price_paise = last.buyer_offer.price_paise
    audit.append(
        actor=f"reviewer:{req.reviewer}",
        action="negotiation_accepted_human",
        payload={"negotiation_id": nid, "reason": req.reason,
                 "final_price_paise": state.final_price_paise},
        parent_action_id=state.parent_action_id,
        review_state="approved",
    )
    P.save(state)
    return _state_dict(state)


def _state_dict(state) -> dict:
    return {
        "negotiation_id": state.negotiation_id,
        "mission_id": state.mission_id,
        "sku": state.bounds.sku,
        "qty": state.bounds.qty,
        "floor_paise": state.bounds.floor_paise,
        "ceiling_paise": state.bounds.ceiling_paise,
        "max_turns": state.bounds.max_turns,
        "buyer_budget_paise": state.buyer_budget_paise,
        "status": state.status.value,
        "final_price_paise": state.final_price_paise,
        "parent_action_id": state.parent_action_id,
        "turns": [
            {
                "turn": t.turn,
                "buyer_offer": _offer_dict(t.buyer_offer),
                "merchant_offer": _offer_dict(t.merchant_offer),
                "gap_paise": t.gap_paise,
                "status": t.status.value,
            } for t in state.turns
        ],
    }


def _offer_dict(o):
    if o is None:
        return None
    return {
        "actor": o.actor.value, "price_paise": o.price_paise,
        "raw_price_paise": o.raw_price_paise, "qty": o.qty,
        "rationale": o.rationale, "turn": o.turn,
    }
