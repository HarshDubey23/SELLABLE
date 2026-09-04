"""The reviewer-facing attack sandbox must be a sandbox.

/attack/custom accepts arbitrary input from anyone who can reach the
server. The claim it makes — "no matter what you send, no money moves" —
is only worth anything if it is structural rather than a promise, so the
first test here reads the module's own AST and proves it cannot even
reference the execution machinery.

The rest assert the two locks behave as advertised, including the case
the demo is built around: a proposal the deterministic gateway is right
to approve, which the approval binding refuses anyway.
"""
from __future__ import annotations

import ast
import pathlib

import pytest
from fastapi.testclient import TestClient

from apps.api import money, ratelimit

MODULE = pathlib.Path("apps/api/attack_custom.py")


@pytest.fixture
def client(monkeypatch):
    monkeypatch.setenv("RAZORPAY_KEY_ID", "")
    monkeypatch.setenv("RAZORPAY_KEY_SECRET", "")
    from apps.api.main import app
    ratelimit.reset()
    return TestClient(app)


def _mission(**over):
    body = {"mission_id": "MSN-ATK-TEST", "intent": "test",
            "budget_paise": 500000, "allowed_categories": ["cricket"],
            "expires_at": 9999999999}
    body.update(over)
    return body


# ----------------------------------------------------------- the sandbox

def test_attack_sandbox_cannot_import_the_execution_machinery():
    """Structural proof, not a promise: the import is simply not there.

    If someone later wires the sandbox to the executor "just to show the
    state machine", this fails before the security review does.
    """
    tree = ast.parse(MODULE.read_text(encoding="utf-8"))
    offenders: list[str] = []
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            offenders += [a.name for a in node.names if "execution" in a.name]
        elif isinstance(node, ast.ImportFrom):
            if node.module and "execution" in node.module:
                offenders.append(node.module)
            offenders += [a.name for a in node.names if "execution" in a.name]
    assert offenders == [], (
        f"the attack sandbox imports execution machinery: {offenders}. "
        f"It must be unable to reach a payment provider by construction.")


def test_attack_sandbox_never_imports_the_money_boundary():
    """It counts boundary calls; it must not be able to make one."""
    tree = ast.parse(MODULE.read_text(encoding="utf-8"))
    for node in ast.walk(tree):
        if isinstance(node, ast.ImportFrom) and node.module:
            assert "razorpay_client" not in node.module
        if isinstance(node, ast.Import):
            for a in node.names:
                assert "razorpay_client" not in a.name


# ------------------------------------------------------------- lock one

def test_budget_bypass_dies_at_the_gateway(client):
    r = client.post("/attack/custom", json={
        "mission": _mission(budget_paise=100),
        "items": [{"sku": "BAT-001", "qty": 1}]})
    assert r.status_code == 200
    body = r.json()
    assert body["refused_layer"] == "gateway"
    assert body["refused_by"] == "gateway/R1_BUDGET"
    assert body["gateway"]["decision"] == "REJECT"
    assert body["money_boundary_calls"] == 0


def test_a_tampered_signature_dies_at_r9(client):
    r = client.post("/attack/custom", json={
        "mission": _mission(), "items": [{"sku": "BAT-001", "qty": 1}],
        "tamper_signature": True})
    body = r.json()
    assert body["refused_by"] == "gateway/R9_SIGNATURE"
    assert body["money_boundary_calls"] == 0


def test_an_out_of_scope_category_dies_at_the_gateway(client):
    r = client.post("/attack/custom", json={
        "mission": _mission(allowed_categories=["books"]),
        "items": [{"sku": "BAT-001", "qty": 1}]})
    body = r.json()
    assert body["refused_layer"] == "gateway"
    assert body["money_boundary_calls"] == 0


# ------------------------------------------------------------- lock two

def test_a_proposal_the_gateway_approves_is_still_refused_by_the_binding(client):
    """The scene the whole demo exists for.

    Budget is generous, the SKU is in scope and the price is correct, so
    R1-R12 are right to approve. The attacker still cannot buy anything,
    because permission is a single-use binding to one exact cart that
    they cannot mint.
    """
    r = client.post("/attack/custom", json={
        "mission": _mission(budget_paise=500000),
        "items": [{"sku": "BAT-001", "qty": 1}],
        "forged_binding": {"seq": 999999, "token": "forged_token_abc123"}})
    body = r.json()

    assert body["gateway"]["decision"] == "APPROVE", \
        "this scenario is pointless unless the gateway genuinely approves"
    assert body["refused_layer"] == "binding"
    assert body["binding_check"]["accepted"] is False
    assert body["headline"] == "THE GATEWAY PASSED YOU. THE BINDING DIDN'T."
    assert body["money_boundary_calls"] == 0


def test_a_missing_binding_is_refused_exactly_like_a_forged_one(client):
    r = client.post("/attack/custom", json={
        "mission": _mission(), "items": [{"sku": "BAT-001", "qty": 1}]})
    body = r.json()
    assert body["refused_layer"] == "binding"
    assert body["binding_check"]["accepted"] is False


def test_a_non_integer_forged_sequence_does_not_crash_the_verifier(client):
    r = client.post("/attack/custom", json={
        "mission": _mission(), "items": [{"sku": "BAT-001", "qty": 1}],
        "forged_binding": {"seq": "'; DROP TABLE bindings; --"}})
    assert r.status_code == 200
    assert r.json()["binding_check"]["seq_presented"] == -1


# ----------------------------------------------------------- lock zero

def test_an_attacker_supplied_price_is_discarded_and_reported(client):
    """The attacker may claim a price. It never becomes the amount."""
    from apps.api.products import CATALOG

    r = client.post("/attack/custom", json={
        "mission": _mission(amount_paise=1),
        "items": [{"sku": "BAT-001", "qty": 1, "price_paise": 1}]})
    body = r.json()

    assert body["price_overwrite_applied"] is True
    assert body["mission_amount_field_ignored"] is True
    discarded = body["attacker_prices_discarded"][0]
    assert discarded["attacker_claimed_paise"] == 1
    assert discarded["catalog_paise"] == CATALOG["BAT-001"]["price_paise"]
    # And crucially: the gateway saw the catalog price, so R3 has nothing
    # to complain about — the lie was removed before evaluation, not
    # caught during it.
    assert body["gateway"]["decision"] == "APPROVE"
    assert body["refused_layer"] == "binding"


def test_an_unknown_sku_is_refused_with_422_not_invented(client):
    r = client.post("/attack/custom", json={
        "mission": _mission(), "items": [{"sku": "NOT-A-SKU", "qty": 1}]})
    assert r.status_code == 422
    assert r.json()["detail"]["error"]["error_code"] == "UNKNOWN_SKU"


@pytest.mark.parametrize("payload", [
    {}, {"mission": {}}, {"mission": {"budget_paise": 0}, "items": []},
    {"mission": {"budget_paise": 5000, "expires_at": 1}, "items": []},
])
def test_malformed_bodies_are_422_never_500(client, payload):
    assert client.post("/attack/custom", json=payload).status_code == 422


# ----------------------------------------------------- the invariant

def test_no_attack_shape_ever_touches_the_money_boundary(client):
    """One counter, checked across every shape of attack we can express."""
    shapes = [
        {"mission": _mission(budget_paise=1), "items": [{"sku": "BAT-001"}]},
        {"mission": _mission(), "items": [{"sku": "BAT-001", "qty": 100}]},
        {"mission": _mission(allowed_categories=["books"]),
         "items": [{"sku": "BAT-001"}]},
        {"mission": _mission(forbidden_categories=["cricket"]),
         "items": [{"sku": "BAT-001"}]},
        {"mission": _mission(), "items": [{"sku": "BAT-001", "price_paise": 0}]},
        {"mission": _mission(), "items": [{"sku": "BAT-001"}],
         "forged_binding": {"seq": 1}},
        {"mission": _mission(), "items": [{"sku": "BAT-001"}],
         "tamper_signature": True},
    ]
    before = money.snapshot()["boundary_calls"]
    for shape in shapes:
        r = client.post("/attack/custom", json=shape)
        assert r.status_code == 200, r.text
        assert r.json()["money_boundary_calls"] == 0
        assert r.json()["amount_moved_paise"] == 0
    assert money.snapshot()["boundary_calls"] == before


# ------------------------------------------------------------- gauntlet

def test_gauntlet_matches_the_suite_and_measures_its_own_latency(client):
    r = client.post("/attack/gauntlet")
    assert r.status_code == 200
    body = r.json()
    assert body["totals"]["blocked"] == body["totals"]["total"] == 8
    assert body["totals"]["money_boundary_calls"] == 0
    assert body["measured_on"] == "this machine, this run"
    for row in body["results"]:
        assert row["latency_ms"] > 0, "a latency of zero is not a measurement"
        assert row["blocked_by"] != "NOT BLOCKED"
        assert row["refused_layer"] in ("gateway", "binding")


def test_the_rate_limit_actually_refuses(client):
    ratelimit.reset()
    codes = [client.post("/attack/gauntlet").status_code for _ in range(8)]
    assert 429 in codes, "an unauthenticated route that does real work needs a ceiling"
    refusal = client.post("/attack/gauntlet")
    if refusal.status_code == 429:
        assert refusal.json()["detail"]["error"]["error_code"] == "RATE_LIMITED"


# ─────────────────────────────────────────────────────────────────────
# Route classification. Everything reachable without a key that can end
# in a Razorpay call needs a ceiling, because "unauthenticated" and
# "unbounded" together is how a storefront becomes an expense.
# ─────────────────────────────────────────────────────────────────────

def test_the_storefront_checkout_has_a_ceiling(client):
    """No API key, by design. Therefore a rate limit, by necessity."""
    ratelimit.reset()
    codes = [client.post("/discovery/checkout",
                         json={"sku": "BAT-001", "budget_paise": 300000}).status_code
             for _ in range(16)]
    assert 429 in codes, (
        "an unauthenticated route that creates real test orders must be "
        "throttled; without this a loop is an unbounded spend")


def test_the_agent_mission_runner_has_a_ceiling(client):
    ratelimit.reset()
    codes = [client.post("/agent/run_full_mission",
                         json={"intent": "x", "budget_inr": 10}).status_code
             for _ in range(12)]
    assert 429 in codes


def test_every_unauthenticated_mutating_route_is_accounted_for():
    """A checklist that fails when someone adds an ungated POST.

    Not a security control — a forcing function. Adding a mutating route
    without a key means deciding, in writing, why that is right and what
    bounds it instead.
    """
    import ast
    import pathlib

    KEYED = "require_api_key"
    # Route -> why it is open, and what bounds it instead.
    ACCOUNTED = {
        "/search": "read-only discovery; no state change",
        "/api/v1/gateway/simulate": "pure gateway evaluation; writes nothing, not even an audit row",
        "/checkout": "the customer's checkout; rate-limited per client",
        "/reconcile/{execution_id}": "customer recovery; bounded by the state machine",
        "/attack/custom": "reviewer sandbox; rate-limited, imports no executor",
        "/attack/gauntlet": "reviewer sandbox; rate-limited",
        "/run/{scenario_id}": "attack lab; gateway-only, no money boundary",
        "/simulate/{scenario_id}": "attack lab; gateway-only, no money boundary",
        "/run_all": "attack lab; gateway-only, no money boundary",
        "/audit/tamper-demo": "in-memory copy only; rate-limited",
        "/demo": "negotiation with catalog-derived bounds; rate-limited",
        "/agent/run_full_mission": "cockpit mission scene; rate-limited",
        "/demo/kill-switch": "double-gated on CHAOS_ENABLED and test credentials",
        "/webhook": "HMAC-verified, fail-closed when the secret is unset",
        "/api/chaos/faults": "gated on CHAOS_ENABLED",
        "/api/chaos/faults/{fault_id}": "gated on CHAOS_ENABLED",
        "/api/chaos/reset": "gated on CHAOS_ENABLED",
        "/api/chaos/scenarios/{scenario_id}/run": "gated on CHAOS_ENABLED",
        "/missions/{mission_id}/start": "observability only; never gates money",
        "/missions/{mission_id}/step": "observability only; never gates money",
        "/missions/{mission_id}/finish": "observability only; never gates money",
        "/evaluate": "growth: gateway verdict only, never creates an order",
        "/transact": "growth: gateway verdict only, never creates an order",
        "/loop/approve/{action_id}": "merchant growth loop; no money boundary",
        "/loop/execute/{action_id}": "merchant growth loop; no money boundary",
    }

    unaccounted = []
    for path in pathlib.Path("apps/api").rglob("*.py"):
        # utf-8-sig: a stray BOM makes ast.parse raise on a valid file.
        tree = ast.parse(path.read_text(encoding="utf-8-sig"))
        for node in ast.walk(tree):
            if not isinstance(node, ast.AsyncFunctionDef | ast.FunctionDef):
                continue
            for dec in node.decorator_list:
                if not isinstance(dec, ast.Call):
                    continue
                target = getattr(dec.func, "attr", "")
                if target not in ("post", "put", "delete", "patch"):
                    continue
                route = dec.args[0].value if dec.args else "?"
                keyed = KEYED in ast.unparse(dec)
                if not keyed and route not in ACCOUNTED:
                    unaccounted.append(f"{path}: {target.upper()} {route}")

    assert unaccounted == [], (
        "these mutating routes have neither an API key nor an entry saying "
        "why they are open:\n  " + "\n  ".join(unaccounted))
