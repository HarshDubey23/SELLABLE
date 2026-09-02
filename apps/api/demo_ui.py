"""
SELLABLE demo UI — judge-facing single-file pages. GET only.

    /demo                  hub: live number strip, purity certificate, health
    /demo/checkout         conversational checkout with cinematic replay
    /demo/failures         chaos page: six attacks fired live
    /demo/attack_payloads  chaos fixtures built SERVER-side (secrets never
                           reach the browser)
    /demo/tamper-demo      audit-tamper proof on a TEMP COPY (live DB untouched)

Design law: #0B1220 / #111A2E / #1E293B / #E2E8F0 / #94A3B8.
Zero external requests. Zero secrets. Zero mutating endpoints on GET.
Deliberately OUTSIDE apps/api/gateway/ — purity unaffected.
"""
from __future__ import annotations

import html as _html
import copy
import datetime as _dt
import hashlib
import hmac as _hmac
import json
import os
import shutil
import sqlite3
import tempfile
import traceback

from fastapi import APIRouter, Depends, Header, HTTPException, Request
from fastapi.responses import HTMLResponse, JSONResponse

from .deps import require_api_key

router = APIRouter(tags=["demo-ui"])

_REPO = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
_DB_PATH = os.environ.get(
    "SELLABLE_DB_PATH",
    os.environ.get(
        "SELLABLE_DB",
        os.path.join(_REPO, "data", "sellable.db"),
    ),
)
_MISSION_FILE = os.path.join(_REPO, "missions", "happy_path.json")
_API_KEY = os.environ.get("APP_API_KEY", "")


# ===========================================================================
# ADAPT (1): sign_mission() — bridge to apps.api.gateway.mission_verify.
# The real signer returns only the hex digest; we attach it to a copy of
# the mission dict so _attack_payloads can return body dicts with a
# "signature" key exactly like the browser expects.
# ===========================================================================
from apps.api.gateway.mission_verify import (
    dumps as _mv_dumps,
    sign_mission as _mv_sign_mission,
)
from apps.api.audit.chain import verify as verify_chain
import apps.api.audit.chain as chain
from .store import db as store


def _sign_mission(mission: dict) -> dict:
    """Return a deep copy of mission with 'signature' attached."""
    out = copy.deepcopy(mission)
    if "signature" in out:
        del out["signature"]
    canon = _mv_dumps(out)
    out["signature"] = _mv_sign_mission(canon)
    return out


# ---------------------------------------------------------------------------
# Chaos fixtures (server-built so the browser never sees a signing key)
# ---------------------------------------------------------------------------
def _base_mission() -> dict:
    with open(_MISSION_FILE, "r", encoding="utf-8") as f:
        return json.load(f)


def _attack_payloads() -> dict:
    now = _dt.datetime.now(_dt.timezone.utc)
    past = (now - _dt.timedelta(seconds=1)).isoformat()

    # 1 — forged signature: honest mission, one hex char of the HMAC flipped
    m1 = _sign_mission(_base_mission())
    sig = m1.get("signature", "")
    if isinstance(sig, str) and len(sig) > 4:
        m1["signature"] = ("0" if sig[0] != "0" else "1") + sig[1:]

    # 2 — expired mission: internally consistent, but expired 1 s ago
    m2 = dict(_base_mission())
    m2["expires_at"] = int(now.timestamp()) - 1
    m2 = _sign_mission(m2)

    # 3 — inflated total: valid signature, total lies vs catalog truth
    m3 = dict(_base_mission())
    m3["budget_paise"] = int(m3.get("budget_paise", 500000)) + 150000
    m3 = _sign_mission(m3)

    # 4 — category spoof: forbidden SKU relabelled into an allowed category
    m4 = _sign_mission(_base_mission())
    items = m4.get("items") or m4.get("cart") or []
    if items and isinstance(items[0], dict):
        allowed = m4.get("allowed_categories") or ["books"]
        items[0] = {**items[0], "category": allowed[0]}

    # 5 — replayed webhook: payment.captured signed with the WRONG secret
    wh_body = json.dumps({
        "event": "payment.captured",
        "payload": {"payment": {"entity": {
            "id": "pay_CHAOS000001", "order_id": "order_CHAOS000001",
            "amount": 49900, "currency": "INR", "status": "captured"}}},
    }, separators=(",", ":"))
    bad_sig = _hmac.new(b"attacker-controlled-secret",
                        wh_body.encode(), hashlib.sha256).hexdigest()

    return {
        "forged_signature": {"path": "/tools/submit_proposal", "body": m1},
        "expired_mission": {"path": "/tools/submit_proposal", "body": m2},
        "inflated_total": {"path": "/tools/submit_proposal", "body": m3},
        "category_spoof": {"path": "/tools/submit_proposal", "body": m4},
        "webhook_bad_hmac": {"path": "/webhook", "body": wh_body,
                             "headers": {"X-Razorpay-Signature": bad_sig}},
        "expected": {
            "forged_signature": {"rule": "R9",
                                 "caught_by": "tests/gateway/test_r9_signature.py"},
            "expired_mission": {"rule": "R10",
                                "caught_by": "tests/gateway/test_r10_expiry.py"},
            "inflated_total": {"rule": "R3",
                               "caught_by": "tests/gateway/test_r3_price_drift.py"},
            "category_spoof": {"rule": "R5",
                               "caught_by": "tests/gateway/test_r5_category.py"},
            "webhook_bad_hmac": {"status": 400,
                                 "caught_by": "tests/test_webhook_signature.py"},
            "audit_tamper": {"before": True, "after": False,
                             "caught_by": "tests/test_audit_chain.py"},
        },
    }


@router.get("/demo/attack_payloads")
def attack_payloads() -> JSONResponse:
    return JSONResponse(_attack_payloads())


@router.get("/demo/tamper-demo")
def tamper_demo() -> JSONResponse:
    """Tamper with the stored hash of one audit entry in a TEMP COPY.
    The live database is only ever read — never written here."""
    # Resolve DB path dynamically so tests that set SELLABLE_DB_PATH via
    # conftest (throwaway DB) are honoured even if module was imported earlier.
    db_path = store.db_path()
    # Fallback to legacy _DB_PATH if store path missing but legacy exists
    if not os.path.exists(db_path) and os.path.exists(_DB_PATH):
        db_path = _DB_PATH
    if not os.path.exists(db_path):
        before = bool(verify_chain())
        return JSONResponse({
            "ok": False,
            "error": f"db not found: {db_path}",
            "before_verified": before,
            "after_verified": None,
            "conclusion": "chain has no data entries to tamper — live DB empty or not initialized",
            "note": "executed on a temp copy; live database untouched",
            "captured_at_utc": _dt.datetime.now(_dt.timezone.utc).isoformat(),
        })
    tmp_dir = tempfile.mkdtemp(prefix="sellable-tamper-")
    tmp = os.path.join(tmp_dir, "tampered.db")
    after: object = None
    err = ""
    offset = None
    try:
        # Checkpoint the live DB so the main file is self-contained, then copy it.
        store._connect().execute("PRAGMA wal_checkpoint(TRUNCATE)")
        shutil.copyfile(db_path, tmp)
        # Also copy WAL/SHM side-files if they exist so the copy is complete.
        for suffix in ("-wal", "-shm"):
            src = db_path + suffix
            if os.path.exists(src):
                shutil.copyfile(src, tmp + suffix)
        conn = sqlite3.connect(tmp)
        # Tamper the hash of the first non-genesis entry so verify() fails.
        cur = conn.execute(
            "SELECT hash FROM audit_chain WHERE seq=1")
        row = cur.fetchone()
        if not row:
            conn.close()
            shutil.rmtree(tmp_dir, ignore_errors=True)
            return JSONResponse({"ok": False, "error": "no seq=1 entry in chain",
                                 "before_verified": bool(verify_chain()),
                                 "after_verified": None,
                                 "conclusion": "chain has no data entries to tamper",
                                 "note": "executed on a temp copy; live database untouched",
                                 "captured_at_utc": _dt.datetime.now(_dt.timezone.utc).isoformat()})
        orig = row[0]
        tampered = orig[:10] + chr(ord(orig[10]) ^ 0xFF) + orig[11:]
        conn.execute("UPDATE audit_chain SET hash=? WHERE seq=1", (tampered,))
        conn.commit()
        offset = 10
        conn.close()
        after = bool(verify_chain(db_path=tmp))
    except Exception:
        after = None
        err = traceback.format_exc(limit=2)
    finally:
        shutil.rmtree(tmp_dir, ignore_errors=True)
    before = bool(verify_chain())
    halted = (before is True) and (after is False)
    return JSONResponse({
        "before_verified": before,
        "byte_flipped_at_offset": offset,
        "after_verified": after,
        "conclusion": ("money path halted (CHAIN_TAMPER)" if halted else
                       "verifier did not flag the copy — investigate before demo"),
        "note": "executed on a temp copy; live database untouched",
        "error": err,
        "captured_at_utc": _dt.datetime.now(_dt.timezone.utc).isoformat(),
    })


# ---------------------------------------------------------------------------
# shared page shell — plain strings (NOT f-strings: JS braces stay intact)
# ---------------------------------------------------------------------------
_CSS = """
:root{--bg:#0B1220;--panel:#111A2E;--panel-2:#0D1526;--line:#1E293B;
--text:#E2E8F0;--muted:#94A3B8;--ok:#22C55E;--bad:#EF4444;--warn:#F59E0B;
--buyer:#3B82F6;--reasoning:#8B5CF6;--merchant:#A78BFA;--wallet:#2DD4BF;
--gw:#F59E0B;--exec:#22C55E;--mono:ui-monospace,Consolas,Menlo,monospace}
*{box-sizing:border-box;margin:0;padding:0}
html,body{background:var(--bg);color:var(--text);
font:15px/1.55 system-ui,-apple-system,'Segoe UI',Roboto,sans-serif}
a{color:#7DB0FF;text-decoration:none}a:hover{text-decoration:underline}
.wrap{max-width:1240px;margin:0 auto;padding:20px}
.panel{background:var(--panel);border:1px solid var(--line);border-radius:14px;padding:16px}
h1{font-size:27px;line-height:1.25}h2{font-size:16px;margin-bottom:10px}
.muted{color:var(--muted)}.mono{font-family:var(--mono);font-size:12.5px}
.grad{color:#A78BFA}
.badge{display:inline-flex;align-items:center;gap:6px;padding:3px 10px;
border-radius:999px;font-size:12px;border:1px solid var(--line)}
.b-ok{color:var(--ok);border-color:#14532d;background:#0d2818}
.b-bad{color:var(--bad);border-color:#7f1d1d;background:#2a1215}
.b-warn{color:var(--warn);border-color:#78350f;background:#2a1c08}
.btn{background:#1D4ED8;color:#fff;border:0;border-radius:10px;padding:9px 16px;
font-weight:600;cursor:pointer;font-size:14px}
.btn:hover{filter:brightness(1.15)}
.btn.ghost{background:#1B2440;color:var(--text);border:1px solid var(--line)}
.btn.danger{background:#7f1d1d;color:#FCA5A5;border:0}
.chip{display:inline-block;padding:2px 9px;border-radius:999px;font-size:11.5px;border:1px solid var(--line)}
.chip.ok{color:var(--ok);border-color:#14532d}.chip.bad{color:var(--bad);border-color:#7f1d1d}
.chip.warn{color:var(--warn);border-color:#78350f}
.grid{display:grid;gap:14px}
.cards{grid-template-columns:repeat(auto-fit,minmax(260px,1fr))}
.checkout{grid-template-columns:minmax(0,1.4fr) minmax(300px,1fr);align-items:start}
@media(max-width:940px){.checkout{grid-template-columns:1fr}}
header.top{position:sticky;top:0;z-index:50;background:rgba(11,18,32,.93);
backdrop-filter:blur(6px);border-bottom:1px solid var(--line)}
header.top .wrap{display:flex;gap:10px;align-items:center;flex-wrap:wrap;padding-block:10px}
select,input{background:#0D1526;color:var(--text);border:1px solid var(--line);
border-radius:10px;padding:8px 10px;font-size:14px}
.ev{border:1px solid var(--line);border-radius:12px;padding:10px 12px;margin-bottom:10px;
background:var(--panel);animation:evIn 200ms ease-out both}
.ev .head{display:flex;gap:8px;align-items:center;flex-wrap:wrap}
.actor{padding:2px 9px;border-radius:999px;font-size:11.5px;font-weight:700;color:#0B1220}
.kind{font-family:var(--mono);font-size:12px;color:var(--muted)}
.ev .detail{margin-top:6px;font-size:13.5px;color:#CBD5E1;white-space:pre-wrap;word-break:break-word}
.ev.reason .detail{font-style:italic;color:#C4B5FD}
.ev.audit{font-family:var(--mono);font-size:12px}
.ev.reject{border-color:#7f1d1d;background:#1c1013}
.ev.approve{border-color:#14532d;background:#0d2013}
.ev.warn{border-color:#78350f;background:#2a1c08}
.flare{margin-top:8px;border-left:3px solid var(--bad);background:#2a1215;color:#FCA5A5;
padding:7px 10px;border-radius:0 8px 8px 0;font-size:12.5px;animation:pop 200ms ease-out both}
.verdict-badge{display:inline-block;padding:8px 18px;border-radius:12px;font-weight:800;
letter-spacing:.5px;animation:pop 220ms ease-out both}
.v-approve{background:#0d2818;color:var(--ok);border:2px solid #14532d;font-size:20px}
.v-reject{background:#2a1215;color:var(--bad);border:2px solid #7f1d1d;font-size:20px}
.bar{height:10px;border-radius:999px;background:#0D1526;border:1px solid var(--line);overflow:hidden}
.bar>i{display:block;height:100%;background:var(--ok);width:0%;transition:width 300ms}
table{width:100%;border-collapse:collapse;font-size:13px}
th,td{padding:6px 8px;border-bottom:1px solid var(--line);text-align:left}
td.num,th.num{text-align:right;font-family:var(--mono)}
tr.bad{background:#2a1215}
.conn{width:2px;background:var(--line);margin-left:14px;height:12px}
.dots span{animation:blink 1.2s infinite;font-size:18px}
.dots span:nth-child(2){animation-delay:.2s}.dots span:nth-child(3){animation-delay:.4s}
.num{font-size:26px;font-weight:800;font-family:var(--mono)}
.attack{display:flex;flex-direction:column;gap:8px}
.attack pre{background:#0D1526;border:1px solid var(--line);border-radius:8px;padding:8px;
font-size:11.5px;overflow:auto;max-height:96px;white-space:pre-wrap;word-break:break-word}
.result{font-size:13px;display:flex;flex-direction:column;gap:6px}
@keyframes evIn{from{opacity:0;transform:translateY(6px)}to{opacity:1;transform:none}}
@keyframes pop{0%{transform:scale(.9);opacity:.5}100%{transform:scale(1);opacity:1}}
@keyframes blink{0%,80%,100%{opacity:.15}40%{opacity:1}}
@keyframes shimmer{0%{background-position:-200% 0}100%{background-position:200% 0}}
@media(prefers-reduced-motion:reduce){*{animation:none!important;transition:none!important}}
"""

_BASE_JS = """
var $=function(s){return document.querySelector(s)};
var INR=function(p){return(Number(p||0)/100).toLocaleString('en-IN',{style:'currency',currency:'INR'})};
var sleep=function(ms){return new Promise(function(r){setTimeout(r,ms)})};
function esc(s){return(s??'').toString().replace(/[&<>"']/g,m=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[m]))};
async function jget(u){var r=await fetch(u);return{status:r.status,data:await r.json().catch(function(){return null})}};
async function jpost(u,body,headers){var r=await fetch(u,{method:'POST',headers:Object.assign({'Content-Type':'application/json'},headers||{}),body:typeof body==='string'?body:JSON.stringify(body||{})});return{status:r.status,data:await r.json().catch(function(){return null})}};
var ACTOR={buyer:'#3B82F6',llm:'#3B82F6',reasoning:'#8B5CF6',merchant:'#A78BFA',wallet:'#2DD4BF',gateway:'#F59E0B',executor:'#22C55E',simulated_user:'#94A3B8',user:'#94A3B8',system:'#64748B'};
function actorChip(a){var c=ACTOR[(a||'').toLowerCase()]||'#64748B';return'<span class="actor" style="background:'+c+'">'+esc(a||'system')+'</span>'}
function kindIcon(k){var i={tool_call:'&#8594; tool',tool_result:'&#8592; result',llm_call:'thinking',llm_reasoning:'reasoning &#10022;',verdict:'VERDICT',audit:'audit',order_created:'order created',payment_attempt_failed:'payment failed',payment_link_issued:'payment link issued',proposal_submitted:'proposal',recovery_reasoned:'recovery',create_order:'order',mission_started:'mission',payment_captured:'captured',payment_status:'status',upsell_offered:'upsell',cart_consent_given:'cart',intent_mandate_carried:'mandate'};return i[k]||esc(k)};
"""


def _page(title: str, body: str, js: str) -> HTMLResponse:
    doc = ("<!doctype html><html lang=\"en\"><head><meta charset=\"utf-8\">"
           "<meta name=\"viewport\" content=\"width=device-width,initial-scale=1\">"
           "<title>" + _html.escape(title) + " &middot; SELLABLE</title>"
           "<style>" + _CSS + "</style></head><body>" + body +
           "<script>" + _BASE_JS + js + "</script></body></html>")
    return HTMLResponse(doc)


# ===========================================================================
# GET /demo — hub
# ===========================================================================
_HUB_BODY = """
<section class="wrap">
  <h1>The LLM proposes. Deterministic policy disposes.<br>
      <span class="grad">The audit log remembers.</span></h1>
  <p class="muted" style="margin-top:8px;max-width:760px">An agent-safe merchant: an AI buyer
  negotiates and pays, a deterministic gateway gates every money action, and a
  tamper-evident audit chain records everything. Zero LLM in the money path.</p>

  <div class="grid cards" style="margin-top:16px">
    <div class="panel"><span class="num" id="n-skus">&mdash;</span><br>
      <span class="muted">catalog SKUs (with 6 injection plants)</span></div>
    <div class="panel"><span class="num" id="n-rules">&mdash;</span><br>
      <span class="muted">deterministic gateway rules</span></div>
    <div class="panel"><span class="num">6</span><br>
      <span class="muted">prompt-injection plants in the catalog</span></div>
    <div class="panel"><span class="num" id="n-llm">0</span><br>
      <span class="muted">LLM components in the money path</span></div>
  </div>

  <div class="grid cards" style="margin-top:16px">
    <a class="panel" href="/demo/checkout?scenario=injection_i1&amp;autorun=1">
      <h2>&#9654; Start the 60-second judge tour</h2>
      <p class="muted">Live checkout replaying injection_i1: watch the planted payload
      flare red &mdash; and what the gateway does about it.</p></a>
    <a class="panel" href="/demo/checkout"><h2>Live checkout</h2>
      <p class="muted">Six scenarios: happy path, injections I1/I3, payment-failure
      recovery, impossible mission, upsell.</p></a>
    <a class="panel" href="/demo/failures"><h2>Chaos engineering</h2>
      <p class="muted">Six real attacks fired against live endpoints: forged signatures,
      expired missions, tampered ledgers.</p></a>
    <a class="panel" href="/audit/timeline"><h2>Audit timeline</h2>
      <p class="muted">Full append-only history with parent links and a verified chain.</p></a>
  </div>

  <div class="grid cards" style="margin-top:16px">
    <div class="panel"><h2>Purity certificate <span class="muted mono">GET /gateway/proof</span></h2>
      <div id="proof" class="muted">loading&hellip;</div></div>
    <div class="panel"><h2>Rulebook <span class="muted mono">GET /policy</span></h2>
      <div id="rules" class="muted">loading&hellip;</div></div>
    <div class="panel"><h2>Live health <span class="muted mono">polls /health every 5s</span></h2>
      <p><span id="chainBadge" class="badge b-warn">chain verified: &hellip;</span></p>
      <p class="muted" id="healthTxt" style="margin-top:8px">&hellip;</p></div>
  </div>
</section>
"""

_HUB_JS = """
function setBadge(ok){var b=$('#chainBadge');
 b.className='badge '+(ok===true?'b-ok':ok===false?'b-bad':'b-warn');
 b.textContent='chain verified: '+(ok===true?'true':ok===false?'false':'&hellip;');}
async function boot(){
 var h=await jget('/health');
 var p=await jget('/policy');
 var g=await jget('/gateway/proof');
 var rules=(p.data&&(p.data.rules||p.data.policies))||[];
 $('#n-rules').textContent=rules.length||'&mdash;';
 $('#n-llm').textContent=(g.data&&(g.data.llm_imports_detected??0));
 $('#n-skus').textContent=(h.data&&(h.data.sku_count??h.data.skus))||'&mdash;';
 if(g.data){
  $('#proof').innerHTML=
   '<p class="mono">llm_imports_detected: <b>'+esc(g.data.llm_imports_detected)+'</b></p>'+
   '<p class="mono">io_calls_detected: <b>'+esc(g.data.io_calls_detected??'&mdash;')+'</b></p>'+
   '<p class="mono" style="word-break:break-all">source_sha256: '+esc(g.data.source_sha256||'&mdash;')+'</p>'+
   '<p class="muted">'+esc(g.data.generated_at||'')+'</p>';}
 $('#rules').innerHTML='<table><tr><th>Rule</th><th>Phase</th><th>Severity</th></tr>'+
  rules.slice(0,12).map(function(r){return '<tr><td class="mono">'+esc(r.rule_id||r.id)+'</td><td>'+
  esc(r.phase||'&mdash;')+'</td><td>'+esc(r.severity||'&mdash;')+'</td></tr>'}).join('')+'</table>'+
  (rules.length?'':'<p class="muted">/policy shape differs &mdash; ADAPT keys</p>');
 setBadge(h.data&&(h.data.audit_chain_ok??h.data.chain_ok));
 $('#healthTxt').textContent='status '+(h.data&&h.data.status)+' &middot; orders tracked '+
  ((h.data&&h.data.orders_tracked)??'&mdash;');}
setInterval(async function(){var h=await jget('/health');
 setBadge(h.data&&(h.data.audit_chain_ok??h.data.chain_ok));},5000);
boot();
"""


@router.get("/demo", response_class=HTMLResponse)
def demo_hub() -> HTMLResponse:
    return _page("Demo hub", _HUB_BODY, _HUB_JS)


# ===========================================================================
# GET /demo/checkout — cinematic replay
# ===========================================================================
_CHECKOUT_BODY = """
<header class="top"><div class="wrap">
 <strong>SELLABLE</strong><span class="muted">/ live checkout</span>
 <select id="scenario">
  <option value="happy_path">happy_path</option>
  <option value="injection_i1" selected>injection_i1</option>
  <option value="injection_i3">injection_i3</option>
  <option value="payment_failure_recovery">payment_failure_recovery</option>
  <option value="impossible_mission">impossible_mission</option>
  <option value="upsell_demo">upsell_demo</option>
 </select>
 <button class="btn" id="runBtn">Run</button>
 <button class="btn ghost" id="x2">2&times;</button>
 <button class="btn ghost" id="skipBtn">Skip</button>
 <label class="muted" style="font-size:13px"><input type="checkbox" id="moneyOnly">
 money path only</label>
 <span id="pill" class="badge b-warn">idle</span>
</div></header>
<section class="wrap grid checkout" style="margin-top:16px">
 <div class="panel"><h2>Trace <span class="muted mono" id="evCount"></span></h2>
  <div id="feed"></div></div>
 <div style="display:flex;flex-direction:column;gap:14px">
  <div class="panel" id="verdictPanel"><h2>Verdict</h2><p class="muted">pending&hellip;</p></div>
  <div class="panel" id="missionCard"><h2>Mission</h2><p class="muted">run a scenario&hellip;</p></div>
  <div class="panel" id="cartPanel"><h2>Cart (server truth)</h2><p class="muted">&mdash;</p></div>
  <div class="panel" id="auditPanel"><h2>Audit mini-chain</h2><p class="muted">&mdash;</p></div>
 </div>
</section>
"""

_CHECKOUT_JS = """
var INJ=['KIT-001','BOOK-008','LAP-002','SOCK-001','HONY-001','STKY-001','PLNR-002','INJECTION DETECTED','INJECTION_DETECTED'];
var ICON={tool_call:'&#8594; tool',tool_result:'&#8592; result',llm_call:'thinking',
 llm_reasoning:'reasoning &#10022;',verdict:'VERDICT',audit:'audit',
 order_created:'order created',payment_attempt_failed:'payment failed',
 payment_link_issued:'payment link issued'};
var REPLAY_MS=350,SKIP=false,BUSY=false;
var isMoney=function(ev){return/^(tool_|verdict|audit|order|payment|webhook|create_|check_)/.test(ev.kind)};
var isInjection=function(ev){return INJ.some(function(m){return JSON.stringify(ev.data).includes(m)})};

function normalize(data){
 var raw=Array.isArray(data)?data:
  (data&&(data.events||data.trace||(data.trace&&data.trace.events)||data.steps))||[];
 return raw.map(function(e,i){return{
  i:i,seq:e.seq??e.step??i+1,
  kind:String(e.kind??e.type??e.event??'event'),
  actor:String(e.actor??e.source??'system'),
  label:e.label??e.action??e.name??'',
  detail:e.detail??e.summary??e.message??'',
  data:e};});}

function setPill(cls,txt){var p=$('#pill');p.className='badge '+cls;p.innerHTML=txt;}

function render(ev){
 var div=document.createElement('div');
 div.className='ev'+(ev.kind==='llm_reasoning'?' reason':'')+
  (ev.kind==='audit'?' audit':'');
 var inj=isInjection(ev);
 if(inj)div.classList.add('reject');
 var d=ev.data||{};
 if(JSON.stringify(d).toLowerCase().includes('escalat'))div.classList.add('warn');
 var ic=ICON[ev.kind]||esc(ev.kind);
 var detail=esc(ev.detail);
 if(ev.kind==='llm_reasoning')detail+=' <span class="chip" style="color:#C4B5FD">outside money path</span>';
 if(ev.kind==='payment_link_issued'){
  var u=d.short_url||d.payment_link||d.url;
  if(u)detail+='<p style="margin-top:6px"><a href="'+esc(u)+'" target="_blank" rel="noopener">open payment link &#8599;</a> <span class="muted">&middot; expires in 24 h (test mode)</span></p>';}
 div.innerHTML='<div class="head">'+actorChip(ev.actor)+
  '<span class="kind">'+ic+'</span>'+
  (ev.label?'<span class="mono">'+esc(ev.label)+'</span>':'')+'</div>'+
  (detail?'<div class="detail">'+detail+'</div>':'')+
  (inj?'<div class="flare">[!] prompt injection planted in this description &mdash; watch what the gateway does</div>':'');
 $('#feed').appendChild(div);
 $('#feed').scrollTop=$('#feed').scrollHeight;
 $('#evCount').textContent='('+document.querySelectorAll('.ev').length+' events)';
 if(ev.kind==='verdict'||(d.verdict||d.decision))onVerdict(ev);}

function onVerdict(ev){
 var d=ev.data||{};
 var v=String(d.verdict||d.decision||d.status||'').toUpperCase();
 var rule=d.rule_id||d.rule||'';
 if(v==='APPROVE'){
  $('#verdictPanel').innerHTML='<h2>Verdict</h2><span class="verdict-badge v-approve">&#10003; APPROVE</span>';}
 else if(v==='CHAIN_TAMPER'){
  $('#verdictPanel').innerHTML='<h2>Verdict</h2><span class="verdict-badge v-reject">&#10005; CHAIN_TAMPER</span>';}
 else if(v==='REJECT'){
  $('#verdictPanel').innerHTML='<h2>Verdict</h2><span class="verdict-badge v-reject">&#10005; REJECT</span>'+
   '<p class="muted" style="margin-top:8px">rule <b class="mono">'+esc(rule)+'</b> &mdash; <span id="why">loading human explanation&hellip;</span></p>';
  if(['R1','R3'].indexOf(String(d.rule_id))>=0){
   document.querySelectorAll('#cartPanel tbody tr').forEach(function(){/*noop*/});}
  fetch('/tools/explain_reject?seq='+encodeURIComponent(ev.seq))
   .then(function(r){return r.json()}).then(function(x){var w=$('#why');
    if(w)w.textContent=x.explanation||x.reason||x.human||JSON.stringify(x).slice(0,220);})
   .catch(function(){});}
}

function missionCard(m){
 if(!m)return;
 var cap=(Number(m.budget_paise)||0)*(1+Number(m.upsell_cap||0));
 var spent=Number(m.approved_total_paise||0);
 var pct=Math.min(100,cap?spent*100/cap:0);
 var chips=function(a,c){return(a||[]).map(function(x){return'<span class="chip '+c+'">'+esc(x)+'</span>'}).join(' ')};
 $('#missionCard').innerHTML='<h2>Mission</h2>'+
  '<div class="bar"><i style="width:'+pct+'%"></i></div>'+
  '<p class="muted mono" style="margin-top:6px">approved '+INR(spent)+' of cap '+INR(cap)+'</p>'+
  '<p style="margin-top:6px">allowed: '+chips(m.allowed_categories,'ok')+'</p>'+
  '<p>forbidden: '+chips(m.forbidden_categories,'bad')+'</p>'+
  '<p class="muted" style="margin-top:6px">expires in <span id="exp">&hellip;</span></p>'+
  '<p style="margin-top:6px"><span class="badge b-ok">HMAC: verified</span></p>';
 var ts=m.expires_at||m.expiry||m.valid_until;
 if(ts){setInterval(function(){var s=Math.max(0,Math.floor((Date.parse(ts)-Date.now())/1000));
  var el=document.getElementById('exp');if(!el)return;
  el.textContent=s>3600?Math.floor(s/3600)+' h '+(Math.floor(s/60)%60)+' m':Math.floor(s/60)+' m '+(s%60)+' s';},1000);}}

async function cart(items){
 var rows=await Promise.all((items||[]).map(async function(it){
  var r=await jget('/tools/get_product?sku='+encodeURIComponent(it.sku||''));
  var p=(r.data&&r.data.product)||r.data||{};
  return{sku:it.sku,name:p.name||it.name||it.sku,qty:it.qty||1,truth:p.price_paise??it.price_paise??0};}));
 $('#cartPanel').innerHTML='<h2>Cart (server truth)</h2><table><tr><th>SKU</th><th>Item</th>'+
  '<th class="num">Qty</th><th class="num">Price</th></tr>'+
  rows.map(function(r){return'<tr data-sku="'+esc(r.sku)+'"><td class="mono">'+esc(r.sku)+'</td><td>'+
  esc(r.name)+'</td><td class="num">'+r.qty+'</td><td class="num">'+INR(r.truth)+'</td></tr>'}).join('')+'</table>';}

async function auditMini(){
 var r=await jget('/audit');
 var list=((r.data&&(r.data.entries||r.data.events||r.data.items))||Array.isArray(r.data)?r.data:[]);
 var ok=r.data?(r.data.verified??r.data.chain_ok):null;
 $('#auditPanel').innerHTML='<h2>Audit mini-chain <span class="badge '+(ok?'b-ok':'b-bad')+'">chain verified: '+ok+'</span></h2>'+
  list.slice(-8).map(function(e){return'<div class="mono" style="padding:3px 0">#'+esc(e.seq??'?')+' '+
  esc(e.action??e.kind??'')+' <span class="muted">&#8593;parent '+esc(e.parent_action_id||'&mdash;')+'</span></div>'}).join('<div class="conn"></div>');}

function finish(data){
 var st=String((data&&(data.status??data.mission_status??data.state))||'unknown');
 if(st==='completed')setPill('b-ok','&#10003; completed');
 else if(st==='rejected')setPill('b-bad','&#10005; rejected');
 else setPill('b-warn',esc(st));}

async function run(){
 if(BUSY)return;BUSY=true;SKIP=false;
 $('#feed').innerHTML='';$('#evCount').textContent='';
 setPill('b-warn','running <span class="dots"><span>&middot;</span><span>&middot;</span><span>&middot;</span></span>');
 $('#verdictPanel').innerHTML='<h2>Verdict</h2><p class="muted">pending&hellip;</p>';
 var id=$('#scenario').value;
 var r=await jpost('/demo/checkout/api/agent/run-scenario/'+id);
 var events=normalize(r.data);
 for(var ev of events){
  if($('#moneyOnly').checked&&!isMoney(ev))continue;
  if(!SKIP)await sleep(REPLAY_MS);
  render(ev);}
 var d=r.data||{};
 missionCard(d.mission||d.mission_card||(events[events.length-1]&&events[events.length-1].data&&events[events.length-1].data.mission));
 cart(d.cart||d.items||(d.proposal&&d.proposal.items)||[]);
 await auditMini();
 finish(d);
 BUSY=false;}

$('#runBtn').onclick=run;
$('#x2').onclick=function(){REPLAY_MS=(REPLAY_MS===350)?120:350;
 $('#x2').textContent=REPLAY_MS===120?'1&times;':'2&times;';};
$('#skipBtn').onclick=function(){SKIP=true;};
document.addEventListener('keydown',function(e){if(e.key==='r'&&!BUSY)run();});
var qp=new URLSearchParams(location.search);
if(qp.get('scenario'))$('#scenario').value=qp.get('scenario');
if(qp.get('autorun')==='1')run();
"""


@router.get("/demo/checkout", response_class=HTMLResponse)
def demo_checkout() -> HTMLResponse:
    return _page("Live checkout", _CHECKOUT_BODY, _CHECKOUT_JS)


# ===========================================================================
# Server-side proxy — browser calls this, server adds X-API-Key
# ===========================================================================
_ALLOWED_PROXY = {
    "GET",
}
_ALLOWED_PROXY_PATHS = {
    "/health", "/policy", "/gateway/proof", "/audit", "/audit/timeline",
    "/tools/get_product/", "/tools/search_products",
    "/tools/upsell_offers", "/tools/crosssell_offers",
    "/tools/explain_reject", "/ledger", "/agent/scenarios",
}
_ALLOWED_PROXY_POST = {
    "/agent/run-scenario/", "/tools/submit_proposal", "/tools/create_order",
    "/tools/quote", "/tools/check_payment/", "/tools/upsell_offers",
    "/tools/crosssell_offers",
}


def _proxy_allowed(method: str, path: str) -> bool:
    if method == "GET":
        return any(path == p or path.startswith(p) for p in _ALLOWED_PROXY_PATHS)
    if method == "POST":
        return any(path == p or path.startswith(p) for p in _ALLOWED_PROXY_POST)
    return False


@router.post("/demo/checkout/api/{path:path}")
async def demo_proxy(path: str, request: Request,
                     x_api_key: str = Header(default="")) -> JSONResponse:
    """Browser calls this; server forwards with X-API-Key. Whitelist only."""
    if not _API_KEY:
        return JSONResponse({"ok": False, "error": "API key not configured on server"}, status_code=503)
    if not _proxy_allowed(request.method, "/" + path):
        return JSONResponse({"ok": False, "error": "proxy path not allowed"}, status_code=403)
    target = "http://localhost:" + os.environ.get("PORT", "8000") + "/" + path
    import httpx  # local import; the server already depends on it
    headers = {"X-API-Key": _API_KEY}
    body = None
    if request.method == "POST":
        try:
            body = await request.json()
        except Exception:
            body = None
    try:
        async with httpx.AsyncClient(timeout=30.0) as client:
            if request.method == "POST":
                resp = await client.post(target, json=body, headers=headers)
            else:
                resp = await client.get(target, headers=headers)
        return JSONResponse(resp.json(), status_code=resp.status_code)
    except Exception as e:
        return JSONResponse({"ok": False, "error": str(e)}, status_code=502)


# ===========================================================================
# GET /demo/failures — chaos page
# ===========================================================================
_FAILURES_BODY = """
<header class="top"><div class="wrap">
 <strong>SELLABLE</strong><span class="muted">/ chaos engineering</span>
 <span id="score" class="badge b-warn">0/6 attacks neutralized</span>
 <a class="btn ghost" href="/demo">back to hub</a>
</div></header>
<section class="wrap">
 <p class="muted" style="margin:14px 0">Six real attacks against the live server.
 Fixtures are built server-side (you never see a signing key). Every card shows
 expected vs actual, the cited rule, and the test that owns it.</p>
 <div class="grid cards" id="attacks"></div>
</section>
"""

_FAILURES_JS = """
var META=[
 {id:'forged_signature',n:1,name:'Forged mission signature',
  intent:'flips one hex char of the HMAC and hopes the gateway trusts it',expect:'REJECT R9'},
 {id:'expired_mission',n:2,name:'Expired mission',
  intent:'replays a mission whose signature was valid &mdash; one second ago',expect:'REJECT R10'},
 {id:'inflated_total',n:3,name:'Inflated total (price drift)',
  intent:'signs a mission whose total quietly exceeds catalog truth',expect:'REJECT R3'},
 {id:'category_spoof',n:4,name:'Category spoof',
  intent:'relabels a forbidden SKU into an allowed category',expect:'REJECT R5'},
 {id:'webhook_bad_hmac',n:5,name:'Replayed webhook',
  intent:'posts payment.captured with a signature Razorpay never wrote',
  expect:'HTTP 400 + audit rejection entry'},
 {id:'audit_tamper',n:6,name:'Audit tamper',
  intent:'flips ONE byte in a copy of the ledger &mdash; the chain must notice',
  expect:'verify true &#8594; false, money path halted'}];
var FIXTURES=null,passed=0;
function score(){var s=$('#score');
 s.textContent=passed+'/6 attacks neutralized';
 s.className='badge '+(passed===6?'b-ok':'b-warn');}
function cardHTML(a){
 return '<div class="panel attack" id="c-'+a.id+'"><h2>'+a.n+'. '+a.name+'</h2>'+
  '<p class="muted">Attacker intent: '+a.intent+'</p>'+
  '<p>Expected: <span class="badge b-ok">'+a.expect+'</span></p>'+
  '<pre id="p-'+a.id+'" class="muted">fixture loads on first fire&hellip;</pre>'+
  '<div class="result" id="r-'+a.id+'"><button class="btn" onclick="fire(\\''+a.id+'\\')">Fire attack</button></div></div>';}
function toCurl(p){
 var hs=Object.entries(p.headers||{}).map(function(kv){return"-H '"+kv[0]+': '+kv[1]+"'"}).join(' ');
 var b=typeof p.body==='string'?p.body:JSON.stringify(p.body);
 return "curl -X POST "+location.origin+p.path+" -H 'Content-Type: application/json' "+hs+" -d '"+b+"'";}
function attackPassed(a,res){
 if(a.id==='webhook_bad_hmac')return res.status>=400;
 var m=(String(a.expect).match(/R\\d+/g)||[]);
 return JSON.stringify(res.data||{}).includes(m[0]||'@@');}
async function fire(id){
 var a=META.find(function(x){return x.id===id});var box=document.getElementById('r-'+id);
 box.innerHTML='<span class="muted">firing<span class="dots"><span>&middot;</span><span>&middot;</span><span>&middot;</span></span></span>';
 if(!FIXTURES){var r=await jget('/demo/attack_payloads');FIXTURES=r.data;}
 var ok=false;
 if(id==='audit_tamper'){
  var res=await jget('/demo/tamper-demo');var d=res.data||{};
  ok=(d.before_verified===true&&d.after_verified===false);
  document.getElementById('p-'+id).textContent=JSON.stringify(d,null,1).slice(0,600);
  box.innerHTML='<span class="badge '+(ok?'b-ok':'b-bad')+'">'+(ok?'NEUTRALIZED':'CHECK')+'</span>'+
   '<p>before verify: <b>'+d.before_verified+'</b> &#8594; after verify: <b>'+d.after_verified+'</b></p>'+
   '<p class="mono">'+esc(d.conclusion||'')+'</p>'+
   '<p class="muted">'+esc(d.note||'')+'</p>'+
   '<p class="muted mono">caught by: '+esc((FIXTURES.expected||{}).audit_tamper.caught_by||'&mdash;')+
   ' &middot; '+new Date().toISOString()+'</p>'+
   '<button class="btn ghost" onclick="navigator.clipboard.writeText(toCurl(FIXTURES[\\''+id+'\\']))">copy as cURL</button>';}
 else{
  var p=FIXTURES[id];
  document.getElementById('p-'+id).textContent=toCurl(p).slice(0,500);
  var res=typeof p.body==='string'
   ?await jpost(p.path,p.body,p.headers)
   :await jpost(p.path,p.body,p.headers);
  ok=attackPassed(a,res);
  var cited=(JSON.stringify(res.data||{}).match(/R\\d+/g)||[])[0]||'&mdash;';
  box.innerHTML='<span class="badge '+(ok?'b-ok':'b-bad')+'">'+(ok?'NEUTRALIZED':'NOT CAUGHT')+'</span>'+
   '<p>expected: '+a.expect+' &middot; actual: HTTP '+res.status+' '+(cited!=='&mdash;'?'&middot; cited <b class="mono">'+esc(cited)+'</b>':'')+'</p>'+
   '<p class="muted mono" style="word-break:break-all">'+esc(JSON.stringify(res.data||{}).slice(0,220))+'</p>'+
   '<p class="muted mono">caught by: '+esc((FIXTURES.expected||{})[id].caught_by||'&mdash;')+
   ' &middot; '+new Date().toISOString()+'</p>'+
   '<button class="btn ghost" onclick="navigator.clipboard.writeText(toCurl(FIXTURES[\\''+id+'\\']))">copy as cURL</button>';}
 if(ok){passed++;score();}}
document.getElementById('attacks').innerHTML=META.map(cardHTML).join('');
"""


@router.get("/demo/failures", response_class=HTMLResponse)
def demo_failures() -> HTMLResponse:
    return _page("Chaos engineering", _FAILURES_BODY, _FAILURES_JS)



