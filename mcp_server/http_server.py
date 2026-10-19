"""SELLABLE as a remote MCP server (Streamable HTTP), standard library only.

    sellable-mcp serve --http --port 8765              # private: your missions, needs a token
    sellable-mcp serve --http --sandbox --port 8765    # public demo: every session gets its own
                                                        # throwaway store and a signed demo mission

Transport: MCP Streamable HTTP. Clients POST JSON-RPC to /mcp and get JSON back; the server
returns an Mcp-Session-Id on initialize and expects it on every later request. There is no
server-to-client stream (GET /mcp answers 405), which the spec allows.

Sandbox mode keeps SELLABLE's invariant: the agent still cannot create a mission or name a
price. The *person* configuring the client chooses the demo mission through the URL
(/mcp?budget=2000&category=books&forbid=electronics), and the server signs it with a key that
belongs to that session alone. Payments are always simulated.
"""
from __future__ import annotations

import json
import os
import secrets
import shutil
import tempfile
import threading
import time
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from typing import Any
from urllib.parse import parse_qs, urlparse

from apps.api.products import CATALOG
from mcp_server import server as core
from mcp_server import store

SESSION_TTL_S = 2 * 3600
MAX_SESSIONS = 400
RATE_PER_MIN = 90
MAX_BODY = 256 * 1024
CATEGORIES = sorted({p["category"] for p in CATALOG.values()})

_lock = threading.Lock()          # the store reads SELLABLE_HOME from the environment
_sessions: dict[str, dict[str, Any]] = {}
_hits: dict[str, list[float]] = {}
_stats = {"sessions": 0, "proposals": 0, "rejected": 0, "orders": 0, "started": int(time.time())}


def _sign_demo_mission(home: Path, q: dict[str, list[str]]) -> dict[str, Any]:
    """Sign one mission for this session, the way `sellable-mcp mission new` would."""
    def ints(name: str, default: int, lo: int, hi: int) -> int:
        try:
            return max(lo, min(hi, int(float(q.get(name, [default])[0]))))
        except ValueError:
            return default
    budget_inr = ints("budget", 2000, 100, 100000)
    hours = ints("hours", 2, 1, 24)
    allowed = [c for c in q.get("category", ["books", "stationery"]) if c in CATEGORIES] or ["books"]
    forbid = [c for c in q.get("forbid", ["electronics"]) if c in CATEGORIES and c not in allowed]
    os.environ["SELLABLE_HOME"] = str(home)
    intent = f"Sandbox: buy {', '.join(allowed)} items within ₹{budget_inr:,}"
    return store.new_mission(intent=intent, budget_paise=budget_inr * 100, allowed=allowed,
                             forbidden=forbid, hours=hours, by="sandbox-url")


def _gc() -> None:
    now = time.time()
    for sid in [s for s, v in _sessions.items() if now - v["seen"] > SESSION_TTL_S]:
        shutil.rmtree(_sessions[sid]["home"], ignore_errors=True)
        _sessions.pop(sid, None)


def _limited(ip: str) -> bool:
    now = time.time()
    hits = [t for t in _hits.get(ip, []) if now - t < 60]
    hits.append(now)
    _hits[ip] = hits
    if len(_hits) > 5000:
        _hits.clear()
    return len(hits) > RATE_PER_MIN


def _count(msg: dict[str, Any], resp: str | None) -> None:
    if msg.get("method") != "tools/call" or not resp:
        return
    name = (msg.get("params") or {}).get("name")
    out = (json.loads(resp).get("result") or {}).get("structuredContent") or {}
    if name == "propose_purchase":
        _stats["proposals"] += 1
        if out.get("decision") == "REJECT":
            _stats["rejected"] += 1
    if name == "place_order" and out.get("status") == "PAID":
        _stats["orders"] += 1


class Handler(BaseHTTPRequestHandler):
    server_version = "sellable-mcp/2.1"
    sandbox = False
    token = ""
    origins: tuple[str, ...] = ()

    # ---- helpers ----
    def _ip(self) -> str:
        fwd = self.headers.get("X-Forwarded-For", "")
        return fwd.split(",")[0].strip() or self.client_address[0]

    def _send(self, code: int, body: bytes | str = b"", ctype: str = "application/json",
              headers: dict[str, str] | None = None) -> None:
        data = body.encode("utf-8") if isinstance(body, str) else body
        self.send_response(code)
        self.send_header("Content-Type", ctype)
        self.send_header("Content-Length", str(len(data)))
        self.send_header("Access-Control-Allow-Origin", self._allowed_origin() or "null")
        self.send_header("Access-Control-Expose-Headers", "Mcp-Session-Id")
        self.send_header("X-Content-Type-Options", "nosniff")
        for k, v in (headers or {}).items():
            self.send_header(k, v)
        self.end_headers()
        if self.command != "HEAD":
            self.wfile.write(data)

    def _allowed_origin(self) -> str | None:
        origin = self.headers.get("Origin")
        if not origin:
            return "*"
        if "*" in self.origins or origin in self.origins:
            return origin
        return None

    def _authorized(self) -> bool:
        if self.sandbox or not self.token:
            return True
        auth = self.headers.get("Authorization", "")
        return secrets.compare_digest(auth, f"Bearer {self.token}")

    def log_message(self, fmt: str, *args: Any) -> None:  # keep logs short and free of bodies
        if os.environ.get("SELLABLE_MCP_QUIET") != "1":
            super().log_message(fmt, *args)

    # ---- routes ----
    def do_OPTIONS(self) -> None:
        self._send(204, b"", headers={
            "Access-Control-Allow-Methods": "GET, POST, DELETE, OPTIONS",
            "Access-Control-Allow-Headers": "Content-Type, Authorization, Mcp-Session-Id, "
                                            "Mcp-Protocol-Version, Accept",
            "Access-Control-Max-Age": "600"})

    def do_HEAD(self) -> None:
        self.do_GET()

    def do_GET(self) -> None:
        path = urlparse(self.path).path
        if path == "/health":
            return self._send(200, json.dumps({"ok": True, "sandbox": self.sandbox}))
        if path == "/stats":
            return self._send(200, json.dumps({**_stats, "active_sessions": len(_sessions)}))
        if path == "/mcp":
            return self._send(405, json.dumps({"error": "this server does not open an SSE stream; POST JSON-RPC to /mcp"}),
                              headers={"Allow": "POST, DELETE, OPTIONS"})
        if path in ("/", "/index.html"):
            return self._send(200, landing(self.headers.get("Host", "localhost"), self.sandbox),
                              "text/html; charset=utf-8")
        self._send(404, json.dumps({"error": "not found"}))

    def do_DELETE(self) -> None:
        if urlparse(self.path).path != "/mcp":
            return self._send(404, json.dumps({"error": "not found"}))
        sid = self.headers.get("Mcp-Session-Id", "")
        with _lock:
            s = _sessions.pop(sid, None)
            if s and s.get("home") and self.sandbox:
                shutil.rmtree(s["home"], ignore_errors=True)
        self._send(204 if s else 404, b"")

    def do_POST(self) -> None:
        url = urlparse(self.path)
        if url.path != "/mcp":
            return self._send(404, json.dumps({"error": "not found"}))
        if self._allowed_origin() is None:
            return self._send(403, json.dumps({"error": "origin not allowed"}))
        if not self._authorized():
            return self._send(401, json.dumps({"error": "missing or wrong bearer token"}),
                              headers={"WWW-Authenticate": "Bearer"})
        if _limited(self._ip()):
            return self._send(429, json.dumps({"error": "slow down: too many requests"}),
                              headers={"Retry-After": "30"})
        length = int(self.headers.get("Content-Length") or 0)
        if length <= 0 or length > MAX_BODY:
            return self._send(413 if length > MAX_BODY else 400, json.dumps({"error": "bad body size"}))
        try:
            payload = json.loads(self.rfile.read(length))
        except json.JSONDecodeError:
            return self._send(400, core._error(None, -32700, "parse error"))

        batch = payload if isinstance(payload, list) else [payload]
        if not batch or not all(isinstance(m, dict) for m in batch):
            return self._send(400, core._error(None, -32600, "invalid request"))
        is_init = any(m.get("method") == "initialize" for m in batch)
        sid = self.headers.get("Mcp-Session-Id", "")
        headers: dict[str, str] = {}

        with _lock:
            _gc()
            if is_init:
                if len(_sessions) >= MAX_SESSIONS:
                    return self._send(503, json.dumps({"error": "too many sessions, try again soon"}),
                                      headers={"Retry-After": "60"})
                sid = secrets.token_urlsafe(18)
                home = Path(tempfile.mkdtemp(prefix="sbx_", dir=_root())) if self.sandbox else _private_home()
                _sessions[sid] = {"home": str(home), "seen": time.time(), "created": time.time()}
                if self.sandbox:
                    _sign_demo_mission(home, parse_qs(url.query))
                _stats["sessions"] += 1
                headers["Mcp-Session-Id"] = sid
            elif sid not in _sessions:
                return self._send(404, json.dumps({"error": "unknown or expired session; initialize again"}))
            sess = _sessions[sid]
            sess["seen"] = time.time()
            os.environ["SELLABLE_HOME"] = sess["home"]
            replies = []
            for m in batch:
                resp = core.handle_message(m)
                _count(m, resp)
                if resp is not None:
                    replies.append(json.loads(resp))

        if not replies:  # only notifications or responses
            return self._send(202, b"", headers=headers)
        body = replies if isinstance(payload, list) else replies[0]
        self._send(200, json.dumps(body, ensure_ascii=False), headers=headers)


def _root() -> str:
    r = Path(os.environ.get("SELLABLE_SANDBOX_ROOT") or Path(tempfile.gettempdir()) / "sellable-sandbox")
    r.mkdir(parents=True, exist_ok=True)
    return str(r)


def _private_home() -> Path:
    return Path(os.environ.get("SELLABLE_PRIVATE_HOME") or store.home())


def landing(host: str, sandbox: bool) -> str:
    scheme = "http" if host.startswith(("localhost", "127.")) else "https"
    url = f"{scheme}://{host}/mcp"
    cfg = json.dumps({"mcpServers": {"sellable": {"url": url}}}, indent=2)
    mode = ("Public sandbox. Every connection gets its own signed ₹2,000 mission for books and "
            "stationery, with electronics forbidden. Payments are simulated; nothing is charged."
            if sandbox else "Private server. Requests need the bearer token the operator set.")
    page = (Path(__file__).with_name("landing.html")).read_text(encoding="utf-8")
    return (page.replace("{{URL}}", url).replace("{{CFG}}", cfg.replace("<", "&lt;"))
                .replace("{{MODE}}", mode).replace("{{SANDBOX}}", "true" if sandbox else "false"))


def run(host: str = "127.0.0.1", port: int = 8765, sandbox: bool = False) -> None:
    Handler.sandbox = sandbox
    Handler.token = os.environ.get("SELLABLE_MCP_TOKEN", "")
    Handler.origins = tuple(o.strip() for o in os.environ.get("SELLABLE_ALLOWED_ORIGINS", "*").split(",") if o.strip())
    if not sandbox and not Handler.token and host not in ("127.0.0.1", "localhost"):
        raise SystemExit("Refusing to expose your private missions without a token. "
                         "Set SELLABLE_MCP_TOKEN, bind to 127.0.0.1, or use --sandbox.")
    if sandbox:
        core.INSTRUCTIONS = (core.INSTRUCTIONS + " This is a public sandbox: the mission was signed "
                             "for this session by the person who configured the server URL, and "
                             "payments are simulated.")
    httpd = ThreadingHTTPServer((host, port), Handler)
    print(f"sellable-mcp: Streamable HTTP on http://{host}:{port}/mcp "
          f"({'sandbox' if sandbox else 'private'})", flush=True)
    try:
        httpd.serve_forever()
    except KeyboardInterrupt:
        pass
