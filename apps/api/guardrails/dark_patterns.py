"""Deterministic dark-pattern screener for agent-generated copy. Defense-only.

Practical subset of India's "Guidelines for Prevention and Regulation of Dark
Patterns, 2023" (CCPA). BLOCKS publication of non-compliant copy. Never
rewrites, never generates, contains no LLM.

SCOPE: agent-generated PERSUASION copy (upsell offers, payment-link
descriptions, recovery messages). Catalog pages state stock and price
factually from the source of truth and are out of scope.

HONEST DEADLINES: "payment link expires in 24 hours" is NOT a dark pattern
here — the deadline is real, machine-enforced (gateway rule R10), and
verifiable in the audit chain. This scanner targets UNVERIFIABLE pressure.
Verifiability is the dividing line.
"""
from __future__ import annotations

import re

GUIDELINE_REF = "CCPA Guidelines for Prevention and Regulation of Dark Patterns, 2023"

_PATTERNS: tuple[tuple[str, re.Pattern[str], str], ...] = (
    ("false_urgency",
     re.compile(r"\b(hurry|act now|last chance|time is running out|don'?t wait)\b", re.I),
     "Generic urgency pressure with no verifiable deadline"),
    ("false_urgency",
     re.compile(r"\b(offer|deal|price|discount)\s+(expires|ends)\s+(today|tonight|now|soon)\b", re.I),
     "Expiry claim without a verifiable deadline"),
    ("fake_scarcity",
     re.compile(r"\b(only|just)\s+\d+\s+(left|remaining|available|in stock)\b", re.I),
     "Stock pressure not sourced from the catalog"),
    ("fake_scarcity",
     re.compile(r"\b(selling fast|almost\s+(gone|sold\s+out))\b", re.I),
     "Manufactured demand signal"),
    ("fake_scarcity",
     re.compile(r"\b\d+\s+(people|users|buyers)\s+(are\s+)?(viewing|watching|bought)\b", re.I),
     "Fabricated live-demand claim"),
    ("drip_pricing",
     re.compile(r"\b(plus|excluding)\s+(taxes|gst|fees|charges)\b", re.I),
     "Non-inclusive pricing in final offer copy"),
    ("drip_pricing",
     re.compile(r"\b(additional|extra|hidden)\s+(charges|fees)\s+(may|will|to)\s+apply\b", re.I),
     "Charges disclosed only later in the flow"),
    ("bait_and_switch",
     re.compile(r"\bfree\b[\s\S]{0,60}\b(but|however|charges apply|terms apply|conditions apply|t&c)\b", re.I),
     "Free claim qualified into a paid reality"),
    ("interface_interference",
     re.compile(r"\bclick here to (claim|win|get your)\b", re.I),
     "Distractive / misleading call-to-action phrasing"),
)


class DarkPatternBlocked(Exception):
    """Raised by assert_allows() when copy violates the guideline subset."""

    def __init__(self, scan: dict) -> None:
        super().__init__("dark pattern detected in agent copy")
        self.scan = scan


def scan_copy(text: str) -> dict:
    """Scan final offer copy. Pure function: same input, same verdict, forever."""
    flags = []
    for category, pattern, description in _PATTERNS:
        match = pattern.search(text or "")
        if match:
            flags.append({"category": category, "match": match.group(0)[:120],
                          "description": description})
    return {"verdict": "block" if flags else "allow", "scanner": "dark_patterns_v1",
            "guideline_ref": GUIDELINE_REF, "flags": flags,
            "scanned_chars": len(text or "")}


def assert_allows(text: str) -> dict:
    """Call at every copy-emission boundary. Raises DarkPatternBlocked."""
    scan = scan_copy(text)
    if scan["verdict"] == "block":
        raise DarkPatternBlocked(scan)
    return scan
