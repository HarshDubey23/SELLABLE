"""The authorization issuer — an explicit, honest boundary.

In a real deployment the things this module produces are NOT produced by
the server that spends the money:

  * the signed **mission** is issued by whoever grants the agent its
    budget (in this codebase, `scripts/sign_mission.py`, run out of band
    with the signing key from .env);
  * the signed **intent and cart mandates** are issued by the user's
    wallet app (`scripts/mandate.py`).

Separating signer from verifier is the whole point of R9 and INV-3: a
compromised storefront must not be able to mint its own permission slip.

This module exists so that the browser-driven demo can complete a run
without a human shelling out to two CLIs — and so that the compromise is
*visible in the code* rather than buried in a route handler. Every
response produced through this path is tagged
`authorization_issued_by: "in_process_demo_issuer"`.

WHAT THIS MEANS FOR THE SECURITY CLAIM
--------------------------------------
When missions are signed here, R9 proves integrity (nothing tampered
with the mission between issuance and evaluation) but not custody (the
same process could have minted it). The API-driven path in `/tools/*`
takes an externally signed mission and does not have this caveat. Read
docs/architecture/trust-boundary.md before quoting a stronger claim than
that.
"""
from __future__ import annotations

import os
import time

from .gateway.mission_verify import dumps as _dumps
from .gateway.mission_verify import sign_mission
from .gateway.types import canonical_json
from .mandates.mandates import (
    CartMandate,
    IntentMandate,
    sign_cart,
    sign_intent,
)

ISSUER_LABEL = "in_process_demo_issuer"


def issue_mission(*, mission_id: str, intent: str, budget_paise: int,
                  allowed_categories: tuple[str, ...],
                  forbidden_categories: tuple[str, ...] = (),
                  upsell_cap: float = 1.0,
                  ttl_seconds: int = 3600,
                  now_ts: int | None = None) -> dict:
    """Mint a signed mission in the exact shape the gateway verifies."""
    now_ts = now_ts if now_ts is not None else int(time.time())
    blob = {
        "mission_id": mission_id,
        "intent": intent,
        "budget_paise": budget_paise,
        "allowed_categories": tuple(allowed_categories),
        "forbidden_categories": tuple(forbidden_categories),
        "upsell_cap": upsell_cap,
        "expires_at": now_ts + ttl_seconds,
    }
    signature = sign_mission(canonical_json(blob))
    out = {k: (list(v) if isinstance(v, tuple) else v) for k, v in blob.items()}
    out["signature"] = signature
    out["issued_by"] = ISSUER_LABEL
    return out


def issue_mandates(*, mission_id: str, proposal_hash: str, amount_paise: int,
                   ceiling_paise: int, user_id: str = "demo-user",
                   ttl_seconds: int = 3600,
                   now_ts: int | None = None) -> tuple[dict, dict]:
    """Mint the user-side intent + cart mandates (wallet stand-in)."""
    now_ts = now_ts if now_ts is not None else int(time.time())
    key = os.environ["USER_MANDATE_KEY"]
    intent_blob = sign_intent(IntentMandate(
        mission_id=mission_id, user_id=user_id,
        ceiling_paise=ceiling_paise, expires_at=now_ts + ttl_seconds), key)
    cart_blob = sign_cart(CartMandate(
        mission_id=mission_id, cart_hash=proposal_hash,
        amount_paise=amount_paise, signed_at=now_ts,
        expires_at=now_ts + ttl_seconds), key)
    return intent_blob, cart_blob


__all__ = ["ISSUER_LABEL", "issue_mission", "issue_mandates", "_dumps"]
