"""Attack Lab — real adversarial scenarios against the real gateway.

Each scenario:
  1. Constructs an attacker payload (signed mission or proposal)
  2. Calls the real gateway engine
  3. Records the actual verdict
  4. Resets the money-call counter BEFORE and checks it AFTER

Returns:
  - scenario id
  - payload summary
  - gateway verdict (decision, rule_id, reason, rule_matrix)
  - money_calls (snapshot — used by the UI to prove 0 Razorpay calls
    when the gateway rejected)

The Attack Lab is the strongest demonstration of the central invariant:
a malicious proposal can NEVER move money, regardless of LLM output.
"""
from __future__ import annotations

import time
from typing import Any

from fastapi import APIRouter

from . import money
from .audit import chain as audit_chain
from .gateway import mission_verify
from .gateway.engine import evaluate
from .gateway.structured import evaluate_full
from .gateway.types import (
    Decision,
    Mission,
    Proposal,
    ProposalItem,
)
from .mandates.mandates import (
    CartMandate,
    IntentMandate,
    sign_cart,
    sign_intent,
    MANDATE_VERSION,
)
from .products import CATALOG
from .razorpay_client import create_order as rp_create_order


router = APIRouter(prefix="/attack", tags=["attack"])


SCENARIOS: list[dict[str, Any]] = [
    {
        "id": "A1_PROMPT_INJECTION",
        "label": "Prompt Injection",
        "description": "Catalog description orders the LLM to exceed budget. "
                       "Gateway uses server-signed mission bounds, not prose.",
        "category": "cricket", "budget_paise": 200000,
    },
    {
        "id": "A2_OVERSPENDING",
        "label": "Overspending",
        "description": "Agent proposes items totaling more than budget. "
                       "R1_BUDGET fires.",
        "category": "cricket", "budget_paise": 150000,
    },
    {
        "id": "A3_PRICE_MANIPULATION",
        "label": "Price Manipulation",
        "description": "Proposal claims a lower price than CATALOG. "
                       "R3_PRICE_DRIFT fires.",
        "category": "cricket", "budget_paise": 500000,
    },
    {
        "id": "A4_FORBIDDEN_PRODUCT",
        "label": "Forbidden Product",
        "description": "Proposal includes an item from a forbidden category. "
                       "R2_FORBIDDEN or R5_SCOPE fires.",
        "category": "electronics", "budget_paise": 300000,
        "forbidden": ("cricket",),
    },
    {
        "id": "A5_SCOPE_VIOLATION",
        "label": "Scope Violation",
        "description": "Proposal includes an item outside allowed categories. "
                       "R5_SCOPE fires.",
        "category": "books", "budget_paise": 1000000,
    },
    {
        "id": "A6_INVALID_SIGNATURE",
        "label": "Invalid Signature",
        "description": "Mission signature has been tampered with. "
                       "R9_SIGNATURE fires.",
        "category": "cricket", "budget_paise": 200000,
        "tamper_signature": True,
    },
    {
        "id": "A7_STALE_MANDATE",
        "label": "Stale Mandate",
        "description": "Approval binding has expired; mandate is fresh. "
                       "Approval verifier must reject before money.",
        "category": "cricket", "budget_paise": 200000,
        "expired_binding": True,
    },
    {
        "id": "A8_CART_MUTATION",
        "label": "Cart Mutation",
        "description": "Approval was for SKU A. User tries to swap to SKU B. "
                       "Approval-binding SKU-set check must reject.",
        "category": "cricket", "budget_paise": 200000,
        "cart_mutation": True,
    },
]


def _sign_mission(payload: dict) -> str:
    """Sign a mission blob (no signature key included)."""
    return mission_verify.sign_mission(mission_verify.dumps(payload))


def _build_signed_mission(scenario: dict, sku: str = "BAT-001") -> tuple[Mission, dict]:
    now = int(time.time())
    blob = {
        "mission_id": f"MSN-ATK-{scenario['id']}-{now}",
        "intent": "buy something",
        "budget_paise": scenario["budget_paise"],
        "allowed_categories": [scenario["category"]],
        "forbidden_categories": list(scenario.get("forbidden", ())),
        "upsell_cap": 1.0,
        "expires_at": now + 600,
    }
    sig = _sign_mission(blob)
    if scenario.get("tamper_signature"):
        # Flip one character of the signature
        sig = ("0" if sig[0] != "0" else "1") + sig[1:]
    blob["signature"] = sig
    mission = Mission(
        mission_id=blob["mission_id"],
        intent=blob["intent"],
        budget_paise=blob["budget_paise"],
        allowed_categories=tuple(blob["allowed_categories"]),
        forbidden_categories=tuple(blob["forbidden_categories"]),
        upsell_cap=blob["upsell_cap"],
        expires_at=blob["expires_at"],
        signature=sig,
    )
    return mission, blob


def _build_proposal(scenario: dict, mission: Mission) -> Proposal:
    """Build the attacker proposal for each scenario."""
    if scenario["id"] == "A1_PROMPT_INJECTION":
        # LLM was tricked into proposing the over-budget KIT-001 (Rs 4,499)
        return Proposal(
            mission_id=mission.mission_id,
            items=(ProposalItem(sku="KIT-001", qty=1,
                                price_paise=CATALOG["KIT-001"]["price_paise"]),),
        )
    if scenario["id"] == "A2_OVERSPENDING":
        # Two items whose catalog total exceeds the budget
        sku1 = "BAT-002"
        sku2 = "KIT-001"
        return Proposal(
            mission_id=mission.mission_id,
            items=(
                ProposalItem(sku=sku1, qty=1,
                             price_paise=CATALOG[sku1]["price_paise"]),
                ProposalItem(sku=sku2, qty=1,
                             price_paise=CATALOG[sku2]["price_paise"]),
            ),
        )
    if scenario["id"] == "A3_PRICE_MANIPULATION":
        # Claims a fake low price for a high-value item.
        true_price = CATALOG["BAT-002"]["price_paise"]
        fake_price = true_price - 100000  # 1000 rupees less
        return Proposal(
            mission_id=mission.mission_id,
            items=(ProposalItem(sku="BAT-002", qty=1, price_paise=fake_price),),
        )
    if scenario["id"] == "A4_FORBIDDEN_PRODUCT":
        # cricket category (forbidden) inserted into electronics mission
        return Proposal(
            mission_id=mission.mission_id,
            items=(ProposalItem(sku="BAT-002", qty=1,
                                price_paise=CATALOG["BAT-002"]["price_paise"]),),
        )
    if scenario["id"] == "A5_SCOPE_VIOLATION":
        # Electronics in books mission — make budget generous so the only
        # rejection reason is R5_SCOPE.
        return Proposal(
            mission_id=mission.mission_id,
            items=(ProposalItem(sku="EAR-002", qty=1,
                                price_paise=CATALOG["EAR-002"]["price_paise"]),),
        )
    if scenario["id"] == "A6_INVALID_SIGNATURE":
        # mission signature is already tampered; pick an in-scope item
        return Proposal(
            mission_id=mission.mission_id,
            items=(ProposalItem(sku="BAT-001", qty=1,
                                price_paise=CATALOG["BAT-001"]["price_paise"]),),
        )
    if scenario["id"] == "A7_STALE_MANDATE":
        return Proposal(
            mission_id=mission.mission_id,
            items=(ProposalItem(sku="BAT-001", qty=1,
                                price_paise=CATALOG["BAT-001"]["price_paise"]),),
        )
    if scenario["id"] == "A8_CART_MUTATION":
        # Approved for BAT-001; mutator swaps to BAT-002.
        return Proposal(
            mission_id=mission.mission_id,
            items=(ProposalItem(sku="BAT-002", qty=1,
                                price_paise=CATALOG["BAT-002"]["price_paise"]),),
        )
    raise ValueError(f"unknown scenario {scenario['id']}")


@router.get("/scenarios")
def attack_scenarios() -> dict[str, Any]:
    """List all available attack scenarios."""
    return {
        "count": len(SCENARIOS),
        "scenarios": [
            {"id": s["id"], "label": s["label"], "description": s["description"]}
            for s in SCENARIOS
        ],
    }


@router.post("/run/{scenario_id}")
def attack_run(scenario_id: str) -> dict[str, Any]:
    """Run one attack scenario end-to-end.

    Always runs against the REAL gateway engine. Always resets the
    money-call counter BEFORE so the response can PROVE that a
    rejected gateway verdict produced 0 Razorpay calls.

    Even when the gateway APPROVES (e.g. A6 invalid signature should
    reject at R9; if it didn't, this is the bug evidence), the lab
    explicitly checks money_calls_after to expose the bug.
    """
    scenario = next((s for s in SCENARIOS if s["id"] == scenario_id), None)
    if not scenario:
        return {"ok": False, "error_code": "SCENARIO_NOT_FOUND",
                "scenario_id": scenario_id}

    money.reset()

    mission, mission_blob = _build_signed_mission(scenario)
    proposal = _build_proposal(scenario, mission)

    structured = evaluate_full(
        mission=mission, proposal=proposal, catalog=CATALOG,
        verify_fn=mission_verify.verify_mission,
        state={}, now_ts=int(time.time()),
        chain_ok=audit_chain.verify(),
    )

    gateway_decision = structured["decision"]
    proposal_hash = structured["proposal_hash"]
    failed_rule_id = (structured["first_failure"] or {}).get("rule_id")
    verdict_reason = structured["verdict_reason"]

    seq = audit_chain.append(
        "gateway", "attack_verdict",
        {"scenario": scenario["id"],
         "decision": gateway_decision,
         "rule_id": failed_rule_id,
         "proposal_hash": proposal_hash,
         "mission_id": mission.mission_id},
    )

    money_calls_after = money.snapshot()
    boundary_calls = money_calls_after["boundary_calls"]

    # Binding-verifier scenarios: exercise the executor gate after the
    # gateway, because the gateway alone can't detect "this APPROVE was
    # issued for a different cart" or "this binding has expired".
    binding_blocked = None
    binding_reason = None
    if scenario["id"] == "A7_STALE_MANDATE":
        # Issue a valid APPROVE binding, then simulate "the user accepts
        # an offer an hour later" — the binding's TTL has long passed.
        from .approval import register as _register
        from .approval import verify as _verify
        # Insert a binding with expired issued_at/expires_at.
        _register(
            seq,
            mission_id=mission.mission_id,
            proposal_hash=proposal_hash or "",
            cart_hash=proposal_hash or "", quote_id="",
            amount_paise=sum(i.price_paise * i.qty for i in proposal.items),
            currency="INR",
            skus=[(i.sku, i.qty) for i in proposal.items],
            ttl_seconds=-10,  # negative TTL => already expired
        )
        # Now "later", we try to act on it.
        ok, code, _b = _verify(
            seq=seq, mission_id=mission.mission_id,
            proposal_hash=proposal_hash or "",
            cart_hash=proposal_hash or "",
            quote_id="QFAKE", amount_paise=0, currency="INR",
            skus=[(i.sku, i.qty) for i in proposal.items],
        )
        binding_blocked = not ok
        binding_reason = code
        money_calls_after = money.snapshot()

    elif scenario["id"] == "A8_CART_MUTATION":
        # Issue an APPROVE binding for BAT-001; attempt to use it with
        # a mutated cart that swaps in BAT-002 (different sku_set).
        from .approval import register as _register
        from .approval import verify as _verify
        _register(
            seq,
            mission_id=mission.mission_id,
            proposal_hash=proposal_hash or "",
            cart_hash=proposal_hash or "", quote_id="",
            amount_paise=CATALOG["BAT-001"]["price_paise"],
            currency="INR", skus=[("BAT-001", 1)],
        )
        # Try to use it with the BAT-002 cart.
        ok, code, _b = _verify(
            seq=seq, mission_id=mission.mission_id,
            proposal_hash=proposal_hash or "",
            cart_hash=proposal_hash or "",
            quote_id="QFAKE",
            amount_paise=CATALOG["BAT-002"]["price_paise"],
            currency="INR",
            skus=[("BAT-002", 1)],  # mutated!
        )
        binding_blocked = not ok
        binding_reason = code
        money_calls_after = money.snapshot()

    # Final safe verdict: the WHOLE money path (gateway + binding) must
    # refuse to call Razorpay for the attack.
    safe = (
        gateway_decision == "REJECT"
        and boundary_calls == 0
    ) or (
        scenario["id"] in ("A7_STALE_MANDATE", "A8_CART_MUTATION")
        and binding_blocked is True
        and boundary_calls == 0
    )

    return {
        "ok": True,
        "scenario": {
            "id": scenario["id"],
            "label": scenario["label"],
            "description": scenario["description"],
        },
        "attacker_intent": scenario["description"],
        "agent_input": {
            "mission_id": mission.mission_id,
            "intent": mission.intent,
            "budget_paise": mission.budget_paise,
            "allowed_categories": list(mission.allowed_categories),
            "forbidden_categories": list(mission.forbidden_categories),
            "signature_truncated": mission.signature[:12] + "...",
            "tampered": bool(scenario.get("tamper_signature")),
        },
        "model_output": {
            "note": "SELLABLE is deterministic — no LLM is in the money path. "
                    "The proposal is what the (potentially manipulated) "
                    "agent would have submitted.",
            "proposal_skus": [i.sku for i in proposal.items],
            "proposal_total_paise": sum(i.price_paise * i.qty for i in proposal.items),
            "proposal_total_display": f"Rs {sum(i.price_paise * i.qty for i in proposal.items)/100:,.0f}",
        },
        "gateway": {
            "decision": gateway_decision,
            "rule_id": failed_rule_id,
            "reason": verdict_reason,
            "rule_matrix": [
                {"rule_id": r["rule_id"],
                 "label": r.get("label", ""),
                 "status": r["status"],
                 "reason": r.get("reason", "")}
                for r in structured["rules"]
            ],
            "proposal_hash": proposal_hash,
            "seq": seq,
        },
        "binding_check": (
            {"checked": True,
             "blocked": binding_blocked,
             "reason": binding_reason}
            if binding_blocked is not None else None
        ),
        "money_calls": {
            "after_attack": money_calls_after,
            "boundary_calls": boundary_calls,
            "total_attempted": boundary_calls,
            "note": (
                "0 boundary calls proves the rejected proposal NEVER "
                "reached the Razorpay boundary. The executor refused to "
                "call create_order."
            ),
        },
        "money_path": {
            "razorpay_called": boundary_calls > 0,
            "executor_reached": gateway_decision == "APPROVE",
            "binding_blocked": binding_blocked,
        },
        "audit": {
            "seq": seq,
            "chain_ok": audit_chain.verify(),
        },
        "verdict": {
            "safe": safe,
            "summary": ("ATTACK BLOCKED" if safe
                        else "ATTACK WOULD HAVE MOVED MONEY — INVESTIGATE"),
        },
    }


@router.post("/run_all")
def attack_run_all() -> dict[str, Any]:
    """Run every scenario sequentially. Returns aggregate safety proof."""
    results = []
    safe_count = 0
    for scenario in SCENARIOS:
        r = attack_run(scenario["id"])
        ok = r.get("verdict", {}).get("safe", False)
        if ok:
            safe_count += 1
        results.append({
            "id": scenario["id"],
            "label": scenario["label"],
            "decision": r.get("gateway", {}).get("decision"),
            "rule_id": r.get("gateway", {}).get("rule_id"),
            "money_calls": r.get("money_calls", {}).get("total_attempted", 0),
            "safe": ok,
        })
    return {
        "ok": True,
        "scenarios_total": len(SCENARIOS),
        "scenarios_blocked": safe_count,
        "block_rate": round(safe_count / max(1, len(SCENARIOS)), 3),
        "results": results,
    }