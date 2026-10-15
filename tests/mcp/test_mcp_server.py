"""End-to-end tests for the SELLABLE MCP server, driven over real stdio JSON-RPC."""
from __future__ import annotations

import json
import os
import subprocess
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]


class Client:
    def __init__(self, home: Path):
        env = {**os.environ, "SELLABLE_HOME": str(home), "PYTHONPATH": str(ROOT)}
        self.p = subprocess.Popen([sys.executable, "-m", "mcp_server.server"], cwd=ROOT, env=env,
                                  stdin=subprocess.PIPE, stdout=subprocess.PIPE, text=True,
                                  encoding="utf-8")
        self.n = 0

    def call(self, method: str, params: dict | None = None) -> dict:
        self.n += 1
        self.p.stdin.write(json.dumps({"jsonrpc": "2.0", "id": self.n, "method": method,
                                       "params": params or {}}) + "\n")
        self.p.stdin.flush()
        return json.loads(self.p.stdout.readline())

    def tool(self, name: str, **args) -> dict:
        r = self.call("tools/call", {"name": name, "arguments": args})
        assert "result" in r, r
        return r["result"]["structuredContent"]

    def close(self) -> None:
        self.p.stdin.close()
        self.p.wait(timeout=10)


def cli(home: Path, *args: str) -> subprocess.CompletedProcess:
    env = {**os.environ, "SELLABLE_HOME": str(home), "PYTHONPATH": str(ROOT)}
    return subprocess.run([sys.executable, "-m", "mcp_server.server", *args], cwd=ROOT, env=env,
                          capture_output=True, text=True, encoding="utf-8")


@pytest.fixture
def setup(tmp_path):
    r = cli(tmp_path, "mission", "new", "--budget", "2000", "--category", "books",
            "--forbid", "electronics", "--hours", "1")
    assert r.returncode == 0, r.stderr
    mid = next(iter(json.loads((tmp_path / "missions.json").read_text(encoding="utf-8"))))
    c = Client(tmp_path)
    init = c.call("initialize", {"protocolVersion": "2025-06-18", "capabilities": {},
                                 "clientInfo": {"name": "pytest", "version": "0"}})
    assert init["result"]["protocolVersion"] == "2025-06-18"
    yield c, mid, tmp_path
    c.close()


def cheapest(c: Client, category: str) -> str:
    rs = c.tool("search_catalog", category=category, max_results=25)["results"]
    return min(rs, key=lambda x: x["price_paise"])["sku"]


def test_search_returns_real_skus(setup):
    c, _, _ = setup
    res = c.tool("search_catalog", query="bat", max_results=3)["results"]
    assert res and all(r["sku"] for r in res)
    assert c.tool("get_product", sku=res[0]["sku"])["sku"] == res[0]["sku"]


def test_happy_path_and_single_use(setup):
    c, mid, _ = setup
    sku = cheapest(c, "books")
    ok = c.tool("propose_purchase", mission_id=mid, items=[{"sku": sku, "qty": 1}])
    assert ok["decision"] == "APPROVE" and ok["approval_id"]
    order = c.tool("place_order", approval_id=ok["approval_id"])
    assert order["status"] == "PAID" and order["payee"] == "SELLABLE-DEMO"
    assert c.tool("place_order", approval_id=ok["approval_id"])["status"] == "REFUSED"
    m = c.tool("list_missions")["missions"][0]
    assert m["remaining_paise"] == 200000 - order["amount_paise"]


def test_scope_budget_and_unknown_inputs_rejected(setup):
    c, mid, _ = setup
    assert c.tool("propose_purchase", mission_id=mid,
                  items=[{"sku": cheapest(c, "cricket"), "qty": 1}])["decision"] == "REJECT"
    assert c.tool("propose_purchase", mission_id=mid,
                  items=[{"sku": cheapest(c, "books"), "qty": 50}])["rule_id"] == "R1_BUDGET"
    assert c.tool("propose_purchase", mission_id="m_fake",
                  items=[{"sku": cheapest(c, "books"), "qty": 1}])["rule_id"] == "UNKNOWN_MISSION"
    assert c.tool("propose_purchase", mission_id=mid,
                  items=[{"sku": "NOPE-1", "qty": 1}])["rule_id"] == "UNKNOWN_SKU"


def test_cumulative_spend_is_enforced(setup):
    c, mid, _ = setup
    sku = cheapest(c, "books")
    price = c.tool("get_product", sku=sku)["price_paise"]
    k = (200000 // price) // 2 + 1  # one basket fits the budget, two baskets do not
    first = c.tool("propose_purchase", mission_id=mid, items=[{"sku": sku, "qty": k}])
    assert first["decision"] == "APPROVE", first
    assert c.tool("place_order", approval_id=first["approval_id"])["status"] == "PAID"
    again = c.tool("propose_purchase", mission_id=mid, items=[{"sku": sku, "qty": k}])
    assert again["decision"] == "REJECT" and again["rule_id"] == "SPEND"


def test_editing_the_budget_on_disk_breaks_the_signature(setup):
    c, mid, home = setup
    f = home / "missions.json"
    ms = json.loads(f.read_text(encoding="utf-8"))
    ms[mid]["budget_paise"] = 10_000_000
    f.write_text(json.dumps(ms), encoding="utf-8")
    r = c.tool("propose_purchase", mission_id=mid, items=[{"sku": cheapest(c, "books"), "qty": 1}])
    assert r["decision"] == "REJECT" and r["rule_id"] == "R9_SIGNATURE"


def test_revoked_mission_is_refused(setup):
    c, mid, home = setup
    ok = c.tool("propose_purchase", mission_id=mid, items=[{"sku": cheapest(c, "books"), "qty": 1}])
    assert cli(home, "mission", "revoke", mid).returncode == 0
    assert c.tool("place_order", approval_id=ok["approval_id"])["status"] == "REFUSED"
    again = c.tool("propose_purchase", mission_id=mid,
                   items=[{"sku": cheapest(c, "books"), "qty": 1}])
    assert again["decision"] == "REJECT"


def test_audit_chain_detects_tampering(setup):
    c, mid, home = setup
    ok = c.tool("propose_purchase", mission_id=mid, items=[{"sku": cheapest(c, "books"), "qty": 1}])
    c.tool("place_order", approval_id=ok["approval_id"])
    assert c.tool("verify_audit_log")["ok"] is True
    f = home / "audit.jsonl"
    lines = f.read_text(encoding="utf-8").splitlines()
    entry = json.loads(lines[1])
    entry["body"]["total_paise"] = 1
    lines[1] = json.dumps(entry)
    f.write_text("\n".join(lines) + "\n", encoding="utf-8")
    bad = c.tool("verify_audit_log")
    assert bad["ok"] is False and bad["first_bad_seq"] == 1


def test_no_tool_accepts_price_or_payee(setup):
    c, _, _ = setup
    tools = c.call("tools/list")["result"]["tools"]
    for t in tools:
        props = json.dumps(t["inputSchema"]).lower()
        assert "price_paise" not in props and "payee" not in props and "amount" not in props, t["name"]
    assert not any(t["name"] in ("create_mission", "sign_mission", "set_budget") for t in tools)


def test_protocol_errors(setup):
    c, _, _ = setup
    assert c.call("tools/call", {"name": "nope", "arguments": {}})["error"]["code"] == -32602
    assert c.call("resources/list")["error"]["code"] == -32601
    assert c.call("ping")["result"] == {}
