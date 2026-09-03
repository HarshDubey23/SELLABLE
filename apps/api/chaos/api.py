"""Chaos Control API Endpoints & SSE Live Feed Router."""
from __future__ import annotations

from typing import Any, Dict

from fastapi import APIRouter, HTTPException
from fastapi.responses import StreamingResponse

from .engine import chaos_engine
from .events import event_bus, sse_event_generator
from .scenarios import scenario_runner

router = APIRouter(tags=["chaos"])


@router.post("/api/chaos/faults")
def arm_fault(payload: Dict[str, Any]):
    """Arm a new fault in Chaos Monkey."""
    fault_id = payload.get("fault_id", f"f-{payload.get('type', 'custom')}")
    type_str = payload.get("type", "latency_spike")
    target_route = payload.get("target_route", "*")
    params = payload.get("params", {})
    duration_ms = int(payload.get("duration_ms", 60000))

    ok, msg, cfg = chaos_engine.arm_fault(fault_id, type_str, target_route, params, duration_ms)
    if not ok:
        raise HTTPException(status_code=400, detail={"ok": False, "error": msg})

    return {"ok": True, "message": msg, "fault": cfg.__dict__ if cfg else {}}


@router.delete("/api/chaos/faults/{fault_id}")
def disarm_fault(fault_id: str):
    """Disarm an active fault."""
    ok = chaos_engine.disarm_fault(fault_id)
    if not ok:
        raise HTTPException(status_code=404, detail={"ok": False, "error": f"Fault '{fault_id}' not found or inactive"})
    return {"ok": True, "message": f"Fault '{fault_id}' disarmed."}


@router.post("/api/chaos/reset")
def reset_chaos():
    """Global kill switch: disarm all faults and restore happy-path operation."""
    res = chaos_engine.reset_all()
    return res


@router.post("/api/chaos/scenarios/{scenario_id}/run")
async def run_scenario(scenario_id: str):
    """Run a deterministic chaos drill end-to-end."""
    verdict = await scenario_runner.run_drill(scenario_id.upper())
    return {
        "ok": True,
        "run_id": verdict.run_id,
        "scenario_id": verdict.scenario_id,
        "outcome": verdict.outcome,
        "counts": verdict.counts,
    }


@router.get("/api/chaos/runs/{run_id}")
def get_run_details(run_id: str):
    """Retrieve full run details, invariant checks, and timeline."""
    run = chaos_engine.get_run(run_id)
    if not run:
        raise HTTPException(status_code=404, detail={"ok": False, "error": f"Run '{run_id}' not found"})
    return {
        "ok": True,
        "run_id": run.run_id,
        "scenario_id": run.scenario_id,
        "outcome": run.outcome,
        "invariants": [inv.__dict__ for inv in run.invariants],
        "counts": run.counts,
        "timeline": run.timeline,
    }


@router.get("/api/chaos/status")
def get_chaos_status():
    """Get active faults and system posture."""
    safe, safety_msg = chaos_engine.check_safety()
    return {
        "ok": True,
        "chaos_enabled": chaos_engine.is_enabled,
        "safety_check": {"safe": safe, "message": safety_msg},
        "armed_faults": chaos_engine.active_faults(),
    }


@router.get("/api/events/stream")
async def event_stream():
    """SSE live event feed: broadcasts chaos injections, agent actions, gateway decisions, ledger appends."""
    q = event_bus.subscribe()
    return StreamingResponse(
        sse_event_generator(q),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
        },
    )
