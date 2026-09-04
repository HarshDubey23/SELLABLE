"""MerchantPolicyEngine — the only thing that turns an intent into money.

PURE, in the same sense the gateway is pure: no LLM, no network, no file
I/O, no database, no clock, no randomness. Inputs are an OfferIntent, a
signed CapabilityManifest and the server-side catalog; the output is a
verdict and, when accepted, an exact integer total. Same inputs, same
answer, forever. `tests/invariants/test_market_isolation.py` proves the
purity by parsing this module rather than by trusting this paragraph.

IT DOES NOT CLAMP
-----------------
This is the design decision worth arguing about. When a merchant offers
15% against an 8% cap, the tempting behaviour is to quietly clamp to 8%
and carry on — the customer gets a legal price, nothing breaks, the demo
looks smooth.

It is the wrong behaviour, for a reason that has nothing to do with
tidiness. Clamping means the system's observable output is identical
whether the merchant is behaving or misbehaving, so nobody ever finds out
that a merchant agent is systematically proposing things it is not
allowed to propose. The misbehaviour becomes invisible at exactly the
moment it becomes routine. Refusing is louder, and loud is what you want
from the component whose whole job is refusing.

So an out-of-policy intent is REJECTED with a machine-readable reason and
an audit event. No total is computed. Nothing is salvaged.

ARITHMETIC IS INTEGER
---------------------
Every figure is paise as an int, and every percentage is applied with
floor division. No floats touch a payable amount, so the total is
byte-identical on every machine and cannot drift into the gateway's
price-drift refusal through rounding alone.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING, Any

from .intents import OfferIntent

if TYPE_CHECKING:  # pragma: no cover - types only, never imported at runtime
    # Type-only. Importing merchants at runtime would pull the SQLite layer
    # into this module's import graph, and "pure" would stop being exactly
    # true. The manifest arrives as an argument; the engine never fetches one.
    from .merchants import CapabilityManifest

# Machine-readable refusal reasons. These strings are contract: they show
# up in the API, in the audit chain and in the UI, and tests assert on
# them by name.
MANIFEST_SIGNATURE_INVALID = "MERCHANT_POLICY_MANIFEST_SIGNATURE_INVALID"
MERCHANT_MISMATCH = "MERCHANT_POLICY_MERCHANT_MISMATCH"
EMPTY_BASKET = "MERCHANT_POLICY_EMPTY_BASKET"
UNKNOWN_SKU = "MERCHANT_POLICY_UNKNOWN_SKU"
SKU_NOT_ELIGIBLE = "MERCHANT_POLICY_SKU_NOT_ELIGIBLE"
ADDON_NOT_ELIGIBLE = "MERCHANT_POLICY_ADDON_NOT_ELIGIBLE"
LINE_DISCOUNT_EXCEEDED = "MERCHANT_POLICY_LINE_DISCOUNT_EXCEEDED"
BUNDLE_DISCOUNT_EXCEEDED = "MERCHANT_POLICY_BUNDLE_DISCOUNT_EXCEEDED"
BUNDLE_NOT_EARNED = "MERCHANT_POLICY_BUNDLE_NOT_EARNED"
FREE_SHIPPING_NOT_EARNED = "MERCHANT_POLICY_FREE_SHIPPING_NOT_EARNED"
DELIVERY_TOO_FAST = "MERCHANT_POLICY_DELIVERY_TOO_FAST"
DELIVERY_TOO_SLOW = "MERCHANT_POLICY_DELIVERY_TOO_SLOW"
WARRANTY_NOT_OFFERED = "MERCHANT_POLICY_WARRANTY_NOT_OFFERED"
MARGIN_VIOLATION = "MERCHANT_POLICY_MARGIN_VIOLATION"

ACCEPTED = "ACCEPTED"
REJECTED = "REJECTED"

_HUMAN = {
    MANIFEST_SIGNATURE_INVALID: "the merchant's capability manifest is not "
                                "correctly signed, so none of its limits can "
                                "be trusted",
    MERCHANT_MISMATCH: "the offer claims a different merchant than the "
                       "manifest it was evaluated against",
    EMPTY_BASKET: "an offer must contain at least one item",
    UNKNOWN_SKU: "the offer references a SKU that is not in the catalog",
    SKU_NOT_ELIGIBLE: "the merchant does not stock that category",
    ADDON_NOT_ELIGIBLE: "the merchant does not stock that add-on's category",
    LINE_DISCOUNT_EXCEEDED: "the per-line discount is larger than this "
                            "merchant's manifest permits",
    BUNDLE_DISCOUNT_EXCEEDED: "the bundle discount is larger than this "
                              "merchant's manifest permits",
    BUNDLE_NOT_EARNED: "a bundle discount was applied to a basket with too "
                       "few lines to qualify",
    FREE_SHIPPING_NOT_EARNED: "free shipping was offered below this "
                              "merchant's threshold",
    DELIVERY_TOO_FAST: "the merchant promised faster than its manifest says "
                       "it can ship",
    DELIVERY_TOO_SLOW: "the promised delivery is outside the merchant's "
                       "stated range",
    WARRANTY_NOT_OFFERED: "the merchant does not sell a warranty of that "
                          "length",
    MARGIN_VIOLATION: "the offer would trade below the merchant's stated "
                      "minimum margin",
}


@dataclass(frozen=True)
class LineItem:
    sku: str
    name: str
    category: str
    list_paise: int
    discounted_paise: int


@dataclass(frozen=True)
class PolicyVerdict:
    """Accepted with an exact total, or rejected with a reason. Never both."""

    decision: str                       # ACCEPTED | REJECTED
    merchant_id: str
    offer_id: str
    reason: str | None = None           # machine-readable, on rejection
    reason_human: str | None = None
    # Populated only on acceptance. There is deliberately no partial total
    # on a rejection — a refused offer has no price.
    total_paise: int | None = None
    subtotal_paise: int | None = None
    line_discount_paise: int = 0
    bundle_discount_paise: int = 0
    shipping_paise: int = 0
    warranty_paise: int = 0
    margin_pct: int | None = None
    delivery_days: int | None = None
    lines: tuple[LineItem, ...] = ()
    breach: dict[str, Any] | None = None   # what was asked vs what is allowed

    @property
    def accepted(self) -> bool:
        return self.decision == ACCEPTED

    def public(self) -> dict[str, Any]:
        d: dict[str, Any] = {
            "decision": self.decision,
            "merchant_id": self.merchant_id,
            "offer_id": self.offer_id,
        }
        if self.accepted:
            d.update({
                "total_paise": self.total_paise,
                "total_display": f"Rs {(self.total_paise or 0) / 100:,.2f}",
                "subtotal_paise": self.subtotal_paise,
                "line_discount_paise": self.line_discount_paise,
                "bundle_discount_paise": self.bundle_discount_paise,
                "shipping_paise": self.shipping_paise,
                "warranty_paise": self.warranty_paise,
                "margin_pct": self.margin_pct,
                "delivery_days": self.delivery_days,
                "lines": [
                    {"sku": ln.sku, "name": ln.name, "category": ln.category,
                     "list_paise": ln.list_paise,
                     "price_paise": ln.discounted_paise}
                    for ln in self.lines],
                "priced_by": "server-side catalog recomputation",
            })
        else:
            d.update({
                "reason": self.reason,
                "reason_human": self.reason_human,
                "breach": self.breach,
                "total_paise": None,
                "note": "a refused offer has no price; nothing was clamped",
            })
        return d


def _reject(intent: OfferIntent, reason: str,
            breach: dict[str, Any] | None = None) -> PolicyVerdict:
    return PolicyVerdict(
        decision=REJECTED, merchant_id=intent.merchant_id,
        offer_id=intent.offer_id, reason=reason,
        reason_human=_HUMAN.get(reason, reason), breach=breach)


def evaluate(*, intent: OfferIntent, manifest: CapabilityManifest,
             catalog: dict[str, Any]) -> PolicyVerdict:
    """The whole decision. Pure; the only source of a payable amount."""

    # 0. The limits themselves must be trustworthy before they can bind.
    if not manifest.signature_valid():
        return _reject(intent, MANIFEST_SIGNATURE_INVALID,
                       {"merchant_id": manifest.merchant_id,
                        "manifest_version": manifest.version})

    if intent.merchant_id != manifest.merchant_id:
        return _reject(intent, MERCHANT_MISMATCH,
                       {"offer_claims": intent.merchant_id,
                        "manifest_is": manifest.merchant_id})

    if not intent.basket_sku_set:
        return _reject(intent, EMPTY_BASKET)

    # 1. Every SKU must exist and be something this merchant stocks.
    eligible = set(manifest.eligible_categories)
    for sku in intent.basket_sku_set:
        item = catalog.get(sku)
        if item is None:
            return _reject(intent, UNKNOWN_SKU, {"sku": sku})
        if item["category"] not in eligible:
            return _reject(intent, SKU_NOT_ELIGIBLE,
                           {"sku": sku, "category": item["category"],
                            "merchant_stocks": sorted(eligible)})
    for sku in intent.addon_skus:
        item = catalog.get(sku)
        if item is None:
            return _reject(intent, UNKNOWN_SKU, {"addon_sku": sku})
        if item["category"] not in eligible:
            return _reject(intent, ADDON_NOT_ELIGIBLE,
                           {"addon_sku": sku, "category": item["category"]})

    # 2. Discounts. This is the check the demo is built around.
    if intent.line_discount_pct > manifest.max_line_discount_pct:
        return _reject(intent, LINE_DISCOUNT_EXCEEDED,
                       {"offered_pct": intent.line_discount_pct,
                        "manifest_cap_pct": manifest.max_line_discount_pct,
                        "excess_pct": intent.line_discount_pct
                                      - manifest.max_line_discount_pct})
    if intent.bundle_discount_pct > manifest.max_bundle_discount_pct:
        return _reject(intent, BUNDLE_DISCOUNT_EXCEEDED,
                       {"offered_pct": intent.bundle_discount_pct,
                        "manifest_cap_pct": manifest.max_bundle_discount_pct,
                        "excess_pct": intent.bundle_discount_pct
                                      - manifest.max_bundle_discount_pct})

    all_skus = tuple(intent.basket_sku_set) + tuple(intent.addon_skus)
    if (intent.bundle_discount_pct > 0
            and len(all_skus) < manifest.bundle_min_items):
        return _reject(intent, BUNDLE_NOT_EARNED,
                       {"lines": len(all_skus),
                        "lines_required": manifest.bundle_min_items})

    # 3. Delivery must be inside what the merchant says it can do.
    if intent.delivery_days < manifest.min_delivery_days:
        return _reject(intent, DELIVERY_TOO_FAST,
                       {"promised_days": intent.delivery_days,
                        "fastest_possible_days": manifest.min_delivery_days})
    if intent.delivery_days > manifest.max_delivery_days:
        return _reject(intent, DELIVERY_TOO_SLOW,
                       {"promised_days": intent.delivery_days,
                        "slowest_offered_days": manifest.max_delivery_days})

    # 4. Warranty must be one the merchant actually sells.
    if intent.warranty_years not in manifest.allowed_warranty_years:
        return _reject(intent, WARRANTY_NOT_OFFERED,
                       {"offered_years": intent.warranty_years,
                        "merchant_offers": list(manifest.allowed_warranty_years)})

    # 5. Arithmetic. Integers throughout; floor division on every percentage.
    lines: list[LineItem] = []
    subtotal = 0
    line_discount_total = 0
    for sku in all_skus:
        item = catalog[sku]
        list_paise = int(item["price_paise"])
        cut = list_paise * intent.line_discount_pct // 100
        lines.append(LineItem(sku=sku, name=item["name"],
                              category=item["category"],
                              list_paise=list_paise,
                              discounted_paise=list_paise - cut))
        subtotal += list_paise
        line_discount_total += cut

    after_line = subtotal - line_discount_total
    bundle_cut = after_line * intent.bundle_discount_pct // 100
    goods = after_line - bundle_cut

    # 6. Free shipping has to be earned, measured on the goods total.
    if intent.shipping == "FREE":
        if goods < manifest.free_ship_threshold_paise:
            return _reject(intent, FREE_SHIPPING_NOT_EARNED,
                           {"goods_paise": goods,
                            "threshold_paise": manifest.free_ship_threshold_paise,
                            "short_by_paise":
                                manifest.free_ship_threshold_paise - goods})
        shipping = 0
    else:
        shipping = manifest.standard_ship_paise

    warranty = (intent.warranty_years
                * manifest.warranty_price_per_year_paise
                * len(intent.basket_sku_set))

    total = goods + shipping + warranty

    # 7. Margin, on the goods only — shipping and warranty are pass-through.
    cost = subtotal * manifest.cost_basis_pct // 100
    if goods <= 0:
        return _reject(intent, MARGIN_VIOLATION,
                       {"goods_paise": goods, "cost_paise": cost})
    margin_pct = (goods - cost) * 100 // goods
    if margin_pct < manifest.min_margin_pct:
        return _reject(intent, MARGIN_VIOLATION,
                       {"resulting_margin_pct": margin_pct,
                        "manifest_floor_pct": manifest.min_margin_pct,
                        "goods_paise": goods, "cost_paise": cost})

    return PolicyVerdict(
        decision=ACCEPTED, merchant_id=intent.merchant_id,
        offer_id=intent.offer_id,
        total_paise=total, subtotal_paise=subtotal,
        line_discount_paise=line_discount_total,
        bundle_discount_paise=bundle_cut,
        shipping_paise=shipping, warranty_paise=warranty,
        margin_pct=margin_pct, delivery_days=intent.delivery_days,
        lines=tuple(lines))
