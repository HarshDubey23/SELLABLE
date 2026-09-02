# -*- coding: utf-8 -*-
import pytest
from apps.api.payment_state import PaymentState, PaymentStateMachine, IllegalStateTransitionError, reconcile_order

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
