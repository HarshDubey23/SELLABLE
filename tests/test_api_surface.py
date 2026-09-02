"""
tests/test_api_surface.py - Key API endpoint smoke tests.
"""
import os, pytest
from fastapi.testclient import TestClient


@pytest.fixture
def client():
    from apps.api.main import app
    return TestClient(app)


def test_health(client):
    resp = client.get("/health")
    assert resp.status_code == 200
    data = resp.json()
    assert data["status"] == "alive"
    assert "audit_chain_ok" in data


def test_audit_verify(client):
    resp = client.get("/audit/verify")
    assert resp.status_code == 200
    data = resp.json()
    assert data["verified"] is True
    assert data["reason"] == "ok"
    assert data["genesis_action"] == "GENESIS"


def test_audit_endpoint(client):
    resp = client.get("/audit")
    assert resp.status_code == 200
    data = resp.json()
    assert "entries" in data
    assert data["verified"] is True


def test_policy_endpoint(client):
    resp = client.get("/policy")
    assert resp.status_code == 200
    data = resp.json()
    assert "rules" in data
    assert len(data["rules"]) > 0


def test_rules_endpoint(client):
    resp = client.get("/rules")
    assert resp.status_code == 200
    data = resp.json()
    assert data["count"] >= 12


def test_catalog_endpoint(client):
    resp = client.get("/catalog")
    assert resp.status_code == 200
    data = resp.json()
    assert data["count"] > 0


def test_invariant_money_calls(client):
    resp = client.get("/invariant/money-calls")
    assert resp.status_code == 200
    data = resp.json()
    assert "money_calls" in data
    assert "boundary_calls" in data["money_calls"]


def test_attack_scenarios_list(client):
    resp = client.get("/attack/scenarios")
    assert resp.status_code == 200
    data = resp.json()
    assert data["count"] == 8


def test_gateway_proof(client):
    resp = client.get("/gateway/proof")
    assert resp.status_code == 200
    data = resp.json()
    assert "source_sha256" in data


def test_manifest(client):
    resp = client.get("/.well-known/agent-manifest.json")
    assert resp.status_code == 200
    data = resp.json()
    assert "tools" in data


def test_search_products(client):
    resp = client.get("/tools/search_products?query=bat")
    assert resp.status_code == 200
    data = resp.json()
    assert "results" in data


def test_get_product(client):
    resp = client.get("/tools/get_product/BAT-001")
    assert resp.status_code == 200
    data = resp.json()
    # Response may be flat {sku, name, ...} or nested {"product": {...}}
    product = data.get("product", data)
    assert product.get("sku") == "BAT-001"
    assert "price_paise" in product
