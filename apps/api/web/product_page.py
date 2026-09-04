"""GET / — the storefront. The whole buyer journey on one page.

A shopper types a sentence and ends up with a purchase, and every step in
between is visible: what the AI found, what it recommends and why, what
the server says the price is, which policy rules ran, exactly what they
are authorizing, and what happened when the payment provider was called.

THE ONE DESIGN RULE
-------------------
Advisory content (violet, dashed) and authoritative content (teal rule,
monospaced figures) never share a box. The AI's recommendation and the
payable amount are rendered as two different kinds of thing, because
they are two different kinds of thing. A shopper who never reads a word
of the copy still learns the architecture from the layout.

NOTHING HERE IS DECORATIVE
--------------------------
Every price, state, rule id and hash on this page came from a response.
The pipeline rail advances only when a step actually completed. When a
request fails, the page shows the real error — there is no fallback
content, because fallback content is how a demo ends up displaying
numbers that nothing produced.
"""
from __future__ import annotations

from fastapi import APIRouter
from fastapi.responses import HTMLResponse

from .shell import FOOTER, PROVIDER_BADGE_JS, head, nav

router = APIRouter()

_CSS = """
/* ── hero ──────────────────────────────────────────────────────────── */
.hero{padding:52px 0 30px;max-width:1080px;margin:0 auto}
.eyebrow{display:inline-flex;align-items:center;gap:8px;font-family:var(--mono);
  font-size:10.5px;font-weight:700;letter-spacing:.18em;text-transform:uppercase;
  color:var(--violet);border:1px solid var(--violet-line);background:var(--violet-soft);
  border-radius:999px;padding:5px 13px;margin-bottom:20px}
h1{font-size:clamp(30px,5vw,58px);font-weight:700;letter-spacing:-.04em;
  line-height:1.04;max-width:15ch}
h1 .no{color:var(--violet);position:relative;white-space:nowrap}
h1 .no::after{content:"";position:absolute;left:-2px;right:-2px;top:56%;height:3px;
  background:var(--violet);border-radius:2px;transform:scaleX(0);transform-origin:left;
  animation:strike .5s .35s cubic-bezier(.2,.8,.3,1) forwards}
@keyframes strike{to{transform:scaleX(1)}}
.sub{color:var(--text-mid);margin-top:20px;max-width:56ch;font-size:16px;line-height:1.65}

/* ── search ────────────────────────────────────────────────────────── */
.search{margin-top:30px;max-width:760px;background:var(--bg-panel);
  border:1px solid var(--border);border-radius:var(--r-panel);padding:18px;
  box-shadow:var(--shadow)}
.srow{display:flex;gap:10px}
.sinput-wrap{flex:1;position:relative;min-width:0}
.sinput{width:100%;height:48px;background:var(--bg-inset);border:1px solid var(--border);
  border-radius:var(--r-ctl);padding:0 14px 0 42px;color:var(--text-hi);font-size:15px}
.sinput:focus{border-color:var(--violet);outline:none}
.sinput::placeholder{color:var(--text-dim)}
.sicon{position:absolute;left:14px;top:50%;transform:translateY(-50%);
  color:var(--text-dim);pointer-events:none}
.sbtn{height:48px;padding:0 26px;background:var(--violet);color:#fff;border-radius:var(--r-ctl);
  font-weight:600;font-size:14.5px;flex-shrink:0;transition:background .15s ease-out}
.sbtn:hover:not(:disabled){background:#7C5AFF}
.sbtn:disabled{opacity:.55;cursor:default}
.brow2{display:flex;align-items:center;gap:9px;margin-top:14px;padding-top:14px;
  border-top:1px solid var(--border);flex-wrap:wrap}
.blabel{font-family:var(--mono);font-size:10px;font-weight:700;letter-spacing:.13em;
  text-transform:uppercase;color:var(--text-dim)}
.binput{width:110px;background:var(--bg-inset);border:1px solid var(--border);
  border-radius:var(--r-ctl);padding:7px 10px;color:var(--text-hi);
  font-family:var(--mono);font-size:13px}
.binput:focus{border-color:var(--violet);outline:none}
.bhint{font-size:12px;color:var(--text-dim)}
.chips{display:flex;gap:7px;margin-top:14px;flex-wrap:wrap}
.qchip{font-size:12.5px;color:var(--text-mid);background:var(--bg-inset);
  border:1px solid var(--border);border-radius:999px;padding:6px 13px;
  transition:border-color .15s ease-out,color .15s ease-out}
.qchip:hover{border-color:var(--violet);color:var(--text-hi)}

/* ── pipeline rail ─────────────────────────────────────────────────── */
.rail-wrap{max-width:1080px;margin:28px auto 0;opacity:0;height:0;overflow:hidden;
  transition:opacity .25s ease-out}
.rail-wrap.on{opacity:1;height:auto;overflow:visible}
.rail{display:flex;align-items:center;background:var(--bg-panel);
  border:1px solid var(--border);border-radius:var(--r-panel);padding:14px 8px;
  position:relative;overflow:hidden}
.rail-bar{position:absolute;left:0;bottom:0;height:2px;background:var(--violet);
  width:0;transition:width .4s ease-out}
.step{flex:1;display:flex;flex-direction:column;align-items:center;gap:7px;
  position:relative;min-width:0}
.step::after{content:"";position:absolute;top:16px;left:calc(50% + 20px);
  right:calc(-50% + 20px);height:1px;background:var(--border)}
.step:last-child::after{display:none}
.sdot{width:32px;height:32px;border-radius:50%;background:var(--bg-inset);
  border:1px solid var(--border);display:flex;align-items:center;justify-content:center;
  font-size:13px;color:var(--text-dim);z-index:1;transition:.2s ease-out}
.slabel{font-family:var(--mono);font-size:9.5px;font-weight:700;letter-spacing:.11em;
  text-transform:uppercase;color:var(--text-dim);text-align:center}
.step.active .sdot{border-color:var(--violet);color:var(--violet);
  box-shadow:0 0 0 4px var(--violet-soft)}
.step.active .slabel{color:var(--violet)}
.step.done .sdot{border-color:var(--teal);color:var(--teal);background:var(--teal-soft)}
.step.done .slabel{color:var(--teal)}
.step.wait .sdot{border-color:var(--amber);color:var(--amber);background:var(--amber-soft)}
.step.wait .slabel{color:var(--amber)}
.step.stop .sdot{border-color:var(--red);color:var(--red);background:var(--red-soft)}
.step.stop .slabel{color:var(--red)}
.status{margin-top:10px;font-family:var(--mono);font-size:12px;color:var(--text-mid);
  min-height:1.4em}

/* ── results ───────────────────────────────────────────────────────── */
main.results{max-width:1080px;margin:0 auto;padding:26px 0 40px}
.rec{display:grid;grid-template-columns:1fr 1fr;gap:0;border:1px solid var(--border);
  border-radius:var(--r-panel);overflow:hidden;background:var(--bg-panel);margin-bottom:26px}
.rec-side{padding:22px 24px}
.rec-side.ai{background:var(--violet-soft);border-right:1px dashed var(--violet-line)}
.rec-side.srv{border-left:3px solid var(--teal)}
.rec-k{font-family:var(--mono);font-size:10px;font-weight:700;letter-spacing:.15em;
  text-transform:uppercase;margin-bottom:14px;display:flex;align-items:center;gap:8px}
.rec-side.ai .rec-k{color:var(--violet)}
.rec-side.srv .rec-k{color:var(--teal)}
.rec-name{font-size:19px;font-weight:600;letter-spacing:-.02em;line-height:1.3}
.rec-why{margin-top:14px;display:flex;flex-direction:column;gap:9px}
.rec-why-i{display:flex;gap:9px;font-size:13.5px;color:var(--text-mid);line-height:1.55}
.rec-why-i::before{content:"";width:5px;height:5px;border-radius:50%;background:var(--violet);
  margin-top:8px;flex-shrink:0}
.rec-price{font-family:var(--mono);font-size:38px;font-weight:700;letter-spacing:-.035em;
  line-height:1.05}
.rec-price-k{font-size:12px;color:var(--text-dim);margin-top:6px}
.rec-facts{margin-top:16px;display:flex;flex-direction:column;gap:7px}
.fact{display:flex;justify-content:space-between;gap:14px;font-size:12.5px;
  padding-bottom:7px;border-bottom:1px dotted var(--border)}
.fact:last-child{border-bottom:none}
.fact-k{color:var(--text-dim)}
.fact-v{font-family:var(--mono);font-size:12px;color:var(--text-hi);text-align:right;
  word-break:break-all}
.buy{margin-top:18px;width:100%;height:46px;background:var(--teal);color:#04211E;
  border-radius:var(--r-ctl);font-weight:700;font-size:14.5px;
  display:flex;align-items:center;justify-content:center;gap:8px;
  transition:background .15s ease-out}
.buy:hover:not(:disabled){background:#4FE3D0}
.buy:disabled{opacity:.5;cursor:default}

/* ── section headers, evidence grid ────────────────────────────────── */
.sec-h{display:flex;align-items:baseline;justify-content:space-between;gap:14px;
  margin:26px 0 12px;flex-wrap:wrap}
.sec-t{font-family:var(--mono);font-size:10.5px;font-weight:700;letter-spacing:.16em;
  text-transform:uppercase;color:var(--text-dim)}
.sec-n{font-size:12px;color:var(--text-dim)}
.pgrid{display:grid;grid-template-columns:repeat(auto-fill,minmax(255px,1fr));gap:12px}
.pcard{background:var(--bg-panel);border:1px dashed var(--violet-line);
  border-radius:var(--r-panel);padding:14px 15px}
.pcard-top{display:flex;justify-content:space-between;gap:10px;align-items:start;margin-bottom:9px}
.pname{font-size:13.5px;font-weight:500;line-height:1.4}
.pprice{font-family:var(--mono);font-size:17px;font-weight:700}
.pprice small{font-size:10.5px;color:var(--text-dim);font-weight:400;margin-left:5px}
.pseller{font-size:11.5px;color:var(--text-dim);margin-top:7px;
  display:flex;gap:7px;align-items:center;flex-wrap:wrap}
.legend{display:flex;gap:16px;flex-wrap:wrap;margin-top:14px;padding-top:14px;
  border-top:1px solid var(--border);font-size:11.5px;color:var(--text-dim)}
.legend-i{display:flex;gap:7px;align-items:center}

/* ── probe ─────────────────────────────────────────────────────────── */
.probe{border:1px solid rgba(255,178,36,.28);background:var(--amber-soft);
  border-radius:var(--r-panel);padding:16px 18px;margin-bottom:26px}
.probe-h{display:flex;align-items:center;gap:10px;flex-wrap:wrap;margin-bottom:8px}
.probe-n{font-size:14px;font-weight:600}
.probe-d{font-size:13px;color:#D9A75B;line-height:1.6;margin-bottom:12px}

/* ── execution ─────────────────────────────────────────────────────── */
.exec{background:var(--bg-panel);border:1px solid var(--border);
  border-left:3px solid var(--teal);border-radius:var(--r-panel);padding:20px 22px;
  margin-bottom:26px;display:none}
.exec.on{display:block}
.exec-t{font-family:var(--mono);font-size:10.5px;font-weight:700;letter-spacing:.15em;
  text-transform:uppercase;color:var(--teal);margin-bottom:14px}
.smr{display:grid;grid-template-columns:12px minmax(150px,180px) 1fr;gap:11px;
  padding:7px 0;align-items:start;opacity:.32;font-size:12.5px}
.smr .d{width:9px;height:9px;border-radius:50%;background:var(--border-hi);margin-top:4px}
.smr .n{font-family:var(--mono);font-size:11.5px;font-weight:700}
.smr .x{color:var(--text-mid);font-size:12px}
.smr.done{opacity:1} .smr.done .d{background:var(--teal)}
.smr.cur{opacity:1} .smr.cur .d{background:var(--violet);box-shadow:0 0 0 4px var(--violet-soft)}
.smr.warn{opacity:1} .smr.warn .d{background:var(--amber);box-shadow:0 0 0 4px var(--amber-soft)}
.smr.bad{opacity:1} .smr.bad .d{background:var(--red)}
.exec-ids{font-family:var(--mono);font-size:11px;color:var(--text-dim);margin-top:14px;
  white-space:pre-wrap;word-break:break-all;line-height:1.7}
.fault-row{display:flex;align-items:center;gap:7px;flex-wrap:wrap;margin-top:16px;
  padding-top:14px;border-top:1px solid var(--border)}
.fault-k{font-family:var(--mono);font-size:10px;font-weight:700;letter-spacing:.12em;
  text-transform:uppercase;color:var(--text-dim);margin-right:4px}
.recon{margin-top:16px;display:none}
.recon.on{display:block}

/* ── modal ─────────────────────────────────────────────────────────── */
.ov{position:fixed;inset:0;background:rgba(4,4,8,.82);backdrop-filter:blur(4px);
  display:none;align-items:center;justify-content:center;padding:20px;z-index:200}
.ov.on{display:flex}
.modal{background:var(--bg-panel);border:1px solid var(--border-hi);
  border-radius:14px;max-width:520px;width:100%;max-height:90vh;overflow-y:auto;
  box-shadow:0 24px 64px rgba(0,0,0,.7)}
.mh{display:flex;align-items:center;justify-content:space-between;gap:14px;
  padding:18px 22px;border-bottom:1px solid var(--border);position:sticky;top:0;
  background:var(--bg-panel);z-index:1}
.mt{font-size:15px;font-weight:600}
.mx{font-size:22px;color:var(--text-dim);line-height:1;padding:0 4px}
.mx:hover{color:var(--text-hi)}
.mb{padding:20px 22px 22px}
.mgroup{margin-bottom:18px}
.mk{font-family:var(--mono);font-size:9.5px;font-weight:700;letter-spacing:.14em;
  text-transform:uppercase;color:var(--text-dim);margin-bottom:8px}
.mprice{font-family:var(--mono);font-size:30px;font-weight:700;letter-spacing:-.03em}
.gcheck{display:flex;gap:9px;align-items:start;font-size:12.5px;color:var(--text-mid);
  padding:5px 0}
.gi{width:15px;height:15px;border-radius:50%;display:flex;align-items:center;
  justify-content:center;font-size:9px;flex-shrink:0;margin-top:2px}
.gi.p{background:var(--teal-soft);color:var(--teal);border:1px solid rgba(45,212,191,.35)}
.gi.f{background:var(--red-soft);color:var(--red);border:1px solid rgba(255,77,94,.35)}
.reason{background:var(--violet-soft);border:1px dashed var(--violet-line);
  border-radius:var(--r-ctl);padding:12px 14px;font-size:13px;color:var(--text-mid);
  line-height:1.6}
.disc{background:var(--bg-inset);border:1px solid var(--border);border-radius:var(--r-ctl);
  padding:12px 14px;font-size:12px;color:var(--text-dim);line-height:1.6;margin-bottom:16px}
.approve{width:100%;height:48px;background:var(--teal);color:#04211E;
  border-radius:var(--r-ctl);font-weight:700;font-size:15px}
.approve:hover:not(:disabled){background:#4FE3D0}
.approve:disabled{opacity:.5;cursor:default}

/* ── alerts / states ───────────────────────────────────────────────── */
.alert{border-radius:var(--r-panel);padding:14px 16px;font-size:13.5px;
  margin-bottom:18px;line-height:1.6}
.alert-bad{background:var(--red-soft);border:1px solid rgba(255,77,94,.3);color:#FFA5AE}
.alert-warn{background:var(--amber-soft);border:1px solid rgba(255,178,36,.3);color:#F0C070}
.alert-ok{background:var(--teal-soft);border:1px solid rgba(45,212,191,.3);color:#8FE8DC}
.alert b{display:block;margin-bottom:4px;color:var(--text-hi)}
.alert .m{display:block;margin-top:6px;font-size:11.5px;color:var(--text-dim)}
.empty{text-align:center;padding:44px 20px;color:var(--text-dim);font-size:13.5px;
  border:1px dashed var(--border-hi);border-radius:var(--r-panel)}

/* ── judge strip ───────────────────────────────────────────────────── */
.jstrip{max-width:1080px;margin:0 auto;background:var(--bg-panel);
  border:1px solid var(--border);border-radius:var(--r-panel);padding:20px 24px;
  display:flex;align-items:center;justify-content:space-between;gap:20px;flex-wrap:wrap}
.jstrip-t{font-size:14px;font-weight:600;margin-bottom:4px}
.jstrip-s{font-size:13px;color:var(--text-mid);max-width:62ch}

@media (max-width:820px){
  .rec{grid-template-columns:1fr}
  .rec-side.ai{border-right:none;border-bottom:1px dashed var(--violet-line)}
  .srow{flex-direction:column}
  .step::after{display:none}
  .slabel{font-size:8.5px}
}
"""

PAGE = f"""{head("SELLABLE — shop with AI that cannot touch your money", _CSS)}
{nav("shop")}

<section class="wrap hero">
  <div class="eyebrow">Agentic commerce &middot; Razorpay Track 01</div>
  <h1>Shop with an AI that <span class="no">cannot</span> touch your money.</h1>
  <p class="sub">It searches real retailers, compares what it finds, and recommends
    one thing. It never decides what you pay &mdash; the price comes from the
    merchant's server, a deterministic policy gateway checks it against your budget,
    and your approval is a single-use key bound to that exact cart.</p>

  <div class="search">
    <div class="srow">
      <div class="sinput-wrap">
        <svg class="sicon" width="17" height="17" fill="none" viewBox="0 0 24 24"
             stroke="currentColor" stroke-width="2" aria-hidden="true">
          <circle cx="11" cy="11" r="8"/><path d="m21 21-4.35-4.35"/></svg>
        <input id="q" class="sinput" type="search" autocomplete="off" spellcheck="false"
          placeholder="cricket bat under 3000, wireless headphones, yoga mat…"
          aria-label="What should the agent buy?">
      </div>
      <button id="go" class="sbtn">Search</button>
    </div>
    <div class="brow2">
      <span class="blabel">Your ceiling</span>
      <span class="m">&#8377;</span>
      <input id="budget" class="binput" type="number" value="3000" min="100" max="100000" step="100">
      <span class="bhint">A signed mandate. Nothing above this can be authorized, whatever the AI proposes.</span>
    </div>
    <div class="chips">
      <button class="qchip" data-q="cricket bat under 3000" data-b="3000">Cricket bat</button>
      <button class="qchip" data-q="wireless bluetooth headphones under 2000" data-b="2000">Headphones</button>
      <button class="qchip" data-q="yoga mat under 1000" data-b="1000">Yoga mat</button>
      <button class="qchip" data-q="python algorithms book under 1000" data-b="1000">Algorithms book</button>
    </div>
  </div>

  <div class="rail-wrap" id="rail-wrap">
    <div class="rail" role="list" aria-label="Purchase pipeline">
      <div class="step" id="s-discover" role="listitem">
        <span class="sdot">1</span><span class="slabel">Discover</span></div>
      <div class="step" id="s-gateway" role="listitem">
        <span class="sdot">2</span><span class="slabel">Policy</span></div>
      <div class="step" id="s-auth" role="listitem">
        <span class="sdot">3</span><span class="slabel">Authorize</span></div>
      <div class="step" id="s-exec" role="listitem">
        <span class="sdot">4</span><span class="slabel">Execute</span></div>
      <div class="step" id="s-done" role="listitem">
        <span class="sdot">5</span><span class="slabel">Settled</span></div>
      <div class="rail-bar" id="rail-bar"></div>
    </div>
    <div class="status m" id="status"></div>
  </div>
</section>

<main class="results" id="results" style="display:none">
  <div id="alerts"></div>

  <div class="rec" id="rec" style="display:none">
    <div class="rec-side ai">
      <div class="rec-k"><span class="chip chip-violet">advisory</span> what the AI chose</div>
      <div class="rec-name" id="rec-name">&mdash;</div>
      <div class="rec-why" id="rec-why"></div>
    </div>
    <div class="rec-side srv">
      <div class="rec-k"><span class="chip chip-ok">server-authoritative</span> what you would pay</div>
      <div class="rec-price" id="rec-price">&mdash;</div>
      <div class="rec-price-k">re-derived from the merchant catalog, not from any listing above</div>
      <div class="rec-facts" id="rec-facts"></div>
      <button class="buy" id="buy">Review &amp; authorize
        <svg width="15" height="15" fill="none" viewBox="0 0 24 24" stroke="currentColor"
             stroke-width="2.5" aria-hidden="true"><path d="M5 12h14M12 5l7 7-7 7"/></svg>
      </button>
    </div>
  </div>

  <div class="probe" id="probe" style="display:none">
    <div class="probe-h">
      <span class="chip chip-warn">try to break it</span>
      <span class="probe-n" id="probe-n">&mdash;</span>
    </div>
    <div class="probe-d" id="probe-d">&mdash;</div>
    <button class="btn" id="probe-go">Ask the agent to buy this instead &rarr;</button>
  </div>

  <div class="exec" id="exec">
    <div class="exec-t">Payment execution</div>
    <div id="exec-sm"></div>
    <div class="exec-ids" id="exec-ids"></div>
    <div class="fault-row">
      <span class="fault-k">Break it on purpose</span>
      <button class="btn btn-sm on" data-fault="none">None</button>
      <button class="btn btn-sm" data-fault="remote_timeout">Response lost</button>
      <button class="btn btn-sm" data-fault="remote_lost">Never dispatched</button>
      <button class="btn btn-sm" data-fault="remote_reject">Provider refuses</button>
    </div>
    <div class="recon" id="recon">
      <div class="alert alert-warn">
        <b>The outcome is unknown.</b>
        The provider was contacted and no answer came back before the timeout.
        SELLABLE will not tell you this succeeded and will not tell you it failed,
        because it does not know. It also will not retry &mdash; a blind retry of an
        unknown outcome is how one charge becomes two.
      </div>
      <button class="btn btn-primary" id="recon-go">Reconcile against the provider</button>
    </div>
  </div>

  <div class="sec-h">
    <span class="sec-t">Market evidence <span class="chip chip-violet">advisory</span></span>
    <span class="sec-n" id="ev-n"></span>
  </div>
  <div class="pgrid" id="grid"></div>
  <div class="empty" id="empty" style="display:none">
    No retail source returned a usable listing for this query.
    Nothing is invented to fill the gap.
  </div>
  <div class="legend">
    <span class="legend-i"><span class="chip chip-ok">observed</span> price seen verbatim in INR</span>
    <span class="legend-i"><span class="chip chip-warn">fx</span> converted at a static rate &mdash; an estimate</span>
    <span class="legend-i"><span class="chip chip-dim">mock</span> synthetic API data, excluded from comparison</span>
    <span class="legend-i"><span class="chip chip-dim">unverified</span> matched the query, published no price</span>
  </div>
</main>

<div class="wrap"><div class="jstrip">
  <div>
    <div class="jstrip-t">Reviewing this for Razorpay?</div>
    <div class="jstrip-s">The cockpit runs the same code you just used, plus the parts
      a shopper never sees: eight adversarial scenarios, a custom attack you write
      yourself, a real provider timeout, and a ledger block you can verify in your own
      browser.</div>
  </div>
  <a class="btn btn-primary" href="/judge">Open the cockpit &rarr;</a>
</div></div>

<div class="ov" id="ov" role="dialog" aria-modal="true" aria-labelledby="mtitle">
  <div class="modal">
    <div class="mh">
      <span class="mt" id="mtitle">Authorize this purchase</span>
      <button class="mx" id="mclose" aria-label="Close">&times;</button>
    </div>
    <div class="mb">
      <div class="mgroup">
        <div class="mk">You are authorizing</div>
        <div style="font-size:15px;font-weight:600" id="m-name">&mdash;</div>
        <div class="mprice" id="m-price">&mdash;</div>
        <div class="m" style="font-size:11.5px;color:var(--text-dim);margin-top:5px" id="m-sku">&mdash;</div>
      </div>
      <div class="mgroup">
        <div class="mk">Against your limits</div>
        <div class="rec-facts" id="m-limits"></div>
      </div>
      <div class="mgroup">
        <div class="mk">Checked before anything can be charged</div>
        <div id="m-checks"></div>
      </div>
      <div class="mgroup">
        <div class="mk">Why the AI picked this</div>
        <div class="reason" id="m-reason">&mdash;</div>
      </div>
      <div class="disc" id="m-disc"></div>
      <button class="approve" id="approve">Approve &mdash; this exact cart, once</button>
    </div>
  </div>
</div>

{FOOTER}
<script>{PROVIDER_BADGE_JS}</script>
<script>{{JS}}</script>
</body>
</html>"""


_JS = r"""
const $ = id => document.getElementById(id);
const esc = s => String(s == null ? '' : s)
  .replace(/&/g,'&amp;').replace(/</g,'&lt;').replace(/>/g,'&gt;').replace(/"/g,'&quot;');
const REDUCED = window.matchMedia('(prefers-reduced-motion: reduce)').matches;

const S = {query:'', budget_paise:300000, discovery:null, sku:null,
           fault:'none', exec_id:null, provider:null, issuer:null};

/* ── the rail advances only when a step actually completed ─────────── */
const STEPS = ['discover','gateway','auth','exec','done'];
const PCT = {discover:8, gateway:30, auth:52, exec:76, done:100};
const EL = {discover:'s-discover', gateway:'s-gateway', auth:'s-auth',
            exec:'s-exec', done:'s-done'};
function step(name, state){
  const el = $(EL[name]);
  el.className = 'step ' + state;
  const i = STEPS.indexOf(name);
  STEPS.slice(0, i).forEach(s => {
    const p = $(EL[s]);
    if (!/stop|wait/.test(p.className)) p.className = 'step done';
  });
  $('rail-bar').style.width = (PCT[name] || 0) + '%';
}
function say(msg){ $('status').textContent = msg; }
function showRail(){ $('rail-wrap').classList.add('on'); }

function alertBox(kind, title, body, meta){
  $('alerts').innerHTML = '<div class="alert alert-' + kind + '">' +
    '<b>' + esc(title) + '</b>' + esc(body) +
    (meta ? '<span class="m">' + esc(meta) + '</span>' : '') + '</div>';
}
function clearAlerts(){ $('alerts').innerHTML = ''; }
function rupees(v){
  if (v == null) return '—';
  return '₹' + Number(v).toLocaleString('en-IN', {maximumFractionDigits:2});
}

async function jfetch(url, opts){
  const r = await fetch(url, opts);
  let body = null;
  try { body = await r.json(); } catch(e){ body = {parse_error:String(e)}; }
  return {status:r.status, ok:r.ok, body:body};
}

/* ── search ────────────────────────────────────────────────────────── */
document.querySelectorAll('.qchip').forEach(b => b.addEventListener('click', () => {
  $('q').value = b.dataset.q; $('budget').value = b.dataset.b; search();
}));
$('go').addEventListener('click', search);
$('q').addEventListener('keydown', e => { if (e.key === 'Enter') search(); });

async function search(){
  const q = $('q').value.trim();
  if (!q){ $('q').focus(); return; }
  S.query = q;
  S.budget_paise = (parseInt($('budget').value, 10) || 3000) * 100;
  S.discovery = null; S.sku = null; S.exec_id = null;

  const btn = $('go'); btn.disabled = true; btn.textContent = 'Searching…';
  showRail(); step('discover','active'); say('querying live retail sources…');
  clearAlerts();
  $('results').style.display = 'none';
  $('exec').classList.remove('on');
  $('recon').classList.remove('on');

  try {
    const r = await jfetch('/discovery/search', {
      method:'POST', headers:{'Content-Type':'application/json'},
      body: JSON.stringify({query:q, budget_paise:S.budget_paise})});
    if (!r.ok){
      step('discover','stop');
      say('search failed');
      alertBox('bad', 'Search failed', (r.body && r.body.detail) || ('HTTP ' + r.status));
      return;
    }
    S.discovery = r.body;
    render(r.body);
  } catch(e){
    step('discover','stop'); say('search failed');
    alertBox('bad', 'Search failed', e.message);
  } finally { btn.disabled = false; btn.textContent = 'Search'; }
}

function render(d){
  $('results').style.display = 'block';
  step('discover','done');

  /* the search status is reported exactly as the server classified it */
  const st = d.search_engine_status;
  if (st === 'LIVE_SEARCH_SUCCESS'){
    say('live retail sources answered · ' + (d.providers_hit || []).length + ' provider(s)');
  } else if (st === 'MOCK_SOURCES_ONLY'){
    say('no live retail listing — only synthetic API records');
    alertBox('warn', 'No real market evidence this time',
      'Every whitelisted retail source either failed or published no usable price, so ' +
      'there is nothing to compare the merchant price against. The recommendation below ' +
      'still stands on the catalog; it simply makes no claim about the market.',
      d.error_message || '');
  } else if (st === 'SEARCH_UNAVAILABLE'){
    say('retail search unavailable');
    alertBox('warn', 'Retail search is unavailable',
      'Discovery reports the failure rather than falling back to invented prices.',
      d.error_message || '');
  } else {
    say('providers responded, no matching products');
  }

  /* recommendation — split across the boundary */
  const rec = d.recommendation, offer = d.merchant_offer;
  if (rec && offer){
    S.sku = offer.sku;
    $('rec').style.display = 'grid';
    $('rec-name').textContent = offer.name;
    $('rec-price').textContent = rupees(offer.price_inr);

    const why = [];
    const cmp = d.comparison || {};
    if (cmp.lowest_observed_market_price_inr != null){
      why.push(offer.price_inr <= cmp.lowest_observed_market_price_inr
        ? 'At or below the lowest price actually observed in the search (' +
          rupees(cmp.lowest_observed_market_price_inr) + ' at ' +
          (cmp.lowest_observed_market_seller || 'a retail source') + ')'
        : 'For context, the lowest observed market price was ' +
          rupees(cmp.lowest_observed_market_price_inr) + ' at ' +
          (cmp.lowest_observed_market_seller || 'a retail source'));
    } else {
      why.push('No verbatim INR market price was observed, so no price comparison is claimed');
    }
    if (offer.rating) why.push('Rated ' + offer.rating + '/5 in the merchant catalog');
    if (rec.recommendation_reason) why.push(rec.recommendation_reason);
    $('rec-why').innerHTML = why.slice(0,4)
      .map(t => '<div class="rec-why-i">' + esc(t) + '</div>').join('');

    const fits = offer.price_paise <= S.budget_paise;
    $('rec-facts').innerHTML = [
      ['SKU', offer.sku],
      ['Category', offer.category],
      ['Your ceiling', rupees(S.budget_paise/100)],
      ['Fits the mandate', fits ? 'yes' : 'no — this would be refused']
    ].map(([k,v]) => '<div class="fact"><span class="fact-k">' + esc(k) +
        '</span><span class="fact-v">' + esc(v) + '</span></div>').join('');
    $('buy').disabled = !fits;
    step('gateway','done');
  } else {
    $('rec').style.display = 'none';
  }

  /* the probe — a real over-budget SKU from the same catalog */
  const p = d.policy_probe;
  if (p){
    $('probe').style.display = 'block';
    $('probe-n').textContent = p.name + ' · ' + rupees(p.price_inr);
    $('probe-d').textContent = p.why;
    $('probe').dataset.sku = p.sku;
  } else { $('probe').style.display = 'none'; }

  /* evidence cards */
  const listings = (d.listings || []);
  const grid = $('grid');
  grid.innerHTML = '';
  $('ev-n').textContent = listings.length + ' source' + (listings.length === 1 ? '' : 's');
  $('empty').style.display = listings.length ? 'none' : 'block';
  const CHIP = {OBSERVED:'chip-ok', FX_CONVERTED:'chip-warn',
                MOCK_SOURCE:'chip-dim', UNVERIFIED:'chip-dim'};
  listings.slice(0,9).forEach(l => {
    const el = document.createElement('div');
    el.className = 'pcard';
    el.innerHTML =
      '<div class="pcard-top"><div class="pname">' + esc(l.product_name) + '</div>' +
      '<span class="chip ' + (CHIP[l.evidence_class] || 'chip-dim') + '">' +
        esc(l.evidence_class) + '</span></div>' +
      (l.price_inr != null
        ? '<div class="pprice">' + esc(rupees(l.price_inr)) +
          (l.fx_converted ? '<small>fx estimate</small>' : '') + '</div>'
        : '<div style="font-size:12.5px;color:var(--text-dim)">no price published</div>') +
      '<div class="pseller">' +
        (l.url ? '<a href="' + esc(l.url) + '" target="_blank" rel="noopener">' +
                 esc(l.seller) + '</a>' : esc(l.seller)) +
        '<span>·</span><span class="m">' + esc((l.scraped_at || '').slice(0,10)) + '</span>' +
      '</div>';
    grid.appendChild(el);
  });
}

/* ── the probe: a real refusal, not a staged one ───────────────────── */
$('probe-go').addEventListener('click', async function(){
  const sku = $('probe').dataset.sku;
  if (!sku) return;
  this.disabled = true; this.textContent = 'Sending to the gateway…';
  step('gateway','active'); say('evaluating an over-budget proposal…');
  try {
    const r = await jfetch('/discovery/checkout', {
      method:'POST', headers:{'Content-Type':'application/json'},
      body: JSON.stringify({sku:sku, budget_paise:S.budget_paise})});
    const b = r.body;
    if (b.ok){
      step('gateway','stop');
      alertBox('bad', 'Unexpected: the gateway allowed it',
        'This should not happen. Please report it.');
    } else {
      step('gateway','stop'); say('refused by ' + (b.rule_id || b.status));
      alertBox('warn', 'Refused — ' + (b.rule_id || b.status),
        b.headline || b.message || '',
        'money boundary calls during this request: ' +
        b.money_boundary_calls_during_request +
        ' · execution opened: ' + (b.execution_state === null ? 'none' : b.execution_state));
    }
  } catch(e){ alertBox('bad', 'Request failed', e.message); }
  finally {
    this.disabled = false;
    this.textContent = 'Ask the agent to buy this instead →';
  }
});

/* ── authorization ─────────────────────────────────────────────────── */
$('buy').addEventListener('click', openModal);
$('mclose').addEventListener('click', closeModal);
$('ov').addEventListener('click', e => { if (e.target === $('ov')) closeModal(); });
document.addEventListener('keydown', e => { if (e.key === 'Escape') closeModal(); });

function openModal(){
  const d = S.discovery, offer = d && d.merchant_offer;
  if (!offer) return;
  const fits = offer.price_paise <= S.budget_paise;

  $('m-name').textContent = offer.name;
  $('m-price').textContent = rupees(offer.price_inr);
  $('m-sku').textContent = 'SKU ' + offer.sku + ' · ' + offer.category;
  $('m-limits').innerHTML = [
    ['Your signed ceiling', rupees(S.budget_paise/100)],
    ['This purchase', rupees(offer.price_inr)],
    ['Headroom', rupees((S.budget_paise - offer.price_paise)/100)]
  ].map(([k,v]) => '<div class="fact"><span class="fact-k">' + esc(k) +
      '</span><span class="fact-v">' + esc(v) + '</span></div>').join('');

  $('m-checks').innerHTML = [
    ['The amount comes from the merchant catalog, never from the AI or a web listing', true],
    ['Twelve deterministic policy rules, with no model in the path', true],
    ['Your approval is bound to this exact cart and can be spent once', true],
    ['Within your signed ceiling', fits]
  ].map(([t, ok]) => '<div class="gcheck"><span class="gi ' + (ok?'p':'f') + '">' +
      (ok ? '✓' : '✗') + '</span><span>' + esc(t) + '</span></div>').join('');

  $('m-reason').textContent =
    (d.recommendation && d.recommendation.recommendation_reason) ||
    'No additional reasoning was returned.';

  step('auth','wait');
  $('ov').classList.add('on');
  $('approve').focus();
  loadDisclosure();
}
function closeModal(){
  $('ov').classList.remove('on');
  if ($(EL.auth).className.includes('wait')) $(EL.auth).className = 'step';
}

/* the disclosure is read from runtime state, never hardcoded */
async function loadDisclosure(){
  const el = $('m-disc');
  el.textContent = 'checking how this authorization is issued…';
  try {
    const d = (await jfetch('/diagnostics')).body;
    const sim = (d.payments || {}).provider === 'simulated';
    el.innerHTML = '<b style="color:var(--text-hi);display:block;margin-bottom:5px">' +
      'How this demo differs from production</b>' +
      'Your mandate is signed by an issuer running <em>inside</em> this server ' +
      '(<span class="m">in_process_demo_issuer</span>), so it proves the ' +
      'approval was not tampered with, but not that only you could have made it. ' +
      'In production the wallet holds that key. ' +
      (sim ? 'Payments are simulated — no Razorpay credentials are configured.'
           : 'Payments run against Razorpay test mode: a real order, no real money.');
  } catch(e){
    el.textContent = 'Could not read /diagnostics: ' + e.message;
  }
}

/* ── execute ───────────────────────────────────────────────────────── */
document.querySelectorAll('[data-fault]').forEach(b => b.addEventListener('click', () => {
  S.fault = b.dataset.fault;
  document.querySelectorAll('[data-fault]').forEach(x => x.classList.remove('on'));
  b.classList.add('on');
}));

const SM = [
  ['APPROVED','Authorization exists. Nothing has been sent anywhere.'],
  ['EXECUTION_PENDING','About to contact the payment provider.'],
  ['REMOTE_ATTEMPTED','Written to disk before the call, so a crash here is recoverable.'],
  ['RECONCILIATION_REQUIRED','Outcome unknown. Nothing is assumed; no blind retry.'],
  ['EXECUTED','The provider accepted and returned an order.'],
  ['FAILED','No money moved.']
];
function renderSM(cur){
  const i = SM.findIndex(s => s[0] === cur);
  $('exec-sm').innerHTML = SM.map((s, ix) => {
    let cls = 'smr';
    if (ix < i && s[0] !== 'EXECUTED' && s[0] !== 'FAILED') cls += ' done';
    else if (s[0] === cur) cls += cur === 'EXECUTED' ? ' done'
      : cur === 'FAILED' ? ' bad' : cur === 'RECONCILIATION_REQUIRED' ? ' warn' : ' cur';
    return '<div class="' + cls + '"><span class="d"></span>' +
      '<span class="n">' + esc(s[0]) + '</span><span class="x">' + esc(s[1]) + '</span></div>';
  }).join('');
}

$('approve').addEventListener('click', async function(){
  const btn = this;
  btn.disabled = true; btn.textContent = 'Authorizing…';
  closeModal();
  step('auth','done'); step('exec','active'); say('contacting the payment provider…');
  $('exec').classList.add('on');
  $('recon').classList.remove('on');
  renderSM('EXECUTION_PENDING');
  $('exec').scrollIntoView({behavior: REDUCED ? 'auto' : 'smooth', block:'start'});

  try {
    const r = await jfetch('/discovery/checkout', {
      method:'POST', headers:{'Content-Type':'application/json'},
      body: JSON.stringify({sku:S.sku, budget_paise:S.budget_paise,
                            fault: S.fault !== 'none' ? S.fault : ''})});
    const b = r.body;
    /* `ok` is the only thing that means success. 202 is a 2xx. */
    const state = b.execution_state || (b.ok ? 'EXECUTED' : 'FAILED');
    S.exec_id = b.execution_id || null;
    renderSM(state);
    $('exec-ids').textContent = [
      b.execution_id ? 'execution      ' + b.execution_id : '',
      b.order_id ? 'provider order ' + b.order_id : '',
      b.mission_id ? 'mission        ' + b.mission_id : '',
      b.provider ? 'provider       ' + b.provider : '',
      b.proposal_hash ? 'proposal       ' + b.proposal_hash : ''
    ].filter(Boolean).join('\n');

    if (b.ok){
      step('exec','done'); step('done','done');
      say('order created · ' + b.order_id);
      alertBox('ok', 'Order created — ' + b.order_id,
        'An order is not a captured payment. SELLABLE will not claim settlement ' +
        'until a signature-verified webhook says so.',
        'priced from ' + b.priced_from);
      $('alerts').insertAdjacentHTML('beforeend',
        '<div class="row-actions" style="display:flex;gap:8px;flex-wrap:wrap;margin-bottom:18px">' +
        '<a class="btn btn-sm" href="/trace/' + esc(b.execution_id) + '">See every step of this purchase →</a>' +
        '<a class="btn btn-sm" href="/api/v1/receipt/' + esc(b.execution_id) + '" target="_blank" rel="noopener">Receipt JSON</a>' +
        '</div>');
    } else if (state === 'RECONCILIATION_REQUIRED'){
      step('exec','wait'); say('outcome unknown — reconciliation required');
      $('recon').classList.add('on');
      alertBox('warn', 'We do not know whether that went through',
        b.headline || '', b.detail || '');
    } else {
      step('exec','stop'); say(b.status || 'refused');
      alertBox('bad', b.rule_id ? ('Refused by ' + b.rule_id) : (b.status || 'Refused'),
        b.headline || b.message || '',
        'money boundary calls during this request: ' +
        b.money_boundary_calls_during_request);
    }
  } catch(e){
    step('exec','stop'); say('request failed');
    alertBox('bad', 'Request failed', e.message);
  } finally { btn.disabled = false; btn.textContent = 'Approve — this exact cart, once'; }
});

$('recon-go').addEventListener('click', async function(){
  if (!S.exec_id) return;
  const btn = this;
  btn.disabled = true; btn.textContent = 'Reading provider state…';
  try {
    const r = await jfetch('/discovery/reconcile/' + encodeURIComponent(S.exec_id),
                           {method:'POST'});
    const d = r.body;
    renderSM(d.state);
    if (d.state === 'EXECUTED'){
      step('exec','done'); step('done','done');
      say('reconciled — the order existed after all');
      $('recon').classList.remove('on');
      alertBox('ok', 'Reconciled: the order exists',
        d.explanation || '', d.remote_order_id ? 'order ' + d.remote_order_id : '');
    } else if (d.state === 'FAILED'){
      step('exec','stop'); say('reconciled — no money moved');
      $('recon').classList.remove('on');
      alertBox('bad', 'Reconciled: nothing was charged', d.explanation || '');
    } else {
      say('still unresolved');
      alertBox('warn', 'Still unresolved', d.explanation || '',
        d.retry_after_seconds != null
          ? 'ask again in ' + d.retry_after_seconds + 's' : '');
    }
  } catch(e){ alertBox('bad', 'Reconcile failed', e.message); }
  finally { btn.disabled = false; btn.textContent = 'Reconcile against the provider'; }
});

$('q').focus();
"""

PAGE = PAGE.replace("{JS}", _JS)


@router.get("/", response_class=HTMLResponse)
async def product_page() -> HTMLResponse:
    return HTMLResponse(PAGE)
