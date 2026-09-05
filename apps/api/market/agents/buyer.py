"""The buyer's planner: a sentence in, a basket and some weights out.

This is where the LLM earns its place. "A complete cricket setup under
₹6,000, I play every weekend" has to become a set of catalog SKUs, a
budget, and a sense of what this shopper actually cares about — and that
is a language problem, which is the one thing a model is genuinely better
at than a rule.

WHAT IT MAY DECIDE
------------------
Which SKUs to ask about, what the budget ceiling is, and how to weight
price against speed against warranty. All three are advisory: the SKUs
are checked against the catalog, the ceiling becomes a signed mission
bound the gateway enforces, and the weights feed a pure scorer.

WHAT IT MAY NOT DECIDE
----------------------
What anything costs. The planner never sees a discount, never proposes a
total, and its output has no field for one. It is choosing what to shop
for, not what to pay.

THE FALLBACK IS KEYWORD MATCHING
--------------------------------
Without a key, the mission is matched against catalog names, categories
and descriptions. It is worse than the model at "something for weekend
cricket" and fine at "cricket bat", and the transcript says which one
ran. A keyless reviewer gets a working market, not a broken one.
"""
from __future__ import annotations

import re
from typing import Any

from pydantic import BaseModel, Field

from . import llm as llm_mod

# What the buyer weights, and what they must sum to. Fixed so the scorer
# stays comparable across missions and across an override re-run.
WEIGHT_KEYS = ("price", "delivery", "warranty", "completeness")
WEIGHT_TOTAL = 100

DEFAULT_WEIGHTS = {"price": 45, "delivery": 25, "warranty": 15,
                   "completeness": 15}
CHEAPEST_WEIGHTS = {"price": 85, "delivery": 5, "warranty": 5,
                    "completeness": 5}


class MissionPlan(BaseModel):
    """The planner's structured reading of a shopper's sentence."""

    model_config = {"extra": "forbid"}

    skus: list[str] = Field(min_length=1, max_length=12)
    budget_paise: int = Field(gt=0, le=10**9)
    weights: dict[str, int]
    reading: str = Field(default="", max_length=300)

    def normalised_weights(self) -> dict[str, int]:
        w = {k: max(0, int(self.weights.get(k, 0))) for k in WEIGHT_KEYS}
        total = sum(w.values())
        if total <= 0:
            return dict(DEFAULT_WEIGHTS)
        # Largest-remainder, so the weights always sum to exactly 100 and
        # do so identically on every machine.
        scaled = {k: v * WEIGHT_TOTAL // total for k, v in w.items()}
        short = WEIGHT_TOTAL - sum(scaled.values())
        for k in sorted(w, key=lambda k: (-(w[k] * WEIGHT_TOTAL % total), k)):
            if short <= 0:
                break
            scaled[k] += 1
            short -= 1
        return scaled


_SYSTEM = """You turn a shopper's sentence into a shopping list.

You are given a catalog. Choose ONLY SKUs from it. Never invent a product \
and never invent a price - you are choosing what to shop for, not what to \
pay. If the catalog cannot serve the request, choose the closest genuinely \
relevant items and say so plainly in your reading.

Also read what this shopper cares about, as four weights summing to 100:
  price         - how much cheapness matters
  delivery      - how much speed matters
  warranty      - how much cover matters
  completeness  - how much having everything in one basket matters

Reply with ONE JSON object and nothing else:
{"skus": ["SKU-1", "SKU-2"], "budget_paise": 600000, \
"weights": {"price": 45, "delivery": 25, "warranty": 15, \
"completeness": 15}, "reading": "one sentence on what they want"}

budget_paise is in paise: Rs 6,000 is 600000."""

_BUDGET_RE = re.compile(
    r"(?:under|below|within|budget(?:\s+of)?|max(?:imum)?|upto|up\s*to)\s*"
    r"(?:rs\.?|inr|₹)?\s*([\d,]+(?:\.\d+)?)\s*(k|lakh|lac|l)?",
    re.IGNORECASE)
_BARE_AMOUNT_RE = re.compile(r"(?:rs\.?|inr|₹)\s*([\d,]+)\s*(k|lakh|lac|l)?",
                             re.IGNORECASE)


def parse_budget_paise(text: str, default_paise: int = 600000) -> int:
    """Read a ceiling out of the sentence. Untrusted; only ever a bound."""
    for rx in (_BUDGET_RE, _BARE_AMOUNT_RE):
        m = rx.search(text or "")
        if not m:
            continue
        try:
            amount = float(m.group(1).replace(",", ""))
        except ValueError:
            continue
        suffix = (m.group(2) or "").lower()
        if suffix == "k":
            amount *= 1_000
        elif suffix in ("lakh", "lac", "l"):
            amount *= 100_000
        if amount > 0:
            return int(round(amount)) * 100
    return default_paise


# Words that qualify an occasion rather than name a product type. They
# legitimately appear in product names ("Travel Yoga Mat", "Pro Grip"),
# which is why they must not be able to carry a match on their own.
_CONTEXT_WORDS = {
    "travel", "gift", "daily", "everyday", "portable", "premium", "pro",
    "professional", "basic", "classic", "compact", "light", "lite",
    "starter", "essential", "essentials", "ultimate", "advanced", "elite",
}

_STOP = {"a", "an", "the", "and", "or", "for", "with", "under", "below",
         "within", "budget", "rs", "inr", "me", "my", "i", "want", "need",
         "buy", "get", "best", "good", "complete", "set", "setup", "kit",
         "some", "of", "to", "up", "max", "maximum", "please", "looking",
         "something", "every", "weekend", "play", "use", "using", "new"}


def keyword_plan(mission_text: str, catalog: dict[str, Any],
                 max_items: int = 5) -> MissionPlan | None:
    """The deterministic fallback. Scores catalog entries by word overlap.

    Returns None when nothing in the catalog matches, rather than an
    arbitrary item dressed up as an answer.
    """
    text = (mission_text or "").lower()
    words = {w for w in re.findall(r"[a-z]+", text) if w not in _STOP
             and len(w) > 2}

    budget = parse_budget_paise(mission_text)

    scored: list[tuple[int, int, str]] = []
    for sku, item in catalog.items():
        # WHAT A THING IS vs WHAT IS SAID ABOUT IT.
        #
        # Only the name and the category can qualify an item. Asked for
        # "camera and lens for travel", matching anywhere in the text
        # returned a 65W charger, because its description says "compact
        # travel size" -- a real catalog row, honestly labelled, and
        # completely wrong. Three merchants then bid on a charger as
        # though the request had been served.
        #
        # A word in a description says something about a product. The
        # name and category say what it *is*, and only that can make it
        # an answer. Description and attributes still count, but only to
        # order items that already qualified.
        # The product family names what the thing IS, which is a stronger
        # signal than either the name or the category.
        family = str((item.get("attributes") or {}).get("family", "")).lower()
        identity = " ".join([
            str(item.get("name", "")),
            str(item.get("category", "")).replace("_", " "),
            family,
        ]).lower()
        blurb = " ".join([
            str(item.get("description", "")),
            " ".join(str(v) for v in (item.get("attributes") or {}).values()),
        ]).lower()

        # CONTEXT WORDS DESCRIBE AN OCCASION, NOT A PRODUCT.
        #
        # "Camera and lens for travel" matched a Liforme Travel Yoga Mat,
        # because "travel" is in its name. Exactly the charger-for-a-camera
        # bug wearing a different hat: a word that says when or why you
        # would use something is not a word that says what it is. Stripped
        # before matching, so they can still appear in names without
        # dragging the wrong product into an answer.
        # Whole words. "mat" must not match "basmati".
        identity_words = set(re.findall(r"[a-z]+", identity))
        blurb_words = set(re.findall(r"[a-z]+", blurb))
        meaningful = [w for w in words if w not in _CONTEXT_WORDS]
        identity_hits = sum(1 for w in meaningful if w in identity_words)
        if not identity_hits:
            continue

        # A WHOLE FAMILY WORD BEATS A WORD INSIDE ONE.
        #
        # "Best laptop for coding" put laptop STANDS above laptops, because
        # "laptop" is inside the family name "laptop stand" and a substring
        # hit scored the same as naming the thing outright. Matching whole
        # words in the family, and weighting that above everything else,
        # puts the laptop first and leaves the stand as an accessory.
        family_words = set(family.split())
        exact_family = sum(1 for w in meaningful if w in family_words)
        blurb_hits = sum(1 for w in meaningful if w in blurb_words)
        score = exact_family * 40 + identity_hits * 10 + blurb_hits
        # Cheaper first among equal matches, so a fallback basket has a
        # chance of fitting the budget.
        scored.append((-score, item["price_paise"], sku))

    scored.sort()

    # ONE BASKET SHOULD NOT BE FIVE OF THE SAME THING.
    #
    # "A complete cricket setup" returned three cricket balls and two more
    # cricket balls, because they were the cheapest things that matched and
    # nothing stopped the list filling up with one family. A setup means a
    # bat AND a ball AND pads. Families are taken round-robin, so the
    # basket spreads before it doubles up.
    by_family: dict[str, list[tuple[int, str]]] = {}
    for _score, price, sku in scored:
        fam = str((catalog[sku].get("attributes") or {}).get(
            "family", catalog[sku]["category"]))
        by_family.setdefault(fam, []).append((price, sku))

    picked: list[str] = []
    running = 0
    depth = 0
    while len(picked) < max_items and depth < 3:
        progressed = False
        for fam in list(by_family):
            if len(picked) >= max_items:
                break
            if depth >= len(by_family[fam]):
                continue
            price, sku = by_family[fam][depth]
            if running + price > budget:
                continue
            picked.append(sku)
            running += price
            progressed = True
        if not progressed:
            break
        depth += 1

    if not picked:
        # Nothing matched. Returning "the closest available item" would mean
        # handing the shopper something arbitrary and calling it a result,
        # which is the fabrication this system is supposed to refuse. So it
        # returns nothing and the caller reports that honestly.
        return None

    return MissionPlan(
        skus=picked, budget_paise=budget, weights=dict(DEFAULT_WEIGHTS),
        reading=f"matched {len(picked)} catalog item(s) by keyword")


async def plan_mission(*, mission_text: str, catalog: dict[str, Any],
                       allow_llm: bool = True
                       ) -> tuple[MissionPlan | None, dict[str, Any]]:
    """Read the mission. Returns the plan, or None if nothing matches."""
    lines = [f"  {sku}  Rs {i['price_paise'] / 100:,.0f}  {i['name']} "
             f"[{i['category']}]"
             for sku, i in catalog.items()]
    user = (f"Shopper said: {mission_text}\n\nCatalog:\n"
            + "\n".join(lines))

    result = llm_mod.LLMResult(ok=False, mode=llm_mod.LLM_DISABLED,
                               error="llm not attempted")
    if allow_llm:
        result = await llm_mod.ask_model(system=_SYSTEM, user=user,
                                         schema=MissionPlan)

    budget_override = None
    plan: MissionPlan | None
    if result.ok:
        plan = result.parsed
        # Every SKU is checked against the catalog. A hallucinated product
        # is dropped here, not discovered later at the payment boundary.
        real = [s for s in plan.skus if s in catalog]
        dropped = [s for s in plan.skus if s not in catalog]

        # THE CEILING IS NOT THE MODEL'S TO SET.
        #
        # Asked for "a gaming PC under 80000", gpt-4o-mini returned
        # budget_paise=80000 - which is Rs 800, not Rs 80,000. A hundredfold
        # error in a number that bounds spending, from a model that had the
        # unit spelled out for it in the prompt.
        #
        # So when the sentence contains an amount, the deterministic parse
        # wins and the model's figure is discarded. The model reads intent;
        # the regex reads the number. Neither does the other's job.
        parsed_budget = parse_budget_paise(mission_text, default_paise=-1)
        if parsed_budget > 0 and parsed_budget != plan.budget_paise:
            budget_override = {"model_said_paise": plan.budget_paise,
                               "text_says_paise": parsed_budget}
        effective_budget = parsed_budget if parsed_budget > 0 else plan.budget_paise

        if real:
            plan = MissionPlan(skus=real, budget_paise=effective_budget,
                               weights=plan.weights, reading=plan.reading)
            source = llm_mod.LLM_OK
        else:
            plan = keyword_plan(mission_text, catalog)
            source = llm_mod.LLM_MALFORMED
            dropped = dropped or ["all proposed SKUs"]
    else:
        plan = keyword_plan(mission_text, catalog)
        source = result.mode
        dropped = []

    provenance = {
        "source": source,
        "label": ("LLM planner" if source == llm_mod.LLM_OK
                  else "keyword fallback planner"),
        "is_llm": source == llm_mod.LLM_OK,
        "model": result.model,
        "latency_ms": result.latency_ms,
        "error": result.error,
        "dropped_unknown_skus": dropped,
        # Recorded, not hidden: a reviewer should be able to see that the
        # model's ceiling was overruled and by how much.
        "budget_overridden": budget_override,
    }
    return plan, provenance
