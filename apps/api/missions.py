"""Mission tracking — live progress for the UI.

Stores per-mission structured trace steps in-memory + SQLite (durable).
The UI polls GET /missions/{id}/trace to render the live timeline.

This is OBSERVABILITY: it never gates any money decision. The audit
chain is the security-relevant history.
"""
from __future__ import annotations

import json
import threading
import time
from typing import Any

from .store import db as store

_lock = threading.Lock()
_missions: dict[str, dict[str, Any]] = {}


def _load_persisted() -> None:
    global _missions
    try:
        for row in store.query(
            "SELECT mission_id, status, trace_json, ts_started, ts_ended "
            "FROM missions"
        ):
            mid = row.get("mission_id")
            if not mid:
                continue
            trace = row.get("trace_json") or "[]"
            try:
                trace_list = json.loads(trace) if isinstance(trace, str) else trace
            except Exception:
                trace_list = []
            _missions[mid] = {
                "mission_id": mid,
                "status": row.get("status", "unknown"),
                "ts_started": row.get("ts_started") or 0,
                "ts_ended": row.get("ts_ended") or 0,
                "trace": trace_list if isinstance(trace_list, list) else [],
            }
    except Exception:
        pass


def ensure_schema() -> None:
    """Create the missions table if missing. Idempotent."""
    try:
        store.execute(
            "CREATE TABLE IF NOT EXISTS missions ("
            " mission_id TEXT PRIMARY KEY,"
            " status TEXT,"
            " trace_json TEXT,"
            " ts_started INTEGER,"
            " ts_ended INTEGER"
            ")"
        )
    except Exception:
        pass


ensure_schema()
_load_persisted()


def start(mission_id: str, intent: str = "",
          budget_paise: int = 0) -> dict[str, Any]:
    with _lock:
        rec = _missions.setdefault(mission_id, {
            "mission_id": mission_id,
            "status": "started",
            "ts_started": int(time.time()),
            "ts_ended": 0,
            "trace": [],
            "intent": intent,
            "budget_paise": budget_paise,
        })
        rec["status"] = "started"
        rec["ts_started"] = int(time.time())
        _persist(mission_id, rec)
        return rec


def step(mission_id: str, *, actor: str, action: str,
         detail: str = "", data: dict | None = None,
         duration_ms: int | None = None) -> dict[str, Any]:
    """Append one trace step. Used by the buyer agent and demo routes."""
    with _lock:
        rec = _missions.setdefault(mission_id, {
            "mission_id": mission_id,
            "status": "started",
            "ts_started": int(time.time()),
            "ts_ended": 0,
            "trace": [],
            "intent": "", "budget_paise": 0,
        })
        entry = {
            "ts": int(time.time()),
            "actor": actor,
            "action": action,
            "detail": detail,
            "data": data or {},
        }
        if duration_ms is not None:
            entry["duration_ms"] = duration_ms
        rec["trace"].append(entry)
        _persist(mission_id, rec)
        return entry


def finish(mission_id: str, status: str) -> None:
    with _lock:
        rec = _missions.get(mission_id)
        if not rec:
            return
        rec["status"] = status
        rec["ts_ended"] = int(time.time())
        _persist(mission_id, rec)


def get(mission_id: str) -> dict[str, Any] | None:
    return _missions.get(mission_id)


def list_all(limit: int = 50) -> list[dict[str, Any]]:
    items = sorted(
        _missions.values(),
        key=lambda m: m.get("ts_started", 0),
        reverse=True,
    )
    return items[:limit]


def _persist(mission_id: str, rec: dict) -> None:
    import json as _json
    try:
        store.execute(
            "INSERT OR REPLACE INTO missions "
            "(mission_id, status, trace_json, ts_started, ts_ended) "
            "VALUES (?, ?, ?, ?, ?)",
            (mission_id, rec.get("status", "unknown"),
             _json.dumps(rec.get("trace", [])),
             rec.get("ts_started", 0),
             rec.get("ts_ended", 0))
        )
    except Exception:
        pass
