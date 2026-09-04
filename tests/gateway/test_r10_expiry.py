"""
tests/gateway/test_r10_expiry.py - R10 mission expiry tests
"""
import time

from apps.api.gateway.rules import rule_r10_expiry
from apps.api.gateway.types import Mission, Violation


def _make_mission(expires_at):
    return Mission(
        mission_id="m1", intent="buy stuff",
        budget_paise=50000, upsell_cap=1.3,
        allowed_categories=("electronics",), forbidden_categories=(),
        expires_at=expires_at, signature="sig",
    )


def test_r10_not_expired():
    now = int(time.time())
    m = _make_mission(expires_at=now + 3600)
    result = rule_r10_expiry(m, now)
    assert result is None


def test_r10_expired():
    now = int(time.time())
    m = _make_mission(expires_at=now - 1)
    result = rule_r10_expiry(m, now)
    assert isinstance(result, Violation)
    assert result.rule_id == "R10_EXPIRY"


def test_r10_expired_at_exact_boundary():
    now = int(time.time())
    m = _make_mission(expires_at=now)
    # == also rejects: fail-closed at the boundary
    result = rule_r10_expiry(m, now)
    assert isinstance(result, Violation)
