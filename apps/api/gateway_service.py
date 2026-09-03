"""
Canonical Payment Gateway Service & Abstraction for SELLABLE.

Implements Section 3 & 4:
- PaymentGateway Protocol
- RazorpayTestGateway: Real Razorpay Test Mode API integration
- SimulatorGateway: Deterministic Fault-Injection harness with explicit simulation modes
"""
import enum
import hashlib
import time

try:
    from enum import StrEnum
except ImportError:

    class StrEnum(enum.StrEnum):
        pass

from typing import Any, Protocol

from . import money, razorpay_client


class GatewayMode(StrEnum):
    NORMAL = "NORMAL"
    CREATE_ORDER_TIMEOUT = "CREATE_ORDER_TIMEOUT"
    CREATE_ORDER_TRANSIENT_FAILURE = "CREATE_ORDER_TRANSIENT_FAILURE"
    PAYMENT_FAILED = "PAYMENT_FAILED"
    PAYMENT_PENDING = "PAYMENT_PENDING"
    WEBHOOK_DROPPED = "WEBHOOK_DROPPED"
    PAYMENT_CAPTURED_BUT_RESPONSE_LOST = "PAYMENT_CAPTURED_BUT_RESPONSE_LOST"
    GATEWAY_500 = "GATEWAY_500"
    GATEWAY_429 = "GATEWAY_429"
    AMOUNT_MISMATCH = "AMOUNT_MISMATCH"
    ORDER_NOT_FOUND = "ORDER_NOT_FOUND"

class GatewayException(Exception):
    def __init__(self, code: str, message: str, status_code: int = 400):
        super().__init__(message)
        self.code = code
        self.message = message
        self.status_code = status_code

class PaymentGateway(Protocol):
    def create_order(self, amount_paise: int, receipt: str, notes: dict[str, Any], idempotency_key: str | None = None) -> dict[str, Any]:
        ...

    def fetch_order(self, order_id: str) -> dict[str, Any]:
        ...

    def list_order_payments(self, order_id: str) -> list[dict[str, Any]]:
        ...

class RazorpayTestGateway:
    """The canonical real Razorpay Test-Mode gateway implementation."""
    def create_order(self, amount_paise: int, receipt: str, notes: dict[str, Any], idempotency_key: str | None = None) -> dict[str, Any]:
        return razorpay_client.create_order(amount_paise, receipt, notes, idempotency_key=idempotency_key)

    def fetch_order(self, order_id: str) -> dict[str, Any]:
        return razorpay_client.fetch_order(order_id)

    def list_order_payments(self, order_id: str) -> list[dict[str, Any]]:
        return razorpay_client.list_order_payments(order_id)

class SimulatorGateway:
    """Deterministic simulation and fault-injection harness."""
    def __init__(self, mode: GatewayMode = GatewayMode.NORMAL):
        self.mode = mode
        self._orders: dict[str, dict[str, Any]] = {}
        self._payments: dict[str, list[dict[str, Any]]] = {}

    def set_mode(self, mode: GatewayMode):
        self.mode = mode

    def create_order(self, amount_paise: int, receipt: str, notes: dict[str, Any], idempotency_key: str | None = None) -> dict[str, Any]:
        money.record("simulator_create_order", amount_paise=amount_paise, mode=self.mode)

        if self.mode == GatewayMode.CREATE_ORDER_TIMEOUT:
            raise GatewayException("GATEWAY_TIMEOUT", "Simulated gateway read timeout (30s exceeded)", 504)
        if self.mode == GatewayMode.CREATE_ORDER_TRANSIENT_FAILURE:
            raise GatewayException("TRANSIENT_ERROR", "Simulated transient connection reset by peer", 503)
        if self.mode == GatewayMode.GATEWAY_500:
            raise GatewayException("INTERNAL_GATEWAY_ERROR", "Simulated 500 upstream server error", 500)
        if self.mode == GatewayMode.GATEWAY_429:
            raise GatewayException("RATE_LIMIT_EXCEEDED", "Simulated 429 too many requests", 429)

        order_id = f"order_sim_{hashlib.sha256((receipt + str(amount_paise)).encode()).hexdigest()[:14]}"
        order_obj = {
            "id": order_id,
            "entity": "order",
            "amount": amount_paise,
            "amount_paid": 0,
            "amount_due": amount_paise,
            "currency": "INR",
            "receipt": receipt,
            "status": "created",
            "attempts": 0,
            "notes": notes,
            "created_at": int(time.time()),
        }
        self._orders[order_id] = order_obj
        self._payments[order_id] = []
        return order_obj

    def fetch_order(self, order_id: str) -> dict[str, Any]:
        if self.mode == GatewayMode.ORDER_NOT_FOUND or order_id not in self._orders:
            raise GatewayException("ORDER_NOT_FOUND", f"Simulated order {order_id} not found", 404)
        return self._orders[order_id]

    def list_order_payments(self, order_id: str) -> list[dict[str, Any]]:
        if self.mode == GatewayMode.PAYMENT_FAILED:
            return [{"id": f"pay_fail_{order_id}", "status": "failed", "method": "upi", "error_code": "BAD_REQUEST_ERROR", "error_description": "Simulated payment declined by issuing bank"}]
        if self.mode == GatewayMode.PAYMENT_PENDING:
            return []
        if self.mode == GatewayMode.AMOUNT_MISMATCH:
            return [{"id": f"pay_mismatch_{order_id}", "status": "captured", "amount": 99900, "currency": "INR", "method": "upi"}]
        return self._payments.get(order_id, [{"id": f"pay_sim_{order_id}", "status": "captured", "amount": self._orders.get(order_id, {}).get("amount", 0), "currency": "INR", "method": "upi"}])

_REAL_GATEWAY = RazorpayTestGateway()
_SIMULATOR = SimulatorGateway()
_ACTIVE_GATEWAY: PaymentGateway = _REAL_GATEWAY

def get_gateway() -> PaymentGateway:
    return _ACTIVE_GATEWAY

def set_gateway(gateway: PaymentGateway):
    global _ACTIVE_GATEWAY
    _ACTIVE_GATEWAY = gateway

def use_simulator(mode: GatewayMode = GatewayMode.NORMAL) -> SimulatorGateway:
    global _ACTIVE_GATEWAY
    _SIMULATOR.set_mode(mode)
    _ACTIVE_GATEWAY = _SIMULATOR
    return _SIMULATOR

def use_real_gateway() -> RazorpayTestGateway:
    global _ACTIVE_GATEWAY
    _ACTIVE_GATEWAY = _REAL_GATEWAY
    return _REAL_GATEWAY
