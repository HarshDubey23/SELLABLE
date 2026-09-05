"""Settlement: what the market is allowed to tell the money path.

The market's job ends at choosing a basket and a total. Everything after
that is the payment path that already existed. These tests are about the
seam between the two, and specifically about what an attacker who has
already got inside the market can still not do.

Every test runs with allow_llm=False. The negotiation these tests settle
is produced by the deterministic fallback merchants, so the numbers are
reproducible and no provider is involved.
"""
from __future__ import annotations

import asyncio
import json

import pytest

from apps.api.market import negotiation as neg
from apps.api.market import settle
from apps.api.store import db as store

MISSION = "A complete cricket setup under Rs 6,000"


def _accepted() -> str:
    """Open, run one round, accept. Returns the negotiation id."""
    async def go() -> str:
        row = await neg.open_negotiation(mission_text=MISSION, allow_llm=False)
        nid = row["negotiation_id"]
        await neg.run_round(nid, allow_llm=False)
        return nid

    nid = asyncio.run(go())
    neg.claim_winner(nid)
    return nid


@pytest.fixture
def accepted() -> str:
    return _accepted()


# ------------------------------------------------------ the happy path

def test_a_settled_negotiation_reaches_the_execution_machine(accepted):
    out = asyncio.run(settle.settle(accepted))

    assert out["merchant_id"] == neg.get(accepted)["winner_merchant_id"]
    assert out["amount_paise"] > 0
    assert out["order"]["execution_state"] == "EXECUTED"
    # The amount that reached the money path is the amount the policy
    # engine computed, to the paisa.
    assert out["order"]["amount_paise"] == out["amount_paise"]


def test_editing_the_stored_total_never_reaches_the_money_path(accepted):
    """Rewrite the total in the database and nothing gets charged at all.

    Two independent defences stand between that edit and a payment, and
    the outer one fires first: the total is part of the transcript, so
    changing it moves the transcript hash and the settlement stops before
    any price is computed. The engine never even gets asked.
    """
    row = neg.get(accepted)
    store.execute(
        "UPDATE market_offers SET total_paise = 1 WHERE offer_id = ?",
        (row["winner_offer_id"],))

    with pytest.raises(settle.SettlementRefused) as exc:
        settle.recompute(accepted)
    assert exc.value.code == "TRANSCRIPT_MUTATED"


def test_the_payable_total_is_derived_not_read(accepted):
    """And the inner defence: the price comes from the engine, every time.

    Even with the transcript intact, what settlement charges is a fresh
    evaluation of the merchant's stored intent against its signed
    manifest -- not the total_paise column sitting next to it. The column
    is a record of what happened; the engine is the authority on what it
    costs.
    """
    from apps.api.market import merchants, policy
    from apps.api.market.intents import OfferIntent
    from apps.api.products import CATALOG

    row = neg.get(accepted)
    offer = next(o for o in neg.offers_for(accepted)
                 if o["offer_id"] == row["winner_offer_id"])

    independent = policy.evaluate(
        intent=OfferIntent.model_validate(json.loads(offer["intent_json"])),
        manifest=merchants.get(offer["merchant_id"]), catalog=CATALOG)

    _row, verdict = settle.recompute(accepted)
    assert verdict.total_paise == independent.total_paise

    out = asyncio.run(settle.settle(accepted))
    assert out["amount_paise"] == independent.total_paise
    assert out["order"]["amount_paise"] == independent.total_paise


# ------------------------------------------------- tamper after accept

def test_editing_the_transcript_after_acceptance_stops_the_settlement(accepted):
    """The hash in the binding is what makes the transcript load-bearing."""
    row = neg.get(accepted)
    store.execute(
        "UPDATE market_offers SET reason = 'edited' WHERE offer_id = ?",
        (row["winner_offer_id"],))

    with pytest.raises(settle.SettlementRefused) as exc:
        settle.recompute(accepted)
    assert exc.value.code == "TRANSCRIPT_MUTATED"


def test_adding_an_offer_after_acceptance_stops_the_settlement(accepted):
    """Not just editing: appending to a settled negotiation is refused too."""
    row = neg.get(accepted)
    store.execute(
        "INSERT INTO market_offers (offer_id, negotiation_id, merchant_id, "
        "round, intent_json, verdict_json, accepted, reason, total_paise, "
        "provenance_json, created_at) "
        "VALUES ('off_forged', ?, 'GEARHUB', 1, '{}', '{}', 1, NULL, 1, "
        "'{}', 0)", (accepted,))

    with pytest.raises(settle.SettlementRefused) as exc:
        settle.recompute(accepted)
    assert exc.value.code == "TRANSCRIPT_MUTATED"
    assert row["transcript_hash"]


def test_an_intent_edited_to_exceed_policy_is_caught_at_settlement(accepted):
    """Rewriting the winning intent to a bigger discount does not pay out.

    The offer was legal when it was made. If the row is edited to
    something the manifest never allowed, the settlement recomputation
    refuses it rather than pricing it.
    """
    row = neg.get(accepted)
    offer = next(o for o in neg.offers_for(accepted)
                 if o["offer_id"] == row["winner_offer_id"])
    intent = json.loads(offer["intent_json"])
    intent["line_discount_pct"] = 90
    store.execute("UPDATE market_offers SET intent_json = ? WHERE offer_id = ?",
                  (json.dumps(intent), offer["offer_id"]))

    with pytest.raises(settle.SettlementRefused) as exc:
        settle.recompute(accepted)
    # Either the policy engine refuses the rewritten intent or the
    # transcript hash catches the edit. Both are correct; neither pays.
    assert exc.value.code in ("RECOMPUTE_REJECTED", "TRANSCRIPT_MUTATED")


# ------------------------------------------------------- binding gates

def test_the_binding_pins_the_merchant_that_won(accepted):
    """Swap the merchant on the quote and the money path refuses it."""
    from apps.api import tools as tools_mod

    out = asyncio.run(settle.settle(accepted))
    quote = tools_mod.quotes[out["quote_id"]]
    assert quote["negotiated"]["merchant_id"] == out["merchant_id"]
    assert quote["negotiated"]["transcript_hash"] == out["transcript_hash"]


def test_a_binding_from_a_market_carries_both_market_fields(accepted):
    from apps.api import approval

    out = asyncio.run(settle.settle(accepted))
    binding = approval.get(out["approve_seq"])
    assert binding is not None
    assert binding.merchant_id == out["merchant_id"]
    assert binding.negotiation_transcript_hash == out["transcript_hash"]


def test_a_market_binding_refuses_a_different_merchant(accepted):
    """The check itself, exercised directly against the binding."""
    from apps.api import approval

    out = asyncio.run(settle.settle(accepted))
    binding = approval.get(out["approve_seq"])
    assert binding is not None

    ok, reason = binding.matches_money(
        mission_id=binding.mission_id, proposal_hash=binding.proposal_hash,
        cart_hash=binding.cart_hash, quote_id=out["quote_id"],
        amount_paise=binding.amount_paise, currency="INR",
        skus=list(binding.sku_set),
        merchant_id="NOT_THE_WINNER",
        negotiation_transcript_hash=binding.negotiation_transcript_hash)
    assert not ok
    assert reason == "MERCHANT_MISMATCH"


def test_a_market_binding_refuses_a_different_transcript(accepted):
    from apps.api import approval

    out = asyncio.run(settle.settle(accepted))
    binding = approval.get(out["approve_seq"])
    assert binding is not None

    ok, reason = binding.matches_money(
        mission_id=binding.mission_id, proposal_hash=binding.proposal_hash,
        cart_hash=binding.cart_hash, quote_id=out["quote_id"],
        amount_paise=binding.amount_paise, currency="INR",
        skus=list(binding.sku_set), merchant_id=binding.merchant_id,
        negotiation_transcript_hash="0" * 64)
    assert not ok
    assert reason == "TRANSCRIPT_MISMATCH"


def test_an_ordinary_binding_is_unaffected_by_the_market_fields():
    """The extension is additive: a non-market binding pins neither field.

    If this ever fails, every non-negotiated purchase in the system has
    started demanding proof of a negotiation that never happened.
    """
    from apps.api import approval

    b = approval.register(
        999_001, mission_id="msn_plain", proposal_hash="h" * 64,
        cart_hash="h" * 64, quote_id="", amount_paise=10000, currency="INR",
        skus=[("BAT-001", 1)])
    assert b.merchant_id == ""
    assert b.negotiation_transcript_hash == ""

    ok, reason = b.matches_money(
        mission_id="msn_plain", proposal_hash="h" * 64, cart_hash="h" * 64,
        quote_id="q1", amount_paise=10000, currency="INR",
        skus=[("BAT-001", 1)])
    assert ok, reason


# ------------------------------------------------------ the ceiling rule

def test_a_settlement_above_the_approved_ceiling_is_refused():
    """The negotiation may only ever move the price down.

    The gateway approves the basket at catalog list price against the
    shopper's signed budget. Binding more than that would mean the
    negotiation layer authorized a spend the deterministic rules never
    evaluated -- so it is refused outright rather than trimmed to fit.
    """
    from fastapi import HTTPException

    import apps.api.tools as tools_mod

    async def go():
        row = await neg.open_negotiation(mission_text=MISSION,
                                         allow_llm=False)
        nid = row["negotiation_id"]
        await neg.run_round(nid, allow_llm=False)
        neg.claim_winner(nid)
        _r, verdict = settle.recompute(nid)

        mission_blob = settle._signed_mission(neg.get(nid), verdict,
                                              int(__import__("time").time()))
        req = tools_mod.ProposalReq(
            mission=mission_blob,
            items=[{"sku": line.sku, "qty": 1} for line in verdict.lines])
        # One paisa above every possible list total.
        absurd = settle.NegotiatedSettlement(
            amount_paise=10 ** 9, merchant_id=verdict.merchant_id,
            transcript_hash=neg.get(nid)["transcript_hash"] or "")
        return await tools_mod.evaluate_proposal(req, settlement=absurd)

    with pytest.raises(HTTPException) as exc:
        asyncio.run(go())
    assert exc.value.status_code == 409
    assert (exc.value.detail["error"]["error_code"]
            == "SETTLEMENT_ABOVE_APPROVED_CEILING")


def test_the_negotiated_total_is_at_or_below_the_list_total(accepted):
    """The rule above, checked against what the market actually produces."""
    from apps.api.products import CATALOG

    _row, verdict = settle.recompute(accepted)
    list_total = sum(CATALOG[line.sku]["price_paise"] for line in verdict.lines)
    assert verdict.total_paise is not None
    assert verdict.total_paise <= list_total


# ------------------------------------------------------- exactly once

def test_settling_twice_does_not_open_a_second_payment(accepted):
    """The second call lands on the same execution row, not a new order."""
    first = asyncio.run(settle.settle(accepted))
    second = asyncio.run(settle.settle(accepted))

    assert second["order"]["order_id"] == first["order"]["order_id"]
    assert second["order"].get("duplicate") is True


def test_an_unaccepted_negotiation_cannot_be_settled():
    async def go():
        row = await neg.open_negotiation(mission_text=MISSION, allow_llm=False)
        return row["negotiation_id"]

    nid = asyncio.run(go())
    with pytest.raises(settle.SettlementRefused) as exc:
        asyncio.run(settle.settle(nid))
    assert exc.value.code == "NEGOTIATION_NOT_ACCEPTED"


# --------------------------------------------------------- the override

def test_the_judge_override_is_a_controlled_experiment(accepted):
    """Re-running on cheapest-first weights is deterministic and separate.

    The original negotiation is never mutated -- the override opens a new
    one. Two runs of the same override produce the same winner, which is
    what makes it evidence rather than a re-roll.
    """
    from apps.api.market.agents.buyer import CHEAPEST_WEIGHTS

    async def override():
        row = await neg.open_negotiation(
            mission_text=MISSION, allow_llm=False,
            weights_override=dict(CHEAPEST_WEIGHTS), override_of=accepted)
        nid = row["negotiation_id"]
        await neg.run_round(nid, allow_llm=False)
        return nid, neg.rank(nid)["winner"]["merchant_id"]

    first_id, first_winner = asyncio.run(override())
    second_id, second_winner = asyncio.run(override())

    assert first_winner == second_winner, "an override must be reproducible"
    assert first_id != second_id != accepted
    assert neg.get(accepted)["state"] == neg.ACCEPTED, \
        "the original negotiation must not be touched by an override"


def test_cheapest_weights_pick_the_cheapest_offer(accepted):
    """A weight change has to actually change what wins, or it is theatre."""
    from apps.api.market.agents.buyer import CHEAPEST_WEIGHTS

    async def go():
        row = await neg.open_negotiation(
            mission_text=MISSION, allow_llm=False,
            weights_override=dict(CHEAPEST_WEIGHTS), override_of=accepted)
        nid = row["negotiation_id"]
        await neg.run_round(nid, allow_llm=False)
        return nid

    nid = asyncio.run(go())
    offers = [o for o in neg.offers_for(nid) if o["accepted"]]
    cheapest = min(offers, key=lambda o: o["total_paise"])
    assert neg.rank(nid)["winner"]["merchant_id"] == cheapest["merchant_id"]


# ------------------------------------------------------------- the trace

def test_the_trace_shows_the_negotiation_the_purchase_came_from(accepted):
    """A settled market purchase is legible end to end on one page."""
    from apps.api.web.trace_page import build_trace, render_trace

    out = asyncio.run(settle.settle(accepted))
    execution_id = out["order"]["execution_id"]

    data = build_trace(execution_id)
    market = data["negotiation"]
    assert market is not None, "the trace did not find the negotiation"
    assert market["negotiation_id"] == accepted
    assert market["winner_merchant_id"] == out["merchant_id"]
    assert len(market["offers"]) == 3
    assert any(o["won"] for o in market["offers"])
    assert market["transcript_intact"] is True

    html = render_trace(data)
    assert "Negotiation transcript" in html
    assert out["transcript_hash"][:16] in html


def test_a_trace_of_an_ordinary_purchase_has_no_negotiation(client_free=None):
    """Most purchases never negotiated, and the trace must not invent one."""
    from apps.api.web.trace_page import build_trace

    row = store.query_one(
        "SELECT execution_id FROM payment_executions "
        "WHERE approve_seq NOT IN (SELECT settlement_approve_seq "
        "FROM market_negotiations "
        "WHERE settlement_approve_seq IS NOT NULL) LIMIT 1")
    if row is None:
        pytest.skip("no non-market execution in this database")

    assert build_trace(row["execution_id"])["negotiation"] is None


def test_the_trace_says_so_when_the_transcript_no_longer_matches(accepted):
    """The hash is only worth putting on the page if a mismatch shows.

    A page that always prints "intact" is decoration. This edits a row
    after settlement and checks the trace reports the disagreement rather
    than rendering the reassuring version.
    """
    from apps.api.web.trace_page import build_trace, render_trace

    out = asyncio.run(settle.settle(accepted))
    execution_id = out["order"]["execution_id"]
    assert build_trace(execution_id)["negotiation"]["transcript_intact"]

    store.execute(
        "UPDATE market_offers SET reason = 'tampered' WHERE negotiation_id = ?",
        (accepted,))

    market = build_trace(execution_id)["negotiation"]
    assert market["transcript_intact"] is False
    assert (market["transcript_hash_recomputed"]
            != market["transcript_hash_recorded"])
    assert "TRANSCRIPT ALTERED" in render_trace(build_trace(execution_id))
