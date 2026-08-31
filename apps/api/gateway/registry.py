"""Canonical rule registry — single source of truth for gateway.

All 12 rules (R1-R12) are defined here. Engine, /policy, docs, and tests
must import from here — never hard-code a separate list.
"""
from __future__ import annotations

from typing import Any

RULE_REGISTRY: list[dict[str, Any]] = [
    {"rule_id": "R9_SIGNATURE", "phase": 0, "severity": "FATAL", "check_description": "mission HMAC must verify"},
    {"rule_id": "R10_EXPIRY", "phase": 0, "severity": "FATAL", "check_description": "now < expires_at (== rejects)"},
    {"rule_id": "R8_ABORT", "phase": 1, "severity": "FATAL", "check_description": "mission not aborted"},
    {"rule_id": "R1_BUDGET", "phase": 2, "severity": "REVISABLE", "check_description": "catalog-priced total <= budget_paise x upsell_cap (effective budget)"},
    {"rule_id": "R2_FORBIDDEN", "phase": 2, "severity": "REVISABLE", "check_description": "no forbidden-category items"},
    {"rule_id": "R5_SCOPE", "phase": 2, "severity": "REVISABLE", "check_description": "items within allowed_categories"},
    {"rule_id": "R4_UPSELL_CAP", "phase": 2, "severity": "REVISABLE", "check_description": "defense-in-depth mirror of the effective-budget ceiling"},
    {"rule_id": "R3_PRICE_DRIFT", "phase": 3, "severity": "FATAL", "check_description": "claimed price == catalog price (+-0 paise)"},
    {"rule_id": "R11_NEGOTIATION_BOUND", "phase": 3, "severity": "FATAL", "check_description": "price within [floor_paise, ceiling_paise] from server catalog"},
    {"rule_id": "R12_PROTOCOL_SCOPE", "phase": 3, "severity": "FATAL", "check_description": "proposal within protocol artifacts (merchant scope, category scope, amount ceiling, validity window); fails closed on malformed scope"},
    {"rule_id": "R7_ALLOWLIST", "phase": 3, "severity": "FATAL", "check_description": "merchant allowlisted"},
    {"rule_id": "R6_RATE_LIMIT", "phase": 3, "severity": "FATAL", "check_description": "<=5 proposals per 60s per mission"},
]

# Map rule_id -> registry entry for quick lookup
RULE_BY_ID = {r["rule_id"]: r for r in RULE_REGISTRY}

def rules_count() -> int:
    return len(RULE_REGISTRY)
