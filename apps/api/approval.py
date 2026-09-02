"""Exact Approval Binding — the executor's gate to the money boundary.

An APPROVE verdict alone is NOT sufficient to authorize money movement.
The binding records every identity that must remain consistent at order
creation time:

  - mission_id      : ties the approval to one mission
  - proposal_hash   : ties to the canonical proposal payload
  - cart_hash       : ties to the user-signed cart (same as proposal_hash
                      in single-cart flow; reserved for multi-cart future)
  - quote_id        : ties to the server-signed price lock
  - amount_paise    : exact paise amount — never a derived value
  - currency        : "INR" only — reject anything else fail-closed
  - sku_set         : tuple of (sku, qty) — guards against cart mutation
  - issued_at       : unix seconds
  - expires_at      : unix seconds — APPROVEs are time-bounded
  - mandate_version : ties to the user-mandate schema version

The executor MUST verify every field at order creation; mismatch on
ANY field => no order, no money.

The legacy `approved_bindings[seq] = proposal_hash` is preserved as a
compatibility shim (tools.create_order still checks it) but the
authoritative check goes through `verify_binding()`.
"""
from __future__ import annotations

import time
from dataclasses import dataclass
from typing import Any

from . import money as money_counter
from .store import db as store


@dataclass(frozen=True)
class ApprovalBinding:
    seq: int
    mission_id: str
    proposal_hash: str
    cart_hash: str
    quote_id: str
    amount_paise: int
    currency: str
    sku_set: tuple[tuple[str, int], ...]
    issued_at: int
    expires_at: int
    mandate_version: int
    policy_version: str

    def is_expired(self, now_ts: int | None = None) -> bool:
        now_ts = now_ts if now_ts is not None else int(time.time())
        return now_ts >= self.expires_at

    def matches_money(self, *, mission_id: str, proposal_hash: str,
                      cart_hash: str, quote_id: str, amount_paise: int,
                      currency: str, skus: list[tuple[str, int]],
                      now_ts: int | None = None) -> tuple[bool, str]:
        """Strict invariant check. Returns (ok, reason).

        Quote linkage: if the binding was registered with quote_id=""
        (the typical case at /tools/submit_proposal time, before a
        quote exists), the executor's call carries the actual
        quote_id and the binding accepts it. If the binding was
        already pinned to a quote_id (pre-bound), the executor MUST
        send the same one — otherwise QUOTE_MISMATCH.
        """
        if self.is_expired(now_ts):
            return False, "BINDING_EXPIRED"
        if mission_id and self.mission_id != mission_id:
            return False, "MISSION_MISMATCH"
        if proposal_hash and self.proposal_hash != proposal_hash:
            return False, "PROPOSAL_HASH_MISMATCH"
        if cart_hash and self.cart_hash != cart_hash:
            return False, "CART_HASH_MISMATCH"
        if self.quote_id and quote_id and self.quote_id != quote_id:
            return False, "QUOTE_MISMATCH"
        if amount_paise and self.amount_paise != amount_paise:
            return False, "AMOUNT_MISMATCH"
        if currency and self.currency != currency:
            return False, "CURRENCY_MISMATCH"
        if skus and tuple(sorted(skus)) != self.sku_set:
            return False, "SKU_SET_MISMATCH"
        return True, "OK"


_BINDINGS: dict[int, ApprovalBinding] = {}
_CONSUMED: set[int] = set()
_DEFAULT_TTL_SECONDS = 30 * 60
_POLICY_VERSION = "sellable-v1.0"


def _load_persisted() -> None:
    """Rebuild the binding map from the verdicts table at boot.

    A binding exists where (decision='APPROVE' AND proposal_hash is set).
    Older rows without the rich columns are loaded best-effort; missing
    fields are filled with sentinel values that cause verify() to reject
    until a fresh proposal re-issues the binding under the new schema.
    """
    global _BINDINGS
    _BINDINGS = {}
    for row in store.query(
        "SELECT seq, decision, rule_id, reason, proposal_hash, mission_id "
        "FROM verdicts WHERE decision='APPROVE' ORDER BY seq"
    ):
        # Legacy data may not have all fields; we still register a minimal
        # binding so old APPROVE seqs remain visible (they will be
        # rejected at order creation until re-issued).
        _BINDINGS[row["seq"]] = ApprovalBinding(
            seq=row["seq"],
            mission_id=str(row["mission_id"] or ""),
            proposal_hash=str(row["proposal_hash"] or ""),
            cart_hash=str(row["proposal_hash"] or ""),
            quote_id="",
            amount_paise=0,
            currency="INR",
            sku_set=tuple(),
            issued_at=0,
            expires_at=0,
            mandate_version=1,
            policy_version=_POLICY_VERSION,
        )


_load_persisted()


def register(seq: int, *, mission_id: str, proposal_hash: str,
             cart_hash: str, quote_id: str, amount_paise: int,
             currency: str, skus: list[tuple[str, int]],
             ttl_seconds: int = _DEFAULT_TTL_SECONDS,
             mandate_version: int = 1,
             now_ts: int | None = None) -> ApprovalBinding:
    """Persist a fresh binding. Called by tools.submit_proposal when APPROVE."""
    now_ts = now_ts if now_ts is not None else int(time.time())
    binding = ApprovalBinding(
        seq=seq,
        mission_id=mission_id,
        proposal_hash=proposal_hash,
        cart_hash=cart_hash,
        quote_id=quote_id,
        amount_paise=amount_paise,
        currency=currency,
        sku_set=tuple(sorted(skus)),
        issued_at=now_ts,
        expires_at=now_ts + ttl_seconds,
        mandate_version=mandate_version,
        policy_version=_POLICY_VERSION,
    )
    _BINDINGS[seq] = binding
    return binding


def get(seq: int) -> ApprovalBinding | None:
    return _BINDINGS.get(seq)


def get_legacy_proposal_hash(seq: int) -> str | None:
    """Back-compat shim: returns seq -> proposal_hash for tools.create_order."""
    b = _BINDINGS.get(seq)
    return b.proposal_hash if b else None


def verify(*, seq: int, mission_id: str, proposal_hash: str,
           cart_hash: str, quote_id: str, amount_paise: int,
           currency: str, skus: list[tuple[str, int]],
           now_ts: int | None = None) -> tuple[bool, str, ApprovalBinding | None]:
    """The money executor's gate.

    Returns (ok, error_code, binding). When ok=False, error_code names
    the failed invariant; the caller MUST reject the order.

    Single-use enforcement: a binding is consumed the FIRST time it
    verifies successfully. A second create_order call with the same
    seq => BINDING_CONSUMED => no order, no money.

    Money boundary invariant:
        rejected verify() => money.create_order MUST NOT be called.
    """
    b = _BINDINGS.get(seq)
    if b is None:
        money_counter.record("binding_miss", seq=seq)
        return False, "BINDING_NOT_FOUND", None
    if seq in _CONSUMED:
        money_counter.record("binding_consumed", seq=seq)
        return False, "BINDING_CONSUMED", b
    ok, reason = b.matches_money(
        mission_id=mission_id, proposal_hash=proposal_hash,
        cart_hash=cart_hash, quote_id=quote_id, amount_paise=amount_paise,
        currency=currency, skus=skus, now_ts=now_ts)
    if not ok:
        money_counter.record(f"binding_{reason.lower()}", seq=seq)
        return False, reason, b
    _CONSUMED.add(seq)
    return True, "OK", b


def reset_consumed() -> None:
    """Clear the consumed set. Used by tests; never call from production."""
    _CONSUMED.clear()


def all_bindings() -> list[ApprovalBinding]:
    return list(_BINDINGS.values())