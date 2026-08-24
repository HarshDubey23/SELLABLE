"""
Storefront tools — the agent-facing API surface.

Security invariant: prices ALWAYS come from CATALOG (server-side truth).
Nothing a client sends can change a price. This kills I3/I5 by design.
`razorpay` is imported ONLY inside razorpay_client (single import boundary).
"""

from fastapi import APIRouter, HTTPException, Header
from pydantic import BaseModel
from typing import Optional
import hashlib, hmac, json, os, time

from .products import CATALOG, search as catalog_search
from . import razorpay_client as rp_client
from .gateway.engine import evaluate
from .gateway.types import Mission, Proposal, ProposalItem
from .gateway import mission_verify
from .audit import chain

router = APIRouter()

QUOTE_TTL_SECONDS = 30 * 60  # 30 minutes

quotes = {}            # quote_id -> quote dict
orders = {}            # order_id -> order dict
idempotency_seen = {}  # idempotency_key -> order_id
verdicts = {}          # seq -> verdict dict (for explain_reject)
approved_bindings = {} # seq -> proposal_hash (G1: order needs this match)
mission_state = {}     # mission_id -> {"proposal_ts": [...]}


def _hmac(payload: str) -> str:
    return hmac.new(
        os.environ["MISSION_HMAC_KEY"].encode(),
        payload.encode(), hashlib.sha256
    ).hexdigest()


class QuoteReq(BaseModel):
    items: list          # [{"sku": "BAT-001", "qty": 1}]
    mission_id: str


class ProposalReq(BaseModel):
    mission: dict        # signed mission fields incl. signature
    items: list          # [{"sku", "qty"}] — prices filled from CATALOG server-side


class CreateOrderReq(BaseModel):
    quote_id: str
    proposal_hash: str
    # Day 2: gateway not built yet. Day 3 makes approve_seq required.
    approve_seq: Optional[int] = None


class VerdictSeq:
    def __init__(self, seq, v):
        self.seq, self.v = seq, v


@router.get("/tools/search_products")
async def tool_search(query: Optional[str] = None,
                      category: Optional[str] = None,
                      max_price_paise: Optional[int] = None,
                      limit: int = 10):
    results = catalog_search(query or "", category, max_price_paise)[:limit]
    return {
        "count": len(results),
        "results": [
            {"sku": r["sku"], "name": r["name"], "category": r["category"],
             "price_paise": r["price_paise"],
             "price_display": f"Rs {r['price_paise']/100:,.0f}"}
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
            "in_stock": True}


@router.post("/tools/quote")
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
                        "expires_at": expires_at, "signature": sig,
                        "signed_payload": payload}

    return {"quote_id": quote_id, "items": line_items, "total_paise": total,
            "total_display": f"Rs {total/100:,.0f}",
            "expires_at": expires_at, "signature": sig}


@router.post("/tools/submit_proposal")
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

    # R6 contract: state["proposal_ts"] is {mission_id: [ts, ...]}
    state = mission_state.setdefault(
        mission.mission_id, {"proposal_ts": {}})
    state["proposal_ts"].setdefault(mission.mission_id, []).append(int(time.time()))

    verdict = evaluate(mission=mission, proposal=proposal, catalog=CATALOG,
                       verify_fn=mission_verify.verify_mission,
                       state=state, now_ts=int(time.time()),
                       chain_ok=chain.verify())

    seq = chain.append("gateway", "verdict_emitted",
                       {"decision": verdict.decision.value,
                        "rule_id": verdict.rule_id,
                        "proposal_hash": verdict.proposal_hash,
                        "mission_id": mission.mission_id})
    bound = VerdictSeq(seq, verdict)
    verdicts[seq] = bound

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
    """Machine-readable rules so agents can self-gate pre-proposal."""
    return {"rules_count": 10, "rules": [
        {"rule_id": "R9_SIGNATURE", "phase": 0, "severity": "FATAL",
         "check_description": "mission HMAC must verify"},
        {"rule_id": "R10_EXPIRY", "phase": 0, "severity": "FATAL",
         "check_description": "now < expires_at (== rejects)"},
        {"rule_id": "R8_ABORT", "phase": 1, "severity": "FATAL",
         "check_description": "mission not aborted"},
        {"rule_id": "R1_BUDGET", "phase": 2, "severity": "REVISABLE",
         "check_description": "catalog-priced total <= budget_paise"},
        {"rule_id": "R2_FORBIDDEN", "phase": 2, "severity": "REVISABLE",
         "check_description": "no forbidden-category items"},
        {"rule_id": "R5_SCOPE", "phase": 2, "severity": "REVISABLE",
         "check_description": "items within allowed_categories"},
        {"rule_id": "R4_UPSELL_CAP", "phase": 2, "severity": "REVISABLE",
         "check_description": "total <= budget * upsell_cap"},
        {"rule_id": "R3_PRICE_DRIFT", "phase": 3, "severity": "FATAL",
         "check_description": "claimed price == catalog price (+-0 paise)"},
        {"rule_id": "R7_ALLOWLIST", "phase": 3, "severity": "FATAL",
         "check_description": "merchant allowlisted"},
        {"rule_id": "R6_RATE_LIMIT", "phase": 3, "severity": "FATAL",
         "check_description": "<=5 proposals per 60s per mission"},
    ]}


@router.post("/tools/create_order")
async def tool_create_order(req: CreateOrderReq,
                            x_idempotency_key: str = Header(default="")):
    """Create a REAL Razorpay order (test mode).

    G1: requires approve_seq + matching proposal_hash from a stored APPROVE.
    Day 3 adds: full mission replay at the executor boundary.
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

    # G1 gate: no APPROVE binding, no money
    # Day 2: gateway not built yet. Day 3 makes approve_seq required.
    if req.approve_seq is not None:
        if approved_bindings.get(req.approve_seq) != req.proposal_hash:
            raise HTTPException(403, detail={
                "ok": False,
                "error": {"error_code": "ORDER_HASH_MISMATCH",
                          "rule_id": None,
                          "message": f"no APPROVE binding at seq {req.approve_seq} "
                                     f"matches proposal_hash",
                          "retryable": False,
                          "hint": "submit_proposal first and use its seq+hash"}})

    try:
        rp = rp_client.create_order(
            amount_paise=q["total_paise"],   # integer paise
            receipt=f"rcpt_{q['quote_id'][:12]}",
            notes={"quote_id": q["quote_id"],
                   "mission_id": q["mission_id"],
                   "proposal_hash": req.proposal_hash},
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
    chain.append("executor", "order_created",
                 {"order_id": rp["id"], "amount_paise": q["total_paise"]})

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
