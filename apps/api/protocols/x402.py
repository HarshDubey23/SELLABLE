"""x402 adapter — honest partial stub (Phase 4).

x402 authorizes payment-per-request via an on-chain (or equivalent
irreversible) transfer. SELLABLE's money path is Razorpay test-mode with a
hash-chained audit ledger; wiring an irreversible payment rail without the
deployment guarantees x402 assumes would be a silent-degradation risk, so
this endpoint refuses honestly (501) instead of pretending.

Honesty over theater: the manifest and the adapter surface both say x402 is
NOT implemented. Everything else in the protocol layer is real.

ADAPTER INVARIANTS (enforced by tests/invariants/test_protocol_adapter_invariants.py):
  - MUST NOT import apps.api.gateway
  - MUST NOT construct verdicts
  - MUST NOT contain rule logic
"""
from __future__ import annotations

from fastapi import APIRouter, Depends
from fastapi.responses import JSONResponse

from ..deps import require_api_key

router = APIRouter(prefix="/protocol/x402", tags=["protocols"])


@router.post("/authorize", dependencies=[Depends(require_api_key)])
async def authorize() -> JSONResponse:
    """Honest 501: x402 settlement is not implemented. Refuse, don't fake."""
    return JSONResponse(
        status_code=501,
        content={
            "protocol": "x402",
            "implemented": False,
            "reason": "x402 requires an irreversible payment rail; "
                      "SELLABLE binds test-mode Razorpay only. This stub "
                      "refuses rather than simulate.",
            "hint": "use /protocol/acp/checkout_sessions or "
                    "/protocol/ap2/mandates/evaluate",
        },
    )
