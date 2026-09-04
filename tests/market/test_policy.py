"""MerchantPolicyEngine: fail-closed, deterministic, and it does not clamp.

The no-clamping tests are the ones that matter. A system that silently
corrects an illegal offer behaves identically whether its merchants are
honest or not, which means nobody ever discovers that one is not.
"""
from __future__ import annotations

import pytest

from apps.api.market import merchants, policy
from apps.api.market.intents import OfferIntent
from apps.api.products import CATALOG


@pytest.fixture(autouse=True)
def _seeded():
    merchants.seed(force=True)


def intent(merchant_id: str = "NOVATECH", **over) -> OfferIntent:
    base = dict(
        merchant_id=merchant_id,
        basket_sku_set=("BAT-001", "BALL-001", "GRIP-001"),
        line_discount_pct=5, bundle_discount_pct=0, shipping="STANDARD",
        delivery_days=3, warranty_years=0, round=1,
        offer_id=f"off-{merchant_id.lower()}-1")
    base.update(over)
    return OfferIntent(**base)


def ev(i: OfferIntent, merchant_id: str | None = None) -> policy.PolicyVerdict:
    m = merchants.get(merchant_id or i.merchant_id)
    assert m is not None
    return policy.evaluate(intent=i, manifest=m, catalog=CATALOG)


# ------------------------------------------------------------ acceptance

def test_a_legal_offer_is_priced_from_the_catalog():
    v = ev(intent())
    assert v.accepted
    assert v.total_paise is not None and v.total_paise > 0
    # Every line's list price is the catalog's, not anything the merchant said.
    for line in v.lines:
        assert line.list_paise == CATALOG[line.sku]["price_paise"]
    assert v.public()["priced_by"] == "server-side catalog recomputation"


def test_the_total_is_reproducible_to_the_paisa():
    """No floats anywhere on the payable path."""
    totals = {ev(intent()).total_paise for _ in range(200)}
    assert len(totals) == 1


def test_arithmetic_is_exactly_what_it_claims():
    """Recompute the total by hand, line and bundle discount both engaged."""
    basket = ("BAT-001", "BALL-001", "GRIP-001")
    v = ev(intent(line_discount_pct=5, bundle_discount_pct=5,
                  basket_sku_set=basket))
    assert v.accepted, v.reason

    subtotal = sum(CATALOG[s]["price_paise"] for s in basket)
    line_cut = sum(CATALOG[s]["price_paise"] * 5 // 100 for s in basket)
    after_line = subtotal - line_cut
    bundle_cut = after_line * 5 // 100
    goods = after_line - bundle_cut
    # The intent asked for STANDARD shipping, so standard shipping is
    # charged. Being ABOVE the free-shipping threshold does not make
    # shipping free — the merchant has to actually offer FREE.
    m = merchants.get("NOVATECH")

    assert v.subtotal_paise == subtotal
    assert v.line_discount_paise == line_cut
    assert v.bundle_discount_paise == bundle_cut
    assert v.shipping_paise == m.standard_ship_paise
    assert v.total_paise == goods + m.standard_ship_paise


def test_stacked_discounts_can_breach_the_margin_floor():
    """Two limits, and the tighter one binds.

    8% line is inside NovaTech's 8% cap and 10% bundle is inside its 10%
    cap, but together they leave a 13% margin against an 18% floor. The
    engine refuses on margin rather than on either cap, which is the
    behaviour a real merchant would want: caps bound each lever, margin
    bounds the deal.
    """
    v = ev(intent(line_discount_pct=8, bundle_discount_pct=10))
    assert v.reason == policy.MARGIN_VIOLATION
    assert v.breach["resulting_margin_pct"] < v.breach["manifest_floor_pct"]
    assert v.total_paise is None


# ----------------------------------------------------- NO CLAMPING

def test_an_over_cap_line_discount_is_refused_not_reduced():
    """The scene the demo is built on.

    NOVATECH's manifest caps line discount at 8%. An offer of 15% is
    refused outright: no total is computed, nothing is silently corrected
    to 8%, and the response names the gap.
    """
    m = merchants.get("NOVATECH")
    assert m.max_line_discount_pct == 8

    v = ev(intent(line_discount_pct=15))
    assert not v.accepted
    assert v.reason == policy.LINE_DISCOUNT_EXCEEDED
    assert v.total_paise is None, "a refused offer must have no price"
    assert v.breach == {"offered_pct": 15, "manifest_cap_pct": 8,
                        "excess_pct": 7}


def test_nothing_in_a_rejection_carries_a_usable_amount():
    """Belt and braces: a refusal must not leak a partial total."""
    v = ev(intent(line_discount_pct=99))
    assert not v.accepted
    pub = v.public()
    assert pub["total_paise"] is None
    for key, value in pub.items():
        if isinstance(value, int) and key.endswith("_paise"):
            pytest.fail(f"rejection exposed an amount in {key}={value}")


def test_an_over_cap_bundle_discount_is_refused():
    v = ev(intent(bundle_discount_pct=40))
    assert v.reason == policy.BUNDLE_DISCOUNT_EXCEEDED
    assert v.total_paise is None


def test_the_cap_belongs_to_the_merchant_not_to_the_number():
    """15% is illegal at NOVATECH and legal at GEARHUB, whose cap is 15%.

    GEARHUB still cannot use all of it here — its own margin floor binds
    first, which is the point of having two independent limits.
    """
    assert merchants.get("GEARHUB").max_line_discount_pct == 15

    refused = ev(intent("NOVATECH", line_discount_pct=15))
    assert refused.reason == policy.LINE_DISCOUNT_EXCEEDED

    # Not a discount-cap refusal at GEARHUB; the margin floor catches it.
    at_gearhub = ev(intent("GEARHUB", line_discount_pct=15, delivery_days=4))
    assert at_gearhub.reason != policy.LINE_DISCOUNT_EXCEEDED

    # And a discount inside both limits is accepted.
    ok = ev(intent("GEARHUB", line_discount_pct=10, delivery_days=4))
    assert ok.accepted, ok.reason


# --------------------------------------------------------- other limits

def test_margin_floor_refuses_a_trade_below_cost_plus_margin():
    v = ev(intent("GEARHUB", line_discount_pct=15, delivery_days=4))
    assert v.reason == policy.MARGIN_VIOLATION
    assert v.breach["resulting_margin_pct"] < v.breach["manifest_floor_pct"]
    assert v.total_paise is None


def test_free_shipping_must_be_earned():
    """One cheap item sits below NOVATECH's threshold."""
    m = merchants.get("NOVATECH")
    v = ev(intent(basket_sku_set=("BAT-001",), shipping="FREE"))
    assert v.reason == policy.FREE_SHIPPING_NOT_EARNED
    assert v.breach["threshold_paise"] == m.free_ship_threshold_paise
    assert v.breach["short_by_paise"] > 0


def test_free_shipping_is_allowed_once_the_threshold_is_met():
    v = ev(intent(basket_sku_set=("BAT-001", "BALL-001", "GRIP-001"),
                  shipping="FREE"))
    assert v.accepted
    assert v.shipping_paise == 0


def test_delivery_outside_the_merchants_range_is_refused():
    assert ev(intent("GEARHUB", delivery_days=1)).reason == policy.DELIVERY_TOO_FAST
    assert ev(intent("GEARHUB", delivery_days=30)).reason == policy.DELIVERY_TOO_SLOW


def test_a_warranty_the_merchant_does_not_sell_is_refused():
    v = ev(intent("GEARHUB", delivery_days=4, warranty_years=2))
    assert v.reason == policy.WARRANTY_NOT_OFFERED
    assert v.breach["merchant_offers"] == [0, 1]


def test_a_bundle_discount_needs_enough_lines():
    v = ev(intent(basket_sku_set=("BAT-001",), bundle_discount_pct=5))
    assert v.reason == policy.BUNDLE_NOT_EARNED


def test_an_unknown_sku_is_refused():
    v = ev(intent(basket_sku_set=("NOT-A-SKU",)))
    assert v.reason == policy.UNKNOWN_SKU
    assert v.breach["sku"] == "NOT-A-SKU"


def test_an_unknown_addon_is_refused():
    v = ev(intent(addon_skus=("NOT-A-SKU",)))
    assert v.reason == policy.UNKNOWN_SKU


def test_an_empty_basket_cannot_be_constructed():
    """Refused by the schema before the engine is even reached."""
    with pytest.raises(ValueError):
        intent(basket_sku_set=())


# ------------------------------------------------- trusting the limits

def test_an_unsigned_manifest_binds_nothing_and_refuses_everything():
    """If the cap itself is not trustworthy, no offer under it can be."""
    from dataclasses import replace

    tampered = replace(merchants.get("NOVATECH"), max_line_discount_pct=99)
    v = policy.evaluate(intent=intent(line_discount_pct=99),
                        manifest=tampered, catalog=CATALOG)
    assert v.reason == policy.MANIFEST_SIGNATURE_INVALID
    assert v.total_paise is None


def test_an_offer_cannot_be_evaluated_against_another_merchants_manifest():
    v = policy.evaluate(intent=intent("GEARHUB"),
                        manifest=merchants.get("NOVATECH"), catalog=CATALOG)
    assert v.reason == policy.MERCHANT_MISMATCH


def test_every_refusal_reason_has_a_human_sentence():
    """A machine-readable code nobody can read is only half a reason."""
    codes = [v for k, v in vars(policy).items()
             if k.isupper() and isinstance(v, str)
             and v.startswith("MERCHANT_POLICY_")]
    assert codes
    for code in codes:
        assert code in policy._HUMAN, f"{code} has no human explanation"
