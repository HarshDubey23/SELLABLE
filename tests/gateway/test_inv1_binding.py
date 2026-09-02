"""
tests/gateway/test_inv1_binding.py — INV-1 binding persistence
"""
import time, pytest
from apps.api import approval


def test_binding_survives_reload(tmp_path, monkeypatch):
    """A registered binding persists in SQLite and can be retrieved by get()."""
    from apps.api.store import db as store
    store._DB_PATH = tmp_path / "db2.db"
    store.init_schema()
    from apps.api.audit import chain as audit_chain
    audit_chain._chain.clear()
    audit_chain._load_from_db()

    now = int(time.time())
    b = approval.register(
        seq=42,
        mission_id="m-persist",
        proposal_hash="p" * 64,
        cart_hash="p" * 64,
        quote_id="",
        amount_paise=10000,
        currency="INR",
        skus=[("SKU-A", 1)],
        now_ts=now,
    )
    assert b.seq == 42

    fetched = approval.get(42)
    assert fetched is not None
    assert fetched.mission_id == "m-persist"
    assert fetched.amount_paise == 10000


def test_binding_cross_mission_rejected():
    """verify() must reject if mission_id in call mismatches binding."""
    now = int(time.time())
    approval.register(
        seq=100,
        mission_id="mission-A",
        proposal_hash="a" * 64,
        cart_hash="a" * 64,
        quote_id="",
        amount_paise=5000,
        currency="INR",
        skus=[("SKU-1", 1)],
        now_ts=now,
    )
    ok, code, _ = approval.verify(
        seq=100,
        mission_id="mission-B",  # different mission!
        proposal_hash="a" * 64,
        cart_hash="a" * 64,
        quote_id="",
        amount_paise=5000,
        currency="INR",
        skus=[("SKU-1", 1)],
        now_ts=now + 1,
    )
    assert not ok
    assert code == "MISSION_MISMATCH"


def test_binding_amount_mismatch_rejected():
    """verify() must reject if amount_paise differs from binding."""
    now = int(time.time())
    approval.register(
        seq=200,
        mission_id="mission-C",
        proposal_hash="c" * 64,
        cart_hash="c" * 64,
        quote_id="",
        amount_paise=5000,
        currency="INR",
        skus=[("SKU-1", 1)],
        now_ts=now,
    )
    ok, code, _ = approval.verify(
        seq=200,
        mission_id="mission-C",
        proposal_hash="c" * 64,
        cart_hash="c" * 64,
        quote_id="",
        amount_paise=9999,  # tampered!
        currency="INR",
        skus=[("SKU-1", 1)],
        now_ts=now + 1,
    )
    assert not ok
    assert code == "AMOUNT_MISMATCH"


def test_binding_expired():
    """Bindings with TTL of 0 must be rejected as expired."""
    now = int(time.time())
    approval.register(
        seq=300,
        mission_id="mission-D",
        proposal_hash="d" * 64,
        cart_hash="d" * 64,
        quote_id="",
        amount_paise=1000,
        currency="INR",
        skus=[("SKU-X", 1)],
        ttl_seconds=0,
        now_ts=now - 100,  # issued in the past
    )
    ok, code, _ = approval.verify(
        seq=300,
        mission_id="mission-D",
        proposal_hash="d" * 64,
        cart_hash="d" * 64,
        quote_id="",
        amount_paise=1000,
        currency="INR",
        skus=[("SKU-X", 1)],
        now_ts=now,  # now > expires_at
    )
    assert not ok
    assert code == "BINDING_EXPIRED"
