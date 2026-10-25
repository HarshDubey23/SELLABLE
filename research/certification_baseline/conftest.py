"""Fixtures for the certification baseline.

Mirrors tests/conftest.py (isolated SQLite file, test keys, simulated
provider) but lives outside `testpaths`, so `make ci`, the README test
count and docs/generated/truth.json are unaffected.
"""
from pathlib import Path

import pytest


@pytest.fixture(autouse=True)
def _isolated(tmp_path, monkeypatch):
    db_file = tmp_path / "baseline.db"
    monkeypatch.setenv("SELLABLE_DB_PATH", str(db_file))
    monkeypatch.setenv("USER_MANDATE_KEY", "testmandatekey1234567890abcdef12")
    monkeypatch.setenv("APP_API_KEY", "test_app_api_key")
    monkeypatch.setenv("MISSION_HMAC_KEY", "testmissionhmackey1234567890abc1")
    monkeypatch.setenv("RAZORPAY_KEY_ID", "")          # simulated provider
    monkeypatch.setenv("RAZORPAY_KEY_SECRET", "")
    monkeypatch.setenv("RAZORPAY_WEBHOOK_SECRET", "test_webhook_secret")

    from apps.api.store import db as store
    store._DB_PATH = Path(db_file)
    store.init_schema()
    from apps.api.audit import chain
    chain._chain.clear()
    chain._load_from_db()
    from apps.api import ratelimit
    ratelimit.reset()
    from apps.api import execution_provider as ep
    ep._SIMULATED_SINGLETON._orders.clear()
    yield db_file
    ratelimit.reset()
