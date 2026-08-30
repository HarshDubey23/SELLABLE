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


def test_gateway_proof_live():
    """Phase 1: the purity proof endpoint is live, machine-checkable, and
    agrees with the registry. If someone adds a forbidden import to the
    gateway, this goes red.

    Adapted to the REAL /gateway/proof response keys (apps/api/gateway/proof.py
    compute_proof()): files, total_lines, llm_imports_detected,
    io_calls_detected, forbidden_patterns_seen, source_sha256,
    invariant_test. The proof carries no rule_count key, so registry
    agreement is asserted against GET /policy (derived from RULE_REGISTRY).
    """
    client = TestClient(app)
    resp = client.get("/gateway/proof")
    assert resp.status_code == 200
    body = resp.json()
    assert body["llm_imports_detected"] == 0
    assert body["io_calls_detected"] == 0
    assert body["forbidden_patterns_seen"] == []   # the imported-forbidden
    # list must be empty
    assert body["invariant_test"] == "tests/invariants/test_gateway_purity.py"
    assert body["files"] >= 8  # 8 gateway modules at Phase 1 baseline
    from apps.api.gateway.registry import rules_count
    policy = client.get("/policy")
    assert policy.status_code == 200
    assert policy.json()["rules_count"] == rules_count()  # proof surface and
    # registry must agree
