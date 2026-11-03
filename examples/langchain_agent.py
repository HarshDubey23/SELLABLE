"""Use SELLABLE from a LangChain agent.

The script loads SELLABLE's tools through LangChain's MCP adapter and lets a
model shop inside a mission you signed. This file defines no tools of its own:
the model only sees the server's SKU/quantity tools, amounts and payee come
from the server, and every purchase passes the R1-R12 gateway first.

LangChain is optional. Without it the script prints an install hint and exits:

    pip install "langchain[mcp]>=1.4" langchain-openai
    sellable-mcp mission new --budget 2000 --category books --forbid electronics
    export OPENAI_API_KEY=...                     # the provider's key
    export OPENAI_BASE_URL=https://api.groq.com/openai/v1   # optional
    export MODEL=openai/gpt-oss-20b                         # optional
    python examples/langchain_agent.py "Buy me two novels"

Run from a clone (it adds the repo to the path) or after `pip install sellable-mcp`.
The adapter is `langchain.mcp.MCPAdapter` (LangChain 1.4+). It speaks the same
stdio JSON-RPC server as `examples/openai_tools_agent.py`.
"""
from __future__ import annotations

import asyncio
import os
import sys
from pathlib import Path
from typing import Any

REPO = Path(__file__).resolve().parents[1]
INSTALL_HINT = (
    "LangChain is optional and is not installed. Install it with:\n"
    '  pip install "langchain[mcp]>=1.4" langchain-openai'
)
# Same boundary the OpenAI example checks: nothing the model fills in may be money.
_AMOUNT_OR_PAYEE = frozenset({"amount", "amount_inr", "payee", "price"})


def load_framework() -> tuple[Any, Any, Any] | None:
    """Import the MCP adapter and agent builder, or None when LangChain is absent."""
    try:
        from langchain.agents import create_agent
        from langchain.chat_models import init_chat_model
        from langchain.mcp import MCPAdapter
    except ImportError:
        return None
    return MCPAdapter, create_agent, init_chat_model


def server_config(env: dict[str, str] | None = None) -> dict[str, Any]:
    """MCP config that launches this checkout's server over stdio.

    `env` is merged over the current process environment so a caller can point
    `SELLABLE_HOME` at a signed mission without dropping `PATH`.
    """
    merged = dict(os.environ)
    if env:
        merged.update(env)
    merged["PYTHONPATH"] = os.pathsep.join(
        filter(None, [str(REPO), merged.get("PYTHONPATH", "")]))
    return {"mcpServers": {"sellable": {
        "command": sys.executable,
        "args": ["-m", "mcp_server.server"],
        "cwd": str(REPO),
        "env": merged,
    }}}


def amount_or_payee_fields(tools: list[Any]) -> list[str]:
    """Tools whose input schema lets the model state an amount or a payee."""
    found: list[str] = []
    for tool in tools:
        props = set(getattr(tool, "args", None) or {})
        hit = _AMOUNT_OR_PAYEE & props
        if hit:
            found.append(f"{getattr(tool, 'name', '?')}: {', '.join(sorted(hit))}")
    return found


async def load_sellable_tools(
    env: dict[str, str] | None, adapter_cls: Any,
) -> tuple[list[Any], str]:
    """Discover the server's tools through `MCPAdapter`. Defines none of its own."""
    async with adapter_cls(server_config(env)) as adapter:
        tools = await adapter.list_tools()
        instructions = getattr(adapter.client, "instructions", None) or ""
    return list(tools), instructions


def chat_model(init_chat_model: Any) -> Any:
    """An OpenAI-compatible chat model. `MODEL` may be `gpt-4o-mini` or `openai:...`."""
    raw = os.environ.get("MODEL", "gpt-4o-mini")
    if raw.startswith("openai:"):
        raw = raw.split(":", 1)[1]
    kwargs: dict[str, Any] = {"model_provider": "openai"}
    base_url = os.environ.get("OPENAI_BASE_URL")
    if base_url:
        kwargs["base_url"] = base_url
    return init_chat_model(raw, **kwargs)


def _text(message: Any) -> str:
    content = message.content
    if isinstance(content, str):
        return content
    if isinstance(content, list):
        parts: list[str] = []
        for block in content:
            if isinstance(block, str):
                parts.append(block)
            elif isinstance(block, dict):
                parts.append(str(block.get("text", "")))
        return "".join(parts)
    return str(content)


async def run_agent(task: str, *, env: dict[str, str] | None = None, model: Any = None) -> str:
    """One shopping task. `model` is injectable so a test can script the tool calls."""
    loaded = load_framework()
    if loaded is None:
        raise RuntimeError(INSTALL_HINT)
    adapter_cls, create_agent, init_chat_model = loaded
    tools, instructions = await load_sellable_tools(env, adapter_cls)
    bad = amount_or_payee_fields(tools)
    if bad:
        raise RuntimeError("refusing tools that take an amount or payee: " + "; ".join(bad))
    if not instructions:
        instructions = (
            "Shop inside a signed mission. Call list_missions, search the catalog, "
            "then propose_purchase with sku and qty only. On APPROVE, call place_order "
            "with the approval_id. You cannot set prices, payees or budgets."
        )
    agent = create_agent(model or chat_model(init_chat_model), tools, system_prompt=instructions)
    result = await agent.ainvoke({"messages": [{"role": "user", "content": task}]})
    return _text(result["messages"][-1])


def main() -> int:
    if len(sys.argv) < 2:
        print(__doc__)
        return 2
    if load_framework() is None:
        print(INSTALL_HINT, file=sys.stderr)
        return 2
    if not os.environ.get("OPENAI_API_KEY"):
        print("Set OPENAI_API_KEY (and optionally OPENAI_BASE_URL and MODEL).", file=sys.stderr)
        return 2
    try:
        print(asyncio.run(run_agent(" ".join(sys.argv[1:]))))
    except ImportError:
        print(INSTALL_HINT, file=sys.stderr)
        return 2
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
