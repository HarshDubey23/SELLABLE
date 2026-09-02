"""Money-call invariant instrumentation.

Counts every call to the Razorpay boundary module. Used by tests and the
Attack Lab UI to PROVE the central security invariant:

    rejected/binding-invalid/mandate-invalid => 0 Razorpay calls

The counter is a module-level singleton so it survives across the same
process. Tests reset it via reset(); the UI reads it via snapshot().

The snapshot's `total` excludes "binding_*" events — those are
instrumentation records emitted by the binding verifier to PROVE a
rejection happened, not actual Razorpay calls. The real Razorpay
boundary calls (create_order, create_upi_payment, capture_payment,
etc.) live under `boundary_calls`.
"""
from __future__ import annotations

import threading
from collections import defaultdict
from typing import Any

# Real Razorpay boundary operations — counted as money boundary calls.
_BOUNDARY_OPS = {
    "create_order",
    "create_upi_payment",
    "create_payment_link",
    "capture_payment",
    "attempt_checkout_payment",
    "fetch_order",
    "fetch_payment",
    "list_order_payments",
}

_lock = threading.Lock()
_counts: dict[str, int] = defaultdict(int)
_calls: list[dict[str, Any]] = []


def record(operation: str, **kwargs: Any) -> None:
    """Record one money-API call. Called from razorpay_client and binding."""
    with _lock:
        _counts[operation] += 1
        _calls.append({"operation": operation, **kwargs})


def reset() -> None:
    """Zero the counters. Tests use this in setup/teardown."""
    with _lock:
        _counts.clear()
        _calls.clear()


def snapshot() -> dict[str, Any]:
    """Read current counter state. Used by /invariant/money-calls endpoint."""
    with _lock:
        boundary_calls = sum(_counts[op] for op in _BOUNDARY_OPS
                             if op in _counts)
        return {
            "total": sum(_counts.values()),
            "boundary_calls": boundary_calls,
            "by_operation": dict(_counts),
            "recent": list(_calls[-50:]),
            "invariant_ok": boundary_calls == 0,
        }


def count(operation: str | None = None) -> int:
    """Number of calls (optionally filtered by operation)."""
    snap = snapshot()
    if operation is None:
        return snap["boundary_calls"]
    return _counts.get(operation, 0)
