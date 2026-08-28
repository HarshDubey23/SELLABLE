"""Deterministic negotiation bounds. Pure stdlib.

N-1 invariant: NO imports of web frameworks, HTTP clients, LLM SDKs, database
drivers, or any I/O/network module. Enforced by tests/test_negotiation_purity.py.

These functions are the deterministic "policy" layer of negotiation. The LLM
can propose any number it likes; clamp_offer() forces it into [floor, ceiling]
before it becomes an Offer. check_monotonic() rejects backwards concessions.
check_walk_away() decides when to terminate. None of this touches the LLM.
"""
from __future__ import annotations

from .types import NegotiationBounds, NegotiationStatus, Offer


def clamp_offer(raw_price_paise: int, bounds: NegotiationBounds,
                actor, qty: int, rationale: str, turn: int) -> Offer:
    """Clamp a raw LLM-proposed price into [floor, ceiling].

    The clamped price becomes the authoritative price_paise. The raw price is
    preserved on the Offer for audit (reviewers can see the LLM misbehaved).
    """
    floor = bounds.floor_paise * qty
    ceiling = bounds.ceiling_paise * qty
    clamped = max(floor, min(ceiling, raw_price_paise))
    return Offer(
        actor=actor,
        price_paise=clamped,
        raw_price_paise=raw_price_paise,
        qty=qty,
        rationale=rationale,
        turn=turn,
    )


def check_monotonic(prev_offer: Offer | None, new_offer: Offer) -> bool:
    """Merchant offers must be <= previous merchant offer (concede toward floor).
    Buyer offers must be >= previous buyer offer (raise toward ceiling).

    Returns True if the monotonic constraint is satisfied.
    A None previous offer (first turn) always passes.
    """
    if prev_offer is None:
        return True
    if new_offer.actor != prev_offer.actor:
        return True  # different actors, not comparable
    if new_offer.actor.value == "merchant":
        return new_offer.price_paise <= prev_offer.price_paise
    # buyer
    return new_offer.price_paise >= prev_offer.price_paise


def check_walk_away(gap_paise: int, bounds: NegotiationBounds,
                    turn: int) -> bool:
    """Return True if the negotiation should walk away.

    Walk away if:
      - turn >= max_turns AND gap > walk_away_gap_paise
    """
    if turn >= bounds.max_turns and gap_paise > bounds.walk_away_gap_paise:
        return True
    return False


def check_accept(buyer_price: int, merchant_price: int,
                 bounds: NegotiationBounds) -> bool:
    """Return True if buyer and merchant have converged.

    Acceptance conditions (any one):
      - buyer_price >= merchant_price (buyer meets/exceeds merchant ask)
      - gap <= walk_away_gap_paise (within tolerance)
    """
    if buyer_price >= merchant_price:
        return True
    gap = merchant_price - buyer_price
    return gap <= bounds.walk_away_gap_paise


def effective_price(merchant_offer: Offer, buyer_offer: Offer) -> int:
    """The agreed price on acceptance = the merchant's last offer (seller sets)."""
    return merchant_offer.price_paise


def check_budget(price_paise: int, budget_paise: int) -> bool:
    """Hard budget gate. The agreed price must not exceed the mission budget."""
    return price_paise <= budget_paise


def check_ttl(created_at: int, now_ts: int, bounds: NegotiationBounds) -> bool:
    """Return True if the negotiation is still within its TTL."""
    return (now_ts - created_at) <= bounds.ttl_seconds


def status_after_turn(turn: int, bounds: NegotiationBounds,
                      buyer_offer: Offer | None,
                      merchant_offer: Offer | None) -> NegotiationStatus:
    """Decide the negotiation status after a turn completes."""
    if buyer_offer is None or merchant_offer is None:
        return NegotiationStatus.OPEN
    if check_accept(buyer_offer.price_paise, merchant_offer.price_paise, bounds):
        return NegotiationStatus.ACCEPTED
    if check_walk_away(
        merchant_offer.price_paise - buyer_offer.price_paise, bounds, turn
    ):
        return NegotiationStatus.WALKED_AWAY
    return NegotiationStatus.OPEN
