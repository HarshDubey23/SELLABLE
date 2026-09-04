"""
tests/gateway/test_attack_lab.py

Proves all 8 adversarial scenarios are blocked with 0 Razorpay calls.
This is the central security invariant test for SELLABLE.
"""
import pytest

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


def test_each_scenario_is_blocked_by_the_layer_it_claims_to_test():
    """A scenario that is refused for the wrong reason proves the wrong thing.

    A8 used to trip R1_BUDGET while advertising itself as a demonstration of
    the approval binding's SKU-set check — the attack was blocked, but not by
    the mechanism on the label. The mutated cart is now identically priced
    and equally in scope, so R1-R12 approve it and the binding is provably
    the layer that refuses.
    """
    from apps.api.attack import attack_run_all

    expected = {
        "A1_PROMPT_INJECTION": "gateway/R1_BUDGET",
        "A2_OVERSPENDING": "gateway/R1_BUDGET",
        "A3_PRICE_MANIPULATION": "gateway/R3_PRICE_DRIFT",
        "A4_FORBIDDEN_PRODUCT": "gateway/R2_FORBIDDEN",
        "A5_SCOPE_VIOLATION": "gateway/R5_SCOPE",
        "A6_INVALID_SIGNATURE": "gateway/R9_SIGNATURE",
        "A7_STALE_MANDATE": "approval_binding/BINDING_EXPIRED",
        "A8_CART_MUTATION": "approval_binding/SKU_SET_MISMATCH",
    }
    actual = {r["id"]: r["blocked_by"] for r in attack_run_all()["results"]}
    assert actual == expected


def test_cart_mutation_passes_the_gateway_before_the_binding_refuses_it():
    """Defence in depth is only demonstrated when the first layer lets it by."""
    from apps.api.attack import attack_run

    result = attack_run("A8_CART_MUTATION")
    assert result["gateway"]["decision"] == "APPROVE", (
        "A8 must reach the money boundary; if the gateway rejects it, the "
        "scenario is testing a policy rule rather than the approval binding")
    assert result["binding_check"]["blocked"] is True
    assert result["binding_check"]["reason"] == "SKU_SET_MISMATCH"
    assert result["money_calls"]["boundary_calls"] == 0
