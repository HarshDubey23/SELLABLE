"""A merchant agent. Sees its own business, and nothing of its rivals.

WHAT IT IS GIVEN
----------------
Its identity, its commercial strategy, its own signed manifest, the
basket the buyer asked about, the mission's requirements, the round
number, and any targeted request the buyer sent *to it*. That is the
whole context.

WHAT IT IS NEVER GIVEN
----------------------
Another merchant's offer, price, discount, delivery or margin. Whether it
is winning. How many rivals there are. Any payment, approval or gateway
internals. Isolation is a property of what `build_prompt` puts in the
string, so it is asserted directly in tests rather than argued for.

WHY THE FALLBACK IS A REAL STRATEGY
-----------------------------------
When the provider is down, this agent still negotiates — from the same
manifest, using a deterministic policy shaped by the same commercial
posture. NovaTech still protects margin and competes on speed; GearHub
still buys share with discount. The negotiation stays interesting and,
more importantly, stays *honest*: the transcript records that the offer
came from the scripted strategy, and every surface says so.

The fallback is not a stub that returns a fixed offer. If it were, a
reviewer running keyless would see three identical merchants and learn
nothing about whether the market works.
"""
from __future__ import annotations

import hashlib
from typing import Any

from pydantic import BaseModel, Field

from ..intents import BuyerCounter, OfferIntent
from ..merchants import CapabilityManifest
from . import llm as llm_mod


class _ModelOffer(BaseModel):
    """Exactly what the model is allowed to decide.

    Note what is missing, again: no merchant_id (it does not get to claim
    to be someone else), no offer_id (the server assigns it), no round
    (the server knows it), and above all no amount.
    """

    model_config = {"extra": "forbid"}

    basket_sku_set: list[str] = Field(min_length=1, max_length=24)
    line_discount_pct: int = Field(ge=0, le=100)
    bundle_discount_pct: int = Field(ge=0, le=100)
    shipping: str
    delivery_days: int = Field(ge=0, le=90)
    addon_skus: list[str] = Field(default_factory=list, max_length=12)
    warranty_years: int = Field(ge=0, le=10)
    rationale: str = Field(default="", max_length=400)


_SYSTEM = """You are {display_name}, a merchant competing for one order.

Your commercial strategy: {strategy_brief}

You are bidding against other merchants, but you cannot see them. You do \
not know their prices, their terms, or whether you are ahead. Bid your \
own book.

YOUR LIMITS. These are enforced by a deterministic policy engine that \
sits between you and the customer. An offer outside them is REFUSED \
outright - not reduced to fit - and you lose the round:
  - per-line discount: at most {max_line}%
  - bundle discount: at most {max_bundle}%, and only on {bundle_min}+ items
  - free shipping: only when the goods total is at least Rs {free_ship:,.0f}
  - delivery: between {min_days} and {max_days} days
  - warranty: only {warranties} year(s)
  - you must keep at least {min_margin}% margin; your goods cost you \
about {cost_basis}% of list, so deep discounts breach this before they \
breach the discount cap

You CANNOT state a price. There is no field for one. You choose \
percentages and terms; the server computes what that costs.

Reply with ONE JSON object and nothing else:
{{"basket_sku_set": ["SKU-1"], "line_discount_pct": 0, \
"bundle_discount_pct": 0, "shipping": "FREE" or "STANDARD", \
"delivery_days": 0, "addon_skus": [], "warranty_years": 0, \
"rationale": "one sentence for the buyer"}}"""


def build_prompt(*, manifest: CapabilityManifest, basket: list[dict[str, Any]],
                 mission_text: str, round_no: int,
                 counter: BuyerCounter | None,
                 previous: OfferIntent | None = None) -> tuple[str, str]:
    """Assemble this merchant's view. Nothing about a rival can enter here.

    `previous` is this merchant's OWN last offer and nobody else's, which
    is what makes including it compatible with the isolation rule. It is
    also what makes a counter mean anything: asking a merchant to
    "improve" while showing it no offer to improve on produced a round
    two uncorrelated with round one -- GEARHUB, asked for faster
    delivery, came back with 4 days changed to 7. It was not ignoring the
    request; it had never been told what it had already said.
    """
    system = _SYSTEM.format(
        display_name=manifest.display_name,
        strategy_brief=manifest.strategy_brief,
        max_line=manifest.max_line_discount_pct,
        max_bundle=manifest.max_bundle_discount_pct,
        bundle_min=manifest.bundle_min_items,
        free_ship=manifest.free_ship_threshold_paise / 100,
        min_days=manifest.min_delivery_days,
        max_days=manifest.max_delivery_days,
        warranties=", ".join(str(w) for w in manifest.allowed_warranty_years),
        min_margin=manifest.min_margin_pct,
        cost_basis=manifest.cost_basis_pct,
    )

    lines = [f"  {i['sku']}  Rs {i['price_paise'] / 100:,.0f}  {i['name']}"
             for i in basket]
    parts = [
        f"The customer asked for: {mission_text}",
        "",
        "Items available to you for this order:",
        *lines,
        "",
        f"Round {round_no}.",
    ]
    if previous is not None:
        parts += [
            "",
            "What you offered last round:",
            f"  line discount {previous.line_discount_pct}%",
            f"  bundle discount {previous.bundle_discount_pct}%",
            f"  shipping {previous.shipping}",
            f"  delivery {previous.delivery_days} day(s)",
            f"  warranty {previous.warranty_years} year(s)",
        ]

    if counter is not None:
        # The ask is a named dimension. There is no way to pass along what
        # a competitor offered, because BuyerCounter has no field for it.
        asks = {
            "FASTER_DELIVERY": "The buyer wants this delivered sooner.",
            "LOWER_PRICE": "The buyer wants a better price.",
            "LONGER_WARRANTY": "The buyer wants a longer warranty.",
            "FREE_SHIPPING": "The buyer wants shipping included.",
            "MORE_INCLUDED": "The buyer wants more included in the basket.",
        }
        parts += ["", f"The buyer has come back to you: {asks[counter.ask]}"]
        if counter.note:
            parts += [f"Their note: {counter.note}"]

        # Name the number to beat. "Improve your offer" is not actionable
        # on its own, and a model given only that will re-roll rather than
        # move in the requested direction.
        if previous is not None:
            targets = {
                "FASTER_DELIVERY":
                    f"Offer FEWER than {previous.delivery_days} delivery "
                    f"days, down to your minimum of "
                    f"{manifest.min_delivery_days}.",
                "LOWER_PRICE":
                    f"Offer a LARGER discount than "
                    f"{previous.line_discount_pct}% per line, up to your "
                    f"cap, while keeping your margin legal.",
                "LONGER_WARRANTY":
                    f"Offer MORE than {previous.warranty_years} warranty "
                    f"year(s), from the years you are allowed to sell.",
                "FREE_SHIPPING":
                    "Set shipping to FREE if the goods total earns it.",
                "MORE_INCLUDED":
                    "Add eligible items to the basket.",
            }
            parts += [targets[counter.ask]]
            parts += ["Keep the rest of your offer at least as good as it "
                      "was. Do not go backwards on the other terms."]
        else:
            parts += ["Improve your offer if your limits allow it."]

    return system, "\n".join(parts)


# ------------------------------------------------------------------
# The deterministic strategies. Used when the provider is unavailable,
# and shaped by the same manifest the model is given, so a keyless run
# still produces three merchants that behave differently.
# ------------------------------------------------------------------

def _headroom(manifest: CapabilityManifest) -> int:
    """The deepest line discount that still clears the margin floor.

    Solves for d in: (1-d) - cost >= min_margin * (1-d), integer and
    conservative, so the scripted strategy never proposes something its
    own manifest would refuse.
    """
    for d in range(manifest.max_line_discount_pct, -1, -1):
        remaining = 100 - d
        if remaining <= 0:
            continue
        margin = (remaining - manifest.cost_basis_pct) * 100 // remaining
        if margin >= manifest.min_margin_pct:
            return d
    return 0


def scripted_offer(*, manifest: CapabilityManifest,
                   basket: list[dict[str, Any]], round_no: int,
                   counter: BuyerCounter | None) -> _ModelOffer:
    """Each merchant's house strategy, expressed in its own levers."""
    skus = [i["sku"] for i in basket]
    goods = sum(i["price_paise"] for i in basket)
    cap = _headroom(manifest)

    if manifest.merchant_id == "NOVATECH":
        # Protects margin; competes on speed and warranty.
        line = min(cap, 3)
        delivery = manifest.min_delivery_days
        warranty = max(manifest.allowed_warranty_years)
        bundle = 0
    elif manifest.merchant_id == "GEARHUB":
        # Buys share: discounts hardest it can, ships free early, slower.
        line = cap
        delivery = manifest.min_delivery_days + 1
        warranty = min(manifest.allowed_warranty_years)
        bundle = 0
    else:  # BYTECART - clears stock by bundling
        line = min(cap, 2)
        delivery = (manifest.min_delivery_days + manifest.max_delivery_days) // 2
        warranty = 1 if 1 in manifest.allowed_warranty_years else 0
        bundle = min(manifest.max_bundle_discount_pct, 8) \
            if len(skus) >= manifest.bundle_min_items else 0

    # A counter moves exactly the dimension asked for, within the limits.
    if counter is not None:
        if counter.ask == "FASTER_DELIVERY":
            delivery = manifest.min_delivery_days
        elif counter.ask == "LOWER_PRICE":
            line = cap
        elif counter.ask == "LONGER_WARRANTY":
            warranty = max(manifest.allowed_warranty_years)
        elif counter.ask == "FREE_SHIPPING":
            pass                      # handled by the shipping choice below
        elif counter.ask == "MORE_INCLUDED" and len(skus) >= manifest.bundle_min_items:
            bundle = min(manifest.max_bundle_discount_pct, bundle + 5)

    # Re-check the stacked position against the margin floor rather than
    # hoping: the scripted strategy must never hand the policy engine
    # something it will refuse.
    while line + bundle > 0:
        remaining = (100 - line) * (100 - bundle) // 100
        if remaining <= 0:
            break
        margin = (remaining - manifest.cost_basis_pct) * 100 // remaining
        if margin >= manifest.min_margin_pct:
            break
        if bundle > 0:
            bundle -= 1
        else:
            line -= 1

    after = goods * (100 - line) // 100
    after = after * (100 - bundle) // 100
    shipping = "FREE" if after >= manifest.free_ship_threshold_paise else "STANDARD"

    rationale = {
        "NOVATECH": f"Fastest delivery we offer at {delivery} days, with "
                    f"{warranty}-year cover included.",
        "GEARHUB": f"Best discount we can do at {line}% off every line.",
        "BYTECART": f"Bundled {bundle}% off the basket to move this stock.",
    }.get(manifest.merchant_id, "Our best offer for this basket.")

    return _ModelOffer(
        basket_sku_set=skus, line_discount_pct=line,
        bundle_discount_pct=bundle, shipping=shipping,
        delivery_days=delivery, addon_skus=[], warranty_years=warranty,
        rationale=rationale)


def _offer_id(negotiation_id: str, merchant_id: str, round_no: int) -> str:
    """Deterministic, and unique per merchant per round.

    Deterministic matters: a replayed round produces the same id, and the
    UNIQUE constraint on it is what refuses the replay.
    """
    raw = f"{negotiation_id}|{merchant_id}|{round_no}"
    return "off_" + hashlib.sha256(raw.encode()).hexdigest()[:24]


async def make_offer(*, negotiation_id: str, manifest: CapabilityManifest,
                     basket: list[dict[str, Any]], mission_text: str,
                     round_no: int, counter: BuyerCounter | None = None,
                     previous: OfferIntent | None = None,
                     allow_llm: bool = True
                     ) -> tuple[OfferIntent, dict[str, Any]]:
    """One merchant's offer for one round, plus how it was produced.

    Returns the intent and a provenance record. The provenance is not
    decoration: it is what lets every surface say "LLM merchant" or
    "scripted fallback" truthfully, and it goes into the transcript.
    """
    system, user = build_prompt(manifest=manifest, basket=basket,
                                mission_text=mission_text, round_no=round_no,
                                counter=counter, previous=previous)

    result = llm_mod.LLMResult(ok=False, mode=llm_mod.LLM_DISABLED,
                               error="llm not attempted")
    if allow_llm:
        def _coerce(obj: dict[str, Any]) -> dict[str, Any]:
            # The model does not get to set these, so they are stripped
            # before validation rather than trusted.
            for owned in ("merchant_id", "offer_id", "round", "in_reply_to"):
                obj.pop(owned, None)
            ship = str(obj.get("shipping", "STANDARD")).upper()
            obj["shipping"] = "FREE" if ship == "FREE" else "STANDARD"
            return obj

        result = await llm_mod.ask_model(system=system, user=user,
                                         schema=_ModelOffer, coerce=_coerce)

    if result.ok:
        offer = result.parsed
        source = llm_mod.LLM_OK
    else:
        offer = scripted_offer(manifest=manifest, basket=basket,
                               round_no=round_no, counter=counter)
        source = result.mode

    intent = OfferIntent(
        merchant_id=manifest.merchant_id,
        basket_sku_set=tuple(offer.basket_sku_set),
        line_discount_pct=offer.line_discount_pct,
        bundle_discount_pct=offer.bundle_discount_pct,
        shipping="FREE" if offer.shipping == "FREE" else "STANDARD",
        delivery_days=offer.delivery_days,
        addon_skus=tuple(offer.addon_skus),
        warranty_years=offer.warranty_years,
        round=round_no,
        in_reply_to=(counter.merchant_id if counter else None),
        offer_id=_offer_id(negotiation_id, manifest.merchant_id, round_no),
        rationale=offer.rationale,
    )

    provenance = {
        "source": source,
        "label": llm_mod.mode_label(source),
        "is_llm": source == llm_mod.LLM_OK,
        "model": result.model,
        "latency_ms": result.latency_ms,
        "attempts": result.attempts,
        "error": result.error,
    }
    return intent, provenance
