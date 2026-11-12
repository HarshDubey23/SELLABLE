"""Use SELLABLE from a LlamaIndex agent.

The script loads SELLABLE's tools through LlamaIndex's MCP tool spec and lets a
FunctionAgent shop inside a mission you signed. This file defines no tools of
its own: the model only sees the server's SKU/quantity tools, amounts and payee
come from the server, and every purchase passes the R1-R12 gateway first.

LlamaIndex is optional. Without it the script prints an install hint and exits:

    pip install llama-index-tools-mcp llama-index-llms-openai-like
    sellable-mcp mission new --budget 2000 --category books --forbid electronics
    export OPENAI_API_KEY=...                     # the provider's key
    export OPENAI_BASE_URL=https://api.groq.com/openai/v1   # optional
    export MODEL=openai/gpt-oss-20b                         # optional
    python examples/llamaindex_agent.py "Buy me two novels"

Run from a clone (it adds the repo to the path) or after installing sellable-mcp.
It speaks the same stdio JSON-RPC server as `examples/langchain_agent.py`.
"""
from __future__ import annotations

import asyncio
import os
import sys
from pathlib import Path
from typing import Any

REPO = Path(__file__).resolve().parents[1]
INSTALL_HINT = (
    "LlamaIndex is optional and is not installed. Install it with:\n"
    "  pip install llama-index-tools-mcp llama-index-llms-openai-like"
)
# Same boundary the other examples check: nothing the model fills in may be money.
_AMOUNT_OR_PAYEE = frozenset({"amount", "amount_inr", "payee", "price"})
_INSTRUCTIONS = (
    "Shop inside a signed mission. Call list_missions, search the catalog, "
    "then propose_purchase with sku and qty only. On APPROVE, call place_order "
    "with the approval_id. You cannot set prices, payees or budgets."
)


def load_framework() -> tuple[Any, Any, Any] | None:
    """Import the MCP client, tool spec and agent, or None when LlamaIndex is absent."""
    try:
        from llama_index.core.agent.workflow import FunctionAgent
        from llama_index.tools.mcp import BasicMCPClient, McpToolSpec
    except ImportError:
        return None
    return BasicMCPClient, McpToolSpec, FunctionAgent


def server_env(env: dict[str, str] | None = None) -> dict[str, str]:
    """Environment for this checkout's stdio server. `env` is merged over os.environ."""
    merged = dict(os.environ)
    if env:
        merged.update(env)
    merged["PYTHONPATH"] = os.pathsep.join(
        filter(None, [str(REPO), merged.get("PYTHONPATH", "")]))
    return merged


def amount_or_payee_fields(tools: list[Any]) -> list[str]:
    """Tools whose input schema lets the model state an amount or a payee."""
    found: list[str] = []
    for tool in tools:
        props = set(tool.metadata.get_parameters_dict().get("properties") or {})
        hit = _AMOUNT_OR_PAYEE & props
        if hit:
            found.append(f"{tool.metadata.name}: {', '.join(sorted(hit))}")
    return found


async def load_sellable_tools(env: dict[str, str] | None = None) -> list[Any]:
    """Discover the server's tools through McpToolSpec. Defines none of its own."""
    loaded = load_framework()
    if loaded is None:
        raise RuntimeError(INSTALL_HINT)
    client_cls, spec_cls, _ = loaded
    client = client_cls(sys.executable, args=["-m", "mcp_server.server"], env=server_env(env))
    return list(await spec_cls(client=client).to_tool_list_async())


def chat_model() -> Any:
    """An OpenAI-compatible chat model. `MODEL` may be `gpt-4o-mini` or `openai:...`."""
    from llama_index.llms.openai_like import OpenAILike
    model = os.environ.get("MODEL", "gpt-4o-mini").removeprefix("openai:")
    return OpenAILike(model=model, api_base=os.environ.get("OPENAI_BASE_URL"),
                      api_key=os.environ.get("OPENAI_API_KEY"),
                      is_chat_model=True, is_function_calling_model=True)


async def run_agent(task: str, *, env: dict[str, str] | None = None, llm: Any = None) -> str:
    """One shopping task. `llm` is injectable so a test can script the tool calls."""
    loaded = load_framework()
    if loaded is None:
        raise RuntimeError(INSTALL_HINT)
    tools = await load_sellable_tools(env)
    bad = amount_or_payee_fields(tools)
    if bad:
        raise RuntimeError("refusing tools that take an amount or payee: " + "; ".join(bad))
    agent = loaded[2](tools=tools, llm=llm or chat_model(), system_prompt=_INSTRUCTIONS)
    return str(await agent.run(user_msg=task))


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
