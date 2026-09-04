"""
tests/test_audit_chain_true_tamper.py — True SQLite Persisted Ledger Tamper Detection

Section 18:
- Step 1: Valid hash chain passes verification.
- Step 2: Directly tamper with a historical persisted record in SQLite.
- Step 3: verify_chain() detects tamper and returns False.
- Step 4: Restoring the exact payload hash recovers verification to True.
"""
from apps.api.audit import chain as audit_chain
from apps.api.store import db as store


def test_true_sqlite_tamper_detection():
    # 1. Ensure clean initial verification
    assert audit_chain.verify() is True

    # 2. Append a known event
    seq = audit_chain.append(
        actor="test_tamper_actor",
        action="TEST_ACTION",
        payload={"note": "original_payload"}
    )
    assert audit_chain.verify() is True

    # 3. Read original record from SQLite
    row = store.query_one("SELECT payload_hash FROM audit_chain WHERE seq = ?", (seq,))
    assert row is not None
    orig_hash = row["payload_hash"]

    try:
        # 4. Tamper with historical persisted event in SQLite
        store.execute("UPDATE audit_chain SET payload_hash = ? WHERE seq = ?", ("forged_tampered_payload_hash", seq))

        # 5. verify() MUST fail on the tampered ledger
        tampered_ok = audit_chain.verify()
        assert tampered_ok is False, "Audit chain verification MUST fail after historical row mutation!"
    finally:
        # 6. Restore original row
        store.execute("UPDATE audit_chain SET payload_hash = ? WHERE seq = ?", (orig_hash, seq))

    # 7. Verification must pass once restored
    assert audit_chain.verify() is True
