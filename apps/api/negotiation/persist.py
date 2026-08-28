"""SQLite persistence for negotiation state. Survives restart.

Tables added in Day 5:
  negotiations   : one row per negotiation (status, bounds, final price)
  negotiation_turns : one row per turn (offer JSON, gap, status)

This module imports sqlite3 (I/O) - it is NOT in the gateway purity boundary.
N-1 applies only to negotiation/types.py and negotiation/bounds.py.
"""
from __future__ import annotations

import json
import time

from ..store import db as store
from .types import NegotiationBounds, NegotiationState, NegotiationStatus, Offer, Turn


def _ensure_schema() -> None:
    """Idempotent table creation for Day-5 negotiation tables."""
    store.execute("""
        CREATE TABLE IF NOT EXISTS negotiations (
            negotiation_id TEXT PRIMARY KEY,
            mission_id TEXT NOT NULL,
            sku TEXT NOT NULL,
            floor_paise INTEGER NOT NULL,
            ceiling_paise INTEGER NOT NULL,
            qty INTEGER NOT NULL,
            max_turns INTEGER NOT NULL,
            walk_away_gap_paise INTEGER NOT NULL,
            ttl_seconds INTEGER NOT NULL,
            buyer_budget_paise INTEGER NOT NULL,
            status TEXT NOT NULL,
            final_price_paise INTEGER,
            final_offer TEXT,
            created_at INTEGER NOT NULL,
            updated_at INTEGER NOT NULL,
            parent_action_id TEXT
        )
    """)
    store.execute("""
        CREATE TABLE IF NOT EXISTS negotiation_turns (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            negotiation_id TEXT NOT NULL,
            turn INTEGER NOT NULL,
            buyer_offer TEXT,
            merchant_offer TEXT,
            gap_paise INTEGER,
            status TEXT NOT NULL,
            created_at INTEGER NOT NULL,
            FOREIGN KEY (negotiation_id) REFERENCES negotiations(negotiation_id)
        )
    """)
    store.execute(
        "CREATE INDEX IF NOT EXISTS idx_neg_mission ON negotiations(mission_id)"
    )


def save(state: NegotiationState) -> None:
    """Upsert a negotiation (and its turns) to SQLite."""
    _ensure_schema()
    now = int(time.time())
    store.execute(
        "INSERT OR REPLACE INTO negotiations "
        "(negotiation_id, mission_id, sku, floor_paise, ceiling_paise, qty, "
        " max_turns, walk_away_gap_paise, ttl_seconds, buyer_budget_paise, "
        " status, final_price_paise, final_offer, created_at, updated_at, "
        " parent_action_id) "
        "VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)",
        (state.negotiation_id, state.mission_id, state.bounds.sku,
         state.bounds.floor_paise, state.bounds.ceiling_paise,
         state.bounds.qty, state.bounds.max_turns,
         state.bounds.walk_away_gap_paise, state.bounds.ttl_seconds,
         state.buyer_budget_paise, state.status.value,
         state.final_price_paise,
         json.dumps(_offer_to_dict(state.final_offer)) if state.final_offer else None,
         state.created_at or now, now, state.parent_action_id)
    )
    # Rewrite turns (cheap; max 5-10 rows)
    store.execute(
        "DELETE FROM negotiation_turns WHERE negotiation_id = ?",
        (state.negotiation_id,)
    )
    for t in state.turns:
        store.execute(
            "INSERT INTO negotiation_turns "
            "(negotiation_id, turn, buyer_offer, merchant_offer, gap_paise, "
            " status, created_at) VALUES (?,?,?,?,?,?,?)",
            (state.negotiation_id, t.turn,
             json.dumps(_offer_to_dict(t.buyer_offer)) if t.buyer_offer else None,
             json.dumps(_offer_to_dict(t.merchant_offer)) if t.merchant_offer else None,
             t.gap_paise, t.status.value, now)
        )


def load(negotiation_id: str) -> NegotiationState | None:
    """Load a negotiation by id. Returns None if not found."""
    _ensure_schema()
    row = store.query_one(
        "SELECT * FROM negotiations WHERE negotiation_id = ?",
        (negotiation_id,)
    )
    if not row:
        return None
    turns_rows = store.query(
        "SELECT * FROM negotiation_turns WHERE negotiation_id = ? "
        "ORDER BY turn",
        (negotiation_id,)
    )
    turns = [_row_to_turn(r) for r in turns_rows]
    bounds = NegotiationBounds(
        sku=row["sku"], floor_paise=row["floor_paise"],
        ceiling_paise=row["ceiling_paise"], qty=row["qty"],
        max_turns=row["max_turns"],
        walk_away_gap_paise=row["walk_away_gap_paise"],
        ttl_seconds=row["ttl_seconds"],
    )
    final_offer = None
    if row["final_offer"]:
        final_offer = _dict_to_offer(json.loads(row["final_offer"]))
    return NegotiationState(
        negotiation_id=row["negotiation_id"],
        mission_id=row["mission_id"],
        sku=row["sku"],
        bounds=bounds,
        buyer_budget_paise=row["buyer_budget_paise"],
        turns=turns,
        status=NegotiationStatus(row["status"]),
        final_price_paise=row["final_price_paise"],
        final_offer=final_offer,
        created_at=row["created_at"],
        updated_at=row["updated_at"],
        parent_action_id=row["parent_action_id"],
    )


def list_for_mission(mission_id: str) -> list[NegotiationState]:
    _ensure_schema()
    rows = store.query(
        "SELECT negotiation_id FROM negotiations WHERE mission_id = ? "
        "ORDER BY created_at",
        (mission_id,)
    )
    result = []
    for r in rows:
        st = load(r["negotiation_id"])
        if st:
            result.append(st)
    return result


# ---- serialization helpers ----

def _offer_to_dict(o: Offer | None) -> dict | None:
    if o is None:
        return None
    return {
        "actor": o.actor.value, "price_paise": o.price_paise,
        "raw_price_paise": o.raw_price_paise, "qty": o.qty,
        "rationale": o.rationale, "turn": o.turn,
    }


def _dict_to_offer(d: dict) -> Offer:
    from .types import NegotiationActor
    return Offer(
        actor=NegotiationActor(d["actor"]),
        price_paise=d["price_paise"],
        raw_price_paise=d["raw_price_paise"],
        qty=d["qty"], rationale=d["rationale"], turn=d["turn"],
    )


def _row_to_turn(r: dict) -> Turn:
    buyer = _dict_to_offer(json.loads(r["buyer_offer"])) if r["buyer_offer"] else None
    merchant = _dict_to_offer(json.loads(r["merchant_offer"])) if r["merchant_offer"] else None
    return Turn(
        turn=r["turn"], buyer_offer=buyer, merchant_offer=merchant,
        gap_paise=r["gap_paise"], status=NegotiationStatus(r["status"]),
    )
