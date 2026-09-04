"""GET /trace/{ref} — one purchase, end to end, from durable state only.

This is both the buyer's receipt and the reviewer's favourite artifact,
because they want the same thing: what did the system actually do, in
order, and which part of it was allowed to decide what.

Nothing here is reconstructed from logs or narrated after the fact. Every
row is read back out of SQLite:

    quotes              the server-side price lock
    verdicts            the deterministic R1-R12 decision
    bindings            the single-use approval, and whether it was spent
    payment_executions  the state machine and its timestamps
    orders              the provider order, if one exists
    webhook_events      signature-verified settlement events
    audit_chain         the hash anchors those rows sit under

`ref` may be an execution id, a mission id or a provider order id,
because those are the three identifiers a person actually has in hand.

The audit chain stores payload *hashes*, not payloads — that is what
makes it tamper-evident — so this page never claims to show the contents
of an audit entry. It shows the row the entry commits to, and the hash
you can check it against.
"""
from __future__ import annotations

import html
import json
from typing import Any

from fastapi import APIRouter, HTTPException
from fastapi.responses import HTMLResponse

from ..store import db as store
from .shell import FOOTER, PROVIDER_BADGE_JS, head, nav

router = APIRouter()


# --------------------------------------------------------------- lookup

def _resolve(ref: str) -> dict[str, Any] | None:
    """Find the execution row from any of the three ids a person may have."""
    row = store.query_one(
        "SELECT * FROM payment_executions WHERE execution_id = ?", (ref,))
    if row:
        return row
    row = store.query_one(
        "SELECT * FROM payment_executions WHERE remote_order_id = ? "
        "ORDER BY created_at DESC LIMIT 1", (ref,))
    if row:
        return row
    return store.query_one(
        "SELECT * FROM payment_executions WHERE mission_id = ? "
        "ORDER BY created_at DESC LIMIT 1", (ref,))


def build_trace(ref: str) -> dict[str, Any]:
    """Assemble the causal chain for one purchase. Read-only."""
    from ..audit import chain as audit_chain
    from ..products import CATALOG

    execution = _resolve(ref)
    if execution is None:
        raise HTTPException(404, detail={
            "error_code": "NO_SUCH_TRACE",
            "message": f"no execution matches {ref!r}",
            "accepts": ["execution_id", "mission_id", "remote_order_id"]})

    quote = store.query_one("SELECT * FROM quotes WHERE quote_id = ?",
                            (execution["quote_id"],))
    verdict = store.query_one(
        "SELECT * FROM verdicts WHERE seq = ?", (execution["approve_seq"],))
    binding = store.query_one(
        "SELECT * FROM bindings WHERE seq = ?", (execution["approve_seq"],))
    order = None
    if execution["remote_order_id"]:
        order = store.query_one("SELECT * FROM orders WHERE order_id = ?",
                                (execution["remote_order_id"],))
    events = store.query(
        "SELECT * FROM webhook_events WHERE order_id = ? ORDER BY received_at",
        (execution["remote_order_id"] or "",))

    items: list[dict[str, Any]] = []
    if quote and quote["items"]:
        try:
            for it in json.loads(quote["items"]):
                sku = it.get("sku", "")
                cat = CATALOG.get(sku, {})
                items.append({
                    "sku": sku,
                    "qty": it.get("qty", 1),
                    "name": cat.get("name", sku),
                    "category": cat.get("category"),
                    "catalog_price_paise": cat.get("price_paise"),
                })
        except (ValueError, TypeError):
            items = []

    # The audit rows these facts are committed under. We show the anchor,
    # not a decoded payload: the chain deliberately keeps only hashes.
    anchors = [e for e in audit_chain.entries()
               if e["seq"] == execution["approve_seq"]]
    chain_ok, chain_reason = audit_chain.verify_strict()

    return {
        "ref": ref,
        "execution": dict(execution),
        "quote": dict(quote) if quote else None,
        "items": items,
        "gateway_verdict": dict(verdict) if verdict else None,
        "approval_binding": dict(binding) if binding else None,
        "order": dict(order) if order else None,
        "webhook_events": [dict(e) for e in events],
        "audit_anchors": anchors,
        "audit_chain_verified": chain_ok,
        "audit_chain_reason": chain_reason,
        "price_authority": ("every amount on this page is the server-side "
                            "catalog price, re-derived at quote time. No "
                            "model and no web listing can set it."),
    }


# -------------------------------------------------------------- render

_STATE_MEANING = {
    "APPROVED": ("Authorization exists. Nothing has been sent to a payment "
                 "provider.", "chip-dim"),
    "EXECUTION_PENDING": ("Preparing to contact the provider.", "chip-dim"),
    "REMOTE_ATTEMPTED": ("The request is in flight. This state was written to "
                         "disk before the call, so a crash here is "
                         "recoverable.", "chip-warn"),
    "EXECUTED": ("The provider accepted the request and returned an order. "
                 "Creating an order is not the same as capturing a payment — "
                 "settlement is only claimed from a signed webhook.",
                 "chip-ok"),
    "FAILED": ("The provider definitively refused, or reconciliation proved "
               "no order exists. No money moved.", "chip-bad"),
    "RECONCILIATION_REQUIRED": ("The outcome is unknown. SELLABLE will not "
                                "guess and will not retry blind; it queries "
                                "the provider for authoritative state.",
                                "chip-warn"),
}


def _esc(v: Any) -> str:
    return html.escape("" if v is None else str(v))


def _rupees(paise: Any) -> str:
    try:
        return f"₹{int(paise) / 100:,.2f}"
    except (TypeError, ValueError):
        return "—"


def _ts(v: Any) -> str:
    import datetime as dt
    try:
        # dt.timezone.utc, not dt.UTC: the latter is 3.11+, and this
        # project supports 3.10.
        return dt.datetime.fromtimestamp(int(v), dt.timezone.utc).strftime(
            "%Y-%m-%d %H:%M:%S UTC")
    except (TypeError, ValueError, OSError):
        return "—"


def _kv(rows: list[tuple[str, str]]) -> str:
    return "".join(
        f'<div class="kv"><span class="kv-k">{_esc(k)}</span>'
        f'<span class="kv-v num">{v}</span></div>'
        for k, v in rows)


def _step(n: int, title: str, surface: str, chip: str, chip_cls: str,
          body: str) -> str:
    return f"""<li class="step">
  <div class="step-rail"><span class="step-n num">{n}</span></div>
  <div class="{surface} step-card">
    <div class="step-head">
      <h2 class="step-title">{_esc(title)}</h2>
      <span class="chip {chip_cls}">{_esc(chip)}</span>
    </div>
    {body}
  </div>
</li>"""


_CSS = """
.hero{padding:34px 0 10px}
.hero h1{font-size:clamp(24px,3.2vw,34px);font-weight:800;letter-spacing:-.03em;line-height:1.15}
.hero .sub{color:var(--text-mid);margin-top:8px;max-width:62ch}
.ref{font-family:var(--mono);font-size:12.5px;color:var(--text-dim);word-break:break-all;margin-top:10px}
.summary{display:grid;grid-template-columns:repeat(auto-fit,minmax(190px,1fr));gap:12px;margin:22px 0 8px}
.sum-card{background:var(--bg-panel);border:1px solid var(--border);border-left:3px solid var(--teal);border-radius:var(--r-panel);padding:13px 15px}
.sum-k{font-size:11px;font-weight:600;letter-spacing:.07em;text-transform:uppercase;color:var(--text-dim)}
.sum-v{font-family:var(--mono);font-variant-numeric:tabular-nums;font-size:17px;font-weight:650;margin-top:3px;word-break:break-all}
.steps{list-style:none;margin:26px 0 0;padding:0}
.step{display:grid;grid-template-columns:44px 1fr;gap:14px;padding-bottom:16px;position:relative}
.step-rail{display:flex;flex-direction:column;align-items:center}
.step-n{width:30px;height:30px;border-radius:50%;background:var(--bg-raise);border:1px solid var(--border-hi);color:var(--text-hi);
  display:flex;align-items:center;justify-content:center;font-size:12.5px;font-weight:700;flex-shrink:0}
.step:not(:last-child) .step-rail::after{content:"";flex:1;width:2px;background:var(--border);margin-top:6px}
.step-card{width:100%}
.step-head{display:flex;align-items:center;justify-content:space-between;gap:12px;margin-bottom:10px;flex-wrap:wrap}
.step-title{font-size:15.5px;font-weight:700;letter-spacing:-.015em}
.note{font-size:13px;color:var(--text-mid);margin-bottom:10px}
.kv{display:flex;justify-content:space-between;gap:16px;padding:5px 0;border-bottom:1px dotted var(--border);font-size:13px}
.kv:last-child{border-bottom:none}
.kv-k{color:var(--text-mid);flex-shrink:0}
.kv-v{text-align:right;word-break:break-all;font-size:12.5px}
.hashline{font-family:var(--mono);font-size:11.5px;color:var(--text-dim);word-break:break-all;margin-top:8px}
.empty{color:var(--text-dim);font-size:13px}
@media (max-width:640px){.step{grid-template-columns:32px 1fr;gap:10px}.step-n{width:26px;height:26px;font-size:11px}}
"""


def render_trace(data: dict[str, Any]) -> str:
    ex = data["execution"]
    state = ex["state"]
    meaning, chip_cls = _STATE_MEANING.get(
        state, ("Unrecognised state.", "chip-dim"))

    # ---- summary strip -------------------------------------------------
    lines = " ".join(
        f'{_esc(i["name"])} ×{i["qty"]}' for i in data["items"]) or "—"
    summary = f"""<div class="summary">
  <div class="sum-card"><div class="sum-k">Amount</div>
    <div class="sum-v">{_rupees(ex["amount_paise"])}</div></div>
  <div class="sum-card"><div class="sum-k">Execution state</div>
    <div class="sum-v">{_esc(state)}</div></div>
  <div class="sum-card"><div class="sum-k">Provider</div>
    <div class="sum-v">{_esc(ex["provider"])}</div></div>
  <div class="sum-card"><div class="sum-k">Attempts</div>
    <div class="sum-v">{_esc(ex["attempts"])}</div></div>
</div>"""

    steps: list[str] = []
    n = 0

    # 1 — intent
    n += 1
    steps.append(_step(
        n, "Intent", "advisory", "buyer intent", "chip-violet",
        '<p class="note">What the buyer asked for. A model turns this into a '
        'SKU and a quantity — and only a SKU and a quantity. It never '
        'proposes an amount.</p>'
        + _kv([("mission", _esc(ex["mission_id"])),
               ("cart", _esc(lines))])))

    # 2 — quote
    n += 1
    q = data["quote"]
    if q:
        item_rows = [
            (f'{i["sku"]} ×{i["qty"]}',
             _rupees(i["catalog_price_paise"]) if i["catalog_price_paise"]
             is not None else "not in catalog")
            for i in data["items"]]
        body = ('<p class="note">The server re-derived every price from its '
                'own catalog and signed the total. Any amount supplied by the '
                'client, by a model, or by a web listing was discarded here.'
                '</p>'
                + _kv(item_rows + [
                    ("quote total", _rupees(q["total_paise"])),
                    ("quote id", _esc(q["quote_id"])),
                    ("signature", _esc(str(q["signature"])[:32]) + "…"),
                    ("expires", _ts(q["expires_at"]))]))
    else:
        body = '<p class="empty">Quote row not found for this execution.</p>'
    steps.append(_step(n, "Server-side pricing", "authoritative",
                       "server-authoritative", "chip-ok", body))

    # 3 — gateway
    n += 1
    v = data["gateway_verdict"]
    if v:
        decided = v["decision"]
        body = ('<p class="note">Twelve deterministic rules, no model in the '
                'path. The same inputs always produce the same verdict.</p>'
                + _kv([("decision", _esc(decided)),
                       ("rule", _esc(v["rule_id"] or "— all rules passed")),
                       ("reason", _esc(v["reason"] or "—")),
                       ("proposal hash", _esc(v["proposal_hash"]))]))
        gchip = "approved" if decided == "APPROVE" else "rejected"
        gcls = "chip-ok" if decided == "APPROVE" else "chip-bad"
    else:
        body = ('<p class="empty">No verdict row is stored for approve_seq '
                f'{_esc(ex["approve_seq"])}.</p>')
        gchip, gcls = "unknown", "chip-dim"
    steps.append(_step(n, "Deterministic policy gateway · R1–R12",
                       "authoritative", gchip, gcls, body))

    # 4 — binding
    n += 1
    b = data["approval_binding"]
    if b:
        spent = b["consumed_at"] is not None
        body = ('<p class="note">The approval is bound to this exact cart: '
                'mission, proposal hash, quote, amount, currency and SKU set. '
                'It is single-use, so replaying it cannot open a second '
                'payment.</p>'
                + _kv([("bound skus", _esc(b["skus"])),
                       ("bound amount", _rupees(b["amount_paise"])),
                       ("issued", _ts(b["issued_at"])),
                       ("expires", _ts(b["expires_at"])),
                       ("consumed",
                        _ts(b["consumed_at"]) if spent else "not consumed")]))
        bchip = "spent once" if spent else "unspent"
        bcls = "chip-ok" if spent else "chip-dim"
    else:
        body = '<p class="empty">No approval binding row for this sequence.</p>'
        bchip, bcls = "none", "chip-dim"
    steps.append(_step(n, "Cryptographic approval binding", "authoritative",
                       bchip, bcls, body))

    # 5 — execution
    n += 1
    body = (f'<p class="note">{_esc(meaning)}</p>'
            + _kv([("state", _esc(state)),
                   ("execution id", _esc(ex["execution_id"])),
                   ("idempotency key", _esc(ex["idempotency_key"])),
                   ("opened", _ts(ex["created_at"])),
                   ("updated", _ts(ex["updated_at"])),
                   ("reconciled",
                    _ts(ex["reconciled_at"]) if ex["reconciled_at"] else "—"),
                   ("last error", _esc(ex["last_error"] or "—"))]))
    steps.append(_step(n, "Execution state machine", "authoritative",
                       _esc(state), chip_cls, body))

    # 6 — provider order
    n += 1
    o = data["order"]
    if o:
        body = ('<p class="note">The order the provider actually returned. An '
                'order is an intent to collect, not a collected payment.</p>'
                + _kv([("order id", _esc(o["order_id"])),
                       ("amount", _rupees(o["amount_paise"])),
                       ("provider status", _esc(o["status"])),
                       ("created", _ts(o["created_at"]))]))
        ochip, ocls = "order exists", "chip-ok"
    else:
        body = ('<p class="empty">No provider order is recorded. Nothing was '
                'collected and nothing is claimed.</p>')
        ochip, ocls = "no order", "chip-dim"
    steps.append(_step(n, "Payment provider", "authoritative", ochip, ocls,
                       body))

    # 7 — settlement
    n += 1
    evs = data["webhook_events"]
    if evs:
        body = ('<p class="note">Settlement is only ever claimed from a '
                'webhook whose HMAC signature verified. Duplicate event ids '
                'are ignored.</p>'
                + _kv([(f'{_esc(e["event_type"])} · {_esc(e["event_id"])}',
                        f'{_esc(e["status"])} · {_ts(e["received_at"])}')
                       for e in evs]))
        schip, scls = "settled", "chip-ok"
    else:
        body = ('<p class="empty">No signature-verified settlement event has '
                'been received for this order.</p>')
        schip, scls = "no settlement event", "chip-dim"
    steps.append(_step(n, "Settlement", "authoritative", schip, scls, body))

    # 8 — audit anchor
    n += 1
    anchors = data["audit_anchors"]
    anchor_rows = [
        (f'seq {a["seq"]} · {_esc(a["actor"])}/{_esc(a["action"])}',
         _esc(a.get("hash", "")[:24]) + "…") for a in anchors]
    verified = data["audit_chain_verified"]
    body = ('<p class="note">The chain stores payload hashes, not payloads — '
            'that is what makes it tamper-evident. Recomputing any entry from '
            'its predecessor proves nothing above was edited after the fact.'
            '</p>'
            + _kv(anchor_rows or [("anchor", "no entry at this sequence")])
            + f'<div class="hashline">verify_strict → '
              f'{"VERIFIED" if verified else "BROKEN"} · '
              f'{_esc(data["audit_chain_reason"])}</div>')
    steps.append(_step(
        n, "Tamper-evident audit chain", "authoritative",
        "verified" if verified else "broken",
        "chip-ok" if verified else "chip-bad", body))

    return f"""{head(f"SELLABLE — trace {ex['execution_id'][:16]}", _CSS)}
{nav("")}
<main class="wrap">
  <section class="hero">
    <h1>Purchase trace</h1>
    <p class="sub">Every step below is read back out of durable storage, in
      order. Violet, dashed panels are advisory — a model or the open web
      produced them. Ink-ruled panels are server-authoritative.</p>
    <div class="ref">{_esc(ex["execution_id"])} · mission {_esc(ex["mission_id"])}</div>
  </section>
  {summary}
  <ol class="steps">
    {"".join(steps)}
  </ol>
  <p class="note" style="margin-top:18px">
    Machine-readable version of this page:
    <a href="/api/v1/trace/{_esc(ex['execution_id'])}" target="_blank"
       rel="noopener">/api/v1/trace/{_esc(ex['execution_id'])}</a>
  </p>
</main>
{FOOTER}
<script>{PROVIDER_BADGE_JS}</script>
</body>
</html>"""


@router.get("/trace/{ref}", response_class=HTMLResponse)
async def trace_page(ref: str) -> HTMLResponse:
    return HTMLResponse(render_trace(build_trace(ref)))


@router.get("/api/v1/trace/{ref}")
async def trace_json(ref: str) -> dict[str, Any]:
    """The same causal chain as JSON, for anyone who would rather read it
    with a tool than with their eyes."""
    return build_trace(ref)
