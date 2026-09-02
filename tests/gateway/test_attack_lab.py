"""
tests/gateway/test_attack_lab.py

Proves all 8 adversarial scenarios are blocked with 0 Razorpay calls.
This is the central security invariant test for SELLABLE.
"""
import os, time, pytest
from apps.api import money


def _setup_env(monkeypatch):
    monkeypatch.setenv("MISSION_HMAC_KEY", "testmissionhmackey1234567890abc1")
    monkeypatch.setenv("USER_MANDATE_KEY", "testmandatekey1234567890abcdef12")


SCENARIO_IDS = [
    "A1_PROMPT_INJECTION",
    "A2_OVERSPENDING",
    "A3_PRICE_MANIPULATION",
    "A4_FORBIDDEN_PRODUCT",
    "A5_SCOPE_VIOLATION",
    "A6_INVALID_SIGNATURE",
    "A7_STALE_MANDATE",
    "A8_CART_MUTATION",
]


@pytest.mark.parametrize("scenario_id", SCENARIO_IDS)
def test_attack_is_blocked(scenario_id):
    """Each attack must be blocked and must produce 0 Razorpay boundary calls."""
    from apps.api.attack import attack_run
    money.reset()
    result = attack_run(scenario_id)
    assert result.get("ok"), f"Scenario {scenario_id} errored: {result}"
    verdict = result.get("verdict", {})
    money_calls = result.get("money_calls", {})
    assert verdict.get("safe"), (
        f"Scenario {scenario_id} NOT blocked!\n"
        f"  gateway_decision={result.get('gateway', {}).get('decision')}\n"
        f"  rule_id={result.get('gateway', {}).get('rule_id')}\n"
        f"  boundary_calls={money_calls.get('boundary_calls')}"
    )
    assert money_calls.get("boundary_calls") == 0, (
        f"Scenario {scenario_id}: expected 0 Razorpay calls, "
        f"got {money_calls.get('boundary_calls')}"
    )


def test_all_8_attacks_blocked():
    """run_all must show 8/8 scenarios blocked."""
    from apps.api.attack import attack_run_all
    result = attack_run_all()
    assert result["scenarios_blocked"] == result["scenarios_total"], (
        f"Only {result['scenarios_blocked']}/{result['scenarios_total']} attacks blocked!\n"
        + "\n".join(
            f"  {r['id']}: safe={r['safe']}, rule={r.get('rule_id')}"
            for r in result["results"] if not r.get("safe")
        )
    )
    assert result["block_rate"] == 1.0
