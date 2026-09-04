"""Mission tracking HTTP endpoints (read + tracked live write)."""
from __future__ import annotations

from fastapi import APIRouter, HTTPException

from . import missions

router = APIRouter()

# A mission is finished when missions.finish() recorded one of these. Any
# other status means work may still be in flight.
_TERMINAL_STATUSES = frozenset({
    "completed", "executed", "rejected", "failed", "error",
    "no_products", "no_proposal", "mandate_error", "blocked",
})


@router.post("/missions/{mission_id}/start")
def mission_start(mission_id: str, body: dict | None = None) -> dict:
    body = body or {}
    rec = missions.start(
        mission_id,
        intent=body.get("intent", ""),
        budget_paise=int(body.get("budget_paise", 0) or 0),
    )
    return {"ok": True, "mission": {"mission_id": mission_id,
                                    "status": rec["status"]}}


@router.post("/missions/{mission_id}/step")
def mission_step(mission_id: str, body: dict) -> dict:
    if not isinstance(body, dict):
        raise HTTPException(400, detail="body must be object")
    entry = missions.step(
        mission_id,
        actor=str(body.get("actor", "system")),
        action=str(body.get("action", "event")),
        detail=str(body.get("detail", "")),
        data=body.get("data") if isinstance(body.get("data"), dict) else {},
        duration_ms=body.get("duration_ms"),
    )
    return {"ok": True, "entry": entry}


@router.post("/missions/{mission_id}/finish")
def mission_finish(mission_id: str, body: dict | None = None) -> dict:
    body = body or {}
    status = str(body.get("status", "completed"))
    missions.finish(mission_id, status)
    return {"ok": True, "mission_id": mission_id, "status": status}


@router.get("/missions/{mission_id}/trace")
def mission_trace(mission_id: str) -> dict:
    rec = missions.get(mission_id)
    if not rec:
        return {"mission_id": mission_id, "status": "unknown",
                "trace": [], "count": 0}
    status = rec.get("status", "unknown")
    return {
        "mission_id": mission_id,
        "status": status,
        # So a poller knows when to stop asking rather than guessing from
        # the event list, which can pause mid-mission on a slow tool call.
        "terminal": status in _TERMINAL_STATUSES,
        "ts_started": rec.get("ts_started", 0),
        "ts_ended": rec.get("ts_ended", 0),
        "trace": rec.get("trace", []),
        "count": len(rec.get("trace", [])),
    }


@router.get("/missions")
def mission_list() -> dict:
    return {"count": len(missions.list_all(1000)),
            "missions": [
                {"mission_id": m["mission_id"],
                 "status": m["status"],
                 "ts_started": m.get("ts_started", 0),
                 "ts_ended": m.get("ts_ended", 0),
                 "step_count": len(m.get("trace", []))}
                for m in missions.list_all(50)
            ]}
