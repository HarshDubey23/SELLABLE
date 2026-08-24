"""T23, T25: R9 signature — valid passes, missing/invalid fails closed."""
import os, sys
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

os.environ.setdefault("MISSION_HMAC_KEY", "test-key-not-a-real-secret")

from apps.api.gateway import mission_verify as mv
from apps.api.gateway.rules import rule_r9_signature
from apps.api.gateway.types import Mission

MISSION = Mission(mission_id="m2", intent="test", budget_paise=100000,
                  allowed_categories=(), forbidden_categories=(),
                  upsell_cap=1.3, expires_at=9_999_999_999)


def test_T23_r9_valid_signature():
    blob = {k: v for k, v in vars(MISSION).items() if k != "signature"}
    sig = mv.sign_mission(mv.dumps(blob))
    assert rule_r9_signature(
        Mission(**{**vars(MISSION), "signature": sig}),
        mv.verify_mission) is None


def test_T25_r9_missing_signature_rejects_fail_closed():
    v = rule_r9_signature(MISSION, mv.verify_mission)   # signature = ""
    assert v is not None and v.rule_id == "R9_SIGNATURE"
