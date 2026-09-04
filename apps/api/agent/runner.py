"""
HTTP endpoints for running buyer agent missions.
"""
from fastapi import APIRouter, Depends, HTTPException, Request

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

    # The Live Mission UI cannot hold MISSION_HMAC_KEY, so it sends a
    # placeholder and asks the server to issue the mission. That is the
    # in-process issuer path: integrity without custody. It goes through
    # apps/api/issuer.py so there is exactly ONE place in the codebase
    # where the server signs on a user's behalf, and every response it
    # produces is tagged authorization_issued_by.
    sig = mission_data.get("signature", "")
    if sig in ("__server_will_resign__", "__demo__"):
        from ..issuer import ISSUER_LABEL, issue_mission
        issued = issue_mission(
            mission_id=str(mission_data.get("mission_id", "")),
            intent=str(mission_data.get("intent", "")),
            budget_paise=int(mission_data.get("budget_paise", 0)),
            allowed_categories=tuple(mission_data.get("allowed_categories") or ()),
            forbidden_categories=tuple(mission_data.get("forbidden_categories") or ()),
            upsell_cap=float(mission_data.get("upsell_cap", 1.0)),
            ttl_seconds=max(60, int(mission_data.get("expires_at", 0))
                            - int(__import__("time").time())) or 3600,
        )
        mission_data["signature"] = issued["signature"]
        mission_data["expires_at"] = issued["expires_at"]
        mission_data["authorization_issued_by"] = ISSUER_LABEL

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
async def run_full_mission_ui(payload: dict | None = None,
                              request: Request = None):  # noqa: RUF013
    """UI convenience endpoint to run a natural language mission directly from UI.

    Accepts: {
        "intent": "Buy SG cricket bat under Rs 2000",
        "budget_inr": 2000,
        "upsell_cap": 1.2,
        "allowed_categories": ["cricket"]
    }
    """
    import time

    from .. import ratelimit
    from ..issuer import ISSUER_LABEL, issue_mission

    # Unauthenticated on purpose — the cockpit's mission scene calls it, and
    # a reviewer should not need a key to watch the agent shop. It can end
    # in a real Razorpay test order, so it gets a ceiling.
    who = (request.client.host if request is not None and request.client
           else "unknown")
    if not ratelimit.allow(who, bucket="agent_mission", limit=8):
        raise HTTPException(429, detail={
            "ok": False,
            "error": {"error_code": "RATE_LIMITED",
                      "message": "too many agent missions from this client",
                      "retry_after_seconds": ratelimit.retry_after(
                          who, bucket="agent_mission")}})

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
    mission_dict = issue_mission(
        mission_id=mission_id,
        intent=intent,
        budget_paise=budget_paise,
        allowed_categories=tuple(allowed_categories),
        upsell_cap=upsell_cap,
        ttl_seconds=3600,
        now_ts=now_ts,
    )
    mission_dict["authorization_issued_by"] = ISSUER_LABEL

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
        "razorpay_key_id": app_config.get().razorpay_key_id or "",
        "raw_response": res,
    }
