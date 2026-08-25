"""
Upsell/Cross-sell Engine Tests — hand-written.
Verifies pre-gating, rating thresholds, and purity.
"""
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from apps.api.gateway.types import Mission
from apps.api.products import CATALOG
from apps.api.upsell.crosssell import find_cross_sell_candidates
from apps.api.upsell.engine import find_upgrade_candidates, generate_upsell_offers


def make_test_mission(budget=300000, cap=1.5):
    return Mission(
        mission_id="MSN-UPSELL-TEST",
        intent="test",
        budget_paise=budget,
        allowed_categories=("cricket",),
        forbidden_categories=(),
        upsell_cap=cap,
        expires_at=int(time.time()) + 3600,
        signature="test",
    )


def test_offer_within_effective_budget():
    """Budget 300000, cap 1.5 -> effective 450000. BAT-001 -> BAT-002 fits."""
    mission = make_test_mission(budget=300000, cap=1.5)
    offers = generate_upsell_offers(["BAT-001"], CATALOG, mission)
    # BAT-001 (149900, 4.1) -> BAT-002 (249900, 4.6): new_total 249900 < 450000
    assert len(offers) > 0
    assert offers[0]["from_sku"] == "BAT-001"
    assert offers[0]["to_sku"] == "BAT-002"
    assert offers[0]["new_total_paise"] <= 450000


def test_offer_exceeds_effective_budget_not_offered():
    """Budget too low -> no offers generated."""
    mission = make_test_mission(budget=100000, cap=1.0)
    # Effective budget = 100000. BAT-001 alone is 149900 — can't even fit.
    offers = generate_upsell_offers(["BAT-001"], CATALOG, mission)
    assert len(offers) == 0


def test_no_offer_small_rating_delta():
    """Rating difference < 0.3 -> that product is never offered."""
    mission = make_test_mission(budget=500000, cap=2.0)
    offers = generate_upsell_offers(["TSH-001"], CATALOG, mission)
    # TSH-002 has rating 4.1 vs 4.0 = 0.1 delta — below threshold.
    for offer in offers:
        assert offer["to_sku"] != "TSH-002", \
            "TSH-002 offered despite rating delta only 0.1"


def test_upgrade_candidates_ranked_by_value():
    """Multiple candidates come back sorted best-value first."""
    mission = make_test_mission(budget=500000, cap=2.0)
    candidates = find_upgrade_candidates("GRIP-001", CATALOG, mission, 29900)
    if len(candidates) > 1:
        scores = [c["value_score"] for c in candidates]
        assert scores == sorted(scores, reverse=True)


def test_crosssell_from_compatible_with():
    """BAT-001 in cart -> a compatible add-on should be offered."""
    mission = make_test_mission(budget=500000, cap=2.0)
    offers = find_cross_sell_candidates(["BAT-001"], CATALOG, mission)
    assert len(offers) > 0
    # GRIP-001 and BALL-001 are both in BAT-001's compatible_with
    addon_skus = [o["addon_sku"] for o in offers]
    assert "GRIP-001" in addon_skus or "BALL-001" in addon_skus


def test_crosssell_respects_budget():
    """Cross-sell that would exceed effective budget -> not offered."""
    # BAT-001 = 149900. GRIP-001 = 29900. Total = 179800.
    # Set budget = 150000, cap = 1.0 -> effective = 150000.
    mission = make_test_mission(budget=150000, cap=1.0)
    offers = find_cross_sell_candidates(["BAT-001"], CATALOG, mission)
    # 149900 + 29900 = 179800 > 150000 -> no offers
    assert len(offers) == 0


def test_upsell_engine_purity():
    """Upsell engine modules are pure rules — no model/network imports."""
    import apps.api.upsell.crosssell as crosssell_mod
    import apps.api.upsell.engine as engine_mod

    forbidden = ["llm", "genai", "openai", "anthropic", "langchain",
                 "gemini", "llama"]

    for module in [engine_mod, crosssell_mod]:
        source = Path(module.__file__).read_text()
        for pattern in forbidden:
            assert pattern not in source.lower(), \
                f"Forbidden pattern '{pattern}' found in {module.__file__}"
