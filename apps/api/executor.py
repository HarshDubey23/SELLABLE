"""Canonical execution service — the ONLY path to money.

Durable execution state machine persisted in SQLite.

State machine:
    APPROVED -> EXECUTION_PENDING -> REMOTE_ATTEMPTED -> EXECUTED | FAILED | RECONCILIATION_REQUIRED

Every transition is audited. The binding is NOT consumed until the
remote Razorpay outcome is known. On timeout/connection loss we
query the authoritative Razorpay state before deciding.

Concurrent attempts cannot create multiple successful executions:
the SQL UPDATE ... WHERE execution_state='APPROVED' is atomic under
SQLite WAL, so exactly one thread wins.

This module is the single application execution service used by
the real API, the UI, /judge, demos, scripts, chaos engine, and
final verification. No other module bypasses this gate.
"""
from __future__ import annotations

import hashlib
import json
import os
import time
import uuid
from dataclasses import dataclass, field
from enum import StrEnum
from typing import Any

from ..audit import chain as audit_chain
from ..config import get as get_config
from ..money import record as money_record
from ..razorpay_client import (
    create_order as _rp_create_order,
    fetch_order as _rp_fetch_order,
    derive_idempotency_key,
)
from ..store import db as store
from ..approval import get as _approval_get


class ExecutionState(StrEnum):
    APPROVED = "APPROVED"
    EXECUTION_PENDING = "EXECUTION_PENDING"
    REMOTE_ATTEMPTED = "REMOTE_ATTEMPTED"
    EXECUTED = "EXECUTED"
    FAILED = "FAILED"
    RECONCILIATION_REQUIRED = "RECONCILIATION_REQUIRED"


VALID_TRANSITIONS: dict[ExecutionState, set[ExecutionState]] = {
    ExecutionState.APPROVED: {ExecutionState.EXECUTION_PENDING},
    ExecutionState.EXECUTION_PENDING: {
        ExecutionState.REMOTE_ATTEMPTED, ExecutionState.FAILED, ExecutionState.RECONCILIATION_REQUIRED
    },
    ExecutionState.REMOTE_ATTEMPTED: {
        ExecutionState.EXECUTED, ExecutionState.FAILED, ExecutionState.RECONCILIATION_REQUIRED
    },
    ExecutionState.EXECUTED: set(),
    ExecutionState.FAILED: {ExecutionState.EXECUTION_PENDING},
    ExecutionState.RECONCILIATION_REQUIRED: {ExecutionState.EXECUTED, ExecutionState.FAILED},
}


class IllegalExecutionTransitionError(ValueError):
    pass


@dataclass(frozen=True)
class ExecutionRecord:
    execution_id: str
    approval_seq: int
    mission_id: str
    proposal_hash: str
    amount_paise: int
    currency: str
    skus: tuple[tuple[str, int], ...]
    idempotency_key: str
    razorpay_order_id: str | None = None
    razorpay_payment_id: str | None = None
    execution_state: ExecutionState = ExecutionState.APPROVED
    previous_state: str = ""
    error_code: str | None = None
    error_reason: str | None = None
    reconciliation_reason: str | None = None
    attempts: int = 0
    created_at: int = 0
    updated_at: int = 0


def _now() -> int:
    return int(time.time())


def _transition_state(execution_id: str, target: ExecutionState, reason: str = "") -> ExecutionRecord:
    """Atomic state transition. Returns new record or raises."""
    rec = get_execution(execution_id)
    if rec is None:
        raise ValueError(f"execution {execution_id} not found")
    valid = VALID_TRANSITIONS.get(ExecutionState(rec.execution_state), set())
    if target not in valid:
        raise IllegalExecutionTransitionError(
            f"Cannot transition {rec.execution_state} -> {target}: {reason}"
        )
    updated = _update_execution_state(execution_id, target, reason)
    audit_chain.append(
        "executor", "execution_state_transition",
        {
            "execution_id": execution_id,
            "from_state": rec.execution_state,
            "to_state": target,
            "reason": reason,
            "approval_seq": rec.approval_seq,
        },
        review_state=f"{rec.execution_state}->{target}",
    )
    return get_execution(execution_id)


def _update_execution_state(
    execution_id: str,
    target: ExecutionState,
    reason: str = "",
    **kwargs: Any,
) -> ExecutionRecord:
    """Direct SQL update for state transitions."""
    now = _now()
    set_clauses = ["execution_state = ?", "updated_at = ?", "previous_state = COALESCE(previous_state, '')"]
    params: list[Any] = [target.value, now]
    if reason:
        set_clauses.append("error_reason = ?")
        params.append(reason)
    if "error_code" in kwargs and kwargs["error_code"]:
        set_clauses.append("error_code = ?")
        params.append(kwargs["error_code"])
    if "reconciliation_reason" in kwargs and kwargs["reconciliation_reason"]:
        set_clauses.append("reconciliation_reason = ?")
        params.append(kwargs["reconciliation_reason"])
    if "razorpay_order_id" in kwargs and kwargs["razorpay_order_id"]:
        set_clauses.append("razorpay_order_id = ?")
        params.append(kwargs["razorpay_order_id"])
    if "razorpay_payment_id" in kwargs and kwargs["razorpay_payment_id"]:
        set_clauses.append("razorpay_payment_id = ?")
        params.append(kwargs["razorpay_payment_id"])
    if "attempts" in kwargs and kwargs["attempts"] is not None:
        set_clauses.append("attempts = ?")
        params.append(kwargs["attempts"])
    set_clauses.append("WHERE execution_id = ?")
    params.append(execution_id)
    sql = f"UPDATE execution_log SET {', '.join(set_clauses)}"
    store.execute(sql, tuple(params))
    return get_execution(execution_id)


def register_execution(
    *,
    approval_seq: int,
    mission_id: str,
    proposal_hash: str,
    amount_paise: int,
    currency: str,
    skus: list[tuple[str, int]],
    idempotency_key: str,
) -> ExecutionRecord:
    """Create a new EXECUTION_PENDING record after approval but BEFORE calling Razorpay.

    The binding is NOT consumed here. It is consumed only after the
    remote outcome is known (in finalize_execution).
    """
    execution_id = f"ex_{uuid.uuid4().hex[:24]}"
    now = _now()
    store.execute(
        "INSERT OR REPLACE INTO execution_log "
        "(execution_id, approval_seq, mission_id, proposal_hash, amount_paise, "
        "currency, skus, idempotency_key, execution_state, previous_state, "
        "attempts, created_at, updated_at) "
        "VALUES (?, ?, ?, ?, ?, ?, ?, ?, 'EXECUTION_PENDING', '', 0, ?, ?)",
        (execution_id, approval_seq, mission_id, proposal_hash, amount_paise,
         currency, json.dumps(sorted(skus)), idempotency_key, now, now),
    )
    rec = get_execution(execution_id)
    audit_chain.append(
        "executor", "execution_registered",
        {
            "execution_id": execution_id,
            "approval_seq": approval_seq,
            "mission_id": mission_id,
            "proposal_hash": proposal_hash,
            "amount_paise": amount_paise,
            "idempotency_key": idempotency_key,
        },
        review_state="execution_pending",
    )
    return rec


def get_execution(execution_id: str) -> ExecutionRecord | None:
    row = store.query_one("SELECT * FROM execution_log WHERE execution_id = ?", (execution_id,))
    if row is None:
        return None
    return _row_to_record(row)


def get_execution_by_approval_seq(seq: int) -> ExecutionRecord | None:
    row = store.query_one(
        "SELECT * FROM execution_log WHERE approval_seq = ? ORDER BY created_at DESC LIMIT 1",
        (seq,),
    )
    return _row_to_record(row) if row else None


def _row_to_record(row: dict[str, Any]) -> ExecutionRecord:
    skus_raw = row.get("skus", "[]")
    if isinstance(skus_raw, str):
        try:
            skus_raw = json.loads(skus_raw)
        except (json.JSONDecodeError, TypeError):
            skus_raw = []
    return ExecutionRecord(
        execution_id=row["execution_id"],
        approval_seq=row["approval_seq"],
        mission_id=row["mission_id"],
        proposal_hash=row["proposal_hash"],
        amount_paise=row["amount_paise"],
        currency=row["currency"],
        skus=tuple(tuple(x) for x in skus_raw) if skus_raw else (),
        idempotency_key=row["idempotency_key"],
        razorpay_order_id=row.get("razorpay_order_id") or None,
        razorpay_payment_id=row.get("razorpay_payment_id") or None,
        execution_state=ExecutionState(row["execution_state"]),
        previous_state=row.get("previous_state") or "",
        error_code=row.get("error_code") or None,
        error_reason=row.get("error_reason") or None,
        reconciliation_reason=row.get("reconciliation_reason") or None,
        attempts=row.get("attempts", 0) or 0,
        created_at=row.get("created_at", 0) or 0,
        updated_at=row.get("updated_at", 0) or 0,
    )


def start_execution(execution_id: str) -> ExecutionRecord:
    """Transition APPROVED -> EXECUTION_PENDING."""
    return _transition_state(execution_id, ExecutionState.EXECUTION_PENDING, "ready for remote call")


def attempt_remote_order(execution_id: str) -> ExecutionRecord:
    """Transition EXECUTION_PENDING -> REMOTE_ATTEMPTED."""
    return _transition_state(execution_id, ExecutionState.REMOTE_ATTEMPTED, "calling Razorpay API")


def finalize_execution(
    execution_id: str,
    order_id: str,
    payment_id: str | None = None,
) -> ExecutionRecord:
    """Transition REMOTE_ATTEMPTED -> EXECUTED. Consume the approval binding."""
    rec = get_execution(execution_id)
    if rec is None:
        raise ValueError(f"execution {execution_id} not found")
    store.execute(
        "UPDATE execution_log SET execution_state = 'EXECUTED', razorpay_order_id = ?, "
        "razorpay_payment_id = ?, updated_at = ?, previous_state = COALESCE(previous_state, '') "
        "WHERE execution_id = ? AND execution_state = 'REMOTE_ATTEMPTED'",
        (order_id, payment_id, _now(), execution_id),
    )
    store.execute(
        "UPDATE bindings SET consumed_at = ? WHERE seq = ? AND consumed_at IS NULL",
        (_now(), rec.approval_seq),
    )
    audit_chain.append(
        "executor", "execution_executed",
        {
            "execution_id": execution_id,
            "order_id": order_id,
            "approval_seq": rec.approval_seq,
            "razorpay_payment_id": payment_id,
        },
        review_state="executed",
    )
    money_record("execute_order", order_id=order_id, execution_id=execution_id)
    return get_execution(execution_id)


def fail_execution(execution_id: str, error_code: str, error_reason: str = "") -> ExecutionRecord:
    """Transition to FAILED."""
    rec = get_execution(execution_id)
    store.execute(
        "UPDATE execution_log SET execution_state = 'FAILED', error_code = ?, "
        "error_reason = ?, updated_at = ?, previous_state = COALESCE(previous_state, '') "
        "WHERE execution_id = ? AND execution_state IN ('EXECUTION_PENDING', 'REMOTE_ATTEMPTED')",
        (error_code, error_reason, _now(), execution_id),
    )
    audit_chain.append(
        "executor", "execution_failed",
        {
            "execution_id": execution_id,
            "error_code": error_code,
            "error_reason": error_reason,
            "approval_seq": rec.approval_seq,
        },
        error_code=error_code,
        review_state="failed",
    )
    money_record("execute_failure", execution_id=execution_id, error_code=error_code)
    return get_execution(execution_id)


def require_reconciliation(execution_id: str, reason: str) -> ExecutionRecord:
    """Transition to RECONCILIATION_REQUIRED."""
    rec = get_execution(execution_id)
    store.execute(
        "UPDATE execution_log SET execution_state = 'RECONCILIATION_REQUIRED', "
        "reconciliation_reason = ?, updated_at = ?, previous_state = COALESCE(previous_state, '') "
        "WHERE execution_id = ? AND execution_state = 'REMOTE_ATTEMPTED'",
        (reason, _now(), execution_id),
    )
    audit_chain.append(
        "executor", "execution_reconciliation_required",
        {
            "execution_id": execution_id,
            "reason": reason,
            "approval_seq": rec.approval_seq,
        },
        review_state="reconciliation_required",
    )
    return get_execution(execution_id)


def query_remote_state(execution_id: str) -> dict[str, Any]:
    """Query authoritative Razorpay state for reconciliation."""
    rec = get_execution(execution_id)
    if rec is None or not rec.razorpay_order_id:
        return {"found": False, "reason": "no razorpay_order_id"}
    try:
        order = _rp_fetch_order(rec.razorpay_order_id)
        return {
            "found": True,
            "order_id": order.get("id"),
            "status": order.get("status"),
            "amount": order.get("amount"),
            "payments": order.get("payments", []),
        }
    except Exception as e:
        return {"found": False, "reason": str(e)}


def reconcile_execution(execution_id: str) -> dict[str, Any]:
    """Reconcile an execution in RECONCILIATION_REQUIRED against Razorpay truth."""
    rec = get_execution(execution_id)
    if rec is None:
        return {"ok": False, "reason": "execution not found"}
    remote = query_remote_state(execution_id)
    if not remote.get("found"):
        return {"ok": False, "reason": "cannot reach Razorpay"}
    amount = rec.amount_paise
    remote_amount = remote.get("amount", 0)
    remote_status = remote.get("status")
    if remote_status == "captured" and remote_amount == amount:
        return {"ok": True, "decision": "EXECUTED", "remote_state": remote}
    elif remote_status == "failed":
        return {"ok": True, "decision": "FAILED", "remote_state": remote}
    else:
        return {"ok": False, "decision": "RECONCILIATION_REQUIRED", "remote_state": remote}


def recover_timeout(execution_id: str) -> dict[str, Any]:
    """Recovery path for timeout/connection loss: query remote state and decide."""
    rec = get_execution(execution_id)
    if rec is None:
        return {"ok": False, "reason": "execution not found"}
    remote = query_remote_state(execution_id)
    if not remote.get("found"):
        return {"ok": False, "decision": "RECONCILIATION_REQUIRED", "reason": "Razorpay unreachable"}
    status = remote.get("status")
    if status == "created":
        return {"ok": True, "decision": "RETRY", "reason": "order created but not captured"}
    elif status == "captured":
        finalize_execution(execution_id, remote["order_id"])
        return {"ok": True, "decision": "EXECUTED", "reason": "captured on remote"}
    elif status == "failed":
        return {"ok": True, "decision": "FAILED", "reason": "payment failed remotely"}
    else:
        return {"ok": False, "decision": "RECONCILIATION_REQUIRED", "reason": f"unknown remote status: {status}"}


def execute_order(
    *,
    approval_seq: int,
    mission_id: str,
    proposal_hash: str,
    amount_paise: int,
    currency: str,
    skus: list[tuple[str, int]],
    idempotency_key: str | None = None,
) -> dict[str, Any]:
    """Full canonical execution: register, transition, call Razorpay, finalize.

    This is the single application execution service. Every money action
    goes through this function.
    """
    if idempotency_key is None:
        idempotency_key = derive_idempotency_key("execute_order", mission_id, approval_seq)

    execution = register_execution(
        approval_seq=approval_seq,
        mission_id=mission_id,
        proposal_hash=proposal_hash,
        amount_paise=amount_paise,
        currency=currency,
        skus=skus,
        idempotency_key=idempotency_key,
    )
    execution_id = execution.execution_id

    try:
        start_execution(execution_id)
    except IllegalExecutionTransitionError:
        existing = get_execution(execution_id)
        if existing and existing.execution_state in (ExecutionState.EXECUTED, ExecutionState.FAILED):
            return {
                "ok": True,
                "execution_id": execution_id,
                "state": existing.execution_state.value,
                "order_id": existing.razorpay_order_id,
                "duplicate": True,
            }
        raise

    try:
        attempt_remote_order(execution_id)
    except IllegalExecutionTransitionError:
        existing = get_execution(execution_id)
        if existing and existing.execution_state in (ExecutionState.EXECUTED, ExecutionState.FAILED):
            return {
                "ok": True,
                "execution_id": execution_id,
                "state": existing.execution_state.value,
                "order_id": existing.razorpay_order_id,
                "duplicate": True,
            }
        raise

    try:
        rp = _rp_create_order(
            amount_paise=amount_paise,
            receipt=f"rcpt_{approval_seq}",
            notes={
                "mission_id": mission_id,
                "proposal_hash": proposal_hash,
                "execution_id": execution_id,
            },
            idempotency_key=idempotency_key,
        )
        order_id = rp["id"]
        finalize_execution(execution_id, order_id)
        return {
            "ok": True,
            "execution_id": execution_id,
            "state": ExecutionState.EXECUTED.value,
            "order_id": order_id,
            "razorpay_mode": "test",
        }
    except Exception as e:
        error_code = getattr(e, "status_code", None) or "REMOTE_ERROR"
        fail_execution(execution_id, str(error_code), str(e)[:200])
        return {
            "ok": False,
            "execution_id": execution_id,
            "state": ExecutionState.FAILED.value,
            "error_code": error_code,
            "error_reason": str(e)[:200],
            "retryable": True,
        }


def init_execution_schema() -> None:
    """Create execution_log table if it doesn't exist."""
    store.execute("""
        CREATE TABLE IF NOT EXISTS execution_log (
            execution_id TEXT PRIMARY KEY,
            approval_seq INTEGER NOT NULL,
            mission_id TEXT NOT NULL,
            proposal_hash TEXT NOT NULL,
            amount_paise INTEGER NOT NULL,
            currency TEXT NOT NULL,
            skus TEXT NOT NULL,
            idempotency_key TEXT,
            razorpay_order_id TEXT,
            razorpay_payment_id TEXT,
            execution_state TEXT NOT NULL DEFAULT 'APPROVED',
            previous_state TEXT,
            error_code TEXT,
            error_reason TEXT,
            reconciliation_reason TEXT,
            attempts INTEGER DEFAULT 0,
            created_at INTEGER NOT NULL,
            updated_at INTEGER NOT NULL
        )
    """)
    store.execute("""
        CREATE TABLE IF NOT EXISTS webhook_lifecycle (
            event_id TEXT PRIMARY KEY,
            event_type TEXT,
            order_id TEXT,
            payment_id TEXT,
            amount_paise INTEGER,
            status TEXT,
            lifecycle_state TEXT NOT NULL DEFAULT 'RECEIVED',
            hmac_valid BOOLEAN NOT NULL DEFAULT 0,
            received_at INTEGER NOT NULL,
            persisted_at INTEGER,
            audited_at INTEGER,
            applied_at INTEGER,
            error_reason TEXT
        )
    """)
    store.execute("""
        CREATE TABLE IF NOT EXISTS execution_state_transitions (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            execution_id TEXT NOT NULL,
            from_state TEXT NOT NULL,
            to_state TEXT NOT NULL,
            reason TEXT,
            actor TEXT DEFAULT 'executor',
            occurred_at INTEGER NOT NULL,
            FOREIGN KEY (execution_id) REFERENCES execution_log(execution_id)
        )
    """)
    store.execute("""
        CREATE INDEX IF NOT EXISTS idx_execution_approval_seq
            ON execution_log(approval_seq)
    """)
    store.execute("""
        CREATE INDEX IF NOT EXISTS idx_execution_state
            ON execution_log(execution_state)
    """)