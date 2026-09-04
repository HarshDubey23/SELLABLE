"""Execution + reconciliation API.

Reconciliation is the answer to the only interesting question in agentic
payments: *what happens when you don't know what happened?*

We never resolve an ambiguous execution by guessing, by retrying blindly,
or by trusting a local flag. We ask the provider for its authoritative
state and match on correlation fields we wrote at creation time.
"""
from __future__ import annotations

import time

from fastapi import APIRouter, Depends, HTTPException

from . import execution as ex
from . import execution_provider as provider_mod
from .audit import chain
from .deps import require_api_key
from .store import db as store

router = APIRouter()


def _public(row: dict) -> dict:
    return {
        "execution_id": row["execution_id"],
        "state": row["state"],
        "provider": row["provider"],
        "mission_id": row["mission_id"],
        "approve_seq": row["approve_seq"],
        "proposal_hash": row["proposal_hash"],
        "quote_id": row["quote_id"],
        "amount_paise": row["amount_paise"],
        "currency": row["currency"],
        "idempotency_key": row["idempotency_key"],
        "remote_order_id": row["remote_order_id"],
        "remote_error_code": row["remote_error_code"],
        "attempts": row["attempts"],
        "last_error": row["last_error"],
        "created_at": row["created_at"],
        "updated_at": row["updated_at"],
        "reconciled_at": row["reconciled_at"],
        "terminal_at": row["terminal_at"],
    }


@router.get("/executions")
def list_executions(state: str | None = None, limit: int = 50):
    """Every execution and its durable state. This is the proof surface."""
    rows = ex.list_executions(state=state, limit=limit)
    return {
        "executions": [_public(r) for r in rows],
        "summary": ex.summary(),
        "states": list(ex.ALL_STATES),
        "terminal_states": sorted(ex.TERMINAL_STATES),
        "provider": provider_mod.provider_name(),
        "provider_description": provider_mod.mode_description(),
    }


@router.get("/executions/{execution_id}")
def get_execution(execution_id: str):
    row = ex.get(execution_id)
    if row is None:
        raise HTTPException(404, detail=f"unknown execution {execution_id}")
    return _public(row)


@router.post("/executions/{execution_id}/reconcile",
             dependencies=[Depends(require_api_key)])
def reconcile(execution_id: str):
    """Resolve an ambiguous execution against authoritative remote state.

    Outcomes:
      remote order found      -> EXECUTED  (the money DID move; record it)
      remote order absent     -> FAILED    (the money did NOT move)
      remote unreachable      -> stays RECONCILIATION_REQUIRED (503)

    The third case is the important one: an unreachable provider does not
    let us conclude anything, so the row stays stuck on purpose.
    """
    row = ex.get(execution_id)
    if row is None:
        raise HTTPException(404, detail=f"unknown execution {execution_id}")

    if row["state"] in ex.TERMINAL_STATES:
        return {"execution_id": execution_id, "state": row["state"],
                "already_terminal": True, "execution": _public(row)}

    if row["state"] != ex.RECONCILIATION_REQUIRED:
        raise HTTPException(409, detail={
            "ok": False,
            "error": {"error_code": "NOT_RECONCILABLE",
                      "message": f"execution is in state {row['state']}; only "
                                 f"{ex.RECONCILIATION_REQUIRED} can be reconciled"}})

    provider = provider_mod.get_provider()
    try:
        remote = provider.find_order_by_correlation(
            proposal_hash=row["proposal_hash"],
            amount_paise=row["amount_paise"])
    except Exception as exc:
        # Cannot read authoritative state => cannot conclude anything.
        chain.append("reconciler", "reconcile_unavailable",
                     {"execution_id": execution_id, "reason": str(exc)[:200]},
                     error_code="RECONCILE_UNAVAILABLE",
                     review_state="reconciliation_required")
        raise HTTPException(503, detail={
            "ok": False,
            "error": {"error_code": "RECONCILE_UNAVAILABLE",
                      "message": "provider unreachable; execution intentionally "
                                 "remains RECONCILIATION_REQUIRED",
                      "detail": str(exc)[:200],
                      "retryable": True}})

    if remote is not None:
        order_id = remote["id"]
        store.execute(
            "INSERT OR REPLACE INTO orders "
            "(order_id, idempotency_key, amount_paise, status, quote_id, "
            " mission_id, proposal_hash, approve_seq, created_at) "
            "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)",
            (order_id, row["idempotency_key"], row["amount_paise"],
             remote.get("status", "created"), row["quote_id"],
             row["mission_id"], row["proposal_hash"], row["approve_seq"],
             int(time.time())))
        from .tools import idempotency_seen
        from .tools import orders as order_cache
        order_cache[order_id] = {
            "order_id": order_id, "amount_paise": row["amount_paise"],
            "quote_id": row["quote_id"], "mission_id": row["mission_id"],
            "proposal_hash": row["proposal_hash"],
            "idempotency_key": row["idempotency_key"],
            "status": remote.get("status", "created"),
            "created_at": int(time.time()),
        }
        idempotency_seen[row["idempotency_key"]] = order_id

        updated = ex.transition(execution_id, ex.EXECUTED,
                                remote_order_id=order_id)
        chain.append("reconciler", "reconciled_executed",
                     {"execution_id": execution_id, "order_id": order_id,
                      "amount_paise": row["amount_paise"]},
                     review_state="reconciled")
        return {"execution_id": execution_id, "state": ex.EXECUTED,
                "resolution": "REMOTE_ORDER_FOUND",
                "remote_order_id": order_id,
                "explanation": ("the provider had executed the request; the "
                                "response was lost, not the order"),
                "execution": _public(updated)}

    # Absence is only evidence of failure once the provider's listing has
    # had time to become consistent. Concluding FAILED from a read taken
    # seconds after the attempt is how a live order gets written off — we
    # did exactly that against the real test API before this guard existed.
    age = int(time.time()) - int(row["updated_at"] or 0)
    never_dispatched = row.get("remote_error_code") == ex.NEVER_DISPATCHED
    if (provider.name == provider_mod.LIVE_TEST
            and not never_dispatched
            and age < provider_mod.ABSENCE_QUIET_PERIOD_SECONDS):
        wait = provider_mod.ABSENCE_QUIET_PERIOD_SECONDS - age
        chain.append("reconciler", "reconcile_inconclusive",
                     {"execution_id": execution_id, "age_seconds": age},
                     error_code="ABSENCE_NOT_YET_CONCLUSIVE",
                     review_state="reconciliation_required")
        raise HTTPException(202, detail={
            "ok": False,
            "error": {
                "error_code": "ABSENCE_NOT_YET_CONCLUSIVE",
                "message": ("the authoritative read found no matching order, "
                            "but the provider's order listing is not "
                            "read-your-writes consistent; this soon after the "
                            "attempt, absence is not evidence of failure"),
                "execution_id": execution_id,
                "execution_state": ex.RECONCILIATION_REQUIRED,
                "retry_after_seconds": wait,
                "retryable": True,
            }})

    updated = ex.transition(
        execution_id, ex.FAILED,
        remote_error_code="NO_REMOTE_ORDER",
        last_error=("the request was never dispatched, so an empty "
                    "authoritative read is conclusive"
                    if never_dispatched else
                    "authoritative read found no matching order after the "
                    "consistency window"))
    chain.append("reconciler", "reconciled_failed",
                 {"execution_id": execution_id},
                 error_code="NO_REMOTE_ORDER", review_state="reconciled")
    return {"execution_id": execution_id, "state": ex.FAILED,
            "resolution": "NO_REMOTE_ORDER",
            "explanation": (
                "the request was never dispatched to the provider, so there "
                "is nothing for its listing to be behind on; no money moved"
                if never_dispatched else
                "the provider has no matching order after its listing had "
                "time to become consistent; the request never took effect "
                "and no money moved"),
            "execution": _public(updated)}
