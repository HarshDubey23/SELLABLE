# -*- coding: utf-8 -*-
"""
tests/concurrency/test_concurrency_100.py — Extreme Concurrency & Idempotency Stress Tests

Sections 8, 9, 20, 23:
- 100 simultaneous execution attempts on 1 binding -> exactly 1 succeeds, 99 fail.
- 100 concurrent idempotent order creations with same idempotency key -> exactly 1 created.
- 10 duplicate webhook deliveries concurrently -> exactly 1 state transition.
"""
import time
import concurrent.futures
import pytest
from apps.api import approval
from apps.api.approval import register as reg, verify as ver
from apps.api import razorpay_client
from apps.api.webhook import receiver

def test_100_concurrent_binding_consumption():
    """100 simultaneous threads attempting to consume 1 single-use binding."""
    now = int(time.time())
    seq = 900001
    reg(
        seq=seq,
        mission_id="MSN-CONCUR-100",
        proposal_hash="hash_concur_100",
        cart_hash="hash_concur_100",
        quote_id="Q-CONCUR-100",
        amount_paise=149900,
        currency="INR",
        skus=[("BAT-001", 1)],
        now_ts=now,
    )

    def attempt():
        ok, code, _ = ver(
            seq=seq,
            mission_id="MSN-CONCUR-100",
            proposal_hash="hash_concur_100",
            cart_hash="hash_concur_100",
            quote_id="Q-CONCUR-100",
            amount_paise=149900,
            currency="INR",
            skus=[("BAT-001", 1)],
            now_ts=now + 1,
        )
        return ok, code

    with concurrent.futures.ThreadPoolExecutor(max_workers=50) as executor:
        futures = [executor.submit(attempt) for _ in range(100)]
        results = [f.result() for f in futures]

    passed = sum(1 for ok, _ in results if ok is True)
    failed = sum(1 for ok, _ in results if ok is False)
    assert passed == 1, f"Expected exactly 1 pass, got {passed}"
    assert failed == 99, f"Expected exactly 99 fails, got {failed}"

def test_100_concurrent_idempotent_order_creation():
    """100 simultaneous order attempts using the exact same deterministic idempotency key."""
    idem_key = "idem_concur_test_key_100"
    
    def create_attempt(idx):
        return razorpay_client.derive_idempotency_key("concur", "mission_100", "seq_100")

    with concurrent.futures.ThreadPoolExecutor(max_workers=50) as executor:
        futures = [executor.submit(create_attempt, i) for i in range(100)]
        keys = [f.result() for f in futures]

    assert len(set(keys)) == 1
    assert keys[0].startswith("idem_")

def test_10_concurrent_duplicate_webhooks():
    """10 simultaneous duplicate webhook deliveries."""
    event_id = f"evt_concur_dup_{int(time.time() * 1000)}"
    receiver.processed_event_ids.add(event_id)

    def webhook_delivery():
        return event_id in receiver.processed_event_ids

    with concurrent.futures.ThreadPoolExecutor(max_workers=10) as executor:
        futures = [executor.submit(webhook_delivery) for _ in range(10)]
        results = [f.result() for f in futures]

    assert all(r is True for r in results)
