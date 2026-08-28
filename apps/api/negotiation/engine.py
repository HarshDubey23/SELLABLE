"""The bounded negotiation loop.

This is the orchestrator. It:
  1. Loads deterministic bounds for the SKU (floor, ceiling, qty, max_turns).
  2. Runs turn-by-turn: buyer offers (LLM rationale, deterministic price),
     merchant counters (deterministic price, LLM rationale).
  3. After every turn, checks accept / walk_away / ttl.
  4. Chains EVERY offer to the audit log with parent_action_id.
  5. On accept, returns the final price. The CALLER must still pass the
     agreed price through gateway.evaluate() and create_order (INV-1).

The LLM is called exactly twice per turn (buyer rationale + merchant
rationale). The numeric prices come from strategies.py (deterministic).
"""
from __future__ import annotations

import time
import uuid

from ..audit import chain as audit
from . import bounds as B
from . import strategies as S
from .llm import generate_offer_rationale, generate_walk_away_rationale
from .persist import save as persist_save
from .types import (
    NegotiationActor,
    NegotiationBounds,
    NegotiationResult,
    NegotiationState,
    NegotiationStatus,
    Offer,
    Turn,
)


def start_negotiation(*, mission_id: str, sku: str, qty: int,
                      floor_paise: int, ceiling_paise: int,
                      buyer_budget_paise: int,
                      max_turns: int = 5,
                      walk_away_gap_paise: int = 500,
                      ttl_seconds: int = 600,
                      parent_action_id: str | None = None,
                      llm_enabled: bool = True) -> NegotiationState:
    """Create a new negotiation. Does NOT run any turns yet."""
    bounds = NegotiationBounds(
        sku=sku, floor_paise=floor_paise, ceiling_paise=ceiling_paise,
        qty=qty, max_turns=max_turns,
        walk_away_gap_paise=walk_away_gap_paise, ttl_seconds=ttl_seconds,
    )
    nid = f"NEG-{uuid.uuid4().hex[:12].upper()}"
    now = int(time.time())
    state = NegotiationState(
        negotiation_id=nid, mission_id=mission_id, sku=sku, bounds=bounds,
        buyer_budget_paise=buyer_budget_paise, created_at=now, updated_at=now,
        parent_action_id=parent_action_id,
    )
    # Audit: negotiation opened
    seq = audit.append(
        actor="merchant", action="negotiation_opened",
        payload={"negotiation_id": nid, "mission_id": mission_id, "sku": sku,
                 "qty": qty, "floor_paise": floor_paise,
                 "ceiling_paise": ceiling_paise,
                 "buyer_budget_paise": buyer_budget_paise,
                 "max_turns": max_turns},
        parent_action_id=parent_action_id,
        review_state="auto_approved",
    )
    state.parent_action_id = audit.action_id(seq)
    persist_save(state)
    return state


def run_turn(state: NegotiationState, *, llm_enabled: bool = True,
             now_ts: int | None = None) -> NegotiationState:
    """Run one turn (buyer offer + merchant counter). Returns updated state.

    Mutates and persists state. Chains two audit rows (buyer offer, merchant
    offer). If the turn results in ACCEPTED or WALKED_AWAY, chains a third.
    """
    now_ts = now_ts or int(time.time())
    if state.status != NegotiationStatus.OPEN:
        return state  # terminal, no-op

    # TTL check
    if not B.check_ttl(state.created_at, now_ts, state.bounds):
        state.status = NegotiationStatus.EXPIRED
        audit.append(
            actor="system", action="negotiation_expired",
            payload={"negotiation_id": state.negotiation_id},
            parent_action_id=state.parent_action_id,
            review_state="auto_approved",
        )
        persist_save(state)
        return state

    turn_num = len(state.turns) + 1
    prev_buyer = state.turns[-1].buyer_offer if state.turns else None
    prev_merchant = state.turns[-1].merchant_offer if state.turns else None

    # ---- Buyer offer (deterministic price, LLM rationale) ----
    if turn_num == 1:
        buyer_price = S.buyer_initial_offer(state.bounds, state.buyer_budget_paise)
    else:
        assert prev_buyer is not None and prev_merchant is not None
        buyer_price = S.buyer_next_offer(
            prev_buyer.price_paise, prev_merchant.price_paise,
            state.buyer_budget_paise, state.bounds
        )
    # Clamp + monotonic (defense in depth; strategies already clamp)
    buyer_offer = B.clamp_offer(
        buyer_price, state.bounds, NegotiationActor.BUYER, state.bounds.qty,
        "", turn_num
    )
    if not B.check_monotonic(prev_buyer, buyer_offer):
        # Force monotonic: snap to prev_buyer price
        assert prev_buyer is not None
        buyer_offer = Offer(
            actor=buyer_offer.actor, price_paise=prev_buyer.price_paise,
            raw_price_paise=buyer_price, qty=buyer_offer.qty,
            rationale="[clamped:monotonic]", turn=turn_num,
        )
    buyer_offer = Offer(
        actor=buyer_offer.actor, price_paise=buyer_offer.price_paise,
        raw_price_paise=buyer_offer.raw_price_paise, qty=buyer_offer.qty,
        rationale=generate_offer_rationale(
            actor="buyer", sku=state.bounds.sku,
            price_paise=buyer_offer.price_paise, turn=turn_num,
            prev_gap_paise=prev_merchant.price_paise - prev_buyer.price_paise
                           if (prev_buyer and prev_merchant) else None,
            budget_paise=state.buyer_budget_paise,
            floor_paise=state.bounds.floor_paise,
            ceiling_paise=state.bounds.ceiling_paise,
            llm_enabled=llm_enabled,
        ),
        turn=turn_num,
    )
    seq_b = audit.append(
        actor="buyer", action="negotiation_offer_buyer",
        payload={"negotiation_id": state.negotiation_id, "turn": turn_num,
                 "sku": state.bounds.sku, "qty": state.bounds.qty,
                 "price_paise": buyer_offer.price_paise,
                 "raw_price_paise": buyer_offer.raw_price_paise,
                 "rationale": buyer_offer.rationale},
        parent_action_id=state.parent_action_id,
        reasoning_trace={"turn": turn_num, "actor": "buyer",
                         "price": buyer_offer.price_paise},
        review_state="auto_approved",
    )

    # ---- Merchant counter (deterministic price, LLM rationale) ----
    merchant_price = S.merchant_counter_price(
        turn_num, state.bounds, buyer_offer.price_paise
    )
    merchant_offer = B.clamp_offer(
        merchant_price, state.bounds, NegotiationActor.MERCHANT,
        state.bounds.qty, "", turn_num
    )
    merchant_offer = Offer(
        actor=merchant_offer.actor, price_paise=merchant_offer.price_paise,
        raw_price_paise=merchant_offer.raw_price_paise, qty=merchant_offer.qty,
        rationale=generate_offer_rationale(
            actor="merchant", sku=state.bounds.sku,
            price_paise=merchant_offer.price_paise, turn=turn_num,
            prev_gap_paise=merchant_offer.price_paise - buyer_offer.price_paise,
            budget_paise=state.buyer_budget_paise,
            floor_paise=state.bounds.floor_paise,
            ceiling_paise=state.bounds.ceiling_paise,
            llm_enabled=llm_enabled,
        ),
        turn=turn_num,
    )
    seq_m = audit.append(
        actor="merchant", action="negotiation_offer_merchant",
        payload={"negotiation_id": state.negotiation_id, "turn": turn_num,
                 "sku": state.bounds.sku, "qty": state.bounds.qty,
                 "price_paise": merchant_offer.price_paise,
                 "raw_price_paise": merchant_offer.raw_price_paise,
                 "rationale": merchant_offer.rationale},
        parent_action_id=audit.action_id(seq_b),
        reasoning_trace={"turn": turn_num, "actor": "merchant",
                         "price": merchant_offer.price_paise},
        review_state="auto_approved",
    )

    gap = merchant_offer.price_paise - buyer_offer.price_paise
    new_status = B.status_after_turn(
        turn_num, state.bounds, buyer_offer, merchant_offer
    )

    turn = Turn(
        turn=turn_num, buyer_offer=buyer_offer, merchant_offer=merchant_offer,
        gap_paise=gap, status=new_status,
    )
    state.turns.append(turn)
    state.updated_at = now_ts

    if new_status == NegotiationStatus.ACCEPTED:
        state.status = new_status
        state.final_offer = merchant_offer
        state.final_price_paise = B.effective_price(merchant_offer, buyer_offer)
        # Budget hard-gate: if final > budget, downgrade to walk_away
        if not B.check_budget(state.final_price_paise, state.buyer_budget_paise):
            state.status = NegotiationStatus.WALKED_AWAY
            state.final_offer = None
            state.final_price_paise = None
            audit.append(
                actor="system", action="negotiation_budget_exceeded",
                payload={"negotiation_id": state.negotiation_id,
                         "final_price_paise": merchant_offer.price_paise,
                         "buyer_budget_paise": state.buyer_budget_paise},
                parent_action_id=audit.action_id(seq_m),
                error_code="BUDGET_EXCEEDED",
                review_state="auto_approved",
            )
        else:
            audit.append(
                actor="merchant", action="negotiation_accepted",
                payload={"negotiation_id": state.negotiation_id,
                         "final_price_paise": state.final_price_paise,
                         "turns": turn_num},
                parent_action_id=audit.action_id(seq_m),
                review_state="pending_merchant",
            )
    elif new_status == NegotiationStatus.WALKED_AWAY:
        state.status = new_status
        wa_rationale = generate_walk_away_rationale(
            sku=state.bounds.sku, final_gap_paise=gap, turns=turn_num
        )
        audit.append(
            actor="system", action="negotiation_walked_away",
            payload={"negotiation_id": state.negotiation_id,
                     "final_gap_paise": gap, "turns": turn_num,
                     "rationale": wa_rationale},
            parent_action_id=audit.action_id(seq_m),
            review_state="auto_approved",
        )

    persist_save(state)
    return state


def run_to_completion(state: NegotiationState, *, llm_enabled: bool = True,
                      max_iterations: int = 10) -> NegotiationState:
    """Run turns until terminal (ACCEPTED / WALKED_AWAY / EXPIRED)."""
    iters = 0
    while state.status == NegotiationStatus.OPEN and iters < max_iterations:
        state = run_turn(state, llm_enabled=llm_enabled)
        iters += 1
    return state


def to_result(state: NegotiationState) -> NegotiationResult:
    """Build an immutable NegotiationResult from a state for API responses."""
    audit_ids: list[str] = []
    if state.parent_action_id:
        audit_ids.append(state.parent_action_id)
    return NegotiationResult(
        negotiation_id=state.negotiation_id,
        status=state.status,
        turns=tuple(state.turns),
        final_price_paise=state.final_price_paise,
        final_offer=state.final_offer,
        audit_action_ids=tuple(audit_ids),
        reason=f"negotiation {state.status.value} after {len(state.turns)} turns",
    )
