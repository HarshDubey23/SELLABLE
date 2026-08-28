"""Test the bounded negotiation engine."""
import os
import sys
from pathlib import Path

# Use a throwaway DB for tests - must set before importing store
os.environ["SELLABLE_DB_PATH"] = str(Path(__file__).resolve().parent / "_test_neg.db")

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from apps.api.negotiation import bounds as B
from apps.api.negotiation import engine as E
from apps.api.negotiation import strategies as S
from apps.api.negotiation.types import NegotiationActor, NegotiationBounds, NegotiationStatus


def _bounds(floor=5000, ceiling=10000, qty=1, max_turns=5, walk_away_gap=500):
    return NegotiationBounds(
        sku="TEST-SKU", floor_paise=floor, ceiling_paise=ceiling,
        qty=qty, max_turns=max_turns, walk_away_gap_paise=walk_away_gap,
    )


def test_clamp_offer():
    b = _bounds(floor=5000, ceiling=10000)
    o = B.clamp_offer(99999, b, NegotiationActor.MERCHANT, 1, "x", 1)
    assert o.price_paise == 10000
    assert o.raw_price_paise == 99999
    o = B.clamp_offer(100, b, NegotiationActor.MERCHANT, 1, "x", 1)
    assert o.price_paise == 5000


def test_monotonic_merchant():
    b = _bounds()
    o1 = B.clamp_offer(10000, b, NegotiationActor.MERCHANT, 1, "a", 1)
    o2 = B.clamp_offer(9000, b, NegotiationActor.MERCHANT, 1, "b", 2)
    assert B.check_monotonic(o1, o2) is True
    o3 = B.clamp_offer(9500, b, NegotiationActor.MERCHANT, 1, "c", 3)
    assert B.check_monotonic(o2, o3) is False


def test_monotonic_buyer():
    b = _bounds()
    o1 = B.clamp_offer(5500, b, NegotiationActor.BUYER, 1, "a", 1)
    o2 = B.clamp_offer(6000, b, NegotiationActor.BUYER, 1, "b", 2)
    assert B.check_monotonic(o1, o2) is True
    o3 = B.clamp_offer(5800, b, NegotiationActor.BUYER, 1, "c", 3)
    assert B.check_monotonic(o2, o3) is False


def test_walk_away_after_max_turns():
    # Buyer budget is below the merchant floor: the buyer's offers clamp to
    # the floor, but the budget hard-gate downgrades the deal to WALKED_AWAY
    # (an agreed price above budget is never accepted - no money is lost).
    state = E.start_negotiation(
        mission_id="MSN-WA", sku="TEST-SKU", qty=1,
        floor_paise=5000, ceiling_paise=10000,
        buyer_budget_paise=4800,  # budget below floor -> cannot converge
        max_turns=3, walk_away_gap_paise=100,
        llm_enabled=False,
    )
    state = E.run_to_completion(state, llm_enabled=False, max_iterations=5)
    assert state.status == NegotiationStatus.WALKED_AWAY, f"expected WALKED_AWAY, got {state.status}"
    assert len(state.turns) == 3


def test_acceptance_on_meet():
    state = E.start_negotiation(
        mission_id="MSN-ACC", sku="TEST-SKU", qty=1,
        floor_paise=5000, ceiling_paise=10000,
        buyer_budget_paise=15000,
        max_turns=5, walk_away_gap_paise=100,
        llm_enabled=False,
    )
    state = E.run_to_completion(state, llm_enabled=False, max_iterations=6)
    assert state.status == NegotiationStatus.ACCEPTED, f"expected ACCEPTED, got {state.status}"
    assert state.final_price_paise is not None


def test_budget_hard_gate():
    """If agreed price > budget, downgrade to WALKED_AWAY."""
    state = E.start_negotiation(
        mission_id="MSN-BUDGET", sku="TEST-SKU", qty=1,
        floor_paise=8000, ceiling_paise=10000,
        buyer_budget_paise=6000,
        max_turns=2, walk_away_gap_paise=0,
        llm_enabled=False,
    )
    state = E.run_to_completion(state, llm_enabled=False, max_iterations=3)
    assert state.status == NegotiationStatus.WALKED_AWAY, f"expected WALKED_AWAY (budget), got {state.status}"


def test_audit_chain_links():
    """Every turn appends audit rows; parent_action_id threads through."""
    from apps.api.audit import chain as audit
    before = len(audit.entries())
    state = E.start_negotiation(
        mission_id="MSN-AUDIT", sku="TEST-SKU", qty=1,
        floor_paise=5000, ceiling_paise=10000,
        buyer_budget_paise=15000, max_turns=3, walk_away_gap_paise=100,
        llm_enabled=False,
    )
    state = E.run_turn(state, llm_enabled=False)
    after = len(audit.entries())
    assert after - before >= 3, f"expected >=3 new audit rows, got {after-before}"


def test_merchant_strategy_anchor_then_concede():
    b = _bounds(floor=5000, ceiling=10000, max_turns=5)
    p1 = S.merchant_counter_price(1, b, None)
    assert p1 == 10000, f"turn 1 should anchor at ceiling, got {p1}"
    p5 = S.merchant_counter_price(5, b, None)
    assert p5 == 5000, f"turn 5 should be floor, got {p5}"
    prices = [S.merchant_counter_price(t, b, 5000) for t in range(1, 6)]
    assert all(prices[i] >= prices[i+1] for i in range(len(prices)-1)), f"prices not monotonic: {prices}"


def test_determinism_same_seed():
    """Same bounds + budget -> same final price (LLM disabled)."""
    s1 = E.start_negotiation(
        mission_id="MSN-DET1", sku="TEST-SKU", qty=1,
        floor_paise=5000, ceiling_paise=10000,
        buyer_budget_paise=12000, max_turns=4, walk_away_gap_paise=100,
        llm_enabled=False,
    )
    s1 = E.run_to_completion(s1, llm_enabled=False, max_iterations=5)
    s2 = E.start_negotiation(
        mission_id="MSN-DET2", sku="TEST-SKU", qty=1,
        floor_paise=5000, ceiling_paise=10000,
        buyer_budget_paise=12000, max_turns=4, walk_away_gap_paise=100,
        llm_enabled=False,
    )
    s2 = E.run_to_completion(s2, llm_enabled=False, max_iterations=5)
    assert s1.final_price_paise == s2.final_price_paise, \
        f"non-deterministic: {s1.final_price_paise} vs {s2.final_price_paise}"
