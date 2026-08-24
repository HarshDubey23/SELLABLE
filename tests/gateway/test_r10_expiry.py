"""T26-T28: R10 expiry — valid / expired / exact-boundary fails closed."""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from apps.api.gateway.rules import rule_r10_expiry
from apps.api.gateway.types import Mission

MISSION = Mission(mission_id="m3", intent="test", budget_paise=100000,
                  allowed_categories=(), forbidden_categories=(),
                  upsell_cap=1.3, expires_at=1_000)


def test_T26_r10_valid():
    assert rule_r10_expiry(MISSION, now_ts=999) is None


def test_T27_r10_expired():
    v = rule_r10_expiry(MISSION, now_ts=1_500)
    assert v is not None and v.rule_id == "R10_EXPIRY"


def test_T28_r10_exact_expiry_rejects():
    # == expiry also REJECTS — fail-closed at the boundary
    v = rule_r10_expiry(MISSION, now_ts=1_000)
    assert v is not None and v.rule_id == "R10_EXPIRY"
