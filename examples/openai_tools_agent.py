"""Use SELLABLE from any OpenAI-compatible chat-completions agent loop.

The script starts the SELLABLE MCP server over stdio, turns its tools into
OpenAI function tools, and lets a model shop inside a mission you signed.
The model only ever sees SKU/quantity tools: amounts and payee come from the
server, and every purchase passes the R1-R12 gateway first.

Standard library only. Works with OpenAI, Groq, OpenRouter, a local vLLM or
Ollama server, or anything else that speaks /chat/completions:

    sellable-mcp mission new --budget 2000 --category books --forbid electronics
    export OPENAI_API_KEY=...                     # the provider's key
    export OPENAI_BASE_URL=https://api.groq.com/openai/v1   # optional
    export MODEL=openai/gpt-oss-20b                         # optional
    python examples/openai_tools_agent.py "Buy me two novels"

Run from a clone (it adds the repo to the path) or after `pip install sellable-mcp`.
"""
from __future__ import annotations

import json
import os
import subprocess
import sys
import urllib.request
from collections.abc import Callable
from pathlib import Path
from typing import Any

REPO = Path(__file__).resolve().parents[1]
Chat = Callable[[list[dict[str, Any]], list[dict[str, Any]]], dict[str, Any]]


class McpStdio:
    """Minimal MCP client: one server subprocess, newline-delimited JSON-RPC."""

    def __init__(self, env: dict[str, str] | None = None):
        env = {**os.environ, **(env or {})}
        env["PYTHONPATH"] = os.pathsep.join(filter(None, [str(REPO), env.get("PYTHONPATH")]))
        self.proc = subprocess.Popen(
            [sys.executable, "-m", "mcp_server.server"], env=env, cwd=REPO,
            stdin=subprocess.PIPE, stdout=subprocess.PIPE, text=True, encoding="utf-8")
        self._id = 0
        self.instructions = self.request("initialize", {
            "protocolVersion": "2025-06-18", "capabilities": {},
            "clientInfo": {"name": "openai-tools-example", "version": "1"},
        }).get("instructions", "")

    def request(self, method: str, params: dict[str, Any] | None = None) -> dict[str, Any]:
        self._id += 1
        assert self.proc.stdin and self.proc.stdout
        self.proc.stdin.write(json.dumps({"jsonrpc": "2.0", "id": self._id, "method": method,
                                          "params": params or {}}) + "\n")
        self.proc.stdin.flush()
        reply = json.loads(self.proc.stdout.readline())
        if "error" in reply:
            raise RuntimeError(reply["error"]["message"])
        return reply["result"]

    def tools(self) -> list[dict[str, Any]]:
        return self.request("tools/list")["tools"]

    def call(self, name: str, arguments: dict[str, Any]) -> str:
        result = self.request("tools/call", {"name": name, "arguments": arguments})
        return result["content"][0]["text"]

    def close(self) -> None:
        if self.proc.stdin:
            self.proc.stdin.close()
        self.proc.wait(timeout=10)


def openai_tools(mcp_tools: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """MCP tool definitions -> OpenAI function-tool definitions (the schemas are already JSON Schema)."""
    return [{"type": "function", "function": {
        "name": t["name"], "description": t.get("description", ""),
        "parameters": t.get("inputSchema") or {"type": "object", "properties": {}},
    }} for t in mcp_tools]


def http_chat(base_url: str, api_key: str, model: str) -> Chat:
    def chat(messages: list[dict[str, Any]], tools: list[dict[str, Any]]) -> dict[str, Any]:
        body = json.dumps({"model": model, "messages": messages, "tools": tools}).encode()
        req = urllib.request.Request(f"{base_url.rstrip('/')}/chat/completions", data=body,
                                     headers={"Authorization": f"Bearer {api_key}",
                                              "Content-Type": "application/json"})
        with urllib.request.urlopen(req, timeout=120) as resp:
            return json.loads(resp.read())["choices"][0]["message"]
    return chat


def run_agent(task: str, mcp: McpStdio, chat: Chat, max_turns: int = 10) -> str:
    """Plain tool-calling loop. Tool errors and gateway refusals go back to the model as text."""
    tools = openai_tools(mcp.tools())
    messages: list[dict[str, Any]] = [{"role": "system", "content": mcp.instructions},
                                      {"role": "user", "content": task}]
    for _ in range(max_turns):
        msg = chat(messages, tools)
        messages.append({k: v for k, v in msg.items() if v is not None})
        calls = msg.get("tool_calls") or []
        if not calls:
            return msg.get("content") or ""
        for call in calls:
            fn = call["function"]
            try:
                args = json.loads(fn.get("arguments") or "{}")
                out = mcp.call(fn["name"], args)
            except (json.JSONDecodeError, RuntimeError) as exc:
                out = f"error: {exc}"
            print(f"  -> {fn['name']}({fn.get('arguments')})", file=sys.stderr)
            messages.append({"role": "tool", "tool_call_id": call["id"], "content": out})
    return "stopped: turn limit reached"


def main() -> int:
    if len(sys.argv) < 2:
        print(__doc__)
        return 2
    key = os.environ.get("OPENAI_API_KEY")
    if not key:
        print("Set OPENAI_API_KEY (and optionally OPENAI_BASE_URL and MODEL).", file=sys.stderr)
        return 2
    chat = http_chat(os.environ.get("OPENAI_BASE_URL", "https://api.openai.com/v1"), key,
                     os.environ.get("MODEL", "gpt-4o-mini"))
    mcp = McpStdio()
    try:
        print(run_agent(" ".join(sys.argv[1:]), mcp, chat))
    finally:
        mcp.close()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
