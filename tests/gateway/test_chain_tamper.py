"""
tests/gateway/test_chain_tamper.py — Audit chain tamper detection
"""
from apps.api.audit import chain as audit_chain


def test_chain_verifies_after_appends():
    audit_chain.append("test", "event_a", {"data": 1})
    audit_chain.append("test", "event_b", {"data": 2})
    ok, reason = audit_chain.verify_strict()
    assert ok, f"Chain failed verification: {reason}"


def test_chain_detects_genesis_tamper():
    audit_chain.append("actor", "action", {"x": 1})
    # Tamper the genesis block in memory
    if audit_chain._chain:
        original = audit_chain._chain[0]["hash"]
        audit_chain._chain[0]["hash"] = "0" * 64
        ok, _ = audit_chain.verify_strict()
        assert not ok, "Chain should fail after genesis hash tamper"
        # Restore
        audit_chain._chain[0]["hash"] = original


def test_chain_detects_mid_chain_tamper():
    for i in range(3):
        audit_chain.append("actor", f"action_{i}", {"i": i})
    # Tamper the second entry
    if len(audit_chain._chain) > 1:
        audit_chain._chain[1]["payload_hash"] = "tampered" * 8
        ok, reason = audit_chain.verify_strict()
        assert not ok, "Chain should fail after payload_hash tamper"


def test_empty_chain_verifies():
    # Starting fresh (cleared in conftest)
    ok, reason = audit_chain.verify_strict()
    assert ok
