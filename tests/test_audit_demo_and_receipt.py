"""The two claims a reader is asked to check for themselves.

1. The audit chain's hash preimage is exactly what the receipt says it
   is, so anyone with SHA-256 can verify a block without trusting this
   server's answer. If the preimage helper ever drifts from
   `audit.chain._hash`, this goes red.

2. The tamper demo never touches the ledger. It flips a bit in a copy,
   reports where verification would halt, and the on-disk chain still
   verifies afterwards.
"""
from __future__ import annotations

import hashlib

import pytest
from fastapi.testclient import TestClient

from apps.api import ratelimit
from apps.api.audit import chain as audit_chain
from apps.api.audit_demo import hash_preimage


@pytest.fixture
def client(monkeypatch):
    monkeypatch.setenv("RAZORPAY_KEY_ID", "")
    monkeypatch.setenv("RAZORPAY_KEY_SECRET", "")
    from apps.api.main import app
    ratelimit.reset()
    return TestClient(app)


def _buy(client):
    r = client.post("/discovery/checkout",
                    json={"sku": "BAT-001", "budget_paise": 300000})
    assert r.status_code == 200, r.text
    return r.json()


# ------------------------------------------- verify it in your own tool

def test_the_published_preimage_hashes_to_the_stored_hash_for_every_block(client):
    """Not a sample — every block on the chain."""
    _buy(client)
    entries = audit_chain.entries()
    assert len(entries) > 1, "need a non-trivial chain to make this meaningful"
    for entry in entries:
        recomputed = hashlib.sha256(
            hash_preimage(entry).encode("utf-8")).hexdigest()
        assert recomputed == entry["hash"], (
            f"seq {entry['seq']}: the preimage published to clients does not "
            f"hash to the stored hash; browser-side verification would be a lie")


def test_the_block_endpoint_publishes_a_checkable_preimage(client):
    _buy(client)
    r = client.get("/audit/block/1")
    assert r.status_code == 200
    b = r.json()
    assert b["hash_algorithm"] == "sha256"
    assert hashlib.sha256(b["hash_preimage"].encode()).hexdigest() == b["hash"]
    # The format string has to describe the real format, or someone
    # following it with sha256sum gets a mismatch and concludes we lied.
    assert b["hash_preimage_format"].startswith(
        "seq|ts|actor|action|payload_hash|prev_hash")


def test_an_unknown_block_is_404_not_a_guess(client):
    r = client.get("/audit/block/99999999")
    assert r.status_code == 404
    assert r.json()["detail"]["error"]["error_code"] == "UNKNOWN_BLOCK"


# ------------------------------------------------------- tamper cascade

def test_tampering_halts_verification_and_invalidates_everything_after(client):
    _buy(client)
    length = len(audit_chain.entries())
    target = 1

    r = client.post("/audit/tamper-demo", json={"block_seq": target})
    assert r.status_code == 200
    body = r.json()

    assert body["halt_at_block"] == target
    assert body["original_hash"] != body["recomputed_hash_after_tamper"]
    assert body["blocks_invalidated"] == length - target
    assert "in-memory copy" in body["disclosure"]


def test_the_tamper_demo_leaves_the_real_ledger_verifying(client):
    _buy(client)
    before_ok, _ = audit_chain.verify_strict()
    assert before_ok

    body = client.post("/audit/tamper-demo", json={"block_seq": 1}).json()
    assert body["on_disk_chain"] == "VERIFIED"

    after_ok, reason = audit_chain.verify_strict()
    assert after_ok, f"the tamper demo damaged the real chain: {reason}"


def test_tampering_an_unknown_block_is_refused(client):
    assert client.post("/audit/tamper-demo",
                       json={"block_seq": 99999999}).status_code == 404


def test_tamper_demo_rejects_a_negative_sequence(client):
    assert client.post("/audit/tamper-demo",
                       json={"block_seq": -1}).status_code == 422


# --------------------------------------------------------------- receipt

def test_the_receipt_reports_only_what_the_rows_say(client):
    order = _buy(client)
    r = client.get(f"/api/v1/receipt/{order['execution_id']}")
    assert r.status_code == 200
    receipt = r.json()

    assert receipt["final_amount_paise"] == order["amount_paise"]
    assert receipt["priced_from"] == "server-side merchant catalog"
    assert receipt["gateway_decision"] == "APPROVE"
    assert receipt["approval_binding"]["single_use"] is True
    assert receipt["approval_binding"]["consumed_at"] is not None
    assert receipt["issuer"] == "in_process_demo_issuer", \
        "the in-process issuer must be disclosed on the receipt, not hidden"

    # An order is not a payment. Nothing may claim settlement without a
    # signature-verified webhook event.
    assert receipt["settlement"]["confirmed"] is False
    assert receipt["settlement"]["events"] == []


def test_the_receipt_anchor_is_verifiable_by_the_reader(client):
    order = _buy(client)
    anchor = client.get(
        f"/api/v1/receipt/{order['execution_id']}").json()["audit_anchor"]
    computed = hashlib.sha256(anchor["hash_preimage"].encode()).hexdigest()
    assert computed == anchor["hash"]


def test_the_receipt_resolves_any_of_the_three_identifiers(client):
    order = _buy(client)
    for ref in (order["execution_id"], order["mission_id"], order["order_id"]):
        r = client.get(f"/api/v1/receipt/{ref}")
        assert r.status_code == 200, f"{ref} should resolve"
        assert r.json()["execution_id"] == order["execution_id"]


def test_an_unknown_receipt_reference_is_404(client):
    r = client.get("/api/v1/receipt/definitely-not-a-thing")
    assert r.status_code == 404
    assert r.json()["detail"]["error"]["error_code"] == "UNKNOWN_REFERENCE"


# ----------------------------------------------------------- kill switch

def test_the_kill_switch_is_gated_off_without_explicit_opt_in(client):
    """It calls os._exit. It must refuse unless someone asked for it twice."""
    status = client.get("/demo/kill-switch").json()
    assert status["enabled"] is False
    assert "CHAOS_ENABLED" in status["reason"]

    r = client.post("/demo/kill-switch", json={"confirm": "KILL"})
    assert r.status_code == 403
    assert r.json()["detail"]["error"]["error_code"] == "CHAOS_DISABLED"


def test_the_kill_switch_needs_both_gates_not_just_one(client, monkeypatch):
    """CHAOS_ENABLED alone is not enough on a keyless deploy."""
    monkeypatch.setenv("CHAOS_ENABLED", "true")
    # provider is still simulated because the fixture cleared the keys
    assert client.get("/demo/kill-switch").json()["enabled"] is False
    assert client.post("/demo/kill-switch",
                       json={"confirm": "KILL"}).status_code == 403
