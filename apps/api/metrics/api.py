"""HTTP adapter for GET /metrics/revenue."""
from __future__ import annotations

import json
from typing import Any

from fastapi import APIRouter

from ..audit import chain as audit_chain
from .revenue import MoneyEvent, compute_revenue_metrics

router = APIRouter()

KIND_MAP = {
    "order_created": "order_created",
    "payment_captured": "payment_captured",
    "payment_failed": "payment_failed",
    "payment_attempt_failed": "payment_failed",
    "upsell_accepted": "upsell_accepted",
}


def _payload(e: dict[str, Any]) -> dict[str, Any]:
    raw = e.get("payload_json")
    if isinstance(raw, dict):
        return raw
    if isinstance(raw, str) and raw.strip():
        try:
            parsed = json.loads(raw)
            return parsed if isinstance(parsed, dict) else {}
        except json.JSONDecodeError:
            return {}
    return {}


def events_from_audit(entries: list[dict[str, Any]]) -> list[MoneyEvent]:
    out: list[MoneyEvent] = []
    for e in entries:
        kind = KIND_MAP.get(str(e.get("action", "")))
        if not kind:
            continue
        meta = _payload(e)
        amount = int(meta.get("amount_paise") or meta.get("after_paise") or 0)
        out.append(MoneyEvent(
            kind=kind,
            amount_paise=amount,
            mission_id=str(meta.get("mission_id") or ""),
            seq=int(e.get("seq", 0)),
            meta=dict(meta),
        ))
    return out


@router.get("/metrics/revenue")
async def revenue_metrics() -> dict[str, Any]:
    """Measured revenue impact, computed from the tamper-evident audit chain."""
    entries = audit_chain.entries()
    report = compute_revenue_metrics(events_from_audit(entries))
    report["guardrails"] = {
        "dark_patterns_blocked": sum(1 for e in entries if e.get("action") == "copy_blocked"),
        "mandates_verified": sum(1 for e in entries if e.get("action") == "mandate_verified"),
        "mandates_rejected": sum(1 for e in entries if e.get("action") == "mandate_rejected"),
    }
    report["audit_chain_verified"] = audit_chain.verify()
    return report
