from fastapi.testclient import TestClient

from apps.api.main import app

client = TestClient(app)

def test_home_page():
    res = client.get("/")
    assert res.status_code == 200
    assert "SELLABLE" in res.text

def test_mission_page():
    res = client.get("/mission")
    assert res.status_code == 200
    assert "Live Mission" in res.text

def test_gateway_ui_page():
    res = client.get("/gateway-ui")
    assert res.status_code == 200
    assert "Policy Gateway" in res.text

def test_attack_ui_page():
    res = client.get("/attack-ui")
    assert res.status_code == 200
    assert "Attack Lab" in res.text

def test_audit_ui_page():
    res = client.get("/audit-ui")
    assert res.status_code == 200
    assert "Audit" in res.text

def test_metrics_ui_page():
    res = client.get("/metrics")
    assert res.status_code == 200

def test_status_endpoint():
    res = client.get("/status")
    assert res.status_code == 200
    data = res.json()
    assert data.get("service") == "SELLABLE"

def test_manifest_endpoint():
    res = client.get("/.well-known/agent-manifest.json")
    assert res.status_code == 200
    data = res.json()
    assert data.get("merchant", {}).get("name") == "SELLABLE Demo Dukaan"

def test_catalog_search():
    res = client.get("/tools/search_products?query=cricket")
    assert res.status_code == 200
    data = res.json()
    assert "results" in data
    assert len(data["results"]) > 0
