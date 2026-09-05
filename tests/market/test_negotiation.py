"""The negotiation state machine: durable, replay-proof, accepted once.

Every test here runs with `allow_llm=False`. A unit test that reaches a
third-party provider is not a unit test — it is a slow, flaky integration
test wearing one's clothes, and it fails for reasons that have nothing to
do with the code under test. The live path has its own marked tests.
"""
from __future__ import annotations

import asyncio
import json

import pytest

from apps.api.market import negotiation as neg

MISSION = "A complete cricket setup under Rs 6,000"


async def _opened(**kw):
    return await neg.open_negotiation(mission_text=MISSION, allow_llm=False, **kw)


@pytest.fixture
def negotiation():
    return asyncio.run(_opened())


# ------------------------------------------------------------- opening

def test_opening_reads_the_mission_and_signs_a_ceiling(negotiation):
    assert negotiation["state"] == neg.OPEN
    assert negotiation["budget_paise"] == 600000
    assert negotiation["mission_id"].startswith("msn_mkt_")
    assert json.loads(negotiation["basket_json"])


def test_a_mission_the_catalog_cannot_serve_is_refused_not_faked():
    """No invented products. If nothing matches, say so."""
    with pytest.raises(ValueError, match="no catalog item"):
        asyncio.run(neg.open_negotiation(mission_text="", allow_llm=False))


# --------------------------------------------------------- transitions

def test_a_round_moves_through_the_declared_states(negotiation):
    nid = negotiation["negotiation_id"]
    row = asyncio.run(neg.run_round(nid, allow_llm=False))
    assert row["state"] == neg.ROUND_COMPLETE
    assert row["current_round"] == 1


def test_the_transition_table_is_enforced(negotiation):
    nid = negotiation["negotiation_id"]
    # OPEN cannot jump straight to ACCEPTED.
    with pytest.raises(neg.IllegalTransition):
        neg.transition(nid, neg.ACCEPTED)


def test_a_terminal_negotiation_refuses_further_rounds(negotiation):
    nid = negotiation["negotiation_id"]
    asyncio.run(neg.run_round(nid, allow_llm=False))
    neg.claim_winner(nid)
    with pytest.raises(neg.IllegalTransition, match="ACCEPTED"):
        asyncio.run(neg.run_round(nid, allow_llm=False))


def test_rounds_are_capped(negotiation):
    nid = negotiation["negotiation_id"]
    for _ in range(neg.MAX_ROUNDS):
        asyncio.run(neg.run_round(nid, allow_llm=False))
        neg.issue_counter(nid, merchant_id="NOVATECH", ask="FASTER_DELIVERY")
    with pytest.raises(neg.IllegalTransition, match="max"):
        asyncio.run(neg.run_round(nid, allow_llm=False))


def test_an_expired_negotiation_cannot_run_a_round(negotiation):
    nid = negotiation["negotiation_id"]
    from apps.api.store import db as store
    store.execute(
        "UPDATE market_negotiations SET expires_at = 1 WHERE negotiation_id = ?",
        (nid,))
    with pytest.raises(neg.IllegalTransition, match="expired"):
        asyncio.run(neg.run_round(nid, allow_llm=False))
    assert neg.get(nid)["state"] == neg.EXPIRED


# -------------------------------------------------------------- replay

def test_offer_ids_are_deterministic_so_a_replay_is_refused(negotiation):
    """The PRIMARY KEY is the replay defence, not a check that can be skipped."""
    from apps.api.market.agents.merchant import _offer_id

    nid = negotiation["negotiation_id"]
    first = _offer_id(nid, "NOVATECH", 1)
    assert first == _offer_id(nid, "NOVATECH", 1)
    assert first != _offer_id(nid, "NOVATECH", 2)
    assert first != _offer_id(nid, "GEARHUB", 1)


def test_a_replayed_round_cannot_produce_a_second_offer(negotiation):
    """Re-running round 1 writes nothing new: same ids, refused inserts."""
    nid = negotiation["negotiation_id"]
    asyncio.run(neg.run_round(nid, allow_llm=False))
    before = len(neg.offers_for(nid))

    # Force the machine back so the same round can be attempted again.
    from apps.api.store import db as store
    store.execute(
        "UPDATE market_negotiations SET state = ?, current_round = 0 "
        "WHERE negotiation_id = ?", (neg.OPEN, nid))

    asyncio.run(neg.run_round(nid, allow_llm=False))
    assert len(neg.offers_for(nid)) == before, \
        "a replayed round must not create duplicate offers"


# ---------------------------------------------------------- isolation

def test_a_counter_reaches_only_its_addressee(negotiation):
    """Isolation, checked on what each merchant is actually handed."""
    from apps.api.market import merchants as merchants_mod
    from apps.api.market.agents.merchant import build_prompt
    from apps.api.market.intents import BuyerCounter

    merchants_mod.seed()
    basket = [{"sku": "BAT-001", "name": "bat", "category": "cricket",
               "price_paise": 149900}]
    counter = BuyerCounter(merchant_id="NOVATECH", ask="FASTER_DELIVERY",
                           round=2)

    for m in merchants_mod.all_manifests():
        mine = counter if counter.merchant_id == m.merchant_id else None
        _system, user = build_prompt(manifest=m, basket=basket,
                                     mission_text=MISSION, round_no=2,
                                     counter=mine)
        if m.merchant_id == "NOVATECH":
            assert "come back to you" in user
        else:
            assert "come back to you" not in user, \
                f"{m.merchant_id} was told about a counter meant for another"


def test_no_merchants_prompt_ever_contains_a_rivals_identifier(negotiation):
    """The strongest form: check every other merchant's name is absent."""
    from apps.api.market import merchants as merchants_mod
    from apps.api.market.agents.merchant import build_prompt

    merchants_mod.seed()
    manifests = merchants_mod.all_manifests()
    basket = [{"sku": "BAT-001", "name": "bat", "category": "cricket",
               "price_paise": 149900}]

    for m in manifests:
        system, user = build_prompt(manifest=m, basket=basket,
                                    mission_text=MISSION, round_no=1,
                                    counter=None)
        blob = (system + user)
        for other in manifests:
            if other.merchant_id == m.merchant_id:
                continue
            assert other.merchant_id not in blob, \
                f"{m.merchant_id}'s prompt names {other.merchant_id}"
            assert other.display_name not in blob, \
                f"{m.merchant_id}'s prompt names {other.display_name}"


# --------------------------------------------------------- transcript

def test_the_transcript_hash_does_not_depend_on_arrival_order(negotiation):
    """Merchants answer concurrently, so arrival order differs every run.

    The hash goes into the approval binding. If it moved with the race,
    the same negotiation would authorize a different payment each time it
    was hashed, which would make the binding meaningless.
    """
    nid = negotiation["negotiation_id"]
    asyncio.run(neg.run_round(nid, allow_llm=False))
    assert len({neg.transcript_hash(nid) for _ in range(20)}) == 1


def test_the_transcript_changes_when_the_negotiation_does(negotiation):
    nid = negotiation["negotiation_id"]
    asyncio.run(neg.run_round(nid, allow_llm=False))
    before = neg.transcript_hash(nid)
    neg.issue_counter(nid, merchant_id="NOVATECH", ask="LOWER_PRICE")
    assert neg.transcript_hash(nid) != before


def test_the_transcript_records_which_agent_produced_each_offer(negotiation):
    nid = negotiation["negotiation_id"]
    asyncio.run(neg.run_round(nid, allow_llm=False))
    for event in neg.canonical_transcript(nid):
        if event["kind"] == "offer":
            assert event["agent_source"], "every offer must say how it was made"


# ------------------------------------------------------ exactly once

def test_accept_is_exactly_once_under_concurrency(negotiation):
    """Twenty threads race. One binding, nineteen refusals."""
    import threading

    nid = negotiation["negotiation_id"]
    asyncio.run(neg.run_round(nid, allow_llm=False))

    wins: list[dict] = []
    refusals: list[Exception] = []
    lock = threading.Lock()

    def attempt():
        try:
            out = neg.claim_winner(nid)
            with lock:
                wins.append(out)
        except Exception as exc:
            with lock:
                refusals.append(exc)

    threads = [threading.Thread(target=attempt) for _ in range(20)]
    for t in threads:
        t.start()
    for t in threads:
        t.join()

    assert len(wins) == 1, f"{len(wins)} accepts succeeded; must be exactly 1"
    assert len(refusals) == 19
    assert neg.get(nid)["state"] == neg.ACCEPTED


def test_the_accepted_winner_is_recorded_with_its_transcript_hash(negotiation):
    nid = negotiation["negotiation_id"]
    asyncio.run(neg.run_round(nid, allow_llm=False))
    out = neg.claim_winner(nid)
    row = neg.get(nid)
    assert row["winner_merchant_id"] == out["ranking"]["winner"]["merchant_id"]
    assert row["transcript_hash"] == out["transcript_hash"]
    assert len(row["transcript_hash"]) == 64


# --------------------------------------------------------- recovery

def test_a_round_interrupted_by_a_crash_recovers_to_failed(negotiation):
    """We cannot know which merchants replied, so we do not pretend to."""
    nid = negotiation["negotiation_id"]
    neg.transition(nid, neg.AWAITING_OFFERS, current_round=1)

    moved = neg.recover_stranded()
    assert nid in moved
    row = neg.get(nid)
    assert row["state"] == neg.FAILED
    assert "process restarted" in row["last_error"]


def test_a_completed_round_survives_a_restart(negotiation):
    """ROUND_COMPLETE is genuinely resumable and must be left alone."""
    nid = negotiation["negotiation_id"]
    asyncio.run(neg.run_round(nid, allow_llm=False))
    neg.recover_stranded()
    assert neg.get(nid)["state"] == neg.ROUND_COMPLETE


def test_an_elapsed_window_is_swept_to_expired(negotiation):
    from apps.api.store import db as store
    nid = negotiation["negotiation_id"]
    store.execute(
        "UPDATE market_negotiations SET expires_at = 1 WHERE negotiation_id = ?",
        (nid,))
    assert nid in neg.recover_stranded()
    assert neg.get(nid)["state"] == neg.EXPIRED


# ------------------------------------------------------- determinism

def test_the_keyless_market_is_reproducible():
    """Two keyless runs of the same mission produce the same offers.

    This is what makes a reviewer's clone useful: they see the same
    market I do, and can compare against what the README says.
    """
    async def run():
        row = await neg.open_negotiation(mission_text=MISSION, allow_llm=False)
        nid = row["negotiation_id"]
        await neg.run_round(nid, allow_llm=False)
        return [(o["merchant_id"], o["total_paise"], o["reason"])
                for o in neg.offers_for(nid)]

    first = asyncio.run(run())
    second = asyncio.run(run())
    assert first == second
    assert len(first) == 3


# ------------------------------------------------------- honest matching

def test_a_description_word_cannot_make_one_product_into_another():
    """Asked for a camera, the catalog must not answer with a charger.

    It did. "Camera and lens for travel" matched CHG-001, a 65W charger,
    on the words "compact travel size" in its description -- a real
    catalog row, honestly labelled, and completely wrong. Three merchants
    then bid on a charger as though the request had been served.

    A word in a description says something about a product. The name and
    the category say what it *is*, and only that can make it an answer.
    """
    from apps.api.market.agents.buyer import keyword_plan
    from apps.api.products import CATALOG

    assert "travel" in str(CATALOG["CHG-001"]["description"]).lower(), \
        "this test is meaningless if the charger no longer mentions travel"

    plan = keyword_plan("Camera and lens for travel under Rs 1,50,000",
                        CATALOG)
    assert plan is None or "CHG-001" not in plan.skus, \
        "a charger was returned for a camera request"


def test_the_catalog_answers_what_it_stocks_and_refuses_what_it_does_not():
    """Both halves matter. Refusing everything would also pass one of them."""
    from apps.api.market.agents.buyer import keyword_plan
    from apps.api.products import CATALOG

    served = ["A complete cricket setup under Rs 6,000",
              "A gaming PC under Rs 80,000",
              "Best laptop for coding under Rs 90,000",
              # Monitors, keyboards and mice are stocked now, so refusing
              # this would be the catalog lying about itself.
              "Best monitor keyboard and mouse combo under Rs 35,000"]
    refused = ["Camera and lens for travel under Rs 1,50,000",
               "a submarine"]

    for mission in served:
        plan = keyword_plan(mission, CATALOG)
        assert plan is not None and plan.skus, f"should serve: {mission}"
    for mission in refused:
        assert keyword_plan(mission, CATALOG) is None, \
            f"should refuse rather than substitute something: {mission}"


# --------------------------------------------------------- the counter

def test_a_counter_issued_through_the_api_actually_reaches_the_merchant():
    """A counter that is recorded but never delivered is theatre.

    issue_counter writes the counter, moves the state and changes the
    transcript hash. None of that asks anybody anything. run_round used
    to take the counter only as an argument, and the HTTP route that runs
    a round has no way to pass one -- so every counter sent from the page
    was written down, displayed, hashed into the transcript, and dropped
    before a merchant was asked to respond.

    This calls run_round the way the route does: with no counter
    argument at all.
    """
    async def go(nid: str) -> None:
        await neg.run_round(nid, allow_llm=False)

    row = asyncio.run(_opened())
    nid = row["negotiation_id"]
    asyncio.run(go(nid))

    def delivery(round_no: int) -> dict[str, int]:
        return {o["merchant_id"]: json.loads(o["intent_json"])["delivery_days"]
                for o in neg.offers_for(nid) if o["round"] == round_no}

    before = delivery(1)
    winner = neg.rank(nid)["winner"]["merchant_id"]
    neg.issue_counter(nid, merchant_id=winner, ask="FASTER_DELIVERY")

    asyncio.run(go(nid))                       # no counter passed
    after = delivery(2)

    assert after[winner] < before[winner], \
        "the merchant that was asked for faster delivery did not move"
    for other in before:
        if other != winner:
            assert after[other] == before[other], \
                f"{other} changed, but the counter was not addressed to it"


def test_a_counter_never_makes_the_offer_it_asked_about_worse():
    """Asked to improve one dimension, a merchant must not go backwards on it.

    Before merchants were shown their own previous offer, "improve your
    offer" had nothing to improve on: GEARHUB, asked for faster
    delivery, came back with 4 days changed to 7. It was not refusing --
    it had never been told what it had already said.
    """
    row = asyncio.run(_opened())
    nid = row["negotiation_id"]
    asyncio.run(neg.run_round(nid, allow_llm=False))

    winner = neg.rank(nid)["winner"]["merchant_id"]
    was = {o["merchant_id"]: json.loads(o["intent_json"])
           for o in neg.offers_for(nid) if o["round"] == 1}[winner]

    for ask, field, better in (("FASTER_DELIVERY", "delivery_days", "lower"),
                               ("LONGER_WARRANTY", "warranty_years", "higher"),
                               ("LOWER_PRICE", "line_discount_pct", "higher")):
        fresh = asyncio.run(_opened())
        fid = fresh["negotiation_id"]
        asyncio.run(neg.run_round(fid, allow_llm=False))
        neg.issue_counter(fid, merchant_id=winner, ask=ask)
        asyncio.run(neg.run_round(fid, allow_llm=False))

        now = {o["merchant_id"]: json.loads(o["intent_json"])
               for o in neg.offers_for(fid) if o["round"] == 2}
        if winner not in now:
            continue
        if better == "lower":
            assert now[winner][field] <= was[field], f"{ask} made {field} worse"
        else:
            assert now[winner][field] >= was[field], f"{ask} made {field} worse"


def test_a_merchant_is_shown_its_own_last_offer_and_no_one_elses():
    """Showing the previous offer is only safe because it is its own."""
    from apps.api.market import merchants as merchants_mod
    from apps.api.market.agents.merchant import build_prompt
    from apps.api.market.intents import OfferIntent

    merchants_mod.seed()
    basket = [{"sku": "BAT-001", "name": "bat", "category": "cricket",
               "price_paise": 149900}]
    previous = OfferIntent(
        merchant_id="NOVATECH", basket_sku_set=("BAT-001",),
        line_discount_pct=7, bundle_discount_pct=0, shipping="STANDARD",
        delivery_days=2, warranty_years=1, round=1, offer_id="off-prev-1")

    _system, user = build_prompt(
        manifest=merchants_mod.get("NOVATECH"), basket=basket,
        mission_text=MISSION, round_no=2, counter=None, previous=previous)

    assert "What you offered last round" in user
    assert "delivery 2 day(s)" in user
    for other in merchants_mod.all_manifests():
        if other.merchant_id != "NOVATECH":
            assert other.merchant_id not in user
            assert other.display_name not in user


def test_an_occasion_word_in_a_name_cannot_answer_a_different_request():
    """Asked for a camera, the catalog must not offer a travel yoga mat.

    "Camera and lens for travel" matched the Liforme Travel Yoga Mat,
    because "travel" is in its name. The same shape as the charger that
    answered a camera request on "compact travel size": a word saying
    when or why you would use a thing is not a word saying what it is.
    """
    from apps.api.market.agents.buyer import keyword_plan
    from apps.api.products import CATALOG

    travel_named = [s for s, i in CATALOG.items()
                    if "travel" in i["name"].lower()]
    assert travel_named, "this test is meaningless with no travel-named product"

    plan = keyword_plan("Camera and lens for travel under Rs 1,50,000",
                        CATALOG)
    assert plan is None or not (set(plan.skus) & set(travel_named))


def test_a_setup_spans_families_rather_than_repeating_one():
    """"A complete cricket setup" returned three cricket balls.

    They were the cheapest matching items and nothing stopped one family
    filling the basket. A setup means a bat and a ball and pads, so
    families are taken round-robin before any of them doubles up.
    """
    from apps.api.market.agents.buyer import keyword_plan
    from apps.api.products import CATALOG

    plan = keyword_plan("A complete cricket setup under Rs 6,000", CATALOG)
    assert plan is not None and len(plan.skus) >= 3

    families = [str((CATALOG[s].get("attributes") or {}).get(
        "family", CATALOG[s]["category"])) for s in plan.skus]
    assert len(set(families)) >= 3,         f"a setup should span families, got {families}"
