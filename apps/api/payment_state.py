"""
Explicit Payment State Machine and Reconciliation Service for SELLABLE.

Implements Section 14, 15, 16:
- Explicit Payment States: DRAFT, AWAITING_APPROVAL, PAYMENT_PENDING, PAID, PAYMENT_FAILED, NEEDS_RECONCILIATION, ABANDONED, REFUNDED
- Bounded reconciliation against gateway truth on timeout
- Strict transition validation (no illegal state transitions)
"""
import enum
import time

try:
    from enum import StrEnum
except ImportError:

    class StrEnum(enum.StrEnum):
        pass

from typing import Any


class PaymentState(StrEnum):
    DRAFT = "DRAFT"
    AWAITING_APPROVAL = "AWAITING_APPROVAL"
    PAYMENT_PENDING = "PAYMENT_PENDING"
    PAID = "PAID"
    PAYMENT_FAILED = "PAYMENT_FAILED"
    NEEDS_RECONCILIATION = "NEEDS_RECONCILIATION"
    ABANDONED = "ABANDONED"
    REFUNDED = "REFUNDED"

VALID_TRANSITIONS = {
    PaymentState.DRAFT: {PaymentState.AWAITING_APPROVAL, PaymentState.ABANDONED},
    PaymentState.AWAITING_APPROVAL: {PaymentState.PAYMENT_PENDING, PaymentState.ABANDONED},
    PaymentState.PAYMENT_PENDING: {PaymentState.PAID, PaymentState.PAYMENT_FAILED, PaymentState.NEEDS_RECONCILIATION},
    PaymentState.PAYMENT_FAILED: {PaymentState.PAYMENT_PENDING, PaymentState.ABANDONED, PaymentState.NEEDS_RECONCILIATION},
    PaymentState.NEEDS_RECONCILIATION: {PaymentState.PAID, PaymentState.PAYMENT_FAILED, PaymentState.REFUNDED},
    PaymentState.PAID: {PaymentState.REFUNDED},
    PaymentState.REFUNDED: set(),
    PaymentState.ABANDONED: set(),
}

class IllegalStateTransitionError(ValueError):
    pass

class PaymentStateMachine:
    def __init__(self, initial_state: PaymentState = PaymentState.DRAFT):
        self.state = initial_state
        self.history: list[dict[str, Any]] = [{"state": initial_state, "timestamp": int(time.time()), "reason": "initial"}]

    def transition(self, target_state: PaymentState, reason: str = "") -> PaymentState:
        if target_state not in VALID_TRANSITIONS.get(self.state, set()):
            raise IllegalStateTransitionError(
                f"Illegal state transition from {self.state} to {target_state}. Valid targets: {VALID_TRANSITIONS.get(self.state)}"
            )
        self.state = target_state
        self.history.append({"state": target_state, "timestamp": int(time.time()), "reason": reason})
        return self.state

def reconcile_order(order_id: str, expected_amount_paise: int, gateway_payments: list[dict[str, Any]]) -> tuple[PaymentState, str]:
    """
    Reconciliation against gateway truth:
    - If gateway shows captured payment matching exact expected amount -> PAID
    - If gateway shows captured payment with wrong amount -> NEEDS_RECONCILIATION
    - If gateway shows only failed payments -> PAYMENT_FAILED
    - If no payments found -> PAYMENT_PENDING
    """
    if not gateway_payments:
        return PaymentState.PAYMENT_PENDING, "No payments recorded on gateway"

    for p in gateway_payments:
        if p.get("status") == "captured":
            actual_amount = p.get("amount")
            if actual_amount == expected_amount_paise:
                return PaymentState.PAID, f"Payment {p.get('id')} captured and verified for exact amount {expected_amount_paise}"
            else:
                return PaymentState.NEEDS_RECONCILIATION, f"Amount mismatch: expected {expected_amount_paise}, got {actual_amount}"

    if all(p.get("status") == "failed" for p in gateway_payments):
        return PaymentState.PAYMENT_FAILED, "All gateway payment attempts failed"

    return PaymentState.NEEDS_RECONCILIATION, "Gateway state ambiguous, requires review"
