"""The remote MCP transport (Streamable HTTP), driven over real HTTP like a hosted client would."""
from __future__ import annotations

import json
import os
import socket
import subprocess
import sys
import time
import urllib.error
import urllib.request
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]
INIT = {"jsonrpc": "2.0", "id": 1, "method": "initialize",
        "params": {"protocolVersion": "2025-06-18", "capabilities": {},
                   "clientInfo": {"name": "pytest", "version": "1"}}}


def _free_port() -> int:
    with socket.socket() as s:
        s.bind(("127.0.0.1", 0))
        return s.getsockname()[1]


class Server:
    def __init__(self, tmp: Path, *extra: str, env: dict | None = None):
        self.port = _free_port()
        self.base = f"http://127.0.0.1:{self.port}"
        e = {**os.environ, "PYTHONPATH": str(ROOT), "SELLABLE_MCP_QUIET": "1",
             "SELLABLE_SANDBOX_ROOT": str(tmp / "sbx"), "SELLABLE_HOME": str(tmp / "private"),
             **(env or {})}
        self.p = subprocess.Popen([sys.executable, "-m", "mcp_server.server", "serve", "--http",
                                   "--port", str(self.port), *extra], cwd=ROOT, env=e,
                                  stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        for _ in range(100):
            try:
                urllib.request.urlopen(self.base + "/health", timeout=1)
                return
            except OSError:
                time.sleep(0.1)
        raise RuntimeError("server did not start")

    def post(self, body, sid: str | None = None, path: str = "/mcp", headers: dict | None = None):
        h = {"Content-Type": "application/json", **(headers or {})}
        if sid:
            h["Mcp-Session-Id"] = sid
        req = urllib.request.Request(self.base + path, data=json.dumps(body).encode(), headers=h)
        try:
            r = urllib.request.urlopen(req, timeout=10)
            raw = r.read()
            return r.status, r.headers, json.loads(raw) if raw else None
        except urllib.error.HTTPError as err:
            return err.code, err.headers, err.read().decode()

    def tool(self, sid: str, name: str, **args):
        st, _, body = self.post({"jsonrpc": "2.0", "id": 2, "method": "tools/call",
                                 "params": {"name": name, "arguments": args}}, sid)
        assert st == 200, body
        return body["result"]["structuredContent"]

    def close(self):
        self.p.terminate()
        self.p.wait(timeout=10)


@pytest.fixture
def sandbox(tmp_path):
    s = Server(tmp_path, "--sandbox")
    yield s
    s.close()


def _init(s: Server, path: str = "/mcp") -> str:
    st, headers, body = s.post(INIT, path=path)
    assert st == 200 and body["result"]["serverInfo"]["name"] == "sellable"
    sid = headers.get("Mcp-Session-Id")
    assert sid
    assert s.post({"jsonrpc": "2.0", "method": "notifications/initialized"}, sid)[0] == 202
    return sid


def test_sandbox_session_buys_once_inside_its_signed_mission(sandbox):
    sid = _init(sandbox, "/mcp?budget=1000&category=books&forbid=electronics")
    m = sandbox.tool(sid, "list_missions")["missions"][0]
    assert m["budget"] == "₹1,000.00" and m["allowed_categories"] == ["books"]
    book = sandbox.tool(sid, "search_catalog", category="books", max_results=1)["results"][0]
    v = sandbox.tool(sid, "propose_purchase", mission_id=m["mission_id"],
                     items=[{"sku": book["sku"], "qty": 1}])
    assert v["decision"] == "APPROVE"
    assert sandbox.tool(sid, "place_order", approval_id=v["approval_id"])["status"] == "PAID"
    assert sandbox.tool(sid, "place_order", approval_id=v["approval_id"])["status"] == "REFUSED"
    over = sandbox.tool(sid, "propose_purchase", mission_id=m["mission_id"],
                        items=[{"sku": book["sku"], "qty": 50}])
    assert over["decision"] == "REJECT" and over["rule_id"] == "R1_BUDGET"
    assert sandbox.tool(sid, "verify_audit_log")["ok"] is True


def test_sessions_are_isolated(sandbox):
    a, b = _init(sandbox), _init(sandbox)
    ma = sandbox.tool(a, "list_missions")["missions"][0]
    book = sandbox.tool(a, "search_catalog", category="books", max_results=1)["results"][0]
    v = sandbox.tool(a, "propose_purchase", mission_id=ma["mission_id"],
                     items=[{"sku": book["sku"], "qty": 1}])
    # session b can neither see a's mission nor redeem a's approval
    assert ma["mission_id"] not in [m["mission_id"] for m in sandbox.tool(b, "list_missions")["missions"]]
    assert sandbox.tool(b, "place_order", approval_id=v["approval_id"])["status"] == "REFUSED"


def test_unknown_session_and_bad_requests(sandbox):
    assert sandbox.post({"jsonrpc": "2.0", "id": 1, "method": "ping"}, "nope")[0] == 404
    st, _, _ = sandbox.post([{"jsonrpc": "2.0", "id": 9, "method": "ping"}], _init(sandbox))
    assert st == 200
    with pytest.raises(urllib.error.HTTPError) as e:
        urllib.request.urlopen(sandbox.base + "/mcp")
    assert e.value.code == 405


def test_url_cannot_widen_beyond_the_catalog(sandbox):
    sid = _init(sandbox, "/mcp?budget=99999999&category=weapons")
    m = sandbox.tool(sid, "list_missions")["missions"][0]
    assert m["budget"] == "₹100,000.00"           # clamped
    assert m["allowed_categories"] == ["books"]   # unknown categories ignored


def test_private_mode_requires_the_token(tmp_path):
    s = Server(tmp_path, env={"SELLABLE_MCP_TOKEN": "s3cret"})
    try:
        assert s.post(INIT)[0] == 401
        st, headers, _ = s.post(INIT, headers={"Authorization": "Bearer s3cret"})
        assert st == 200 and headers.get("Mcp-Session-Id")
    finally:
        s.close()
