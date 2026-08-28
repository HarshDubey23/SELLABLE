"""Smoke tests for judge-facing HTTP surfaces."""
from fastapi.testclient import TestClient

from apps.api.main import app


def test_judge_facing_endpoints_are_mounted():
    client = TestClient(app)
    for path in (
        "/health",
        "/.well-known/agent-manifest.json",
        "/tools/search_products",
        "/tools/scan_copy",
        "/metrics/revenue",
        "/missions",
    ):
        response = (
            client.post(path, json={"text": "plain honest copy"})
            if path == "/tools/scan_copy"
            else client.get(path)
        )
        assert response.status_code == 200, f"{path}: {response.text[:200]}"
