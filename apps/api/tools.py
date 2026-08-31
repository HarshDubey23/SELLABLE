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

from fastapi import APIRouter, Depends, Header, HTTPException
from pydantic import BaseModel

from . import razorpay_client as rp_client
from .audit import chain
from .deps import require_api_key
from .gateway import mission_verify
from .gateway.engine import evaluate
from .gateway.types import Decision, Mission, Proposal, ProposalItem, Verdict
from .products import CATALOG
from .products import search as catalog_search
from .store import db as store
from .upsell.crosssell import find_cross_sell_candidates
from .upsell.engine import generate_upsell_offers

router = APIRouter()

QUOTE_TTL_SECONDS = 30 * 60  # 30 minutes

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
        "signature FROM quotes"
    ):
        quotes[row["quote_id"]] = {
            "quote_id": row["quote_id"],
            "mission_id": row["mission_id"],
            "items": json.loads(row["items"]),
            "total_paise": row["total_paise"],
            "expires_at": row["expires_at"],
            "signature": row["signature"],
        }

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

    verdict = evaluate(mission=mission, proposal=proposal, catalog=CATALOG,
                       verify_fn=mission_verify.verify_mission,
                       state=state, now_ts=int(time.time()),
                       chain_ok=chain.verify(),
                       protocol_scope=req.protocol_scope)

    seq = chain.append("gateway", "verdict_emitted",
                       {"decision": verdict.decision.value,
                        "rule_id": verdict.rule_id,
                        "proposal_hash": verdict.proposal_hash,
                        "mission_id": mission.mission_id})
    bound = VerdictSeq(seq, verdict)
    verdicts[seq] = bound

    # PERSIST: verdicts and bindings must outlive the process.
    store.execute(
        "INSERT OR REPLACE INTO verdicts "
        "(seq, decision, rule_id, reason, proposal_hash, mission_id, "
        " created_at) VALUES (?, ?, ?, ?, ?, ?, ?)",
        (seq, verdict.decision.value, verdict.rule_id, verdict.reason,
         verdict.proposal_hash, mission.mission_id, int(time.time()))
    )

    if verdict.decision.value == "APPROVE":
        approved_bindings[seq] = verdict.proposal_hash

    return {"ok": True, "seq": seq,
            "data": {"decision": verdict.decision.value,
                     "rule_id": verdict.rule_id,
                     "reason": verdict.reason,
                     "proposal_hash": verdict.proposal_hash}}


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
                            x_idempotency_key: str = Header(default="")):
    """Create a REAL Razorpay order (test mode).

    G1 INVARIANT: requires approve_seq + matching proposal_hash from a
    stored APPROVE verdict. No APPROVE = no order = no money. This is
    the single enforcement point of INV-1 at the executor boundary.
    """
    idem = (x_idempotency_key or "").strip()
    if not idem:
        raise HTTPException(400, detail="X-Idempotency-Key header required")
    if idem in idempotency_seen:
        existing = orders[idempotency_seen[idem]]
        return {"order_id": existing["order_id"],
                "amount_paise": existing["amount_paise"],
                "status": existing["status"], "duplicate": True}

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

    # G1 GATE: No APPROVE binding, no money. EVER.
    # This is INV-1 enforcement — the only path to order creation.
    if approved_bindings.get(req.approve_seq) != req.proposal_hash:
        raise HTTPException(403, detail={
            "ok": False,
            "error": {
                "error_code": "ORDER_HASH_MISMATCH",
                "rule_id": None,
                "message": f"No APPROVE binding at seq {req.approve_seq} "
                           f"matches proposal_hash "
                           f"{req.proposal_hash[:16]}...",
                "retryable": False,
                "hint": "submit_proposal first, get APPROVE, then use its "
                        "seq + proposal_hash here"
            }})

    # INV-3: user-signed intent + cart mandates required before any order.
    from .mandates.mandates import MandateError, verify_cart, verify_intent

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
        verify_intent(intent_blob, order_total_paise=total_paise)
        verify_cart(cart_blob, proposal_hash=req.proposal_hash,
                    amount_paise=total_paise)
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

    # Deterministic idempotency key: same mission + proposal + verdict
    # always derives the same key, so a replay is detectable end-to-end.
    idem_key = rp_client.derive_idempotency_key(
        "create_order", q["mission_id"], req.proposal_hash, req.approve_seq)

    try:
        rp = rp_client.create_order(
            amount_paise=q["total_paise"],   # integer paise
            receipt=f"rcpt_{q['quote_id'][:12]}",
            notes={"quote_id": q["quote_id"],
                   "mission_id": q["mission_id"],
                   "proposal_hash": req.proposal_hash},
            idempotency_key=idem_key,
        )
    except Exception as e:
        raise HTTPException(503, detail={
            "ok": False,
            "error": {"error_code": "RAZORPAY_UNREACHABLE", "rule_id": None,
                      "message": str(e), "retryable": True,
                      "hint": "idempotency key remains reusable"}})

    orders[rp["id"]] = {
        "order_id": rp["id"], "amount_paise": q["total_paise"],
        "quote_id": q["quote_id"], "mission_id": q["mission_id"],
        "proposal_hash": req.proposal_hash, "idempotency_key": idem,
        "status": "created", "created_at": int(time.time()),
    }
    idempotency_seen[idem] = rp["id"]

    # PERSIST: the order (and its idempotency key) hits disk immediately.
    store.execute(
        "INSERT OR REPLACE INTO orders "
        "(order_id, idempotency_key, amount_paise, status, quote_id, "
        " mission_id, proposal_hash, approve_seq, created_at) "
        "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)",
        (rp["id"], idem, q["total_paise"], "created", q["quote_id"],
         q["mission_id"], req.proposal_hash, req.approve_seq, int(time.time()))
    )

    chain.append("executor", "order_created",
                 {"order_id": rp["id"], "amount_paise": q["total_paise"],
                  "mission_id": q["mission_id"]},
                 idempotency_key=idem_key,
                 review_state="auto_approved")

    return {"order_id": rp["id"], "amount_paise": q["total_paise"],
            "amount_display": f"Rs {q['total_paise']/100:,.0f}",
            "currency": "INR", "status": "created",
            "razorpay_key_id": os.environ["RAZORPAY_KEY_ID"],
            "checkout_url": f"/checkout/{rp['id']}"}


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
