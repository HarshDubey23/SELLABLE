"""Local state for the SELLABLE MCP server.

Everything lives in one directory (SELLABLE_HOME, default ~/.sellable):

    key            32 random bytes; signs missions. Created by the CLI, never exposed as a tool.
    missions.json  missions the *user* signed with `sellable-mcp mission new`
    approvals.json single-use approvals minted by the gateway (10-minute expiry)
    orders.json    executed orders
    audit.jsonl    hash-chained log of every proposal, verdict and order

The agent talks to the server only through MCP tools, and no tool can create a mission,
change a budget, read the key, or move money without a fresh gateway APPROVE.
"""
from __future__ import annotations

import hashlib
import hmac
import json
import os
import secrets
import time
from pathlib import Path
from typing import Any

from apps.api.gateway.types import Mission, canonical_json

GENESIS = "0" * 64


def home() -> Path:
    p = Path(os.environ.get("SELLABLE_HOME") or Path.home() / ".sellable")
    p.mkdir(parents=True, exist_ok=True)
    return p


def _read(name: str, default: Any) -> Any:
    f = home() / name
    if not f.exists():
        return default
    return json.loads(f.read_text(encoding="utf-8"))


def _write(name: str, data: Any) -> None:
    f = home() / name
    tmp = f.with_suffix(".tmp")
    tmp.write_text(json.dumps(data, indent=2, ensure_ascii=False), encoding="utf-8")
    tmp.replace(f)


# ---- signing key (user custody) -------------------------------------------------------------

def key(create: bool = False) -> bytes | None:
    f = home() / "key"
    if f.exists():
        return f.read_bytes()
    if not create:
        return None
    k = secrets.token_bytes(32)
    f.write_bytes(k)
    try:
        f.chmod(0o600)
    except OSError:
        pass
    return k


def sign(blob: str, k: bytes) -> str:
    return hmac.new(k, blob.encode("utf-8"), hashlib.sha256).hexdigest()


def verify_fn(k: bytes | None):
    def verify(blob: str, sig: str) -> bool:
        return bool(k) and bool(sig) and hmac.compare_digest(sign(blob, k), sig)
    return verify


# ---- missions -----------------------------------------------------------------------------

def missions() -> dict[str, dict[str, Any]]:
    return _read("missions.json", {})


def save_missions(m: dict[str, dict[str, Any]]) -> None:
    _write("missions.json", m)


def new_mission(*, intent: str, budget_paise: int, allowed: list[str], forbidden: list[str],
                hours: float, by: str = "user-cli") -> dict[str, Any]:
    k = key(create=True)
    assert k is not None
    mid = "m_" + secrets.token_hex(6)
    unsigned = Mission(mission_id=mid, intent=intent, budget_paise=int(budget_paise),
                       allowed_categories=tuple(sorted(allowed)),
                       forbidden_categories=tuple(sorted(forbidden)),
                       upsell_cap=1.0, expires_at=int(time.time() + hours * 3600))
    blob = {k_: v for k_, v in vars(unsigned).items() if k_ != "signature"}
    record = {**{k_: (list(v) if isinstance(v, tuple) else v) for k_, v in blob.items()},
              "signature": sign(canonical_json(blob), k), "revoked": False,
              "created_at": int(time.time())}
    m = missions()
    m[mid] = record
    save_missions(m)
    append_audit({"type": "MISSION_SIGNED", "mission_id": mid, "budget_paise": int(budget_paise),
                  "allowed": sorted(allowed), "by": by})
    return record


def mission_obj(rec: dict[str, Any]) -> Mission:
    return Mission(mission_id=rec["mission_id"], intent=rec["intent"],
                   budget_paise=int(rec["budget_paise"]),
                   allowed_categories=tuple(rec["allowed_categories"]),
                   forbidden_categories=tuple(rec["forbidden_categories"]),
                   upsell_cap=float(rec["upsell_cap"]), expires_at=int(rec["expires_at"]),
                   signature=rec["signature"])


def spent_paise(mission_id: str) -> int:
    return sum(o["amount_paise"] for o in orders().values() if o["mission_id"] == mission_id)


# ---- approvals and orders -----------------------------------------------------------------

def approvals() -> dict[str, dict[str, Any]]:
    return _read("approvals.json", {})


def save_approvals(a: dict[str, dict[str, Any]]) -> None:
    _write("approvals.json", a)


def orders() -> dict[str, dict[str, Any]]:
    return _read("orders.json", {})


def save_orders(o: dict[str, dict[str, Any]]) -> None:
    _write("orders.json", o)


def gateway_state() -> dict[str, Any]:
    return _read("gateway_state.json", {"proposal_ts": {}, "aborted_missions": []})


def save_gateway_state(s: dict[str, Any]) -> None:
    _write("gateway_state.json", s)


# ---- hash-chained audit log -----------------------------------------------------------------

def _entry_hash(prev: str, body: dict[str, Any]) -> str:
    return hashlib.sha256((prev + canonical_json(body)).encode("utf-8")).hexdigest()


def audit_entries() -> list[dict[str, Any]]:
    f = home() / "audit.jsonl"
    if not f.exists():
        return []
    return [json.loads(x) for x in f.read_text(encoding="utf-8").splitlines() if x.strip()]


def append_audit(body: dict[str, Any]) -> dict[str, Any]:
    entries = audit_entries()
    prev = entries[-1]["hash"] if entries else GENESIS
    body = {**body, "ts": int(time.time()), "seq": len(entries)}
    entry = {"body": body, "prev": prev, "hash": _entry_hash(prev, body)}
    with (home() / "audit.jsonl").open("a", encoding="utf-8") as f:
        f.write(json.dumps(entry, ensure_ascii=False) + "\n")
    return entry


def verify_audit() -> dict[str, Any]:
    prev = GENESIS
    entries = audit_entries()
    for i, e in enumerate(entries):
        if e["prev"] != prev or e["hash"] != _entry_hash(prev, e["body"]):
            return {"ok": False, "entries": len(entries), "first_bad_seq": i}
        prev = e["hash"]
    return {"ok": True, "entries": len(entries), "head": prev}
