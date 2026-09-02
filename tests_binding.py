"""Tests for the approval binding system.

Critical security tests:
  - approve mission A, mandate mission B -> REJECT MISSION_MISMATCH
  - approve cart A, change SKU -> REJECT SKU_SET_MISMATCH
  - approve Rs 1000, change to Rs 1001 -> REJECT AMOUNT_MISMATCH
  - approve quote A, present quote B -> REJECT QUOTE_MISMATCH
  - same binding used twice -> BINDING_CONSUMED
  - binding past expiry -> BINDING_EXPIRED
  - wrong cart hash -> CART_HASH_MISMATCH
  - wrong currency -> CURRENCY_MISMATCH
"""
import sys

sys.stdout.reconfigure(encoding="utf-8")
sys.path.insert(0, r'C:\Users\Lenovo\Downloads\SELLABLE')
import os

os.environ.setdefault('MISSION_HMAC_KEY', 'test-hmac')
os.environ.setdefault('USER_MANDATE_KEY', 'test-mandate-key')

from apps.api.approval import (
    register,
    reset_consumed,
    verify,
)

PASS_COUNT = 0
FAIL_COUNT = 0


def check(name, ok):
    global PASS_COUNT, FAIL_COUNT
    if ok:
        PASS_COUNT += 1
        print("PASS " + name)
    else:
        FAIL_COUNT += 1
        print("FAIL " + name)


def make(seq, **kw):
    """Register a binding with sensible defaults."""
    defaults = dict(
        mission_id="MSN-1",
        proposal_hash="hash-A",
        cart_hash="hash-A",
        quote_id="Q-1",
        amount_paise=100000,
        currency="INR",
        skus=[("BAT-001", 1)],
    )
    # Sync cart_hash with proposal_hash unless explicitly overridden
    if "proposal_hash" in kw and "cart_hash" not in kw:
        kw["cart_hash"] = kw["proposal_hash"]
    defaults.update(kw)
    return register(seq, **defaults)


def verify_call(seq, **kw):
    defaults = dict(
        mission_id="MSN-1",
        proposal_hash="hash-A",
        cart_hash="hash-A",
        quote_id="Q-1",
        amount_paise=100000,
        currency="INR",
        skus=[("BAT-001", 1)],
    )
    defaults.update(kw)
    return verify(seq=seq, **defaults)


def _run_all():
    global PASS_COUNT, FAIL_COUNT
    # 1. Happy path
    reset_consumed()
    make(100, mission_id="MSN-A", proposal_hash="h-A", quote_id="Q-A",
         skus=[("BAT-001", 1)], amount_paise=100000)
    ok, reason, _ = verify_call(100, mission_id="MSN-A", proposal_hash="h-A",
                                cart_hash="h-A", quote_id="Q-A",
                                skus=[("BAT-001", 1)], amount_paise=100000)
    check("1. happy path verifies", ok and reason == "OK")

    # 2. Wrong mission
    reset_consumed()
    make(200, mission_id="MSN-A")
    ok, reason, _ = verify_call(200, mission_id="MSN-B")
    check("2. wrong mission rejected", not ok and reason == "MISSION_MISMATCH")

    # 3. Wrong quote (binding has quote_id=Q-A, executor sends Q-B)
    reset_consumed()
    make(300, quote_id="Q-A")
    ok, reason, _ = verify_call(300, quote_id="Q-B")
    check("3. wrong quote rejected", not ok and reason == "QUOTE_MISMATCH")

    # 4. Wrong cart (different SKU)
    reset_consumed()
    make(400, skus=[("BAT-001", 1)], proposal_hash="h", cart_hash="h")
    ok, reason, _ = verify_call(400, proposal_hash="h", cart_hash="h",
                                skus=[("BAT-002", 1)])
    check("4. cart mutation rejected (SKU)",
          not ok and reason == "SKU_SET_MISMATCH")

    # 5. Amount drift
    reset_consumed()
    make(500, amount_paise=100000)
    ok, reason, _ = verify_call(500, amount_paise=100001)
    check("5. amount drift rejected",
          not ok and reason == "AMOUNT_MISMATCH")

    # 6. Currency mismatch
    reset_consumed()
    make(600, currency="INR")
    ok, reason, _ = verify_call(600, currency="USD")
    check("6. currency mismatch rejected",
          not ok and reason == "CURRENCY_MISMATCH")

    # 7. Proposal hash mismatch
    reset_consumed()
    make(700, proposal_hash="hash-A", cart_hash="hash-A")
    ok, reason, _ = verify_call(700, proposal_hash="hash-B",
                                cart_hash="hash-B")
    check("7. proposal hash mismatch rejected",
          not ok and reason == "PROPOSAL_HASH_MISMATCH")

    # 8. Single-use enforcement
    reset_consumed()
    make(800, skus=[("BAT-001", 1)], amount_paise=100000,
         proposal_hash="h", cart_hash="h")
    ok1, r1, _ = verify_call(800, skus=[("BAT-001", 1)],
                             amount_paise=100000,
                             proposal_hash="h", cart_hash="h")
    ok2, r2, _ = verify_call(800, skus=[("BAT-001", 1)],
                             amount_paise=100000,
                             proposal_hash="h", cart_hash="h")
    check("8a. first use passes", ok1)
    check("8b. second use rejected as BINDING_CONSUMED",
          not ok2 and r2 == "BINDING_CONSUMED")

    # 9. Expired binding (TTL in the past)
    reset_consumed()
    make(900, ttl_seconds=-10)
    ok, reason, _ = verify_call(900)
    check("9. expired binding rejected",
          not ok and reason == "BINDING_EXPIRED")

    # 10. Wrong cart hash
    reset_consumed()
    make(1000, cart_hash="hash-A")
    ok, reason, _ = verify_call(1000, cart_hash="hash-B")
    check("10. cart hash mismatch rejected",
          not ok and reason == "CART_HASH_MISMATCH")

    print()
    print(f"Results: {PASS_COUNT} passed, {FAIL_COUNT} failed")


# Import-safe: unit tests may import this module during collection;
# real suite lives under tests/*. Only run standalone body outside pytest.
if "pytest" not in sys.modules:
    _run_all()
else:
    # When collected by pytest, expose as a real test so `pytest tests_binding.py` still runs it.
    def test_binding_full_suite():
        _run_all()
        assert FAIL_COUNT == 0, f"{FAIL_COUNT} binding checks failed"
