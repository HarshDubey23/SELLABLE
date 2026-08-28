"""SELLABLE Negotiation Engine - Day 5.

The thesis is unchanged: "The LLM proposes. Deterministic policy disposes.
The audit log remembers."

The negotiation engine extends SELLABLE from a single-shot accept/decline
upsell flow into a *multi-turn, bounded-rationality* price negotiation
between a buyer agent and a merchant agent - while keeping every money
decision deterministic, gated, and audit-chained.

BOUNDING CONTRACT (enforced by negotiation/bounds.py, NOT by the LLM):
  - floor_paise   : merchant walk-away price per SKU (server-side, from CATALOG)
  - ceiling_paise : MSRP per SKU (server-side, from CATALOG)
  - max_turns     : hard cap on negotiation rounds (default 5)
  - monotonic     : merchant concessions must be monotonically decreasing
                    (price moves toward floor only); buyer offers must be
                    monotonically increasing (toward ceiling)
  - walk_away     : if gap > walk_away_threshold_paise after max_turns,
                    negotiation terminates with status=walked_away
  - budget_gate   : the final agreed price still goes through the FULL
                    gateway evaluate() (R1-R10) and create_order INV-1 gate.
                    Negotiation NEVER shortcuts the money path.

The LLM is used ONLY to:
  (a) draft the merchant's counter-offer rationale (natural language), and
  (b) draft the buyer agent's offer rationale.
The numeric price in every offer is CLAMPED by bounds.py before it is
recorded - the LLM can never push the price outside [floor, ceiling].

Public submodules:
  types        - frozen dataclasses (NegotiationState, Offer, Turn, Result)
  bounds       - deterministic clamp + walk-away + monotonic checks
  strategies   - merchant anchor/concede/walk-away strategy (deterministic)
  llm          - LLM offer-rationale generation (single import boundary)
  engine       - the bounded negotiation loop
  api          - FastAPI routes (/negotiation/*)
  persist      - SQLite-backed negotiation state (survives restart)
"""
