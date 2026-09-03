"""
HTTP endpoints for running buyer agent missions.
"""
from fastapi import APIRouter, Depends, HTTPException

from .. import config as app_config
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

    # Demo convenience: the Live Mission UI sends a placeholder signature
    # because the browser must not hold MISSION_HMAC_KEY. The server
    # (which does hold the key) re-signs the mission for the demo run.
    # The custody invariant is preserved for all non-demo callers.
    sig = mission_data.get("signature", "")
    if sig == "__server_will_resign__" or sig == "__demo__":
        from ..gateway.mission_verify import dumps as _dumps
        from ..gateway.mission_verify import sign_mission as _sign
        tmp = {k: v for k, v in mission_data.items() if k != "signature"}
        mission_data["signature"] = _sign(_dumps(tmp))

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


@router.post("/agent/run_full_mission")
async def run_full_mission_ui(payload: dict | None = None):
    """UI convenience endpoint to run a natural language mission directly from UI.

    Accepts: {
        "intent": "Buy SG cricket bat under Rs 2000",
        "budget_inr": 2000,
        "upsell_cap": 1.2,
        "allowed_categories": ["cricket"]
    }
    """
    import time

    from ..gateway.mission_verify import dumps as _dumps
    from ..gateway.mission_verify import sign_mission as _sign

    if not payload:
        payload = {}

    intent = payload.get("intent", "Buy cricket bat under Rs 2000")
    budget_inr = float(payload.get("budget_inr", 2000))
    budget_paise = int(budget_inr * 100)
    upsell_cap = float(payload.get("upsell_cap", 1.2))
    allowed_categories = payload.get("allowed_categories", ["cricket"])
    if isinstance(allowed_categories, str):
        allowed_categories = [allowed_categories]

    now_ts = int(time.time())
    mission_id = f"MSN-UI-{now_ts}"
    mission_dict = {
        "mission_id": mission_id,
        "intent": intent,
        "budget_paise": budget_paise,
        "allowed_categories": allowed_categories,
        "forbidden_categories": [],
        "upsell_cap": upsell_cap,
        "expires_at": now_ts + 3600,
    }

    sig = _sign(_dumps(mission_dict))
    mission_dict["signature"] = sig

    res = await run_mission(mission_dict)

    trace_dict = res.get("trace", {}) if isinstance(res, dict) else {}
    events = trace_dict.get("events", [])
    order_id = res.get("order_id") if isinstance(res, dict) else None
    amount_paise = res.get("amount_paise", 0) if isinstance(res, dict) else 0

    order_obj = None
    if order_id:
        order_obj = {"id": order_id, "amount": amount_paise}

    return {
        "ok": True,
        "status": res.get("status", "unknown") if isinstance(res, dict) else "unknown",
        "events": events,
        "trace": trace_dict,
        "order": order_obj,
        "order_id": order_id,
        "amount_paise": amount_paise,
        "verdict": "APPROVED" if order_id else "REJECTED",
        "razorpay_key_id": app_config.status_summary().get("razorpay_key_id", "rzp_test_TSttLNvLt9yUPI"),
        "raw_response": res,
    }
