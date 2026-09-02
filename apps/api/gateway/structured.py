"""Structured gateway evaluation: returns the FULL R1-R12 rule matrix.

The original `evaluate()` in engine.py returns the first Violation only
(first-violation-wins for fail-fast semantics). That's correct for the
money-path gate, but the UI needs the FULL rule matrix so judges can
see every rule's pass/fail state, not just the one that stopped the
flow.

`evaluate_full()` runs every rule deterministically, collects ALL
violations, and returns a UI-friendly structured report.

INVARIANTS:
  - Pure stdlib (no FastAPI, no I/O).
  - Fail-closed: malformed inputs become REJECTs, never crash.
  - Same rule order as RULE_REGISTRY (canonical 12 rules).
  - Same verdict hash as engine.evaluate() on APPROVE.
"""
from __future__ import annotations

import time as _time
from collections.abc import Callable
from typing import Any

from . import rules as R
from .rules import VerifyFn
from .rules_r11 import rule_r11_negotiation_bound
from .rules_r12 import rule_r12_protocol_scope
from .types import (
    Mission,
    Proposal,
    canonical_json,
    sha256_hex,
)

RULE_INFO: list[dict[str, Any]] = [
    {"rule_id": "R9_SIGNATURE",            "label": "Signature",       "phase": 0},
    {"rule_id": "R10_EXPIRY",              "label": "Expiry",          "phase": 0},
    {"rule_id": "R8_ABORT",                "label": "Abort",           "phase": 1},
    {"rule_id": "R1_BUDGET",               "label": "Budget",          "phase": 2},
    {"rule_id": "R2_FORBIDDEN",            "label": "Forbidden",       "phase": 2},
    {"rule_id": "R5_SCOPE",                "label": "Scope",           "phase": 2},
    {"rule_id": "R4_UPSELL_CAP",           "label": "Upsell Cap",      "phase": 2},
    {"rule_id": "R3_PRICE_DRIFT",          "label": "Price Drift",     "phase": 3},
    {"rule_id": "R11_NEGOTIATION_BOUND",   "label": "Negotiation",     "phase": 3},
    {"rule_id": "R12_PROTOCOL_SCOPE",      "label": "Protocol Scope",  "phase": 3},
    {"rule_id": "R7_ALLOWLIST",            "label": "Allowlist",       "phase": 3},
    {"rule_id": "R6_RATE_LIMIT",           "label": "Rate Limit",      "phase": 3},
]


def _check(rule_id: str, label: str, fn: Callable[[], Any]) -> dict[str, Any]:
    """Run one rule, swallow exceptions as FAIL-CLOSED."""
    try:
        v = fn()
    except Exception as e:
        return {
            "rule_id": rule_id, "label": label, "status": "FAIL",
            "reason": f"rule raised {type(e).__name__}: {e}",
        }
    if v is None:
        return {
            "rule_id": rule_id, "label": label, "status": "PASS",
            "reason": "",
        }
    return {
        "rule_id": rule_id, "label": label, "status": "FAIL",
        "reason": getattr(v, "message", "") or str(v),
        "attempted_value": getattr(v, "attempted_value", None),
        "limit_value": getattr(v, "limit_value", None),
        "hint": getattr(v, "hint", ""),
    }


def evaluate_full(*, mission: Mission | None,
                  proposal: Proposal | None,
                  catalog: dict[str, dict[str, Any]],
                  verify_fn: VerifyFn,
                  state: dict[str, Any] | None = None,
                  now_ts: int | None = None,
                  merchant_id: str = "SELLABLE-DEMO",
                  allowlist: frozenset[str] = frozenset({"SELLABLE-DEMO"}),
                  chain_ok: bool = True,
                  protocol_scope: dict[str, Any] | None = None) -> dict[str, Any]:
    """Run every R1-R12 rule and return the full structured matrix.

    Returns a dict with:
      - decision: APPROVE | REJECT | INPUT_MISSING | CHAIN_TAMPER
      - proposal_hash: str | None
      - rules: list of {rule_id, label, status, reason, ...}
      - first_failure: dict | None  (the rule that stopped the flow)
      - ts: unix seconds of the evaluation
    """
    state = state if state is not None else {}
    now_ts = now_ts if now_ts is not None else int(_time.time())

    def phash() -> str:
        return sha256_hex(canonical_json(proposal))

    if mission is None or proposal is None or not catalog:
        rules = [{"rule_id": r["rule_id"], "label": r["label"],
                  "status": "FAIL", "reason": "INPUT_MISSING"}
                 for r in RULE_INFO]
        return {
            "decision": "REJECT",
            "verdict_reason": "required input missing (fail-closed)",
            "proposal_hash": None,
            "rules": rules,
            "first_failure": rules[0] if rules else None,
            "ts": now_ts,
        }

    if not chain_ok:
        rules = [{"rule_id": r["rule_id"], "label": r["label"],
                  "status": "FAIL", "reason": "CHAIN_TAMPER halted evaluation"}
                 for r in RULE_INFO]
        return {
            "decision": "REJECT",
            "verdict_reason": "audit chain failed verification; halted",
            "proposal_hash": phash(),
            "rules": rules,
            "first_failure": rules[0],
            "ts": now_ts,
        }

    aborted = frozenset(state.get("aborted_missions", set()))
    effective_budget = int(mission.budget_paise * mission.upsell_cap)
    baseline = min((i.price_paise * i.qty for i in proposal.items), default=0)

    def r9() -> Any: return R.rule_r9_signature(mission, verify_fn)
    def r10() -> Any: return R.rule_r10_expiry(mission, now_ts)
    def r8() -> Any: return R.rule_r8_abort(mission.mission_id, aborted)
    def r1() -> Any: return R.rule_r1_budget(proposal, catalog, mission)
    def r2() -> Any: return R.rule_r2_forbidden(proposal, catalog, mission)
    def r5() -> Any: return R.rule_r5_scope(proposal, catalog, mission)
    def r4() -> Any: return R.rule_r4_upsell_cap(proposal, catalog, mission, baseline)
    def r3() -> Any: return R.rule_r3_price_drift(proposal, catalog)
    def r11() -> Any: return rule_r11_negotiation_bound(proposal, catalog, mission)
    def r12() -> Any: return rule_r12_protocol_scope(
        proposal, catalog, protocol_scope,
        merchant_id=merchant_id, now_ts=now_ts)
    def r7() -> Any: return R.rule_r7_allowlist(merchant_id, allowlist)
    def r6() -> Any: return R.rule_r6_rate_limit(mission.mission_id, state, now_ts)

    runners = [
        ("R9_SIGNATURE",          "Signature",      r9),
        ("R10_EXPIRY",            "Expiry",         r10),
        ("R8_ABORT",              "Abort",          r8),
        ("R1_BUDGET",             "Budget",         r1),
        ("R2_FORBIDDEN",          "Forbidden",      r2),
        ("R5_SCOPE",              "Scope",          r5),
        ("R4_UPSELL_CAP",         "Upsell Cap",     r4),
        ("R3_PRICE_DRIFT",        "Price Drift",    r3),
        ("R11_NEGOTIATION_BOUND", "Negotiation",    r11),
        ("R12_PROTOCOL_SCOPE",    "Protocol Scope", r12),
        ("R7_ALLOWLIST",          "Allowlist",      r7),
        ("R6_RATE_LIMIT",         "Rate Limit",     r6),
    ]

    rule_reports: list[dict[str, Any]] = []
    for rid, label, fn in runners:
        rule_reports.append(_check(rid, label, fn))

    failed = [r for r in rule_reports if r["status"] == "FAIL"]
    decision = "APPROVE" if not failed else "REJECT"
    first_failure = failed[0] if failed else None

    return {
        "decision": decision,
        "verdict_reason": (first_failure["reason"] if first_failure
                           else "all rules passed"),
        "proposal_hash": phash(),
        "rules": rule_reports,
        "first_failure": first_failure,
        "ts": now_ts,
        "effective_budget_paise": effective_budget,
        "merchant_id": merchant_id,
        "chain_ok": chain_ok,
    }
