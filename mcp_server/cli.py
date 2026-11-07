"""User-side CLI. This is the only place missions are created or revoked.

    sellable-mcp mission new --budget 2000 --category books --category stationery \
                             [--forbid electronics] [--hours 24] [--intent "..."]
    sellable-mcp mission list
    sellable-mcp mission revoke <mission_id>
    sellable-mcp mission inspect <mission_id>
    sellable-mcp catalog search [--query "..."] [--category books] [--limit 8]
    sellable-mcp catalog get <sku>
    sellable-mcp orders
    sellable-mcp audit verify
    sellable-mcp config          # prints the MCP client config snippet
    sellable-mcp --version       # prints the installed version
"""
from __future__ import annotations

import argparse
import json
import shutil
import time

from mcp_server import store


def _print(obj) -> None:
    print(json.dumps(obj, indent=2, ensure_ascii=False))


def _inspect(mission_id: str) -> dict | None:
    from mcp_server.server import _inr
    rec = store.missions().get(mission_id)
    if rec is None:
        return None
    now = int(time.time())
    orders = [o for o in store.orders().values()
              if o["mission_id"] == mission_id and o.get("status") == "PAID"]
    apvs = {k: a for k, a in store.approvals().items() if a["mission_id"] == mission_id}
    spent = sum(o["amount_paise"] for o in orders)
    pending = sum(a["amount_paise"] for a in apvs.values()
                  if not a["used"] and now < a["expires_at"])
    budget = rec["budget_paise"]
    remaining = budget - spent - pending
    status = ("REVOKED" if rec.get("revoked") else "EXPIRED" if now >= rec["expires_at"]
              else "EXHAUSTED" if remaining <= 0 else "ACTIVE")
    return {"mission_id": mission_id, "status": status, "budget_paise": budget,
            "budget_inr": _inr(budget), "spent_paise": spent,
            "committed_paise": spent + pending, "remaining_paise": remaining,
            "order_ids": [o["order_id"] for o in orders], "approval_ids": list(apvs)}


def main(argv: list[str]) -> int:
    from mcp_server.server import SERVER_INFO  # single source of truth for the version
    ap = argparse.ArgumentParser(prog="sellable-mcp")
    ap.add_argument("--version", action="version",
                    version=f"%(prog)s {SERVER_INFO['version']}")
    sub = ap.add_subparsers(dest="cmd", required=True)
    m = sub.add_parser("mission").add_subparsers(dest="action", required=True)
    new = m.add_parser("new", help="sign a new mission with your local key")
    new.add_argument("--budget", type=float, required=True, help="budget in rupees")
    new.add_argument("--category", action="append", required=True,
                     help="allowed category (repeatable)")
    new.add_argument("--forbid", action="append", default=[], help="forbidden category")
    new.add_argument("--hours", type=float, default=24)
    new.add_argument("--intent", default="")
    m.add_parser("list")
    rv = m.add_parser("revoke")
    rv.add_argument("mission_id")
    m.add_parser("inspect").add_argument("mission_id")
    c = sub.add_parser("catalog").add_subparsers(dest="action", required=True)
    cs = c.add_parser("search")
    cs.add_argument("--query", default="")
    cs.add_argument("--category")
    cs.add_argument("--limit", type=int, default=8)
    c.add_parser("get").add_argument("sku")
    sub.add_parser("orders")
    au = sub.add_parser("audit").add_subparsers(dest="action", required=True)
    au.add_parser("verify")
    sub.add_parser("config")
    a = ap.parse_args(argv)

    if a.cmd == "mission" and a.action == "new":
        intent = a.intent or f"Buy {', '.join(a.category)} items within ₹{a.budget:,.0f}"
        rec = store.new_mission(intent=intent, budget_paise=int(round(a.budget * 100)),
                                allowed=a.category, forbidden=a.forbid, hours=a.hours)
        _print({k: rec[k] for k in ("mission_id", "intent", "budget_paise", "allowed_categories",
                                     "forbidden_categories", "expires_at")})
        print(f"\nSigned. Your agent can now shop inside mission {rec['mission_id']}.")
    elif a.cmd == "mission" and a.action == "list":
        from mcp_server.server import tool_list_missions
        _print(tool_list_missions())
    elif a.cmd == "mission" and a.action == "revoke":
        ms = store.missions()
        if a.mission_id not in ms:
            print(f"unknown mission {a.mission_id}")
            return 1
        ms[a.mission_id]["revoked"] = True
        store.save_missions(ms)
        store.append_audit({"type": "MISSION_REVOKED", "mission_id": a.mission_id, "by": "user-cli"})
        print(f"revoked {a.mission_id}")
    elif a.cmd == "mission" and a.action == "inspect":
        res = _inspect(a.mission_id)
        if res is None:
            print(f"unknown mission {a.mission_id}")
            return 1
        _print(res)
    elif a.cmd == "catalog" and a.action == "search":
        from mcp_server.server import tool_search_catalog
        _print(tool_search_catalog(query=a.query, category=a.category, max_results=a.limit))
    elif a.cmd == "catalog" and a.action == "get":
        from mcp_server.server import tool_get_product
        res = tool_get_product(a.sku)
        _print(res)
        return 1 if "error" in res else 0
    elif a.cmd == "orders":
        _print(list(store.orders().values()))
    elif a.cmd == "audit":
        res = store.verify_audit()
        _print(res)
        return 0 if res["ok"] else 2
    elif a.cmd == "config":
        cmd = "sellable-mcp" if shutil.which("sellable-mcp") else "uvx"
        args = [] if cmd == "sellable-mcp" else [
            "--from", "git+https://github.com/HarshDubey23/SELLABLE", "sellable-mcp"]
        _print({"mcpServers": {"sellable": {"command": cmd, "args": args}}})
    return 0
