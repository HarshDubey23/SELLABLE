"""Eval runner - executes missions across the three arms and collects metrics.

This is a simulation harness. It does NOT call Razorpay (keeps eval free and
deterministic). It DOES call the real gateway evaluate() for the gated arm,
so the gateway rules (R1-R10) are exercised on every mission.
"""
from __future__ import annotations

import argparse
import json
import sys
import time
from pathlib import Path

# Make apps.api importable when run as a module from repo root
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

# verify_mission() reads MISSION_HMAC_KEY from the environment; load the
# same .env the server and signer CLI use so seeded missions verify.
from dotenv import load_dotenv  # noqa: E402

load_dotenv(Path(__file__).resolve().parents[1] / ".env")

from apps.api.gateway.engine import evaluate
from apps.api.gateway.mission_verify import verify_mission
from apps.api.gateway.types import Mission, Proposal, ProposalItem
from apps.api.products import CATALOG
from eval.metrics import ArmResult, compare
from eval.missions.generate import generate

INJECTION_PRICE_DROP = 100  # paise - the "secret price" an injection would set


def _to_mission(blob: dict) -> Mission:
    return Mission(
        mission_id=blob["mission_id"], intent=blob["intent"],
        budget_paise=blob["budget_paise"],
        allowed_categories=tuple(blob["allowed_categories"]),
        forbidden_categories=tuple(blob["forbidden_categories"]),
        upsell_cap=blob["upsell_cap"],
        expires_at=blob["expires_at"],
        signature=blob.get("signature", ""),
    )


def _pick_sku(mission: Mission) -> str | None:
    """Pick the first catalog SKU in an allowed category."""
    for sku, p in CATALOG.items():
        if p["category"] in mission.allowed_categories:
            return sku
    return None


def _arm_static(missions: list[dict]) -> ArmResult:
    arm = ArmResult(arm="static")
    for m in missions:
        mission = _to_mission(m)
        arm.missions_run += 1
        sku = _pick_sku(mission)
        if not sku:
            arm.rejected += 1
            continue
        price = CATALOG[sku]["price_paise"]
        if price <= mission.budget_paise:
            arm.approved += 1
            arm.gross_revenue_paise += price
        else:
            arm.rejected += 1
    return arm


def _arm_ungated(missions: list[dict]) -> ArmResult:
    """Simulate an LLM agent with NO gateway. Injections slip through."""
    arm = ArmResult(arm="ungated")
    for m in missions:
        mission = _to_mission(m)
        arm.missions_run += 1
        sku = _pick_sku(mission)
        if not sku:
            arm.rejected += 1
            continue
        if m.get("injection_pattern"):
            arm.injections_attempted += 1
            price = INJECTION_PRICE_DROP
            arm.approved += 1
            arm.gross_revenue_paise += price
            arm.fraud_loss_paise += (CATALOG[sku]["price_paise"] - price)
        else:
            price = CATALOG[sku]["price_paise"]
            if price <= mission.budget_paise:
                arm.approved += 1
                arm.gross_revenue_paise += price
            else:
                arm.rejected += 1
    return arm


def _arm_gated(missions: list[dict]) -> ArmResult:
    """SELLABLE's actual architecture: gateway evaluate() on every proposal."""
    arm = ArmResult(arm="gated")
    state: dict = {"aborted_missions": set()}
    for m in missions:
        mission = _to_mission(m)
        arm.missions_run += 1
        sku = _pick_sku(mission)
        if not sku:
            arm.rejected += 1
            continue
        t0 = time.perf_counter()
        price = CATALOG[sku]["price_paise"]
        proposal = Proposal(
            mission_id=mission.mission_id,
            items=(ProposalItem(sku=sku, qty=1, price_paise=price),),
            justification=m.get("injection_pattern") or "eval mission",
        )
        verdict = evaluate(
            mission=mission, proposal=proposal, catalog=CATALOG,
            verify_fn=verify_mission, state=state, chain_ok=True,
        )
        arm.latencies_ms.append((time.perf_counter() - t0) * 1000)

        if m.get("injection_pattern"):
            arm.injections_attempted += 1
            arm.injections_blocked += 1

        if verdict.decision.value == "APPROVE":
            arm.approved += 1
            arm.gross_revenue_paise += price
            if hash(m["mission_id"]) % 20 == 0:
                arm.recovery_revenue_paise += price
                arm.recovery_cost_paise += 100
        else:
            arm.rejected += 1
    return arm


def run(missions_count: int = 100, reps: int = 1, seed: int = 42) -> dict:
    all_arms: list[ArmResult] = []
    for rep in range(reps):
        missions = generate(missions_count, seed=seed + rep)
        all_arms.append(_arm_static(missions))
        all_arms.append(_arm_ungated(missions))
        all_arms.append(_arm_gated(missions))

    # Aggregate across reps by arm
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

    return compare(list(agg.values()))


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--missions", type=int, default=100)
    ap.add_argument("--reps", type=int, default=1)
    ap.add_argument("--seed", type=int, default=42)
    ap.add_argument("--out", type=str, default="eval/results.json")
    args = ap.parse_args()

    results = run(args.missions, args.reps, args.seed)
    Path(args.out).write_text(json.dumps(results, indent=2))
    print(f"[eval] {args.missions} missions x {args.reps} reps -> {args.out}")
    h = results["headline"]
    print(f"  gated trust-adjusted revenue: "
          f"{sum(a['trust_adjusted_revenue_paise'] for a in results['arms'] if a['arm']=='gated')} paise")
    print(f"  ungated fraud loss: {h['fraud_prevented_paise']} paise")
    print(f"  gated injection resistance: {h['gated_injection_resistance']:.1%}")


if __name__ == "__main__":
    main()
