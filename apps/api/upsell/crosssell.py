"""
Deterministic Cross-sell Engine — compatibility-based add-ons.

Finds products that logically pair with items already in the cart,
using the compatible_with links in the catalog. Like the upsell
engine, it is PRE-GATED: only offers add-ons that keep the total
within the effective budget (budget x upsell_cap).

Pure rules over catalog data. No model calls, no network, no I/O.
"""
from typing import Any

from ..gateway.types import Mission


def find_cross_sell_candidates(
    cart_skus: list[str],
    catalog: dict[str, dict[str, Any]],
    mission: Mission,
) -> list[dict[str, Any]]:
    """
    Find compatible add-ons for the proposed cart.

    Criteria:
    - From compatible_with of cart items
    - Add-on SKU not already in cart
    - Total (cart + add-on) fits within effective budget
    - Return maximum 1 offer (cross-sell is lighter than upsell)
    """
    effective_budget = int(mission.budget_paise * mission.upsell_cap)
    cart_total = sum(
        catalog[sku]["price_paise"]
        for sku in cart_skus
        if sku in catalog
    )

    candidates = []
    seen_addons: set[str] = set()  # avoid duplicate offers

    for sku in cart_skus:
        if sku not in catalog:
            continue

        for addon_sku in catalog[sku].get("compatible_with", []):
            # Skip if already in cart
            if addon_sku in cart_skus:
                continue

            # Skip if we've already considered this addon
            if addon_sku in seen_addons:
                continue
            seen_addons.add(addon_sku)

            if addon_sku not in catalog:
                continue

            addon_price = catalog[addon_sku]["price_paise"]
            new_total = cart_total + addon_price

            # PRE-GATE: must fit within effective budget
            if new_total > effective_budget:
                continue

            addon_product = catalog[addon_sku]
            candidates.append({
                "base_sku": sku,
                "addon_sku": addon_sku,
                "addon_name": addon_product["name"],
                "addon_price_paise": addon_price,
                "new_total_paise": new_total,
                "effective_budget_paise": effective_budget,
                "reason": (
                    f"pairs with your {catalog[sku]['name']}, "
                    f"+Rs {addon_price/100:,.0f}, new total "
                    f"Rs {new_total/100:,.0f}"
                ),
            })

    # Return max 1 offer
    return candidates[:1]
