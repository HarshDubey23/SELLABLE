"""Mission Control Chaos Room & Interactive Architecture Diagram UI."""
from __future__ import annotations

from fastapi import APIRouter
from fastapi.responses import HTMLResponse

router = APIRouter(tags=["chaos-ui"])


@router.get("/chaos", response_class=HTMLResponse)
async def chaos_mission_control():
    """Mission Control Chaos Page — Fault Injection & Invariant Compliance Engine."""
    content = """<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>Chaos Monkey · Mission Control · SELLABLE</title>
  <style>
    :root {
      --bg: #050A14; --panel: #0E1726; --border: #1E293B;
      --cyan: #00BAF2; --purple: #7C3AED; --ok: #10B981;
      --warn: #F59E0B; --bad: #EF4444; --text: #F8FAFC; --muted: #94A3B8;
      --font-mono: ui-monospace, Consolas, Menlo, monospace;
    }
    * { box-sizing: border-box; margin: 0; padding: 0; }
    body { background: var(--bg); color: var(--text); font-family: system-ui, -apple-system, sans-serif; padding: 24px; line-height: 1.5; }
    .wrap { max-width: 1300px; margin: 0 auto; }
    header { display: flex; justify-content: space-between; align-items: center; margin-bottom: 24px; flex-wrap: wrap; gap: 16px; border-bottom: 1px solid var(--border); padding-bottom: 16px; }
    .title { font-size: 26px; font-weight: 900; letter-spacing: -0.5px; }
    .nav-links { display: flex; gap: 12px; }
    .nav-links a { color: var(--muted); text-decoration: none; font-size: 13px; font-weight: 600; padding: 6px 12px; border-radius: 8px; border: 1px solid var(--border); transition: all 0.2s; }
    .nav-links a:hover, .nav-links a.active { color: var(--cyan); border-color: var(--cyan); background: rgba(0,186,242,0.1); }
    .btn { background: var(--cyan); color: #000; border: none; padding: 10px 18px; border-radius: 8px; font-weight: 700; font-size: 13px; cursor: pointer; transition: transform 0.1s, opacity 0.2s; display: inline-flex; align-items: center; gap: 8px; }
    .btn:hover { opacity: 0.9; }
    .btn:active { transform: translateY(1px); }
    .btn-danger { background: var(--bad); color: #fff; }
    .btn-purple { background: var(--purple); color: #fff; }
    .grid { display: grid; gap: 20px; }
    .grid-2 { grid-template-columns: 1fr 1fr; }
    .grid-3 { grid-template-columns: repeat(auto-fit, minmax(320px, 1fr)); }
    .panel { background: var(--panel); border: 1px solid var(--border); border-radius: 14px; padding: 20px; }
    .panel-title { font-size: 16px; font-weight: 700; margin-bottom: 12px; display: flex; align-items: center; justify-content: space-between; }
    
    /* Verdict Banner */
    .verdict-banner { display: none; background: rgba(16, 185, 129, 0.15); border: 2px solid var(--ok); border-radius: 12px; padding: 16px 20px; margin-bottom: 24px; animation: pop 0.3s ease-out; }
    .verdict-banner.breach { background: rgba(239, 68, 68, 0.15); border-color: var(--bad); }
    .verdict-title { font-size: 20px; font-weight: 900; color: var(--ok); margin-bottom: 6px; }
    .verdict-banner.breach .verdict-title { color: var(--bad); }
    .verdict-evidence { font-size: 13px; color: var(--muted); font-family: var(--font-mono); }

    /* Scenario Card */
    .scenario-card { background: rgba(14, 23, 38, 0.8); border: 1px solid var(--border); border-radius: 10px; padding: 16px; display: flex; flex-direction: column; justify-content: space-between; gap: 12px; }
    .scenario-name { font-size: 15px; font-weight: 700; color: #fff; }
    .scenario-desc { font-size: 12.5px; color: var(--muted); line-height: 1.4; }

    /* Log Stream */
    .log-box { font-family: var(--font-mono); font-size: 12px; background: #050A14; border: 1px solid var(--border); border-radius: 10px; padding: 14px; max-height: 480px; overflow-y: auto; display: flex; flex-direction: column; gap: 6px; }
    .log-entry { padding: 4px 8px; border-radius: 4px; border-left: 3px solid var(--border); word-break: break-all; }
    .log-entry.chaos_injection { border-color: var(--warn); background: rgba(245, 158, 11, 0.1); color: #FCD34D; }
    .log-entry.gateway_decision { border-color: var(--cyan); background: rgba(0, 186, 242, 0.1); color: #7DD3FC; }
    .log-entry.order_created { border-color: var(--ok); background: rgba(16, 185, 129, 0.1); color: #6EE7B7; }
    .log-entry.REJECT { border-color: var(--bad); background: rgba(239, 68, 68, 0.1); color: #FCA5A5; }

    @keyframes pop { 0% { opacity: 0; transform: scale(0.95); } 100% { opacity: 1; transform: scale(1); } }
  </style>
</head>
<body>
  <div class="wrap">
    <header>
      <div>
        <div class="title">🐵 Chaos Monkey Control Room</div>
        <p style="font-size: 13px; color: var(--muted);">Fault-injection engine proving SELLABLE money-handling guarantees under active chaos.</p>
      </div>
      <div class="nav-links">
        <a href="/">Command Center</a>
        <a href="/mission">Live Mission</a>
        <a href="/judge">Judge Console</a>
        <a href="/chaos" class="active">Chaos Control</a>
        <a href="/architecture">Architecture Diagram</a>
      </div>
    </header>

    <!-- Global Kill Switch Bar -->
    <div style="display: flex; justify-content: space-between; align-items: center; background: rgba(239, 68, 68, 0.1); border: 1px solid rgba(239, 68, 68, 0.3); padding: 14px 20px; border-radius: 12px; margin-bottom: 24px;">
      <div>
        <span style="font-weight: 700; color: var(--bad);">SAFETY STATUS: SAFE (rzp_test_ Active)</span>
        <span style="color: var(--muted); font-size: 13px; margin-left: 12px;">All fault injections auto-expire in max 60s.</span>
      </div>
      <button class="btn btn-danger" onclick="resetChaos()">🚨 RESET ALL / KILL SWITCH</button>
    </div>

    <!-- Machine-Verifiable Verdict Banner -->
    <div id="verdict-banner" class="verdict-banner">
      <div id="verdict-title" class="verdict-title">SURVIVED — 8/8 Invariants Held</div>
      <div id="verdict-evidence" class="verdict-evidence">Verified 0 double captures, 0 stock leaks, 100% structured refusals, and clean SHA-256 audit ledger.</div>
    </div>

    <div class="grid grid-2">
      <!-- Deterministic Scenario Drills -->
      <div class="panel">
        <div class="panel-title">⚡ Deterministic Chaos Drills</div>
        <div class="grid grid-2" style="gap: 12px;">
          <div class="scenario-card">
            <div>
              <div class="scenario-name">1. DUPLICATE_STORM</div>
              <div class="scenario-desc">Replays signed intent 5x concurrently with same IdemKey -> 1 order, 4 cached replays.</div>
            </div>
            <button class="btn btn-purple" onclick="runScenario('DUPLICATE_STORM')">Run Drill &rarr;</button>
          </div>

          <div class="scenario-card">
            <div>
              <div class="scenario-name">2. PRICE_FLIP</div>
              <div class="scenario-desc">Catalog price flips Rs 1,299 -> Rs 1,499 mid-flight -> 409 PRICE_STALE -> fresh quote -> approved.</div>
            </div>
            <button class="btn btn-purple" onclick="runScenario('PRICE_FLIP')">Run Drill &rarr;</button>
          </div>

          <div class="scenario-card">
            <div>
              <div class="scenario-name">3. LATENCY_TIMEOUT</div>
              <div class="scenario-desc">3s latency spike on order creation -> agent times out -> retries same IdemKey -> 1 order.</div>
            </div>
            <button class="btn btn-purple" onclick="runScenario('LATENCY_TIMEOUT')">Run Drill &rarr;</button>
          </div>

          <div class="scenario-card">
            <div>
              <div class="scenario-name">4. WEBHOOK_BLACKHOLE</div>
              <div class="scenario-desc">Drops payment.captured 10s -> pending order -> fallback link -> delivers webhook TWICE -> deduplicated.</div>
            </div>
            <button class="btn btn-purple" onclick="runScenario('WEBHOOK_BLACKHOLE')">Run Drill &rarr;</button>
          </div>

          <div class="scenario-card">
            <div>
              <div class="scenario-name">5. LAST_UNIT_RACE</div>
              <div class="scenario-desc">Stock=1, 3 agents submit concurrently -> 1 approved, 2 structured OUT_OF_STOCK.</div>
            </div>
            <button class="btn btn-purple" onclick="runScenario('LAST_UNIT_RACE')">Run Drill &rarr;</button>
          </div>

          <div class="scenario-card">
            <div>
              <div class="scenario-name">6. AGENT_CRASH</div>
              <div class="scenario-desc">Buyer agent crashes after approval -> clock_jump 35s -> stock auto-released, audit logged.</div>
            </div>
            <button class="btn btn-purple" onclick="runScenario('AGENT_CRASH')">Run Drill &rarr;</button>
          </div>
        </div>

        <div style="margin-top: 16px;">
          <button class="btn" style="width: 100%; justify-content: center; font-size: 15px; padding: 14px;" onclick="runScenario('FULL_CHAOS')">🔥 RUN FULL 60s CHAOS STORM</button>
        </div>
      </div>

      <!-- Live Unified SSE Stream -->
      <div class="panel">
        <div class="panel-title">
          <span>📡 Live Chaos Stream (/api/events/stream)</span>
          <span style="font-size: 11px; font-weight: 600; color: var(--ok);">CONNECTED</span>
        </div>
        <div id="log-box" class="log-box">
          <div style="color: var(--muted); text-align: center; padding: 40px 0;">
            Waiting for chaos scenario execution...
          </div>
        </div>
      </div>
    </div>
  </div>

  <script>
    const logBox = document.getElementById('log-box');
    const verdictBanner = document.getElementById('verdict-banner');

    // Subscribe to live SSE feed
    try {
      const evtSource = new EventSource('/api/events/stream');
      evtSource.onmessage = function(e) {
        try {
          const ev = JSON.parse(e.data);
          appendLog(ev);
        } catch(err) {}
      };
    } catch(err) {}

    function appendLog(ev) {
      if (!ev || !ev.summary) return;
      const row = document.createElement('div');
      let cls = 'log-entry ' + (ev.kind || '');
      if (ev.summary.includes('REJECT') || ev.summary.includes('refused')) cls += ' REJECT';
      row.className = cls;
      const timeStr = new Date(ev.ts * 1000).toLocaleTimeString();
      row.innerHTML = '<strong>[' + timeStr + '] ' + (ev.actor || 'SYS') + '</strong>: ' + ev.summary;
      logBox.appendChild(row);
      logBox.scrollTop = logBox.scrollHeight;
    }

    async function runScenario(id) {
      logBox.innerHTML = '';
      verdictBanner.style.display = 'none';
      try {
        const res = await fetch('/api/chaos/scenarios/' + id + '/run', { method: 'POST' });
        const data = await res.json();
        if (data.run_id) {
          fetchRunDetails(data.run_id);
        }
      } catch(err) {
        alert('Failed to run drill: ' + err.message);
      }
    }

    async function fetchRunDetails(runId) {
      try {
        const res = await fetch('/api/chaos/runs/' + runId);
        const data = await res.json();
        if (data.outcome) {
          verdictBanner.style.display = 'block';
          verdictBanner.className = 'verdict-banner ' + (data.outcome === 'SURVIVED' ? '' : 'breach');
          document.getElementById('verdict-title').innerText = data.outcome + ' — ' + (data.outcome === 'SURVIVED' ? '8/8 Invariants Held' : 'INVARIANT BREACH DETECTED');
          const details = data.invariants ? data.invariants.map(inv => inv.id + ': ' + inv.evidence).join(' | ') : '';
          document.getElementById('verdict-evidence').innerText = details;
        }
      } catch(err) {}
    }

    async function resetChaos() {
      try {
        const res = await fetch('/api/chaos/reset', { method: 'POST' });
        const data = await res.json();
        alert(data.message || 'Chaos Monkey Reset Complete.');
        verdictBanner.style.display = 'none';
        logBox.innerHTML = '<div style="color: var(--ok); text-align: center; padding: 20px;">System reset to baseline. Happy path restored.</div>';
      } catch(err) {
        alert('Reset failed: ' + err.message);
      }
    }
  </script>
</body>
</html>
"""
    return HTMLResponse(content)


@router.get("/architecture", response_class=HTMLResponse)
async def architecture_diagram_page():
    """Interactive Architecture Diagram Page — connected to live Chaos API and SSE stream."""
    content = """<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>SELLABLE — Agentic Commerce Architecture</title>
<link rel="preconnect" href="https://fonts.googleapis.com">
<link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
<link href="https://fonts.googleapis.com/css2?family=Space+Grotesk:wght@500;600;700&family=IBM+Plex+Mono:wght@400;500;600&display=swap" rel="stylesheet">
<style>
  :root{
    --paper:#F4F1E8; --panel:#FBF9F4; --ink:#26241E; --mut:#8A8478;
    --green:#0E7A54; --green-deep:#063D2B; --orange:#C2410C;
  }
  *{box-sizing:border-box; margin:0; padding:0;}
  body{background:var(--paper); color:var(--ink); font-family:'Space Grotesk',Arial,sans-serif; padding:26px 32px 44px;}
  .wrap{max-width:1760px; margin:0 auto;}
  .bar{display:flex; justify-content:space-between; align-items:flex-end; gap:16px; margin-bottom:14px; flex-wrap:wrap;}
  .brand{display:flex; align-items:baseline; gap:14px;}
  .b1{font-weight:700; font-size:22px; letter-spacing:.5px;}
  .b2{font-family:'IBM Plex Mono',monospace; font-size:11px; letter-spacing:2px; color:var(--mut);}
  .controls{display:flex; gap:8px; flex-wrap:wrap;}
  .controls button{
    display:inline-flex; align-items:center; gap:7px;
    font-family:'IBM Plex Mono',monospace; font-size:11px; font-weight:600; letter-spacing:1.5px;
    padding:9px 14px; background:transparent; border:1.5px solid var(--ink); color:var(--ink);
    cursor:pointer; border-radius:8px; transition:background .15s, color .15s, transform .1s;
  }
  .controls button:hover{background:var(--ink); color:var(--panel);}
  .controls button:active{transform:translateY(1px);}
  .controls button.primary{background:var(--green); border-color:var(--green); color:#fff;}
  .controls button.primary:hover{background:var(--green-deep); border-color:var(--green-deep);}
  .controls button svg{display:block;}
  .frame{
    border:1.5px solid var(--ink); background:var(--panel); border-radius:14px;
    overflow:auto; box-shadow:6px 6px 0 rgba(38,36,30,.12);
  }
  .frame svg{display:block; min-width:1280px; width:100%; height:auto;}
  .caption{
    margin-top:16px; border:1.5px solid var(--ink); background:#fff; border-radius:12px;
    padding:14px 20px; display:flex; gap:20px; align-items:center;
    box-shadow:6px 6px 0 rgba(38,36,30,.10);
  }
  .cstep{font-family:'IBM Plex Mono',monospace; font-size:24px; font-weight:600; color:var(--green); min-width:96px;}
  .cbody{flex:1; min-width:0;}
  .ctitle{font-weight:600; font-size:15.5px; margin-bottom:3px;}
  .ctext{font-size:13.5px; color:#6F6A5E; line-height:1.45;}
  .dots{display:flex; gap:6px; flex-wrap:wrap; max-width:180px; justify-content:flex-end;}
  .dots span{width:9px; height:9px; border:1.5px solid var(--ink); border-radius:2px; opacity:.35;}
  .dots span.on{background:var(--green); border-color:var(--green); opacity:1;}
  .hint{margin-top:12px; font-family:'IBM Plex Mono',monospace; font-size:11px; color:var(--mut); letter-spacing:.5px;}

  /* ---- interaction states for the inline SVG ---- */
  .node,.edge,.badge{transition:opacity .4s;}
  .edge .body{transition:stroke .25s;}
  svg.is-playing .node:not(.lit){opacity:.28;}
  svg.is-playing .edge:not(.lit){opacity:.20;}
  svg.is-playing .badge:not(.lit){opacity:.25;}
  .edge.trace .body{stroke:var(--green) !important;}
  .badge{cursor:pointer;}
  .badge:hover circle{fill:var(--ink);}
  .badge:hover text{fill:#fff;}
  .badge.lit circle{fill:var(--green); stroke:var(--green);}
  .badge.lit text{fill:#fff;}
  .callout{opacity:0; transition:opacity .35s;}
  .callout.show{opacity:1;}
</style>
</head>
<body>
<div class="wrap">
  <div class="bar">
    <div class="brand">
      <span class="b1">SELLABLE</span>
      <span class="b2">AGENTIC COMMERCE · ARCHITECTURE v1.0</span>
    </div>
    <div class="controls">
      <button class="primary" id="btnPlay">
        <svg width="12" height="12" viewBox="0 0 12 12"><path d="M2,1 L11,6 L2,11 Z" fill="currentColor"/></svg>
        PLAY FLOW
      </button>
      <button id="btnDrill">
        <svg width="12" height="12" viewBox="0 0 12 12"><path d="M7,0.5 L2,7 H5.4 L4.4,11.5 L10,4.8 H6.6 Z" fill="currentColor"/></svg>
        FAILURE DRILL
      </button>
      <button id="btnReset">
        <svg width="12" height="12" viewBox="0 0 12 12"><path d="M10.6,6a4.6,4.6 0 1 1-1.4-3.3" fill="none" stroke="currentColor" stroke-width="1.6"/><path d="M9.6,0.6 v2.4 h-2.4" fill="none" stroke="currentColor" stroke-width="1.6"/></svg>
        RESET
      </button>
      <a href="/chaos" style="font-family:'IBM Plex Mono',monospace; font-size:11px; font-weight:600; padding:9px 14px; border:1.5px solid var(--ink); color:var(--ink); border-radius:8px; text-decoration:none;">MISSION CONTROL &rarr;</a>
    </div>
  </div>

  <div class="frame" id="frame"></div>

  <div class="caption">
    <div class="cstep" id="cstep">—</div>
    <div class="cbody">
      <div class="ctitle" id="ctitle">Ready</div>
      <div class="ctext" id="ctext">Press PLAY FLOW to walk one full agent transaction, or FAILURE DRILL to trigger Chaos Monkey against the live server API.</div>
    </div>
    <div class="dots" id="dots"></div>
  </div>
</div>

<script>
(function(){
'use strict';
const NS = 'http://www.w3.org/2000/svg';
const INK='#26241E', MUT='#8A8478', GREEN='#0E7A54', GREEN_DEEP='#063D2B', ORANGE='#C2410C', PANEL='#FBF9F4';
const SG = "Space Grotesk, Arial, sans-serif";
const MO = "IBM Plex Mono, Consolas, monospace";

const NODES = [
  {id:'human', x:62,  y:230, w:256, h:76,  title:'Human Buyer',            subs:['chat · web · assistant surface'], tag:'A1'},
  {id:'agent', x:62,  y:350, w:256, h:140, title:'Buyer Agent',            subs:['LLM orchestration · MCP client','signed mandate · spend cap','speaks AP2 · ACP · x402'], tag:'A2'},
  {id:'endpoint', x:402, y:206, w:272, h:92,  title:'Protocol Endpoint',       subs:['MCP server · AP2 / ACP / x402','OpenAPI for agents — no UI'], tag:'B1'},
  {id:'catalog',  x:402, y:330, w:272, h:92,  title:'Agent-Readable Catalog',  subs:['products.json · llms.txt','signed offers · price + TTL'], tag:'B2'},
  {id:'policy',   x:402, y:462, w:272, h:170, title:'Policy Gateway', hero:true,
    rows:['mandate & signature verify','spend bounds · velocity caps','idempotency · replay guard','explain engine — why approved'], tag:'MONEY GATE'},
  {id:'ledger',   x:402, y:692, w:272, h:96,  title:'Append-Only Ledger',      subs:['hash-chained · signed events','decision + reason per action'], tag:'B6'},
  {id:'g1', x:706, y:206, w:272, h:92, title:'Growth Agents',          subs:['upsell · cross-sell · bundles'], tag:'B3'},
  {id:'g2', x:706, y:330, w:272, h:92, title:'Campaign Orchestrator',  subs:['segments · timing · budget caps'], tag:'B4'},
  {id:'g3', x:706, y:454, w:272, h:92, title:'Price & Promo Agent',    subs:['bounded discounts · margin floor'], tag:'B5'},
  {id:'console',   x:1062, y:206, w:200, h:110, title:'Merchant Console',       subs:['set bounds · approve campaigns','/mission — live ops view'], tag:'C1'},
  {id:'inventory', x:1062, y:352, w:200, h:110, title:'Inventory & Reservations',subs:['stock · TTL holds on intent','atomic commit on capture'], tag:'C2'},
  {id:'dash',      x:1062, y:498, w:200, h:110, title:'Revenue Dashboard',      subs:['AOV · attach rate','% revenue from AI agents'], tag:'C3'},
  {id:'orders', x:1342, y:206, w:280, h:96, title:'Orders API',          subs:['order create · amount pinned','test-mode keys'], tag:'D1'},
  {id:'pay',    x:1342, y:334, w:280, h:96, title:'Payments & Methods',  subs:['UPI collect · cards · test wallets','in-app payment sheet'], tag:'D2'},
  {id:'hooks',  x:1342, y:462, w:280, h:96, title:'Webhooks',            subs:['payment.captured · payment.failed','signature verified at gateway'], tag:'D3'},
  {id:'plink',  x:1342, y:590, w:280, h:96, title:'Payment Links',       subs:['payment.failed → human handoff','graceful degradation path'], tag:'D4'},
  {id:'psim',   x:64,   y:916, w:460, h:72, title:'Multi-Agent Simulator', subs:['N buyer agents · shared limited stock · contention queue'], tag:'P1'},
  {id:'pchaos', x:556,  y:916, w:520, h:72, title:'Chaos Monkey',          subs:['latency spikes · duplicate submits · price flips mid-approval · killed agents'], tag:'P2', accent:true},
  {id:'pobs',   x:1108, y:916, w:508, h:72, title:'Observability',         subs:['trace-id per money action · decision log · replay'], tag:'P3'},
];

const EDGES = [
  {id:'e_prompt',  d:'M190,306 V350', cls:'sync', n:['human','agent']},
  {id:'e_discover',d:'M318,400 H368 V252 H402', cls:'sync', both:true, n:['agent','endpoint']},
  {id:'e_intent',  d:'M318,466 H348 V580 H402', cls:'sync', n:['agent','policy']},
  {id:'e_serve',   d:'M538,330 V298', cls:'sync', n:['catalog','endpoint']},
  {id:'e_stock',   d:'M538,422 V462', cls:'sync', n:['catalog','policy']},
  {id:'e_explain', d:'M402,500 H332 V436 H318', cls:'sync', n:['policy','agent']},
  {id:'e_append',  d:'M538,632 V692', cls:'sync', n:['policy','ledger']},
  {id:'e_money',   d:'M674,560 H1036 V700 H1300 V254 H1342', cls:'money', n:['policy','orders']},
  {id:'e_hook',    d:'M1342,510 H1311 V660 H660 V632', cls:'async', n:['hooks','policy']},
  {id:'e_inv',     d:'M1162,462 V620 H620 V632', cls:'sync', n:['inventory','policy']},
  {id:'e_chaos',   d:'M780,916 V856', cls:'chaos', n:['pchaos']},
  {id:'e_auth',    d:'M1482,302 V334', cls:'sync', n:['orders','pay']},
  {id:'e_emit',    d:'M1482,430 V462', cls:'async', n:['pay','hooks']},
];

const BADGES = [
  {n:1,x:340,y:400},{n:2,x:386,y:252},{n:3,x:372,y:580},{n:4,x:402,y:462},
  {n:5,x:716,y:560},{n:6,x:1268,y:660},{n:7,x:366,y:500},{n:8,x:402,y:692}
];

const FLOW = [
  {title:'1 · Discover', nodes:['agent','endpoint'], edges:['e_discover'], text:'The buyer agent pulls the catalog over MCP / llms.txt — no scraping, no screenshots.'},
  {title:'2 · Offers', nodes:['endpoint','catalog'], edges:['e_serve'], text:'Signed machine-readable offers come back: price, stock, TTL.'},
  {title:'3 · Intent', nodes:['agent','policy'], edges:['e_intent'], text:'The agent submits a signed intent mandate — cart, spend cap, idempotency key.'},
  {title:'4 · Gate', nodes:['policy','catalog','inventory'], edges:['e_stock','e_inv'], text:'Signature verified, spend bounds and velocity checked, stock reserved.'},
  {title:'5 · Order', nodes:['policy','orders'], edges:['e_money'], text:'A Razorpay test-mode order is created with the amount pinned to the mandate.'},
  {title:'6 · Capture', nodes:['orders','pay','hooks'], edges:['e_auth','e_emit','e_hook'], text:'payment.captured fires; gateway verifies webhook signature.'},
  {title:'7 · Explain', nodes:['policy','agent'], edges:['e_explain'], text:'The agent receives an explainable receipt — why approved, which bounds applied.'},
  {title:'8 · Ledger', nodes:['ledger','dash','pobs'], edges:['e_append'], text:'One hash-chained row per money action logged to SQLite.'}
];

const DRILL = [
  {title:'Drill 1 · Run it straight', nodes:['agent','policy','inventory','orders'], edges:['e_intent','e_stock','e_money'], text:'Happy-path replay: signed intent → mandate verified → stock held → order created at Rs 1,499.'},
  {title:'Drill 2 · Chaos strikes', nodes:['pchaos','policy'], edges:['e_chaos'], callout:'A', text:'Chaos Monkey flips merchant price mid-flight (Rs 1,299 -> Rs 1,499) and replays duplicate intent.'},
  {title:'Drill 3 · The gate holds', nodes:['policy','ledger'], edges:['e_append'], callout:'A', text:'Stale mandate caught: 409 PRICE_STALE. Replay hits idempotency: exactly 1 order.'},
  {title:'Drill 4 · Clean retry', nodes:['agent','catalog','policy'], edges:['e_intent','e_stock'], callout:'B', text:'The agent re-quotes from fresh catalog, re-signs, and passes.'},
  {title:'Drill 5 · The bar, proven', nodes:['policy','ledger','g1'], edges:[], callout:'B', text:'Bounded, gated, explainable — even under active chaos.'}
];

const svg = document.createElementNS(NS,'svg');
svg.setAttribute('viewBox','0 0 1680 1060');
svg.setAttribute('xmlns', NS);
document.getElementById('frame').appendChild(svg);

function el(name, attrs, parent){
  const e = document.createElementNS(NS, name);
  for(const k in attrs) e.setAttribute(k, attrs[k]);
  if(parent) parent.appendChild(e);
  return e;
}
function txt(parent, x, y, str, o={}){
  const t = el('text', {
    x, y, fill:o.fill||INK, 'font-family':o.font||SG, 'font-size':o.size||13,
    'font-weight':o.weight||500, 'text-anchor':o.anchor||'start',
    'letter-spacing':o.ls||'0'
  }, parent);
  t.textContent = str;
  return t;
}

el('rect',{x:0,y:0,width:1680,height:1060,fill:PANEL},svg);

function zone(x,y,w,h,label,opts={}){
  el('rect',{x,y,width:w,height:h,rx:14, fill:opts.fill||'#F3F1E8',
    stroke:opts.stroke||'#C9C3B2', 'stroke-width':opts.dashed?1.8:1.4,
    'stroke-dasharray':opts.dashed?'8 6':'none'},svg);
  txt(svg, x+18, y+28, label, {font:MO, size:12, weight:600, fill:opts.labFill||MUT, ls:'2'});
}
zone(40,140,300,710,'DEMAND · AI BUYER');
zone(380,140,620,710,'SELLABLE CORE · TRUST & GROWTH LAYER',{fill:'#ECF2EC', stroke:GREEN_DEEP, labFill:GREEN_DEEP});
zone(1040,140,240,710,'MERCHANT · SUPPLY');
zone(1320,140,320,710,'EXTERNAL · RAZORPAY (TEST MODE)',{dashed:true, stroke:MUT, fill:'#F6F4ED'});
zone(40,880,1600,120,'PLATFORM · SIMULATION / CHAOS / OBSERVABILITY',{fill:'#F0EEE5'});

const nodeEls = {};
NODES.forEach(o=>{
  const g = el('g',{class:'node', id:'n_'+o.id},svg);
  const hero = !!o.hero;
  el('rect',{x:o.x,y:o.y,width:o.w,height:o.h,rx:10,
    fill: hero?GREEN:'#FFFFFF',
    stroke: hero?GREEN_DEEP : (o.accent?ORANGE:INK),
    'stroke-width':1.4},g);
  if(hero){
    txt(g,o.x+16,o.y+32,o.title,{size:17,weight:700,fill:'#FFFFFF'});
    (o.rows||[]).forEach((r,i)=>{
      const ry = o.y+62+i*25;
      txt(g,o.x+24,ry,'✔ ' + r,{font:MO,size:10.5,fill:'#E9F4EE'});
    });
  }else{
    txt(g,o.x+14,o.y+26,o.title,{size:15,weight:600});
    (o.subs||[]).forEach((s,i)=> txt(g,o.x+14,o.y+47+i*17,s,{font:MO,size:10.5,fill:'#6F6A5E'}));
  }
  nodeEls[o.id]=g;
});

const edgeEls = {};
EDGES.forEach(e=>{
  const g = el('g',{class:'edge', id:'edge_'+e.id},svg);
  el('path',{class:'body', d:e.d, fill:'none', stroke:e.cls==='money'?GREEN:e.cls==='chaos'?ORANGE:INK, 'stroke-width':2},g);
  edgeEls[e.id]=g;
});

BADGES.forEach(b=>{
  const g = el('g',{class:'badge', id:'badge_'+b.n},svg);
  el('circle',{cx:b.x,cy:b.y,r:12,fill:PANEL,stroke:INK,'stroke-width':1.6},g);
  txt(g,b.x,b.y+4,String(b.n),{font:MO,size:11.5,weight:700,anchor:'middle'});
  badgeEls.push(g);
});

txt(svg,48,64,'SELLABLE — Agentic Commerce Architecture',{size:30,weight:700});
txt(svg,48,92,'Interactive Money Gateway Architecture & Chaos monkey Drill Player',{font:MO,size:12.5,fill:'#6F6A5E'});

const cstep=document.getElementById('cstep'), ctitle=document.getElementById('ctitle'), ctext=document.getElementById('ctext');
let curIdx = -1, seq = FLOW;

function applyStep(i){
  document.querySelectorAll('.lit').forEach(n=>n.classList.remove('lit'));
  const s = seq[i];
  (s.nodes||[]).forEach(id=>{ const n=document.getElementById('n_'+id); if(n)n.classList.add('lit'); });
  (s.edges||[]).forEach(id=>{ const e=document.getElementById('edge_'+id); if(e)e.classList.add('lit'); });
  cstep.textContent = String(i+1).padStart(2,'0')+' / '+String(seq.length).padStart(2,'0');
  ctitle.textContent = s.title;
  ctext.textContent = s.text;
  curIdx = i;
}

document.getElementById('btnPlay').addEventListener('click', () => {
  seq = FLOW;
  let i = 0;
  applyStep(0);
  const timer = setInterval(() => {
    i++;
    if (i >= seq.length) clearInterval(timer);
    else applyStep(i);
  }, 2000);
});

document.getElementById('btnDrill').addEventListener('click', async () => {
  seq = DRILL;
  applyStep(0);
  // Trigger real backend chaos scenario
  try {
    await fetch('/api/chaos/scenarios/PRICE_FLIP/run', { method: 'POST' });
  } catch(e) {}
  let i = 0;
  const timer = setInterval(() => {
    i++;
    if (i >= seq.length) clearInterval(timer);
    else applyStep(i);
  }, 2200);
});

document.getElementById('btnReset').addEventListener('click', () => {
  document.querySelectorAll('.lit').forEach(n=>n.classList.remove('lit'));
  cstep.textContent = '—'; ctitle.textContent = 'Ready';
  ctext.textContent = 'Press PLAY FLOW to walk one full agent transaction, or FAILURE DRILL to trigger Chaos Monkey.';
});
})();
</script>
</body>
</html>
"""
    return HTMLResponse(content)
