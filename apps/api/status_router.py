"""System status and observability endpoints.

These power the Command Center UI's real-time data:
  - /status            : full state for the top dashboard
  - /invariant/money-calls : proves the rejected => 0 Razorpay calls invariant
  - /metrics/summary   : mission/payment/webhook counters derived from audit

None of these endpoints mutate state.
"""
from __future__ import annotations

from typing import Any

from fastapi import APIRouter

from . import config, money
from .audit import chain as audit_chain
from .gateway.registry import RULE_REGISTRY
from .products import CATALOG
from .tools import orders, quotes
from .webhook.receiver import payment_ledger, processed_event_ids

router = APIRouter()


@router.get("/status")
def system_status() -> dict[str, Any]:
    """Top dashboard snapshot. UI polls this."""
    cfg = config.get()
    entries = audit_chain.entries()
    chain_ok = audit_chain.verify()

    orders_count = len(orders)
    quotes_count = len(quotes)
    ledger_orders = len(payment_ledger)
    events_processed = len(processed_event_ids)

    # Real agent loop indicator: any verdicts?
    approvals = sum(1 for e in entries if e.get("action") == "verdict_emitted"
                    and "APPROVE" in str(_payload(e).get("decision", "")))
    rejections = sum(1 for e in entries if e.get("action") == "verdict_emitted"
                     and "REJECT" in str(_payload(e).get("decision", "")))

    order_created_count = sum(1 for e in entries
                              if e.get("action") == "order_created")
    payment_captured_count = sum(1 for e in entries
                                 if e.get("action") == "payment_captured")

    # LLM fallback rate: any verdicts whose trace mentions llm_fallback?
    llm_calls = 0
    llm_fallbacks = 0
    for e in entries:
        pj = e.get("reasoning_trace") or ""
        if isinstance(pj, str) and "llm" in pj.lower():
            llm_calls += 1
        if e.get("action") == "llm_fallback":
            llm_fallbacks += 1

    razorpay_mode = "test" if cfg.payment_configured else "offline"
    system_risk = "LOW"
    if not chain_ok:
        system_risk = "HIGH"
    elif not cfg.payment_configured:
        system_risk = "MEDIUM"
    elif rejections > approvals:
        system_risk = "MEDIUM"

    return {
        "service": "SELLABLE",
        "service_version": "1.0.0",
        "policy_version": cfg.policy_version,
        "ts_now": _now_ts(),
        "system_risk": system_risk,
        "agents": {
            "online": True,
            "scenarios_available": _scenario_count(),
        },
        "policy_gateway": {
            "enforcing": True,
            "rules_count": len(RULE_REGISTRY),
            "approvals_total": approvals,
            "rejections_total": rejections,
        },
        "razorpay": {
            "mode": razorpay_mode,
            "configured": cfg.payment_configured,
            "missing_required": list(cfg.payment_missing_required),
        },
        "audit_chain": {
            "healthy": chain_ok,
            "entries": len(entries),
            "genesis_present": bool(entries and entries[0]["action"] == "GENESIS"),
            "last_seq": entries[-1]["seq"] if entries else 0,
        },
        "ledger": {
            "orders": orders_count,
            "quotes": quotes_count,
            "payment_ledger_orders": ledger_orders,
            "events_processed": events_processed,
        },
        "metrics": {
            "missions_processed": approvals + rejections,
            "orders_created": order_created_count,
            "payments_captured": payment_captured_count,
        },
        "llm": {
            "configured": cfg.llm_configured,
            "model": cfg.gemini_model if cfg.llm_configured else None,
            "fallbacks": list(cfg.gemini_fallback_models),
            "fallback_count": llm_fallbacks,
        },
        "catalog": {
            "sku_count": len(CATALOG),
            "categories": sorted({p["category"] for p in CATALOG.values()}),
        },
        "money_calls": money.snapshot(),
    }


@router.get("/invariant/money-calls")
def money_calls_invariant() -> dict[str, Any]:
    """Money-call invariant: total Razorpay boundary calls in this process.

    The central security invariant: a REJECT verdict, a failed binding,
    or a rejected mandate MUST result in 0 calls to create_order /
    create_upi_payment / capture_payment.

    Tests reset() the counter before each scenario and assert total == 0.
    The UI reads this to display the live invariant number.
    """
    snap = money.snapshot()
    return {
        "ok": True,
        "invariant": (
            "rejected/binding-invalid/mandate-invalid => 0 money calls"
        ),
        "money_calls": snap,
        "note": (
            "this counter records every call into the Razorpay boundary "
            "module. Tests reset() it before attack scenarios to PROVE the "
            "no-money-without-authorization invariant."
        ),
    }


@router.get("/metrics/summary")
def metrics_summary() -> dict[str, Any]:
    """Aggregate observability metrics derived from the audit chain."""
    entries = audit_chain.entries()
    approvals = sum(1 for e in entries if e.get("action") == "verdict_emitted"
                    and "APPROVE" in str(_payload(e).get("decision", "")))
    rejections = sum(1 for e in entries if e.get("action") == "verdict_emitted"
                     and "REJECT" in str(_payload(e).get("decision", "")))

    # Latency: pull duration_ms from buyer-agent trace payloads.
    latencies: list[int] = []
    for e in entries:
        pj = e.get("reasoning_trace")
        if not pj:
            continue
        try:
            import json as _json
            obj = _json.loads(pj) if isinstance(pj, str) else pj
            ms = obj.get("duration_ms") if isinstance(obj, dict) else None
            if isinstance(ms, (int, float)):
                latencies.append(int(ms))
        except Exception:
            continue
    latencies.sort()
    p50 = latencies[len(latencies) // 2] if latencies else 0
    p95 = latencies[int(len(latencies) * 0.95)] if latencies else 0

    money_calls = money.snapshot()
    return {
        "audit_verified": audit_chain.verify(),
        "audit_entries": len(entries),
        "verdicts": {"approve": approvals, "reject": rejections,
                     "approval_rate": (
                         round(approvals / (approvals + rejections), 3)
                         if (approvals + rejections) else 0
                     )},
        "latency_ms": {
            "samples": len(latencies),
            "p50": p50, "p95": p95,
        },
        "money_calls": money_calls,
        "webhook_events": len(processed_event_ids),
        "payment_ledger_orders": len(payment_ledger),
    }


@router.get("/catalog")
def catalog_list() -> dict[str, Any]:
    """Full catalog with prices. Source of truth for the Search UI."""
    items = []
    for sku, p in CATALOG.items():
        items.append({
            "sku": sku,
            "name": p["name"],
            "category": p["category"],
            "price_paise": p["price_paise"],
            "price_display": f"Rs {p['price_paise']/100:,.0f}",
            "rating": p.get("rating"),
            "stock": p.get("stock", 0),
            "attributes": p.get("attributes", {}),
        })
    items.sort(key=lambda x: x["sku"])
    return {"count": len(items), "items": items}


@router.get("/rules")
def rules_list() -> dict[str, Any]:
    """R1-R12 rule catalog for the Gateway UI."""
    return {"count": len(RULE_REGISTRY), "rules": RULE_REGISTRY}


def _payload(e: dict) -> dict:
    """Parse payload_json if present, else fall back to a stub."""
    pj = e.get("payload_json")
    if isinstance(pj, dict):
        return pj
    if isinstance(pj, str) and pj.strip():
        import json as _json
        try:
            return _json.loads(pj)
        except Exception:
            return {}
    return {}


def _now_ts() -> int:
    import time as _t
    return int(_t.time())


def _scenario_count() -> int:
    """Best-effort count of available scenarios. Used by the dashboard."""
    try:
        from .agent.scenarios import list_scenarios
        return len(list_scenarios())
    except Exception:
        return 0
