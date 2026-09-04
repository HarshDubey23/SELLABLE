import pytest

from apps.api.payment_state import (
    IllegalStateTransitionError,
    PaymentState,
    PaymentStateMachine,
    reconcile_order,
)


def test_valid_state_transitions():
    sm = PaymentStateMachine(PaymentState.DRAFT)
    assert sm.state == PaymentState.DRAFT
    sm.transition(PaymentState.AWAITING_APPROVAL, "user submitted mission")
    assert sm.state == PaymentState.AWAITING_APPROVAL
    sm.transition(PaymentState.PAYMENT_PENDING, "binding authorized and order created")
    assert sm.state == PaymentState.PAYMENT_PENDING
    sm.transition(PaymentState.PAID, "webhook captured payment")
    assert sm.state == PaymentState.PAID
    sm.transition(PaymentState.REFUNDED, "merchant refund")
    assert sm.state == PaymentState.REFUNDED

def test_invalid_state_transitions():
    sm = PaymentStateMachine(PaymentState.DRAFT)
    # Cannot jump straight from DRAFT to PAID
    with pytest.raises(IllegalStateTransitionError):
        sm.transition(PaymentState.PAID)

    sm.transition(PaymentState.AWAITING_APPROVAL)
    # Cannot jump from AWAITING_APPROVAL to REFUNDED
    with pytest.raises(IllegalStateTransitionError):
        sm.transition(PaymentState.REFUNDED)

def test_reconciliation_exact_captured():
    state, reason = reconcile_order("order_123", 149900, [{"id": "pay_1", "status": "captured", "amount": 149900}])
    assert state == PaymentState.PAID
    assert "captured and verified" in reason

def test_reconciliation_amount_mismatch():
    state, reason = reconcile_order("order_123", 149900, [{"id": "pay_1", "status": "captured", "amount": 99900}])
    assert state == PaymentState.NEEDS_RECONCILIATION
    assert "Amount mismatch" in reason

def test_reconciliation_all_failed():
    state, reason = reconcile_order("order_123", 149900, [{"id": "pay_1", "status": "failed"}])
    assert state == PaymentState.PAYMENT_FAILED
    assert "failed" in reason

def test_reconciliation_no_payments():
    state, reason = reconcile_order("order_123", 149900, [])
    assert state == PaymentState.PAYMENT_PENDING


# ─────────────────────────────────────────────────────────────────────
# Regression: a list endpoint is not read-your-writes consistent.
#
# Found by running the failure drill against the real Razorpay test API:
# `remote_timeout` dispatched the order, we lost the response on purpose,
# and reconciling seventeen seconds later read /v1/orders, did not see the
# order, and marked the execution FAILED. The order existed the whole
# time. "I did not see it" is not "it is not there", and only the second
# statement justifies writing off a payment.
# ─────────────────────────────────────────────────────────────────────

def test_absence_soon_after_the_attempt_is_not_treated_as_failure(monkeypatch):
    """A live provider that has not listed the order yet must not close it."""
    import time as _time

    from fastapi.testclient import TestClient

    from apps.api import execution as ex
    from apps.api import execution_provider as provider_mod

    monkeypatch.setenv("RAZORPAY_KEY_ID", "rzp_test_realish")
    monkeypatch.setenv("RAZORPAY_KEY_SECRET", "realish_secret")

    class BlindProvider:
        """A live-mode provider whose listing has not caught up yet."""
        name = provider_mod.LIVE_TEST

        def create_order(self, **kw):  # pragma: no cover - not used here
            raise AssertionError("reconciliation must not create orders")

        def find_order_by_correlation(self, **kw):
            return None

    monkeypatch.setattr(provider_mod, "get_provider", lambda: BlindProvider())

    from apps.api.main import app
    client = TestClient(app)

    now = int(_time.time())
    row, _ = ex.open_execution(
        mission_id="MSN-QUIET-1", proposal_hash="q" * 64, approve_seq=910001,
        quote_id="q-quiet", amount_paise=149900, currency="INR",
        idempotency_key="idem-quiet-1", provider=provider_mod.LIVE_TEST,
        now_ts=now)
    eid = row["execution_id"]
    ex.transition(eid, ex.EXECUTION_PENDING, now_ts=now)
    ex.transition(eid, ex.REMOTE_ATTEMPTED, now_ts=now)
    ex.transition(eid, ex.RECONCILIATION_REQUIRED, now_ts=now,
                  last_error="response lost")

    r = client.post(f"/executions/{eid}/reconcile",
                    headers={"X-API-Key": "test_app_api_key"})

    assert r.status_code == 202, r.text
    err = r.json()["detail"]["error"]
    assert err["error_code"] == "ABSENCE_NOT_YET_CONCLUSIVE"
    assert err["retryable"] is True
    assert err["retry_after_seconds"] > 0
    assert ex.get(eid)["state"] == ex.RECONCILIATION_REQUIRED, \
        "an inconclusive read must leave the execution exactly where it was"


def test_absence_after_the_quiet_period_does_resolve_to_failed(monkeypatch):
    """The guard delays the conclusion; it must not prevent it forever."""
    import time as _time

    from fastapi.testclient import TestClient

    from apps.api import execution as ex
    from apps.api import execution_provider as provider_mod

    monkeypatch.setenv("RAZORPAY_KEY_ID", "rzp_test_realish")
    monkeypatch.setenv("RAZORPAY_KEY_SECRET", "realish_secret")

    class BlindProvider:
        name = provider_mod.LIVE_TEST

        def create_order(self, **kw):  # pragma: no cover
            raise AssertionError("reconciliation must not create orders")

        def find_order_by_correlation(self, **kw):
            return None

    monkeypatch.setattr(provider_mod, "get_provider", lambda: BlindProvider())

    from apps.api.main import app
    client = TestClient(app)

    stale = int(_time.time()) - provider_mod.ABSENCE_QUIET_PERIOD_SECONDS - 30
    row, _ = ex.open_execution(
        mission_id="MSN-QUIET-2", proposal_hash="r" * 64, approve_seq=910002,
        quote_id="q-quiet-2", amount_paise=149900, currency="INR",
        idempotency_key="idem-quiet-2", provider=provider_mod.LIVE_TEST,
        now_ts=stale)
    eid = row["execution_id"]
    ex.transition(eid, ex.EXECUTION_PENDING, now_ts=stale)
    ex.transition(eid, ex.REMOTE_ATTEMPTED, now_ts=stale)
    ex.transition(eid, ex.RECONCILIATION_REQUIRED, now_ts=stale,
                  last_error="response lost")

    r = client.post(f"/executions/{eid}/reconcile",
                    headers={"X-API-Key": "test_app_api_key"})

    assert r.status_code == 200, r.text
    assert r.json()["state"] == ex.FAILED
    assert r.json()["resolution"] == "NO_REMOTE_ORDER"


def test_the_simulated_provider_is_authoritative_immediately(monkeypatch):
    """The quiet period is a property of a remote listing, not of the machine.

    The in-process simulator knows its own writes, so `remote_lost` must
    still resolve to FAILED on the first ask — otherwise the keyless demo
    would be stuck waiting for a consistency window that does not exist.
    """
    from fastapi.testclient import TestClient

    from apps.api import execution as ex

    monkeypatch.setenv("RAZORPAY_KEY_ID", "")
    monkeypatch.setenv("RAZORPAY_KEY_SECRET", "")
    from apps.api.main import app
    client = TestClient(app)

    body = client.post("/discovery/checkout", json={
        "sku": "BAT-001", "budget_paise": 300000, "fault": "remote_lost"}).json()
    assert body["execution_state"] == ex.RECONCILIATION_REQUIRED

    out = client.post(f"/discovery/reconcile/{body['execution_id']}").json()
    assert out["state"] == ex.FAILED
    assert out["resolution"] == "NO_REMOTE_ORDER"


def test_a_request_that_never_left_resolves_immediately(monkeypatch):
    """The quiet period is about a listing being behind, not about waiting.

    `remote_lost` raises before the provider call by construction, so we
    have ground truth that nothing was dispatched. There is nothing for an
    eventually-consistent listing to be behind on, and making a reviewer
    wait two minutes for a conclusion we can already draw would be
    caution theatre rather than caution.
    """
    from fastapi.testclient import TestClient

    from apps.api import execution as ex
    from apps.api import execution_provider as provider_mod

    monkeypatch.setenv("RAZORPAY_KEY_ID", "rzp_test_realish")
    monkeypatch.setenv("RAZORPAY_KEY_SECRET", "realish_secret")

    class NeverListsAnything:
        name = provider_mod.LIVE_TEST

        def create_order(self, **kw):
            raise ex.AmbiguousRemoteOutcome(
                "simulated connection reset before dispatch", dispatched=False)

        def find_order_by_correlation(self, **kw):
            return None

    monkeypatch.setattr(provider_mod, "get_provider", lambda: NeverListsAnything())

    from apps.api.main import app
    client = TestClient(app)

    body = client.post("/discovery/checkout", json={
        "sku": "BAT-001", "budget_paise": 300000, "fault": "remote_lost"}).json()
    assert body["execution_state"] == ex.RECONCILIATION_REQUIRED

    row = ex.get(body["execution_id"])
    assert row["remote_error_code"] == ex.NEVER_DISPATCHED, \
        "the executor must record that nothing was sent"

    out = client.post(f"/discovery/reconcile/{body['execution_id']}").json()
    assert out["state"] == ex.FAILED, \
        "an undispatched request resolves on the first ask, not after a wait"
    assert "never dispatched" in out["explanation"]


def test_an_unknown_dispatch_state_still_waits(monkeypatch):
    """The default is caution: a real reset may have written the socket."""
    from apps.api import execution as ex

    exc = ex.AmbiguousRemoteOutcome("ConnectionError: may have reached Razorpay")
    assert exc.dispatched is True, (
        "AmbiguousRemoteOutcome must default to 'possibly dispatched'; a real "
        "connection error is not evidence that nothing was sent")
