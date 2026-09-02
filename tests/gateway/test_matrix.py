"""
tests/gateway/test_matrix.py - R1-R12 gateway rule matrix
"""
import time

from apps.api.gateway.rules import (
    rule_r1_budget,
    rule_r2_forbidden,
    rule_r3_price_drift,
    rule_r5_scope,
)
from apps.api.gateway.rules_r11 import rule_r11_negotiation_bound
from apps.api.gateway.rules_r12 import rule_r12_protocol_scope
from apps.api.gateway.types import Mission, Proposal, ProposalItem, Violation

CATALOG = {
    "SKU-1": {"price_paise": 10000, "category": "electronics",
               "floor_paise": 8000, "ceiling_paise": 12000},
    "SKU-2": {"price_paise": 5000, "category": "books",
               "floor_paise": 4000, "ceiling_paise": 6000},
    "SKU-BAD": {"price_paise": 999999, "category": "weapons",
                 "floor_paise": 0, "ceiling_paise": 999999},
}


def _mission(budget=50000, allowed=None, forbidden=None, expires_at=None, sig="sig"):
    return Mission(
        mission_id="m1",
        intent="buy something",
        budget_paise=budget, upsell_cap=1.3,
        allowed_categories=tuple(allowed or ["electronics", "books"]),
        forbidden_categories=tuple(forbidden or []),
        expires_at=expires_at or (int(time.time()) + 3600),
        signature=sig,
    )


def _proposal(items):
    return Proposal(mission_id="m1", items=tuple(ProposalItem(**i) for i in items))


# R1 BUDGET
def test_r1_within_budget():
    p = _proposal([{"sku": "SKU-1", "qty": 1, "price_paise": 10000}])
    assert rule_r1_budget(p, CATALOG, _mission(budget=50000)) is None


def test_r1_over_budget():
    p = _proposal([{"sku": "SKU-1", "qty": 10, "price_paise": 10000}])
    result = rule_r1_budget(p, CATALOG, _mission(budget=50000))
    assert isinstance(result, Violation)
    assert result.rule_id == "R1_BUDGET"


# R2 FORBIDDEN
def test_r2_forbidden_category():
    p = _proposal([{"sku": "SKU-BAD", "qty": 1, "price_paise": 999999}])
    result = rule_r2_forbidden(p, CATALOG, _mission(forbidden=["weapons"]))
    assert isinstance(result, Violation)
    assert result.rule_id == "R2_FORBIDDEN"


def test_r2_unknown_sku_rejected():
    p = _proposal([{"sku": "UNKNOWN", "qty": 1, "price_paise": 1000}])
    result = rule_r2_forbidden(p, CATALOG, _mission())
    assert isinstance(result, Violation)


# R3 PRICE DRIFT
def test_r3_price_matches():
    p = _proposal([{"sku": "SKU-1", "qty": 1, "price_paise": 10000}])
    assert rule_r3_price_drift(p, CATALOG) is None


def test_r3_price_drifted():
    p = _proposal([{"sku": "SKU-1", "qty": 1, "price_paise": 9999}])
    result = rule_r3_price_drift(p, CATALOG)
    assert isinstance(result, Violation)
    assert result.rule_id == "R3_PRICE_DRIFT"


# R5 SCOPE
def test_r5_in_scope():
    p = _proposal([{"sku": "SKU-1", "qty": 1, "price_paise": 10000}])
    assert rule_r5_scope(p, CATALOG, _mission(allowed=["electronics"])) is None


def test_r5_out_of_scope():
    p = _proposal([{"sku": "SKU-2", "qty": 1, "price_paise": 5000}])
    result = rule_r5_scope(p, CATALOG, _mission(allowed=["electronics"]))
    assert isinstance(result, Violation)
    assert result.rule_id == "R5_SCOPE"


# R11 NEGOTIATION BOUNDS
def test_r11_within_bounds():
    p = _proposal([{"sku": "SKU-1", "qty": 1, "price_paise": 10000}])
    assert rule_r11_negotiation_bound(p, CATALOG, _mission()) is None


def test_r11_below_floor():
    p = _proposal([{"sku": "SKU-1", "qty": 1, "price_paise": 7000}])
    result = rule_r11_negotiation_bound(p, CATALOG, _mission())
    assert isinstance(result, Violation)
    assert result.rule_id == "R11_NEGOTIATION_BOUND"


def test_r11_missing_bounds_fail_closed():
    catalog_no_bounds = {"SKU-X": {"price_paise": 500, "category": "misc"}}
    p = _proposal([{"sku": "SKU-X", "qty": 1, "price_paise": 500}])
    result = rule_r11_negotiation_bound(p, catalog_no_bounds, _mission())
    assert isinstance(result, Violation), "Missing bounds must fail-closed"


# R12 PROTOCOL SCOPE
def test_r12_none_scope_passes():
    p = _proposal([{"sku": "SKU-1", "qty": 1, "price_paise": 10000}])
    result = rule_r12_protocol_scope(p, CATALOG, None, merchant_id="m1", now_ts=int(time.time()))
    assert result is None


def test_r12_expired_session():
    now = int(time.time())
    p = _proposal([{"sku": "SKU-1", "qty": 1, "price_paise": 10000}])
    scope = {"valid_until": now - 100}
    result = rule_r12_protocol_scope(p, CATALOG, scope, merchant_id="m1", now_ts=now)
    assert isinstance(result, Violation)
    assert result.rule_id == "R12_PROTOCOL_SCOPE"
