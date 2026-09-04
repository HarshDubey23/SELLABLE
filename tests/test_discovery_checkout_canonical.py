"""The discovery UI must buy through the same executor as the API.

There must not be a "demo architecture" that skips the difficult parts.
These tests assert that /discovery/checkout produces a real gateway
verdict, a real approval binding, and a real execution row — and that it
cannot invent an order when the provider refuses.
"""

import pytest
from fastapi.testclient import TestClient

from apps.api import execution as ex


@pytest.fixture
def client(monkeypatch):
    monkeypatch.setenv("RAZORPAY_KEY_ID", "")
    monkeypatch.setenv("RAZORPAY_KEY_SECRET", "")
    from apps.api.main import app
    return TestClient(app)


@pytest.fixture(autouse=True)
def _clean_provider():
    from apps.api import execution_provider as p
    p._SIMULATED_SINGLETON._orders.clear()
    yield


def _checkout(client, sku="EAR-001", budget_paise=500000):
    return client.post("/discovery/checkout", json={
        "sku": sku, "product_name": "ignored by the server",
        "amount_paise": 1, "budget_paise": budget_paise,
        "category": "ignored by the server"})


def test_checkout_runs_the_canonical_path_and_records_an_execution(client):
    resp = _checkout(client)
    assert resp.status_code == 200, resp.text
    body = resp.json()

    assert body["gateway_decision"] == "APPROVE"
    assert body["execution_state"] == ex.EXECUTED
    assert body["provider"] == "simulated"
    assert body["order_id"].startswith("order_sim_")
    assert body["authorization_issued_by"] == "in_process_demo_issuer", \
        "the in-process issuer must be disclosed, not hidden"

    row = ex.get(body["execution_id"])
    assert row is not None and row["state"] == ex.EXECUTED
    assert row["remote_order_id"] == body["order_id"]


def test_checkout_prices_from_the_catalog_not_from_the_request(client):
    """A client-supplied amount must have no effect whatsoever."""
    from apps.api.products import CATALOG

    resp = client.post("/discovery/checkout", json={
        "sku": "EAR-001", "product_name": "x",
        "amount_paise": 1,          # attacker-controlled
        "budget_paise": 500000, "category": "x"})
    assert resp.status_code == 200
    assert resp.json()["amount_paise"] == CATALOG["EAR-001"]["price_paise"]
    assert resp.json()["priced_from"] == "server-side merchant catalog"


def test_checkout_over_budget_is_rejected_by_the_gateway(client):
    from apps.api.products import CATALOG

    price = CATALOG["EAR-001"]["price_paise"]
    resp = _checkout(client, budget_paise=price - 1)
    assert resp.status_code == 422
    body = resp.json()
    assert body["ok"] is False
    assert body["status"] == "POLICY_GATEWAY_REJECT"
    assert body["rule_id"] == "R1_BUDGET"
    assert body["execution_state"] is None, \
        "no execution exists when the gateway refuses before the money path"
    assert body["money_boundary_calls_during_request"] == 0, \
        "a gateway refusal must not touch the payment provider"
    assert ex.list_executions() == [], "a rejected proposal must not open an execution"


def test_ambiguous_outcome_is_never_reportable_as_success(client):
    """The bug this guards: HTTP 202 is a 2xx.

    The executor signals "the provider's outcome is unknown" with 202. A
    browser client that checks only `response.ok` sees 2xx and, if the
    state is not at the top level of the body, falls back to a default and
    tells the buyer the payment succeeded. Every checkout outcome therefore
    carries `ok` and `execution_state` as top-level fields.
    """
    resp = client.post("/discovery/checkout", json={
        "sku": "EAR-001", "budget_paise": 500000, "fault": "remote_timeout"})

    assert resp.status_code == 202
    body = resp.json()
    assert body["ok"] is False, "202 must not be readable as success"
    assert body["execution_state"] == ex.RECONCILIATION_REQUIRED
    assert "detail" not in body or not isinstance(body.get("detail"), dict), \
        "the outcome must be flat, not nested under `detail`"
    assert body["reconcile_hint"].endswith("/reconcile")
    assert body["retryable"] is False, "blind retry of an unknown outcome is never offered"

    row = ex.get(body["execution_id"])
    assert row is not None and row["state"] == ex.RECONCILIATION_REQUIRED


def test_reconciliation_resolves_the_ambiguous_outcome_from_provider_state(client):
    """The order really was created; only the response was lost."""
    body = client.post("/discovery/checkout", json={
        "sku": "EAR-001", "budget_paise": 500000,
        "fault": "remote_timeout"}).json()

    resolved = client.post(f"/discovery/reconcile/{body['execution_id']}")
    assert resolved.status_code == 200
    out = resolved.json()
    assert out["state"] == ex.EXECUTED
    assert out["resolution"] == "REMOTE_ORDER_FOUND"
    assert out["remote_order_id"].startswith("order_sim_")


def test_undispatched_request_reconciles_to_failed_not_to_success(client):
    """`remote_lost` never reached the provider, so nothing may be claimed."""
    body = client.post("/discovery/checkout", json={
        "sku": "EAR-001", "budget_paise": 500000,
        "fault": "remote_lost"}).json()
    assert body["execution_state"] == ex.RECONCILIATION_REQUIRED

    out = client.post(f"/discovery/reconcile/{body['execution_id']}").json()
    assert out["state"] == ex.FAILED
    assert out["resolution"] == "NO_REMOTE_ORDER"


def test_checkout_refuses_a_sku_the_merchant_does_not_stock(client):
    resp = _checkout(client, sku="NOT-A-REAL-SKU")
    assert resp.status_code == 400
    assert resp.json()["detail"]["error"]["error_code"] == "SKU_NOT_FOUND"


def test_payment_status_never_asserts_a_settlement(client):
    order_id = _checkout(client).json()["order_id"]
    resp = client.get(f"/discovery/payment-status/{order_id}")
    assert resp.status_code == 200
    body = resp.json()
    assert body["settlement"] == "NO_SETTLEMENT_EVENT_RECEIVED"
    assert body["execution_state"] == ex.EXECUTED
    assert body["webhook_events"] == []


def test_no_confirm_payment_route_exists(client):
    """The route that fabricated a captured payment must be gone."""
    resp = client.post("/discovery/confirm-payment",
                       json={"order_id": "x", "payment_id": "pay_fake"})
    assert resp.status_code == 404


def test_discovery_checkout_makes_no_direct_provider_import():
    """razorpay_client must be reachable only through the executor boundary."""
    source = open("apps/api/discovery/api.py", encoding="utf-8").read()
    assert "razorpay_client.create_order" not in source
    assert "from .. import razorpay_client" not in source
