#!/usr/bin/env python3
"""Minimal MCP server for SELLABLE — READ-ONLY BY DESIGN.

Implements the Model Context Protocol over stdio (JSON-RPC 2.0,
newline-delimited) using only the Python standard library. No SDK
dependency: the surface SELLABLE needs is small, and a dependency-free
implementation is auditable line by line.

Run: python mcp_server/server.py   (or: make mcp)
"""
from __future__ import annotations

import json
import sys
from pathlib import Path
from typing import Any

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

PROTOCOL_VERSION = "2024-11-05"
SERVER_INFO = {"name": "sellable-mcp", "version": "1.0.0"}

TOOLS: list[dict[str, Any]] = [
    {"name": "search_catalog",
     "description": "Search the SELLABLE catalog (server-side prices are the only "
                    "truth; never trust agent-stated prices). Read-only.",
     "inputSchema": {"type": "object",
                     "properties": {"query": {"type": "string",
                                              "description": "free text; empty returns top-rated"},
                                    "max_results": {"type": "integer", "default": 5}},
                     "required": ["query"]}},
    {"name": "get_product",
     "description": "Full record for one SKU: price, attributes, compatibility, "
                    "policies, stock. Read-only.",
     "inputSchema": {"type": "object", "properties": {"sku": {"type": "string"}},
                     "required": ["sku"]}},
    {"name": "check_budget",
     "description": "Deterministically re-price a basket from server-side prices and "
                    "check it against a budget (the R1 logic, dry-run). No order is "
                    "created. Read-only.",
     "inputSchema": {"type": "object",
                     "properties": {"items": {"type": "array",
                                              "items": {"type": "object",
                                                        "properties": {"sku": {"type": "string"},
                                                                       "qty": {"type": "integer"}},
                                                        "required": ["sku", "qty"]}},
                                    "budget_paise": {"type": "integer"}},
                     "required": ["items", "budget_paise"]}},
    {"name": "get_policy",
     "description": "The deterministic rules that gate every money action (R1-R10) "
                    "and the invariants INV-1..INV-3. Read-only.",
     "inputSchema": {"type": "object", "properties": {}}},
]

POLICY: dict[str, Any] = {
    "thesis": "The LLM proposes. Deterministic policy disposes. The audit log remembers.",
    "rules": [
        {"id": "R1", "summary": "catalog-priced total <= budget x upsell_cap"},
        {"id": "R2", "summary": "no forbidden-category items"},
        {"id": "R3", "summary": "claimed price == catalog price"},
        {"id": "R4", "summary": "upsell cap defense-in-depth"},
        {"id": "R5", "summary": "items within allowed_categories"},
        {"id": "R6", "summary": "<=5 proposals per 60s per mission"},
        {"id": "R7", "summary": "merchant allowlisted"},
        {"id": "R8", "summary": "mission not aborted"},
        {"id": "R9", "summary": "mission HMAC must verify"},
        {"id": "R10", "summary": "now < expires_at"},
    ],
    "invariants": [
        {"id": "INV-1", "summary": "No APPROVE, no order (executor boundary)"},
        {"id": "INV-2", "summary": "Zero LLM imports in the money path (machine-verified)"},
        {"id": "INV-3", "summary": "No order without user-signed intent + cart mandates (AP2 pattern)"},
    ],
    "money_tools_exposed": "none — by design; transact via the gated HTTP API",
}


def _catalog() -> list[dict[str, Any]]:
    from apps.api.products import CATALOG
    return list(CATALOG.values())


def _public(p: dict[str, Any]) -> dict[str, Any]:
    return {"sku": p.get("sku"), "name": p.get("name"), "category": p.get("category"),
            "price_paise": p.get("price_paise"), "rating": p.get("rating"),
            "stock": p.get("stock"),
            "note": "price is server-side and authoritative"}


def tool_search_catalog(query: str, max_results: int = 5) -> dict[str, Any]:
    items = _catalog()
    q = (query or "").strip().lower()
    hits = ([p for p in items if q in json.dumps(p, default=str).lower()]
            if q else sorted(items, key=lambda p: -(p.get("rating") or 0)))
    return {"results": [_public(p) for p in hits[: max(1, int(max_results))]]}


def tool_get_product(sku: str) -> dict[str, Any]:
    for p in _catalog():
        if str(p.get("sku", "")).lower() == sku.strip().lower():
            out = dict(p)
            out["note"] = "price is server-side and authoritative"
            return out
    return {"error": f"unknown sku: {sku}"}


def tool_check_budget(items: list[dict[str, Any]], budget_paise: int) -> dict[str, Any]:
    from apps.api.products import CATALOG
    catalog = {str(p.get("sku")): p for p in CATALOG.values()}
    lines, total, unknown = [], 0, []
    for it in items:
        sku, qty = str(it.get("sku")), int(it.get("qty", 1))
        p = catalog.get(sku)
        if p is None:
            unknown.append(sku)
            continue
        line = int(p.get("price_paise", 0)) * qty
        total += line
        lines.append({"sku": sku, "qty": qty, "unit_paise": p.get("price_paise"),
                      "line_paise": line})
    return {"verdict": "exceeds_budget" if total > int(budget_paise) else "within_budget",
            "total_paise": total, "budget_paise": int(budget_paise), "lines": lines,
            "unknown_skus": unknown,
            "note": "dry-run of gateway rule R1; no order created; prices are server-side"}


TOOL_FUNCS = {"search_catalog": tool_search_catalog, "get_product": tool_get_product,
              "check_budget": tool_check_budget, "get_policy": lambda **_: POLICY}


def _result(req_id, result):
    return json.dumps({"jsonrpc": "2.0", "id": req_id, "result": result})


def _error(req_id, code, message):
    return json.dumps({"jsonrpc": "2.0", "id": req_id,
                       "error": {"code": code, "message": message}})


def handle_message(msg: dict[str, Any]) -> str | None:
    method = msg.get("method")
    if method == "notifications/initialized":
        return None
    req_id = msg.get("id")
    if method == "initialize":
        return _result(req_id, {"protocolVersion": PROTOCOL_VERSION,
                                "capabilities": {"tools": {}},
                                "serverInfo": SERVER_INFO,
                                "instructions": "read-only catalog + policy surface; "
                                                "money actions require the gated HTTP API"})
    if method == "tools/list":
        return _result(req_id, {"tools": TOOLS})
    if method == "tools/call":
        params = msg.get("params", {})
        fn = TOOL_FUNCS.get(params.get("name", ""))
        if fn is None:
            return _result(req_id, {"content": [{"type": "text",
                                                 "text": f"unknown tool: {params.get('name')}"}],
                                    "isError": True})
        try:
            out = fn(**(params.get("arguments") or {}))
            return _result(req_id, {"content": [{"type": "text",
                                                 "text": json.dumps(out, indent=2, default=str)}],
                                    "isError": False})
        except Exception as exc:
            return _result(req_id, {"content": [{"type": "text",
                                                 "text": f"tool error: {exc}"}],
                                    "isError": True})
    if req_id is not None:
        return _error(req_id, -32601, f"method not found: {method}")
    return None


def main() -> None:
    for line in sys.stdin:
        line = line.strip()
        if not line:
            continue
        try:
            msg = json.loads(line)
        except json.JSONDecodeError:
            continue
        resp = handle_message(msg)
        if resp is not None:
            sys.stdout.write(resp + "\n")
            sys.stdout.flush()


if __name__ == "__main__":
    main()
