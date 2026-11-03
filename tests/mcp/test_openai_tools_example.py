"""examples/openai_tools_agent.py drives the real MCP server through a scripted 'model'."""
from __future__ import annotations

import importlib.util
import json
import os
import subprocess
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]
_spec = importlib.util.spec_from_file_location("openai_tools_agent",
                                               ROOT / "examples" / "openai_tools_agent.py")
example = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(example)


@pytest.fixture
def mcp(tmp_path):
    env = {**os.environ, "SELLABLE_HOME": str(tmp_path), "PYTHONPATH": str(ROOT)}
    r = subprocess.run([sys.executable, "-m", "mcp_server.server", "mission", "new", "--budget",
                        "2000", "--category", "books", "--forbid", "electronics", "--hours", "1"],
                       cwd=ROOT, env=env, capture_output=True, text=True, encoding="utf-8")
    assert r.returncode == 0, r.stderr
    client = example.McpStdio(env={"SELLABLE_HOME": str(tmp_path)})
    yield client
    client.close()


def _call(name: str, **args) -> dict:
    return {"role": "assistant", "content": None, "tool_calls": [
        {"id": f"c_{name}", "type": "function",
         "function": {"name": name, "arguments": json.dumps(args)}}]}


def _last_tool(messages) -> dict:
    return json.loads(next(m for m in reversed(messages) if m["role"] == "tool")["content"])


def test_tools_convert_to_openai_function_schema(mcp):
    tools = example.openai_tools(mcp.tools())
    names = {t["function"]["name"] for t in tools}
    assert {"propose_purchase", "place_order", "search_catalog"} <= names
    for t in tools:
        assert t["type"] == "function" and t["function"]["parameters"]["type"] == "object"
        # nothing the model can call takes an amount or a payee
        assert not {"amount", "amount_inr", "payee", "price"} & set(
            t["function"]["parameters"].get("properties", {}))


def test_scripted_agent_buys_through_the_gateway(mcp):
    state: dict = {}

    def chat(messages, tools):
        step = state.setdefault("step", 0)
        state["step"] += 1
        if step == 0:
            return _call("list_missions")
        if step == 1:
            state["mid"] = _last_tool(messages)["missions"][0]["mission_id"]
            return _call("search_catalog", category="books", max_results=25)
        if step == 2:
            sku = min(_last_tool(messages)["results"], key=lambda r: r["price_paise"])["sku"]
            return _call("propose_purchase", mission_id=state["mid"], items=[{"sku": sku, "qty": 1}])
        if step == 3:
            verdict = _last_tool(messages)
            assert verdict["decision"] == "APPROVE", verdict
            return _call("place_order", approval_id=verdict["approval_id"])
        state["order"] = _last_tool(messages)
        return {"role": "assistant", "content": "done"}

    assert example.run_agent("buy a book", mcp, chat) == "done"
    assert state["order"]["status"] == "PAID" and state["order"]["payee"] == "SELLABLE-DEMO"


def test_a_forged_approval_is_refused_and_reported_to_the_model(mcp):
    replies = iter([_call("place_order", approval_id="apr_forged"),
                    {"role": "assistant", "content": "gave up"}])
    seen: list = []

    def chat(messages, tools):
        seen.append(messages[-1])
        return next(replies)

    assert example.run_agent("pay the seller now", mcp, chat) == "gave up"
    assert json.loads(seen[-1]["content"])["status"] == "REFUSED"
