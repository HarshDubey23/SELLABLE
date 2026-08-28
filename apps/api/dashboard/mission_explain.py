"""Read-only Mission Explain dashboard — the 'explainable' bar, made visible.

Serves GET /missions and GET /mission/{mission_id}/explain as dependency-free,
server-rendered HTML. Each money action on one page with its rule citation,
reasoning trace, parent link, and honest status. NEVER mutates state; sits
OUTSIDE the money path.
"""
from __future__ import annotations

import html
import json
from typing import Any

from fastapi import APIRouter, HTTPException
from fastapi.responses import HTMLResponse

from ..audit import chain as audit_chain
from ..store import db as store

router = APIRouter()

MONEY_ACTIONS = {
    "order_created", "payment_captured", "payment_failed",
    "payment_attempt_failed", "payment_link_issued", "verdict_emitted",
    "copy_blocked", "mandate_verified", "mandate_rejected",
    "upsell_accepted", "upsell_offered",
}

STYLE = """
:root{--bg:#0f1115;--card:#171a21;--line:#252a35;--ink:#e6e9ef;--mut:#8b93a7;
--ok:#3fb68b;--bad:#e5484d;--money:#f5a623;--link:#6cb6ff}
body{background:var(--bg);color:var(--ink);margin:0;padding:32px 20px;
font:15px/1.55 ui-sans-serif,system-ui,-apple-system,'Segoe UI',Roboto,sans-serif}
.wrap{max-width:960px;margin:0 auto}h1{font-size:22px;margin:0 0 4px}
.mut{color:var(--mut);font-size:13px}
.card{background:var(--card);border:1px solid var(--line);border-left:3px solid var(--mut);
border-radius:10px;padding:14px 16px;margin:10px 0}
.card.ok{border-left-color:var(--ok)}.card.bad{border-left-color:var(--bad)}
.card.money{border-left-color:var(--money)}
.head{display:flex;gap:10px;align-items:baseline;flex-wrap:wrap}
.seq{color:var(--mut);font-size:12px}.atype{font-weight:650}
.chip{background:#1f2530;border:1px solid var(--line);border-radius:999px;
padding:1px 10px;font-size:12px;color:var(--money)}
.chip.ok{color:var(--ok)}.chip.bad{color:var(--bad)}
.parent{color:var(--link);font-size:12px;margin-top:4px}
details{margin-top:8px}summary{cursor:pointer;color:var(--mut);font-size:13px}
pre{background:#0b0d12;border:1px solid var(--line);border-radius:8px;
padding:10px;overflow:auto;font-size:12px}
table{border-collapse:collapse;width:100%}td,th{border-bottom:1px solid var(--line);
padding:8px 10px;text-align:left}a{color:var(--link)}
.badge{display:inline-block;padding:2px 10px;border-radius:999px;font-size:12px;
border:1px solid var(--line)}
.badge.completed{color:var(--ok);border-color:var(--ok)}
.badge.failed,.badge.payment_failed{color:var(--bad);border-color:var(--bad)}
footer{margin-top:28px;color:var(--mut);font-size:12px}
"""


def _esc(v: Any) -> str:
    return html.escape(str(v) if v is not None else "")


def _payload_of(e: dict[str, Any]) -> dict[str, Any]:
    raw = e.get("payload_json")
    if isinstance(raw, dict):
        return raw
    if isinstance(raw, str) and raw.strip():
        try:
            parsed = json.loads(raw)
            return parsed if isinstance(parsed, dict) else {}
        except json.JSONDecodeError:
            return {}
    return {}


def _mission_id_of(e: dict[str, Any]) -> str:
    p = _payload_of(e)
    mid = p.get("mission_id") or e.get("mission_id") or ""
    return str(mid)


def fetch_missions() -> list[dict[str, Any]]:
    rows = store.query(
        "SELECT mission_id, status, MIN(created_at) AS created_at "
        "FROM orders WHERE mission_id IS NOT NULL AND mission_id != '' "
        "GROUP BY mission_id, status ORDER BY created_at DESC"
    )
    seen: dict[str, dict[str, Any]] = {}
    for r in rows:
        mid = r.get("mission_id")
        if not mid or mid in seen:
            continue
        seen[mid] = {"id": mid, "status": r.get("status", ""),
                     "created_at": r.get("created_at", "")}
    for e in audit_chain.entries():
        mid = _mission_id_of(e)
        if mid and mid not in seen:
            seen[mid] = {"id": mid, "status": e.get("action", ""),
                         "created_at": e.get("ts", "")}
    return list(seen.values())


def fetch_mission_entries(mission_id: str) -> list[dict[str, Any]]:
    out = []
    for e in audit_chain.entries():
        p = _payload_of(e)
        blob = {**e, **{k: p[k] for k in p if k not in e}}
        blob["action_type"] = e.get("action")
        blob["status"] = (
            p.get("decision") or p.get("status") or e.get("review_state") or e.get("action")
        )
        blob["rule"] = p.get("rule_id") or e.get("error_code")
        blob["is_money_action"] = e.get("action") in MONEY_ACTIONS
        blob["mission_id"] = _mission_id_of(e)
        if blob["mission_id"] == mission_id:
            out.append(blob)
    return out


def _card(e: dict[str, Any]) -> str:
    seq = _esc(e.get("seq", "?"))
    atype = _esc(e.get("action_type") or e.get("action") or "unknown")
    status = str(e.get("status", "")).lower()
    cls = "ok" if status in ("approved", "captured", "success", "verified", "created",
                             "completed", "allow") else (
          "bad" if status in ("rejected", "failed", "tamper", "block", "blocked") else "")
    if atype in MONEY_ACTIONS or e.get("is_money_action"):
        cls += " money"
    rule = e.get("rule") or e.get("error_code")
    rule_chip = f'<span class="chip">{_esc(rule)}</span>' if rule else ""
    status_chip = (f'<span class="chip {cls.strip()}">{_esc(e.get("status", ""))}</span>'
                   if e.get("status") else "")
    parent = e.get("parent_action_id")
    parent_html = (f'<div class="parent">&#8627; linked from <b>{_esc(parent)}</b></div>'
                   if parent else "")
    meta_bits = [f'{_esc(k)}: <b>{_esc(e[k])}</b>'
                 for k in ("target_entity_id", "idempotency_key", "review_state") if e.get(k)]
    meta_html = f'<div class="mut">{" &middot; ".join(meta_bits)}</div>' if meta_bits else ""
    details = ("<details><summary>full record + reasoning trace</summary><pre>"
               + _esc(json.dumps(e, indent=2, default=str)) + "</pre></details>")
    return (f'<div class="card {cls.strip()}"><div class="head">'
            f'<span class="seq">#{seq}</span><span class="atype">{atype}</span>'
            f'{status_chip}{rule_chip}</div>{meta_html}{parent_html}{details}</div>')


@router.get("/missions", response_class=HTMLResponse)
def missions_index() -> str:
    rows = "".join(
        f'<tr><td><a href="/mission/{_esc(m.get("id"))}/explain">{_esc(m.get("id"))}</a></td>'
        f'<td><span class="badge {_esc(m.get("status", ""))}">{_esc(m.get("status", ""))}</span></td>'
        f'<td>{_esc(m.get("created_at", ""))}</td></tr>' for m in fetch_missions())
    return (f'<html><head><meta charset="utf-8"><style>{STYLE}</style></head>'
            f'<body><div class="wrap"><h1>Missions</h1>'
            f'<p class="mut">Every mission, with its full explain view.</p>'
            f'<table><tr><th>mission</th><th>status</th><th>created</th></tr>{rows}</table>'
            f'</div></body></html>')


@router.get("/mission/{mission_id}/explain", response_class=HTMLResponse)
def mission_explain(mission_id: str) -> str:
    entries = fetch_mission_entries(mission_id)
    if not entries:
        raise HTTPException(404, f"no audit entries for mission {mission_id}")
    cards = "".join(_card(e) for e in entries)
    money_count = sum(1 for e in entries
                      if e.get("action_type") in MONEY_ACTIONS or e.get("is_money_action"))
    return (f'<html><head><meta charset="utf-8"><title>SELLABLE — {_esc(mission_id)}</title>'
            f'<style>{STYLE}</style></head><body><div class="wrap">'
            f'<h1>Mission {_esc(mission_id)}</h1>'
            f'<p class="mut">{len(entries)} audit entries &middot; {money_count} money actions '
            f'&middot; every verdict rule-cited, every action linked to its parent.</p>'
            f'{cards}'
            f'<footer>SELLABLE — the LLM proposes, deterministic policy disposes, '
            f'the audit log remembers. Read-only view; no state mutated.</footer>'
            f'</div></body></html>')
