"""
tests/gateway/test_r9_signature.py - R9 mission signature tests
"""
import hashlib
import hmac
import json
import time

from apps.api.gateway.rules import rule_r9_signature
from apps.api.gateway.types import Mission, Violation


def _make_mission(**overrides):
    data = dict(
        mission_id="m1", intent="buy stuff",
        budget_paise=50000, upsell_cap=1.3,
        allowed_categories=("electronics",), forbidden_categories=(),
        expires_at=int(time.time()) + 3600,
        signature="",
    )
    data.update(overrides)
    return Mission(**data)


def _sign(mission: Mission, key: str) -> str:
    blob = {k: v for k, v in vars(mission).items() if k != "signature"}
    canon = json.dumps(_plain(blob), sort_keys=True, separators=(",", ":"))
    return hmac.new(key.encode(), canon.encode(), hashlib.sha256).hexdigest()


def _plain(obj):
    if isinstance(obj, (list, tuple)):
        return [_plain(i) for i in obj]
    if isinstance(obj, dict):
        return {k: _plain(v) for k, v in obj.items()}
    return obj


def _verify_fn(key: str):
    def _verify(canon: str, sig: str) -> bool:
        expected = hmac.new(key.encode(), canon.encode(), hashlib.sha256).hexdigest()
        return hmac.compare_digest(expected, sig)
    return _verify


def test_r9_valid_signature():
    key = "test_mission_hmac_key"
    m = _make_mission()
    sig = _sign(m, key)
    signed = Mission(
        mission_id=m.mission_id, intent=m.intent,
        budget_paise=m.budget_paise, upsell_cap=m.upsell_cap,
        allowed_categories=m.allowed_categories,
        forbidden_categories=m.forbidden_categories,
        expires_at=m.expires_at, signature=sig,
    )
    result = rule_r9_signature(signed, _verify_fn(key))
    assert result is None


def test_r9_missing_signature():
    key = "test_mission_hmac_key"
    m = _make_mission(signature="")
    result = rule_r9_signature(m, _verify_fn(key))
    assert isinstance(result, Violation)
    assert result.rule_id == "R9_SIGNATURE"


def test_r9_bad_signature():
    key = "test_mission_hmac_key"
    m = _make_mission(signature="bad" * 20)
    result = rule_r9_signature(m, _verify_fn(key))
    assert isinstance(result, Violation)


def test_r9_none_mission():
    result = rule_r9_signature(None, lambda c, s: True)
    assert isinstance(result, Violation)
