#!/usr/bin/env python3
"""SELLABLE MCP server: an AI shopping agent that structurally cannot spend your money.

The agent gets catalog tools plus two money tools, and neither one takes a price or a payee:

    propose_purchase(mission_id, items=[{sku, qty}])  ->  the deterministic gateway (R1-R12)
                                                         decides; APPROVE mints a single-use
                                                         approval bound to the proposal hash
    place_order(approval_id)                          ->  executes only that approved basket,
                                                         at catalog prices, once

Budgets and allowed categories come from missions the *user* signs on the command line
(`sellable-mcp mission new ...`). No tool can create a mission, raise a budget or read the
signing key, so a prompt-injected agent has no way to express "pay more" or "pay someone else".

Transport: MCP over stdio (JSON-RPC 2.0, newline-delimited), standard library only.
Payments are executed by a simulated provider and recorded locally; nothing is charged.
"""
from __future__ import annotations

import json
import secrets
import sys
import time
from pathlib import Path
from typing import Any

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from apps.api.gateway import engine  # noqa: E402
from apps.api.gateway.types import Decision, Proposal, ProposalItem  # noqa: E402
from apps.api.products import CATALOG  # noqa: E402

from mcp_server import store  # noqa: E402

SUPPORTED_VERSIONS = ("2025-06-18", "2025-03-26", "2024-11-05")
SERVER_INFO = {"name": "sellable", "version": "2.0.0"}
APPROVAL_TTL_S = 600
MERCHANT = "SELLABLE-DEMO"

INSTRUCTIONS = (
    "SELLABLE lets you shop for the user inside a mission they signed. Call list_missions "
    "first, search the catalog, then propose_purchase. If the gateway approves, call "
    "place_order with the approval_id. You cannot set prices, payees or budgets: amounts come "
    "from the server-side catalog and limits from the user's signed mission. If a proposal is "
    "rejected, read the rule_id and hint and adjust the basket; don't try to work around it."
)

_ITEMS_SCHEMA = {"type": "array", "minItems": 1, "maxItems": 20,
                 "items": {"type": "object", "additionalProperties": False,
                           "properties": {"sku": {"type": "string"},
                                          "qty": {"type": "integer", "minimum": 1, "maximum": 50}},
                           "required": ["sku", "qty"]}}

TOOLS: list[dict[str, Any]] = [
    {"name": "search_catalog",
     "description": "Search products by text, optionally filtered by category and maximum price "
                    "in rupees. Prices are server-side and authoritative.",
     "annotations": {"readOnlyHint": True},
     "inputSchema": {"type": "object", "properties": {
         "query": {"type": "string", "description": "free text; empty lists top-rated"},
         "category": {"type": "string"},
         "max_price_inr": {"type": "number"},
         "max_results": {"type": "integer", "minimum": 1, "maximum": 25, "default": 8}}}},
    {"name": "get_product",
     "description": "Full record for one SKU: price, attributes, compatibility, policies, stock.",
     "annotations": {"readOnlyHint": True},
     "inputSchema": {"type": "object", "properties": {"sku": {"type": "string"}},
                     "required": ["sku"]}},
    {"name": "list_categories",
     "description": "All product categories with item counts.",
     "annotations": {"readOnlyHint": True},
     "inputSchema": {"type": "object", "properties": {}}},
    {"name": "list_missions",
     "description": "Missions the user has signed: intent, budget, remaining budget, allowed and "
                    "forbidden categories, expiry. You can only buy inside one of these.",
     "annotations": {"readOnlyHint": True},
     "inputSchema": {"type": "object", "properties": {}}},
    {"name": "propose_purchase",
     "description": "Ask the deterministic gateway to approve a basket for a mission. You send "
                    "only SKUs and quantities. On APPROVE you get a single-use approval_id valid "
                    "for 10 minutes; on REJECT you get the rule that refused it and a hint.",
     "inputSchema": {"type": "object", "additionalProperties": False, "properties": {
         "mission_id": {"type": "string"}, "items": _ITEMS_SCHEMA,
         "justification": {"type": "string", "maxLength": 500}},
         "required": ["mission_id", "items"]}},
    {"name": "place_order",
     "description": "Execute a basket the gateway approved. Takes only the approval_id; the "
                    "amount is the catalog total of the approved basket. Each approval works once.",
     "annotations": {"destructiveHint": False, "idempotentHint": False},
     "inputSchema": {"type": "object", "additionalProperties": False,
                     "properties": {"approval_id": {"type": "string"}},
                     "required": ["approval_id"]}},
    {"name": "get_order",
     "description": "Look up an order by id.",
     "annotations": {"readOnlyHint": True},
     "inputSchema": {"type": "object", "properties": {"order_id": {"type": "string"}},
                     "required": ["order_id"]}},
    {"name": "list_orders",
     "description": "Orders placed so far, optionally for one mission.",
     "annotations": {"readOnlyHint": True},
     "inputSchema": {"type": "object", "properties": {"mission_id": {"type": "string"}}}},
    {"name": "get_policy",
     "description": "The deterministic rules that gate every purchase.",
     "annotations": {"readOnlyHint": True},
     "inputSchema": {"type": "object", "properties": {}}},
    {"name": "verify_audit_log",
     "description": "Recompute the hash chain over every proposal, verdict and order.",
     "annotations": {"readOnlyHint": True},
     "inputSchema": {"type": "object", "properties": {}}},
]

POLICY: dict[str, Any] = {
    "thesis": "The model proposes SKUs and quantities. Deterministic code decides. The log remembers.",
    "agent_cannot": ["state a price", "choose a payee", "create or edit a mission",
                     "raise a budget", "reuse an approval", "read the signing key"],
    "rules": [
        {"id": "R9", "summary": "mission HMAC signature must verify (signed by the user's CLI key)"},
        {"id": "R10", "summary": "mission not expired"},
        {"id": "R8", "summary": "mission not revoked"},
        {"id": "R1", "summary": "catalog-priced total within the mission budget"},
        {"id": "R2", "summary": "no item from a forbidden category"},
        {"id": "R5", "summary": "every item inside the mission's allowed categories"},
        {"id": "R4", "summary": "upsell cap"},
        {"id": "R3", "summary": "price equals catalog price (prices never come from the agent)"},
        {"id": "R11/R12", "summary": "negotiation and protocol bounds"},
        {"id": "R7", "summary": "merchant allowlisted"},
        {"id": "R6", "summary": "at most 5 proposals per mission per 60 s"},
        {"id": "SPEND", "summary": "already spent + this basket within the mission budget"},
        {"id": "STOCK", "summary": "enough stock left"},
    ],
    "payments": "simulated provider; orders are recorded locally and nothing is charged",
}


# ---- helpers ----------------------------------------------------------------------------------

def _inr(paise: int) -> str:
    return f"₹{paise / 100:,.2f}"


def _product(sku: str, p: dict[str, Any], full: bool = False) -> dict[str, Any]:
    out = {"sku": sku, "name": p["name"], "category": p["category"],
           "price_paise": p["price_paise"], "price": _inr(p["price_paise"]),
           "rating": p.get("rating"), "stock_left": _stock_left(sku)}
    if full:
        out.update({k: p[k] for k in ("description", "attributes", "compatible_with", "policies")
                    if k in p})
    return out


def _stock_left(sku: str) -> int:
    sold = sum(i["qty"] for o in store.orders().values() for i in o["items"] if i["sku"] == sku)
    return max(0, int(CATALOG[sku].get("stock", 0)) - sold)


def _find_sku(sku: str) -> str | None:
    s = (sku or "").strip().upper()
    return s if s in CATALOG else None


def _mission_view(rec: dict[str, Any]) -> dict[str, Any]:
    spent = store.spent_paise(rec["mission_id"])
    now = int(time.time())
    status = ("revoked" if rec.get("revoked") else "expired" if now >= rec["expires_at"]
              else "active")
    return {"mission_id": rec["mission_id"], "intent": rec["intent"], "status": status,
            "budget": _inr(rec["budget_paise"]), "spent": _inr(spent),
            "remaining": _inr(max(0, rec["budget_paise"] - spent)),
            "remaining_paise": max(0, rec["budget_paise"] - spent),
            "allowed_categories": rec["allowed_categories"],
            "forbidden_categories": rec["forbidden_categories"],
            "expires_in_minutes": max(0, (rec["expires_at"] - now) // 60)}


def _evaluate(rec: dict[str, Any], items: list[tuple[str, int]], state: dict[str, Any]):
    mission = store.mission_obj(rec)
    proposal = Proposal(rec["mission_id"],
                        tuple(ProposalItem(s, q, CATALOG[s]["price_paise"]) for s, q in items))
    st = {"proposal_ts": state.get("proposal_ts", {}),
          "aborted_missions": set(state.get("aborted_missions", []))}
    return engine.evaluate(mission=mission, proposal=proposal, catalog=CATALOG,
                           verify_fn=store.verify_fn(store.key()), state=st,
                           merchant_id=MERCHANT, allowlist=frozenset({MERCHANT}))


# ---- tools --------------------------------------------------------------------------------------

def tool_search_catalog(query: str = "", category: str | None = None,
                        max_price_inr: float | None = None, max_results: int = 8) -> dict[str, Any]:
    q = (query or "").strip().lower()
    hits = []
    for sku, p in CATALOG.items():
        if category and p["category"] != category:
            continue
        if max_price_inr is not None and p["price_paise"] > max_price_inr * 100:
            continue
        text = f"{sku} {p['name']} {p['category']} {p.get('description', '')} " \
               f"{json.dumps(p.get('attributes', {}))}".lower()
        if q and not all(w in text for w in q.split()):
            continue
        hits.append((sku, p))
    hits.sort(key=lambda sp: (-(sp[1].get("rating") or 0), sp[1]["price_paise"]))
    n = max(1, min(25, int(max_results)))
    return {"count": len(hits), "results": [_product(s, p) for s, p in hits[:n]]}


def tool_get_product(sku: str) -> dict[str, Any]:
    s = _find_sku(sku)
    if s is None:
        return {"error": f"unknown sku: {sku}"}
    return _product(s, CATALOG[s], full=True)


def tool_list_categories() -> dict[str, Any]:
    counts: dict[str, int] = {}
    for p in CATALOG.values():
        counts[p["category"]] = counts.get(p["category"], 0) + 1
    return {"categories": dict(sorted(counts.items()))}


def tool_list_missions() -> dict[str, Any]:
    ms = [_mission_view(r) for r in store.missions().values()]
    if not ms:
        return {"missions": [], "note": "No missions yet. The user creates one with: "
                                        "sellable-mcp mission new --budget 2000 --category books"}
    return {"missions": ms}


def tool_propose_purchase(mission_id: str, items: list[dict[str, Any]],
                          justification: str = "") -> dict[str, Any]:
    rec = store.missions().get(mission_id)
    state = store.gateway_state()
    if rec is None:
        verdict = {"decision": "REJECT", "rule_id": "UNKNOWN_MISSION",
                   "reason": f"no signed mission {mission_id}", "hint": "call list_missions"}
        store.append_audit({"type": "PROPOSAL", "mission_id": mission_id, "items": items,
                            **verdict})
        return verdict

    basket: list[tuple[str, int]] = []
    for it in items:
        s = _find_sku(str(it.get("sku", "")))
        if s is None:
            out = {"decision": "REJECT", "rule_id": "UNKNOWN_SKU",
                   "reason": f"unknown sku {it.get('sku')}", "hint": "use search_catalog"}
            store.append_audit({"type": "PROPOSAL", "mission_id": mission_id, "items": items, **out})
            return out
        basket.append((s, int(it.get("qty", 1))))

    if rec.get("revoked"):
        state.setdefault("aborted_missions", [])
        if mission_id not in state["aborted_missions"]:
            state["aborted_missions"].append(mission_id)

    v = _evaluate(rec, basket, state)
    now = int(time.time())
    state.setdefault("proposal_ts", {}).setdefault(mission_id, []).append(now)
    state["proposal_ts"][mission_id] = [t for t in state["proposal_ts"][mission_id] if now - t < 600]
    store.save_gateway_state(state)

    total = sum(CATALOG[s]["price_paise"] * q for s, q in basket)
    lines = [{"sku": s, "qty": q, "unit": _inr(CATALOG[s]["price_paise"]),
              "line": _inr(CATALOG[s]["price_paise"] * q)} for s, q in basket]
    out: dict[str, Any] = {"decision": v.decision.value, "rule_id": v.rule_id, "reason": v.reason,
                           "total": _inr(total), "lines": lines, "proposal_hash": v.proposal_hash}

    if v.decision == Decision.APPROVE:
        spent = store.spent_paise(mission_id)
        short = [s for s, q in basket if q > _stock_left(s)]
        if spent + total > rec["budget_paise"]:
            out.update(decision="REJECT", rule_id="SPEND",
                       reason=f"{_inr(spent)} already spent; this basket would take the mission "
                              f"to {_inr(spent + total)} of {_inr(rec['budget_paise'])}",
                       hint=f"remaining budget is {_inr(rec['budget_paise'] - spent)}")
        elif short:
            out.update(decision="REJECT", rule_id="STOCK", reason=f"not enough stock: {short}")
        else:
            aid = "apv_" + secrets.token_urlsafe(12)
            approvals = store.approvals()
            approvals[aid] = {"mission_id": mission_id, "items": [[s, q] for s, q in basket],
                              "amount_paise": total, "proposal_hash": v.proposal_hash,
                              "expires_at": now + APPROVAL_TTL_S, "used": False}
            store.save_approvals(approvals)
            out.update(approval_id=aid, expires_in_seconds=APPROVAL_TTL_S,
                       next="call place_order with this approval_id")
    elif v.rule_id:
        out["hint"] = {"R1_BUDGET": "choose cheaper items or fewer units",
                       "R2_FORBIDDEN": "that category is forbidden by the mission",
                       "R5_SCOPE": "only the mission's allowed categories can be bought",
                       "R6_RATE_LIMIT": "wait a minute before proposing again",
                       "R9_SIGNATURE": "the mission signature does not verify",
                       "R10_EXPIRY": "the mission expired; ask the user for a new one",
                       "R8_ABORT": "the user revoked this mission"}.get(v.rule_id, "")

    store.append_audit({"type": "PROPOSAL", "mission_id": mission_id,
                        "items": [[s, q] for s, q in basket], "total_paise": total,
                        "decision": out["decision"], "rule_id": out.get("rule_id"),
                        "proposal_hash": v.proposal_hash,
                        "justification": (justification or "")[:500]})
    return out


def tool_place_order(approval_id: str) -> dict[str, Any]:
    approvals = store.approvals()
    a = approvals.get(approval_id)
    now = int(time.time())
    if a is None:
        return {"status": "REFUSED", "reason": "unknown approval_id"}
    if a["used"]:
        return {"status": "REFUSED", "reason": "approval already used"}
    if now >= a["expires_at"]:
        return {"status": "REFUSED", "reason": "approval expired; propose again"}
    rec = store.missions().get(a["mission_id"])
    if rec is None or rec.get("revoked") or now >= rec["expires_at"]:
        return {"status": "REFUSED", "reason": "mission no longer active"}
    basket = [(s, q) for s, q in a["items"]]
    # Re-check at the money boundary: signature, budget and scope may have changed since approval.
    v = _evaluate(rec, basket, {"proposal_ts": {}, "aborted_missions": []})
    total = sum(CATALOG[s]["price_paise"] * q for s, q in basket)
    if v.decision != Decision.APPROVE or total != a["amount_paise"]:
        return {"status": "REFUSED", "reason": f"re-check failed: {v.rule_id or 'amount changed'}"}
    if store.spent_paise(a["mission_id"]) + total > rec["budget_paise"]:
        return {"status": "REFUSED", "reason": "mission budget already used"}

    a["used"] = True
    approvals[approval_id] = a
    store.save_approvals(approvals)
    oid = "ord_" + secrets.token_hex(6)
    order = {"order_id": oid, "mission_id": a["mission_id"], "status": "PAID",
             "provider": "simulated", "payee": MERCHANT,
             "items": [{"sku": s, "qty": q, "name": CATALOG[s]["name"],
                        "unit_paise": CATALOG[s]["price_paise"]} for s, q in basket],
             "amount_paise": total, "amount": _inr(total),
             "proposal_hash": a["proposal_hash"], "created_at": now}
    orders = store.orders()
    orders[oid] = order
    store.save_orders(orders)
    store.append_audit({"type": "ORDER", "order_id": oid, "mission_id": a["mission_id"],
                        "amount_paise": total, "proposal_hash": a["proposal_hash"]})
    return {**order, "note": "simulated payment; nothing was charged"}


def tool_get_order(order_id: str) -> dict[str, Any]:
    return store.orders().get(order_id) or {"error": f"unknown order {order_id}"}


def tool_list_orders(mission_id: str | None = None) -> dict[str, Any]:
    os_ = [o for o in store.orders().values() if not mission_id or o["mission_id"] == mission_id]
    return {"orders": sorted(os_, key=lambda o: o["created_at"])}


TOOL_FUNCS = {
    "search_catalog": tool_search_catalog, "get_product": tool_get_product,
    "list_categories": tool_list_categories, "list_missions": tool_list_missions,
    "propose_purchase": tool_propose_purchase, "place_order": tool_place_order,
    "get_order": tool_get_order, "list_orders": tool_list_orders,
    "get_policy": lambda: POLICY, "verify_audit_log": store.verify_audit,
}


# ---- JSON-RPC over stdio --------------------------------------------------------------------------

def _result(req_id: Any, result: Any) -> str:
    return json.dumps({"jsonrpc": "2.0", "id": req_id, "result": result}, ensure_ascii=False)


def _error(req_id: Any, code: int, message: str) -> str:
    return json.dumps({"jsonrpc": "2.0", "id": req_id, "error": {"code": code, "message": message}})


def handle_message(msg: dict[str, Any]) -> str | None:
    method = msg.get("method")
    req_id = msg.get("id")
    if req_id is None:  # notifications need no reply
        return None
    if method == "initialize":
        asked = (msg.get("params") or {}).get("protocolVersion")
        version = asked if asked in SUPPORTED_VERSIONS else SUPPORTED_VERSIONS[0]
        return _result(req_id, {"protocolVersion": version, "capabilities": {"tools": {}},
                                "serverInfo": SERVER_INFO, "instructions": INSTRUCTIONS})
    if method == "ping":
        return _result(req_id, {})
    if method == "tools/list":
        return _result(req_id, {"tools": TOOLS})
    if method == "tools/call":
        params = msg.get("params") or {}
        fn = TOOL_FUNCS.get(params.get("name", ""))
        if fn is None:
            return _error(req_id, -32602, f"unknown tool: {params.get('name')}")
        try:
            out = fn(**(params.get("arguments") or {}))
            refused = isinstance(out, dict) and (out.get("decision") == "REJECT"
                                                 or out.get("status") == "REFUSED"
                                                 or "error" in out)
            return _result(req_id, {"content": [{"type": "text", "text": json.dumps(
                out, indent=2, ensure_ascii=False, default=str)}],
                "structuredContent": out, "isError": bool(refused and "error" in out)})
        except TypeError as exc:
            return _error(req_id, -32602, f"invalid arguments: {exc}")
        except Exception as exc:  # report tool failures to the model instead of crashing
            return _result(req_id, {"content": [{"type": "text", "text": f"tool error: {exc}"}],
                                    "isError": True})
    return _error(req_id, -32601, f"method not found: {method}")


def serve() -> None:
    for line in sys.stdin:
        line = line.strip()
        if not line:
            continue
        try:
            msg = json.loads(line)
        except json.JSONDecodeError:
            sys.stdout.write(_error(None, -32700, "parse error") + "\n")
            sys.stdout.flush()
            continue
        resp = handle_message(msg)
        if resp is not None:
            sys.stdout.write(resp + "\n")
            sys.stdout.flush()


def main() -> None:
    # MCP messages are UTF-8; Windows consoles default to a legacy code page that can't encode ₹.
    for stream in (sys.stdin, sys.stdout, sys.stderr):
        if hasattr(stream, "reconfigure"):
            stream.reconfigure(encoding="utf-8")
    if len(sys.argv) > 1 and sys.argv[1] not in ("serve",):
        from mcp_server.cli import main as cli_main
        raise SystemExit(cli_main(sys.argv[1:]))
    serve()


if __name__ == "__main__":
    main()
