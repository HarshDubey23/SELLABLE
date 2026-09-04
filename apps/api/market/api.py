"""HTTP surface for the market. JSON only; the page renders it.

A note on the guard, because it is a deliberate departure. The obvious
choice was to hang these off /tools/* behind require_api_key, which is
where an agent-facing route belongs. But the market is driven from a
page in a browser, and the only way a browser could send that key is if
the server had written it into the HTML -- which would publish the
credential to everyone who can load /judge.

So these follow the rule the storefront checkout already established
here: a browser-facing route that can spend gets a ceiling instead of a
key. No new auth system is introduced; both halves of this are existing
machinery, used the way the rest of the app already uses them.

Every route reports the honest provenance of what it did -- which agent
produced each offer, whether a model or the deterministic fallback wrote
it, and whether the payment was a real test-mode order or a simulation.
"""
from __future__ import annotations

import os
from typing import Any

from fastapi import APIRouter, HTTPException, Request
from pydantic import BaseModel, Field

from .. import ratelimit
from . import merchants as merchants_mod
from . import negotiation as neg
from . import settle as settle_mod

router = APIRouter(prefix="/market", tags=["market"])

# A round calls three language models. The ceiling is per-client and low
# enough that a page cannot spend someone else's provider budget by
# holding down a button, and high enough that a reviewer clicking through
# the whole demo twice never meets it.
_OPEN_LIMIT = 10
_ROUND_LIMIT = 20
_SETTLE_LIMIT = 6


def _guard(request: Request, bucket: str, limit: int) -> None:
    who = request.client.host if request.client else "unknown"
    if not ratelimit.allow(who, bucket=bucket, limit=limit):
        raise HTTPException(429, detail={
            "ok": False,
            "error": {"error_code": "RATE_LIMITED",
                      "message": f"too many {bucket} requests",
                      "retry_after_seconds": ratelimit.retry_after(
                          who, bucket=bucket)}})


def llm_available() -> bool:
    """Is there a usable provider key? Decides the honest mode label."""
    from .agents import llm as llm_mod

    return llm_mod.provider_configured()


class OpenReq(BaseModel):
    mission_text: str = Field(min_length=1, max_length=400)
    use_llm: bool = True


class CounterReq(BaseModel):
    merchant_id: str
    ask: str
    note: str = Field(default="", max_length=200)


class OverrideReq(BaseModel):
    weights: dict[str, int] | None = None
    preset: str = "cheapest"


def _mode() -> dict[str, Any]:
    """The banner every response carries. Never claims more than is true."""
    from .. import execution_provider as provider

    live_llm = llm_available()
    payments = provider.provider_name()
    return {
        "merchants": "llm" if live_llm else "scripted_fallback",
        "merchants_label": ("live LLM merchants" if live_llm
                            else "scripted fallback merchants"),
        "payments": payments,
        "payments_label": ("Razorpay TEST MODE" if payments == "razorpay_test"
                           else "simulated payment"),
        "payments_detail": provider.mode_description(),
    }


def _public(negotiation_id: str) -> dict[str, Any]:
    """Everything the page needs about one negotiation, in one shape."""
    row = neg.get(negotiation_id)
    if row is None:
        raise HTTPException(404, detail=f"unknown negotiation {negotiation_id}")

    import json as _json

    offers = []
    for o in neg.offers_for(negotiation_id):
        provenance = _json.loads(o["provenance_json"])
        offers.append({
            "offer_id": o["offer_id"],
            "merchant_id": o["merchant_id"],
            "round": o["round"],
            "accepted": bool(o["accepted"]),
            "reason": o["reason"],
            "total_paise": o["total_paise"],
            "total_display": (f"Rs {o['total_paise'] / 100:,.2f}"
                              if o["total_paise"] else None),
            "intent": _json.loads(o["intent_json"]),
            "verdict": _json.loads(o["verdict_json"]),
            "agent_source": provenance.get("source"),
            "agent_label": provenance.get("label"),
            "is_llm": bool(provenance.get("is_llm")),
            "model": provenance.get("model"),
            "latency_ms": provenance.get("latency_ms"),
        })

    ranking = None
    if row["state"] in (neg.ROUND_COMPLETE, neg.COUNTER_ISSUED, neg.ACCEPTED):
        try:
            ranking = neg.rank(negotiation_id)
        except neg.IllegalTransition:
            ranking = None

    return {
        "negotiation_id": negotiation_id,
        "state": row["state"],
        "mission_text": row["mission_text"],
        "mission_id": row["mission_id"],
        "budget_paise": row["budget_paise"],
        "budget_display": f"Rs {row['budget_paise'] / 100:,.0f}",
        "basket": _json.loads(row["basket_json"]),
        "weights": _json.loads(row["weights_json"]),
        "planner": _json.loads(row["planner_json"]),
        "current_round": row["current_round"],
        "max_rounds": neg.MAX_ROUNDS,
        "winner_merchant_id": row["winner_merchant_id"],
        "transcript_hash": row["transcript_hash"],
        "override_of": row["override_of"],
        "settled": row["settlement_approve_seq"] is not None,
        "offers": offers,
        "counters": [
            {"merchant_id": c["merchant_id"], "round": c["round"],
             "ask": c["ask"], "note": c["note"]}
            for c in neg.counters_for(negotiation_id)],
        "ranking": ranking,
        "mode": _mode(),
    }


@router.get("/merchants")
async def market_merchants() -> dict[str, Any]:
    """The three capability manifests, as the merchants themselves see them."""
    merchants_mod.seed()
    mode = _mode()
    return {"ok": True, "mode": mode,
            "merchants": [merchants_mod.public_view(m,
                                                    mode=mode["merchants"])
                          for m in merchants_mod.all_manifests()]}


@router.post("/open")
async def market_open(req: OpenReq, request: Request) -> dict[str, Any]:
    _guard(request, "market_open", _OPEN_LIMIT)
    allow = req.use_llm and llm_available()
    try:
        row = await neg.open_negotiation(mission_text=req.mission_text,
                                         allow_llm=allow)
    except ValueError as exc:
        # An honest refusal, not an error. The catalog cannot serve this.
        raise HTTPException(422, detail={
            "ok": False,
            "error": {"error_code": "NO_CATALOG_MATCH",
                      "message": str(exc),
                      "hint": "SELLABLE only sells what it stocks"}}) from exc
    return {"ok": True, **_public(row["negotiation_id"])}


@router.post("/{negotiation_id}/round")
async def market_round(negotiation_id: str, request: Request,
                       use_llm: bool = True) -> dict[str, Any]:
    _guard(request, "market_round", _ROUND_LIMIT)
    try:
        await neg.run_round(negotiation_id,
                            allow_llm=use_llm and llm_available())
    except neg.IllegalTransition as exc:
        raise HTTPException(409, detail={
            "ok": False,
            "error": {"error_code": "ILLEGAL_TRANSITION",
                      "message": str(exc)}}) from exc
    return {"ok": True, **_public(negotiation_id)}


@router.post("/{negotiation_id}/counter")
async def market_counter(negotiation_id: str, req: CounterReq,
                         request: Request) -> dict[str, Any]:
    _guard(request, "market_round", _ROUND_LIMIT)
    try:
        neg.issue_counter(negotiation_id, merchant_id=req.merchant_id,
                          ask=req.ask, note=req.note)  # type: ignore[arg-type]
    except (neg.IllegalTransition, ValueError) as exc:
        raise HTTPException(409, detail={
            "ok": False,
            "error": {"error_code": "COUNTER_REFUSED",
                      "message": str(exc)}}) from exc
    return {"ok": True, **_public(negotiation_id)}


@router.get("/{negotiation_id}")
async def market_get(negotiation_id: str) -> dict[str, Any]:
    return {"ok": True, **_public(negotiation_id)}


@router.post("/{negotiation_id}/accept")
async def market_accept(negotiation_id: str,
                        request: Request) -> dict[str, Any]:
    _guard(request, "market_round", _ROUND_LIMIT)
    try:
        neg.claim_winner(negotiation_id)
    except neg.IllegalTransition as exc:
        raise HTTPException(409, detail={
            "ok": False,
            "error": {"error_code": "ACCEPT_REFUSED",
                      "message": str(exc)}}) from exc
    return {"ok": True, **_public(negotiation_id)}


@router.post("/{negotiation_id}/settle")
async def market_settle(negotiation_id: str,
                        request: Request) -> dict[str, Any]:
    """Cross the money boundary. Rate-limited because it spends."""
    _guard(request, "market_settle", _SETTLE_LIMIT)
    try:
        out = await settle_mod.settle(negotiation_id)
    except settle_mod.SettlementRefused as exc:
        raise HTTPException(409, detail={
            "ok": False,
            "error": {"error_code": exc.code, "message": exc.message,
                      **exc.detail}}) from exc
    return {"ok": True, "settlement": out, **_public(negotiation_id)}


@router.post("/{negotiation_id}/override")
async def market_override(negotiation_id: str, req: OverrideReq,
                          request: Request) -> dict[str, Any]:
    """Re-run the same mission under different priorities.

    A fresh negotiation, never a mutation of the old one. The original
    stays exactly as it was decided, which is what lets the two be put
    side by side as evidence.
    """
    _guard(request, "market_open", _OPEN_LIMIT)
    from .agents.buyer import CHEAPEST_WEIGHTS, DEFAULT_WEIGHTS

    original = neg.get(negotiation_id)
    if original is None:
        raise HTTPException(404, detail=f"unknown negotiation {negotiation_id}")

    weights = req.weights or (dict(CHEAPEST_WEIGHTS)
                              if req.preset == "cheapest"
                              else dict(DEFAULT_WEIGHTS))
    row = await neg.open_negotiation(
        mission_text=original["mission_text"],
        allow_llm=llm_available(),
        weights_override=weights, override_of=negotiation_id)
    nid = row["negotiation_id"]
    await neg.run_round(nid, allow_llm=llm_available())
    return {"ok": True, "override_of": negotiation_id, **_public(nid)}


@router.get("")
async def market_index() -> dict[str, Any]:
    """State counts, for the boot banner and the cockpit header."""
    return {"ok": True, "states": neg.summary(), "mode": _mode(),
            "public_base_url": os.environ.get("PUBLIC_BASE_URL", "")}
