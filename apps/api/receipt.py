"""GET /api/v1/receipt/{ref} — the settled facts of one purchase.

A receipt is the short version of the trace: what was bought, for how
much, under whose authority, and whether the ledger that records it
still verifies. It is a join over rows that already exist — nothing here
computes a new fact, and nothing here asserts a payment the provider did
not confirm.

The interesting field is `audit_anchor`. It carries the exact byte
string the anchor block's hash was computed over, so the person holding
the receipt can recompute that hash themselves and stop trusting this
server's word for it.

`ref` accepts an execution id, a mission id or a provider order id.
"""
from __future__ import annotations

import time
from typing import Any

from fastapi import APIRouter, HTTPException

from .audit import chain as audit_chain
from .audit_demo import hash_preimage
from .store import db as store

router = APIRouter(tags=["receipt"])


@router.get("/api/v1/receipt/{ref}")
def mission_receipt(ref: str) -> dict[str, Any]:
    from .products import CATALOG

    execution = (
        store.query_one("SELECT * FROM payment_executions WHERE execution_id = ?", (ref,))
        or store.query_one("SELECT * FROM payment_executions WHERE remote_order_id = ? "
                           "ORDER BY created_at DESC LIMIT 1", (ref,))
        or store.query_one("SELECT * FROM payment_executions WHERE mission_id = ? "
                           "ORDER BY created_at DESC LIMIT 1", (ref,))
    )
    if execution is None:
        raise HTTPException(404, detail={
            "ok": False,
            "error": {"error_code": "UNKNOWN_REFERENCE",
                      "message": f"no execution matches {ref!r}",
                      "accepts": ["execution_id", "mission_id", "remote_order_id"]}})

    binding = store.query_one("SELECT * FROM bindings WHERE seq = ?",
                              (execution["approve_seq"],))
    verdict = store.query_one("SELECT * FROM verdicts WHERE seq = ?",
                              (execution["approve_seq"],))
    quote = store.query_one("SELECT * FROM quotes WHERE quote_id = ?",
                            (execution["quote_id"],))

    # What was actually bought, named from the catalog rather than from
    # anything a client sent.
    product_names: list[str] = []
    if quote and quote["items"]:
        import json as _json
        try:
            for it in _json.loads(quote["items"]):
                entry = CATALOG.get(it.get("sku", ""), {})
                name = entry.get("name", it.get("sku", "?"))
                qty = it.get("qty", 1)
                product_names.append(f"{name}" + (f" x{qty}" if qty != 1 else ""))
        except (ValueError, TypeError):
            product_names = []

    settlement_rows = store.query(
        "SELECT event_id, event_type, status, received_at FROM webhook_events "
        "WHERE order_id = ? ORDER BY received_at",
        (execution["remote_order_id"] or "",))

    chain_ok, chain_reason = audit_chain.verify_strict()
    anchor = next((e for e in audit_chain.entries()
                   if e["seq"] == execution["approve_seq"]), None)

    return {
        "ok": True,
        "reference": ref,
        "execution_id": execution["execution_id"],
        "mission_id": execution["mission_id"],
        "product": ", ".join(product_names) or None,
        "final_amount_paise": execution["amount_paise"],
        "final_amount_display": f"Rs {execution['amount_paise'] / 100:,.2f}",
        "currency": execution["currency"],
        "priced_from": "server-side merchant catalog",
        "provider": execution["provider"],
        "provider_order_id": execution["remote_order_id"],
        "execution_state": execution["state"],
        "attempts": execution["attempts"],
        "gateway_decision": verdict["decision"] if verdict else None,
        "gateway_rule_failed": verdict["rule_id"] if verdict else None,
        "policy_version": "sellable-v1.0",
        "proposal_hash": execution["proposal_hash"],
        "approval_binding": {
            "seq": binding["seq"],
            "bound_skus": binding["skus"],
            "bound_amount_paise": binding["amount_paise"],
            "issued_at": binding["issued_at"],
            "expires_at": binding["expires_at"],
            "consumed_at": binding["consumed_at"],
            "single_use": True,
        } if binding else None,
        # Settlement is a fact only a signed webhook or an authoritative
        # provider read can establish. An order is not a payment.
        "settlement": {
            "confirmed": any(r["status"] == "captured" for r in settlement_rows),
            "events": [dict(r) for r in settlement_rows],
            "note": ("settlement is claimed only from HMAC-verified webhook "
                     "events; creating an order does not collect money"),
        },
        "audit_chain": "VERIFIED" if chain_ok else "HALTED",
        "audit_chain_reason": chain_reason,
        "audit_anchor": {
            "seq": anchor["seq"],
            "hash": anchor.get("hash"),
            "hash_algorithm": "sha256",
            "hash_preimage": hash_preimage(anchor),
            "verify_it_yourself": (
                "SHA-256 the preimage with any tool. If it matches `hash`, "
                "this block is exactly what it claims to be — and every "
                "later block commits to it."),
        } if anchor else None,
        "issuer": "in_process_demo_issuer",
        "issuer_note": ("the browser demo signs the user mandate inside this "
                        "server, which proves integrity but not custody; the "
                        "API path takes an externally signed mandate"),
        "generated_at": int(time.time()),
    }
