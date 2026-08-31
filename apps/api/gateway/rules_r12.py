"""R12_PROTOCOL_SCOPE - Phase 3 FATAL gateway rule (Phase 4).

Protocol adapters (ACP/AP2) carry signed scope artifacts with each request:
merchant scope, category scope, amount ceiling, validity window. R12 re-binds
those artifacts at the gateway so a drifted or replayed scope cannot widen a
proposal the wallet already bounded. Rejects citing the drifted field path.

The rule is FAIL-CLOSED on malformed scope: a non-dict or wrongly-typed
artifact is a violation, never a pass. scope=None means "no protocol
artifacts on this request" (native sellable-v1 traffic) and is skipped —
the same back-compat contract as R11's floor/ceiling skip.
"""
from __future__ import annotations

from typing import Any

from .types import Proposal, Violation

Catalog = dict[str, dict[str, Any]]


def rule_r12_protocol_scope(proposal: Proposal,
                            catalog: Catalog,
                            scope: Any,
                            *,
                            merchant_id: str,
                            now_ts: int) -> Violation | None:
    """Bind the proposal to the request's protocol scope artifacts.

    scope keys (all optional, but each must be well-typed when present):
      merchant_id: str           — the merchant the artifacts were minted for
      category_scope: list[str]  — categories the protocol session may touch
      amount_ceiling_paise: int  — max catalog-priced total for this session
      valid_until: int           — unix seconds; now must be strictly before
    """
    if scope is None:
        return None
    if not isinstance(scope, dict):
        return Violation(
            rule_id="R12_PROTOCOL_SCOPE",
            message="protocol scope is not an object (fail-closed)",
            hint="adapters must send protocol_scope as a JSON object or omit it",
        )

    bound_merchant = scope.get("merchant_id")
    if bound_merchant is not None:
        if not isinstance(bound_merchant, str):
            return Violation(
                "R12_PROTOCOL_SCOPE",
                "protocol_scope.merchant_id is not a string (fail-closed)",
            )
        if bound_merchant != merchant_id:
            return Violation(
                "R12_PROTOCOL_SCOPE",
                f"protocol scope binds merchant '{bound_merchant}' but the "
                f"request targets '{merchant_id}'",
                hint="merchant scope drift; re-mint the protocol artifacts",
            )

    category_scope = scope.get("category_scope")
    if category_scope is not None:
        if not isinstance(category_scope, list) or not all(
            isinstance(c, str) for c in category_scope
        ):
            return Violation(
                "R12_PROTOCOL_SCOPE",
                "protocol_scope.category_scope is not a list of strings "
                "(fail-closed)",
            )
        for idx, item in enumerate(proposal.items):
            product = catalog.get(item.sku)
            if not product:
                continue  # R5_SCOPE / R3 catch unknown SKUs first
            cat = product["category"]
            if cat not in category_scope:
                return Violation(
                    "R12_PROTOCOL_SCOPE",
                    f"items[{idx}] ({item.sku}) is category '{cat}' outside "
                    f"the protocol session's category scope",
                    hint="category scope drift; re-mint the protocol artifacts",
                )

    ceiling = scope.get("amount_ceiling_paise")
    if ceiling is not None:
        if not isinstance(ceiling, int) or isinstance(ceiling, bool):
            return Violation(
                "R12_PROTOCOL_SCOPE",
                "protocol_scope.amount_ceiling_paise is not an int "
                "(fail-closed)",
            )
        total = sum(catalog[i.sku]["price_paise"] * i.qty
                    for i in proposal.items if i.sku in catalog)
        if total > ceiling:
            return Violation(
                "R12_PROTOCOL_SCOPE",
                f"total {total} paise exceeds the protocol session's amount "
                f"ceiling {ceiling} paise",
                attempted_value=total,
                limit_value=ceiling,
                hint="amount ceiling drift; re-mint the protocol artifacts",
            )

    valid_until = scope.get("valid_until")
    if valid_until is not None:
        if not isinstance(valid_until, int) or isinstance(valid_until, bool):
            return Violation(
                "R12_PROTOCOL_SCOPE",
                "protocol_scope.valid_until is not an int (fail-closed)",
            )
        if now_ts >= valid_until:
            return Violation(
                "R12_PROTOCOL_SCOPE",
                f"protocol session expired at {valid_until}, now {now_ts}",
                attempted_value=now_ts,
                limit_value=valid_until,
                hint="validity window drift; re-mint the protocol artifacts",
            )

    return None
