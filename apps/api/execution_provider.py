"""The money provider boundary: one interface, two honest implementations.

`LiveRazorpayProvider` talks to api.razorpay.com in test mode.
`SimulatedProvider` runs the identical state machine with no network.

The simulated provider exists so that a fresh clone with no credentials
can still exercise the full authorization -> execution -> reconciliation
path. It is never described as "live" anywhere: every response, audit
entry and UI surface carries `provider: "simulated"`, and the simulated
order ids are prefixed `order_sim_` so they can never be mistaken for a
Razorpay identifier.

The critical contract both implementations share is the *classification
of outcomes*:

    returns dict            -> definitively executed
    DefiniteRemoteFailure   -> definitively refused (4xx, validation)
    AmbiguousRemoteOutcome  -> unknown (timeout, connection reset, 5xx,
                               unparseable body). NEVER guess.

Timeouts and 5xx are ambiguous on purpose. A gateway that returns 502
may still have created the order; only an authoritative read can say.
"""
from __future__ import annotations

import os
import time
import uuid
from typing import Any, Protocol

import requests

from . import money
from .config import PLACEHOLDER_VALUES, is_placeholder  # noqa: F401  (re-export)
from .execution import AmbiguousRemoteOutcome, DefiniteRemoteFailure

LIVE_TEST = "razorpay_test"
SIMULATED = "simulated"


def _is_real(value: str) -> bool:
    """A credential counts only when it is neither empty nor a placeholder."""
    return not is_placeholder(value)


def razorpay_credentials_present() -> bool:
    """True only when both Razorpay keys look like real credentials."""
    return (_is_real(os.environ.get("RAZORPAY_KEY_ID", ""))
            and _is_real(os.environ.get("RAZORPAY_KEY_SECRET", "")))


class MoneyProvider(Protocol):
    name: str

    def create_order(self, *, amount_paise: int, receipt: str,
                     notes: dict[str, Any],
                     idempotency_key: str) -> dict[str, Any]: ...

    def find_order_by_correlation(self, *, proposal_hash: str,
                                  amount_paise: int) -> dict[str, Any] | None: ...


class LiveRazorpayProvider:
    """Real test-mode calls against api.razorpay.com."""

    name = LIVE_TEST

    def create_order(self, *, amount_paise: int, receipt: str,
                     notes: dict[str, Any],
                     idempotency_key: str) -> dict[str, Any]:
        from . import razorpay_client as rp

        try:
            return rp.create_order(
                amount_paise=amount_paise, receipt=receipt, notes=notes,
                idempotency_key=idempotency_key)
        except rp.RazorpayAPIError as exc:
            # 4xx is Razorpay telling us it did NOT do the thing.
            # 5xx means the request may have been applied before it failed.
            if 400 <= exc.status_code < 500:
                code = ""
                if isinstance(exc.error, dict):
                    code = str(exc.error.get("code", "")) or ""
                raise DefiniteRemoteFailure(
                    code or f"HTTP_{exc.status_code}", str(exc)) from exc
            raise AmbiguousRemoteOutcome(
                f"razorpay returned HTTP {exc.status_code}; "
                f"order may or may not exist") from exc
        except (requests.Timeout, requests.ConnectionError) as exc:
            raise AmbiguousRemoteOutcome(
                f"{type(exc).__name__}: request may have reached Razorpay"
            ) from exc
        except ValueError as exc:
            # Unparseable body — we cannot tell what happened.
            raise AmbiguousRemoteOutcome(f"unparseable response: {exc}") from exc

    def find_order_by_correlation(self, *, proposal_hash: str,
                                  amount_paise: int) -> dict[str, Any] | None:
        """Authoritative reconciliation read.

        Razorpay exposes no public "fetch by idempotency key" lookup, so
        we do not pretend one exists. We page recent orders and match on
        the correlation fields we wrote into `notes` at creation time.
        """
        from . import razorpay_client as rp

        money.record("list_orders_for_reconciliation")
        data = rp._get("/v1/orders?count=100")
        for item in data.get("items", []):
            notes = item.get("notes") or {}
            if (notes.get("proposal_hash") == proposal_hash
                    and int(item.get("amount", -1)) == amount_paise):
                return item
        return None


class SimulatedProvider:
    """No-network implementation with the same outcome classification.

    Deterministic fault injection is available for the failure demo. It
    is explicit and opt-in — `fault` is only ever set from a request that
    asked for it, and the resulting state transitions are the real ones.
    """

    name = SIMULATED

    def __init__(self) -> None:
        self._orders: dict[str, dict[str, Any]] = {}

    def create_order(self, *, amount_paise: int, receipt: str,
                     notes: dict[str, Any],
                     idempotency_key: str) -> dict[str, Any]:
        money.record("create_order", amount_paise=amount_paise,
                     receipt=receipt, idempotency_key=idempotency_key,
                     provider=SIMULATED)
        fault = (notes.get("_fault") or "").strip()

        if fault == "remote_timeout":
            # The order IS recorded locally in the simulator, exactly like
            # a real gateway that applied the write before the response was
            # lost. Reconciliation must therefore find it.
            # Materialise it and then lose the response. Reconciliation
            # MUST be able to find this order — that is the whole point of
            # the scenario, and discarding the return value is deliberate.
            self._materialise(amount_paise, receipt, notes)
            raise AmbiguousRemoteOutcome(
                "simulated network timeout after the request was dispatched")
        if fault == "remote_lost":
            # Request never reached the provider. Reconciliation must find
            # nothing and resolve to FAILED.
            raise AmbiguousRemoteOutcome(
                "simulated connection reset before the request was applied")
        if fault == "remote_reject":
            raise DefiniteRemoteFailure(
                "BAD_REQUEST_ERROR", "simulated definitive provider rejection")

        return self._materialise(amount_paise, receipt, notes)

    def _materialise(self, amount_paise: int, receipt: str,
                     notes: dict[str, Any]) -> dict[str, Any]:
        order = {
            "id": "order_sim_" + uuid.uuid4().hex[:14],
            "entity": "order",
            "amount": amount_paise,
            "currency": "INR",
            "receipt": receipt,
            "status": "created",
            "notes": {k: v for k, v in notes.items() if not k.startswith("_")},
            "created_at": int(time.time()),
            "provider": SIMULATED,
        }
        self._orders[order["id"]] = order
        return order

    def find_order_by_correlation(self, *, proposal_hash: str,
                                  amount_paise: int) -> dict[str, Any] | None:
        for order in self._orders.values():
            if (order["notes"].get("proposal_hash") == proposal_hash
                    and order["amount"] == amount_paise):
                return order
        return None


_SIMULATED_SINGLETON = SimulatedProvider()


def get_provider() -> MoneyProvider:
    """Pick the provider from real credentials — never from a flag."""
    if razorpay_credentials_present():
        return LiveRazorpayProvider()
    return _SIMULATED_SINGLETON


def provider_name() -> str:
    return LIVE_TEST if razorpay_credentials_present() else SIMULATED


def mode_description() -> str:
    if razorpay_credentials_present():
        return "Razorpay test mode — real orders on api.razorpay.com"
    return ("Simulated provider — no Razorpay credentials configured; "
            "no network calls, order ids prefixed order_sim_")
