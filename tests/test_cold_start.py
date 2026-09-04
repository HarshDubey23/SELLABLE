"""Cold Start Test Suite — Proves app boots and renders all HTML routes with zero keys and empty DB.

Cross-platform parity: Windows, macOS, Linux.
"""
from __future__ import annotations

import os
import tempfile

import pytest
from fastapi.testclient import TestClient


@pytest.fixture(autouse=True)
def cold_start_env(monkeypatch):
    """Sets up a cold-start environment with no keys and a temporary DB."""
    tmp_dir = tempfile.mkdtemp(prefix="sellable-cold-")
    tmp_db = os.path.join(tmp_dir, "cold_start.db")
    monkeypatch.setenv("SELLABLE_DB_PATH", tmp_db)
    monkeypatch.setenv("RAZORPAY_KEY_ID", "")
    monkeypatch.setenv("RAZORPAY_KEY_SECRET", "")
    monkeypatch.setenv("GEMINI_API_KEY", "")
    monkeypatch.setenv("APP_API_KEY", "cold_start_dev_key")
    monkeypatch.setenv("MISSION_HMAC_KEY", "cold_start_hmac_key")
    monkeypatch.setenv("USER_MANDATE_KEY", "cold_start_mandate_key")
    yield tmp_db


def test_cold_start_routes():
    """Boots app with empty keys and asserts all 13 HTML routes return 200 OK without tracebacks."""
    from apps.api.main import app
    client = TestClient(app)

    routes = [
        "/",
        "/mission",
        "/judge",
        "/chaos",
        "/architecture",
        "/attack-ui",
        "/audit-ui",
        "/gateway-ui",
        "/products",
        "/why",
        "/demo",
        "/demo/checkout",
        "/demo/failures",
    ]

    for route in routes:
        response = client.get(route)
        assert response.status_code == 200, f"Route {route} failed with HTTP {response.status_code}"
        content = response.text
        assert "Traceback (most recent call last)" not in content, f"Traceback detected on route {route}"
        assert "Internal Server Error" not in content, f"Internal Server Error detected on route {route}"
