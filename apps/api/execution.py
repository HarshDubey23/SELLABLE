"""Durable payment execution state machine.

WHY THIS EXISTS
---------------
An approval binding answers "is this payment authorized?". It does NOT
answer "did this payment happen?". Conflating the two is the classic
agentic-payments bug:

    verify_binding()      # authorization consumed, irreversibly
    razorpay.create_order()  # <-- times out
    # ...authorization is now destroyed, no order recorded, and nobody
    #    knows whether Razorpay created the order or not.

A network timeout is not a failure. It is an *unknown*. If the local
process treats it as a failure it can double-charge on retry; if it
treats it as a success it can ship goods that were never paid for.
The only correct move is to record the ambiguity durably and resolve it
against the remote system's authoritative state.

THE STATE MACHINE
-----------------
    APPROVED
       |                      binding verified, execution row created
       v
    EXECUTION_PENDING
       |                      idempotency key fixed; nothing dispatched yet
       v
    REMOTE_ATTEMPTED          <-- written to disk BEFORE the network call
       |
       +--> EXECUTED                    remote returned a definitive success
       +--> FAILED                      remote returned a definitive error
       +--> RECONCILIATION_REQUIRED     outcome unknown (timeout/connection)
                |
                +--> EXECUTED           reconciler found the order remotely
                +--> FAILED             reconciler proved no order exists

Ordering is the whole point. REMOTE_ATTEMPTED is committed to SQLite
*before* the HTTP request leaves the process, so a crash mid-flight is
indistinguishable-from-ambiguous rather than indistinguishable-from-
nothing-happened. At boot, `recover_stranded()` sweeps every row still
sitting in REMOTE_ATTEMPTED into RECONCILIATION_REQUIRED: the process
died while a payment was in flight, and that fact survived the crash.

EXECUTION_PENDING rows are the safe case: the key was fixed but nothing
was dispatched, so they can be retried without risk.

IDEMPOTENCY
-----------
`execution_id` is derived deterministically from (mission_id,
proposal_hash, approve_seq) — the same authorized intent always maps to
the same execution row, so a duplicate request finds the existing row
instead of starting a second payment. The row is claimed with an atomic
INSERT (UNIQUE primary key), so two concurrent requests cannot both open
an execution: exactly one INSERT wins and the loser reads the winner's
row.

We do NOT assume the remote API's idempotency header guarantees
end-to-end safety. It is sent, but reconciliation queries authoritative
remote state and matches on our own correlation fields.
"""
from __future__ import annotations

import hashlib
import sqlite3
import time
from typing import Any

from .store import db as store

# ---------------------------------------------------------------- states

APPROVED = "APPROVED"
EXECUTION_PENDING = "EXECUTION_PENDING"
REMOTE_ATTEMPTED = "REMOTE_ATTEMPTED"
EXECUTED = "EXECUTED"
FAILED = "FAILED"
RECONCILIATION_REQUIRED = "RECONCILIATION_REQUIRED"

ALL_STATES = (
    APPROVED,
    EXECUTION_PENDING,
    REMOTE_ATTEMPTED,
    EXECUTED,
    FAILED,
    RECONCILIATION_REQUIRED,
)

TERMINAL_STATES = frozenset({EXECUTED, FAILED})

# Recorded in `remote_error_code` when we have ground truth that the
# request never left this process. Reconciliation may then treat an empty
# authoritative read as conclusive instead of waiting out the provider's
# consistency window — there is nothing for a listing to be behind on if
# nothing was ever sent. Absence of this marker means "we do not know",
# which is the safe default.
NEVER_DISPATCHED = "NEVER_DISPATCHED"

VALID_TRANSITIONS: dict[str, frozenset[str]] = {
    APPROVED: frozenset({EXECUTION_PENDING, FAILED}),
    EXECUTION_PENDING: frozenset({REMOTE_ATTEMPTED, FAILED}),
    REMOTE_ATTEMPTED: frozenset({EXECUTED, FAILED, RECONCILIATION_REQUIRED}),
    RECONCILIATION_REQUIRED: frozenset({EXECUTED, FAILED}),
    EXECUTED: frozenset(),
    FAILED: frozenset(),
}


class IllegalTransition(RuntimeError):
    """Raised when code attempts a transition the machine forbids."""


class AmbiguousRemoteOutcome(Exception):
    """The remote call's outcome is unknown — never treat as success or failure.

    Raised for timeouts, connection resets and unparseable responses:
    every case where the request may or may not have been executed by
    the remote system.

    `dispatched` says whether the request is known to have left this
    process. It defaults to True, which is the safe direction: if we do
    not know, we must assume the provider may have acted on it, and
    reconciliation has to allow for the provider's listing being
    eventually consistent before concluding anything.

    It is only False where we have ground truth that nothing was sent —
    today that is the `remote_lost` drill, which raises before the call
    by construction. A real ConnectionError is NOT such a case: the
    socket may have been written before it broke.
    """

    def __init__(self, message: str, *, dispatched: bool = True):
        super().__init__(message)
        self.dispatched = dispatched


class DefiniteRemoteFailure(Exception):
    """The remote system definitively refused. Safe to mark FAILED."""

    def __init__(self, code: str, message: str):
        self.code = code
        super().__init__(f"{code}: {message}")


# ------------------------------------------------------------------ ids

def derive_execution_id(mission_id: str, proposal_hash: str,
                        approve_seq: int) -> str:
    """Deterministic id for one authorized intent.

    Same authorization => same execution row => a replay can never open a
    second payment attempt. Never includes wall-clock time.
    """
    raw = f"{mission_id}|{proposal_hash}|{approve_seq}"
    return "exec_" + hashlib.sha256(raw.encode()).hexdigest()[:32]


# --------------------------------------------------------------- writes

def open_execution(*, mission_id: str, proposal_hash: str, approve_seq: int,
                   quote_id: str, amount_paise: int, currency: str,
                   idempotency_key: str, provider: str,
                   now_ts: int | None = None) -> tuple[dict[str, Any], bool]:
    """Atomically claim an execution row.

    Returns (row, created). `created` is False when a row for this
    authorization already existed — the caller MUST then inspect its
    state rather than starting a second attempt.
    """
    now_ts = now_ts if now_ts is not None else int(time.time())
    execution_id = derive_execution_id(mission_id, proposal_hash, approve_seq)

    try:
        store.execute(
            "INSERT INTO payment_executions "
            "(execution_id, mission_id, approve_seq, proposal_hash, quote_id, "
            " amount_paise, currency, idempotency_key, state, provider, "
            " attempts, created_at, updated_at) "
            "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 0, ?, ?)",
            (execution_id, mission_id, approve_seq, proposal_hash, quote_id,
             amount_paise, currency, idempotency_key, APPROVED, provider,
             now_ts, now_ts),
        )
        created = True
    except sqlite3.IntegrityError:
        # Another request already claimed this authorization.
        created = False

    row = get(execution_id)
    if row is None:  # pragma: no cover - only if the DB vanished mid-call
        raise RuntimeError(f"execution row {execution_id} disappeared")
    return row, created


def transition(execution_id: str, target: str, *,
               remote_order_id: str | None = None,
               remote_error_code: str | None = None,
               last_error: str | None = None,
               now_ts: int | None = None) -> dict[str, Any]:
    """Move one execution to `target`, enforcing the transition table.

    The UPDATE carries the expected current state in its WHERE clause, so
    two concurrent writers cannot both apply the same transition.
    """
    now_ts = now_ts if now_ts is not None else int(time.time())
    row = get(execution_id)
    if row is None:
        raise IllegalTransition(f"unknown execution {execution_id}")

    current = row["state"]
    if target not in VALID_TRANSITIONS.get(current, frozenset()):
        raise IllegalTransition(
            f"{execution_id}: {current} -> {target} is not a legal transition "
            f"(allowed: {sorted(VALID_TRANSITIONS.get(current, ()))})"
        )

    terminal_at = now_ts if target in TERMINAL_STATES else row.get("terminal_at")
    reconciled_at = row.get("reconciled_at")
    if current == RECONCILIATION_REQUIRED and target in TERMINAL_STATES:
        reconciled_at = now_ts

    attempts = row["attempts"] + (1 if target == REMOTE_ATTEMPTED else 0)

    affected = store.execute_rowcount(
        "UPDATE payment_executions SET state = ?, remote_order_id = ?, "
        "remote_error_code = ?, last_error = ?, attempts = ?, updated_at = ?, "
        "terminal_at = ?, reconciled_at = ? "
        "WHERE execution_id = ? AND state = ?",
        (target,
         remote_order_id if remote_order_id is not None else row.get("remote_order_id"),
         remote_error_code if remote_error_code is not None else row.get("remote_error_code"),
         last_error if last_error is not None else row.get("last_error"),
         attempts, now_ts, terminal_at, reconciled_at,
         execution_id, current),
    )
    if affected != 1:
        raise IllegalTransition(
            f"{execution_id}: state changed concurrently (expected {current})"
        )

    updated = get(execution_id)
    assert updated is not None
    return updated


# ---------------------------------------------------------------- reads

def get(execution_id: str) -> dict[str, Any] | None:
    return store.query_one(
        "SELECT * FROM payment_executions WHERE execution_id = ?",
        (execution_id,),
    )


def list_executions(state: str | None = None,
                    limit: int = 100) -> list[dict[str, Any]]:
    if state:
        return store.query(
            "SELECT * FROM payment_executions WHERE state = ? "
            "ORDER BY created_at DESC LIMIT ?", (state, limit))
    return store.query(
        "SELECT * FROM payment_executions ORDER BY created_at DESC LIMIT ?",
        (limit,))


def stranded() -> list[dict[str, Any]]:
    """Executions that need human or automated resolution."""
    return store.query(
        "SELECT * FROM payment_executions WHERE state IN (?, ?) "
        "ORDER BY created_at",
        (REMOTE_ATTEMPTED, RECONCILIATION_REQUIRED),
    )


def summary() -> dict[str, int]:
    rows = store.query(
        "SELECT state, COUNT(*) AS c FROM payment_executions GROUP BY state")
    counts = {s: 0 for s in ALL_STATES}
    for r in rows:
        counts[r["state"]] = r["c"]
    return counts


# ------------------------------------------------------------- recovery

def recover_stranded(now_ts: int | None = None) -> list[str]:
    """Boot sweep: a REMOTE_ATTEMPTED row means the process died in flight.

    We cannot know whether the remote system executed the request, so the
    row becomes RECONCILIATION_REQUIRED — never EXECUTED, never FAILED.
    Returns the execution ids that were moved.
    """
    now_ts = now_ts if now_ts is not None else int(time.time())
    moved: list[str] = []
    for row in store.query(
            "SELECT execution_id FROM payment_executions WHERE state = ?",
            (REMOTE_ATTEMPTED,)):
        try:
            transition(
                row["execution_id"], RECONCILIATION_REQUIRED,
                last_error="process restarted while remote call was in flight",
                now_ts=now_ts,
            )
            moved.append(row["execution_id"])
        except IllegalTransition:  # pragma: no cover - raced with a live call
            continue
    return moved
