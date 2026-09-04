"""Who wins, decided by arithmetic.

PURE. No randomness, no clock, no network, no model. The same offers and
the same weights produce the same winner on every machine, forever, which
is what makes the judge's override button meaningful: changing the
weights and re-running is a controlled experiment, not a re-roll.

The LLM never picks the winner. It writes the merchants' offers and it
reads the shopper's priorities into weights, and then it is done. A
scorer a model could lean on would put the model back in the money path
through the side door.

HOW A SCORE IS BUILT
--------------------
Four dimensions, each normalised to 0-1000 against the field actually on
the table, then combined by the mission's weights. Normalising against
the field rather than against an absolute means the score answers the
only question that matters here — "which of these is best for this
shopper" — instead of an unanswerable one about deals in general.

Integer arithmetic throughout, so there is no float ordering to argue
with when two offers are close.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Any

SCALE = 1000


@dataclass(frozen=True)
class OfferFacts:
    """Everything the scorer is allowed to look at."""

    merchant_id: str
    offer_id: str
    total_paise: int
    delivery_days: int
    warranty_years: int
    line_count: int


@dataclass(frozen=True)
class ScoredOffer:
    merchant_id: str
    offer_id: str
    score: int                       # 0-1000, higher is better
    components: dict[str, int]       # per-dimension, before weighting
    contributions: dict[str, int]    # per-dimension, after weighting

    def public(self) -> dict[str, Any]:
        return {
            "merchant_id": self.merchant_id,
            "offer_id": self.offer_id,
            "score": self.score,
            "score_display": f"{self.score / 10:.1f}",
            "components": self.components,
            "contributions": self.contributions,
        }


def _normalise(value: int, best: int, worst: int, *, lower_is_better: bool) -> int:
    """Map a value onto 0-1000 against the field. Ties score full marks."""
    if best == worst:
        return SCALE
    if lower_is_better:
        return (worst - value) * SCALE // (worst - best)
    return (value - worst) * SCALE // (best - worst)


def score_offers(facts: list[OfferFacts],
                 weights: dict[str, int]) -> list[ScoredOffer]:
    """Rank the field. Deterministic, and stable under equal scores.

    Ties break on merchant_id so the ordering cannot depend on the order
    the merchants happened to answer in — which, with concurrent calls, is
    different on every run.
    """
    if not facts:
        return []

    totals = [f.total_paise for f in facts]
    deliveries = [f.delivery_days for f in facts]
    warranties = [f.warranty_years for f in facts]
    lines = [f.line_count for f in facts]

    w = {k: int(weights.get(k, 0)) for k in
         ("price", "delivery", "warranty", "completeness")}
    w_total = sum(w.values()) or 1

    scored: list[ScoredOffer] = []
    for f in facts:
        components = {
            "price": _normalise(f.total_paise, min(totals), max(totals),
                                lower_is_better=True),
            "delivery": _normalise(f.delivery_days, min(deliveries),
                                   max(deliveries), lower_is_better=True),
            "warranty": _normalise(f.warranty_years, max(warranties),
                                   min(warranties), lower_is_better=False),
            "completeness": _normalise(f.line_count, max(lines), min(lines),
                                       lower_is_better=False),
        }
        contributions = {k: components[k] * w[k] // w_total for k in components}
        scored.append(ScoredOffer(
            merchant_id=f.merchant_id, offer_id=f.offer_id,
            score=sum(contributions.values()),
            components=components, contributions=contributions))

    scored.sort(key=lambda s: (-s.score, s.merchant_id))
    return scored


def winner(facts: list[OfferFacts],
           weights: dict[str, int]) -> ScoredOffer | None:
    ranked = score_offers(facts, weights)
    return ranked[0] if ranked else None
