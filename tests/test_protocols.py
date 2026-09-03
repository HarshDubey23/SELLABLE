"""Tests for protocol adapters: NPCI UAP, Google AP2, OpenAI ACP."""
import os
import time
from fastapi.testclient import TestClient
from apps.api.main import app
from apps.api.gateway.mission_verify import sign_mission, dumps as _dumps

client = TestClient(app)


def get_headers():
    return {"X-API-Key": os.environ.get("APP_API_KEY", "test_app_api_key")}


def test_uap_happy_path():
    """NPCI UAP compliant order executes through deterministic gateway."""
    now_ts = int(time.time())
    mission = {
        "mission_id": f"UAP-{now_ts}",
        "intent": "Buy cricket bat under Rs 2,500 via NPCI UAP",
        "budget_paise": 250000,
        "allowed_categories": ["cricket"],
        "forbidden_categories": [],
        "upsell_cap": 1.0,
        "expires_at": now_ts + 3600,
    }
    mission["signature"] = sign_mission(_dumps(mission))

    payload = {
        "uap_agent_id": "npci:agent:buyer-delhivery-v1",
        "consent_handle": "upi:delegated:handle_9921",
        "mission": mission,
        "mandate": {
            "mandate_id": f"MND-{now_ts}",
            "max_amount_paise": 250000,
            "purpose_code": "COMMERCE_PURCHASE",
            "valid_until": now_ts + 3600,
            "signature": "simulated_npci_signature",
        },
        "items": [{"sku": "BAT-001", "qty": 1}],
    }
    resp = client.post("/protocol/uap/transact", json=payload, headers=get_headers())
    assert resp.status_code == 200, resp.text
    data = resp.json()
    assert data["protocol"] == "NPCI_UAP_v1.0"
    assert data["settlement_rail"] == "UPI_DELEGATED_MANDATE"
    assert data["uap_receipt"]["status"] == "AUTHORIZED"
    assert data["total_paise"] == 149900


def test_uap_expired_mandate_fails_closed():
    """Expired NPCI UAP mandate is rejected at adapter boundary."""
    now_ts = int(time.time())
    mission = {
        "mission_id": "UAP-EXP",
        "intent": "Expired",
        "budget_paise": 200000,
        "allowed_categories": ["cricket"],
        "forbidden_categories": [],
        "upsell_cap": 1.0,
        "expires_at": now_ts + 3600,
    }
    mission["signature"] = sign_mission(_dumps(mission))
    payload = {
        "uap_agent_id": "npci:agent:buyer-v1",
        "consent_handle": "upi:delegated:handle_exp",
        "mission": mission,
        "mandate": {
            "mandate_id": "MND-EXPIRED",
            "max_amount_paise": 200000,
            "purpose_code": "COMMERCE_PURCHASE",
            "valid_until": now_ts - 60,
            "signature": "sig",
        },
        "items": [{"sku": "BAT-001", "qty": 1}],
    }
    resp = client.post("/protocol/uap/transact", json=payload, headers=get_headers())
    assert resp.status_code == 400
    assert resp.json()["detail"]["error"] == "MANDATE_EXPIRED"


def test_uap_ceiling_exceeded_fails_closed():
    """Order exceeding UAP mandate ceiling is blocked."""
    now_ts = int(time.time())
    mission = {
        "mission_id": "UAP-LOW",
        "intent": "Low Ceiling",
        "budget_paise": 200000,
        "allowed_categories": ["cricket"],
        "forbidden_categories": [],
        "upsell_cap": 1.0,
        "expires_at": now_ts + 3600,
    }
    mission["signature"] = sign_mission(_dumps(mission))
    payload = {
        "uap_agent_id": "npci:agent:buyer-v1",
        "consent_handle": "upi:delegated:handle_low",
        "mission": mission,
        "mandate": {
            "mandate_id": "MND-LOW-CEILING",
            "max_amount_paise": 100000,  # 1,000 INR
            "purpose_code": "COMMERCE_PURCHASE",
            "valid_until": now_ts + 3600,
            "signature": "sig",
        },
        "items": [{"sku": "BAT-001", "qty": 1}],  # 1,499 INR
    }
    resp = client.post("/protocol/uap/transact", json=payload, headers=get_headers())
    assert resp.status_code == 400
    assert resp.json()["detail"]["error"] == "MANDATE_CEILING_EXCEEDED"


def test_uap_unknown_sku_fails_closed():
    """Unknown product SKU is rejected."""
    now_ts = int(time.time())
    mission = {
        "mission_id": "UAP-BAD-SKU",
        "intent": "Bad SKU",
        "budget_paise": 500000,
        "allowed_categories": ["cricket"],
        "forbidden_categories": [],
        "upsell_cap": 1.0,
        "expires_at": now_ts + 3600,
    }
    mission["signature"] = sign_mission(_dumps(mission))
    payload = {
        "uap_agent_id": "npci:agent:buyer-v1",
        "consent_handle": "upi:delegated:handle_sku",
        "mission": mission,
        "mandate": {
            "mandate_id": "MND-BAD-SKU",
            "max_amount_paise": 500000,
            "purpose_code": "COMMERCE_PURCHASE",
            "valid_until": now_ts + 3600,
            "signature": "sig",
        },
        "items": [{"sku": "NON_EXISTENT_SKU_999", "qty": 1}],
    }
    resp = client.post("/protocol/uap/transact", json=payload, headers=get_headers())
    assert resp.status_code == 400
    assert resp.json()["detail"]["error"] == "UNKNOWN_SKU"


def test_protocol_adapter_invariants():
    """Verify that protocol adapters never import gateway and never decide directly."""
    from pathlib import Path
    proto_dir = Path(__file__).resolve().parents[1] / "apps" / "api" / "protocols"
    for py_file in proto_dir.glob("*.py"):
        if py_file.name == "__init__.py":
            continue
        lines = py_file.read_text(encoding="utf-8").splitlines()
        for line in lines:
            s = line.strip()
            if s.startswith("#") or s.startswith('"""') or s.startswith("'''") or s.startswith("-"):
                continue
            assert "import apps.api.gateway" not in line, f"Illegal gateway import in {py_file}"
            assert "from ..gateway" not in line, f"Illegal gateway import in {py_file}"
            assert "from .gateway" not in line, f"Illegal gateway import in {py_file}"
