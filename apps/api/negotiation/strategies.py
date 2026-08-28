"""Deterministic merchant negotiation strategy. Pure stdlib.

The merchant's *numeric* counter-offer is computed here - NOT by the LLM.
This is the "deterministic policy disposes" half of the thesis applied to
negotiation. The LLM only writes the rationale string for the offer.

Strategy: Anchor-Then-Concede (with walk-away)
  Turn 1: anchor at ceiling (MSRP) - merchant opens high.
  Turn 2..max-1: concede by a shrinking step toward floor.
                  step_t = (ceiling - floor) * concede_rate * decay^(t-1)
  Turn max: make the floor offer (best-and-final).
  If buyer never meets the floor within max_turns, walk away.

The concede_rate and decay are config-driven (defaults: 0.25, 0.6).
This makes the merchant predictable, auditable, and impossible to "negotiate
into a loss" - the floor is a hard wall.

N-1 invariant: NO LLM / network / web-framework imports.
"""
from __future__ import annotations

from .types import NegotiationBounds


def merchant_counter_price(turn: int, bounds: NegotiationBounds,
                           last_buyer_price: int | None,
                           concede_rate: float = 0.25,
                           decay: float = 0.6) -> int:
    """Compute the merchant's price for this turn (per-unit, paise).

    turn=1: anchor at ceiling.
    turn>=max_turns: floor (best-and-final).
    otherwise: concede from ceiling toward floor by shrinking steps.

    If the buyer's last offer is already >= the planned counter, snap to the
    buyer's price (accept). This lets the merchant accept a good offer early.
    """
    floor = bounds.floor_paise
    ceiling = bounds.ceiling_paise

    if turn >= bounds.max_turns:
        return floor

    if turn == 1:
        planned = ceiling
    else:
        # cumulative concession from ceiling
        total_concede = 0.0
        span = ceiling - floor
        for t in range(2, turn + 1):
            total_concede += span * concede_rate * (decay ** (t - 2))
        planned = max(floor, ceiling - int(total_concede))

    # Early acceptance: if buyer already meets/exceeds planned, accept.
    if last_buyer_price is not None and last_buyer_price >= planned:
        return last_buyer_price
    return planned


def merchant_should_walk_away(turn: int, bounds: NegotiationBounds,
                              last_buyer_price: int | None) -> bool:
    """Merchant walks away if the buyer's best offer is below floor at turn max."""
    if turn < bounds.max_turns:
        return False
    if last_buyer_price is None:
        return True
    return last_buyer_price < bounds.floor_paise


def buyer_initial_offer(bounds: NegotiationBounds, budget_paise: int) -> int:
    """Deterministic buyer opening offer: min(budget, floor + 10% of span).

    The buyer opens near the floor (optimistic) but never above budget.
    The LLM may override this with a rationale, but the numeric anchor is
    deterministic so the audit trail is reproducible.
    """
    span = bounds.ceiling_paise - bounds.floor_paise
    anchor = bounds.floor_paise + int(span * 0.10)
    return min(anchor, budget_paise)


def buyer_next_offer(prev_offer_price: int, merchant_offer_price: int,
                     budget_paise: int, bounds: NegotiationBounds,
                     concede_rate: float = 0.30) -> int:
    """Deterministic buyer concession: raise toward merchant by concede_rate.

    step = (merchant_offer - prev_buyer_offer) * concede_rate
    new = prev_buyer_offer + step
    clamp to [floor, min(ceiling, budget)].
    """
    gap = merchant_offer_price - prev_offer_price
    step = int(gap * concede_rate)
    new_price = prev_offer_price + step
    hard_cap = min(bounds.ceiling_paise, budget_paise)
    return max(bounds.floor_paise, min(hard_cap, new_price))
