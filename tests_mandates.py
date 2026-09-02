"""Mandate security tests.

Critical security tests for INV-3:
  - bad signature -> MANDATE_BAD_SIGNATURE
  - wrong mission -> MANDATE_MISSION_MISMATCH
  - bad version -> MANDATE_BAD_VERSION
  - wrong currency -> MANDATE_BAD_CURRENCY
  - expired -> MANDATE_EXPIRED
  - stale cart -> MANDATE_CART_STALE
  - wrong amount -> MANDATE_AMOUNT_MISMATCH
  - wrong cart hash -> MANDATE_CART_MISMATCH
"""
import sys
import time

sys.stdout.reconfigure(encoding="utf-8")
sys.path.insert(0, r'C:\Users\Lenovo\Downloads\SELLABLE')
import os

os.environ.setdefault('MISSION_HMAC_KEY', 'test-hmac')
os.environ.setdefault('USER_MANDATE_KEY', 'test-mandate-key')

from apps.api.mandates.mandates import (
    MANDATE_VERSION,
    CartMandate,
    IntentMandate,
    MandateError,
    sign_cart,
    sign_intent,
    verify_cart,
    verify_intent,
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


def expect_mandate_error(label, fn, expected_code):
    try:
        fn()
        check(label, False)
    except MandateError as e:
        check(label, e.code == expected_code)


KEY = os.environ.get("USER_MANDATE_KEY", "test-mandate-key")


def make_intent(mission_id="MSN-1", user="u1", ceiling=100000,
                expires_in=3600, version=MANDATE_VERSION, currency="INR"):
    return sign_intent(IntentMandate(
        mission_id=mission_id, user_id=user,
        ceiling_paise=ceiling, expires_at=int(time.time()) + expires_in,
        currency=currency, version=version,
    ), KEY)


def make_cart(mission_id="MSN-1", cart_hash="h", amount=100000,
              signed_offset=0, version=MANDATE_VERSION):
    return sign_cart(CartMandate(
        mission_id=mission_id, cart_hash=cart_hash,
        amount_paise=amount,
        signed_at=int(time.time()) + signed_offset,
        version=version,
    ), KEY)


def _run_all():
    global PASS_COUNT, FAIL_COUNT
    # 1. Happy intent
    intent = make_intent()
    try:
        payload = verify_intent(intent, order_total_paise=100000,
                                expected_mission_id="MSN-1")
        check("1. happy intent verifies", payload["mission_id"] == "MSN-1")
    except MandateError:
        check("1. happy intent verifies", False)

    # 2. Bad signature
    intent = make_intent()
    intent["sig"] = intent["sig"][:-4] + "AAAA"
    expect_mandate_error("2. bad intent signature",
                         lambda: verify_intent(intent, expected_mission_id="MSN-1"),
                         "MANDATE_BAD_SIGNATURE")

    # 3. Wrong mission
    intent = make_intent(mission_id="MSN-A")
    expect_mandate_error("3. intent wrong mission",
                         lambda: verify_intent(intent,
                                                expected_mission_id="MSN-B"),
                         "MANDATE_MISSION_MISMATCH")

    # 4. Expired
    intent = make_intent(expires_in=-10)
    expect_mandate_error("4. intent expired",
                         lambda: verify_intent(intent,
                                                expected_mission_id="MSN-1"),
                         "MANDATE_EXPIRED")

    # 5. Bad version
    intent = make_intent(version=999)
    expect_mandate_error("5. intent bad version",
                         lambda: verify_intent(intent,
                                                expected_mission_id="MSN-1"),
                         "MANDATE_BAD_VERSION")

    # 6. Bad currency
    intent = make_intent(currency="USD")
    expect_mandate_error("6. intent bad currency",
                         lambda: verify_intent(intent,
                                                expected_mission_id="MSN-1"),
                         "MANDATE_BAD_CURRENCY")

    # 7. Ceiling exceeded
    intent = make_intent(ceiling=50000)
    expect_mandate_error("7. intent ceiling exceeded",
                         lambda: verify_intent(intent,
                                                order_total_paise=100000,
                                                expected_mission_id="MSN-1"),
                         "MANDATE_CEILING_EXCEEDED")

    # 8. Happy cart
    cart = make_cart()
    try:
        payload = verify_cart(cart, proposal_hash="h", amount_paise=100000,
                              expected_mission_id="MSN-1")
        check("8. happy cart verifies", payload["cart_hash"] == "h")
    except MandateError:
        check("8. happy cart verifies", False)

    # 9. Cart wrong mission
    cart = make_cart(mission_id="MSN-A")
    expect_mandate_error("9. cart wrong mission",
                         lambda: verify_cart(cart, proposal_hash="h",
                                             amount_paise=100000,
                                             expected_mission_id="MSN-B"),
                         "MANDATE_MISSION_MISMATCH")

    # 10. Cart hash mismatch
    cart = make_cart(cart_hash="h-A")
    expect_mandate_error("10. cart hash mismatch",
                         lambda: verify_cart(cart, proposal_hash="h-B",
                                             amount_paise=100000,
                                             expected_mission_id="MSN-1"),
                         "MANDATE_CART_MISMATCH")

    # 11. Cart amount mismatch
    cart = make_cart(amount=100000)
    expect_mandate_error("11. cart amount mismatch",
                         lambda: verify_cart(cart, proposal_hash="h",
                                             amount_paise=100001,
                                             expected_mission_id="MSN-1"),
                         "MANDATE_AMOUNT_MISMATCH")

    # 12. Cart bad version
    cart = make_cart(version=999)
    expect_mandate_error("12. cart bad version",
                         lambda: verify_cart(cart, proposal_hash="h",
                                             amount_paise=100000,
                                             expected_mission_id="MSN-1"),
                         "MANDATE_BAD_VERSION")

    # 13. Cart stale (signed before approval was issued)
    cart = make_cart(signed_offset=-7200)  # 2 hours ago
    expect_mandate_error("13. cart stale (older than approval)",
                         lambda: verify_cart(cart, proposal_hash="h",
                                             amount_paise=100000,
                                             expected_mission_id="MSN-1",
                                             approval_issued_at=int(time.time()) - 60),
                         "MANDATE_CART_STALE")

    # 14. Malformed token
    expect_mandate_error("14. intent malformed (string)",
                         lambda: verify_intent("not a dict"),
                         "MANDATE_MALFORMED")

    # 15. Malformed token (no payload)
    expect_mandate_error("15. intent missing payload",
                         lambda: verify_intent({"sig": "x"}),
                         "MANDATE_MALFORMED")

    print()
    print(f"Results: {PASS_COUNT} passed, {FAIL_COUNT} failed")


if "pytest" not in sys.modules:
    _run_all()
else:
    def test_mandate_full_suite():
        _run_all()
        assert FAIL_COUNT == 0, f"{FAIL_COUNT} mandate checks failed"
