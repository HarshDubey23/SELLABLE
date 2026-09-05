"""Product discovery and the storefront checkout. JSON only.

Search queries live retail sources and returns what they actually said,
with provenance attached. Checkout runs the canonical money path — quote,
gateway, approval binding, execution state machine — and reports every
outcome in one envelope so a client cannot mistake an unknown result for
a successful one.

The discovery studio page that used to live here was retired when the
product collapsed to three surfaces; `/discovery` now redirects to the
storefront.
"""
from __future__ import annotations

import time
import uuid
from typing import Any

from fastapi import APIRouter, HTTPException, Request
from fastapi.responses import JSONResponse
from pydantic import BaseModel, Field

from .. import config as app_config
from ..audit import chain as audit_chain
from ..products import CATALOG
from ..store import db as store
from .pipeline import DiscoveryPipelineResult, run_real_product_discovery

router = APIRouter(prefix="/discovery", tags=["discovery"])


class DiscoverySearchReq(BaseModel):
    query: str = Field("bluetooth wireless headphones under 5000", description="User search query")
    budget_paise: int = Field(500000, gt=0, description="Spending limit in paise")


class DiscoveryCheckoutReq(BaseModel):
    sku: str = Field("EAR-001", description="Merchant SKU to buy")
    budget_paise: int = Field(500000, gt=0, description="Signed mandate budget ceiling")
    # Accepted for readability of client payloads and IGNORED by the server:
    # the amount and category always come from the catalog.
    product_name: str = Field("", description="ignored; server uses the catalog")
    amount_paise: int = Field(1, description="ignored; server uses the catalog price")
    category: str = Field("", description="ignored; server uses the catalog category")
    fault: str = Field("", description="simulated-provider fault injection only")


class DiscoveryConfirmReq(BaseModel):
    order_id: str
    payment_id: str | None = None


# The four outcomes a storefront checkout can have. Every one of them is
# reported in the same shape, so a client cannot accidentally read one as
# another. `execution_state` is None only when no execution row was ever
# opened — i.e. the policy gateway refused before the money path began.
_OUTCOME_HEADLINE = {
    "POLICY_GATEWAY_REJECT": "The deterministic policy gateway refused this "
                             "proposal. No authorization was issued and no "
                             "payment provider was contacted.",
    "MANDATE_REJECTED": "The signed user mandate did not authorize this cart. "
                        "No payment provider was contacted.",
    "RECONCILIATION_REQUIRED": "The payment provider was contacted but its "
                               "outcome is unknown. SELLABLE will not claim "
                               "success or failure, and will not retry blind.",
    "REMOTE_REJECTED": "The payment provider definitively refused. No money "
                       "moved.",
    "EXECUTION_IN_PROGRESS": "This authorization is already being executed. A "
                             "second payment attempt is refused by design.",
}


def _as_error(detail: Any) -> dict[str, Any]:
    """Normalise the two refusal shapes this system raises into one.

    Most refusals carry a nested dict: {"error": {"error_code": ...,
    "message": ...}}. The mandate verifier carries a flat one, where
    "error" is a plain string and the code lives beside it:
    {"error": "MANDATE_REJECTED", "code": "MANDATE_CART_STALE"}.

    This function exists because the envelope assumed the first shape and
    called .get() on the second, so every mandate rejection reaching
    /discovery/checkout raised AttributeError instead of returning a
    refusal -- the refusal path itself crashed, which is the one path that
    must not. A caller then saw a 500 where it should have seen a clean,
    machine-readable no.
    """
    if not isinstance(detail, dict):
        return {"message": str(detail)} if detail else {}

    inner = detail.get("error")
    if isinstance(inner, dict):
        return inner
    if isinstance(inner, str):
        # The flat shape. The human-readable label is in "error" and the
        # machine-readable code is in "code".
        return {"error_code": str(detail.get("code") or inner),
                "message": str(detail.get("detail") or inner)}
    return {k: v for k, v in detail.items() if k != "error"}


def _outcome_envelope(detail: Any, *, mission_id: str, sku: str,
                      product_name: str, amount_paise: int,
                      proposal_hash: str, approve_seq: int,
                      money_calls_before: int) -> dict[str, Any]:
    """Flatten an executor/gateway refusal into the one checkout envelope.

    `money_boundary_calls_during_request` is a delta, not the process-wide
    counter. "Zero Razorpay calls happened while handling THIS refusal" is
    a claim that stays true after a successful purchase; "the process has
    made zero calls" stops being true the moment anyone buys anything.
    """
    from .. import money as money_mod

    err = _as_error(detail)
    code = str(err.get("error_code") or "CHECKOUT_REFUSED")
    return {
        "ok": False,
        "status": code,
        "headline": _OUTCOME_HEADLINE.get(code, str(err.get("message") or code)),
        "message": err.get("message"),
        "detail": err.get("detail"),
        "rule_id": err.get("rule_id"),
        "rule_matrix": err.get("rule_matrix"),
        "execution_id": err.get("execution_id"),
        # Always present at the top level. A client never has to dig for it.
        "execution_state": err.get("execution_state"),
        "reconcile_hint": err.get("hint"),
        "retryable": err.get("retryable", False),
        "mission_id": mission_id,
        "sku": sku,
        "product_name": product_name,
        "amount_paise": amount_paise,
        "amount_inr": amount_paise / 100.0,
        "proposal_hash": proposal_hash,
        "approve_seq": approve_seq,
        "priced_from": "server-side merchant catalog",
        "money_boundary_calls_during_request": (
            money_mod.snapshot().get("boundary_calls", 0) - money_calls_before),
        "audit_head_hash": audit_chain._head_hash(),
    }


@router.post("/search", response_model=DiscoveryPipelineResult)
async def api_search_products(req: DiscoverySearchReq) -> DiscoveryPipelineResult:
    """Execute multi-merchant product discovery, price extraction, comparison, and policy check."""
    return run_real_product_discovery(
        query=req.query,
        budget_paise=req.budget_paise,
    )


@router.post("/checkout")
async def api_discovery_checkout(req: DiscoveryCheckoutReq,
                                 request: Request) -> dict[str, Any]:
    """Buy the merchant SKU — through the SAME executor the API path uses.

    This route used to be a second money path: it signed its own mission,
    registered a binding it never verified, called razorpay_client
    directly, and on failure invented an order id and reported success.
    That is exactly the "demo architecture vs real architecture" split a
    reviewer should assume is there until proven otherwise.

    It is now an orchestration over the canonical steps and nothing else:

        issuer.issue_mission
          -> tools.tool_quote            (server-side pricing)
          -> tools.tool_submit_proposal  (gateway R1-R12 + approval binding)
          -> issuer.issue_mandates       (user wallet stand-in)
          -> tools.tool_create_order     (binding verify + execution machine)

    If any step rejects, this route surfaces that rejection. It never
    manufactures an order id and never reports a payment that did not
    happen.
    """
    from .. import issuer, ratelimit
    from .. import money as money_mod
    from .. import tools as tools_mod

    # This is the customer's checkout, so it has no API key — that is right
    # for a storefront. It does create a real Razorpay test order when
    # credentials are configured, so it gets a ceiling instead: an
    # unauthenticated route that spends is a route that needs one.
    who = request.client.host if request.client else "unknown"
    if not ratelimit.allow(who, bucket="storefront_checkout", limit=12):
        raise HTTPException(429, detail={
            "ok": False,
            "error": {"error_code": "RATE_LIMITED",
                      "message": "too many checkouts from this client",
                      "retry_after_seconds": ratelimit.retry_after(
                          who, bucket="storefront_checkout")}})

    now_ts = int(time.time())
    mission_id = f"msn_disc_{now_ts}_{uuid.uuid4().hex[:8]}"
    # Baseline for the per-request money-call delta reported on refusal.
    money_before = money_mod.snapshot().get("boundary_calls", 0)

    if req.sku not in CATALOG:
        raise HTTPException(400, detail={
            "ok": False,
            "error": {"error_code": "SKU_NOT_FOUND",
                      "message": f"{req.sku} is not in the merchant catalog; "
                                 f"SELLABLE can only sell what it stocks"}})

    catalog_item = CATALOG[req.sku]
    category = catalog_item["category"]

    # The amount is ALWAYS the server-side catalog price. Whatever the
    # client (or a web listing, or an LLM) claimed is discarded; the quote
    # below re-derives it from the catalog.

    mission = issuer.issue_mission(
        mission_id=mission_id,
        intent=f"buy {catalog_item['name']} within Rs {req.budget_paise // 100}",
        allowed_categories=(category,),
        budget_paise=req.budget_paise,
        upsell_cap=1.0,
        now_ts=now_ts,
    )

    quote = await tools_mod.tool_quote(tools_mod.QuoteReq(
        items=[{"sku": req.sku, "qty": 1}], mission_id=mission_id))

    proposal = await tools_mod.tool_submit_proposal(tools_mod.ProposalReq(
        mission={k: v for k, v in mission.items() if k != "issued_by"},
        items=[{"sku": req.sku, "qty": 1}]))

    verdict = proposal["data"]
    if verdict["decision"] != "APPROVE":
        # Refused before any authorization existed, so there is no execution
        # row and no provider was contacted. Same envelope as every other
        # outcome; `execution_state` is null and `money_calls` proves it.
        return JSONResponse(
            status_code=422,
            content=_outcome_envelope(
                {"error": {"error_code": "POLICY_GATEWAY_REJECT",
                           "rule_id": verdict["rule_id"],
                           "message": verdict["reason"],
                           "rule_matrix": verdict["rule_matrix"]}},
                mission_id=mission_id, sku=req.sku,
                product_name=str(catalog_item["name"]),
                amount_paise=int(quote["total_paise"]),
                proposal_hash=str(verdict["proposal_hash"]),
                approve_seq=int(proposal["seq"]),
                money_calls_before=money_before,
            ),
        )

    # STAMPED WHEN SIGNED, NOT WHEN THE REQUEST STARTED.
    #
    # now_ts was read at the top of this function, before issuing the
    # mission, quoting, and running the whole gateway -- and the approval
    # binding is registered inside that last step, with its own clock
    # read. Passing the older stamp here meant the cart mandate could
    # claim to be signed seconds before the approval it authorizes, and
    # the executor's staleness check (correctly) refused it as
    # MANDATE_CART_STALE. On a fast machine the gap was under the one
    # second of tolerance and nothing showed; on a loaded CI runner it
    # was not, and the same commit passed on one branch and failed on
    # another. Nothing was stale -- the clock was just read too early.
    intent_blob, cart_blob = issuer.issue_mandates(
        mission_id=mission_id,
        proposal_hash=verdict["proposal_hash"],
        amount_paise=quote["total_paise"],
        ceiling_paise=req.budget_paise,
    )

    try:
        order = await tools_mod.tool_create_order(
            tools_mod.CreateOrderReq(
                quote_id=quote["quote_id"],
                proposal_hash=verdict["proposal_hash"],
                approve_seq=proposal["seq"],
                intent_mandate=intent_blob,
                cart_mandate=cart_blob,
            ),
            x_idempotency_key=f"disc_{mission_id}",
            x_sellable_fault=req.fault or "",
        )
    except HTTPException as exc:
        # The executor signals a non-success outcome by raising, and one of
        # those outcomes is NOT an error in the HTTP sense: 202 means "the
        # provider's outcome is unknown". A browser client that only checks
        # `response.ok` reads a 202 as success and tells the buyer their
        # payment went through — which is the exact lie this whole system
        # exists to prevent. So every outcome, success or not, is returned
        # in ONE envelope whose `ok` and `execution_state` are top-level.
        return JSONResponse(
            status_code=exc.status_code,
            content=_outcome_envelope(
                exc.detail, mission_id=mission_id, sku=req.sku,
                product_name=str(catalog_item["name"]),
                amount_paise=int(quote["total_paise"]),
                proposal_hash=str(verdict["proposal_hash"]),
                approve_seq=int(proposal["seq"]),
                money_calls_before=money_before,
            ),
        )

    return {
        "ok": True,
        "status": "ORDER_CREATED_AWAITING_PAYMENT",
        "authorization_issued_by": issuer.ISSUER_LABEL,
        "mission_id": mission_id,
        "sku": req.sku,
        "product_name": catalog_item["name"],
        "amount_paise": order["amount_paise"],
        "amount_inr": order["amount_paise"] / 100.0,
        "currency": "INR",
        "priced_from": "server-side merchant catalog",
        "order_id": order["order_id"],
        "execution_id": order["execution_id"],
        "execution_state": order["execution_state"],
        "provider": order["provider"],
        "proposal_hash": verdict["proposal_hash"],
        "approve_seq": proposal["seq"],
        "gateway_decision": verdict["decision"],
        "policy_version": verdict["policy_version"],
        "audit_head_hash": audit_chain._head_hash(),
        "razorpay_key_id": app_config.get().razorpay_key_id,
    }


@router.post("/reconcile/{execution_id}")
async def api_discovery_reconcile(execution_id: str) -> dict[str, Any]:
    """Storefront-side recovery action, delegating to the one reconciler.

    Same code path as POST /executions/{id}/reconcile — this exists only
    because that endpoint sits behind the agent API key, and recovery on
    the storefront is a customer-facing action rather than an agent one.
    There is no second reconciliation implementation.
    """
    from ..execution_api import reconcile

    try:
        return reconcile(execution_id)
    except HTTPException as exc:
        # Same trap as checkout: the reconciler signals "I still cannot
        # tell" with a 202, and 202 is a 2xx. Flatten it so `state` is
        # always top-level and a client checking `response.ok` cannot read
        # an unresolved outcome as a resolved one.
        err = _as_error(exc.detail)
        return JSONResponse(status_code=exc.status_code, content={
            "ok": False,
            "execution_id": execution_id,
            "state": err.get("execution_state"),
            "resolution": err.get("error_code", "RECONCILE_FAILED"),
            "explanation": err.get("message") or str(exc.detail),
            "retryable": err.get("retryable", False),
            "retry_after_seconds": err.get("retry_after_seconds"),
        })


@router.get("/payment-status/{order_id}")
async def api_discovery_payment_status(order_id: str) -> dict[str, Any]:
    """Report what is actually known about a payment. Nothing is asserted.

    This replaces a route that accepted a payment_id from the caller and
    wrote a `captured` entry into the audit chain — manufacturing a
    settlement that no payment system had confirmed. Settlement facts come
    from one of exactly two places: a signature-verified webhook, or an
    authoritative read from the provider.
    """
    from ..webhook.receiver import payment_ledger

    order = store.query_one("SELECT * FROM orders WHERE order_id = ?", (order_id,))
    if order is None:
        raise HTTPException(404, detail=f"unknown order {order_id}")

    exec_row = store.query_one(
        "SELECT * FROM payment_executions WHERE remote_order_id = ?", (order_id,))
    ledger_entry = payment_ledger.get(order_id)

    if ledger_entry and ledger_entry.get("status") == "captured":
        settlement = "CAPTURED_CONFIRMED_BY_SIGNED_WEBHOOK"
    elif ledger_entry:
        settlement = f"WEBHOOK_REPORTED_{ledger_entry['status'].upper()}"
    else:
        settlement = "NO_SETTLEMENT_EVENT_RECEIVED"

    return {
        "order_id": order_id,
        "amount_paise": order["amount_paise"],
        "local_order_status": order["status"],
        "execution_state": exec_row["state"] if exec_row else None,
        "execution_id": exec_row["execution_id"] if exec_row else None,
        "provider": exec_row["provider"] if exec_row else None,
        "settlement": settlement,
        "webhook_events": (ledger_entry or {}).get("events", []),
        "note": ("settlement is reported only from signature-verified webhook "
                 "events or an authoritative provider read; this endpoint "
                 "never asserts a payment on its own"),
    }
