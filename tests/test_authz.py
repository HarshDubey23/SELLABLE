"""Authz tests (F-08, Phase 3): mutating routes are gated by X-API-Key.
- no key    -> 401
- wrong key -> 401
- env unset -> 503 fail-closed (error names APP_API_KEY)
- good key  -> passes the gate (any status except 401/503)

Route dependencies run BEFORE body validation in FastAPI, so an empty body
still exercises the gate. PROTECTED_POST = /tools/quote, the simplest mutating
route in the FACT 3 inventory.
"""
import os

from fastapi.testclient import TestClient

from apps.api.main import app

PROTECTED_POST = "/tools/quote"


def _client() -> TestClient:
    return TestClient(app)


def test_missing_key_401(monkeypatch):
    monkeypatch.setenv("APP_API_KEY", "test-key-ci")
    resp = _client().post(PROTECTED_POST, json={})
    assert resp.status_code == 401, resp.text


def test_wrong_key_401(monkeypatch):
    monkeypatch.setenv("APP_API_KEY", "test-key-ci")
    resp = _client().post(
        PROTECTED_POST, json={}, headers={"X-API-Key": "definitely-wrong"}
    )
    assert resp.status_code == 401, resp.text


def test_unset_key_503_fail_closed(monkeypatch):
    monkeypatch.delenv("APP_API_KEY", raising=False)
    resp = _client().post(PROTECTED_POST, json={}, headers={"X-API-Key": "anything"})
    assert resp.status_code == 503, resp.text
    assert "APP_API_KEY" in resp.json()["detail"]


def test_good_key_passes_gate(monkeypatch):
    monkeypatch.setenv("APP_API_KEY", "test-key-ci")
    resp = _client().post(PROTECTED_POST, json={}, headers={"X-API-Key": "test-key-ci"})
    assert resp.status_code not in (401, 503), resp.text
