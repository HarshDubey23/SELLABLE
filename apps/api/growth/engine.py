"""Merchant Growth Strategist Engine.

Analyzes buyer intent, leverages real-world competitor intelligence, and
synthesizes high-AOV, high-conversion product bundles that respect the buyer's
budget mandate and pass deterministic gateway governance.

KEY INVARIANTS:
1. Growth bundles MUST stay within the buyer's budget ceiling (R1_BUDGET).
2. Growth items MUST match the buyer's allowed categories (R5_CATEGORY).
3. Item prices MUST be pulled exclusively from the server-side CATALOG (R3_PRICE_DRIFT).
4. Web intelligence is UNTRUSTED and used only for advisory value propositions.
"""
from __future__ import annotations

from typing import Any

from pydantic import BaseModel

from ..products import CATALOG
from .intelligence import MarketIntelligenceRecord, get_market_intelligence


class BundleItem(BaseModel):
    sku: str
    name: str
    price_paise: int
    category: str
    is_base_item: bool = False
    role: str = "primary"  # "primary" | "cross_sell" | "accessory"


class GrowthEvaluationResult(BaseModel):
    intent: str
    budget_paise: int
    base_sku: str
    base_item_name: str
    base_price_paise: int
    bundle_items: list[BundleItem]
    bundle_total_paise: int
    aov_expansion_paise: int
    aov_expansion_pct: float
    market_intelligence: MarketIntelligenceRecord | None
    buyer_savings_vs_competitor_paise: int
    growth_strategy_summary: str
    gateway_precheck: dict[str, Any]
    is_compliant: bool = True


def evaluate_merchant_growth(
    intent: str,
    budget_paise: int,
    allowed_categories: list[str] | None = None,
    preferred_sku: str | None = None,
) -> GrowthEvaluationResult:
    """Execute strategic merchant growth analysis: intent -> discovery -> bundling -> gateway check."""
    allowed = set(c.lower() for c in (allowed_categories or ["cricket"]))
    intent_lower = intent.lower()

    # Step 1: Discover base item matching intent and category
    base_sku = preferred_sku
    if not base_sku or base_sku not in CATALOG:
        # Fuzzy match across catalog
        best_candidate = None
        for sku, item in CATALOG.items():
            if item.get("category") in allowed:
                # Check keywords in intent
                name_words = item["name"].lower().split()
                matches = sum(1 for w in name_words if w in intent_lower)
                if matches > 0 and item["price_paise"] <= budget_paise:
                    if best_candidate is None or matches > best_candidate[0]:
                        best_candidate = (matches, sku)
        if best_candidate:
            base_sku = best_candidate[1]
        else:
            # Fallback to first SKU in allowed category
            for sku, item in CATALOG.items():
                if item.get("category") in allowed and item["price_paise"] <= budget_paise:
                    base_sku = sku
                    break

    if not base_sku or base_sku not in CATALOG:
        # Ultimate fallback
        base_sku = "BAT-001"

    base_product = CATALOG[base_sku]
    base_price = base_product["price_paise"]

    # Step 2: Fetch real-world market intelligence (untrusted advisory context)
    market_intel = get_market_intelligence(base_sku)

    # Step 3: Compute Cross-Sell Bundling (AOV Expansion)
    # Remaining budget available for attaching compatible accessories
    bundle_items: list[BundleItem] = [
        BundleItem(
            sku=base_sku,
            name=base_product["name"],
            price_paise=base_price,
            category=base_product.get("category", "general"),
            is_base_item=True,
            role="primary",
        )
    ]

    current_bundle_total = base_price
    compat_skus = base_product.get("compatible_with", [])

    for addon_sku in compat_skus:
        if addon_sku in CATALOG:
            addon_item = CATALOG[addon_sku]
            addon_price = addon_item["price_paise"]
            addon_cat = addon_item.get("category", "")
            # Must be within allowed categories and within remaining budget
            if (not allowed or addon_cat in allowed) and (current_bundle_total + addon_price <= budget_paise):
                bundle_items.append(
                    BundleItem(
                        sku=addon_sku,
                        name=addon_item["name"],
                        price_paise=addon_price,
                        category=addon_cat,
                        is_base_item=False,
                        role="cross_sell",
                    )
                )
                current_bundle_total += addon_price

    # Step 4: Calculate Growth Metrics
    aov_expansion = current_bundle_total - base_price
    aov_expansion_pct = round((aov_expansion / base_price) * 100, 1) if base_price > 0 else 0.0

    # Calculate savings vs competitor
    comp_price = market_intel.competitor_price_paise if market_intel else base_price
    buyer_savings = max(0, comp_price - base_price)

    # Step 5: Gateway Pre-Check Simulation
    # Verify that this bundle satisfies R1 (budget) and R5 (category)
    precheck = {
        "R1_BUDGET": current_bundle_total <= budget_paise,
        "R5_CATEGORY": all(it.category in allowed for it in bundle_items) if allowed else True,
        "R3_SERVER_PRICING": True,
        "PASS": (current_bundle_total <= budget_paise),
    }

    # Strategy narrative
    addons_count = len(bundle_items) - 1
    if addons_count > 0:
        addon_names = ", ".join(it.name for it in bundle_items if not it.is_base_item)
        strategy = (
            f"Attached {addons_count} high-synergy cross-sell(s) ({addon_names}) "
            f"expanding AOV by +{aov_expansion_pct}% (₹{aov_expansion/100:.2f}) "
            f"while saving customer ₹{buyer_savings/100:.2f} vs {market_intel.competitor_name if market_intel else 'market'}."
        )
    else:
        strategy = (
            f"Positioned primary product with ₹{buyer_savings/100:.2f} savings "
            f"against {market_intel.competitor_name if market_intel else 'market'}."
        )

    return GrowthEvaluationResult(
        intent=intent,
        budget_paise=budget_paise,
        base_sku=base_sku,
        base_item_name=base_product["name"],
        base_price_paise=base_price,
        bundle_items=bundle_items,
        bundle_total_paise=current_bundle_total,
        aov_expansion_paise=aov_expansion,
        aov_expansion_pct=aov_expansion_pct,
        market_intelligence=market_intel,
        buyer_savings_vs_competitor_paise=buyer_savings,
        growth_strategy_summary=strategy,
        gateway_precheck=precheck,
        is_compliant=precheck["PASS"],
    )
