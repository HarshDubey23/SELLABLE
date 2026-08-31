"""
HTTP endpoints for running buyer agent missions.
"""
from fastapi import APIRouter, Depends, HTTPException

from ..deps import require_api_key
from .buyer import run_mission
from .scenarios import get_scenario, list_scenarios

router = APIRouter()

REQUIRED_MISSION_FIELDS = ["mission_id", "intent", "budget_paise",
                           "allowed_categories", "expires_at", "signature"]


@router.post("/agent/run-mission", dependencies=[Depends(require_api_key)])
async def run_mission_endpoint(mission_data: dict | None = None):
    """Run a buyer agent mission with a full protocol trace.

    Body (optional): a signed mission dict. If absent, the happy_path
    scenario mission is used.
    """
    if not mission_data:
        scenario = get_scenario("happy_path")
        if not scenario:
            raise HTTPException(500, detail="default scenario not found")
        mission_data = scenario["mission"]

    for field in REQUIRED_MISSION_FIELDS:
        if field not in mission_data:
            raise HTTPException(400, detail={
                "ok": False,
                "error": {"error_code": "MISSING_FIELD",
                          "message": f"mission missing required field: {field}"}
            })

    return await run_mission(mission_data)


@router.get("/agent/scenarios")
async def list_scenarios_endpoint():
    """List all available demo scenarios."""
    return {"scenarios": list_scenarios()}


@router.post("/agent/run-scenario/{scenario_id}", dependencies=[Depends(require_api_key)])
async def run_scenario_endpoint(scenario_id: str):
    """Run a specific demo scenario. Returns the full protocol trace."""
    scenario = get_scenario(scenario_id)
    if not scenario:
        raise HTTPException(404, detail={
            "ok": False,
            "error": {"error_code": "SCENARIO_NOT_FOUND",
                      "message": f"unknown scenario: {scenario_id}"}
        })

    result = await run_mission(
        scenario["mission"],
        payment_mode=scenario.get("payment_mode", "success"),
    )

    result["scenario"] = {
        "id": scenario_id,
        "title": scenario["title"],
        "description": scenario["description"],
        "expected": scenario["expected"],
    }
    return result
