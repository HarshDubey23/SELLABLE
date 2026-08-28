"""Deterministic revenue-impact metrics, computed from the audit chain.

Track 01's goal is to GROW merchant revenue. This module measures it from
the tamper-evident audit chain — baseline revenue, upsell lift, recovered
revenue, revenue lost — so every number is backed by an audit entry.

Pure computation: no LLM, no network, no I/O. Read-only. Test money — the
measurement methodology is the deliverable, not the rupees.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


@dataclass(frozen=True)
class MoneyEvent:
    kind: str            # order_created | payment_captured | payment_failed | upsell_accepted
    amount_paise: int = 0
    mission_id: str = ""
    seq: int = 0         # ordering within the mission (audit seq)
    meta: dict[str, Any] = field(default_factory=dict)


def compute_revenue_metrics(events: list[MoneyEvent]) -> dict[str, Any]:
    missions: dict[str, list[MoneyEvent]] = {}
    for ev in events:
        if ev.mission_id:
            missions.setdefault(ev.mission_id, []).append(ev)
    for evs in missions.values():
        evs.sort(key=lambda e: e.seq)

    total = lift = recovered = lost = 0
    upsells_accepted = upsells_captured = recoveries = 0
    for evs in missions.values():
        captured = next((e for e in evs if e.kind == "payment_captured"), None)
        failed = any(e.kind == "payment_failed" for e in evs)
        upsell = next((e for e in evs if e.kind == "upsell_accepted"), None)
        if upsell is not None:
            upsells_accepted += 1
        if captured is None:
            if failed:
                lost += next((e.amount_paise for e in evs if e.kind == "order_created"), 0)
            continue
        total += captured.amount_paise
        if upsell is not None:
            upsells_captured += 1
            before = int(upsell.meta.get("before_paise", captured.amount_paise))
            lift += max(0, captured.amount_paise - before)
        if failed:
            recoveries += 1
            recovered += captured.amount_paise
    baseline = total - lift
    growth_pct = round(100.0 * lift / baseline, 2) if baseline > 0 else None
    at_risk = recovered + lost
    recovery_pct = round(100.0 * recovered / at_risk, 2) if at_risk > 0 else None
    return {
        "currency": "INR (Razorpay test mode)",
        "missions": len(missions),
        "missions_captured": sum(1 for evs in missions.values()
                                 if any(e.kind == "payment_captured" for e in evs)),
        "total_captured_paise": total,
        "baseline_paise": baseline,
        "upsell": {"accepted": upsells_accepted, "captured": upsells_captured,
                   "lift_paise": lift, "growth_pct": growth_pct},
        "recovery": {"missions_recovered": recoveries,
                     "recovered_revenue_paise": recovered,
                     "revenue_lost_paise": lost,
                     "recovery_pct": recovery_pct},
        "methodology": "computed from the SHA-256 audit chain; recovered revenue is "
                       "a subset of total (protected, not additive); upsell lift "
                       "counts only when the upsold cart actually captured",
    }
