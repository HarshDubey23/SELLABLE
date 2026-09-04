"""Why this merchant. Computed differences, never adjectives.

Every line this produces is a subtraction between two offers that are
both on the table. "₹900 above the cheapest, 2 days faster, +1 year
cover" is checkable by a reader with the offer list in front of them.

Nothing here asks a model to explain anything. A generated justification
would be fluent, plausible, and unfalsifiable — three properties that
together make it worthless as evidence, and actively harmful next to a
number that is none of those things.
"""
from __future__ import annotations

from typing import Any

from .score import OfferFacts, ScoredOffer


def _rupees(paise: int) -> str:
    return f"Rs {abs(paise) / 100:,.0f}"


def explain_winner(*, winner: ScoredOffer, ranked: list[ScoredOffer],
                   facts: dict[str, OfferFacts],
                   weights: dict[str, int]) -> dict[str, Any]:
    """The card shown next to the winning offer."""
    win_facts = facts[winner.merchant_id]
    others = [facts[s.merchant_id] for s in ranked
              if s.merchant_id != winner.merchant_id]

    reasons: list[dict[str, Any]] = []

    if others:
        cheapest = min(others + [win_facts], key=lambda f: f.total_paise)
        delta = win_facts.total_paise - cheapest.total_paise
        if delta == 0:
            reasons.append({"dimension": "price", "direction": "better",
                            "text": "cheapest offer on the table"})
        else:
            reasons.append({
                "dimension": "price", "direction": "worse",
                "text": f"{_rupees(delta)} above the cheapest "
                        f"({cheapest.merchant_id})",
                "delta_paise": delta})

        fastest = min(others + [win_facts], key=lambda f: f.delivery_days)
        slowest = max(others + [win_facts], key=lambda f: f.delivery_days)
        if win_facts.delivery_days < slowest.delivery_days:
            reasons.append({
                "dimension": "delivery", "direction": "better",
                "text": f"{slowest.delivery_days - win_facts.delivery_days} "
                        f"day(s) faster than the slowest offer",
                "delta_days": slowest.delivery_days - win_facts.delivery_days})
        elif win_facts.delivery_days > fastest.delivery_days:
            reasons.append({
                "dimension": "delivery", "direction": "worse",
                "text": f"{win_facts.delivery_days - fastest.delivery_days} "
                        f"day(s) slower than {fastest.merchant_id}",
                "delta_days": win_facts.delivery_days - fastest.delivery_days})

        best_warranty = max(f.warranty_years for f in others + [win_facts])
        if win_facts.warranty_years > 0 and win_facts.warranty_years == best_warranty:
            reasons.append({
                "dimension": "warranty", "direction": "better",
                "text": f"{win_facts.warranty_years}-year cover, the longest "
                        f"offered"})
        elif win_facts.warranty_years < best_warranty:
            reasons.append({
                "dimension": "warranty", "direction": "worse",
                "text": f"{best_warranty - win_facts.warranty_years} year(s) "
                        f"less cover than the best on offer"})

        most_lines = max(f.line_count for f in others + [win_facts])
        if win_facts.line_count == most_lines and most_lines > 1:
            reasons.append({
                "dimension": "completeness", "direction": "better",
                "text": f"{win_facts.line_count} items, the most complete "
                        f"basket"})
    else:
        reasons.append({"dimension": "field", "direction": "neutral",
                        "text": "the only offer that passed policy"})

    return {
        "merchant_id": winner.merchant_id,
        "score": winner.score,
        "score_display": f"{winner.score / 10:.1f}",
        "headline": f"{winner.merchant_id} wins on a weighted score of "
                    f"{winner.score / 10:.1f} out of 100",
        "reasons": reasons,
        "weights_used": dict(weights),
        "contributions": winner.contributions,
        "runner_up": (
            {"merchant_id": ranked[1].merchant_id,
             "score": ranked[1].score,
             "margin": winner.score - ranked[1].score}
            if len(ranked) > 1 else None),
        "basis": "every figure here is a subtraction between offers in this "
                 "round; nothing is generated",
    }
