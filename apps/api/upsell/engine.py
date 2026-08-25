"""
Deterministic Upsell Engine — the merchant's revenue growth layer.

ARCHITECTURAL PRINCIPLE: this engine NEVER offers anything the policy
gateway would reject. It reads the mission's signed upsell_cap and only
generates offers where the new total fits within the effective budget
(budget x cap). That means:

- Zero wasted proposals (every offer is pre-approved by R1)
- Zero trust violations (bounded by signed mission data)
- Zero model involvement (pure rules over catalog data)

The flow:
1. Buyer agent proposes BAT-001 (Rs 1,499, rating 4.1)
2. Engine finds BAT-002 (Rs 2,499, rating 4.6) — same category, higher rating
3. Engine checks: new_total <= budget_paise x upsell_cap
4. If it fits -> generate an offer with a reason string
5. Buyer decides: accept or decline (ONE additional decision step)
6. If accepted: the new proposal goes through the FULL gateway pass
7. Everything audited: upsell_offered -> upsell_accepted/declined -> verdict

This module imports nothing but the gateway types. Purity is enforced by
tests/test_upsell.py::test_upsell_engine_purity.
"""
from typing import Any

from ..gateway.types import Mission


def find_upgrade_candidates(
    sku: str,
    catalog: dict[str, dict[str, Any]],
    mission: Mission,
    current_cart_total: int,
) -> list[dict[str, Any]]:
    """
    Find higher-rated alternatives in the same category.

    Criteria:
    - Same category as the proposed SKU
    - Higher rating (minimum +0.3 difference)
    - Higher price (it's an upsell, not a downgrade)
    - Resulting total (replacing the SKU) must fit within
      effective budget (budget x upsell_cap) — THE PRE-GATE

    Returns ranked list (best value first).
    """
    if sku not in catalog:
        return []

    base_product = catalog[sku]
    base_category = base_product["category"]
    base_rating = base_product.get("rating", 0)
    base_price = base_product["price_paise"]

    effective_budget = int(mission.budget_paise * mission.upsell_cap)

    candidates = []
    for other_sku, other in catalog.items():
        if other_sku == sku:
            continue
        if other["category"] != base_category:
            continue

        other_rating = other.get("rating", 0)
        other_price = other["price_paise"]

        # Must be higher rated
        if other_rating - base_rating < 0.3:
            continue

        # Must be more expensive (upsell, not downgrade)
        if other_price <= base_price:
            continue

        # PRE-GATE: new total must fit within effective budget
        # (replacing this SKU in the cart)
        new_total = current_cart_total - base_price + other_price
        if new_total > effective_budget:
            continue

        # Value score: rating improvement per Rs 100 spent
        rating_delta = other_rating - base_rating
        price_delta = other_price - base_price
        value_score = rating_delta / (price_delta / 100)

        candidates.append({
            "from_sku": sku,
            "to_sku": other_sku,
            "to_name": other["name"],
            "from_rating": base_rating,
            "to_rating": other_rating,
            "from_price_paise": base_price,
            "to_price_paise": other_price,
            "delta_paise": price_delta,
            "new_total_paise": new_total,
            "effective_budget_paise": effective_budget,
            "value_score": round(value_score, 4),
            "reason": (
                f"rating {base_rating}->{other_rating} for "
                f"+Rs {price_delta/100:,.0f}, new total "
                f"Rs {new_total/100:,.0f} within your "
                f"{mission.upsell_cap}x cap"
            ),
        })

    # Sort by value score (best value first)
    candidates.sort(key=lambda x: x["value_score"], reverse=True)
    return candidates


def generate_upsell_offers(
    cart_skus: list[str],
    catalog: dict[str, dict[str, Any]],
    mission: Mission,
) -> list[dict[str, Any]]:
    """
    Generate upsell offers for a proposed cart.

    For each SKU in the cart, find upgrade candidates, merge and rank.
    Maximum 2 offers total — never overwhelm the buyer.

    All offers are PRE-GATED: the engine only offers what R1_BUDGET
    would approve. The gateway never sees a doomed upsell proposal.
    """
    cart_total = sum(
        catalog[sku]["price_paise"]
        for sku in cart_skus
        if sku in catalog
    )

    all_candidates = []
    for sku in cart_skus:
        candidates = find_upgrade_candidates(sku, catalog, mission, cart_total)
        all_candidates.extend(candidates)

    # Sort by value score
    all_candidates.sort(key=lambda x: x["value_score"], reverse=True)

    # Return max 2 offers
    return all_candidates[:2]
