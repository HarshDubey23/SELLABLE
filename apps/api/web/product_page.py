"""GET / — the product.

This page has one job: make a stranger understand, without reading any
documentation, that an AI agent did the shopping and could not have done
the paying.

It is deliberately not a security console. The controls are visible
because they are the product, not because dashboards look impressive:
each stage lights up from a real HTTP response, every hash and id shown
comes from runtime state, and the failure buttons cause genuine state
transitions rather than animations.
"""
from __future__ import annotations

from fastapi import APIRouter
from fastapi.responses import HTMLResponse

router = APIRouter()

PAGE = r"""<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<link rel="icon" href="data:image/svg+xml,%3Csvg xmlns='http://www.w3.org/2000/svg' viewBox='0 0 32 32'%3E%3Crect width='32' height='32' rx='7' fill='%230a0b0d'/%3E%3Cpath d='M9 21V11h8a3 3 0 010 6h-8' stroke='%234d8dff' stroke-width='2.4' fill='none' stroke-linecap='round'/%3E%3C/svg%3E">
<title>SELLABLE — autonomous commerce without autonomous money</title>
<style>
  *, *::before, *::after { box-sizing: border-box; }
  :root {
    --bg:#0a0b0d; --surface:#101216; --surface-2:#15181d; --line:#22262e;
    --line-soft:#1a1d23; --ink:#eef1f6; --ink-2:#a7afbd; --ink-3:#6b7383;
    --accent:#4d8dff; --accent-dim:#1d3a6b;
    --ok:#3fbf87; --warn:#e0a33a; --bad:#e5575f; --amber:#d4913b;
    --mono: ui-monospace, "SF Mono", "Cascadia Mono", Menlo, monospace;
    --sans: -apple-system, BlinkMacSystemFont, "Segoe UI", Inter, Roboto, sans-serif;
    --r:10px;
  }
  html { -webkit-text-size-adjust: 100%; }
  body {
    margin:0; background:var(--bg); color:var(--ink); font-family:var(--sans);
    font-size:15px; line-height:1.6; -webkit-font-smoothing:antialiased;
  }
  a { color:var(--accent); }
  .wrap { max-width:1080px; margin:0 auto; padding:0 24px; }

  /* ---------- top bar ---------- */
  .top {
    border-bottom:1px solid var(--line-soft); position:sticky; top:0;
    background:rgba(10,11,13,.85); backdrop-filter:blur(12px); z-index:50;
  }
  .top .wrap { display:flex; align-items:center; gap:16px; height:60px; }
  .brand { font-weight:700; letter-spacing:-.02em; font-size:16px; }
  .brand span { color:var(--ink-3); font-weight:400; margin-left:10px; font-size:13px; }
  .top nav { margin-left:auto; display:flex; gap:20px; font-size:13px; }
  .top nav a { color:var(--ink-2); text-decoration:none; }
  .top nav a:hover { color:var(--ink); }
  .mode {
    font-family:var(--mono); font-size:11px; letter-spacing:.04em;
    border:1px solid var(--line); border-radius:999px; padding:4px 11px;
    color:var(--ink-2); white-space:nowrap;
  }
  .mode.sim { border-color:#4a3a1a; color:var(--amber); background:rgba(212,145,59,.07); }
  .mode.live { border-color:#1d4a34; color:var(--ok); background:rgba(63,191,135,.07); }

  /* ---------- hero ---------- */
  .hero { padding:72px 0 40px; border-bottom:1px solid var(--line-soft); }
  .hero-grid { display:grid; grid-template-columns:1.35fr .85fr; gap:48px; align-items:start; }
  .invariant {
    border:1px solid var(--line); border-radius:14px; background:var(--surface);
    padding:20px; font-size:13.5px;
  }
  .invariant h3 {
    margin:0 0 14px; font-size:11px; letter-spacing:.09em; text-transform:uppercase;
    color:var(--ink-3); font-weight:650;
  }
  .invariant ul { list-style:none; margin:0; padding:0; display:grid; gap:9px; }
  .invariant li { display:grid; grid-template-columns:16px 1fr; gap:10px; color:var(--ink-2); }
  .invariant .y { color:var(--ok); font-family:var(--mono); }
  .invariant .n { color:var(--bad); font-family:var(--mono); }
  .invariant p {
    margin:16px 0 0; padding-top:14px; border-top:1px solid var(--line-soft);
    color:var(--ink-3); font-size:12.5px;
  }
  @media (max-width:900px) { .hero-grid { grid-template-columns:1fr; gap:32px; } }
  h1 {
    font-size:clamp(30px,4.4vw,46px); line-height:1.1; letter-spacing:-.03em;
    font-weight:680; margin:0 0 18px; max-width:17ch;
  }
  h1 em {
    font-style:normal; color:var(--ink);
    box-shadow:inset 0 -0.14em 0 rgba(77,141,255,.45);
  }
  .lede { color:var(--ink-2); max-width:60ch; margin:0 0 34px; font-size:16.5px; }

  .ask {
    background:var(--surface); border:1px solid var(--line); border-radius:14px;
    padding:20px; display:grid; gap:14px;
  }
  .ask label {
    display:block; font-size:11px; letter-spacing:.09em; text-transform:uppercase;
    color:var(--ink-3); margin-bottom:7px; font-weight:600;
  }
  .ask input {
    width:100%; background:var(--bg); border:1px solid var(--line);
    border-radius:var(--r); padding:12px 14px; color:var(--ink);
    font-size:15px; font-family:inherit;
  }
  .ask input:focus { outline:none; border-color:var(--accent-dim); }
  .row { display:grid; grid-template-columns:1fr 190px; gap:14px; }
  .go {
    background:var(--accent); color:#06121f; border:0; border-radius:var(--r);
    padding:13px 22px; font-size:15px; font-weight:650; cursor:pointer;
    font-family:inherit; transition:opacity .15s;
  }
  .go:hover { opacity:.9; }
  .go:disabled { opacity:.45; cursor:default; }
  .examples { display:flex; gap:8px; flex-wrap:wrap; }
  .examples button {
    background:transparent; border:1px solid var(--line); color:var(--ink-2);
    border-radius:999px; padding:5px 13px; font-size:12.5px; cursor:pointer;
    font-family:inherit;
  }
  .examples button:hover { border-color:var(--accent-dim); color:var(--ink); }

  /* ---------- stage rail ---------- */
  .rail { display:flex; gap:0; margin:44px 0 30px; flex-wrap:wrap; }
  .stage {
    flex:1 1 0; min-width:104px; padding:12px 10px 12px 0; position:relative;
    border-top:2px solid var(--line-soft); opacity:.4; transition:opacity .3s;
  }
  .stage + .stage { padding-left:14px; }
  .stage.on { opacity:1; border-top-color:var(--accent); }
  .stage.done { opacity:1; border-top-color:var(--ok); }
  .stage.err { opacity:1; border-top-color:var(--bad); }
  .stage.hold { opacity:1; border-top-color:var(--amber); }
  .stage .n {
    font-family:var(--mono); font-size:10px; color:var(--ink-3);
    letter-spacing:.08em;
  }
  .stage .t { font-size:12.5px; font-weight:600; margin-top:3px; }
  .stage .s { font-size:11px; color:var(--ink-3); margin-top:2px; min-height:14px; }

  /* ---------- cards ---------- */
  section { padding:30px 0; border-top:1px solid var(--line-soft); }
  section:first-of-type { border-top:0; }
  h2 {
    font-size:12px; text-transform:uppercase; letter-spacing:.1em;
    color:var(--ink-3); font-weight:650; margin:0 0 4px;
  }
  .h2note { color:var(--ink-3); font-size:13px; margin:0 0 18px; max-width:62ch; }
  .card {
    background:var(--surface); border:1px solid var(--line); border-radius:var(--r);
    padding:16px 18px;
  }
  .cards { display:grid; gap:10px; }
  .listing { display:grid; grid-template-columns:1fr auto; gap:14px; align-items:start; }
  .listing .name { font-weight:560; font-size:14.5px; }
  .listing .meta { color:var(--ink-3); font-size:12.5px; margin-top:4px; }
  .listing .price { font-family:var(--mono); font-size:15px; text-align:right; white-space:nowrap; }
  .listing .price small { display:block; color:var(--ink-3); font-size:11px; font-family:var(--sans); }
  .ev {
    display:inline-block; font-family:var(--mono); font-size:10px; letter-spacing:.05em;
    border-radius:4px; padding:2px 7px; margin-right:6px; border:1px solid;
  }
  .ev-OBSERVED     { color:var(--ok);   border-color:#1d4a34; background:rgba(63,191,135,.08); }
  .ev-FX_CONVERTED { color:var(--warn); border-color:#4a3a1a; background:rgba(224,163,58,.08); }
  .ev-MOCK_SOURCE  { color:var(--ink-3);border-color:var(--line); }
  .ev-UNVERIFIED   { color:var(--ink-3);border-color:var(--line); }
  .ev-MERCHANT     { color:var(--accent); border-color:var(--accent-dim); background:rgba(77,141,255,.08); }

  .merchant {
    border-color:var(--accent-dim); background:linear-gradient(180deg,rgba(77,141,255,.06),transparent);
  }
  .buy {
    background:var(--ok); color:#04140d; border:0; border-radius:8px; padding:10px 18px;
    font-weight:650; cursor:pointer; font-family:inherit; font-size:14px; margin-top:14px;
  }
  .buy:disabled { opacity:.45; cursor:default; }

  /* ---------- rules ---------- */
  .rules { display:grid; grid-template-columns:repeat(auto-fill,minmax(168px,1fr)); gap:7px; }
  .rule {
    border:1px solid var(--line); border-radius:7px; padding:8px 10px;
    font-family:var(--mono); font-size:11px; display:flex; gap:8px; align-items:center;
  }
  .rule .dot { width:6px; height:6px; border-radius:50%; flex:none; background:var(--ink-3); }
  .rule.pass .dot { background:var(--ok); }
  .rule.fail .dot { background:var(--bad); }
  .rule.fail { border-color:#4a1f22; background:rgba(229,87,95,.07); }

  /* ---------- execution ---------- */
  .states { display:flex; flex-wrap:wrap; gap:6px; }
  .st {
    font-family:var(--mono); font-size:11px; border:1px solid var(--line);
    border-radius:6px; padding:6px 10px; color:var(--ink-3);
  }
  .st.at { color:var(--ink); border-color:var(--accent); background:rgba(77,141,255,.09); }
  .st.past { color:var(--ink-2); border-color:#1d4a34; }
  .st.hold { color:var(--amber); border-color:#4a3a1a; background:rgba(212,145,59,.09); }
  .st.bad  { color:var(--bad); border-color:#4a1f22; }

  .faults { display:flex; gap:8px; flex-wrap:wrap; margin-top:14px; }
  .faults button {
    background:transparent; border:1px solid var(--line); color:var(--ink-2);
    border-radius:8px; padding:8px 13px; font-size:13px; cursor:pointer; font-family:inherit;
  }
  .faults button:hover:not(:disabled) { border-color:var(--amber); color:var(--ink); }
  .faults button:disabled { opacity:.4; cursor:default; }
  .rec {
    background:var(--amber); color:#1a1204; border:0; border-radius:8px;
    padding:9px 16px; font-weight:650; cursor:pointer; font-family:inherit; font-size:13.5px;
  }

  /* ---------- proof drawer ---------- */
  details.proof { border:1px solid var(--line); border-radius:var(--r); background:var(--surface); }
  details.proof summary {
    cursor:pointer; padding:13px 18px; font-size:13px; color:var(--ink-2);
    list-style:none; display:flex; align-items:center; gap:9px;
  }
  details.proof summary::-webkit-details-marker { display:none; }
  details.proof summary::before { content:"▸"; color:var(--ink-3); }
  details.proof[open] summary::before { content:"▾"; }
  .kv { border-top:1px solid var(--line-soft); padding:14px 18px; display:grid; gap:7px; }
  .kv div { display:grid; grid-template-columns:190px 1fr; gap:14px; font-family:var(--mono); font-size:11.5px; }
  .kv dt, .kv .k { color:var(--ink-3); }
  .kv .v { color:var(--ink-2); word-break:break-all; }

  .note {
    font-size:13px; color:var(--ink-3); border-left:2px solid var(--line);
    padding-left:14px; margin:14px 0 0;
  }
  .err {
    border:1px solid #4a1f22; background:rgba(229,87,95,.07); border-radius:var(--r);
    padding:13px 16px; font-size:13.5px; color:#f0a8ac;
  }
  .ok-banner {
    border:1px solid #1d4a34; background:rgba(63,191,135,.07); border-radius:var(--r);
    padding:13px 16px; font-size:13.5px; color:#9fe0c2;
  }
  .hold-banner {
    border:1px solid #4a3a1a; background:rgba(212,145,59,.07); border-radius:var(--r);
    padding:13px 16px; font-size:13.5px; color:#ecc98a;
  }
  .hidden { display:none !important; }
  .spin { display:inline-block; width:11px; height:11px; border:2px solid var(--line);
          border-top-color:var(--accent); border-radius:50%; animation:sp .7s linear infinite; }
  @keyframes sp { to { transform:rotate(360deg); } }
  footer { padding:40px 0 60px; color:var(--ink-3); font-size:13px; border-top:1px solid var(--line-soft); }
  footer a { color:var(--ink-2); }
  @media (max-width:720px) {
    .row { grid-template-columns:1fr; }
    .kv div { grid-template-columns:1fr; gap:2px; }
    .top nav { display:none; }
  }
</style>
</head>
<body>

<div class="top"><div class="wrap">
  <div class="brand">SELLABLE<span>autonomous commerce without autonomous money</span></div>
  <nav>
    <a href="/judge">Judge walkthrough</a>
    <a href="/console">Console</a>
    <a href="/docs">API</a>
  </nav>
  <div class="mode" id="mode">checking…</div>
</div></div>

<div class="wrap">

  <div class="hero">
  <div class="hero-grid">
    <div>
    <h1>An agent that shops for you, and <em>cannot</em> pay for you.</h1>
    <p class="lede">
      Give it an intent and a budget. It searches the market, weighs the evidence and
      proposes a purchase. Then a deterministic policy gateway — no model, no network —
      decides whether any money moves. Watch both halves happen below.
    </p>

    <div class="ask">
      <div>
        <label for="q">What should the agent buy?</label>
        <input id="q" value="cricket bat with good reviews" autocomplete="off">
      </div>
      <div class="row">
        <div>
          <label for="b">Budget ceiling (₹)</label>
          <input id="b" type="number" value="2000" min="1">
        </div>
        <div style="display:flex;align-items:flex-end;">
          <button class="go" id="run" style="width:100%">Run mission</button>
        </div>
      </div>
      <div class="examples">
        <button data-q="cricket bat with good reviews" data-b="2000">cricket bat under ₹2,000</button>
        <button data-q="wireless earbuds long battery" data-b="1500">earbuds under ₹1,500</button>
        <button data-q="cricket bat with good reviews" data-b="1000">a budget too small</button>
      </div>
    </div>
    </div>

    <div class="invariant">
      <h3>What the agent can and cannot do</h3>
      <ul>
        <li><span class="y">+</span><span>Search the open web for market evidence</span></li>
        <li><span class="y">+</span><span>Compare, reason and revise its choice</span></li>
        <li><span class="y">+</span><span>Propose a SKU and a quantity</span></li>
        <li><span class="n">&minus;</span><span>Set or claim a price</span></li>
        <li><span class="n">&minus;</span><span>Widen its own budget or category scope</span></li>
        <li><span class="n">&minus;</span><span>Sign a mission or a user mandate</span></li>
        <li><span class="n">&minus;</span><span>Reach the payment API at all</span></li>
      </ul>
      <p>The bottom four aren't policy the model is asked to follow.
         They have no representation in the interface it talks to.</p>
    </div>
  </div>
  </div>

  <div class="rail" id="rail"></div>

  <section id="s-discovery" class="hidden">
    <h2>Discovery</h2>
    <p class="h2note" id="discovery-note"></p>
    <div class="cards" id="listings"></div>
    <p class="note" id="evidence-note"></p>
  </section>

  <section id="s-recommend" class="hidden">
    <h2>Recommendation</h2>
    <p class="h2note">The agent proposes a SKU. It never proposes an amount —
      the price below comes from the server-side catalog, not from the agent
      and not from any listing.</p>
    <div class="card merchant" id="merchant"></div>
  </section>

  <section id="s-policy" class="hidden">
    <h2>Policy gateway</h2>
    <p class="h2note">Twelve deterministic rules. No model call, no network call,
      no file read. First violation wins and the gateway fails closed.</p>
    <div class="rules" id="rules"></div>
    <div id="policy-outcome" style="margin-top:14px"></div>
  </section>

  <section id="s-execute" class="hidden">
    <h2>Execution</h2>
    <p class="h2note">Authorization is not payment. The execution state is written to
      disk before the provider is called, so a crash mid-flight is recoverable as
      <em>unknown</em> rather than lost.</p>
    <div class="card">
      <div class="states" id="states"></div>
      <div id="exec-outcome" style="margin-top:15px"></div>
      <div id="fault-box" class="hidden">
        <p class="note" style="margin-bottom:0">
          Try breaking it. These inject a real fault into the simulated provider and
          drive genuine state transitions — they are refused outright when real
          Razorpay credentials are configured.
        </p>
        <div class="faults">
          <button data-fault="remote_timeout">Provider times out after applying the write</button>
          <button data-fault="remote_lost">Request never reaches the provider</button>
          <button data-fault="remote_reject">Provider refuses definitively</button>
        </div>
      </div>
    </div>
  </section>

  <section id="s-proof" class="hidden">
    <h2>Technical proof</h2>
    <p class="h2note">Every value here is read back from runtime state after the run.</p>
    <details class="proof">
      <summary>Runtime identifiers, hashes and states</summary>
      <div class="kv" id="proof"></div>
    </details>
  </section>

  <footer>
    <p style="margin:0 0 6px">
      <a href="https://github.com/HarshDubey23/SELLABLE">Source</a> ·
      <a href="/docs">API reference</a> ·
      <a href="/executions">Execution ledger (JSON)</a> ·
      <a href="/audit/verify">Audit chain verification</a>
    </p>
    <p style="margin:0" id="foot-mode"></p>
  </footer>
</div>

<script>
const STAGES = [
  ["01","Mission","signed budget + scope"],
  ["02","Discovery","live market evidence"],
  ["03","Recommend","a SKU, never a price"],
  ["04","Policy","R1–R12 deterministic"],
  ["05","Authorize","single-use binding"],
  ["06","Execute","durable state machine"],
  ["07","Settle","authoritative read"],
];
const $ = (id) => document.getElementById(id);
const rail = $("rail");
STAGES.forEach(([n,t,s],i) => {
  const d = document.createElement("div");
  d.className = "stage"; d.id = "stage-"+i;
  d.innerHTML = `<div class="n">${n}</div><div class="t">${t}</div><div class="s">${s}</div>`;
  rail.appendChild(d);
});
function stage(i, cls, sub) {
  const el = $("stage-"+i);
  el.className = "stage " + cls;
  if (sub !== undefined) el.querySelector(".s").textContent = sub;
}
function resetStages() {
  STAGES.forEach(([n,t,s],i) => stage(i, "", s));
}
const esc = (s) => String(s == null ? "" : s).replace(/[&<>"]/g,
  c => ({"&":"&amp;","<":"&lt;",">":"&gt;",'"':"&quot;"}[c]));
const rupees = (p) => "₹" + (p/100).toLocaleString("en-IN",{minimumFractionDigits:2, maximumFractionDigits:2});

let MODE = "unknown";
let STATE = {};

async function loadMode() {
  try {
    const d = await (await fetch("/diagnostics")).json();
    MODE = d.payments.provider;
    const el = $("mode");
    el.textContent = MODE === "simulated" ? "SIMULATED PROVIDER" : "RAZORPAY TEST MODE";
    el.className = "mode " + (MODE === "simulated" ? "sim" : "live");
    el.title = d.payments.provider_description;
    $("foot-mode").textContent = d.payments.provider_description;
  } catch (e) { $("mode").textContent = "provider unknown"; }
}
loadMode();

document.querySelectorAll(".examples button").forEach(b => {
  b.onclick = () => { $("q").value = b.dataset.q; $("b").value = b.dataset.b; run(); };
});
$("run").onclick = () => run();
$("q").addEventListener("keydown", e => { if (e.key === "Enter") run(); });

async function run() {
  const q = $("q").value.trim();
  const budget = Math.round(parseFloat($("b").value || "0") * 100);
  if (!q || budget <= 0) return;

  STATE = {};
  $("run").disabled = true;
  resetStages();
  ["s-discovery","s-recommend","s-policy","s-execute","s-proof"].forEach(id => $(id).classList.add("hidden"));
  $("fault-box").classList.add("hidden");

  stage(0, "done", "budget " + rupees(budget));
  stage(1, "on", "searching…");
  $("s-discovery").classList.remove("hidden");
  $("listings").innerHTML = '<div class="card" style="color:var(--ink-3)"><span class="spin"></span> querying live providers…</div>';

  let d;
  try {
    d = await (await fetch("/discovery/search", {
      method:"POST", headers:{"Content-Type":"application/json"},
      body: JSON.stringify({query:q, budget_paise:budget})
    })).json();
  } catch (e) {
    $("listings").innerHTML = `<div class="err">Discovery request failed: ${esc(e.message)}</div>`;
    stage(1, "err", "request failed"); $("run").disabled = false; return;
  }

  STATE.discovery = d;
  renderDiscovery(d, budget);
  $("run").disabled = false;
}

function renderDiscovery(d, budget) {
  const status = d.search_engine_status;
  const n = d.listings.length;

  if (status === "LIVE_SEARCH_SUCCESS") {
    stage(1, "done", n + " live listing" + (n===1?"":"s"));
    $("discovery-note").textContent =
      `${n} external listing${n===1?"":"s"} retrieved from ${d.providers_hit.join(", ")}. ` +
      `Everything below is untrusted: it can influence which SKU is proposed and nothing else.`;
  } else if (status === "ZERO_RESULTS") {
    stage(1, "hold", "no results");
    $("discovery-note").textContent =
      "The providers responded but published nothing matching this query. " +
      "Zero results are reported as zero results.";
  } else {
    stage(1, "hold", "providers unavailable");
    $("discovery-note").textContent =
      "Every live provider failed. This is reported as SEARCH_UNAVAILABLE rather than " +
      "quietly succeeding — the merchant catalog below is not a search result.";
  }

  const box = $("listings");
  box.innerHTML = "";
  if (d.provider_errors && d.provider_errors.length) {
    const e = document.createElement("div");
    e.className = "err";
    e.innerHTML = "<b>Provider errors</b><br>" +
      d.provider_errors.map(x => esc(x)).join("<br>");
    box.appendChild(e);
  }
  d.listings.forEach(l => {
    const c = document.createElement("div");
    c.className = "card listing";
    const priceTxt = l.price_inr == null ? "—" :
      "₹" + l.price_inr.toLocaleString("en-IN",{minimumFractionDigits:2,maximumFractionDigits:2});
    const src = l.source_currency && l.source_currency !== "INR"
      ? `${l.source_currency} ${l.source_price} × ${l.fx_rate_used}` : "as published";
    c.innerHTML =
      `<div>
         <div class="name">${esc(l.product_name)}</div>
         <div class="meta">
           <span class="ev ev-${esc(l.evidence_class)}">${esc(l.evidence_class)}</span>
           ${esc(l.seller)} · ${esc(l.seller_domain)}
           ${l.rating != null ? " · " + l.rating + "★" + (l.rating_verified ? "" : " (unverified)") : ""}
         </div>
         <div class="meta" style="margin-top:6px;opacity:.8">${esc((l.raw_evidence||"").slice(0,150))}</div>
       </div>
       <div class="price">${priceTxt}<small>${esc(src)}</small></div>`;
    box.appendChild(c);
  });
  if (!d.listings.length && !(d.provider_errors||[]).length) {
    box.innerHTML = '<div class="card" style="color:var(--ink-3)">No external listings.</div>';
  }

  const c = d.comparison || {};
  $("evidence-note").textContent =
    `Comparison basis: ${c.comparison_basis || "n/a"}. ` +
    `${c.market_evidence_count || 0} listing(s) counted as market evidence; ` +
    `${c.mock_source_count || 0} excluded as synthetic; ` +
    `${c.fx_converted_count || 0} FX-estimated and therefore never treated as a verified price.`;

  const m = d.merchant_offer;
  if (!m) {
    stage(2, "hold", "nothing in stock matches");
    $("s-recommend").classList.remove("hidden");
    $("merchant").innerHTML =
      `<div style="color:var(--ink-2)">Nothing in the merchant catalog matches this
       intent inside the budget, so the agent has nothing to propose. SELLABLE only
       sells what it stocks — external listings are evidence, not inventory.</div>`;
    return;
  }

  stage(2, "done", m.sku);
  $("s-recommend").classList.remove("hidden");
  const rec = d.recommendation || {};
  $("merchant").innerHTML =
    `<div class="listing">
       <div>
         <div class="name">${esc(m.name)}</div>
         <div class="meta">
           <span class="ev ev-MERCHANT">MERCHANT CATALOG</span>
           SKU ${esc(m.sku)} · ${esc(m.category)}${m.rating ? " · " + m.rating + "★" : ""}
           ${m.in_stock ? "" : " · out of stock"}
         </div>
       </div>
       <div class="price">${rupees(m.price_paise)}<small>server-side price</small></div>
     </div>
     <p class="note">${esc(rec.recommendation_reason || "")}</p>
     <button class="buy" id="buy">Authorize and execute →</button>`;
  $("buy").onclick = () => execute(m.sku, budget, "");

  const probe = d.policy_probe;
  if (probe) {
    const box = document.createElement("div");
    box.style.marginTop = "18px";
    box.style.paddingTop = "16px";
    box.style.borderTop = "1px solid var(--line-soft)";
    box.innerHTML =
      `<div style="font-size:12.5px;color:var(--ink-3);margin-bottom:10px">
         <b style="color:var(--ink-2)">Now break it.</b> Suppose a product page had
         talked the agent into proposing something else — the expensive one, with a
         persuasive justification. This proposes a real catalog SKU that exceeds the
         signed budget.
       </div>
       <button id="probe" style="background:transparent;border:1px solid #4a1f22;
         color:#e5878d;border-radius:8px;padding:9px 15px;font-size:13.5px;
         cursor:pointer;font-family:inherit">
         Propose ${esc(probe.name)} — ${"₹" + probe.price_inr.toLocaleString("en-IN")}
         (over budget)
       </button>`;
    $("merchant").appendChild(box);
    $("probe").onclick = () => {
      $("probe").disabled = true;
      execute(probe.sku, budget, "");
    };
  }
}

const EXEC_STATES = ["APPROVED","EXECUTION_PENDING","REMOTE_ATTEMPTED","EXECUTED"];
function renderStates(current) {
  const order = ["APPROVED","EXECUTION_PENDING","REMOTE_ATTEMPTED"];
  const box = $("states"); box.innerHTML = "";
  const idx = order.indexOf(current);
  order.forEach((s,i) => {
    const d = document.createElement("div");
    let cls = "st";
    if (current === s) cls += " at";
    else if (idx === -1 || i < idx) cls += " past";
    d.className = cls; d.textContent = s; box.appendChild(d);
  });
  [["EXECUTED","past"],["RECONCILIATION_REQUIRED","hold"],["FAILED","bad"]].forEach(([s,c]) => {
    const d = document.createElement("div");
    d.className = "st" + (current === s ? " " + (s==="EXECUTED"?"at":c) : "");
    d.textContent = s; box.appendChild(d);
  });
}

async function execute(sku, budget, fault) {
  stage(3, "on", "evaluating"); stage(4, "", ""); stage(5, "", ""); stage(6, "", "");
  ["s-policy","s-execute"].forEach(id => $(id).classList.remove("hidden"));
  $("rules").innerHTML = '<div style="color:var(--ink-3)"><span class="spin"></span> running the gateway…</div>';
  $("policy-outcome").innerHTML = ""; $("exec-outcome").innerHTML = "";
  renderStates("APPROVED");
  const buy = $("buy"); if (buy) buy.disabled = true;
  document.querySelectorAll(".faults button").forEach(b => b.disabled = true);

  let res, body;
  try {
    res = await fetch("/discovery/checkout", {
      method:"POST", headers:{"Content-Type":"application/json"},
      body: JSON.stringify({sku, budget_paise:budget, fault})
    });
    body = await res.json();
  } catch (e) {
    $("policy-outcome").innerHTML = `<div class="err">Request failed: ${esc(e.message)}</div>`;
    stage(3, "err", "request failed"); if (buy) buy.disabled = false; return;
  }

  const err = (body.detail && body.detail.error) || null;

  if (err && err.error_code === "POLICY_GATEWAY_REJECT") {
    renderRules(err.rule_matrix, err.rule_id);
    stage(3, "err", err.rule_id);
    $("policy-outcome").innerHTML =
      `<div class="err"><b>REJECTED by ${esc(err.rule_id)}</b><br>${esc(err.message)}
       <br><br>No approval binding was created and the money boundary was never
       reached. The agent may revise and re-propose.</div>`;
    $("s-execute").classList.add("hidden");
    if (buy) buy.disabled = false;
    showProof({ gateway_rule: err.rule_id, gateway_decision: "REJECT" });
    return;
  }

  if (err && err.error_code === "RECONCILIATION_REQUIRED") {
    stage(3,"done","APPROVE"); stage(4,"done","bound"); stage(5,"hold","outcome unknown");
    $("rules").innerHTML = ""; $("policy-outcome").innerHTML =
      '<div class="ok-banner">All twelve rules passed. Approval binding issued and consumed.</div>';
    renderStates("RECONCILIATION_REQUIRED");
    STATE.execution_id = err.execution_id;
    $("exec-outcome").innerHTML =
      `<div class="hold-banner">
         <b>The provider's outcome is unknown.</b><br>${esc(err.detail || err.message)}
         <br><br>No success and no failure has been assumed. The authorization is spent,
         so retrying could double-charge — the only safe move is to ask the provider
         what actually happened.
         <br><br><button class="rec" id="do-rec">Reconcile against provider state</button>
       </div>`;
    $("do-rec").onclick = () => reconcile(err.execution_id);
    $("fault-box").classList.remove("hidden");
    document.querySelectorAll(".faults button").forEach(b => b.disabled = false);
    showProof({ execution_id: err.execution_id, execution_state: err.execution_state });
    return;
  }

  if (err && err.error_code === "REMOTE_REJECTED") {
    stage(3,"done","APPROVE"); stage(4,"done","bound"); stage(5,"err","refused");
    $("rules").innerHTML = "";
    $("policy-outcome").innerHTML =
      '<div class="ok-banner">All twelve rules passed. Approval binding issued and consumed.</div>';
    renderStates("FAILED");
    $("exec-outcome").innerHTML =
      `<div class="err"><b>The provider refused, definitively.</b><br>${esc(err.message)}
       <br><br>A 4xx means the provider is telling us it did <i>not</i> act, so this is
       terminal rather than ambiguous. No money moved. The authorization is spent and a
       fresh approval is required.</div>`;
    $("fault-box").classList.remove("hidden");
    document.querySelectorAll(".faults button").forEach(b => b.disabled = false);
    showProof({ execution_id: err.execution_id, execution_state: "FAILED" });
    return;
  }

  if (!res.ok) {
    $("policy-outcome").innerHTML =
      `<div class="err">${esc((err && err.message) || JSON.stringify(body).slice(0,300))}</div>`;
    stage(3, "err", "error"); if (buy) buy.disabled = false; return;
  }

  // success
  STATE.order = body;
  $("rules").innerHTML = "";
  $("policy-outcome").innerHTML =
    `<div class="ok-banner">All twelve rules passed — decision
     <b>${esc(body.gateway_decision)}</b> under policy ${esc(body.policy_version)}.</div>`;
  stage(3,"done","APPROVE"); stage(4,"done","bound"); stage(5,"done",body.execution_state);
  renderStates(body.execution_state);
  $("exec-outcome").innerHTML =
    `<div class="ok-banner"><b>Order ${esc(body.order_id)}</b> for
     ${rupees(body.amount_paise)} · provider <code>${esc(body.provider)}</code>
     ${body.provider === "simulated"
        ? "<br>Simulated provider: no network call was made and the order id is prefixed <code>order_sim_</code>."
        : ""}</div>`;
  $("fault-box").classList.remove("hidden");
  document.querySelectorAll(".faults button").forEach(b => b.disabled = false);
  await settle(body.order_id);
  showProof(body);
}

function renderRules(matrix, failed) {
  const box = $("rules"); box.innerHTML = "";
  (matrix || []).forEach(r => {
    const d = document.createElement("div");
    const failedRule = r.rule_id === failed || r.status === "FAIL";
    d.className = "rule " + (failedRule ? "fail" : (r.status === "PASS" ? "pass" : ""));
    d.innerHTML = `<span class="dot"></span>${esc(r.rule_id)}`;
    d.title = r.reason || r.status;
    box.appendChild(d);
  });
}

async function reconcile(execId) {
  $("do-rec").disabled = true;
  $("do-rec").innerHTML = '<span class="spin"></span> reading provider state…';
  let r;
  try {
    r = await (await fetch(`/discovery/reconcile/${execId}`, {method:"POST"})).json();
  } catch (e) {
    $("exec-outcome").innerHTML = `<div class="err">Reconcile failed: ${esc(e.message)}</div>`;
    return;
  }
  renderStates(r.state);
  if (r.state === "EXECUTED") {
    stage(5,"done","reconciled");
    $("exec-outcome").innerHTML =
      `<div class="ok-banner"><b>Resolved: ${esc(r.resolution)}</b><br>${esc(r.explanation)}
       <br>Order <code>${esc(r.remote_order_id)}</code> now recorded locally.</div>`;
    if (r.remote_order_id) await settle(r.remote_order_id);
  } else {
    stage(5,"done","reconciled → FAILED"); stage(6,"done","no money moved");
    $("exec-outcome").innerHTML =
      `<div class="err"><b>Resolved: ${esc(r.resolution)}</b><br>${esc(r.explanation)}</div>`;
  }
  showProof(Object.assign({}, STATE.order || {}, r.execution || {}));
}

async function settle(orderId) {
  stage(6, "on", "reading state…");
  try {
    const s = await (await fetch("/discovery/payment-status/" + orderId)).json();
    STATE.settlement = s;
    stage(6, s.settlement === "NO_SETTLEMENT_EVENT_RECEIVED" ? "hold" : "done",
          s.settlement === "NO_SETTLEMENT_EVENT_RECEIVED" ? "awaiting webhook" : s.settlement);
    const box = document.createElement("div");
    box.style.marginTop = "12px";
    box.className = s.settlement === "CAPTURED_CONFIRMED_BY_SIGNED_WEBHOOK" ? "ok-banner" : "hold-banner";
    box.innerHTML = `<b>Settlement: ${esc(s.settlement)}</b><br>${esc(s.note)}`;
    $("exec-outcome").appendChild(box);
  } catch (e) { stage(6, "hold", "unavailable"); }
}

function showProof(o) {
  const src = STATE.order || {};
  const rows = [
    ["mission id", o.mission_id || src.mission_id],
    ["proposal hash", o.proposal_hash || src.proposal_hash],
    ["approval sequence", o.approve_seq != null ? o.approve_seq : src.approve_seq],
    ["gateway decision", o.gateway_decision || src.gateway_decision || o.gateway_rule],
    ["policy version", o.policy_version || src.policy_version],
    ["execution id", o.execution_id || src.execution_id],
    ["execution state", o.state || o.execution_state || src.execution_state],
    ["idempotency key", o.idempotency_key],
    ["provider", o.provider || src.provider],
    ["remote order id", o.remote_order_id || o.order_id || src.order_id],
    ["amount (paise)", o.amount_paise || src.amount_paise],
    ["authorization issued by", src.authorization_issued_by],
    ["audit head hash", src.audit_head_hash],
    ["settlement", (STATE.settlement||{}).settlement],
  ].filter(([,v]) => v !== undefined && v !== null && v !== "");
  $("proof").innerHTML = rows.map(([k,v]) =>
    `<div><span class="k">${esc(k)}</span><span class="v">${esc(v)}</span></div>`).join("");
  $("s-proof").classList.remove("hidden");
}

document.querySelectorAll(".faults button").forEach(b => {
  b.onclick = () => {
    const m = STATE.discovery && STATE.discovery.merchant_offer;
    if (!m) return;
    const budget = Math.round(parseFloat($("b").value || "0") * 100);
    execute(m.sku, budget, b.dataset.fault);
  };
});
</script>
</body>
</html>
"""


@router.get("/", response_class=HTMLResponse)
async def product_page() -> HTMLResponse:
    return HTMLResponse(PAGE)
