"""The negotiation: a durable state machine over three competing merchants.

Modelled on the execution machine that already sits in front of Razorpay,
for the same reason it exists: a process that dies mid-round must come
back to a state that is either terminal or safely resumable, never to a
phantom one.

    OPEN -> AWAITING_OFFERS -> ROUND_COMPLETE -> COUNTER_ISSUED -> ...
                                    |
                                    +-> ACCEPTED | EXPIRED | FAILED

Three properties are load-bearing:

  offer_id is a PRIMARY KEY.  It is derived deterministically from
  (negotiation, merchant, round), so replaying a round produces the same
  id and the insert is refused. A merchant cannot bid twice in a round,
  and a replayed request cannot manufacture a second offer.

  Accept is a conditional UPDATE.  Exactly the pattern the single-use
  authorization already uses: the winning row is claimed with `WHERE
  state = 'ROUND_COMPLETE'`, so twenty concurrent accepts produce one
  winner and nineteen refusals rather than twenty bindings.

  The transcript is canonical and hashed.  Ordered by (round, merchant),
  serialised with sorted keys, SHA-256'd. The hash goes into the approval
  binding, so altering the negotiation after the fact invalidates the
  authorization to pay for it.
"""
from __future__ import annotations

import asyncio
import hashlib
import json
import time
import uuid
from typing import Any

from ..audit import chain as audit_chain
from ..store import db as store
from . import merchants as merchants_mod
from . import policy as policy_mod
from .agents import buyer as buyer_agent
from .agents import llm as llm_mod
from .agents import merchant as merchant_agent
from .intents import BuyerAsk, BuyerCounter, OfferIntent

OPEN = "OPEN"
AWAITING_OFFERS = "AWAITING_OFFERS"
ROUND_COMPLETE = "ROUND_COMPLETE"
COUNTER_ISSUED = "COUNTER_ISSUED"
ACCEPTED = "ACCEPTED"
EXPIRED = "EXPIRED"
FAILED = "FAILED"

ALL_STATES = (OPEN, AWAITING_OFFERS, ROUND_COMPLETE, COUNTER_ISSUED,
              ACCEPTED, EXPIRED, FAILED)
TERMINAL_STATES = frozenset({ACCEPTED, EXPIRED, FAILED})

VALID_TRANSITIONS: dict[str, frozenset[str]] = {
    OPEN: frozenset({AWAITING_OFFERS, FAILED, EXPIRED}),
    AWAITING_OFFERS: frozenset({ROUND_COMPLETE, FAILED, EXPIRED}),
    ROUND_COMPLETE: frozenset({COUNTER_ISSUED, ACCEPTED, EXPIRED, FAILED}),
    COUNTER_ISSUED: frozenset({AWAITING_OFFERS, EXPIRED, FAILED}),
    ACCEPTED: frozenset(),
    EXPIRED: frozenset(),
    FAILED: frozenset(),
}

MAX_ROUNDS = 3
ROUND_TTL_SECONDS = 900          # an unfinished negotiation expires
ROUND_DEADLINE_SECONDS = llm_mod.ROUND_DEADLINE_SECONDS


class IllegalTransition(RuntimeError):
    """The machine refused a move it does not allow."""


# ------------------------------------------------------------- schema

def ensure_schema() -> None:
    store.execute(
        "CREATE TABLE IF NOT EXISTS market_negotiations ("
        " negotiation_id TEXT PRIMARY KEY,"
        " state TEXT NOT NULL,"
        " mission_text TEXT NOT NULL,"
        " mission_id TEXT NOT NULL,"
        " budget_paise INTEGER NOT NULL,"
        " basket_json TEXT NOT NULL,"
        " weights_json TEXT NOT NULL,"
        " planner_json TEXT NOT NULL,"
        " current_round INTEGER NOT NULL DEFAULT 0,"
        " winner_merchant_id TEXT,"
        " winner_offer_id TEXT,"
        " transcript_hash TEXT,"
        " parent_negotiation_id TEXT,"
        " override_of TEXT,"
        " settlement_approve_seq INTEGER,"
        " settlement_quote_id TEXT,"
        " settlement_proposal_hash TEXT,"
        " settled_at INTEGER,"
        " created_at INTEGER NOT NULL,"
        " updated_at INTEGER NOT NULL,"
        " expires_at INTEGER NOT NULL,"
        " last_error TEXT)")
    store.execute(
        "CREATE TABLE IF NOT EXISTS market_offers ("
        " offer_id TEXT PRIMARY KEY,"          # replay refused by this
        " negotiation_id TEXT NOT NULL,"
        " merchant_id TEXT NOT NULL,"
        " round INTEGER NOT NULL,"
        " intent_json TEXT NOT NULL,"
        " verdict_json TEXT NOT NULL,"
        " accepted INTEGER NOT NULL,"
        " reason TEXT,"
        " total_paise INTEGER,"
        " provenance_json TEXT NOT NULL,"
        " created_at INTEGER NOT NULL)")
    store.execute(
        "CREATE TABLE IF NOT EXISTS market_counters ("
        " counter_id TEXT PRIMARY KEY,"
        " negotiation_id TEXT NOT NULL,"
        " merchant_id TEXT NOT NULL,"
        " round INTEGER NOT NULL,"
        " ask TEXT NOT NULL,"
        " note TEXT,"
        " created_at INTEGER NOT NULL)")


def _migrate_settlement_columns() -> None:
    """Add the settlement claim columns to an existing table (idempotent)."""
    existing = {row["name"] for row in
                store.query("SELECT name FROM pragma_table_info("
                            "'market_negotiations')")}
    for col, coltype in (("settlement_approve_seq", "INTEGER"),
                         ("settlement_quote_id", "TEXT"),
                         ("settlement_proposal_hash", "TEXT"),
                         ("settled_at", "INTEGER")):
        if col not in existing:
            store.execute(
                f"ALTER TABLE market_negotiations ADD COLUMN {col} {coltype}")



ensure_schema()
_migrate_settlement_columns()


def claim_settlement(negotiation_id: str, *, approve_seq: int, quote_id: str,
                     proposal_hash: str, now_ts: int | None = None) -> bool:
    """Claim the sole right to settle this negotiation.

    The same conditional UPDATE the rest of the system uses for anything
    that must happen once. Without it, settling twice would evaluate the
    gateway twice, mint two approve sequences, two bindings and two
    execution rows -- and the execution machine, which dedupes on the
    authorization it is handed, would correctly conclude these were two
    different authorized purchases and open two payments.

    Returns True if this caller claimed it, False if someone already had.
    """
    now_ts = now_ts if now_ts is not None else int(time.time())
    affected = store.execute_rowcount(
        "UPDATE market_negotiations SET settlement_approve_seq = ?, "
        "settlement_quote_id = ?, settlement_proposal_hash = ?, "
        "settled_at = ?, updated_at = ? "
        "WHERE negotiation_id = ? AND settlement_approve_seq IS NULL",
        (approve_seq, quote_id, proposal_hash, now_ts, now_ts,
         negotiation_id))
    return affected == 1


# -------------------------------------------------------- transitions

def get(negotiation_id: str) -> dict[str, Any] | None:
    return store.query_one(
        "SELECT * FROM market_negotiations WHERE negotiation_id = ?",
        (negotiation_id,))


def transition(negotiation_id: str, target: str, *,
               now_ts: int | None = None, **fields: Any) -> dict[str, Any]:
    """Move one negotiation, enforcing the table.

    The UPDATE carries the expected current state, so two writers racing
    the same transition cannot both apply it.
    """
    now_ts = now_ts if now_ts is not None else int(time.time())
    row = get(negotiation_id)
    if row is None:
        raise IllegalTransition(f"unknown negotiation {negotiation_id}")

    current = row["state"]
    if target not in VALID_TRANSITIONS.get(current, frozenset()):
        raise IllegalTransition(
            f"{negotiation_id}: {current} -> {target} is not allowed "
            f"(from {current}: {sorted(VALID_TRANSITIONS.get(current, ()))})")

    sets = ["state = ?", "updated_at = ?"]
    params: list[Any] = [target, now_ts]
    for key, value in fields.items():
        sets.append(f"{key} = ?")
        params.append(value)
    params += [negotiation_id, current]

    affected = store.execute_rowcount(
        f"UPDATE market_negotiations SET {', '.join(sets)} "
        f"WHERE negotiation_id = ? AND state = ?", tuple(params))
    if affected != 1:
        raise IllegalTransition(
            f"{negotiation_id}: state changed concurrently (expected {current})")

    updated = get(negotiation_id)
    assert updated is not None
    return updated


# --------------------------------------------------------- transcript

def offers_for(negotiation_id: str) -> list[dict[str, Any]]:
    return store.query(
        "SELECT * FROM market_offers WHERE negotiation_id = ? "
        "ORDER BY round, merchant_id", (negotiation_id,))


def counters_for(negotiation_id: str) -> list[dict[str, Any]]:
    return store.query(
        "SELECT * FROM market_counters WHERE negotiation_id = ? "
        "ORDER BY round, merchant_id", (negotiation_id,))


def canonical_transcript(negotiation_id: str) -> list[dict[str, Any]]:
    """Every event, in an order that does not depend on who answered first.

    Merchants are called concurrently, so arrival order differs every run.
    Sorting by (round, merchant) makes the transcript — and therefore its
    hash — a property of what happened rather than of the race.
    """
    row = get(negotiation_id)
    if row is None:
        return []

    events: list[dict[str, Any]] = [{
        "kind": "mission",
        "round": 0,
        "mission_text": row["mission_text"],
        "budget_paise": row["budget_paise"],
        "basket": json.loads(row["basket_json"]),
        "weights": json.loads(row["weights_json"]),
    }]

    for c in counters_for(negotiation_id):
        events.append({
            "kind": "counter", "round": c["round"],
            "merchant_id": c["merchant_id"], "ask": c["ask"],
            "note": c["note"] or "",
        })

    for o in offers_for(negotiation_id):
        intent = json.loads(o["intent_json"])
        events.append({
            "kind": "offer", "round": o["round"],
            "merchant_id": o["merchant_id"], "offer_id": o["offer_id"],
            "intent": intent,
            "accepted": bool(o["accepted"]),
            "reason": o["reason"],
            "total_paise": o["total_paise"],
            "agent_source": json.loads(o["provenance_json"]).get("source"),
        })

    events.sort(key=lambda e: (e["round"], e["kind"],
                               e.get("merchant_id", ""), e.get("offer_id", "")))
    return events


def transcript_hash(negotiation_id: str) -> str:
    blob = json.dumps(canonical_transcript(negotiation_id),
                      sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(blob.encode()).hexdigest()


# ------------------------------------------------------------- rounds

def _catalog_basket(skus: list[str]) -> list[dict[str, Any]]:
    from ..products import CATALOG
    return [{"sku": s, **CATALOG[s]} for s in skus if s in CATALOG]


async def open_negotiation(*, mission_text: str, allow_llm: bool = True,
                           weights_override: dict[str, int] | None = None,
                           override_of: str | None = None) -> dict[str, Any]:
    """Read the mission, sign it, and open the market."""
    from ..products import CATALOG

    merchants_mod.seed()
    now = int(time.time())
    negotiation_id = "neg_" + uuid.uuid4().hex[:16]

    plan, planner_prov = await buyer_agent.plan_mission(
        mission_text=mission_text, catalog=CATALOG, allow_llm=allow_llm)
    if plan is None:
        raise ValueError(
            "no catalog item matches this mission - SELLABLE can only sell "
            "what it stocks, and nothing here does")

    weights = weights_override or plan.normalised_weights()
    basket = _catalog_basket(plan.skus)
    if not basket:
        raise ValueError(
            "no catalog item matches this mission - every proposed SKU was "
            "rejected against the catalog")

    # The ceiling becomes a signed mission the existing gateway enforces.
    from .. import issuer
    categories = tuple(sorted({b["category"] for b in basket}))
    mission = issuer.issue_mission(
        mission_id=f"msn_mkt_{now}_{uuid.uuid4().hex[:8]}",
        intent=mission_text[:200],
        allowed_categories=categories,
        budget_paise=plan.budget_paise,
        upsell_cap=1.0, now_ts=now)

    store.execute(
        "INSERT INTO market_negotiations "
        "(negotiation_id, state, mission_text, mission_id, budget_paise, "
        " basket_json, weights_json, planner_json, current_round, "
        " created_at, updated_at, expires_at, override_of) "
        "VALUES (?, ?, ?, ?, ?, ?, ?, ?, 0, ?, ?, ?, ?)",
        (negotiation_id, OPEN, mission_text, mission["mission_id"],
         plan.budget_paise, json.dumps([b["sku"] for b in basket]),
         json.dumps(weights), json.dumps(planner_prov), now, now,
         now + ROUND_TTL_SECONDS, override_of))

    audit_chain.append("market", "negotiation_opened", {
        "negotiation_id": negotiation_id, "mission_id": mission["mission_id"],
        "basket": [b["sku"] for b in basket],
        "budget_paise": plan.budget_paise,
        "planner": planner_prov.get("source"),
        "override_of": override_of},
        review_state="market_open")

    opened = get(negotiation_id)
    assert opened is not None
    return opened


async def run_round(negotiation_id: str, *, allow_llm: bool = True,
                    counter: BuyerCounter | None = None) -> dict[str, Any]:
    """Ask every merchant, score what survives policy, record everything."""
    row = get(negotiation_id)
    if row is None:
        raise IllegalTransition(f"unknown negotiation {negotiation_id}")
    if row["state"] in TERMINAL_STATES:
        raise IllegalTransition(
            f"{negotiation_id} is {row['state']}; no further rounds")
    if int(time.time()) > row["expires_at"]:
        transition(negotiation_id, EXPIRED,
                   last_error="negotiation window elapsed")
        raise IllegalTransition(f"{negotiation_id} expired")

    round_no = row["current_round"] + 1
    if round_no > MAX_ROUNDS:
        raise IllegalTransition(
            f"{negotiation_id}: max {MAX_ROUNDS} rounds already used")

    transition(negotiation_id, AWAITING_OFFERS, current_round=round_no)

    basket = _catalog_basket(json.loads(row["basket_json"]))
    manifests = merchants_mod.all_manifests()

    # All three concurrently, under one hard deadline. A merchant that
    # does not answer in time is simply not in this round; the round is
    # never held open by one slow provider.
    async def _one(m: merchants_mod.CapabilityManifest) -> tuple[OfferIntent, dict[str, Any]]:
        # Only the merchant the counter was addressed to hears about it.
        mine = counter if (counter and counter.merchant_id == m.merchant_id) else None
        return await merchant_agent.make_offer(
            negotiation_id=negotiation_id, manifest=m, basket=basket,
            mission_text=row["mission_text"], round_no=round_no,
            counter=mine, allow_llm=allow_llm)

    try:
        results = await asyncio.wait_for(
            asyncio.gather(*[_one(m) for m in manifests],
                           return_exceptions=True),
            timeout=ROUND_DEADLINE_SECONDS)
    # asyncio.TimeoutError rather than the builtin: identical from 3.11
    # on, but on 3.10 wait_for raises concurrent.futures.TimeoutError,
    # which is not a builtin TimeoutError. Catching the wrong one there
    # would let a slow provider take down the whole round.
    except asyncio.TimeoutError:
        results = [TimeoutError("round deadline elapsed")] * len(manifests)

    from ..products import CATALOG
    now = int(time.time())
    recorded = 0

    for manifest, result in zip(manifests, results, strict=True):
        if isinstance(result, BaseException):
            audit_chain.append("market", "merchant_non_responsive", {
                "negotiation_id": negotiation_id, "round": round_no,
                "merchant_id": manifest.merchant_id,
                "error": str(result)[:200]},
                error_code="MERCHANT_NON_RESPONSIVE",
                review_state="market_round")
            continue

        intent, provenance = result
        verdict = policy_mod.evaluate(intent=intent, manifest=manifest,
                                      catalog=CATALOG)

        try:
            store.execute(
                "INSERT INTO market_offers "
                "(offer_id, negotiation_id, merchant_id, round, intent_json, "
                " verdict_json, accepted, reason, total_paise, "
                " provenance_json, created_at) "
                "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
                (intent.offer_id, negotiation_id, manifest.merchant_id,
                 round_no, json.dumps(intent.canonical()),
                 json.dumps(verdict.public()), 1 if verdict.accepted else 0,
                 verdict.reason, verdict.total_paise,
                 json.dumps(provenance), now))
            recorded += 1
        except Exception:
            # PRIMARY KEY on offer_id. A replayed round lands here and is
            # refused rather than producing a second offer for the round.
            audit_chain.append("market", "offer_replay_refused", {
                "negotiation_id": negotiation_id, "round": round_no,
                "merchant_id": manifest.merchant_id,
                "offer_id": intent.offer_id},
                error_code="OFFER_REPLAY_REFUSED",
                review_state="market_round")
            continue

        audit_chain.append(
            "market",
            "offer_accepted" if verdict.accepted else "offer_refused",
            {"negotiation_id": negotiation_id, "round": round_no,
             "merchant_id": manifest.merchant_id,
             "offer_id": intent.offer_id,
             "decision": verdict.decision,
             "reason": verdict.reason,
             "total_paise": verdict.total_paise,
             "agent_source": provenance.get("source")},
            error_code=verdict.reason,
            review_state="market_policy")

    if recorded == 0:
        return transition(
            negotiation_id, FAILED,
            last_error="no merchant produced a recordable offer")

    return transition(negotiation_id, ROUND_COMPLETE)


def issue_counter(negotiation_id: str, *, merchant_id: str,
                  ask: BuyerAsk, note: str = "") -> dict[str, Any]:
    """One targeted request to one merchant. Nothing about rivals travels."""
    row = get(negotiation_id)
    if row is None:
        raise IllegalTransition(f"unknown negotiation {negotiation_id}")

    counter = BuyerCounter(merchant_id=merchant_id, ask=ask,
                           round=row["current_round"] + 1, note=note)
    now = int(time.time())
    store.execute(
        "INSERT INTO market_counters "
        "(counter_id, negotiation_id, merchant_id, round, ask, note, created_at) "
        "VALUES (?, ?, ?, ?, ?, ?, ?)",
        ("ctr_" + uuid.uuid4().hex[:16], negotiation_id, merchant_id,
         counter.round, ask, note, now))

    audit_chain.append("market", "counter_issued", {
        "negotiation_id": negotiation_id, "merchant_id": merchant_id,
        "ask": ask, "round": counter.round,
        "disclosure": "the counter names a dimension only; no competitor "
                      "terms are included"},
        review_state="market_counter")

    return transition(negotiation_id, COUNTER_ISSUED)


# --------------------------------------------------------- the winner

def rank(negotiation_id: str) -> dict[str, Any]:
    """Score the best offer each merchant has standing. Pure downstream."""
    from .explain import explain_winner
    from .score import OfferFacts, score_offers

    row = get(negotiation_id)
    if row is None:
        raise IllegalTransition(f"unknown negotiation {negotiation_id}")

    best: dict[str, dict[str, Any]] = {}
    for o in offers_for(negotiation_id):
        if not o["accepted"]:
            continue
        # A later round supersedes an earlier one for the same merchant.
        prev = best.get(o["merchant_id"])
        if prev is None or o["round"] >= prev["round"]:
            best[o["merchant_id"]] = o

    facts: dict[str, OfferFacts] = {}
    for merchant_id, o in best.items():
        intent = json.loads(o["intent_json"])
        facts[merchant_id] = OfferFacts(
            merchant_id=merchant_id, offer_id=o["offer_id"],
            total_paise=o["total_paise"],
            delivery_days=intent["delivery_days"],
            warranty_years=intent["warranty_years"],
            line_count=len(intent["basket_sku_set"]) + len(intent["addon_skus"]))

    weights = json.loads(row["weights_json"])
    ranked = score_offers(list(facts.values()), weights)

    return {
        "negotiation_id": negotiation_id,
        "weights": weights,
        "ranked": [s.public() for s in ranked],
        "winner": ranked[0].public() if ranked else None,
        "explanation": (explain_winner(winner=ranked[0], ranked=ranked,
                                       facts=facts, weights=weights)
                        if ranked else None),
        "refused_count": sum(1 for o in offers_for(negotiation_id)
                             if not o["accepted"]),
    }


def claim_winner(negotiation_id: str) -> dict[str, Any]:
    """Accept, exactly once, under any amount of concurrency.

    The same conditional-UPDATE pattern the single-use authorization uses:
    the transition to ACCEPTED carries `WHERE state = 'ROUND_COMPLETE'`,
    so of twenty racing accepts exactly one UPDATE affects a row.
    """
    ranking = rank(negotiation_id)
    if not ranking["winner"]:
        raise IllegalTransition(
            f"{negotiation_id}: no offer survived policy, nothing to accept")

    winner_id = ranking["winner"]["merchant_id"]
    offer_id = ranking["winner"]["offer_id"]
    thash = transcript_hash(negotiation_id)

    updated = transition(negotiation_id, ACCEPTED,
                         winner_merchant_id=winner_id,
                         winner_offer_id=offer_id,
                         transcript_hash=thash)

    audit_chain.append("market", "negotiation_accepted", {
        "negotiation_id": negotiation_id, "merchant_id": winner_id,
        "offer_id": offer_id, "transcript_hash": thash,
        "score": ranking["winner"]["score"]},
        review_state="market_accepted")

    return {"negotiation": updated, "ranking": ranking,
            "transcript_hash": thash}


# ------------------------------------------------------------ recovery

def recover_stranded(now_ts: int | None = None) -> list[str]:
    """Boot sweep, in the shape the execution machine already uses.

    A negotiation still mid-round when the process died cannot be resumed
    safely — the merchants were mid-answer and we do not know which
    replied. It goes to FAILED, which is honest, rather than being
    resumed into a round with a partial field. One left at ROUND_COMPLETE
    is genuinely resumable and is left alone unless its window elapsed.
    """
    now_ts = now_ts if now_ts is not None else int(time.time())
    moved: list[str] = []

    for row in store.query(
            "SELECT negotiation_id, state, expires_at FROM market_negotiations "
            "WHERE state IN (?, ?, ?, ?)",
            (OPEN, AWAITING_OFFERS, ROUND_COMPLETE, COUNTER_ISSUED)):
        nid, state = row["negotiation_id"], row["state"]
        try:
            if state == AWAITING_OFFERS:
                transition(nid, FAILED, now_ts=now_ts,
                           last_error="process restarted while a round was "
                                      "in flight; the field is unknown")
                moved.append(nid)
            elif now_ts > row["expires_at"]:
                transition(nid, EXPIRED, now_ts=now_ts,
                           last_error="negotiation window elapsed")
                moved.append(nid)
        except IllegalTransition:       # pragma: no cover - raced
            continue
    return moved


def summary() -> dict[str, int]:
    counts = {s: 0 for s in ALL_STATES}
    for r in store.query(
            "SELECT state, COUNT(*) AS c FROM market_negotiations GROUP BY state"):
        counts[r["state"]] = r["c"]
    return counts
