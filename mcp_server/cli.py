"""User-side CLI. This is the only place missions are created or revoked.

    sellable-mcp mission new --budget 2000 --category books --category stationery \
                             [--forbid electronics] [--hours 24] [--intent "..."]
    sellable-mcp mission list
    sellable-mcp mission revoke <mission_id>
    sellable-mcp orders
    sellable-mcp audit verify
    sellable-mcp config          # prints the MCP client config snippet
"""
from __future__ import annotations

import argparse
import json
import shutil

from mcp_server import store


def _print(obj) -> None:
    print(json.dumps(obj, indent=2, ensure_ascii=False))


def main(argv: list[str]) -> int:
    ap = argparse.ArgumentParser(prog="sellable-mcp")
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
