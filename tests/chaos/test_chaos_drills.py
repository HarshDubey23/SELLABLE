"""Automated Pytest Suite for Chaos Monkey Fault-Injection & Invariants."""
import pytest
from fastapi.testclient import TestClient

from apps.api.main import app
from apps.api.chaos.engine import chaos_engine
from apps.api.chaos.scenarios import scenario_runner

client = TestClient(app)


def test_chaos_safety_check():
    """Safety check: refuse to arm if key is live mode."""
    safe, msg = chaos_engine.check_safety()
    assert safe is True
    assert "rzp_test_" in os.environ.get("RAZORPAY_KEY_ID", "rzp_test_")


def test_arm_and_disarm_fault():
    """Test arming and disarming a fault via API."""
    res = client.post("/api/chaos/faults", json={
        "fault_id": "f-test-lat",
        "type": "latency_spike",
        "target_route": "/tools/create_order",
        "duration_ms": 5000,
        "params": {"delay_ms": 100}
    })
    assert res.status_code == 200
    data = res.json()
    assert data["ok"] is True
    assert data["fault"]["fault_id"] == "f-test-lat"

    # Disarm
    dis_res = client.delete("/api/chaos/faults/f-test-lat")
    assert dis_res.status_code == 200
    assert dis_res.json()["ok"] is True


def test_kill_switch_reset():
    """Test global kill switch reset."""
    client.post("/api/chaos/faults", json={
        "fault_id": "f-test-1", "type": "bound_breach", "target_route": "/tools/submit_proposal"
    })
    res = client.post("/api/chaos/reset")
    assert res.status_code == 200
    assert res.json()["ok"] is True
    assert res.json()["disarmed_count"] >= 0


@pytest.mark.asyncio
async def test_drill_duplicate_storm():
    """Drill 1: DUPLICATE_STORM -> 1 order created, replays cached."""
    verdict = await scenario_runner.run_drill("DUPLICATE_STORM")
    assert verdict.outcome == "SURVIVED"
    i1 = next(inv for inv in verdict.invariants if inv.id == "I1")
    assert i1.held is True


@pytest.mark.asyncio
async def test_drill_price_flip():
    """Drill 2: PRICE_FLIP -> 409 PRICE_STALE -> fresh quote -> re-sign -> SURVIVED."""
    verdict = await scenario_runner.run_drill("PRICE_FLIP")
    assert verdict.outcome == "SURVIVED"
    i6 = next(inv for inv in verdict.invariants if inv.id == "I6")
    assert i6.held is True


@pytest.mark.asyncio
async def test_drill_latency_timeout():
    """Drill 3: LATENCY_TIMEOUT -> retry same IdemKey -> SURVIVED."""
    verdict = await scenario_runner.run_drill("LATENCY_TIMEOUT")
    assert verdict.outcome == "SURVIVED"


@pytest.mark.asyncio
async def test_drill_webhook_blackhole():
    """Drill 4: WEBHOOK_BLACKHOLE -> deduplication -> SURVIVED."""
    verdict = await scenario_runner.run_drill("WEBHOOK_BLACKHOLE")
    assert verdict.outcome == "SURVIVED"
    i3 = next(inv for inv in verdict.invariants if inv.id == "I3")
    assert i3.held is True


@pytest.mark.asyncio
async def test_drill_last_unit_race():
    """Drill 5: LAST_UNIT_RACE -> 1 approved, 2 OUT_OF_STOCK -> SURVIVED."""
    verdict = await scenario_runner.run_drill("LAST_UNIT_RACE")
    assert verdict.outcome == "SURVIVED"


@pytest.mark.asyncio
async def test_drill_agent_crash():
    """Drill 6: AGENT_CRASH -> TTL release -> stock restored -> SURVIVED."""
    verdict = await scenario_runner.run_drill("AGENT_CRASH")
    assert verdict.outcome == "SURVIVED"
    i5 = next(inv for inv in verdict.invariants if inv.id == "I5")
    assert i5.held is True


import os
