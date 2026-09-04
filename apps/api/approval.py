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

import json
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
        if self.mission_id != mission_id:
            return False, "MISSION_MISMATCH"
        if self.proposal_hash != proposal_hash:
            return False, "PROPOSAL_HASH_MISMATCH"
        if self.cart_hash != cart_hash:
            return False, "CART_HASH_MISMATCH"
        if self.quote_id != "" and self.quote_id != quote_id:
            return False, "QUOTE_MISMATCH"
        if self.amount_paise != amount_paise:
            return False, "AMOUNT_MISMATCH"
        if self.currency != currency:
            return False, "CURRENCY_MISMATCH"
        if tuple(sorted(skus)) != self.sku_set:
            return False, "SKU_SET_MISMATCH"
        return True, "OK"


_DEFAULT_TTL_SECONDS = 30 * 60
_POLICY_VERSION = "sellable-v1.0"


def _row_to_binding(row: dict[str, Any]) -> ApprovalBinding:
    skus_list = json.loads(row["skus"]) if row["skus"] else []
    return ApprovalBinding(
        seq=row["seq"],
        mission_id=row["mission_id"],
        proposal_hash=row["proposal_hash"],
        cart_hash=row["cart_hash"],
        quote_id=row["quote_id"],
        amount_paise=row["amount_paise"],
        currency=row["currency"],
        sku_set=tuple(sorted(tuple(x) for x in skus_list)),
        issued_at=row["issued_at"],
        expires_at=row["expires_at"],
        mandate_version=int(row["mandate_version"]),
        policy_version=_POLICY_VERSION,
    )


def register(seq: int, *, mission_id: str, proposal_hash: str,
             cart_hash: str, quote_id: str, amount_paise: int,
             currency: str, skus: list[tuple[str, int]],
             ttl_seconds: int = _DEFAULT_TTL_SECONDS,
             mandate_version: int = 1,
             now_ts: int | None = None) -> ApprovalBinding:
    """Persist a fresh binding in SQLite. Called by tools.submit_proposal when APPROVE."""
    now_ts = now_ts if now_ts is not None else int(time.time())
    expires_at = now_ts + ttl_seconds
    skus_json = json.dumps(skus)

    store.execute(
        "INSERT INTO bindings (seq, mission_id, proposal_hash, cart_hash, quote_id, amount_paise, currency, skus, mandate_version, issued_at, expires_at, consumed_at) "
        "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, NULL)",
        (seq, mission_id, proposal_hash, cart_hash, quote_id, amount_paise, currency, skus_json, str(mandate_version), now_ts, expires_at)
    )

    return ApprovalBinding(
        seq=seq,
        mission_id=mission_id,
        proposal_hash=proposal_hash,
        cart_hash=cart_hash,
        quote_id=quote_id,
        amount_paise=amount_paise,
        currency=currency,
        sku_set=tuple(sorted(skus)),
        issued_at=now_ts,
        expires_at=expires_at,
        mandate_version=mandate_version,
        policy_version=_POLICY_VERSION,
    )


def get(seq: int) -> ApprovalBinding | None:
    row = store.query_one("SELECT * FROM bindings WHERE seq = ?", (seq,))
    return _row_to_binding(row) if row else None


def get_legacy_proposal_hash(seq: int) -> str | None:
    """Back-compat shim: returns seq -> proposal_hash for tools.create_order."""
    b = get(seq)
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
    row = store.query_one("SELECT * FROM bindings WHERE seq = ?", (seq,))
    if row is None:
        money_counter.record("binding_miss", seq=seq)
        return False, "BINDING_NOT_FOUND", None

    b = _row_to_binding(row)
    if row["consumed_at"] is not None:
        money_counter.record("binding_consumed", seq=seq)
        return False, "BINDING_CONSUMED", b

    ok, reason = b.matches_money(
        mission_id=mission_id, proposal_hash=proposal_hash,
        cart_hash=cart_hash, quote_id=quote_id, amount_paise=amount_paise,
        currency=currency, skus=skus, now_ts=now_ts)

    if not ok:
        money_counter.record(f"binding_{reason.lower()}", seq=seq)
        return False, reason, b

    # Mark as consumed atomically
    now_ts_consumed = now_ts if now_ts is not None else int(time.time())
    affected = store.execute_rowcount(
        "UPDATE bindings SET consumed_at = ? WHERE seq = ? AND consumed_at IS NULL",
        (now_ts_consumed, seq)
    )
    if affected != 1:
        money_counter.record("binding_concurrent_consumed", seq=seq)
        return False, "BINDING_CONSUMED", b

    return True, "OK", b


def reset_consumed() -> None:
    """Clear the consumed set. Used by tests; never call from production."""
    store.execute("UPDATE bindings SET consumed_at = NULL")


def all_bindings() -> list[ApprovalBinding]:
    rows = store.query("SELECT * FROM bindings")
    return [_row_to_binding(r) for r in rows]