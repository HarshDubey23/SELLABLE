"""Fallback proof: with the LLM client stubbed to report an outage, buyer.py
still completes search -> propose via _deterministic_pick, and the trace
labels the run as fallback (used_fallback). Added Phase 2.

This labeling is the hook Phase 7's counterfactual measures: fallback runs
must never be counted as LLM behavior in the eval.

Contract note (discovery FACT 3): apps/api/llm/gemini.py::ask NEVER raises —
its documented contract is "Failures return error dicts, never raise", and
buyer.py switches to _deterministic_pick on llm_result["error"] (there is no
try/except around the call, by design). So the outage stub returns the error
shape rather than raising; that exercises the REAL fallback branch.

The ONLY application behavior mocked is the outbound Razorpay HTTP boundary
(apps/api/razorpay_client.*) — the repo's single money-API module.
"""
import asyncio
import os

import httpx
import pytest
from httpx import ASGITransport

os.environ.setdefault("MISSION_HMAC_KEY", "test-fallback-mission-key")
os.environ.setdefault("RAZORPAY_KEY_ID", "test-rzp-key-id")
os.environ.setdefault("USER_MANDATE_KEY", "test-fallback-user-mandate-key")

import apps.api.agent.buyer as buyer  # noqa: E402
from apps.api.main import app  # noqa: E402
from scripts.sign_mission import MISSION_TEMPLATES, sign_blob  # noqa: E402

# F-08: inject X-API-Key into the buyer's HTTP client so protected routes
# are exercised successfully in the test environment.
_orig_asyncclient_init = buyer.httpx.AsyncClient.__init__
def _patched_asyncclient_init(self, *args, **kwargs):
    kwargs.setdefault("headers", {}).__setitem__(
        "X-API-Key", os.environ.get("APP_API_KEY", "")
    )
    _orig_asyncclient_init(self, *args, **kwargs)
buyer.httpx.AsyncClient.__init__ = _patched_asyncclient_init

FAKE_ORDER_ID = "order_test_fallback_001"


def _signed_mission() -> dict:
    import time as _time

    mission = dict(MISSION_TEMPLATES["happy_path"])
    mission["mission_id"] = f"MSN-FALLBACK-{_time.time_ns()}"
    mission["expires_at"] = int(_time.time()) + 24 * 3600
    mission["signature"] = sign_blob(mission)
    return mission


@pytest.fixture(autouse=True)
def _fresh_audit_chain():
    """T30 corrupts the in-memory chain session-wide; restore from SQLite."""
    import importlib

    import apps.api.audit.chain as chain
    importlib.reload(chain)
    assert chain.verify() is True
    yield


def _patch_llm_outage(monkeypatch):
    """Simulate an LLM outage exactly the way gemini.ask reports one."""
    def _outage(*_a, **_k):
        return {"text": "", "latency_ms": 0, "model": "outage-stub",
                "error": "llm down (simulated outage)"}
    monkeypatch.setattr("apps.api.llm.gemini.ask", _outage)


def _patch_razorpay_boundary(monkeypatch):
    """Mock the outbound Razorpay HTTP calls at the single boundary module."""
    monkeypatch.setattr(
        "apps.api.razorpay_client.create_order",
        lambda **kwargs: {"id": FAKE_ORDER_ID, "status": "created"})
    # The UPI attempt fails deterministically, exactly like the real
    # test-mode rail refusal (recovery.py reads result["error"]).
    monkeypatch.setattr(
        "apps.api.razorpay_client.attempt_checkout_payment",
        lambda order_id, amount_paise, method_body, **kw: {
            "order_id": order_id, "http_status": 400,
            "result": {"error": {
                "code": "BAD_REQUEST_ERROR",
                "description": "UPI is not enabled for this test account",
                "step": "payment_initiation"}}})
    monkeypatch.setattr(
        "apps.api.razorpay_client.list_order_payments",
        lambda order_id: [])
    monkeypatch.setattr(
        "apps.api.razorpay_client.fetch_order",
        lambda order_id: {"id": order_id, "status": "created"})


def _patch_agent_transport(monkeypatch):
    """Point buyer.py's httpx.AsyncClient at the real ASGI app (in-process);
    the agent code and the merchant handlers stay 100% real."""
    transport = ASGITransport(app=app)

    class _Client(httpx.AsyncClient):
        def __init__(self, *args, **kwargs):
            kwargs.setdefault("transport", transport)
            kwargs.setdefault("base_url", "http://testserver")
            super().__init__(*args, **kwargs)

    monkeypatch.setattr(buyer.httpx, "AsyncClient", _Client)


def test_llm_outage_still_produces_labeled_fallback_proposal(monkeypatch):
    _patch_llm_outage(monkeypatch)
    _patch_razorpay_boundary(monkeypatch)
    _patch_agent_transport(monkeypatch)
    monkeypatch.setattr(buyer.time, "sleep", lambda s: None)

    mission = _signed_mission()
    result = asyncio.run(buyer.run_mission(mission, base_url="http://testserver"))

    trace_events = result["trace"]["events"]

    # 1. A proposal IS still produced via _deterministic_pick.
    fallback_events = [e for e in trace_events if e["action"] == "llm_fallback"]
    assert fallback_events, "expected an llm_fallback trace event on outage"
    assert fallback_events[0]["data"]["skus"], "fallback proposed no SKUs"
    assert fallback_events[0]["data"]["skus"][0].startswith("BAT-")
    assert any(e["action"] == "proposal_submitted" for e in trace_events)

    # 2. The trace records the fallback designation.
    assert fallback_events[0]["used_fallback"] is True

    # 3. The money path still completed (order created, honestly labeled).
    assert result["order_id"] == FAKE_ORDER_ID
    order_event = next(e for e in trace_events if e["action"] == "order_created")
    assert order_event["data"]["order_id"] == FAKE_ORDER_ID
