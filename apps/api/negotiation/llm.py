"""LLM boundary for negotiation rationale generation.

This is the ONLY file in negotiation/ that imports google.genai. It generates
natural-language rationales for offers - NEVER the numeric price (which is
deterministic, computed in strategies.py).

N-1 DOES NOT apply to this file (it imports the LLM by design). It IS the
boundary. The purity test allows negotiation/llm.py to import google.genai.

Fail-soft: if the LLM is unavailable or returns garbage, we fall back to a
deterministic one-line rationale. The negotiation NEVER blocks on LLM uptime.
"""
from __future__ import annotations

try:
    from ..llm.gemini import ask as _gemini_ask
    _LLM_AVAILABLE = True
except Exception:  # pragma: no cover
    _gemini_ask = None  # type: ignore
    _LLM_AVAILABLE = False


def _fallback_rationale(actor: str, price_paise: int, turn: int,
                        reason: str = "") -> str:
    rupees = price_paise / 100
    who = "Buyer" if actor == "buyer" else "Merchant"
    base = f"{who} offers Rs. {rupees:.2f} (turn {turn})."
    if reason:
        return f"{base} {reason}"
    return base


def generate_offer_rationale(*, actor: str, sku: str, price_paise: int,
                             turn: int, prev_gap_paise: int | None,
                             budget_paise: int | None,
                             floor_paise: int, ceiling_paise: int,
                             llm_enabled: bool = True) -> str:
    """Generate a 1-2 sentence rationale for an offer.

    Falls back to a deterministic string if the LLM is unavailable or the
    response is empty/unparseable. The numeric price is NEVER taken from the
    LLM - it is passed in already-clamped from strategies.py.
    """
    if not llm_enabled or not _LLM_AVAILABLE:
        return _fallback_rationale(actor, price_paise, turn)

    system = (
        "You are a concise commerce negotiator. Output ONE sentence (max 25 "
        "words) explaining the offer rationale. Do NOT mention internal "
        "variables, floor, ceiling, or audit. Speak as the actor. No markdown."
    )
    rupees = price_paise / 100
    gap_r = (prev_gap_paise / 100) if prev_gap_paise else 0
    user = (
        f"Actor: {actor}. SKU: {sku}. Offer: Rs. {rupees:.2f}. "
        f"Turn: {turn}. Previous gap: Rs. {gap_r:.2f}. "
        f"Speak naturally as {actor} justifying this offer."
    )
    try:
        resp = _gemini_ask(system, user)
        if isinstance(resp, dict) and resp.get("text"):
            text = str(resp["text"]).strip().split("\n")[0].strip()
            if 5 <= len(text) <= 300:
                return text
    except Exception:
        pass
    return _fallback_rationale(actor, price_paise, turn)


def generate_walk_away_rationale(*, sku: str, final_gap_paise: int,
                                 turns: int) -> str:
    if not _LLM_AVAILABLE:
        return f"Negotiation walked away after {turns} turns (gap too wide)."
    system = (
        "You are a commerce negotiator ending a deal. Output ONE sentence "
        "(max 20 words) explaining why the parties walked away. No markdown."
    )
    user = (
        f"SKU: {sku}. Turns: {turns}. Final gap: Rs. {final_gap_paise/100:.2f}."
    )
    try:
        resp = _gemini_ask(system, user)
        if isinstance(resp, dict) and resp.get("text"):
            text = str(resp["text"]).strip().split("\n")[0].strip()
            if 5 <= len(text) <= 300:
                return text
    except Exception:
        pass
    return f"Negotiation walked away after {turns} turns (gap too wide)."
