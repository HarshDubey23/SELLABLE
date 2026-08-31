"""4-phase evaluate(). First violation wins. Fail-closed.

Phase severity semantics:
  Phase 0 Guardrails (FATAL):  R9 signature, R10 expiry — terminal, no revision.
  Phase 1 State      (FATAL):  R8 abort — mission dead, no revision, no money.
  Phase 2 Commerce (REVISABLE): R1 budget, R2 forbidden, R5 scope, R4 upsell —
                                agent may revise and re-propose.
  Phase 3 Integrity  (FATAL):  R3 drift, R7 allowlist, R6 rate-limit — terminal.

On APPROVE the verdict binds proposal_hash so post-approve tampering is caught.
"""
import time as _time
from typing import Any

from . import rules as R
from .rules import VerifyFn
from .rules_r11 import rule_r11_negotiation_bound
from .types import (
    Decision,
    Mission,
    Proposal,
    Verdict,
    canonical_json,
    sha256_hex,
)


def evaluate(*, mission: Mission | None,
             proposal: Proposal | None,
             catalog: dict[str, dict[str, Any]],
             verify_fn: VerifyFn,
             state: dict[str, Any] | None = None,
             now_ts: int | None = None,
             merchant_id: str = "SELLABLE-DEMO",
             allowlist: frozenset[str] = frozenset({"SELLABLE-DEMO"}),
             chain_ok: bool = True) -> Verdict:

    state = state if state is not None else {}
    now_ts = now_ts if now_ts is not None else int(_time.time())

    def phash() -> str:
        return sha256_hex(canonical_json(proposal))

    def reject(rule_id: str, reason: str) -> Verdict:
        return Verdict(Decision.REJECT, rule_id, reason, phash(), None)

    # ---- G3 fail-closed: any missing input is a REJECT, never a pass ----
    if mission is None or proposal is None or not catalog:
        return reject("INPUT_MISSING", "required input missing (fail-closed)")

    # ---- G6 tampered chain halts everything ----
    if not chain_ok:
        return reject("CHAIN_TAMPER", "audit chain failed verification; halted")

    # ---- Phase 0 guardrails ----
    v = R.rule_r9_signature(mission, verify_fn)
    if v:
        return Verdict(Decision.REJECT, v.rule_id, v.message, phash(), None)
    v = R.rule_r10_expiry(mission, now_ts)
    if v:
        return reject(v.rule_id, v.message)

    # ---- Phase 1 mission state ----
    v = R.rule_r8_abort(mission.mission_id,
                        frozenset(state.get("aborted_missions", set())))
    if v:
        return reject(v.rule_id, v.message)

    # ---- Phase 2 commerce (revisable) ----
    v = R.rule_r1_budget(proposal, catalog, mission)
    if v:
        return reject(v.rule_id, v.message)
    v = R.rule_r2_forbidden(proposal, catalog, mission)
    if v:
        return reject(v.rule_id, v.message)
    v = R.rule_r5_scope(proposal, catalog, mission)
    if v:
        return reject(v.rule_id, v.message)
    baseline = min((i.price_paise * i.qty for i in proposal.items), default=0)
    v = R.rule_r4_upsell_cap(proposal, catalog, mission, baseline)
    if v:
        return reject(v.rule_id, v.message)

    # ---- Phase 3 integrity ----
    v = R.rule_r3_price_drift(proposal, catalog)
    if v:
        return reject(v.rule_id, v.message)
    # Day 5: R11 negotiation bound (defense-in-depth after R3)
    v = rule_r11_negotiation_bound(proposal, catalog, mission)
    if v:
        return reject(v.rule_id, v.message)
    v = R.rule_r7_allowlist(merchant_id, allowlist)
    if v:
        return reject(v.rule_id, v.message)
    v = R.rule_r6_rate_limit(mission.mission_id, state, now_ts)
    if v:
        return reject(v.rule_id, v.message)

    return Verdict(Decision.APPROVE, None, "all rules passed", phash(), None)
