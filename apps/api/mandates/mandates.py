"""User-signed mandates — the AP2 pattern, implemented natively. INV-3.

  IntentMandate — the user pre-authorizes the mission: spend ceiling,
                  expiry, currency. Signed before the agent runs.
  CartMandate   — the user co-signs the FINAL cart: locked cart hash +
                  final amount. Signed at the consent step, after the
                  gateway APPROVE, before the order.

Custody (machine-verified by tests/invariants/test_agent_custody.py):
  - Mandates are minted out-of-band by scripts/mandate.py — a separate
    process simulating the user's wallet app — mirroring the Day-4
    mission-signer split.
  - The buyer agent module never reads USER_MANDATE_KEY and never calls
    sign_intent/sign_cart. It only CARRIES blobs.
  - The executor verifies both mandates before any order exists.

Deterministic: stdlib only. No LLM, no network, no I/O. Inside the money
path's gating layer, covered by INV-2 purity.
"""
from __future__ import annotations

import base64
import hashlib
import hmac
import json
import os
import time
from dataclasses import dataclass
from typing import Any

MANDATE_VERSION = 1
SUPPORTED_VERSIONS = (MANDATE_VERSION,)
SUPPORTED_CURRENCIES = ("INR",)


class MandateError(Exception):
    """Raised by the verifier with a machine-readable code."""

    CODES = {
        "MANDATE_MISSING": "no mandate token supplied",
        "MANDATE_BAD_SIGNATURE": "signature verification failed",
        "MANDATE_EXPIRED": "expires_at is in the past",
        "MANDATE_CEILING_EXCEEDED": "order total exceeds the intent ceiling",
        "MANDATE_CART_MISMATCH": "cart hash does not match the approved proposal",
        "MANDATE_AMOUNT_MISMATCH": "mandated amount differs from the order amount",
        "MANDATE_MALFORMED": "token is not a well-formed mandate",
        "MANDATE_BAD_VERSION": "mandate version not supported",
        "MANDATE_BAD_CURRENCY": "mandate currency not supported",
        "MANDATE_MISSION_MISMATCH": "mandate mission_id differs from approved proposal",
        "MANDATE_CART_STALE": "cart mandate signed_at is older than the approval",
    }

    def __init__(self, code: str, detail: str = "") -> None:
        super().__init__(f"{code}: {detail or self.CODES.get(code, '')}")
        self.code = code
        self.detail = detail


def _canonical(payload: dict[str, Any]) -> bytes:
    return json.dumps(payload, sort_keys=True, separators=(",", ":")).encode()


def _sign(payload: dict[str, Any], key: str) -> str:
    mac = hmac.new(key.encode(), _canonical(payload), hashlib.sha256).digest()
    return base64.urlsafe_b64encode(mac).decode().rstrip("=")


def _verify(token: str, payload: dict[str, Any], key: str) -> bool:
    return hmac.compare_digest(_sign(payload, key), (token or "").strip())


def _key() -> str:
    key = os.environ.get("USER_MANDATE_KEY", "")
    if not key:
        raise MandateError("MANDATE_MISSING", "USER_MANDATE_KEY is not configured")
    return key


@dataclass(frozen=True)
class IntentMandate:
    mission_id: str
    user_id: str
    ceiling_paise: int
    expires_at: int          # unix seconds
    currency: str = "INR"
    version: int = MANDATE_VERSION

    def payload(self) -> dict[str, Any]:
        return {"type": "intent_mandate", "version": self.version,
                "mission_id": self.mission_id, "user_id": self.user_id,
                "ceiling_paise": self.ceiling_paise, "expires_at": self.expires_at,
                "currency": self.currency}


@dataclass(frozen=True)
class CartMandate:
    mission_id: str
    cart_hash: str           # the gateway-APPROVED proposal hash
    amount_paise: int
    signed_at: int
    version: int = MANDATE_VERSION

    def payload(self) -> dict[str, Any]:
        return {"type": "cart_mandate", "version": self.version,
                "mission_id": self.mission_id, "cart_hash": self.cart_hash,
                "amount_paise": self.amount_paise, "signed_at": self.signed_at}


def sign_intent(mandate: IntentMandate, key: str) -> dict[str, Any]:
    payload = mandate.payload()
    return {"payload": payload, "sig": _sign(payload, key)}


def sign_cart(mandate: CartMandate, key: str) -> dict[str, Any]:
    payload = mandate.payload()
    return {"payload": payload, "sig": _sign(payload, key)}


def verify_intent(blob: Any, *, now: int | None = None,
                  order_total_paise: int | None = None,
                  expected_mission_id: str | None = None) -> dict[str, Any]:
    if not isinstance(blob, dict) or "payload" not in blob or "sig" not in blob:
        raise MandateError("MANDATE_MALFORMED")
    payload = blob["payload"]
    if not isinstance(payload, dict) or payload.get("type") != "intent_mandate":
        raise MandateError("MANDATE_MALFORMED", "wrong mandate type")
    version = int(payload.get("version", 0))
    if version not in SUPPORTED_VERSIONS:
        raise MandateError("MANDATE_BAD_VERSION", f"version={version}")
    currency = str(payload.get("currency", ""))
    if currency not in SUPPORTED_CURRENCIES:
        raise MandateError("MANDATE_BAD_CURRENCY", f"currency={currency}")
    if not _verify(str(blob["sig"]), payload, _key()):
        raise MandateError("MANDATE_BAD_SIGNATURE")
    now = int(time.time()) if now is None else now
    if int(payload.get("expires_at", 0)) <= now:
        raise MandateError("MANDATE_EXPIRED")
    if (expected_mission_id is not None
            and str(payload.get("mission_id", "")) != expected_mission_id):
        raise MandateError("MANDATE_MISSION_MISMATCH")
    if order_total_paise is not None and int(payload.get("ceiling_paise", 0)) < order_total_paise:
        raise MandateError("MANDATE_CEILING_EXCEEDED")
    return payload


def verify_cart(blob: Any, *, proposal_hash: str, amount_paise: int,
                expected_mission_id: str | None = None,
                approval_issued_at: int | None = None) -> dict[str, Any]:
    if not isinstance(blob, dict) or "payload" not in blob or "sig" not in blob:
        raise MandateError("MANDATE_MALFORMED")
    payload = blob["payload"]
    if not isinstance(payload, dict) or payload.get("type") != "cart_mandate":
        raise MandateError("MANDATE_MALFORMED", "wrong mandate type")
    version = int(payload.get("version", 0))
    if version not in SUPPORTED_VERSIONS:
        raise MandateError("MANDATE_BAD_VERSION", f"version={version}")
    if not _verify(str(blob["sig"]), payload, _key()):
        raise MandateError("MANDATE_BAD_SIGNATURE")
    if payload.get("cart_hash") != proposal_hash:
        raise MandateError("MANDATE_CART_MISMATCH")
    if int(payload.get("amount_paise", -1)) != int(amount_paise):
        raise MandateError("MANDATE_AMOUNT_MISMATCH")
    if (expected_mission_id is not None
            and str(payload.get("mission_id", "")) != expected_mission_id):
        raise MandateError("MANDATE_MISSION_MISMATCH")
    if approval_issued_at is not None:
        if int(payload.get("signed_at", 0)) < int(approval_issued_at) - 1:
            raise MandateError("MANDATE_CART_STALE")
    return payload
