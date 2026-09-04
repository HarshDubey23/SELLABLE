"""
Storefront tools — the agent-facing API surface.

Security invariants:
- Prices ALWAYS come from CATALOG (server-side truth). Nothing a client
  sends can change a price. This kills I3/I5 by design.
- create_order REQUIRES an APPROVE binding (approve_seq + proposal_hash).
  No gateway APPROVE = no order = no money. INV-1 enforcement point.
- State is durable: quotes/orders/verdicts live in SQLite and are
  reloaded at boot, so a restart never loses a binding or an order.
`razorpay` is imported ONLY inside razorpay_client (single import boundary).
"""

import hashlib
import hmac
import json
import os
import time
from typing import TYPE_CHECKING

from fastapi import APIRouter, Depends, Header, HTTPException
from pydantic import BaseModel

from . import razorpay_client as rp_client
from .approval import get_legacy_proposal_hash as verify_legacy
from .approval import register as register_binding
from .audit import chain
from .deps import require_api_key
from .gateway import mission_verify
from .gateway.structured import evaluate_full
from .gateway.types import Decision, Mission, Proposal, ProposalItem, Verdict
from .mandates.mandates import (
    MANDATE_VERSION,
    MandateError,
    verify_cart,
    verify_intent,
)
from .products import CATALOG
from .products import search as catalog_search
from .store import db as store
from .upsell.crosssell import find_cross_sell_candidates
from .upsell.engine import generate_upsell_offers

if TYPE_CHECKING:  # settlement is in-process only; no runtime import cycle
    from .market.settle import NegotiatedSettlement

router = APIRouter()

QUOTE_TTL_SECONDS = 30 * 60  # 30 minutes

# Faults a caller may inject at the money boundary, in either provider.
# They model the three things that can happen to a request from the
# client's side: the reply is lost, the request never left, or the
# provider refused. Anything else is rejected rather than silently
# ignored, so a typo in a demo cannot look like a passing drill.
_INJECTABLE_FAULTS = frozenset({"remote_timeout", "remote_lost", "remote_reject"})

quotes = {}            # quote_id -> quote dict
orders = {}            # order_id -> order dict
idempotency_seen = {}  # idempotency_key -> order_id
verdicts = {}          # seq -> VerdictSeq (for explain_reject)
approved_bindings = {} # seq -> proposal_hash (G1: order needs this match)
mission_state = {}     # mission_id -> {"proposal_ts": [...], "mission": {...}}


class VerdictSeq:
    def __init__(self, seq, v):
        self.seq, self.v = seq, v


def _hmac(payload: str) -> str:
    return hmac.new(
        os.environ["MISSION_HMAC_KEY"].encode(),
        payload.encode(), hashlib.sha256
    ).hexdigest()


def _load_persisted_state() -> None:
    """Reload every durable structure from SQLite at boot."""
    global quotes, orders, idempotency_seen, verdicts, approved_bindings

    for row in store.query(
        "SELECT quote_id, mission_id, items, total_paise, expires_at, "
        "signature, negotiated_json FROM quotes"
    ):
        quotes[row["quote_id"]] = {
            "quote_id": row["quote_id"],
            "mission_id": row["mission_id"],
            "items": json.loads(row["items"]),
            "total_paise": row["total_paise"],
            "expires_at": row["expires_at"],
            "signature": row["signature"],
        }
        # A market quote carries the merchant and transcript its binding
        # is pinned to. Losing it on restart would leave a settlement
        # unable to prove itself and stuck at MERCHANT_MISMATCH.
        if row["negotiated_json"]:
            quotes[row["quote_id"]]["negotiated"] = json.loads(
                row["negotiated_json"])

    for row in store.query(
        "SELECT order_id, idempotency_key, amount_paise, status, quote_id, "
        "mission_id, proposal_hash, approve_seq, created_at FROM orders"
    ):
        orders[row["order_id"]] = {
            "order_id": row["order_id"],
            "amount_paise": row["amount_paise"],
            "quote_id": row["quote_id"],
            "mission_id": row["mission_id"],
            "proposal_hash": row["proposal_hash"],
            "idempotency_key": row["idempotency_key"],
            "status": row["status"],
            "created_at": row["created_at"],
        }
        if row["idempotency_key"]:
            idempotency_seen[row["idempotency_key"]] = row["order_id"]

    for row in store.query(
        "SELECT seq, decision, rule_id, reason, proposal_hash, mission_id "
        "FROM verdicts ORDER BY seq"
    ):
        v = Verdict(
            decision=Decision(row["decision"]),
            rule_id=row["rule_id"],
            reason=row["reason"] or "",
            proposal_hash=row["proposal_hash"],
            seq=row["seq"],
        )
        verdicts[row["seq"]] = VerdictSeq(row["seq"], v)
        if row["decision"] == "APPROVE":
            approved_bindings[row["seq"]] = row["proposal_hash"]


_load_persisted_state()


class QuoteReq(BaseModel):
    items: list          # [{"sku": "BAT-001", "qty": 1}]
    mission_id: str


class ProposalReq(BaseModel):
    mission: dict        # signed mission fields incl. signature
    items: list          # [{"sku", "qty"}] — prices filled from CATALOG server-side
    protocol_scope: dict | None = None  # protocol artifacts (Phase 4): bound by R12 at the gateway; native traffic omits it


class CreateOrderReq(BaseModel):
    quote_id: str
    proposal_hash: str
    approve_seq: int  # REQUIRED — no APPROVE binding, no money
    intent_mandate: dict | None = None
    cart_mandate: dict | None = None


@router.get("/tools/search_products")
async def tool_search(query: str | None = None,
                      category: str | None = None,
                      max_price_paise: int | None = None,
                      min_rating: float | None = None,
                      attribute: str | None = None,
                      limit: int = 10):
    results = catalog_search(
        query or "", category, max_price_paise,
        min_rating=min_rating, attribute=attribute,
    )[:limit]
    return {
        "count": len(results),
        "results": [
            {"sku": r["sku"], "name": r["name"], "category": r["category"],
             "price_paise": r["price_paise"],
             "price_display": f"Rs {r['price_paise']/100:,.0f}",
             "rating": r.get("rating"),
             "attributes": r.get("attributes", {}),
             "compatible_with": r.get("compatible_with", []),
             "stock": r.get("stock", 0)}
            for r in results
        ],
    }


@router.get("/tools/get_product/{sku}")
async def tool_get_product(sku: str):
    """Full product detail. Descriptions may contain injection payloads —
    intentional. The gateway is the defense, not the LLM."""
    p = CATALOG.get(sku)
    if not p:
        raise HTTPException(404, detail={
            "ok": False,
            "error": {"error_code": "SKU_NOT_FOUND", "rule_id": None,
                      "message": f"unknown sku {sku}", "retryable": False,
                      "hint": "use /tools/search_products to list valid skus"}})
    return {"sku": sku, **p,
            "price_display": f"Rs {p['price_paise']/100:,.0f}",
            "in_stock": p.get("stock", 0) > 0}


@router.post("/tools/quote", dependencies=[Depends(require_api_key)])
async def tool_quote(req: QuoteReq):
    """Signed price lock, TTL 30 min. Total computed SERVER-SIDE."""
    line_items, total = [], 0

    for it in req.items:
        sku, qty = it.get("sku"), int(it.get("qty", 1))
        p = CATALOG.get(sku)
        if not p:
            raise HTTPException(400, detail=f"unknown sku {sku}")
        if qty < 1 or qty > 10:
            raise HTTPException(400, detail=f"qty for {sku} must be 1-10, got {qty}")
        line = p["price_paise"] * qty
        total += line
        line_items.append({"sku": sku, "name": p["name"], "qty": qty,
                           "unit_price_paise": p["price_paise"],
                           "line_total_paise": line})

    if total <= 0:
        raise HTTPException(400, detail="total must be > 0")

    quote_id = hashlib.sha256(
        f"{req.mission_id}|{time.time_ns()}".encode()).hexdigest()[:16]
    expires_at = int(time.time()) + QUOTE_TTL_SECONDS

    payload = json.dumps({"quote_id": quote_id, "mission_id": req.mission_id,
                          "items": [{"sku": i["sku"], "qty": i["qty"]} for i in line_items],
                          "total_paise": total, "expires_at": expires_at},
                         sort_keys=True)
    sig = _hmac(payload)

    quotes[quote_id] = {"quote_id": quote_id, "mission_id": req.mission_id,
                        "items": line_items, "total_paise": total,
                        "expires_at": expires_at, "signature": sig}

    # PERSIST: survive restarts so APPROVE bindings stay spendable.
    store.execute(
        "INSERT OR REPLACE INTO quotes "
        "(quote_id, mission_id, items, total_paise, expires_at, signature, "
        " created_at) VALUES (?, ?, ?, ?, ?, ?, ?)",
        (quote_id, req.mission_id, json.dumps(line_items), total,
         expires_at, sig, int(time.time()))
    )

    return {"quote_id": quote_id, "items": line_items, "total_paise": total,
            "total_display": f"Rs {total/100:,.0f}",
            "expires_at": expires_at, "signature": sig}


@router.post("/tools/submit_proposal", dependencies=[Depends(require_api_key)])
async def tool_submit_proposal(req: ProposalReq):
    """Gateway evaluate() — the ONLY path an agent has toward money.
    Prices in the proposal are filled from CATALOG here; the client cannot
    inject a price even if it tries."""
    return await evaluate_proposal(req)


async def evaluate_proposal(req: ProposalReq, *,
                            settlement: "NegotiatedSettlement | None" = None):
    """The gateway evaluation, shared by the HTTP route and the market.

    `settlement` is reachable only in-process. The HTTP route never passes
    one, so nothing a client can send changes the amount that gets bound —
    which is the property the price-injection defence rests on. The market
    passes one because its amount is also server-computed, just by the
    merchant policy engine rather than by the catalog directly.

    Rule evaluation is identical either way. A negotiated purchase is
    approved against the same R1-R12 the client path is, on the same
    catalog list prices, and the settlement only ever narrows what the
    resulting binding will authorize.
    """
    m = req.mission or {}
    try:
        mission = Mission(
            mission_id=str(m.get("mission_id", "")),
            intent=str(m.get("intent", "")),
            budget_paise=int(m.get("budget_paise", -1)),
            allowed_categories=tuple(m.get("allowed_categories") or ()),
            forbidden_categories=tuple(m.get("forbidden_categories") or ()),
            upsell_cap=float(m.get("upsell_cap", 1.3)),
            expires_at=int(m.get("expires_at", 0)),
            signature=str(m.get("signature", "")),
        )
    except (TypeError, ValueError) as e:
        raise HTTPException(400, detail={
            "ok": False,
            "error": {"error_code": "MALFORMED_MISSION", "rule_id": None,
                      "message": str(e), "retryable": False,
                      "hint": "check field types"}})

    items = []
    for it in req.items:
        sku = it.get("sku")
        if sku not in CATALOG:
            raise HTTPException(400, detail={
                "ok": False,
                "error": {"error_code": "SKU_NOT_FOUND", "rule_id": None,
                          "message": f"unknown sku {sku}", "retryable": False,
                          "hint": "search_products first"}})
        items.append(ProposalItem(sku=sku, qty=int(it.get("qty", 1)),
                                  price_paise=CATALOG[sku]["price_paise"]))
    proposal = Proposal(mission_id=mission.mission_id, items=tuple(items))

    # R6 contract: state["proposal_ts"] is {mission_id: [ts, ...]}.
    # The signed mission snapshot also rides along so the upsell engine
    # can pre-gate offers against the same bounds the gateway enforces.
    state = mission_state.setdefault(mission.mission_id, {"proposal_ts": {}})
    state["proposal_ts"].setdefault(mission.mission_id, []).append(int(time.time()))
    state["mission"] = {
        "intent": mission.intent,
        "budget_paise": mission.budget_paise,
        "allowed_categories": list(mission.allowed_categories),
        "forbidden_categories": list(mission.forbidden_categories),
        "upsell_cap": mission.upsell_cap,
        "expires_at": mission.expires_at,
        "signature": mission.signature,
    }

    structured = evaluate_full(
        mission=mission, proposal=proposal, catalog=CATALOG,
        verify_fn=mission_verify.verify_mission,
        state=state, now_ts=int(time.time()),
        chain_ok=chain.verify_strict()[0],
        protocol_scope=req.protocol_scope,
    )

    decision_str = structured["decision"]
    first_failure = structured["first_failure"]
    proposal_hash = structured["proposal_hash"]

    seq = chain.append(
        "gateway",
        "verdict_emitted",
        {
            "decision": decision_str,
            "rule_id": first_failure["rule_id"] if first_failure else None,
            "proposal_hash": proposal_hash,
            "mission_id": mission.mission_id,
            "rule_matrix": [
                {"rule_id": r["rule_id"], "status": r["status"],
                 "reason": r["reason"]}
                for r in structured["rules"]
            ],
        },
    )
    bound = VerdictSeq(seq, Verdict(
        decision=Decision(decision_str),
        rule_id=first_failure["rule_id"] if first_failure else None,
        reason=structured["verdict_reason"],
        proposal_hash=proposal_hash,
        seq=seq,
    ))
    verdicts[seq] = bound

    # PERSIST: verdicts and bindings must outlive the process.
    store.execute(
        "INSERT OR REPLACE INTO verdicts "
        "(seq, decision, rule_id, reason, proposal_hash, mission_id, "
        " created_at) VALUES (?, ?, ?, ?, ?, ?, ?)",
        (seq, decision_str,
         first_failure["rule_id"] if first_failure else None,
         structured["verdict_reason"],
         proposal_hash or "", mission.mission_id, int(time.time()))
    )

    # REGISTER APPROVAL BINDING (exact, multi-field) on APPROVE.
    if decision_str == "APPROVE":
        list_total = sum(i.price_paise * i.qty for i in items)
        bind_amount = list_total
        if settlement is not None:
            # THE NEGOTIATION MAY ONLY EVER MOVE THE PRICE DOWN.
            #
            # The gateway has just approved this basket at catalog list
            # price against the shopper's signed budget. Binding a larger
            # amount than that would mean the negotiation layer had
            # authorized a spend the deterministic rules never saw, which
            # is precisely the hole three bargaining language models
            # should not be given.
            #
            # So the ceiling the gateway approved is the ceiling, and a
            # negotiated settlement above it is refused outright rather
            # than trimmed to fit.
            if settlement.amount_paise > list_total:
                raise HTTPException(409, detail={
                    "ok": False,
                    "error": {
                        "error_code": "SETTLEMENT_ABOVE_APPROVED_CEILING",
                        "rule_id": None,
                        "message": (
                            f"negotiated total {settlement.amount_paise} "
                            f"exceeds the approved list ceiling {list_total}"),
                        "retryable": False,
                        "hint": "the negotiation may only lower the price",
                    }})
            bind_amount = settlement.amount_paise

        register_binding(
            seq,
            mission_id=mission.mission_id,
            proposal_hash=proposal_hash or "",
            cart_hash=proposal_hash or "",
            quote_id="",
            amount_paise=bind_amount,
            currency="INR",
            skus=[(i.sku, i.qty) for i in items],
            mandate_version=MANDATE_VERSION,
            merchant_id=settlement.merchant_id if settlement else "",
            negotiation_transcript_hash=(
                settlement.transcript_hash if settlement else ""),
        )
        approved_bindings[seq] = proposal_hash or ""

    return {
        "ok": True,
        "seq": seq,
        "data": {
            "decision": decision_str,
            "rule_id": first_failure["rule_id"] if first_failure else None,
            "reason": structured["verdict_reason"],
            "proposal_hash": proposal_hash,
            "rule_matrix": structured["rules"],
            "effective_budget_paise": structured.get("effective_budget_paise"),
            "merchant_id": structured.get("merchant_id"),
            "policy_version": "sellable-v1.0",
        },
    }


@router.get("/tools/explain_reject")
async def tool_explain_reject(seq: int):
    """Human-readable story of why the verdict at seq was emitted."""
    b = verdicts.get(seq)
    if not b:
        raise HTTPException(404, detail=f"no verdict at seq {seq}")
    v = b.v
    return {"seq": seq, "decision": v.decision.value, "rule_id": v.rule_id,
            "reason": v.reason, "proposal_hash": v.proposal_hash}


@router.get("/policy")
async def policy():
    """Machine-readable rules so agents can self-gate pre-proposal.

    Derived from the canonical RULE_REGISTRY — single source of truth.
    """
    from .gateway.registry import RULE_REGISTRY

    return {"rules_count": len(RULE_REGISTRY), "rules": RULE_REGISTRY}


@router.post("/tools/create_order", dependencies=[Depends(require_api_key)])
async def tool_create_order(req: CreateOrderReq,
                            x_idempotency_key: str = Header(default=""),
                            x_sellable_fault: str = Header(default="")):
    """Cross the money boundary — once, durably, and never ambiguously.

    Order of operations matters more than any single check here:

      1. Look up the durable execution row FIRST. A replay of an intent we
         already executed returns the original order instead of opening a
         second payment.
      2. Only then verify (and atomically consume) the approval binding.
      3. Record REMOTE_ATTEMPTED on disk BEFORE the network call, so a crash
         mid-flight is recoverable as "unknown" rather than lost.
      4. Classify the outcome. A timeout is neither success nor failure —
         it becomes RECONCILIATION_REQUIRED and is resolved against the
         provider's authoritative state.

    G1 INVARIANT (strict): every field of the ApprovalBinding must match
    (mission_id, proposal_hash, cart_hash, quote_id, amount, currency, sku
    set) and the binding must be unconsumed. No binding match = no order.
    """
    from . import execution as ex
    from . import execution_provider as provider_mod
    from .approval import verify as verify_binding

    idem = (x_idempotency_key or "").strip()
    if not idem:
        raise HTTPException(400, detail="X-Idempotency-Key header required")

    q = quotes.get(req.quote_id)
    if not q:
        raise HTTPException(404, detail=f"quote {req.quote_id} not found")
    if time.time() > q["expires_at"]:
        raise HTTPException(409, detail={
            "ok": False,
            "error": {"error_code": "QUOTE_EXPIRED", "rule_id": "R10_EXPIRY",
                      "message": f"quote {req.quote_id} expired",
                      "retryable": True,
                      "hint": "request a fresh quote"}})

    # ---- STEP 1: durable business-level idempotency -------------------
    # The execution id is derived from the authorization itself, so the
    # same authorized intent always lands on the same row no matter what
    # the client sends in its header.
    execution_id = ex.derive_execution_id(
        q["mission_id"], req.proposal_hash, req.approve_seq)
    existing = ex.get(execution_id)

    if existing is not None and existing["state"] == ex.EXECUTED:
        order_id = existing["remote_order_id"] or ""
        known = orders.get(order_id, {})
        return {"order_id": order_id,
                "amount_paise": existing["amount_paise"],
                "amount_display": f"Rs {existing['amount_paise']/100:,.0f}",
                "currency": existing["currency"],
                "status": known.get("status", "created"),
                "execution_id": execution_id,
                "execution_state": ex.EXECUTED,
                "provider": existing["provider"],
                "duplicate": True,
                "checkout_url": f"/checkout/{order_id}"}

    if existing is not None and existing["state"] in (
            ex.REMOTE_ATTEMPTED, ex.RECONCILIATION_REQUIRED):
        # The authorization was already spent on an attempt whose outcome
        # is unknown. Re-attempting could double-charge. Reconcile first.
        raise HTTPException(409, detail={
            "ok": False,
            "error": {
                "error_code": "RECONCILIATION_REQUIRED",
                "rule_id": None,
                "message": ("a previous execution of this authorization has an "
                            "unknown outcome; resolve it before retrying"),
                "retryable": False,
                "execution_id": execution_id,
                "execution_state": existing["state"],
                "hint": f"POST /executions/{execution_id}/reconcile",
            }})

    if existing is not None and existing["state"] == ex.FAILED:
        raise HTTPException(409, detail={
            "ok": False,
            "error": {
                "error_code": "EXECUTION_ALREADY_FAILED",
                "message": "this authorization was consumed by a failed "
                           "execution; a new proposal and approval are required",
                "retryable": False,
                "execution_id": execution_id,
                "remote_error_code": existing["remote_error_code"],
            }})

    resuming = existing is not None  # APPROVED / EXECUTION_PENDING: never dispatched

    # Header-level replay of a *different* authorization still short-circuits.
    if not resuming and idem in idempotency_seen:
        prior = orders[idempotency_seen[idem]]
        return {"order_id": prior["order_id"],
                "amount_paise": prior["amount_paise"],
                "status": prior["status"], "duplicate": True}

    quote_skus = [(item["sku"], int(item["qty"])) for item in q["items"]]

    # A negotiated quote knows which merchant won and over which
    # transcript. Both are read from the server's own quote record, never
    # from the request -- a client cannot mint a quote, so it cannot
    # assert a merchant either. An ordinary quote has neither, and a
    # binding with neither pinned skips the check.
    negotiated = q.get("negotiated") or {}

    # ---- STEP 2: binding gate (atomic single-use consumption) ---------
    if not resuming:
        ok, code, _binding = verify_binding(
            seq=req.approve_seq,
            mission_id=q["mission_id"],
            proposal_hash=req.proposal_hash,
            cart_hash=req.proposal_hash,
            quote_id=req.quote_id,
            amount_paise=q["total_paise"],
            currency="INR",
            skus=quote_skus,
            merchant_id=str(negotiated.get("merchant_id", "")),
            negotiation_transcript_hash=str(
                negotiated.get("transcript_hash", "")),
        )
        if not ok:
            chain.append(
                "executor", "binding_rejected",
                {"mission_id": q["mission_id"],
                 "approve_seq": req.approve_seq,
                 "proposal_hash_prefix": req.proposal_hash[:16] if req.proposal_hash else "",
                 "code": code},
                error_code=code,
                review_state="blocked_binding",
            )
            raise HTTPException(403, detail={
                "ok": False,
                "error": {
                    "error_code": code,
                    "rule_id": None,
                    "message": f"approval binding failed: {code}",
                    "retryable": False,
                    "hint": "binding has expired or changed; re-submit proposal",
                }})

        legacy = verify_legacy(req.approve_seq)
        if legacy != req.proposal_hash:
            raise HTTPException(403, detail={
                "ok": False,
                "error": {"error_code": "ORDER_HASH_MISMATCH",
                          "message": "legacy binding mismatch"}})
    else:
        _binding = None

    # INV-3: user-signed intent + cart mandates required before any order.
    intent_blob = req.intent_mandate
    cart_blob = req.cart_mandate
    total_paise = q["total_paise"]
    if intent_blob is None or cart_blob is None:
        chain.append("executor", "mandate_rejected",
                     {"mission_id": q["mission_id"], "order_blocked": True},
                     error_code="MANDATE_MISSING",
                     review_state="blocked_mandate")
        raise HTTPException(422, detail={
            "error": "MANDATE_REQUIRED", "code": "MANDATE_MISSING",
            "detail": "INV-3: user-signed intent + cart mandates required"})
    try:
        verify_intent(intent_blob, order_total_paise=total_paise,
                      expected_mission_id=q["mission_id"])
        verify_cart(cart_blob, proposal_hash=req.proposal_hash,
                    amount_paise=total_paise,
                    expected_mission_id=q["mission_id"],
                    approval_issued_at=_binding.issued_at if _binding else None)
    except MandateError as exc:
        chain.append("executor", "mandate_rejected",
                     {"mission_id": q["mission_id"], "code": exc.code},
                     error_code=exc.code,
                     review_state="blocked_mandate")
        raise HTTPException(403, detail={
            "error": "MANDATE_REJECTED", "code": exc.code})
    chain.append("executor", "mandate_verified",
                 {"mission_id": q["mission_id"],
                  "cart_hash": req.proposal_hash,
                  "amount_paise": total_paise},
                 review_state="verified")

    # ---- STEP 3: durable execution record ----------------------------
    idem_key = rp_client.derive_idempotency_key(
        "create_order", q["mission_id"], req.proposal_hash, req.approve_seq)
    provider = provider_mod.get_provider()

    row, _created = ex.open_execution(
        mission_id=q["mission_id"], proposal_hash=req.proposal_hash,
        approve_seq=req.approve_seq, quote_id=req.quote_id,
        amount_paise=total_paise, currency="INR",
        idempotency_key=idem_key, provider=provider.name)

    if row["state"] == ex.APPROVED:
        try:
            ex.transition(execution_id, ex.EXECUTION_PENDING)
        except ex.IllegalTransition:
            pass  # another request advanced it first; the claim below decides

    notes = {"quote_id": q["quote_id"],
             "mission_id": q["mission_id"],
             "proposal_hash": req.proposal_hash}
    fault = (x_sellable_fault or "").strip()
    if fault:
        # Fault injection simulates the CLIENT's view of the provider call —
        # a lost response, a reset connection, a definitive refusal. It never
        # fabricates an outcome: every injected fault takes the same code
        # path a genuine one would, so the state machine and reconciler are
        # exercised for real. It is recorded in the audit chain precisely so
        # that a drill can never be mistaken for an organic incident.
        if fault not in _INJECTABLE_FAULTS:
            raise HTTPException(400, detail={
                "ok": False,
                "error": {"error_code": "UNKNOWN_FAULT",
                          "message": f"{fault!r} is not an injectable fault",
                          "injectable": sorted(_INJECTABLE_FAULTS)}})
        notes["_fault"] = fault
        chain.append("executor", "fault_injected",
                     {"execution_id": execution_id, "fault": fault,
                      "provider": provider.name,
                      "note": "deliberate reliability drill, not an incident"},
                     review_state="drill")

    # STEP 4: the attempt is recorded on disk BEFORE it is dispatched.
    # If the process dies on the next line, boot recovery finds this row
    # in REMOTE_ATTEMPTED and moves it to RECONCILIATION_REQUIRED.
    # The REMOTE_ATTEMPTED transition IS the dispatch claim: it is a
    # conditional UPDATE, so exactly one concurrent request can take it.
    # Everyone else learns that an attempt is already in flight and backs
    # off rather than firing a second payment.
    try:
        ex.transition(execution_id, ex.REMOTE_ATTEMPTED)
    except ex.IllegalTransition:
        current = ex.get(execution_id)
        raise HTTPException(409, detail={
            "ok": False,
            "error": {
                "error_code": "EXECUTION_IN_PROGRESS",
                "message": "another request is already executing this "
                           "authorization",
                "execution_id": execution_id,
                "execution_state": current["state"] if current else "UNKNOWN",
                "retryable": False,
            }})
    chain.append("executor", "remote_attempted",
                 {"execution_id": execution_id,
                  "mission_id": q["mission_id"],
                  "amount_paise": total_paise,
                  "provider": provider.name},
                 idempotency_key=idem_key,
                 review_state="in_flight")

    try:
        rp = provider.create_order(
            amount_paise=total_paise,
            receipt=f"rcpt_{q['quote_id'][:12]}",
            notes=notes,
            idempotency_key=idem_key,
        )
    except ex.DefiniteRemoteFailure as exc:
        ex.transition(execution_id, ex.FAILED,
                      remote_error_code=exc.code, last_error=str(exc))
        chain.append("executor", "execution_failed",
                     {"execution_id": execution_id, "code": exc.code},
                     error_code=exc.code, review_state="failed")
        raise HTTPException(502, detail={
            "ok": False,
            "error": {"error_code": "REMOTE_REJECTED",
                      "message": str(exc),
                      "execution_id": execution_id,
                      "execution_state": ex.FAILED,
                      "retryable": False}})
    except ex.AmbiguousRemoteOutcome as exc:
        # Whether the request ever left matters to the reconciler: if it
        # provably did not, an empty authoritative read is conclusive and
        # need not wait out the provider's consistency window.
        ex.transition(execution_id, ex.RECONCILIATION_REQUIRED,
                      remote_error_code=(None if getattr(exc, "dispatched", True)
                                         else ex.NEVER_DISPATCHED),
                      last_error=str(exc))
        chain.append("executor", "execution_ambiguous",
                     {"execution_id": execution_id, "reason": str(exc)},
                     error_code="AMBIGUOUS_REMOTE_OUTCOME",
                     review_state="reconciliation_required")
        raise HTTPException(202, detail={
            "ok": False,
            "error": {
                "error_code": "RECONCILIATION_REQUIRED",
                "message": ("the provider's outcome is unknown; no success or "
                            "failure has been assumed"),
                "detail": str(exc),
                "execution_id": execution_id,
                "execution_state": ex.RECONCILIATION_REQUIRED,
                "retryable": False,
                "hint": f"POST /executions/{execution_id}/reconcile",
            }})

    _persist_order(rp, q, req, idem, total_paise)
    ex.transition(execution_id, ex.EXECUTED, remote_order_id=rp["id"])
    chain.append("executor", "order_created",
                 {"order_id": rp["id"], "amount_paise": total_paise,
                  "mission_id": q["mission_id"],
                  "execution_id": execution_id,
                  "provider": provider.name},
                 idempotency_key=idem_key,
                 review_state="auto_approved")

    return {"order_id": rp["id"], "amount_paise": total_paise,
            "amount_display": f"Rs {total_paise/100:,.0f}",
            "currency": "INR", "status": "created",
            "execution_id": execution_id,
            "execution_state": ex.EXECUTED,
            "provider": provider.name,
            "razorpay_key_id": os.environ.get("RAZORPAY_KEY_ID", ""),
            "checkout_url": f"/checkout/{rp['id']}"}


def _persist_order(rp: dict, q: dict, req: "CreateOrderReq", idem: str,
                   total_paise: int) -> None:
    """Record the order locally. Called only after a definitive success."""
    orders[rp["id"]] = {
        "order_id": rp["id"], "amount_paise": total_paise,
        "quote_id": q["quote_id"], "mission_id": q["mission_id"],
        "proposal_hash": req.proposal_hash, "idempotency_key": idem,
        "status": "created", "created_at": int(time.time()),
    }
    idempotency_seen[idem] = rp["id"]
    store.execute(
        "INSERT OR REPLACE INTO orders "
        "(order_id, idempotency_key, amount_paise, status, quote_id, "
        " mission_id, proposal_hash, approve_seq, created_at) "
        "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)",
        (rp["id"], idem, total_paise, "created", q["quote_id"],
         q["mission_id"], req.proposal_hash, req.approve_seq, int(time.time()))
    )


@router.get("/tools/check_payment/{order_id}")
async def tool_check_payment(order_id: str):
    """Local ledger first, Razorpay API as authority."""
    local = orders.get(order_id)
    if not local:
        raise HTTPException(404, detail=f"order {order_id} not found")
    try:
        rp = rp_client.fetch_order(order_id)
        rp_status, rp_paid = rp.get("status"), rp.get("paid", False)
    except Exception:
        rp_status, rp_paid = "api_error", False
    return {"order_id": order_id,
            "amount_paise": local["amount_paise"],
            "status": rp_status if rp_status != "api_error" else local["status"],
            "local_status": local["status"],
            "razorpay_status": rp_status, "paid": rp_paid}


@router.get("/tools/upsell_offers")
async def tool_upsell_offers(mission_id: str, skus: str):
    """Get PRE-GATED upsell offers for a proposed cart.

    Offers are bounded by the mission's signed upsell_cap — the engine
    never offers anything the gateway would reject. Every offer event
    lands in the audit chain.
    """
    sku_list = [s.strip() for s in skus.split(",") if s.strip()]

    for sku in sku_list:
        if sku not in CATALOG:
            raise HTTPException(400, detail={
                "ok": False,
                "error": {"error_code": "SKU_NOT_FOUND", "rule_id": None,
                          "message": f"unknown sku {sku}", "retryable": False}})

    mission_data = mission_state.get(mission_id, {}).get("mission")
    if not mission_data:
        return {"offers": [], "count": 0,
                "reason": "mission not found or expired"}

    mission = Mission(
        mission_id=mission_id,
        intent=mission_data.get("intent", ""),
        budget_paise=mission_data.get("budget_paise", 0),
        allowed_categories=tuple(mission_data.get("allowed_categories", ())),
        forbidden_categories=tuple(mission_data.get("forbidden_categories", ())),
        upsell_cap=float(mission_data.get("upsell_cap", 1.3)),
        expires_at=int(mission_data.get("expires_at", 0)),
        signature=mission_data.get("signature", ""),
    )

    offers = generate_upsell_offers(sku_list, CATALOG, mission)

    chain.append("merchant_ai", "upsell_offered", {
        "mission_id": mission_id,
        "cart_skus": sku_list,
        "offer_count": len(offers),
        "offers": [
            {"from": o["from_sku"], "to": o["to_sku"],
             "delta_paise": o["delta_paise"]}
            for o in offers
        ],
    })

    return {"offers": offers, "count": len(offers)}


@router.get("/tools/crosssell_offers")
async def tool_crosssell_offers(mission_id: str, skus: str):
    """Get PRE-GATED cross-sell offers based on product compatibility."""
    sku_list = [s.strip() for s in skus.split(",") if s.strip()]

    for sku in sku_list:
        if sku not in CATALOG:
            raise HTTPException(400, detail={
                "ok": False,
                "error": {"error_code": "SKU_NOT_FOUND", "rule_id": None,
                          "message": f"unknown sku {sku}", "retryable": False}})

    mission_data = mission_state.get(mission_id, {}).get("mission")
    if not mission_data:
        return {"offers": [], "count": 0,
                "reason": "mission not found or expired"}

    mission = Mission(
        mission_id=mission_id,
        intent=mission_data.get("intent", ""),
        budget_paise=mission_data.get("budget_paise", 0),
        allowed_categories=tuple(mission_data.get("allowed_categories", ())),
        forbidden_categories=tuple(mission_data.get("forbidden_categories", ())),
        upsell_cap=float(mission_data.get("upsell_cap", 1.3)),
        expires_at=int(mission_data.get("expires_at", 0)),
        signature=mission_data.get("signature", ""),
    )

    offers = find_cross_sell_candidates(sku_list, CATALOG, mission)

    chain.append("merchant_ai", "crosssell_offered", {
        "mission_id": mission_id,
        "cart_skus": sku_list,
        "offer_count": len(offers),
    })

    return {"offers": offers, "count": len(offers)}


@router.post("/tools/scan_copy", dependencies=[Depends(require_api_key)])
async def scan_copy_endpoint(body: dict) -> dict:
    from .guardrails.dark_patterns import scan_copy
    return scan_copy(str(body.get("text", "")))
