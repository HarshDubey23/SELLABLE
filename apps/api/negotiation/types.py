"""Negotiation contracts. Pure stdlib - no web framework, no network, no LLM,
no I/O.

These types live in negotiation/ (NOT gateway/) because the negotiation loop
orchestrates LLM calls. The *bounds* enforced here are deterministic, but the
orchestration layer is allowed to import the LLM. The gateway remains pure.

Invariant N-1: negotiation/types.py must not import any web framework, HTTP
client, LLM SDK, or I/O module. Enforced by tests/test_negotiation_purity.py.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from enum import StrEnum


class NegotiationStatus(StrEnum):
    OPEN = "open"                 # rounds in progress
    ACCEPTED = "accepted"         # agreed price reached
    WALKED_AWAY = "walked_away"   # gap too wide after max_turns
    EXPIRED = "expired"           # TTL elapsed
    ABORTED = "aborted"           # mission aborted (R8)


class NegotiationActor(StrEnum):
    BUYER = "buyer"
    MERCHANT = "merchant"


@dataclass(frozen=True)
class Offer:
    """A single priced offer in the negotiation.

    price_paise is ALREADY clamped to [floor, ceiling] by bounds.clamp_offer
    before this object is constructed. The raw LLM-proposed price is kept in
    raw_price_paise for the audit trail (so reviewers can see the LLM tried
    to go out of bounds and was clamped).
    """
    actor: NegotiationActor
    price_paise: int             # clamped, server-authoritative
    raw_price_paise: int         # what the LLM actually proposed (pre-clamp)
    qty: int
    rationale: str               # LLM-generated natural-language reason
    turn: int                    # 1-indexed round number


@dataclass(frozen=True)
class NegotiationBounds:
    """Deterministic bounds for one SKU negotiation. Derived from CATALOG."""
    sku: str
    floor_paise: int             # merchant walk-away
    ceiling_paise: int           # MSRP
    qty: int
    max_turns: int = 5
    walk_away_gap_paise: int = 0  # if final gap > this, walk away
    ttl_seconds: int = 600        # 10 min negotiation window


@dataclass(frozen=True)
class Turn:
    """One round = buyer offer + merchant counter-offer (or terminal)."""
    turn: int
    buyer_offer: Offer | None
    merchant_offer: Offer | None
    gap_paise: int | None         # |merchant - buyer| after this turn
    status: NegotiationStatus


@dataclass
class NegotiationState:
    """Mutable negotiation state. Persisted to SQLite by negotiation/persist."""
    negotiation_id: str
    mission_id: str
    sku: str
    bounds: NegotiationBounds
    buyer_budget_paise: int       # hard ceiling from mission.budget_paise
    turns: list[Turn] = field(default_factory=list)
    status: NegotiationStatus = NegotiationStatus.OPEN
    final_price_paise: int | None = None
    final_offer: Offer | None = None
    created_at: int = 0
    updated_at: int = 0
    parent_action_id: str | None = None  # links to the audit row that started it


@dataclass(frozen=True)
class NegotiationResult:
    """Returned by engine.run(). The caller decides what to do with it."""
    negotiation_id: str
    status: NegotiationStatus
    turns: tuple[Turn, ...]
    final_price_paise: int | None
    final_offer: Offer | None
    audit_action_ids: tuple[str, ...]  # aud_<seq> for every chained step
    reason: str
