"""End-to-end money-path tests through the real HTTP surface.

Every test here drives the canonical path a judge sees in the product:
signed mission -> quote -> gateway proposal -> approval binding ->
create_order -> execution state -> reconciliation. There is no test-only
shortcut into the executor.

The simulated provider is selected the same way production selects it:
by the absence of real Razorpay credentials. Fault injection is explicit
and only accepted on the simulated provider.
"""
import os
import time

import pytest
from fastapi.testclient import TestClient

from apps.api import execution as ex
from apps.api.gateway.mission_verify import sign_mission
from apps.api.gateway.types import canonical_json
from apps.api.mandates.mandates import (
    CartMandate,
    IntentMandate,
    sign_cart,
    sign_intent,
)

SKU = "BAT-001"
PRICE = 149900


@pytest.fixture
def client(monkeypatch):
    # No Razorpay credentials => simulated provider, exactly as a fresh
    # clone behaves. Nothing here reaches the network.
    monkeypatch.setenv("RAZORPAY_KEY_ID", "")
    monkeypatch.setenv("RAZORPAY_KEY_SECRET", "")
    from apps.api.main import app
    return TestClient(app)


@pytest.fixture(autouse=True)
def _clean_provider():
    from apps.api import execution_provider as p
    p._SIMULATED_SINGLETON._orders.clear()
    yield


def _headers(idem: str) -> dict:
    return {"X-API-Key": os.environ["APP_API_KEY"],
            "X-Idempotency-Key": idem}


def _signed_mission(mission_id: str, budget_paise: int = 300000) -> dict:
    now = int(time.time())
    blob = {
        "mission_id": mission_id,
        "intent": "buy a cricket bat",
        "budget_paise": budget_paise,
        "allowed_categories": ("cricket",),
        "forbidden_categories": (),
        "upsell_cap": 1.0,
        "expires_at": now + 3600,
    }
    signature = sign_mission(canonical_json(blob))
    out = {k: (list(v) if isinstance(v, tuple) else v) for k, v in blob.items()}
    out["signature"] = signature
    return out


def _mandates(mission_id: str, proposal_hash: str, amount: int) -> tuple[dict, dict]:
    key = os.environ["USER_MANDATE_KEY"]
    now = int(time.time())
    intent = sign_intent(IntentMandate(
        mission_id=mission_id, user_id="u1",
        ceiling_paise=amount + 100000, expires_at=now + 3600), key)
    cart = sign_cart(CartMandate(
        mission_id=mission_id, cart_hash=proposal_hash,
        amount_paise=amount, signed_at=now, expires_at=now + 3600), key)
    return intent, cart


def _authorize(client, mission_id: str) -> dict:
    """Run the honest path up to (not including) create_order."""
    mission = _signed_mission(mission_id)

    q = client.post("/tools/quote",
                    json={"items": [{"sku": SKU, "qty": 1}],
                          "mission_id": mission_id},
                    headers={"X-API-Key": os.environ["APP_API_KEY"]})
    assert q.status_code == 200, q.text
    quote = q.json()

    p = client.post("/tools/submit_proposal",
                    json={"mission": mission, "items": [{"sku": SKU, "qty": 1}]},
                    headers={"X-API-Key": os.environ["APP_API_KEY"]})
    assert p.status_code == 200, p.text
    body = p.json()
    assert body["data"]["decision"] == "APPROVE", body

    proposal_hash = body["data"]["proposal_hash"]
    intent, cart = _mandates(mission_id, proposal_hash, quote["total_paise"])
    return {
        "quote_id": quote["quote_id"],
        "total_paise": quote["total_paise"],
        "proposal_hash": proposal_hash,
        "approve_seq": body["seq"],
        "intent_mandate": intent,
        "cart_mandate": cart,
        "mission_id": mission_id,
    }


def _order_body(auth: dict) -> dict:
    return {"quote_id": auth["quote_id"],
            "proposal_hash": auth["proposal_hash"],
            "approve_seq": auth["approve_seq"],
            "intent_mandate": auth["intent_mandate"],
            "cart_mandate": auth["cart_mandate"]}


# ------------------------------------------------------------- happy path

def test_clean_run_reaches_executed(client):
    auth = _authorize(client, "m-happy")
    r = client.post("/tools/create_order", json=_order_body(auth),
                    headers=_headers("idem-happy"))
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["execution_state"] == ex.EXECUTED
    assert body["provider"] == "simulated"
    assert body["order_id"].startswith("order_sim_"), \
        "simulated orders must be visibly simulated"

    row = ex.get(body["execution_id"])
    assert row["state"] == ex.EXECUTED
    assert row["remote_order_id"] == body["order_id"]
    assert row["terminal_at"] is not None


def test_replay_of_executed_intent_returns_the_same_order(client):
    auth = _authorize(client, "m-replay")
    first = client.post("/tools/create_order", json=_order_body(auth),
                        headers=_headers("idem-a")).json()

    # Different client idempotency header, same authorized intent.
    second = client.post("/tools/create_order", json=_order_body(auth),
                         headers=_headers("idem-b-different"))
    assert second.status_code == 200, second.text
    assert second.json()["order_id"] == first["order_id"]
    assert second.json()["duplicate"] is True
    assert len(ex.list_executions()) == 1, "a replay must not open a 2nd execution"


# --------------------------------------------------- ambiguous outcomes

def test_timeout_becomes_reconciliation_required_not_failure(client):
    auth = _authorize(client, "m-timeout")
    r = client.post("/tools/create_order", json=_order_body(auth),
                    headers={**_headers("idem-timeout"),
                             "X-Sellable-Fault": "remote_timeout"})
    assert r.status_code == 202, r.text
    err = r.json()["detail"]["error"]
    assert err["error_code"] == "RECONCILIATION_REQUIRED"

    row = ex.get(err["execution_id"])
    assert row["state"] == ex.RECONCILIATION_REQUIRED
    assert row["terminal_at"] is None
    assert row["remote_order_id"] is None


def test_retry_after_ambiguous_outcome_is_refused(client):
    """Retrying an unknown outcome is how agents double-charge people."""
    auth = _authorize(client, "m-retry")
    first = client.post("/tools/create_order", json=_order_body(auth),
                        headers={**_headers("idem-r1"),
                                 "X-Sellable-Fault": "remote_timeout"})
    assert first.status_code == 202

    retry = client.post("/tools/create_order", json=_order_body(auth),
                        headers=_headers("idem-r2"))
    assert retry.status_code == 409
    assert retry.json()["detail"]["error"]["error_code"] == "RECONCILIATION_REQUIRED"
    assert len(ex.list_executions()) == 1


def test_reconcile_finds_the_order_the_provider_actually_created(client):
    """Response lost, order created. Reconciliation must resolve to EXECUTED."""
    auth = _authorize(client, "m-recon-found")
    amb = client.post("/tools/create_order", json=_order_body(auth),
                      headers={**_headers("idem-rf"),
                               "X-Sellable-Fault": "remote_timeout"})
    eid = amb.json()["detail"]["error"]["execution_id"]

    r = client.post(f"/executions/{eid}/reconcile",
                    headers={"X-API-Key": os.environ["APP_API_KEY"]})
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["state"] == ex.EXECUTED
    assert body["resolution"] == "REMOTE_ORDER_FOUND"
    assert body["remote_order_id"].startswith("order_sim_")
    assert ex.get(eid)["reconciled_at"] is not None


def test_reconcile_proves_no_money_moved_when_request_was_lost(client):
    """Request never reached the provider. Reconciliation must resolve FAILED."""
    auth = _authorize(client, "m-recon-lost")
    amb = client.post("/tools/create_order", json=_order_body(auth),
                      headers={**_headers("idem-rl"),
                               "X-Sellable-Fault": "remote_lost"})
    assert amb.status_code == 202
    eid = amb.json()["detail"]["error"]["execution_id"]

    r = client.post(f"/executions/{eid}/reconcile",
                    headers={"X-API-Key": os.environ["APP_API_KEY"]})
    assert r.status_code == 200, r.text
    assert r.json()["state"] == ex.FAILED
    assert r.json()["resolution"] == "NO_REMOTE_ORDER"
    assert ex.get(eid)["remote_error_code"] == "NO_REMOTE_ORDER"


def test_reconcile_is_idempotent(client):
    auth = _authorize(client, "m-recon-twice")
    amb = client.post("/tools/create_order", json=_order_body(auth),
                      headers={**_headers("idem-rt"),
                               "X-Sellable-Fault": "remote_timeout"})
    eid = amb.json()["detail"]["error"]["execution_id"]
    hdr = {"X-API-Key": os.environ["APP_API_KEY"]}

    first = client.post(f"/executions/{eid}/reconcile", headers=hdr).json()
    second = client.post(f"/executions/{eid}/reconcile", headers=hdr).json()
    assert first["state"] == second["state"] == ex.EXECUTED
    assert second["already_terminal"] is True


# ------------------------------------------------------- definite failure

def test_definite_provider_rejection_is_terminal_failure(client):
    auth = _authorize(client, "m-reject")
    r = client.post("/tools/create_order", json=_order_body(auth),
                    headers={**_headers("idem-rej"),
                             "X-Sellable-Fault": "remote_reject"})
    assert r.status_code == 502, r.text
    err = r.json()["detail"]["error"]
    assert err["execution_state"] == ex.FAILED
    assert ex.get(err["execution_id"])["remote_error_code"] == "BAD_REQUEST_ERROR"


def test_failed_execution_cannot_be_retried_on_the_same_authorization(client):
    auth = _authorize(client, "m-refail")
    client.post("/tools/create_order", json=_order_body(auth),
                headers={**_headers("idem-f1"),
                         "X-Sellable-Fault": "remote_reject"})
    again = client.post("/tools/create_order", json=_order_body(auth),
                        headers=_headers("idem-f2"))
    assert again.status_code == 409
    assert again.json()["detail"]["error"]["error_code"] == "EXECUTION_ALREADY_FAILED"


# ------------------------------------------------------------ guardrails

def test_fault_injection_is_refused_when_a_real_provider_is_configured(
        client, monkeypatch):
    monkeypatch.setenv("RAZORPAY_KEY_ID", "rzp_test_realish")
    monkeypatch.setenv("RAZORPAY_KEY_SECRET", "realish_secret")
    auth = _authorize(client, "m-faultguard")
    r = client.post("/tools/create_order", json=_order_body(auth),
                    headers={**_headers("idem-fg"),
                             "X-Sellable-Fault": "remote_timeout"})
    assert r.status_code == 400
    assert r.json()["detail"]["error"]["error_code"] == "FAULT_INJECTION_REFUSED"


def test_placeholder_credentials_are_not_treated_as_configured(monkeypatch):
    from apps.api import execution_provider as p
    monkeypatch.setenv("RAZORPAY_KEY_ID", "rzp_test_xxxxxxxx")
    monkeypatch.setenv("RAZORPAY_KEY_SECRET", "your_secret_here")
    assert p.razorpay_credentials_present() is False
    assert p.provider_name() == "simulated"


def test_concurrent_create_order_produces_exactly_one_order(client):
    """Two agents, one authorization. Only one payment may exist."""
    import threading

    auth = _authorize(client, "m-concurrent")
    results: list[int] = []
    barrier = threading.Barrier(6)
    lock = threading.Lock()

    def worker(i: int):
        barrier.wait()
        resp = client.post("/tools/create_order", json=_order_body(auth),
                           headers=_headers(f"idem-c{i}"))
        with lock:
            results.append(resp.status_code)

    threads = [threading.Thread(target=worker, args=(i,)) for i in range(6)]
    for t in threads:
        t.start()
    for t in threads:
        t.join()

    executions = ex.list_executions()
    assert len(executions) == 1, f"only one execution may exist: {executions}"
    assert executions[0]["state"] == ex.EXECUTED
    assert results.count(200) >= 1
    # Every loser gets a clean, explained refusal — never a 500.
    assert all(code in (200, 403, 409) for code in results), results
    assert 500 not in results, "a concurrency loser must not crash"


def test_executions_endpoint_reports_honest_provider(client):
    r = client.get("/executions")
    assert r.status_code == 200
    body = r.json()
    assert body["provider"] == "simulated"
    assert "no Razorpay credentials" in body["provider_description"]
    assert set(body["states"]) == set(ex.ALL_STATES)
