"""Shared pytest fixtures for the SELLABLE test suite."""
from pathlib import Path

import pytest


@pytest.fixture(autouse=True)
def _isolated_db(tmp_path, monkeypatch):
    db_file = str(tmp_path / "test.db")
    monkeypatch.setenv("SELLABLE_DB_PATH", db_file)
    monkeypatch.setenv("USER_MANDATE_KEY", "testmandatekey1234567890abcdef12")
    monkeypatch.setenv("APP_API_KEY", "test_app_api_key")
    monkeypatch.setenv("MISSION_HMAC_KEY", "testmissionhmackey1234567890abc1")
    monkeypatch.setenv("RAZORPAY_KEY_ID", "rzp_test_dummy")
    monkeypatch.setenv("RAZORPAY_KEY_SECRET", "dummy_secret")
    monkeypatch.setenv("RAZORPAY_WEBHOOK_SECRET", "test_webhook_secret")
    from apps.api.store import db as store
    store._DB_PATH = Path(db_file)
    store.init_schema()
    from apps.api.audit import chain as audit_chain
    audit_chain._chain.clear()
    audit_chain._load_from_db()

    # The rate limiter is process-global and time-windowed, so without this
    # a test that deliberately exhausts a bucket leaves the next sixty
    # seconds of tests getting 429s. That makes the suite pass or fail on
    # how fast the machine is, which is how this first showed up: green
    # locally and on Ubuntu, red on one Windows runner.
    from apps.api import ratelimit
    ratelimit.reset()
    yield
    ratelimit.reset()
