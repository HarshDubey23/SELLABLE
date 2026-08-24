"""T01-T03: R1 budget — under / over / exact boundary."""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from apps.api.gateway.rules import rule_r1_budget
from apps.api.gateway.types import Mission, Proposal, ProposalItem

CATALOG = {"BAT-001": {"price_paise": 149900, "category": "cricket"}}
MISSION = Mission(mission_id="m1", intent="gift", budget_paise=200000,
                  allowed_categories=("cricket",), forbidden_categories=(),
                  upsell_cap=1.3, expires_at=9_999_999_999)
PROP = Proposal(mission_id="m1",
                items=(ProposalItem("BAT-001", 1, 149900),))


def test_T01_r1_under_budget():
    assert rule_r1_budget(PROP, CATALOG, MISSION) is None


def test_T02_r1_over_budget():
    prop = Proposal("m1", (ProposalItem("BAT-001", 2, 149900),))
    v = rule_r1_budget(prop, CATALOG, MISSION)
    assert v is not None and v.rule_id == "R1_BUDGET"
    assert v.attempted_value == 299800 and v.limit_value == 200000


def test_T03_r1_exact_boundary():
    # exactly at budget -> allowed (only strictly-greater rejects)
    m = Mission(**{**vars(MISSION), "budget_paise": 149900})
    assert rule_r1_budget(PROP, CATALOG, m) is None
