"""Protocol adapter surface tests (Phase 4).

ACP and AP2 translate into the canonical executor; the gateway decides.
x402 is an honest 501 stub. Every adapter POST is a mutating route gated
by X-API-Key (F-08). The end-to-end case proves R12 binds protocol
artifacts through the adapter path (executor REJECT R12 on ceiling drift).
"""
import os
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import pytest
from fastapi.testclient import TestClient

os.environ.setdefault("MISSION_HMAC_KEY", "test-protocol-mission-key")
os.environ.setdefault("USER_MANDATE_KEY", "test-protocol-mandate-key")

from apps.api.main import app  # noqa: E402
from apps.api.mandates.mandates import IntentMandate, sign_intent  # noqa: E402
from apps.api.products import CATALOG  # noqa: E402
from scripts.sign_mission import sign_blob  # noqa: E402

KEY = {"X-API-Key": os.environ["APP_API_KEY"]}
BAT = CATALOG["BAT-001"]["price_paise"]


def _client() -> TestClient:
    return TestClient(app)


def _signed_mission(mission_id: str, budget: int = 200000) -> dict:
    m = {"mission_id": mission_id, "intent": "protocol test",
         "budget_paise": budget,
         "allowed_categories": ["cricket"], "forbidden_categories": [],
         "upsell_cap": 1.3, "expires_at": int(time.time()) + 3600}
    m["signature"] = sign_blob(m)
    return m


def _intent_mandate(mission_id: str, ceiling: int) -> dict:
    im = IntentMandate(mission_id=mission_id, user_id="user-protocol",
                       ceiling_paise=ceiling,
                       expires_at=int(time.time()) + 1800)
    return sign_intent(im, os.environ["USER_MANDATE_KEY"])


# ---------------- ACP ----------------

def test_acp_happy_path_translates_and_executes():
    m = _signed_mission(f"MSN-ACP-{int(time.time()*1000)}")
    r = _client().post("/protocol/acp/checkout_sessions", headers=KEY, json={
        "mission": m,
        "line_items": [{"id": "BAT-001", "quantity": 1}],
    })
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["protocol"] == "ACP"
    assert body["translated_items"] == [{"sku": "BAT-001", "qty": 1}]
    assert body["executor"]["data"]["decision"] == "APPROVE", body["executor"]


def test_acp_unknown_sku_400():
    m = _signed_mission(f"MSN-ACP-BAD-{int(time.time()*1000)}")
    r = _client().post("/protocol/acp/checkout_sessions", headers=KEY, json={
        "mission": m,
        "line_items": [{"id": "NO-SUCH-SKU", "quantity": 1}],
    })
    assert r.status_code == 400
    assert "NO-SUCH-SKU" in r.text


def test_acp_protocol_scope_binds_via_r12():
    """End-to-end: the adapter's protocol_scope reaches the gateway; R12
    rejects with the drifted ceiling — the adapter never decided anything."""
    m = _signed_mission(f"MSN-ACP-R12-{int(time.time()*1000)}")
    r = _client().post("/protocol/acp/checkout_sessions", headers=KEY, json={
        "mission": m,
        "line_items": [{"id": "BAT-001", "quantity": 1}],
        "protocol_scope": {"amount_ceiling_paise": BAT - 1},
    })
    assert r.status_code == 200, r.text
    ex = r.json()["executor"]
    assert ex["data"]["decision"] == "REJECT"
    assert ex["data"]["rule_id"] == "R12_PROTOCOL_SCOPE"
    assert "amount ceiling" in ex["data"]["reason"]


def test_acp_requires_api_key():
    r = _client().post("/protocol/acp/checkout_sessions", json={"mission": {}})
    assert r.status_code == 401


# ---------------- AP2 ----------------

def test_ap2_happy_path_intent_verified_and_executed():
    mid = f"MSN-AP2-{int(time.time()*1000)}"
    m = _signed_mission(mid)
    blob = _intent_mandate(mid, ceiling=200000)
    r = _client().post("/protocol/ap2/mandates/evaluate", headers=KEY, json={
        "mission": m,
        "items": [{"sku": "BAT-001", "qty": 1}],
        "intent_mandate": blob,
    })
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["protocol"] == "AP2"
    assert body["intent_verified"]["mission_id"] == mid
    assert body["executor"]["data"]["decision"] == "APPROVE", body["executor"]


def test_ap2_intent_ceiling_enforced_by_wallet_verifier():
    """The wallet verifier refuses BEFORE the gateway: ceiling < catalog total."""
    mid = f"MSN-AP2-CEIL-{int(time.time()*1000)}"
    m = _signed_mission(mid)
    blob = _intent_mandate(mid, ceiling=BAT - 1)
    r = _client().post("/protocol/ap2/mandates/evaluate", headers=KEY, json={
        "mission": m,
        "items": [{"sku": "BAT-001", "qty": 1}],
        "intent_mandate": blob,
    })
    assert r.status_code == 403
    assert "MANDATE_CEILING_EXCEEDED" in r.text


def test_ap2_bad_signature_403():
    mid = f"MSN-AP2-BADSIG-{int(time.time()*1000)}"
    m = _signed_mission(mid)
    blob = _intent_mandate(mid, ceiling=200000)
    blob["sig"] = "bogus"
    r = _client().post("/protocol/ap2/mandates/evaluate", headers=KEY, json={
        "mission": m,
        "items": [{"sku": "BAT-001", "qty": 1}],
        "intent_mandate": blob,
    })
    assert r.status_code == 403
    assert "MANDATE_BAD_SIGNATURE" in r.text


def test_ap2_mission_mismatch_403():
    """The mandate must reference the SAME mission it evaluates."""
    m = _signed_mission(f"MSN-AP2-MM-{int(time.time()*1000)}")
    blob = _intent_mandate("MSN-SOME-OTHER-MISSION", ceiling=200000)
    r = _client().post("/protocol/ap2/mandates/evaluate", headers=KEY, json={
        "mission": m,
        "items": [{"sku": "BAT-001", "qty": 1}],
        "intent_mandate": blob,
    })
    assert r.status_code == 403
    assert "MANDATE_MISSION_MISMATCH" in r.text


def test_ap2_requires_api_key():
    r = _client().post("/protocol/ap2/mandates/evaluate", json={})
    assert r.status_code == 401


# ---------------- x402 ----------------

def test_x402_honest_501_stub():
    r = _client().post("/protocol/x402/authorize", headers=KEY)
    assert r.status_code == 501
    body = r.json()
    assert body["implemented"] is False
    assert "Razorpay" in body["reason"]


def test_x402_requires_api_key():
    r = _client().post("/protocol/x402/authorize")
    assert r.status_code == 401
