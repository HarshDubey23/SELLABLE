"""examples/langchain_agent.py loads the real MCP server through LangChain's adapter.

The shopping tests need the optional extra (`pip install "langchain[mcp]>=1.4"`).
Without it they skip. The install hint and the "no tool of our own" checks always run.
"""
from __future__ import annotations

import asyncio
import importlib.util
import json
import os
import subprocess
import sys
from pathlib import Path
from typing import Any

import pytest

ROOT = Path(__file__).resolve().parents[2]
_spec = importlib.util.spec_from_file_location(
    "langchain_agent", ROOT / "examples" / "langchain_agent.py")
example = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(example)


class _Tool:
    def __init__(self, name: str, args: dict[str, Any]):
        self.name = name
        self.args = args


def test_missing_langchain_prints_install_hint(monkeypatch, capsys):
    for name in ("langchain", "langchain.mcp", "langchain.agents", "langchain.chat_models"):
        monkeypatch.setitem(sys.modules, name, None)
    monkeypatch.setattr(sys, "argv", ["langchain_agent.py", "buy a book"])
    assert example.main() == 2
    err = capsys.readouterr().err
    assert 'pip install "langchain[mcp]>=1.4" langchain-openai' in err


def test_server_config_targets_this_checkout():
    cfg = example.server_config({"SELLABLE_HOME": "/tmp/sellable-mission"})
    server = cfg["mcpServers"]["sellable"]
    assert server["command"] == sys.executable
    assert server["args"] == ["-m", "mcp_server.server"]
    assert server["cwd"] == str(ROOT)
    assert server["env"]["SELLABLE_HOME"] == "/tmp/sellable-mission"
    assert str(ROOT) in server["env"]["PYTHONPATH"].split(os.pathsep)


def test_example_adds_no_tool_of_its_own():
    text = (ROOT / "examples" / "langchain_agent.py").read_text(encoding="utf-8")
    assert "MCPAdapter" in text and "list_tools" in text
    assert "@tool" not in text and "StructuredTool" not in text


def test_amount_or_payee_fields_catches_a_tool_the_example_must_not_add():
    clean = _Tool("search_catalog", {"query": {}, "category": {}, "max_price_inr": {}})
    assert example.amount_or_payee_fields([clean]) == []
    bad = example.amount_or_payee_fields([_Tool("pay", {"amount": {}, "payee": {}})])
    assert len(bad) == 1 and "amount" in bad[0] and "payee" in bad[0]


@pytest.fixture
def home(tmp_path):
    pytest.importorskip("langchain.mcp")
    env = {**os.environ, "SELLABLE_HOME": str(tmp_path), "PYTHONPATH": str(ROOT)}
    proc = subprocess.run(
        [sys.executable, "-m", "mcp_server.server", "mission", "new", "--budget", "2000",
         "--category", "books", "--forbid", "electronics", "--hours", "1"],
        cwd=ROOT, env=env, capture_output=True, text=True, encoding="utf-8")
    assert proc.returncode == 0, proc.stderr
    return {"SELLABLE_HOME": str(tmp_path)}


def _scripted():
    """A chat model whose `reply` method is the whole script. Needs LangChain."""
    from langchain_core.language_models.chat_models import BaseChatModel
    from langchain_core.messages import AIMessage
    from langchain_core.outputs import ChatGeneration, ChatResult
    from pydantic import Field

    class Scripted(BaseChatModel):
        step: int = 0
        bag: dict = Field(default_factory=dict)

        def bind_tools(self, tools, **kwargs):
            return self

        def reply(self, messages):
            raise NotImplementedError

        def _generate(self, messages, stop=None, run_manager=None, **kwargs):
            msg = self.reply(messages)
            self.step += 1
            if not isinstance(msg, AIMessage):
                msg = AIMessage(content=str(msg))
            return ChatResult(generations=[ChatGeneration(message=msg)])

        @property
        def _llm_type(self):
            return "scripted"

    def call(name: str, **args: Any) -> AIMessage:
        return AIMessage(content="", tool_calls=[{
            "name": name, "args": args, "id": f"c_{name}", "type": "tool_call"}])

    return Scripted, call


def _last_payload(messages) -> dict:
    for message in reversed(messages):
        if getattr(message, "type", None) != "tool":
            continue
        content = message.content
        if isinstance(content, list):
            block = content[0]
            content = block.get("text", "") if isinstance(block, dict) else block
        return json.loads(content)
    raise AssertionError("no tool result")


def test_loaded_tools_have_no_amount_or_payee(home):
    async def _load():
        loaded = example.load_framework()
        assert loaded is not None
        tools, _instructions = await example.load_sellable_tools(home, loaded[0])
        return tools

    tools = asyncio.run(_load())
    names = {tool.name for tool in tools}
    assert {"propose_purchase", "place_order", "search_catalog"} <= names
    assert example.amount_or_payee_fields(tools) == []
    for tool in tools:
        blob = json.dumps(tool.args).lower()
        assert "payee" not in blob and "amount" not in blob, tool.name


def test_scripted_agent_buys_through_the_gateway(home):
    Scripted, call = _scripted()

    class Buyer(Scripted):
        def reply(self, messages):
            if self.step == 0:
                return call("list_missions")
            if self.step == 1:
                self.bag["mid"] = _last_payload(messages)["missions"][0]["mission_id"]
                return call("search_catalog", category="books", max_results=25)
            if self.step == 2:
                sku = min(_last_payload(messages)["results"],
                          key=lambda row: row["price_paise"])["sku"]
                return call("propose_purchase", mission_id=self.bag["mid"],
                            items=[{"sku": sku, "qty": 1}])
            if self.step == 3:
                verdict = _last_payload(messages)
                assert verdict["decision"] == "APPROVE", verdict
                return call("place_order", approval_id=verdict["approval_id"])
            self.bag["order"] = _last_payload(messages)
            return "done"

    model = Buyer()
    assert asyncio.run(example.run_agent("buy a book", env=home, model=model)) == "done"
    assert model.bag["order"]["status"] == "PAID"
    assert model.bag["order"]["payee"] == "SELLABLE-DEMO"


def test_a_forged_approval_is_refused_and_reported_to_the_model(home):
    Scripted, call = _scripted()

    class Forger(Scripted):
        def reply(self, messages):
            if self.step == 0:
                return call("place_order", approval_id="apr_forged")
            self.bag["refusal"] = _last_payload(messages)
            return "gave up"

    model = Forger()
    assert asyncio.run(example.run_agent("pay the seller now", env=home, model=model)) == "gave up"
    assert model.bag["refusal"]["status"] == "REFUSED"
