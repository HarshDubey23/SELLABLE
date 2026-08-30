"""Protocol Adapter Layer v0 — adapters translate, the gateway decides.

No rule logic lives here; see Section 4.1 of the blueprint.

Phase 4 fills this package with:
  - acp.py  — ACP-style checkout session adapter (POST /protocol/acp/checkout_sessions)
  - ap2.py  — AP2-style Intent+Cart mandate adapter (POST /protocol/ap2/mandates/evaluate)
  - x402.py — honest partial stub (POST /protocol/x402/authorize -> 501)

Invariants enforced from Phase 4 onward (tests/invariants/):
  - adapters MUST NOT import apps.api.gateway
  - adapters MUST NOT construct verdicts
  - adapters MUST NOT contain rule logic

Adapters normalize protocol artifacts into Mission/proposal objects the gateway
already understands. Adapters translate; the gateway decides.
"""
