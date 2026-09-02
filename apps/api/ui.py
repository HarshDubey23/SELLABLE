"""Command Center UI — the judge-facing polished frontend.

A single-file dark-theme fintech UI served at GET /. Replaces the older
demo_ui.py for the main surfaces; demo_ui keeps the demo /demo/checkout
cinematic replay page.

Surfaces:
  GET /                  Command Center dashboard
  GET /mission           Live mission runner
  GET /products          Catalog + search
  GET /gateway-ui        R1-R12 rule matrix viewer
  GET /audit-ui          Audit explorer
  GET /attack-ui         Attack Lab

All pages share one CSS+JS bundle. Pages poll /status, /missions,
/missions/{id}/trace, /invariant/money-calls for live state.
"""
from __future__ import annotations

import datetime as _dt
import html as _html_escape
import os

from fastapi import APIRouter, Request
from fastapi.responses import HTMLResponse, JSONResponse

from .audit import chain as audit_chain
from . import config as app_config
from . import money as money_mod
from .gateway.registry import RULE_REGISTRY
from .products import CATALOG
from .tools import orders, quotes
from .webhook.receiver import payment_ledger, processed_event_ids


router = APIRouter(tags=["ui"])


_CSS = """
:root{
  --bg:#0B1220;--panel:#111A2E;--panel-2:#0D1526;--line:#1E293B;
  --text:#E2E8F0;--muted:#94A3B8;--dim:#64748B;
  --ok:#22C55E;--bad:#EF4444;--warn:#F59E0B;--info:#3B82F6;
  --accent:#A78BFA;--accent-2:#2DD4BF;
  --mono:ui-monospace,SFMono-Regular,Consolas,Menlo,monospace;
}
*{box-sizing:border-box;margin:0;padding:0}
html,body{background:var(--bg);color:var(--text);
  font:14px/1.55 system-ui,-apple-system,'Segoe UI',Roboto,sans-serif}
a{color:#7DB0FF;text-decoration:none}a:hover{text-decoration:underline}
.wrap{max-width:1320px;margin:0 auto;padding:24px 24px 60px}
header.top{position:sticky;top:0;z-index:50;background:rgba(11,18,32,.92);
  backdrop-filter:blur(8px);border-bottom:1px solid var(--line)}
header.top .bar{display:flex;gap:14px;align-items:center;flex-wrap:wrap;padding:14px 24px}
header.top .brand{font-weight:700;font-size:16px;letter-spacing:.2px;color:var(--text)}
header.top .brand .accent{color:var(--accent)}
header.top nav{display:flex;gap:6px;flex-wrap:wrap}
header.top nav a{color:var(--muted);padding:6px 10px;border-radius:8px;font-size:13px;
  border:1px solid transparent}
header.top nav a:hover{color:var(--text);background:var(--panel);text-decoration:none}
header.top nav a.active{color:var(--text);background:var(--panel);border-color:var(--line)}
.h1{font-size:30px;font-weight:700;letter-spacing:-.5px;margin-bottom:6px}
.h1 .accent{color:var(--accent)}
.lede{color:var(--muted);max-width:760px;margin-bottom:20px}
.grid{display:grid;gap:14px}
.cards-2{grid-template-columns:repeat(auto-fit,minmax(280px,1fr))}
.cards-3{grid-template-columns:repeat(auto-fit,minmax(220px,1fr))}
.cards-4{grid-template-columns:repeat(auto-fit,minmax(200px,1fr))}
.panel{background:var(--panel);border:1px solid var(--line);border-radius:14px;
  padding:18px 20px}
.panel h2{font-size:13px;color:var(--muted);text-transform:uppercase;
  letter-spacing:.6px;font-weight:600;margin-bottom:10px}
.panel h3{font-size:15px;font-weight:600;margin-bottom:8px}
.muted{color:var(--muted)}
.dim{color:var(--dim)}
.mono{font-family:var(--mono);font-size:12.5px}
.num{font-family:var(--mono);font-weight:700;font-size:22px}
.num.big{font-size:34px;letter-spacing:-1px}
.row{display:flex;gap:10px;align-items:center;flex-wrap:wrap}
.space{flex:1}
.badge{display:inline-flex;align-items:center;gap:6px;padding:3px 10px;
  border-radius:999px;font-size:11.5px;border:1px solid var(--line);
  text-transform:uppercase;letter-spacing:.4px;font-weight:600}
.b-ok{color:var(--ok);border-color:#14532d;background:#0d2818}
.b-bad{color:var(--bad);border-color:#7f1d1d;background:#2a1215}
.b-warn{color:var(--warn);border-color:#78350f;background:#2a1c08}
.b-info{color:var(--info);border-color:#1e3a8a;background:#0c1e3d}
.b-muted{color:var(--muted);border-color:var(--line);background:var(--panel-2)}
.btn{background:#1D4ED8;color:#fff;border:0;border-radius:10px;padding:9px 14px;
  font-weight:600;cursor:pointer;font-size:13px;transition:filter .15s}
.btn:hover{filter:brightness(1.15)}
.btn:disabled{opacity:.5;cursor:not-allowed}
.btn.ghost{background:var(--panel-2);color:var(--text);border:1px solid var(--line)}
.btn.danger{background:#7f1d1d;color:#FCA5A5}
select,input,textarea{background:var(--panel-2);color:var(--text);border:1px solid var(--line);
  border-radius:10px;padding:8px 11px;font-size:13px;font-family:inherit}
textarea{font-family:var(--mono);min-height:80px;width:100%}
input:focus,select:focus,textarea:focus{outline:0;border-color:var(--accent)}
table{width:100%;border-collapse:collapse;font-size:13px}
th,td{padding:8px 10px;border-bottom:1px solid var(--line);text-align:left}
td.num,th.num{text-align:right;font-family:var(--mono)}
tr.bad td{background:#2a1215}
tr.warn td{background:#2a1c08}
tr.ok td{background:#0d2818}
.evt{border-left:3px solid var(--line);background:var(--panel-2);
  padding:10px 12px;margin-bottom:8px;border-radius:0 10px 10px 0;
  font-size:13px;animation:slide .2s ease-out both}
.evt.buyer{border-color:#3B82F6}
.evt.gateway{border-color:#F59E0B}
.evt.executor{border-color:#22C55E}
.evt.system{border-color:#64748B}
.evt.llm{border-color:#8B5CF6}
.evt.wallet{border-color:#2DD4BF}
.evt.reject{border-color:#EF4444;background:#2a1215}
.evt .ts{font-family:var(--mono);font-size:11px;color:var(--muted)}
.evt .actor{display:inline-block;padding:1px 8px;border-radius:6px;font-size:11px;
  font-weight:700;color:#0B1220;margin-right:6px;text-transform:uppercase}
.actor.buyer_agent{background:#3B82F6;color:#fff}
.actor.gateway{background:#F59E0B;color:#000}
.actor.executor{background:#22C55E;color:#000}
.actor.system{background:#64748B;color:#fff}
.actor.llm{background:#8B5CF6;color:#fff}
.actor.wallet{background:#2DD4BF;color:#000}
.actor.webhook{background:#A78BFA;color:#000}
.actor.merchant{background:#A78BFA;color:#000}
.actor.razorpay{background:#22C55E;color:#000}
.actor.user{background:#94A3B8;color:#000}
.actor.simulated_user{background:#94A3B8;color:#000}
.rule-row{display:flex;gap:8px;padding:8px 10px;border-bottom:1px solid var(--line);
  font-size:13px;align-items:center}
.rule-row:last-child{border-bottom:0}
.rule-row .rid{font-family:var(--mono);font-weight:700;width:90px;font-size:12px}
.rule-row .lbl{width:130px;color:var(--muted);font-size:12.5px}
.rule-row .stat{width:60px;font-weight:700;text-align:center}
.rule-row .stat.pass{color:var(--ok)}
.rule-row .stat.fail{color:var(--bad)}
.rule-row .why{flex:1;color:var(--muted);font-size:12.5px;
  font-family:var(--mono);overflow:hidden;text-overflow:ellipsis;white-space:nowrap}
.attacks{display:grid;gap:12px;grid-template-columns:repeat(auto-fill,minmax(260px,1fr))}
.atk{background:var(--panel-2);border:1px solid var(--line);border-radius:12px;
  padding:14px;cursor:pointer;transition:all .15s}
.atk:hover{border-color:var(--accent);transform:translateY(-1px)}
.atk h3{font-size:14px;margin-bottom:4px}
.atk .muted{font-size:12px}
.atk .res{margin-top:10px;font-family:var(--mono);font-size:11.5px}
.pipeline{display:flex;flex-wrap:wrap;gap:0;align-items:center;
  padding:10px 0;margin:14px 0;font-family:var(--mono);font-size:11.5px}
.pipeline .node{padding:8px 12px;background:var(--panel-2);border:1px solid var(--line);
  border-radius:8px;margin-right:-1px;position:relative;min-width:90px;text-align:center}
.pipeline .node.active{border-color:var(--accent);background:#1A0F30;color:var(--accent)}
.pipeline .node.done{border-color:var(--ok);color:var(--ok)}
.pipeline .node.fail{border-color:var(--bad);color:var(--bad)}
.pipeline .arrow{color:var(--dim);padding:0 6px}
.tag{display:inline-block;padding:2px 8px;border-radius:6px;
  background:var(--panel-2);border:1px solid var(--line);
  font-size:11px;margin-right:4px;color:var(--muted)}
.kpi{display:flex;flex-direction:column;gap:4px}
.kpi .label{font-size:11px;text-transform:uppercase;letter-spacing:.5px;color:var(--muted)}
.kpi .val{font-size:24px;font-weight:700;font-family:var(--mono)}
.dot{width:8px;height:8px;border-radius:50%;display:inline-block;margin-right:4px}
.dot.ok{background:var(--ok);box-shadow:0 0 8px rgba(34,197,94,.6)}
.dot.bad{background:var(--bad);box-shadow:0 0 8px rgba(239,68,68,.6)}
.dot.warn{background:var(--warn);box-shadow:0 0 8px rgba(245,158,11,.6)}
.dot.dim{background:var(--dim)}
@keyframes slide{from{opacity:0;transform:translateX(-6px)}to{opacity:1;transform:none}}
.kbd{font-family:var(--mono);font-size:11px;background:var(--panel-2);
  border:1px solid var(--line);padding:1px 6px;border-radius:4px;color:var(--muted)}
.divider{height:1px;background:var(--line);margin:18px 0}
.empty{color:var(--muted);padding:14px;text-align:center;font-size:13px;
  border:1px dashed var(--line);border-radius:10px;background:var(--panel-2)}
.error{color:var(--bad);background:#2a1215;border:1px solid #7f1d1d;
  padding:10px 12px;border-radius:8px;font-family:var(--mono);font-size:12px}
.warnbox{color:var(--warn);background:#2a1c08;border:1px solid #78350f;
  padding:10px 12px;border-radius:8px;font-family:var(--mono);font-size:12px}
.okbox{color:var(--ok);background:#0d2818;border:1px solid #14532d;
  padding:10px 12px;border-radius:8px;font-family:var(--mono);font-size:12px}
.infobox{color:var(--info);background:#0c1e3d;border:1px solid #1e3a8a;
  padding:10px 12px;border-radius:8px;font-family:var(--mono);font-size:12px}
pre.code{background:#060B16;border:1px solid var(--line);border-radius:10px;
  padding:12px;font-family:var(--mono);font-size:12px;overflow:auto;max-height:240px;
  color:#CBD5E1}
.footer{color:var(--dim);font-size:12px;text-align:center;margin-top:30px;padding-top:18px;
  border-top:1px solid var(--line)}
@media(max-width:760px){.h1{font-size:24px}.num.big{font-size:28px}}
"""


_JS_BASE = """
var $=function(s){return document.querySelector(s)};
var $$=function(s){return Array.from(document.querySelectorAll(s))};
var esc=function(s){return(s??'').toString().replace(/[&<>"']/g,
  function(m){return {'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[m]})};
var INR=function(p){return 'Rs '+(Number(p||0)/100).toLocaleString('en-IN',{maximumFractionDigits:0})};
var sleep=function(ms){return new Promise(function(r){setTimeout(r,ms)})};
async function jget(u){var r=await fetch(u);return{status:r.status,data:await r.json().catch(function(){return null})}};
async function jpost(u,body,headers){var r=await fetch(u,{method:'POST',headers:
  Object.assign({'Content-Type':'application/json'},headers||{}),body:typeof body==='string'?body:JSON.stringify(body||{})});
  return{status:r.status,data:await r.json().catch(function(){return null})}};
function fmtTs(t){if(!t)return'';var d=new Date(t*1000);return d.toLocaleTimeString('en-GB',{hour:'2-digit',minute:'2-digit',second:'2-digit'})};
function fmtMs(ms){if(ms<1000)return ms+' ms';if(ms<60000)return (ms/1000).toFixed(1)+' s';return (ms/60000).toFixed(1)+' min'};
function pct(n,d){return d?(Math.round(n*1000/d)/10)+'%':'—'};
function badge(cls,t){return '<span class="badge '+cls+'">'+esc(t)+'</span>'};
"""


_NAV = """
<header class="top"><div class="bar">
  <div class="brand">SELLABLE<span class="accent">.</span>
    <span class="muted" style="font-weight:400;font-size:12px;margin-left:6px">
    Autonomous Commerce Security</span></div>
  <nav>
    <a href="/" id="nav-home">Command Center</a>
    <a href="/mission" id="nav-mission">Live Mission</a>
    <a href="/products" id="nav-products">Catalog</a>
    <a href="/gateway-ui" id="nav-gateway">Policy Gateway</a>
    <a href="/audit-ui" id="nav-audit">Audit</a>
    <a href="/attack-ui" id="nav-attack">Attack Lab</a>
    <a href="/metrics" id="nav-metrics">Metrics</a>
    <a href="/demo" class="muted">/demo</a>
  </nav>
  <div class="space"></div>
  <span id="hdr-status" class="badge b-muted">connecting...</span>
</div></header>
"""


def _shell(title: str, body_html: str, js: str, active_nav: str = "") -> str:
    """Wrap page in standard shell."""
    nav = _NAV
    # Mark active nav link
    if active_nav:
        nav = nav.replace(f'id="nav-{active_nav}"', f'id="nav-{active_nav}" class="active"')
    return (f"<!doctype html><html lang='en'><head>"
            f"<meta charset='utf-8'>"
            f"<meta name='viewport' content='width=device-width,initial-scale=1'>"
            f"<title>{_html_escape.escape(title)} · SELLABLE</title>"
            f"<style>{_CSS}</style></head><body>"
            f"{nav}<main class='wrap'>{body_html}</main>"
            f"<div class='footer'>SELLABLE · LLM proposes · Deterministic policy disposes · "
            f"Cryptographic bindings authorize · Razorpay executes · Audit remembers</div>"
            f"<script>{_JS_BASE}{js}</script></body></html>")


@router.get("/", response_class=HTMLResponse)
def command_center():
    body = """
<section class="h1">Autonomous Commerce <span class="accent">without autonomous money</span>.</h1>
<p class="lede">An AI buyer can search, reason, negotiate, and propose a purchase.
It <em>cannot</em> authorize money movement. SELLABLE enforces that separation with
deterministic policy, cryptographic approvals, and a tamper-evident audit chain.</p>

<div class="grid cards-4" id="kpis" style="margin-bottom:16px">
  <div class="panel kpi"><div class="label">System Risk</div>
    <div class="val" id="k-risk">—</div><div id="k-risk-tag"></div></div>
  <div class="panel kpi"><div class="label">Policy Gateway</div>
    <div class="val" id="k-gw">—</div><div class="muted mono" id="k-gw-sub"></div></div>
  <div class="panel kpi"><div class="label">Razorpay</div>
    <div class="val" id="k-rz">—</div><div class="muted mono" id="k-rz-sub"></div></div>
  <div class="panel kpi"><div class="label">Audit Chain</div>
    <div class="val" id="k-au">—</div><div class="muted mono" id="k-au-sub"></div></div>
</div>

<div class="panel" style="margin-bottom:14px">
  <h2>The Transaction Pipeline</h2>
  <div class="pipeline" id="pipeline">
    <div class="node" data-step="mission">MISSION</div>
    <span class="arrow">→</span>
    <div class="node" data-step="search">SEARCH</div>
    <span class="arrow">→</span>
    <div class="node" data-step="agent">AGENT</div>
    <span class="arrow">→</span>
    <div class="node" data-step="proposal">PROPOSAL</div>
    <span class="arrow">→</span>
    <div class="node" data-step="policy">POLICY</div>
    <span class="arrow">→</span>
    <div class="node" data-step="approval">APPROVAL</div>
    <span class="arrow">→</span>
    <div class="node" data-step="mandates">MANDATES</div>
    <span class="arrow">→</span>
    <div class="node" data-step="quote">QUOTE</div>
    <span class="arrow">→</span>
    <div class="node" data-step="razorpay">RAZORPAY</div>
    <span class="arrow">→</span>
    <div class="node" data-step="webhook">WEBHOOK</div>
    <span class="arrow">→</span>
    <div class="node" data-step="audit">AUDIT</div>
  </div>
  <p class="muted mono" style="font-size:12px;margin-top:6px">
    Each node reflects runtime state. The LLM is the proposer. Deterministic policy disposes.
    Cryptographic bindings authorize. Razorpay executes. The audit chain remembers.
  </p>
</div>

<div class="grid cards-2">
  <div class="panel">
    <h2>Recent Activity</h2>
    <div id="recent" class="muted mono" style="font-size:12px">loading…</div>
  </div>
  <div class="panel">
    <h2>Quick Actions</h2>
    <div class="row" style="gap:8px;flex-direction:column;align-items:stretch">
      <a class="btn" href="/mission">▶ Run a Live Mission</a>
      <a class="btn ghost" href="/attack-ui">⚡ Attack Lab</a>
      <a class="btn ghost" href="/audit-ui">🔍 Audit Explorer</a>
      <a class="btn ghost" href="/gateway-ui">🛡 Policy Gateway</a>
      <a class="btn ghost" href="/products">🛒 Browse Catalog</a>
    </div>
  </div>
</div>

<div class="grid cards-3" style="margin-top:14px">
  <div class="panel">
    <h2>Catalog</h2>
    <div class="num big" id="m-skus">—</div>
    <div class="muted mono" id="m-cats"></div>
  </div>
  <div class="panel">
    <h2>Money Calls (Invariant)</h2>
    <div class="num big" id="m-money">—</div>
    <div class="muted mono" id="m-money-sub"></div>
  </div>
  <div class="panel">
    <h2>LLM Status</h2>
    <div class="num" id="m-llm">—</div>
    <div class="muted mono" id="m-llm-sub"></div>
  </div>
</div>

<div class="panel" style="margin-top:14px">
  <h2>What Judges See in 5 Minutes</h2>
  <div class="grid cards-3" style="margin-top:8px">
    <div>
      <h3 style="color:var(--accent)">30 seconds — What this is</h3>
      <p class="muted">An agent-safe merchant: AI buyer proposes purchases,
      deterministic gateway approves or rejects, Razorpay executes only on cryptographic approval.</p>
    </div>
    <div>
      <h3 style="color:var(--accent)">2 minutes — A real purchase</h3>
      <p class="muted">Run the cricket bat mission. Watch search → agent → policy → approval → Razorpay → webhook → audit.</p>
    </div>
    <div>
      <h3 style="color:var(--accent)">4 minutes — A blocked attack</h3>
      <p class="muted">Open the Attack Lab. Fire all 8 scenarios. Verify: 0 Razorpay calls when gateway rejects.</p>
    </div>
  </div>
</div>
"""
    js = """
async function poll(){
  var r=await jget('/status');var s=r.data;if(!s)return;
  var risk=s.system_risk;
  $('#k-risk').textContent=risk;
  $('#k-risk-tag').innerHTML= badge(risk==='LOW'?'b-ok':risk==='MEDIUM'?'b-warn':'b-bad', risk);
  var gw=s.policy_gateway;
  $('#k-gw').innerHTML='<span class="dot ok"></span>Enforcing';
  $('#k-gw-sub').textContent=gw.rules_count+' rules · '
    +gw.approvals_total+' APPROVE · '+gw.rejections_total+' REJECT';
  var rz=s.razorpay;
  $('#k-rz').innerHTML=rz.configured
    ?'<span class="dot ok"></span>Test Mode':'<span class="dot warn"></span>Config Req.';
  $('#k-rz-sub').textContent=rz.configured?'configured':'missing: '+rz.missing_required.join(', ');
  var au=s.audit_chain;
  $('#k-au').innerHTML=au.healthy
    ?'<span class="dot ok"></span>Healthy':'<span class="dot bad"></span>Tampered';
  $('#k-au-sub').textContent=au.entries+' entries · seq #'+au.last_seq;
  var m=s.metrics;
  $('#m-skus').textContent=s.catalog.sku_count;
  $('#m-cats').textContent=s.catalog.categories.join(' · ');
  var mc=s.money_calls;
  $('#m-money').innerHTML=mc.boundary_calls===0
    ?'<span class="dot ok"></span>0':'<span class="dot warn"></span>'+mc.boundary_calls;
  $('#m-money-sub').textContent=mc.boundary_calls===0
    ?'INVARIANT OK · no Razorpay boundary calls'
    :'boundary calls detected — investigate';
  var l=s.llm;
  $('#m-llm').textContent=l.configured?l.model:'fallback';
  $('#m-llm-sub').textContent=l.configured
    ?'config OK · '+l.fallbacks.length+' fallbacks'
    :'deterministic fallback in use';
  $('#hdr-status').className='badge '+(au.healthy&&risk!=='HIGH'?'b-ok':risk==='MEDIUM'?'b-warn':'b-bad');
  $('#hdr-status').textContent=au.healthy&&risk!=='HIGH'?'OPERATIONAL':risk;
  // Recent activity
  var entries=(await jget('/audit')).data.entries||[];
  $('#recent').innerHTML=entries.slice(-8).reverse().map(function(e){
    return '<div style="padding:4px 0;border-bottom:1px solid var(--line)">'
      +'<span class="mono">#'+e.seq+'</span> '
      +esc(e.action)+' · <span class="dim">'+fmtTs(e.ts)+'</span></div>';
  }).join('') || '<div class="muted">no audit entries yet</div>';
}
poll();
setInterval(poll, 4000);
"""
    return HTMLResponse(_shell("Command Center", body, js, active_nav="home"))


@router.get("/mission", response_class=HTMLResponse)
def mission_page():
    """Live Mission Runner — submit a mission and watch the agent work."""
    body = """
<section class="h1">Live Mission</h1>
<p class="lede">Type a mission. The buyer agent searches the catalog, reasons about products,
proposes items, and submits to the deterministic policy gateway. Watch each step execute
against the real backend.</p>

<div class="grid" style="grid-template-columns:1fr 1fr;gap:14px;margin-bottom:14px">
  <div class="panel">
    <h2>1 · Define the Mission</h2>
    <label class="muted mono" style="font-size:12px">Intent</label>
    <textarea id="intent" style="margin-top:6px;margin-bottom:10px">Buy me a cricket bat under Rs 2,000. Prefer English willow.</textarea>
    <div class="row" style="margin-bottom:10px">
      <div style="flex:1"><label class="muted mono" style="font-size:12px">Budget (Rs)</label>
        <input id="budget" type="number" value="2000" style="width:100%;margin-top:4px"></div>
      <div style="flex:1"><label class="muted mono" style="font-size:12px">Upsell Cap (×)</label>
        <input id="cap" type="number" step="0.1" value="1.3" style="width:100%;margin-top:4px"></div>
      <div style="flex:1"><label class="muted mono" style="font-size:12px">Category</label>
        <select id="category" style="width:100%;margin-top:4px">
          <option value="cricket">cricket</option>
          <option value="books">books</option>
          <option value="electronics">electronics</option>
          <option value="apparel">apparel</option>
          <option value="groceries">groceries</option>
          <option value="stationery">stationery</option>
        </select></div>
    </div>
    <div class="row">
      <button class="btn" id="runBtn">▶ Run Mission</button>
      <button class="btn ghost" id="demoBtn">Use Demo</button>
      <span class="space"></span>
      <span id="missionIdTag" class="muted mono" style="font-size:12px"></span>
    </div>
    <div id="runStatus" style="margin-top:10px"></div>
  </div>

  <div class="panel">
    <h2>2 · Search Results</h2>
    <div id="searchResults" class="muted">Run a mission to see search results here.</div>
  </div>
</div>

<div class="panel" style="margin-bottom:14px">
  <h2>3 · Live Agent Trace</h2>
  <div id="trace" class="muted">Trace will appear here.</div>
</div>

<div class="grid" style="grid-template-columns:1fr 1fr;gap:14px">
  <div class="panel">
    <h2>4 · Gateway Verdict</h2>
    <div id="verdict" class="muted">Verdict will appear here.</div>
  </div>
  <div class="panel">
    <h2>5 · Approval Binding</h2>
    <div id="binding" class="muted">Binding will appear here.</div>
  </div>
</div>

<div class="grid" style="grid-template-columns:1fr 1fr;gap:14px;margin-top:14px">
  <div class="panel">
    <h2>6 · Mandates</h2>
    <div id="mandates" class="muted">Mandates will appear here.</div>
  </div>
  <div class="panel">
    <h2>7 · Razorpay Order</h2>
    <div id="payment" class="muted">Payment will appear here.</div>
  </div>
</div>
"""
    js = """
var CURRENT_MISSION=null;
$('#demoBtn').onclick=function(){
  $('#intent').value='Buy me a cricket bat under Rs 2,000. Prefer English willow.';
  $('#budget').value=2000;$('#category').value='cricket';$('#cap').value=1.3;
};
$('#runBtn').onclick=runMission;

async function runMission(){
  var intent=$('#intent').value;
  var budget=Number($('#budget').value||0);
  var cap=Number($('#cap').value||1.0);
  var category=$('#category').value;
  var mid='MSN-LIVE-'+Date.now();
  CURRENT_MISSION=mid;
  $('#missionIdTag').textContent='mission: '+mid;
  $('#runStatus').innerHTML=infobox('Mission submitted. Agent is searching…');
  $('#trace').innerHTML='';$('#verdict').innerHTML='<div class='muted'>pending…</div>';
  $('#binding').innerHTML='<div class='muted'>pending…</div>';
  $('#mandates').innerHTML='<div class='muted'>pending…</div>';
  $('#payment').innerHTML='<div class='muted'>pending…</div>';
  $('#searchResults').innerHTML='<div class='muted'>searching…</div>';

  // Step 1: Sign mission via /attack (cheat) or use the demo flow.
  // We use /agent/run-mission — that path signs its own mission.
  var res=await jpost('/agent/run-mission',{
    mission_id:mid, intent:intent,
    budget_paise:budget*100, allowed_categories:[category],
    forbidden_categories:[], upsell_cap:cap,
    expires_at:Math.floor(Date.now()/1000)+600,
    signature:'__server_will_resign__',
  });
  var trace=res.data&&res.data.trace&&res.data.trace.events?res.data.trace.events:[];
  if(res.status!==200){
    $('#runStatus').innerHTML=errorbox('Mission failed: HTTP '+res.status+' '+JSON.stringify(res.data).slice(0,200));
    return;
  }

  // Show search results (the agent ran search_products — read from audit)
  $('#searchResults').innerHTML='<div class="okbox">Agent executed search and reasoning. '
    +'See trace below for the SKU list and prices.</div>';

  // Render trace
  var html=trace.map(function(e){
    var actor=String(e.actor||'system');
    var isReject=(String(e.detail||'').toLowerCase().includes('reject')
      ||(e.data&&e.data.decision==='REJECT'));
    var cls='evt '+(isReject?'reject':actor);
    var dataStr='';
    if(e.data&&Object.keys(e.data).length){
      dataStr='<details style="margin-top:6px"><summary class="muted">payload</summary>'
        +'<pre class="code">'+esc(JSON.stringify(e.data,null,1).slice(0,500))+'</pre></details>';
    }
    return '<div class="'+cls+'"><span class="ts">'+fmtTs(e.ts)+'</span>'
      +'<span class="actor '+actor+'">'+esc(actor)+'</span>'
      +'<b>'+esc(e.action||'')+'</b> · '+esc(e.detail||'')
      +dataStr+'</div>';
  }).join('');
  $('#trace').innerHTML=html||'<div class="empty">No trace events.</div>';

  // Show verdict from trace
  var verdictEv=trace.filter(function(e){return e.action==='verdict_received'}).slice(-1)[0];
  if(verdictEv&&verdictEv.data){
    var v=verdictEv.data;
    var d=(v.decision||'').toUpperCase();
    var color=d==='APPROVE'?'b-ok':'b-bad';
    var html2='<div class="row" style="margin-bottom:10px">'
      +badge(color,d)+' <span class="mono">seq #'+esc(v.seq||'?')+'</span></div>';
    if(d==='APPROVE'){
      html2+='<div class="okbox">All R1-R12 rules passed. Approval binding issued.</div>';
      html2+='<div class="mono" style="margin-top:10px;font-size:12px">'
        +'<div>proposal_hash: '+esc((v.proposal_hash||'').slice(0,32))+'…</div>'
        +'</div>';
    } else {
      html2+='<div class="error">Failed rule: <b>'+esc(v.rule_id||'?')+'</b></div>'
        +'<p class="muted" style="margin-top:8px">'+esc(v.reason||'')+'</p>';
    }
    $('#verdict').innerHTML=html2;
  }

  // Binding section
  if(res.data&&res.data.proposed_skus){
    var skus=res.data.proposed_skus;
    var amt=res.data.amount_paise||0;
    $('#binding').innerHTML=
      '<table><tr><th>Field</th><th>Value</th></tr>'
      +'<tr><td>mission_id</td><td class="mono">'+esc(mid)+'</td></tr>'
      +'<tr><td>proposal_hash</td><td class="mono">'+esc((verdictEv&&verdictEv.data&&verdictEv.data.proposal_hash||'').slice(0,32))+'…</td></tr>'
      +'<tr><td>amount_paise</td><td class="mono">'+esc(amt)+'</td></tr>'
      +'<tr><td>currency</td><td class="mono">INR</td></tr>'
      +'<tr><td>sku_set</td><td class="mono">'+esc(JSON.stringify(skus))+'</td></tr>'
      +'</table>'
      +'<div class="okbox" style="margin-top:10px">'
        +'Binding links mission → proposal → quote → cart → amount → expiry. '
        +'The executor will reject any mismatch.</div>';
  } else {
    $('#binding').innerHTML='<div class="muted">No approval issued (verdict was not APPROVE).</div>';
  }

  // Mandates
  if(res.data&&res.data.status==='completed'||res.data&&res.data.status==='payment_authorized_capture_pending'){
    $('#mandates').innerHTML=
      '<div class="okbox">Intent Mandate — verified</div>'
      +'<div class="okbox" style="margin-top:6px">Cart Mandate — verified</div>';
  } else {
    $('#mandates').innerHTML=
      '<div class="muted">Mandates issued out-of-band by the simulated wallet.</div>';
  }

  // Payment
  if(res.data&&res.data.order_id){
    $('#payment').innerHTML=
      '<table><tr><th>Field</th><th>Value</th></tr>'
      +'<tr><td>order_id</td><td class="mono">'+esc(res.data.order_id)+'</td></tr>'
      +'<tr><td>amount</td><td class="mono">'+INR(res.data.amount_paise)+'</td></tr>'
      +'<tr><td>final_status</td><td>'+badge('b-info', esc(res.data.final_payment_status||'pending'))+'</td></tr>'
      +'</table>';
  } else if(res.data&&res.data.status){
    $('#payment').innerHTML='<div class="warnbox">Status: '+esc(res.data.status)+'</div>';
  }

  if(res.data&&res.data.status==='completed'){
    $('#runStatus').innerHTML='<div class="okbox">✅ Mission completed. See payment panel for order details.</div>';
  } else {
    $('#runStatus').innerHTML='<div class="warnbox">Mission status: '+esc(res.data?res.data.status:'unknown')+'</div>';
  }
}

function infobox(t){return '<div class="infobox">'+esc(t)+'</div>'};
function errorbox(t){return '<div class="error">'+esc(t)+'</div>'};
"""
    return HTMLResponse(_shell("Live Mission", body, js, active_nav="mission"))


@router.get("/products", response_class=HTMLResponse)
def products_page():
    body = """
<section class="h1">Catalog</h1>
<p class="lede">40 SKUs across 6 categories. Prices are server-side truth — no
client, no LLM, no agent can change them. Some descriptions contain adversarial
prompt-injection payloads (intentional). The gateway defends.</p>

<div class="panel" style="margin-bottom:14px">
  <div class="row">
    <input id="q" placeholder="Search name or category" style="flex:1">
    <select id="cat" style="width:160px"><option value="">all categories</option></select>
    <input id="maxp" type="number" placeholder="max Rs" style="width:120px">
    <button class="btn" id="goBtn">Search</button>
  </div>
</div>
<div class="panel">
  <div id="prodList">loading…</div>
</div>
"""
    js = """
async function load(){
  var r=await jget('/catalog');var items=r.data.items||[];
  var cats=Array.from(new Set(items.map(function(i){return i.category}))).sort();
  var sel=$('#cat');cats.forEach(function(c){var o=document.createElement('option');o.value=c;o.textContent=c;sel.appendChild(o)});
  render(items);
}
function render(items){
  if(!items.length){$('#prodList').innerHTML='<div class="empty">no products match</div>';return;}
  var html='<table><tr><th>SKU</th><th>Name</th><th>Category</th><th class="num">Price</th><th class="num">Rating</th><th class="num">Stock</th></tr>';
  items.forEach(function(p){
    var inj=(p.name+' '+p.category).toLowerCase().match(/kit-001|book-008|lap-002|sock-001|hony-001|stky-001/);
    html+='<tr'+(inj?' class="warn"':'')+'><td class="mono">'+esc(p.sku)+'</td>'
      +'<td>'+esc(p.name)+(inj?' <span class="badge b-warn">injection payload</span>':'')+'</td>'
      +'<td><span class="tag">'+esc(p.category)+'</span></td>'
      +'<td class="num">'+esc(p.price_display)+'</td>'
      +'<td class="num">'+(p.rating||0)+'</td>'
      +'<td class="num">'+(p.stock||0)+'</td></tr>';
  });
  html+='</table>';
  $('#prodList').innerHTML=html;
}
function go(){
  var q=$('#q').value.toLowerCase();
  var c=$('#cat').value;
  var maxp=Number($('#maxp').value||0)*100;
  jget('/catalog').then(function(r){var items=(r.data.items||[]).filter(function(p){
    return (!q||p.name.toLowerCase().includes(q)||p.category.toLowerCase().includes(q))
      &&(!c||p.category===c)
      &&(!maxp||p.price_paise<=maxp);
  });render(items)});
}
$('#goBtn').onclick=go;
$('#q').addEventListener('keydown',function(e){if(e.key==='Enter')go()});
load();
"""
    return HTMLResponse(_shell("Catalog", body, js, active_nav="products"))


@router.get("/gateway-ui", response_class=HTMLResponse)
def gateway_ui():
    body = """
<section class="h1">Policy Gateway</h1>
<p class="lede">12 deterministic rules. The LLM <em>cannot</em> authorize money.
The gateway decides. Every rule is fail-closed.</p>

<div class="panel" style="margin-bottom:14px">
  <h2>Rule Registry</h2>
  <div id="rules"></div>
</div>

<div class="panel" style="margin-bottom:14px">
  <h2>Live Decisions</h2>
  <div id="recent"></div>
</div>

<div class="panel">
  <h2>Money-Call Invariant</h2>
  <div id="inv"></div>
</div>
"""
    js = """
async function load(){
  var rules=await jget('/rules');
  var html='<table><tr><th>Rule</th><th>Phase</th><th>Severity</th><th>What it checks</th></tr>';
  (rules.data.rules||[]).forEach(function(r){
    html+='<tr><td class="mono"><b>'+esc(r.rule_id)+'</b></td>'
      +'<td>'+esc(r.phase||'')+'</td>'
      +'<td>'+badge(r.severity==='FATAL'?'b-bad':'b-warn', esc(r.severity))+'</td>'
      +'<td class="muted">'+esc(r.check_description||'')+'</td></tr>';
  });
  $('#rules').innerHTML=html;

  var inv=await jget('/invariant/money-calls');
  var mc=inv.data.money_calls;
  $('#inv').innerHTML=
    '<div class="row" style="margin-bottom:8px">'
    +badge(mc.invariant_ok?'b-ok':'b-bad', mc.invariant_ok?'INVARIANT OK':'INVARIANT VIOLATED')
    +'</div>'
    +'<p class="muted">'+esc(inv.data.invariant)+'</p>'
    +'<table style="margin-top:10px"><tr><th>Operation</th><th class="num">Calls</th></tr>'
    +Object.keys(mc.by_operation).map(function(k){
      return '<tr><td class="mono">'+esc(k)+'</td><td class="num">'+mc.by_operation[k]+'</td></tr>';
    }).join('')+'</table>';

  var audit=await jget('/audit');
  var dec=((audit.data.entries||[]).filter(function(e){return e.action==='verdict_emitted'})).slice(-6).reverse();
  $('#recent').innerHTML=dec.length?dec.map(function(e){
    var p=JSON.parse(e.payload_json||'{}');
    var d=p.decision||'?';
    return '<div class="evt '+(d==='APPROVE'?'':'reject')+'">'
      +'<span class="ts">'+fmtTs(e.ts)+'</span>'
      +badge(d==='APPROVE'?'b-ok':'b-bad', d)
      +' <b>'+esc(p.rule_id||'all_passed')+'</b>'
      +' <span class="muted">'+(p.reason||'').slice(0,140)+'</span>'
      +'</div>';
  }).join(''):'<div class="empty">No decisions yet.</div>';
}
load();
setInterval(load, 5000);
"""
    return HTMLResponse(_shell("Policy Gateway", body, js, active_nav="gateway"))


@router.get("/audit-ui", response_class=HTMLResponse)
def audit_ui():
    body = """
<section class="h1">Audit Explorer</h1>
<p class="lede">Tamper-evident hash chain. Every money-relevant action is appended.
Each entry covers seq · ts · actor · action · payload_hash · prev_hash.</p>

<div class="panel" style="margin-bottom:14px">
  <div class="row">
    <button class="btn" id="verifyBtn">🔒 Verify Chain</button>
    <span id="verifyResult"></span>
    <span class="space"></span>
    <span class="muted mono">entries: <span id="cnt">—</span></span>
  </div>
</div>

<div class="panel">
  <h2>Latest Entries</h2>
  <div id="entries" class="mono" style="font-size:12px">loading…</div>
</div>
"""
    js = """
async function load(){
  var r=await jget('/audit');
  var entries=(r.data.entries||[]).slice().reverse();
  $('#cnt').textContent=entries.length;
  $('#verifyResult').innerHTML=badge(r.data.verified?'b-ok':'b-bad', r.data.verified?'CHAIN VALID':'CHAIN INVALID');
  var html=entries.slice(0,20).map(function(e){
    return '<div class="evt">'
      +'<span class="ts">#'+e.seq+' · '+fmtTs(e.ts)+'</span> '
      +'<b>'+esc(e.action)+'</b> '
      +'<span class="dim">actor='+esc(e.actor)+'</span> '
      +'<span class="dim">hash='+(e.hash||'').slice(0,12)+'…</span> '
      +'<span class="dim">prev='+(e.prev_hash||'').slice(0,12)+'…</span>'
      +'</div>';
  }).join('');
  $('#entries').innerHTML=html||'<div class="empty">empty</div>';
}
$('#verifyBtn').onclick=function(){load()};
load();
setInterval(load, 5000);
"""
    return HTMLResponse(_shell("Audit", body, js, active_nav="audit"))


@router.get("/attack-ui", response_class=HTMLResponse)
def attack_ui():
    body = """
<section class="h1">Attack Lab</h1>
<p class="lede">8 real adversarial scenarios against the real gateway. Each one
runs the actual engine and resets the money-call counter. A safe result
means: 0 Razorpay calls when the gateway rejects.</p>

<div class="panel" style="margin-bottom:14px">
  <div class="row">
    <button class="btn danger" id="runAllBtn">⚡ Run All Attacks</button>
    <span id="summary"></span>
  </div>
</div>

<div class="attacks" id="attacks">loading…</div>

<div class="panel" style="margin-top:14px">
  <h2>Last Result Detail</h2>
  <div id="detail" class="muted">Run an attack to see the breakdown.</div>
</div>
"""
    js = """
var ATKS=[
  {id:'A1_PROMPT_INJECTION',label:'Prompt Injection',desc:'Catalog description orders the LLM to over-spend.'},
  {id:'A2_OVERSPENDING',label:'Overspending',desc:'Agent proposes items totaling more than budget.'},
  {id:'A3_PRICE_MANIPULATION',label:'Price Manipulation',desc:'Proposal claims a fake low price.'},
  {id:'A4_FORBIDDEN_PRODUCT',label:'Forbidden Product',desc:'Item from a forbidden category.'},
  {id:'A5_SCOPE_VIOLATION',label:'Scope Violation',desc:'Item outside allowed categories.'},
  {id:'A6_INVALID_SIGNATURE',label:'Invalid Signature',desc:'Mission HMAC tampered.'},
  {id:'A7_STALE_MANDATE',label:'Stale Mandate',desc:'Approval binding expired.'},
  {id:'A8_CART_MUTATION',label:'Cart Mutation',desc:'Approved cart swapped to different SKU.'}
];
function renderCards(){
  $('#attacks').innerHTML=ATKS.map(function(a){
    return '<div class="atk" data-id="'+a.id+'"><h3>'+esc(a.label)+'</h3>'
      +'<p class="muted">'+esc(a.desc)+'</p>'
      +'<button class="btn ghost run1" data-id="'+a.id+'" style="margin-top:8px">▶ Run</button>'
      +'<div class="res" id="r-'+a.id+'"></div></div>';
  }).join('');
  $$('.run1').forEach(function(b){b.onclick=function(){run(b.getAttribute('data-id'))}});
}
async function run(id){
  $('#r-'+id).innerHTML='<span class="muted">firing…</span>';
  var res=await jpost('/attack/run/'+id,{});
  var d=res.data;
  var color=d.verdict.safe?'b-ok':'b-bad';
  $('#r-'+id).innerHTML=
    badge(color, d.verdict.summary)
    +'<div class="muted" style="margin-top:4px">decision: '+esc(d.gateway.decision)
    +' · rule: '+esc(d.gateway.rule_id||'-')
    +' · money_calls: '+d.money_calls.boundary_calls+'</div>';
  showDetail(d);
}
function showDetail(d){
  var rules=(d.gateway.rule_matrix||[]).map(function(r){
    var c=r.status==='PASS'?'b-ok':'b-bad';
    return '<div class="rule-row"><div class="rid">'+esc(r.rule_id)+'</div>'
      +'<div class="lbl">'+esc(r.label||'')+'</div>'
      +'<div class="stat '+(r.status==='PASS'?'pass':'fail')+'">'+esc(r.status)+'</div>'
      +'<div class="why">'+esc(r.reason||'')+'</div></div>';
  }).join('');
  $('#detail').innerHTML=
    '<h3>'+esc(d.scenario.label)+'</h3>'
    +'<p class="muted" style="margin-bottom:10px">'+esc(d.scenario.description)+'</p>'
    +'<div class="grid" style="grid-template-columns:1fr 1fr;gap:10px;margin-bottom:14px">'
    +'<div><h4 class="muted" style="font-size:11px;text-transform:uppercase">Attacker Intent</h4>'
    +'<p>'+esc(d.attacker_intent)+'</p></div>'
    +'<div><h4 class="muted" style="font-size:11px;text-transform:uppercase">Agent Input</h4>'
    +'<pre class="code">'+esc(JSON.stringify(d.agent_input,null,1))+'</pre></div>'
    +'</div>'
    +'<h4 class="muted" style="font-size:11px;text-transform:uppercase">Model Output</h4>'
    +'<p>'+esc(d.model_output.note)+'</p>'
    +'<pre class="code">proposed_skus: '+esc(JSON.stringify(d.model_output.proposal_skus))
    +'\\ntotal: '+esc(d.model_output.proposal_total_display)+'</pre>'
    +'<h4 class="muted" style="font-size:11px;text-transform:uppercase;margin-top:14px">Gateway Verdict</h4>'
    +'<div class="row" style="margin-bottom:8px">'
    +badge(d.gateway.decision==='APPROVE'?'b-ok':'b-bad',d.gateway.decision)
    +' <span class="mono">rule: '+esc(d.gateway.rule_id||'-')+'</span></div>'
    +'<p class="muted">'+esc(d.gateway.reason)+'</p>'
    +'<div class="rule-list" style="margin-top:10px">'+rules+'</div>'
    +'<h4 class="muted" style="font-size:11px;text-transform:uppercase;margin-top:14px">Money Path</h4>'
    +'<div class="row">'
    +badge(d.money_calls.boundary_calls===0?'b-ok':'b-bad',
       d.money_calls.boundary_calls===0?'NO Razorpay call':'Razorpay CALLED')
    +' <span class="muted mono">boundary_calls: '+d.money_calls.boundary_calls+'</span></div>'
    +(d.binding_check?'<h4 class="muted" style="font-size:11px;text-transform:uppercase;margin-top:14px">Binding Check</h4>'
      +'<div class="row">'+badge(d.binding_check.blocked?'b-ok':'b-bad',
        d.binding_check.blocked?'binding refused':'binding ACCEPTED')
      +' <span class="mono">'+esc(d.binding_check.reason||'')+'</span></div>':'')
    +'<h4 class="muted" style="font-size:11px;text-transform:uppercase;margin-top:14px">Final Verdict</h4>'
    +'<div class="row">'+badge(d.verdict.safe?'b-ok':'b-bad',d.verdict.summary)+'</div>';
}
$('#runAllBtn').onclick=async function(){
  var res=await jpost('/attack/run_all',{});
  var d=res.data;
  $('#summary').innerHTML=badge(d.scenarios_blocked===d.scenarios_total?'b-ok':'b-warn',
    d.scenarios_blocked+'/'+d.scenarios_total+' blocked ('+(d.block_rate*100)+'%)');
  (d.results||[]).forEach(function(r){
    $('#r-'+r.id).innerHTML=badge(r.safe?'b-ok':'b-bad',
      r.decision+' · '+r.rule_id+' · '+r.money_calls+' calls');
  });
};
renderCards();
"""
    return HTMLResponse(_shell("Attack Lab", body, js, active_nav="attack"))


@router.get("/metrics", response_class=HTMLResponse)
def metrics_page():
    body = """
<section class="h1">Metrics</h1>
<p class="lede">Real operational metrics from the live audit chain.</p>

<div class="grid cards-3" id="cards">loading…</div>

<div class="panel" style="margin-top:14px">
  <h2>Revenue &amp; Money Flow</h2>
  <div id="revenue">loading…</div>
</div>
"""
    js = """
async function load(){
  var r=await jget('/metrics/summary');var s=r.data;
  var html='<div class="panel kpi"><div class="label">Audit Entries</div><div class="val">'+s.audit_entries+'</div></div>'
    +'<div class="panel kpi"><div class="label">Approval Rate</div><div class="val">'+((s.verdicts.approval_rate||0)*100).toFixed(1)+'%</div>'
    +'<div class="panel kpi"><div class="label">APPROVE</div><div class="val" style="color:var(--ok)">'+s.verdicts.approve+'</div></div>'
    +'<div class="panel kpi"><div class="label">REJECT</div><div class="val" style="color:var(--bad)">'+s.verdicts.reject+'</div></div>'
    +'<div class="panel kpi"><div class="label">Money Calls</div><div class="val">'+s.money_calls.boundary_calls+'</div>'
    +'<div class="muted mono" style="font-size:11px">'+(s.money_calls.invariant_ok?'INVARIANT OK':'CHECK')+'</div></div>'
    +'<div class="panel kpi"><div class="label">p50 Latency</div><div class="val">'+s.latency_ms.p50+' ms</div></div>'
    +'<div class="panel kpi"><div class="label">p95 Latency</div><div class="val">'+s.latency_ms.p95+' ms</div></div>'
    +'<div class="panel kpi"><div class="label">Webhook Events</div><div class="val">'+s.webhook_events+'</div></div>'
    +'<div class="panel kpi"><div class="label">Ledger Orders</div><div class="val">'+s.payment_ledger_orders+'</div></div>';
  $('#cards').innerHTML=html;

  var rev=await jget('/metrics/revenue');
  $('#revenue').innerHTML='<pre class="code">'+esc(JSON.stringify(rev.data,null,1))+'</pre>';
}
load();
setInterval(load, 5000);
"""
    return HTMLResponse(_shell("Metrics", body, js, active_nav="metrics"))


@router.get("/health-check")
def health_json():
    """Alias for /health that the UI can call without coupling."""
    cfg = app_config.get()
    return {
        "status": "alive",
        "audit_entries": len(audit_chain.entries()),
        "audit_chain_ok": audit_chain.verify(),
        "orders": len(orders),
        "quotes": len(quotes),
        "config": cfg,
        "money_calls": money_mod.snapshot(),
    }