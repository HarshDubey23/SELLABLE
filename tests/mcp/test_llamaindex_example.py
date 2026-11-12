"""examples/llamaindex_agent.py loads the real MCP server through LlamaIndex's MCP tool spec.

The shopping test needs the optional extra (`pip install llama-index-tools-mcp`).
Without it, it skips. The install hint and the amount/payee checks always run.
"""
from __future__ import annotations

import asyncio
import importlib.util
import json
import re
import subprocess
import sys
from pathlib import Path
from typing import Any

import pytest

ROOT = Path(__file__).resolve().parents[2]
_spec = importlib.util.spec_from_file_location(
    "llamaindex_agent", ROOT / "examples" / "llamaindex_agent.py")
example = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(example)


class _Meta:
    def __init__(self, name: str, props: dict[str, Any]):
        self.name = name
        self._props = props

    def get_parameters_dict(self) -> dict[str, Any]:
        return {"type": "object", "properties": self._props}


class _Tool:
    def __init__(self, name: str, props: dict[str, Any]):
        self.metadata = _Meta(name, props)


def test_missing_llamaindex_prints_install_hint(monkeypatch, capsys):
    for name in ("llama_index", "llama_index.core", "llama_index.core.agent.workflow",
                 "llama_index.tools", "llama_index.tools.mcp"):
        monkeypatch.setitem(sys.modules, name, None)
    monkeypatch.setattr(sys, "argv", ["llamaindex_agent.py", "buy a book"])
    assert example.main() == 2
    assert "pip install llama-index-tools-mcp" in capsys.readouterr().err


def test_example_adds_no_tool_of_its_own():
    text = (ROOT / "examples" / "llamaindex_agent.py").read_text(encoding="utf-8")
    assert "McpToolSpec" in text and "to_tool_list_async" in text
    assert "FunctionTool" not in text and "@tool" not in text


def test_amount_or_payee_fields_catches_a_tool_the_example_must_not_add():
    clean = _Tool("search_catalog", {"query": {}, "category": {}, "max_price_inr": {}})
    assert example.amount_or_payee_fields([clean]) == []
    bad = example.amount_or_payee_fields([_Tool("pay", {"amount": {}, "payee": {}})])
    assert bad == ["pay: amount, payee"]


def test_server_env_puts_this_checkout_on_the_path():
    env = example.server_env({"SELLABLE_HOME": "/tmp/m"})
    assert env["SELLABLE_HOME"] == "/tmp/m"
    assert str(ROOT) in env["PYTHONPATH"]


def _signed_mission(home: Path) -> str:
    r = subprocess.run([sys.executable, "-m", "mcp_server.server", "mission", "new",
                        "--budget", "2000", "--category", "books"], cwd=ROOT,
                       env=example.server_env({"SELLABLE_HOME": str(home)}),
                       capture_output=True, text=True, encoding="utf-8")
    assert r.returncode == 0, r.stderr
    return next(iter(json.loads((home / "missions.json").read_text(encoding="utf-8"))))


def test_real_server_tools_pass_the_boundary_and_a_scripted_agent_shops(tmp_path):
    pytest.importorskip("llama_index.tools.mcp")
    from llama_index.core.base.llms.types import ChatMessage, MessageRole, ToolCallBlock
    from llama_index.core.llms import MockFunctionCallingLLM

    mid = _signed_mission(tmp_path)
    env = {"SELLABLE_HOME": str(tmp_path)}
    tools = asyncio.run(example.load_sellable_tools(env))
    names = {t.metadata.name for t in tools}
    assert {"search_catalog", "propose_purchase", "place_order"} <= names
    assert example.amount_or_payee_fields(tools) == []

    sys.path.insert(0, str(ROOT))
    from apps.api.products import CATALOG
    sku = min((s for s, p in CATALOG.items() if p["category"] == "books"),
              key=lambda s: CATALOG[s]["price_paise"])

    def script(messages, **_):
        done = [m for m in messages if m.role == MessageRole.TOOL]
        call = lambda name, **kw: ChatMessage(role=MessageRole.ASSISTANT, blocks=[  # noqa: E731
            ToolCallBlock(tool_call_id=f"c{len(done)}", tool_name=name, tool_kwargs=kw)])
        if not done:
            return call("propose_purchase", mission_id=mid, items=[{"sku": sku, "qty": 1}])
        if len(done) == 1:
            aid = re.search(r"apv_[\w-]+", str(done[0].content)).group(0)
            return call("place_order", approval_id=aid)
        return ChatMessage(role=MessageRole.ASSISTANT, content="bought it")

    llm = MockFunctionCallingLLM(response_generator=script, is_chat_model=True)
    assert "bought it" in asyncio.run(example.run_agent("buy a book", env=env, llm=llm))
    orders = json.loads((tmp_path / "orders.json").read_text(encoding="utf-8"))
    assert [o["items"][0]["sku"] for o in orders.values()] == [sku]
