"""A mandate is stamped when it is signed, not when the request began.

This is the bug that made the same commit pass on one branch and fail on
another. `/discovery/checkout` read the clock once at the top of the
request and reused that stamp for the cart mandate -- but the approval
binding is registered later, inside the gateway call, with its own clock
read. On a fast machine the gap was under the executor's one second of
tolerance and nothing showed. On a loaded CI runner it was not, and the
executor refused the mandate as MANDATE_CART_STALE.

Nothing was actually stale. The clock was read too early.

The test forces the gap rather than hoping for it: the gateway is made
to take three seconds, which is what a contended runner does on its own
and what no fast machine will ever do by accident.
"""
from __future__ import annotations

import time

import pytest
from fastapi.testclient import TestClient

SLOW_SECONDS = 3.0


@pytest.fixture
def slow_gateway(monkeypatch):
    """Make approving a proposal take longer than the staleness tolerance."""
    from apps.api import tools as tools_mod

    original = tools_mod.evaluate_proposal

    async def slow(req, **kw):
        time.sleep(SLOW_SECONDS)
        return await original(req, **kw)

    monkeypatch.setattr(tools_mod, "evaluate_proposal", slow)
    return slow


def test_a_slow_gateway_does_not_make_the_cart_mandate_look_stale(slow_gateway):
    """The whole point: a slow server must not refuse its own authorization."""
    from apps.api.main import app

    client = TestClient(app)
    body = client.post("/discovery/checkout",
                       json={"sku": "BAT-001", "budget_paise": 300000}).json()

    error = (body.get("error") or {}) if isinstance(body, dict) else {}
    assert error.get("error_code") != "MANDATE_CART_STALE", \
        "a slow gateway made the checkout refuse its own cart mandate"
    assert body.get("execution_state") is not None, \
        f"checkout did not reach the execution machine: {body}"


def test_the_market_settles_through_a_slow_gateway_too(slow_gateway):
    """The market signs its own mandates and had the identical bug."""
    import asyncio

    from apps.api.market import negotiation as neg
    from apps.api.market import settle as settle_mod

    async def go() -> str:
        row = await neg.open_negotiation(
            mission_text="A complete cricket setup under Rs 6,000",
            allow_llm=False)
        nid = row["negotiation_id"]
        await neg.run_round(nid, allow_llm=False)
        return nid

    nid = asyncio.run(go())
    neg.claim_winner(nid)
    out = asyncio.run(settle_mod.settle(nid))

    assert out["order"]["execution_state"] == "EXECUTED"
    assert out["amount_paise"] > 0


def test_the_tolerance_still_refuses_a_genuinely_stale_mandate():
    """Fixing the false positive must not remove the check.

    A cart mandate signed well before the approval it claims to
    authorize is still refused. That is the case the check exists for --
    a mandate captured earlier and replayed against a later approval.
    """
    from apps.api.mandates.mandates import CartMandate, MandateError, sign_cart, verify_cart

    now = int(time.time())
    key = "k" * 32
    blob = sign_cart(CartMandate(
        mission_id="msn_x", cart_hash="h" * 64, amount_paise=1000,
        signed_at=now - 600, expires_at=now + 3600), key)

    import os
    os.environ["USER_MANDATE_KEY"] = key
    with pytest.raises(MandateError) as exc:
        verify_cart(blob, proposal_hash="h" * 64, amount_paise=1000,
                    expected_mission_id="msn_x", approval_issued_at=now)
    assert "MANDATE_CART_STALE" in str(exc.value)


# ------------------------------------------- the refusal must not crash

def test_a_mandate_rejection_returns_a_refusal_not_a_crash(monkeypatch):
    """The one path that must never raise is the path that says no.

    Two refusal shapes exist in this system. Most carry a nested dict:
    {"error": {"error_code": ..., "message": ...}}. The mandate verifier
    carries a flat one where "error" is a plain string and the code sits
    beside it. The checkout envelope assumed the first and called .get()
    on the second, so a mandate rejection produced AttributeError -- the
    caller got a 500 where it should have got a clean, machine-readable
    no.
    """
    from apps.api import tools as tools_mod
    from apps.api.main import app
    from apps.api.mandates.mandates import MandateError

    def always_stale(*a, **kw):
        raise MandateError("MANDATE_CART_STALE")

    monkeypatch.setattr(tools_mod, "verify_cart", always_stale)

    client = TestClient(app)
    response = client.post("/discovery/checkout",
                           json={"sku": "BAT-001", "budget_paise": 300000})
    body = response.json()

    assert response.status_code == 403, f"expected a refusal, got {body}"
    assert body["ok"] is False
    assert body["status"] == "MANDATE_CART_STALE", \
        "the refusal must name the code a client can act on"
    assert body["money_boundary_calls_during_request"] == 0, \
        "a refused checkout must not have touched the money boundary"


def test_every_refusal_shape_flattens_to_one_envelope():
    """Both shapes, plus the degenerate ones, without raising."""
    from apps.api.discovery.api import _as_error

    nested = _as_error({"error": {"error_code": "R1_BUDGET", "message": "m"}})
    assert nested["error_code"] == "R1_BUDGET"

    flat = _as_error({"error": "MANDATE_REJECTED", "code": "MANDATE_EXPIRED"})
    assert flat["error_code"] == "MANDATE_EXPIRED", \
        "the machine-readable code lives in 'code' for the flat shape"

    assert _as_error("a bare string") == {"message": "a bare string"}
    assert _as_error(None) == {}
