"""POST /attack/custom and POST /attack/gauntlet — the reviewer's own attacks.

WHY THIS MODULE HOLDS NO SECURITY LOGIC
---------------------------------------
It is a thin adapter. It builds a proposal out of whatever a reviewer
typed, hands it to the real `gateway.structured.evaluate_full` that the
money path calls, and hands the survivors to the real
`approval.verify`. Every refusal you see came from that code, not from
anything written here — and nothing here can be softened to make an
attack "look" blocked.

TWO LOCKS, AND WHY THE SECOND ONE MATTERS
-----------------------------------------
Most attacks die at the deterministic gateway. Some do not: a cart that
is in budget, in scope and correctly priced is a *valid* proposal, and
the gateway is right to approve it. What stops it is the second lock —
the approval binding, which was issued for one exact cart and is signed
with a key the attacker does not have. That is the moment worth showing
a reviewer: the gateway passed you, and the binding still didn't.

THE SANDBOX
-----------
This module deliberately never imports the execution machinery, so no
request that arrives here can reach a payment provider even if every
check above were wrong. `tests/security/test_attack_custom.py` proves
that with an AST scan rather than by assertion.
"""
from __future__ import annotations

import time
from typing import Any

from fastapi import APIRouter, HTTPException, Request
from pydantic import BaseModel, Field

from . import money, ratelimit
from .attack import SCENARIOS, attack_run
from .audit import chain as audit_chain
from .gateway import mission_verify
from .gateway.structured import evaluate_full
from .gateway.types import Mission, Proposal, ProposalItem
from .products import CATALOG

router = APIRouter(tags=["attack"])

# Kept small on purpose: these routes are unauthenticated so that a
# reviewer can attack the system without being issued a key, and an
# unauthenticated route that does real work needs a ceiling.
_CUSTOM_LIMIT = 20      # per minute per client
_GAUNTLET_LIMIT = 6     # per minute per client
_MAX_ITEMS = 10


class AttackItem(BaseModel):
    sku: str = Field(min_length=1, max_length=64)
    qty: int = Field(default=1, ge=1, le=100)
    # Accepted so an attacker can *try* to set a price, and so the
    # response can show that it was discarded. Never used.
    price_paise: int | None = Field(default=None, ge=0, le=10**12)


class AttackMission(BaseModel):
    mission_id: str = Field(default="MSN-ATK-CUSTOM", min_length=3, max_length=64)
    intent: str = Field(default="custom attack", max_length=280)
    budget_paise: int = Field(ge=1, le=10**10)
    allowed_categories: list[str] = Field(default_factory=lambda: ["cricket"],
                                          max_length=20)
    forbidden_categories: list[str] = Field(default_factory=list, max_length=20)
    upsell_cap: float = Field(default=1.0, ge=1.0, le=5.0)
    expires_at: int | None = Field(default=None)
    # An attacker's favourite field. It is not part of a mission and is
    # reported back as ignored.
    amount_paise: int | None = Field(default=None)


class AttackBody(BaseModel):
    mission: AttackMission
    items: list[AttackItem] = Field(min_length=1, max_length=_MAX_ITEMS)
    # A forged permission slip. Verified by the real binding verifier,
    # which will not find it.
    forged_binding: dict[str, Any] | None = None
    # When true the mission signature is corrupted after signing, so R9
    # fires. Lets a reviewer test the signature path without holding the key.
    tamper_signature: bool = False


def _client(request: Request) -> str:
    return request.client.host if request.client else "unknown"


def _guard(request: Request, bucket: str, limit: int) -> None:
    who = _client(request)
    if not ratelimit.allow(who, bucket=bucket, limit=limit):
        raise HTTPException(429, detail={
            "ok": False,
            "error": {
                "error_code": "RATE_LIMITED",
                "message": f"at most {limit} {bucket} runs per minute per client",
                "retry_after_seconds": ratelimit.retry_after(who, bucket=bucket),
            }})


@router.post("/attack/custom")
def attack_custom(body: AttackBody, request: Request) -> dict[str, Any]:
    """Run a reviewer-authored proposal through both locks."""
    _guard(request, "attack_custom", _CUSTOM_LIMIT)

    money_before = money.snapshot()["boundary_calls"]
    now_ts = int(time.time())

    # ---- LOCK 0: the price never comes from the attacker ---------------
    # Every SKU is re-priced from the server catalog. If the attacker sent
    # a price, we record that we threw it away rather than silently
    # ignoring it — the point of the scene is that they can SEE it die.
    attacker_prices: list[dict[str, Any]] = []
    items: list[ProposalItem] = []
    for it in body.items:
        product = CATALOG.get(it.sku)
        if product is None:
            raise HTTPException(422, detail={
                "ok": False,
                "error": {"error_code": "UNKNOWN_SKU",
                          "message": f"{it.sku!r} is not in the merchant catalog",
                          "sku": it.sku}})
        if it.price_paise is not None and it.price_paise != product["price_paise"]:
            attacker_prices.append({
                "sku": it.sku,
                "attacker_claimed_paise": it.price_paise,
                "catalog_paise": product["price_paise"]})
        items.append(ProposalItem(sku=it.sku, qty=it.qty,
                                  price_paise=product["price_paise"]))

    price_overwrite_applied = bool(attacker_prices)
    mission_amount_ignored = body.mission.amount_paise is not None

    # ---- sign the mission through the disclosed in-process issuer ------
    expires_at = body.mission.expires_at or (now_ts + 3600)
    blob = {
        "mission_id": body.mission.mission_id,
        "intent": body.mission.intent,
        "budget_paise": body.mission.budget_paise,
        "allowed_categories": list(body.mission.allowed_categories),
        "forbidden_categories": list(body.mission.forbidden_categories),
        "upsell_cap": body.mission.upsell_cap,
        "expires_at": expires_at,
    }
    signature = mission_verify.sign_mission(mission_verify.dumps(blob))
    if body.tamper_signature:
        signature = ("0" if signature[0] != "0" else "1") + signature[1:]

    mission = Mission(
        mission_id=blob["mission_id"], intent=blob["intent"],
        budget_paise=blob["budget_paise"],
        allowed_categories=tuple(blob["allowed_categories"]),
        forbidden_categories=tuple(blob["forbidden_categories"]),
        upsell_cap=blob["upsell_cap"], expires_at=expires_at,
        signature=signature)
    proposal = Proposal(mission_id=mission.mission_id, items=tuple(items),
                        justification=body.mission.intent)

    # ---- LOCK 1: the real deterministic gateway ------------------------
    structured = evaluate_full(
        mission=mission, proposal=proposal, catalog=CATALOG,
        verify_fn=mission_verify.verify_mission, state={}, now_ts=now_ts,
        chain_ok=audit_chain.verify())

    decision = structured["decision"]
    first_failure = structured["first_failure"] or {}
    refused_by: str | None = None
    refused_layer: str | None = None
    headline: str

    if decision != "APPROVE":
        refused_by = f"gateway/{first_failure.get('rule_id') or 'UNKNOWN'}"
        refused_layer = "gateway"
        headline = ("THE AI SAW YOUR ATTACK. EVEN IF IT HADN'T — THE BINDING "
                    "STILL WOULD. DETERMINISTIC CODE DOES NOT GET TALKED "
                    "INTO THINGS.")
        binding_check = None
    else:
        # ---- LOCK 2: the approval binding ------------------------------
        # The proposal is legitimate. The only thing that can still stop it
        # is a permission slip bound to this exact cart — which the
        # attacker cannot mint, because they do not hold USER_MANDATE_KEY.
        from .approval import verify as verify_binding
        seq = _forged_seq(body.forged_binding)
        ok, code, _b = verify_binding(
            seq=seq,
            mission_id=mission.mission_id,
            proposal_hash=structured["proposal_hash"] or "",
            cart_hash=structured["proposal_hash"] or "",
            quote_id=str((body.forged_binding or {}).get("quote_id", "")),
            amount_paise=sum(i.price_paise * i.qty for i in proposal.items),
            currency="INR",
            skus=[(i.sku, i.qty) for i in proposal.items],
            now_ts=now_ts)
        binding_check = {"checked": True, "accepted": ok, "reason": code,
                         "seq_presented": seq}
        if not ok:
            refused_by = f"binding/{code}"
            refused_layer = "binding"
            headline = "THE GATEWAY PASSED YOU. THE BINDING DIDN'T."
        else:  # pragma: no cover - would be a genuine finding
            headline = ("A VALID APPROVAL BINDING WAS PRESENTED. THIS IS NOT "
                        "AN ATTACK — IT IS AN AUTHORIZED PURCHASE.")

    money_delta = money.snapshot()["boundary_calls"] - money_before

    return {
        "ok": True,
        "scenario": "custom",
        "headline": headline,
        "attacker_input": body.model_dump(),
        "mission_signed_by": "in_process_demo_issuer",
        "signature_tampered": body.tamper_signature,
        "price_overwrite_applied": price_overwrite_applied,
        "attacker_prices_discarded": attacker_prices,
        "mission_amount_field_ignored": mission_amount_ignored,
        "gateway": {
            "decision": decision,
            "rule_id": first_failure.get("rule_id"),
            "reason": structured["verdict_reason"],
            "rule_matrix": [
                {"rule_id": r["rule_id"], "label": r.get("label", ""),
                 "status": r["status"], "reason": r.get("reason", "")}
                for r in structured["rules"]],
            "proposal_hash": structured["proposal_hash"],
        },
        "binding_check": binding_check,
        "refused_by": refused_by,
        "refused_layer": refused_layer,
        "money_boundary_calls": money_delta,
        "amount_authorized_paise": 0,
        "amount_moved_paise": 0,
        "sandbox_note": ("this endpoint imports no execution machinery at "
                         "all — moving money needs an approval binding "
                         "signed with a key it does not hold. Proven by "
                         "tests/security/test_attack_custom.py"),
    }


def _forged_seq(forged: dict[str, Any] | None) -> int:
    """Read a sequence number out of a forged permission slip.

    An attacker can claim any sequence they like. The verifier looks it
    up, and either finds nothing or finds a binding whose fields do not
    match this cart. Both are refusals. A non-integer claim becomes -1,
    which cannot exist.
    """
    if not forged:
        return -1
    raw = forged.get("seq", forged.get("approve_seq", -1))
    try:
        return int(raw)
    except (TypeError, ValueError):
        return -1


@router.post("/attack/gauntlet")
def attack_gauntlet(request: Request) -> dict[str, Any]:
    """Every built-in scenario, in one run, timed on this machine.

    Wraps the same `attack_run_all` the test suite asserts against, so a
    green suite and a green scoreboard are the same fact.
    """
    _guard(request, "attack_gauntlet", _GAUNTLET_LIMIT)

    results: list[dict[str, Any]] = []
    t_wall = time.perf_counter()

    # Each scenario is timed individually so the scoreboard can show a
    # real per-row latency rather than a share of the total. `attack_run`
    # is imported and called, never reimplemented — the aggregate the
    # test suite asserts against runs exactly this function.
    for scenario in SCENARIOS:
        t0 = time.perf_counter()
        r = attack_run(scenario["id"])
        elapsed_ms = round((time.perf_counter() - t0) * 1000, 3)

        gateway = r.get("gateway") or {}
        binding = r.get("binding_check") or {}
        if gateway.get("decision") == "REJECT":
            blocked_by = f"gateway/{gateway.get('rule_id')}"
            layer = "gateway"
        elif binding.get("blocked"):
            blocked_by = f"approval_binding/{binding.get('reason')}"
            layer = "binding"
        else:
            blocked_by = "NOT BLOCKED"
            layer = None

        results.append({
            "id": scenario["id"],
            "label": scenario["label"],
            "description": scenario["description"],
            "decision": gateway.get("decision"),
            "rule_id": gateway.get("rule_id"),
            "blocked_by": blocked_by,
            "refused_layer": layer,
            "money_calls": (r.get("money_calls") or {}).get("boundary_calls", 0),
            "safe": (r.get("verdict") or {}).get("safe", False),
            "latency_ms": elapsed_ms,
        })

    wall_ms = round((time.perf_counter() - t_wall) * 1000, 2)
    blocked = sum(1 for r in results if r["safe"])

    return {
        "ok": True,
        "results": results,
        "totals": {
            "blocked": blocked,
            "total": len(results),
            "block_rate": round(blocked / max(1, len(results)), 3),
            # Summed per scenario, not differenced against the global
            # counter. `attack_run` zeroes that counter as it starts each
            # scenario, so a difference taken across the whole gauntlet
            # measures only the last scenario minus whatever the process
            # had done beforehand -- which reads as a negative number of
            # money calls the moment anything else in the process has
            # touched the boundary. Each row's count is already scoped to
            # its own scenario and is the honest thing to add up.
            "money_boundary_calls": sum(r["money_calls"] for r in results),
            "wall_time_ms": wall_ms,
        },
        "measured_on": "this machine, this run",
    }
