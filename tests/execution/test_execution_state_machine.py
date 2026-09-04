"""Unit tests for the durable payment execution state machine.

These cover the transition table, deterministic identity, concurrent
claiming and crash recovery — the parts that must hold before any
network call is even considered.
"""
import time

import pytest

from apps.api import execution as ex


def _open(seq=1, mission="m-exec", phash="a" * 64, amount=149900):
    return ex.open_execution(
        mission_id=mission, proposal_hash=phash, approve_seq=seq,
        quote_id="q-1", amount_paise=amount, currency="INR",
        idempotency_key=f"idem_{seq}", provider="simulated")


def test_execution_id_is_deterministic_and_time_independent():
    a = ex.derive_execution_id("m1", "h" * 64, 7)
    time.sleep(0.01)
    b = ex.derive_execution_id("m1", "h" * 64, 7)
    assert a == b
    assert a != ex.derive_execution_id("m1", "h" * 64, 8)
    assert a != ex.derive_execution_id("m2", "h" * 64, 7)


def test_open_execution_is_idempotent_claim():
    row1, created1 = _open(seq=11)
    row2, created2 = _open(seq=11)
    assert created1 is True
    assert created2 is False, "a second claim must not create a second execution"
    assert row1["execution_id"] == row2["execution_id"]
    assert len(ex.list_executions()) == 1


def test_concurrent_open_yields_exactly_one_execution():
    """Two racing requests must not open two payment attempts."""
    import threading

    results = []
    barrier = threading.Barrier(8)

    def worker():
        barrier.wait()
        try:
            results.append(_open(seq=42)[1])
        except Exception as exc:  # pragma: no cover
            results.append(exc)

    threads = [threading.Thread(target=worker) for _ in range(8)]
    for t in threads:
        t.start()
    for t in threads:
        t.join()

    assert results.count(True) == 1, f"exactly one claim must win: {results}"
    assert len(ex.list_executions()) == 1


def test_happy_path_transitions():
    _open(seq=21)
    eid = ex.derive_execution_id("m-exec", "a" * 64, 21)
    ex.transition(eid, ex.EXECUTION_PENDING)
    ex.transition(eid, ex.REMOTE_ATTEMPTED)
    row = ex.transition(eid, ex.EXECUTED, remote_order_id="order_sim_x")
    assert row["state"] == ex.EXECUTED
    assert row["remote_order_id"] == "order_sim_x"
    assert row["terminal_at"] is not None
    assert row["attempts"] == 1


@pytest.mark.parametrize("path", [
    (ex.EXECUTED,),                                  # APPROVED -> EXECUTED
    (ex.REMOTE_ATTEMPTED,),                          # APPROVED -> REMOTE_ATTEMPTED
    (ex.RECONCILIATION_REQUIRED,),                   # APPROVED -> RECONCILIATION_REQUIRED
])
def test_illegal_transitions_are_refused(path):
    _open(seq=31)
    eid = ex.derive_execution_id("m-exec", "a" * 64, 31)
    with pytest.raises(ex.IllegalTransition):
        for target in path:
            ex.transition(eid, target)


def test_terminal_states_are_absorbing():
    _open(seq=32)
    eid = ex.derive_execution_id("m-exec", "a" * 64, 32)
    ex.transition(eid, ex.EXECUTION_PENDING)
    ex.transition(eid, ex.REMOTE_ATTEMPTED)
    ex.transition(eid, ex.FAILED, remote_error_code="BAD_REQUEST_ERROR")
    with pytest.raises(ex.IllegalTransition):
        ex.transition(eid, ex.EXECUTED)


def test_ambiguous_outcome_never_becomes_success_or_failure_by_itself():
    _open(seq=33)
    eid = ex.derive_execution_id("m-exec", "a" * 64, 33)
    ex.transition(eid, ex.EXECUTION_PENDING)
    ex.transition(eid, ex.REMOTE_ATTEMPTED)
    row = ex.transition(eid, ex.RECONCILIATION_REQUIRED, last_error="timeout")
    assert row["state"] == ex.RECONCILIATION_REQUIRED
    assert row["terminal_at"] is None, "ambiguity is not a terminal outcome"
    assert row["reconciled_at"] is None


def test_reconciliation_records_when_it_resolved():
    _open(seq=34)
    eid = ex.derive_execution_id("m-exec", "a" * 64, 34)
    ex.transition(eid, ex.EXECUTION_PENDING)
    ex.transition(eid, ex.REMOTE_ATTEMPTED)
    ex.transition(eid, ex.RECONCILIATION_REQUIRED)
    row = ex.transition(eid, ex.EXECUTED, remote_order_id="order_sim_y")
    assert row["reconciled_at"] is not None
    assert row["terminal_at"] is not None


def test_crash_recovery_moves_in_flight_executions_to_reconciliation():
    """A process that dies mid-call must not lose the fact that it dispatched."""
    _open(seq=51)
    eid = ex.derive_execution_id("m-exec", "a" * 64, 51)
    ex.transition(eid, ex.EXECUTION_PENDING)
    ex.transition(eid, ex.REMOTE_ATTEMPTED)
    # <- process dies here; nothing else is written

    moved = ex.recover_stranded()

    assert moved == [eid]
    assert ex.get(eid)["state"] == ex.RECONCILIATION_REQUIRED
    assert "restarted" in ex.get(eid)["last_error"]


def test_recovery_leaves_undispatched_executions_alone():
    """EXECUTION_PENDING was never dispatched — it is safe, not ambiguous."""
    _open(seq=52)
    eid = ex.derive_execution_id("m-exec", "a" * 64, 52)
    ex.transition(eid, ex.EXECUTION_PENDING)

    assert ex.recover_stranded() == []
    assert ex.get(eid)["state"] == ex.EXECUTION_PENDING


def test_recovery_is_idempotent_across_repeated_boots():
    _open(seq=53)
    eid = ex.derive_execution_id("m-exec", "a" * 64, 53)
    ex.transition(eid, ex.EXECUTION_PENDING)
    ex.transition(eid, ex.REMOTE_ATTEMPTED)
    assert ex.recover_stranded() == [eid]
    assert ex.recover_stranded() == []
    assert ex.get(eid)["state"] == ex.RECONCILIATION_REQUIRED


def test_summary_counts_every_state():
    summary = ex.summary()
    assert set(summary) == set(ex.ALL_STATES)
    assert all(v == 0 for v in summary.values())
