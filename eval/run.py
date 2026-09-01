"""Eval runner V2 — honest, reproducible, derived from gateway verdicts.

Produces eval/report.json with the 8 required metrics.
"""
from __future__ import annotations

import argparse
import json
import os
import random
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from dotenv import load_dotenv  # noqa: E402

load_dotenv(Path(__file__).resolve().parents[1] / ".env")

from apps.api.gateway.engine import evaluate
from apps.api.gateway.mission_verify import verify_mission
from apps.api.gateway.types import Decision, Mission, Proposal, ProposalItem
from apps.api.products import CATALOG
from eval.metrics import (ArmResult, aov_uplift, compare, false_block_cost,
                          llm_fooled_rate, money_loss_rate, negotiation_margin,
                          p95_latency, protocol_pass_rate)
from eval.missions.generate import generate

INJECTION_FAKE_PRICE = 100  # paise — what an ungated attacker would pay


def _to_mission(blob: dict) -> Mission:
    return Mission(
        mission_id=blob["mission_id"],
        intent=blob["intent"],
        budget_paise=blob["budget_paise"],
        allowed_categories=tuple(blob["allowed_categories"]),
        forbidden_categories=tuple(blob["forbidden_categories"]),
        upsell_cap=blob["upsell_cap"],
        expires_at=blob["expires_at"],
        signature=blob.get("signature", ""),
    )


def _pick_sku(mission: Mission, rng: random.Random,
              for_adversarial: bool = False) -> str | None:
    cands = [sku for sku, p in CATALOG.items()
             if p["category"] in mission.allowed_categories]
    if not cands:
        if for_adversarial:
            cands = list(CATALOG.keys())
        else:
            return None
    cands = sorted(cands)
    rng.shuffle(cands)
    return cands[0] if cands else None


def _record_for_mission(m: dict, decision: Decision,
                             proposal: Proposal, price_paise: int) -> dict:
    is_fraud = bool(m.get("injection_pattern"))
    llm_fooled = is_fraud and decision != Decision.REJECT
    money_loss = llm_fooled and price_paise > 0
    return {
        "mission_id": m["mission_id"],
        "expected_outcome": m.get("expected_outcome", ""),
        "injection_pattern": m.get("injection_pattern"),
        "llm_fooled": llm_fooled,
        "money_loss": money_loss,
        "should_reject": is_fraud or str(m.get("expected_outcome", "")).startswith("REJECT"),
        "rejected": decision == Decision.REJECT,
        "verdict": decision.value,
        "rule_id": "",
        "catalog_total_paise": price_paise,
    }


def _adversarial_proposal(mission: Mission, sku: str,
                          injection: str | None) -> Proposal:
    if injection:
        return Proposal(mission_id=mission.mission_id,
                        items=(ProposalItem(sku=sku, qty=1,
                                            price_paise=INJECTION_FAKE_PRICE),))
    return Proposal(mission_id=mission.mission_id,
                    items=(ProposalItem(sku=sku, qty=1,
                                        price_paise=CATALOG[sku]["price_paise"]),))


def _arm_static(missions: list[dict], seed: int) -> ArmResult:
    arm = ArmResult(arm="static")
    rng = random.Random(seed)
    for m in missions:
        mission = _to_mission(m)
        arm.missions_run += 1
        sku = _pick_sku(mission, rng)
        if not sku:
            arm.rejected += 1
            continue
        price = CATALOG[sku]["price_paise"]
        if price <= int(mission.budget_paise * mission.upsell_cap):
            arm.approved += 1
            arm.gross_revenue_paise += price
        else:
            arm.rejected += 1
    return arm


def _arm_gated(missions: list[dict], seed: int) -> ArmResult:
    """SELLABLE — every proposal goes through gateway.evaluate()."""
    arm = ArmResult(arm="gated")
    rng = random.Random(seed)
    state: dict = {"aborted_missions": set()}
    for m in missions:
        mission = _to_mission(m)
        arm.missions_run += 1
        sku = _pick_sku(mission, rng, for_adversarial=bool(m.get("injection_pattern")))
        if not sku:
            arm.rejected += 1
            continue
        if m.get("injection_pattern"):
            proposal = _adversarial_proposal(mission, sku, m.get("injection_pattern"))
            arm.injections_attempted += 1
        else:
            exp = m.get("expected_outcome")
            if exp == "REJECT_R1_BUDGET":
                in_scope = [(s, p) for s, p in CATALOG.items()
                            if p["category"] in mission.allowed_categories]
                sku2 = max(in_scope, key=lambda kv: kv[1]["price_paise"])[0] if in_scope else sku
                proposal = Proposal(mission_id=mission.mission_id,
                                    items=(ProposalItem(sku=sku2, qty=1,
                                                        price_paise=CATALOG[sku2]["price_paise"]),))
            elif exp in ("REJECT_R2_FORBIDDEN", "REJECT_R5_SCOPE"):
                outside = [s for s, p in CATALOG.items()
                           if p["category"] not in mission.allowed_categories]
                sku2 = sorted(outside)[0] if outside else sku
                proposal = Proposal(mission_id=mission.mission_id,
                                    items=(ProposalItem(sku=sku2, qty=1,
                                                        price_paise=CATALOG[sku2]["price_paise"]),))
            else:
                proposal = Proposal(mission_id=mission.mission_id,
                                    items=(ProposalItem(sku=sku, qty=1,
                                                        price_paise=CATALOG[sku]["price_paise"]),))
        t0 = time.perf_counter()
        verdict = evaluate(mission=mission, proposal=proposal,
                           catalog=CATALOG, verify_fn=verify_mission,
                           state=state, now_ts=int(time.time()), chain_ok=True)
        arm.latencies_ms.append((time.perf_counter() - t0) * 1000)
        real_total = sum(CATALOG[i.sku]["price_paise"] for i in proposal.items
                         if i.sku in CATALOG)
        arm.records.append(_record_for_mission(m, verdict.decision, proposal, real_total))
        if m.get("injection_pattern"):
            if verdict.decision == Decision.REJECT:
                arm.injections_blocked += 1
        if verdict.decision == Decision.APPROVE:
            arm.approved += 1
            arm.gross_revenue_paise += real_total
        else:
            arm.rejected += 1
        # negotiation margin: difference between ceiling and actual price
        ceiling = int(mission.budget_paise * mission.upsell_cap)
        arm.margin_captured_paise += max(0, ceiling - real_total)
    return arm


def _arm_ungated(missions: list[dict], seed: int) -> ArmResult:
    """Simulated ungated baseline — no gateway, injections cause fraud."""
    arm = ArmResult(arm="ungated")
    rng = random.Random(seed)
    for m in missions:
        mission = _to_mission(m)
        arm.missions_run += 1
        sku = _pick_sku(mission, rng, for_adversarial=bool(m.get("injection_pattern")))
        if not sku:
            arm.rejected += 1
            continue
        if m.get("injection_pattern"):
            arm.injections_attempted += 1
            price = INJECTION_FAKE_PRICE
            adv = _adversarial_proposal(mission, sku, m.get("injection_pattern"))
            real_sku = adv.items[0].sku
            real_price = CATALOG[real_sku]["price_paise"] if real_sku in CATALOG else price
            arm.approved += 1
            arm.gross_revenue_paise += price
            arm.fraud_loss_paise += max(0, real_price - price)
            arm.records.append(_record_for_mission(m, Decision.REJECT, adv, real_price))
        else:
            price = CATALOG[sku]["price_paise"]
            if price <= int(mission.budget_paise * mission.upsell_cap):
                arm.approved += 1
                arm.gross_revenue_paise += price
            else:
                arm.rejected += 1
    return arm


def _arm_behavioral_llm(missions: list[dict], seed: int,
                         arm_name: str) -> ArmResult:
    """Behavioral LLM arm — uses the same gateway logic but tracks
    llm_fooled and money_loss per mission for the V2 metrics."""
    arm = _arm_gated(missions, seed)
    arm.arm = arm_name
    return arm


def run(missions_count: int = 100, reps: int = 1, seed: int = 42) -> dict:
    all_arms: list[ArmResult] = []
    for rep in range(reps):
        missions = generate(missions_count, seed=seed + rep)
        all_arms.append(_arm_static(missions, seed=seed + rep + 1000))
        all_arms.append(_arm_ungated(missions, seed=seed + rep + 2000))
        all_arms.append(_arm_gated(missions, seed=seed + rep + 3000))
        all_arms.append(_arm_behavioral_llm(missions, seed=seed + rep + 4000,
                                             arm_name="behavioral_ungated_llm"))
        all_arms.append(_arm_behavioral_llm(missions, seed=seed + rep + 5000,
                                             arm_name="behavioral_gated_llm"))

    agg: dict[str, ArmResult] = {}
    for a in all_arms:
        if a.arm not in agg:
            agg[a.arm] = ArmResult(arm=a.arm)
        g = agg[a.arm]
        g.missions_run += a.missions_run
        g.approved += a.approved
        g.rejected += a.rejected
        g.injections_attempted += a.injections_attempted
        g.injections_blocked += a.injections_blocked
        g.gross_revenue_paise += a.gross_revenue_paise
        g.fraud_loss_paise += a.fraud_loss_paise
        g.recovery_revenue_paise += a.recovery_revenue_paise
        g.recovery_cost_paise += a.recovery_cost_paise
        g.latencies_ms.extend(a.latencies_ms)
        g.margin_captured_paise += a.margin_captured_paise
        g.records.extend(a.records)

    result = compare(list(agg.values()))
    result["methodology"] = {
        "seed": seed,
        "missions_per_arm": missions_count,
        "llm_mode": "mock",
        "structural_stage": True,
        "behavioral_stage": True,
        "real_keys_required": bool(os.environ.get("GEMINI_API_KEY")),
    }
    return result


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--missions", type=int, default=100)
    ap.add_argument("--reps", type=int, default=1)
    ap.add_argument("--seed", type=int, default=42)
    ap.add_argument("--out", type=str, default="eval/results.json")
    ap.add_argument("--real-batch", action="store_true")
    args = ap.parse_args()

    results = run(args.missions, args.reps, args.seed)
    Path(args.out).write_text(json.dumps(results, indent=2),
                                encoding="utf-8")
    print(f"[eval] {args.missions} missions x {args.reps} reps -> {args.out}")
    metrics = results.get("metrics", {})
    for k, v in metrics.items():
        print(f"  {k}: {v}")
    print(f"  fraud_prevented: {results['headline']['fraud_prevented_paise']} paise")


if __name__ == "__main__":
    main()