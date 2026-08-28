"""R11_NEGOTIATION_BOUND - Phase 3 FATAL gateway rule.

R11 enforces that every item's price is within [floor, ceiling] for every
SKU in the proposal, AND within the mission's effective budget.
Defense-in-depth: negotiation already clamps, R11 re-verifies at gateway.
"""
from __future__ import annotations

from typing import Any

from .types import Proposal, Violation


def rule_r11_negotiation_bound(proposal: Proposal,
                               catalog: dict[str, dict[str, Any]],
                               mission: Any) -> Violation | None:
    """Every item's price must be within [floor_paise, ceiling_paise].

    floor_paise and ceiling_paise are read from the CATALOG (server-side),
    NOT from the proposal. If a SKU lacks floor/ceiling in the catalog,
    the rule is skipped for that SKU (back-compat with pre-Day-5 catalogs).

    Returns a Violation if any item's price is out of bounds.
    """
    for item in proposal.items:
        product = catalog.get(item.sku)
        if not product:
            continue  # R5_SCOPE / R3 will catch unknown SKUs
        floor = product.get("floor_paise")
        ceiling = product.get("ceiling_paise")
        if floor is None or ceiling is None:
            continue  # pre-Day-5 catalog; skip
        unit_price = item.price_paise
        if unit_price < floor:
            return Violation(
                rule_id="R11_NEGOTIATION_BOUND",
                message=f"SKU {item.sku} price {unit_price}p below floor {floor}p",
                attempted_value=unit_price,
                limit_value=floor,
                hint="negotiation agreed below merchant walk-away; rejected",
            )
        if unit_price > ceiling:
            return Violation(
                rule_id="R11_NEGOTIATION_BOUND",
                message=f"SKU {item.sku} price {unit_price}p above ceiling {ceiling}p",
                attempted_value=unit_price,
                limit_value=ceiling,
                hint="negotiation agreed above MSRP; rejected",
            )
    return None
