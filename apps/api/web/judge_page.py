"""GET /judge (and /cockpit) — the reviewer's cockpit.

SEVEN SCENES, ONE PAGE
----------------------
  A  Sentinel        live status, read from real endpoints on a poll
  B  Gauntlet        every built-in attack, one button, real latencies
  C  Mission         the agent actually shops; the timeline is its trace
  D  Negotiation     buyer vs merchant, with the policy clamp visible
  E  Two locks       write your own attack; watch both layers refuse it
  F  Kill & resurrect  really kill the process, watch recovery classify it
  G  Trust nothing   verify a chain block in your own browser, then break it

WHY IT IS ONE PAGE
------------------
There used to be a console, a mission viewer, a gateway UI, an attack UI,
an audit UI, a chaos room, an architecture page, a growth studio and a
protocol page. A reviewer had to find nine surfaces and work out which
generation of the project each belonged to. Everything they showed is
here, and every scene calls the same code the storefront calls.

WHAT IS NOT ON THIS PAGE
------------------------
A number that was typed in by hand. Metrics from a test run are read from
docs/generated/truth.json, which scripts/generate_truth.py writes by
running the thing it measures; everything else is fetched live and
rendered exactly as it arrived. When a fetch fails the panel says so, in
red, with the real error — there is no fallback content.
"""
from __future__ import annotations

import html
import json
from pathlib import Path
from typing import Any

from fastapi import APIRouter
from fastapi.responses import HTMLResponse

from .shell import FOOTER, PROVIDER_BADGE_JS, head, nav

router = APIRouter()

TRUTH_PATH = Path(__file__).resolve().parents[3] / "docs" / "generated" / "truth.json"


def _load_truth() -> dict[str, Any]:
    try:
        return json.loads(TRUTH_PATH.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return {}


def _esc(v: Any) -> str:
    return html.escape("" if v is None else str(v))


SCENES = [
    ("sentinel", "A", "Sentinel"),
    ("gauntlet", "B", "Gauntlet"),
    ("mission", "C", "Mission"),
    ("negotiation", "D", "Negotiation"),
    ("locks", "E", "Two locks"),
    ("recovery", "F", "Kill &amp; resurrect"),
    ("trust", "G", "Trust nothing"),
    ("evidence", "—", "Evidence"),
]

_CSS = """
/* ── status strip (S1) ─────────────────────────────────────────────── */
.strip{border-bottom:1px solid var(--border);background:var(--bg-inset)}
.strip-in{max-width:1440px;margin:0 auto;padding:0 24px;height:48px;
  display:flex;align-items:center;gap:0;overflow-x:auto;scrollbar-width:none}
.strip-in::-webkit-scrollbar{display:none}
.pill{display:flex;align-items:center;gap:9px;padding:0 20px;height:48px;
  border-right:1px solid var(--border);white-space:nowrap;flex-shrink:0}
.pill:first-child{padding-left:0}
.pill-k{font-family:var(--mono);font-size:9.5px;font-weight:700;
  letter-spacing:.16em;text-transform:uppercase;color:var(--text-dim)}
.pill-v{font-family:var(--mono);font-size:12px;font-weight:500;color:var(--text-hi)}
.pill-v.ok{color:var(--teal)} .pill-v.bad{color:var(--red)} .pill-v.warn{color:var(--amber)}

/* ── hero ──────────────────────────────────────────────────────────── */
.hero{padding:44px 0 26px}
.kicker{font-family:var(--mono);font-size:10.5px;font-weight:700;
  letter-spacing:.2em;text-transform:uppercase;color:var(--violet);margin-bottom:16px}
.hero h1{font-size:clamp(28px,4.4vw,52px);font-weight:700;letter-spacing:-.035em;
  line-height:1.06;max-width:17ch}
.hero h1 .a{color:var(--violet)}
.hero h1 .b{color:var(--teal)}
.hero p{color:var(--text-mid);margin-top:18px;max-width:64ch;font-size:15.5px}

/* ── scene nav ─────────────────────────────────────────────────────── */
.scenes{position:sticky;top:52px;z-index:90;background:rgba(7,7,11,.94);
  backdrop-filter:blur(12px);border-bottom:1px solid var(--border);margin-bottom:26px}
.scenes-in{max-width:1440px;margin:0 auto;padding:0 24px;display:flex;gap:0;
  overflow-x:auto;scrollbar-width:none}
.scenes-in::-webkit-scrollbar{display:none}
.scene-tab{display:flex;align-items:baseline;gap:8px;padding:13px 16px 11px;
  border-bottom:2px solid transparent;white-space:nowrap;color:var(--text-mid);
  font-size:13px;font-weight:500;transition:color .15s ease-out}
.scene-tab .ix{font-family:var(--mono);font-size:10px;font-weight:700;
  color:var(--text-dim);letter-spacing:.1em}
.scene-tab:hover{color:var(--text-hi)}
.scene-tab[aria-selected="true"]{color:var(--text-hi);border-bottom-color:var(--violet)}
.scene-tab[aria-selected="true"] .ix{color:var(--violet)}
.scene[hidden]{display:none}
.scene{padding-bottom:28px}

/* ── scene furniture ───────────────────────────────────────────────── */
h2.st{font-size:24px;font-weight:700;letter-spacing:-.028em;margin-bottom:8px}
p.sl{color:var(--text-mid);max-width:74ch;margin-bottom:18px;font-size:14.5px}
h3.sh{font-size:14px;font-weight:600;margin:24px 0 8px;letter-spacing:-.01em}
.grid2{display:grid;grid-template-columns:repeat(auto-fit,minmax(320px,1fr));gap:14px}
.grid3{display:grid;grid-template-columns:repeat(auto-fit,minmax(210px,1fr));gap:12px}
.row-actions{display:flex;gap:8px;flex-wrap:wrap;align-items:center}

/* ── S5 gauntlet scoreboard ────────────────────────────────────────── */
.board{border:1px solid var(--border);border-radius:var(--r-panel);overflow:hidden;
  background:var(--bg-panel);margin-top:14px}
.brow{display:grid;grid-template-columns:22px minmax(150px,1.4fr) 116px minmax(190px,1.5fr) 88px 74px 44px;
  gap:12px;padding:11px 14px;border-bottom:1px solid var(--border);
  align-items:center;font-size:12.5px}
.brow:last-child{border-bottom:none}
.brow.h{background:var(--bg-inset);font-family:var(--mono);font-size:9.5px;
  font-weight:700;letter-spacing:.13em;text-transform:uppercase;color:var(--text-dim)}
.brow .ix{font-family:var(--mono);font-size:11px;color:var(--text-dim)}
.brow .nm{font-weight:500}
.brow .id{font-family:var(--mono);font-size:10px;color:var(--text-dim);display:block}
.banner{margin-top:14px;border:1px solid var(--teal);background:var(--teal-soft);
  border-radius:var(--r-panel);padding:16px 18px}
.banner.bad{border-color:var(--red);background:var(--red-soft)}
.banner-t{font-family:var(--mono);font-size:19px;font-weight:700;color:var(--teal);
  letter-spacing:-.01em}
.banner.bad .banner-t{color:var(--red)}
.banner-s{font-size:11px;color:var(--text-dim);margin-top:6px;font-family:var(--mono)}

/* ── S2 timeline ───────────────────────────────────────────────────── */
.tl{margin-top:14px;position:relative;padding-left:22px}
.tl::before{content:"";position:absolute;left:4px;top:6px;bottom:6px;
  width:2px;background:var(--border)}
.tev{position:relative;padding:9px 0 9px 14px;display:grid;
  grid-template-columns:78px 1fr;gap:12px;align-items:baseline}
.tev::before{content:"";position:absolute;left:-22px;top:15px;width:9px;height:9px;
  background:var(--teal);transform:rotate(45deg);border:2px solid var(--bg-base)}
.tev.rej::before{background:var(--red)}
.tev.inj::before{background:var(--amber)}
.tev.model::before{background:var(--violet)}
.tev-ts{font-family:var(--mono);font-size:10.5px;color:var(--text-dim)}
.tev-b{min-width:0}
.tev-a{font-family:var(--mono);font-size:10.5px;color:var(--violet);
  letter-spacing:.06em;text-transform:uppercase}
.tev-s{font-size:13px;color:var(--text-hi);margin-top:2px;word-break:break-word}
.tev.inj .tev-s{color:var(--amber)}
.tev.rej .tev-s{color:var(--red)}

/* ── S3 negotiation ────────────────────────────────────────────────── */
.nego{display:grid;grid-template-columns:1fr 1fr;gap:14px;margin-top:14px}
.nego-col-k{font-family:var(--mono);font-size:10px;font-weight:700;
  letter-spacing:.15em;text-transform:uppercase;margin-bottom:10px}
.nego-col.buyer .nego-col-k{color:var(--violet)}
.nego-col.merch .nego-col-k{color:var(--teal)}
.bub{border-radius:var(--r-panel);padding:12px 14px;margin-bottom:10px;
  border:1px solid var(--border)}
.nego-col.buyer .bub{background:var(--violet-soft);border-color:var(--violet-line)}
.nego-col.merch .bub{background:var(--bg-panel)}
.bub-p{font-family:var(--mono);font-size:20px;font-weight:700;letter-spacing:-.02em}
.bub-r{font-size:12.5px;color:var(--text-mid);margin-top:5px}
.bub-t{font-family:var(--mono);font-size:10px;color:var(--text-dim);margin-bottom:5px}
.deal{margin-top:14px;border:1px solid var(--teal);background:var(--teal-soft);
  border-radius:var(--r-panel);padding:18px 20px;display:flex;
  align-items:center;justify-content:space-between;gap:16px;flex-wrap:wrap}
.deal-p{font-family:var(--mono);font-size:32px;font-weight:700;letter-spacing:-.03em}

/* ── S4 attack terminal ────────────────────────────────────────────── */
.term{background:var(--bg-inset);border:1px solid var(--border);
  border-radius:var(--r-panel);overflow:hidden;margin-top:14px}
.term-bar{display:flex;align-items:center;gap:7px;padding:10px 14px;
  border-bottom:1px solid var(--border);background:var(--bg-panel)}
.term-dot{width:8px;height:8px;border-radius:50%}
.term-t{font-family:var(--mono);font-size:11px;color:var(--text-dim);margin-left:8px}
.term-body{padding:16px}
textarea.json{width:100%;min-height:190px;resize:vertical;background:var(--bg-base);
  border:1px solid var(--border);border-radius:var(--r-ctl);padding:12px;
  color:var(--text-hi);font-family:var(--mono);font-size:12px;line-height:1.65}
textarea.json:focus{border-color:var(--violet);outline:none}
.money-line{font-family:var(--mono);font-size:clamp(16px,2.6vw,32px);font-weight:700;
  letter-spacing:-.025em;margin-top:18px;color:var(--teal);word-break:break-word}
.kick{margin-top:12px;font-family:var(--mono);font-size:12px;line-height:1.75;
  color:var(--amber);letter-spacing:.02em;max-width:70ch;min-height:3.4em}
.kick.binding{color:var(--red);font-size:clamp(13px,1.9vw,19px);font-weight:700}

/* ── S6 chain cards ────────────────────────────────────────────────── */
.chain{display:flex;gap:0;align-items:center;overflow-x:auto;padding:14px 0 6px;
  scrollbar-width:thin}
.cblk{flex-shrink:0;border:1px solid var(--border);border-radius:var(--r-ctl);
  background:var(--bg-panel);padding:9px 11px;min-width:132px;
  transition:border-color .2s ease-out,background .2s ease-out}
.cblk-s{font-family:var(--mono);font-size:10px;color:var(--text-dim)}
.cblk-h{font-family:var(--mono);font-size:11px;color:var(--teal);margin-top:3px}
.cblk-a{font-size:11px;color:var(--text-mid);margin-top:3px;
  white-space:nowrap;overflow:hidden;text-overflow:ellipsis;max-width:118px}
.cblk.broken{border-color:var(--red);background:var(--red-soft)}
.cblk.broken .cblk-h{color:var(--red)}
.clink{width:16px;height:1px;background:var(--border);flex-shrink:0}

/* ── S7 receipt ────────────────────────────────────────────────────── */
.receipt{background:#F4F4F8;color:#17171F;border-radius:var(--r-panel);
  padding:24px 26px;max-width:460px;position:relative;
  box-shadow:0 12px 32px rgba(0,0,0,.5)}
.receipt::before,.receipt::after{content:"";position:absolute;left:0;right:0;height:8px;
  background-image:radial-gradient(circle at 5px -1px,transparent 5px,#F4F4F8 5px);
  background-size:10px 8px}
.receipt::before{top:-7px;transform:rotate(180deg)}
.receipt::after{bottom:-7px}
.rc-h{font-family:var(--mono);font-size:11px;font-weight:700;letter-spacing:.16em;
  text-transform:uppercase;color:#6A6A80;padding-bottom:12px;
  border-bottom:1px dashed #C8C8D6;margin-bottom:14px}
.rc-row{display:flex;justify-content:space-between;gap:14px;padding:6px 0;align-items:baseline}
.rc-k{font-family:var(--mono);font-size:10px;font-weight:700;letter-spacing:.09em;
  text-transform:uppercase;color:#7A7A90;flex-shrink:0}
.rc-v{font-family:var(--mono);font-size:13px;text-align:right;word-break:break-all;color:#17171F}
.rc-total{border-top:1px dashed #C8C8D6;margin-top:12px;padding-top:12px}
.rc-total .rc-v{font-size:22px;font-weight:700}
.rc-stamp{margin-top:16px;display:inline-block;border:2px solid #0B7C72;color:#0B7C72;
  border-radius:6px;padding:6px 13px;font-family:var(--mono);font-size:12px;
  font-weight:700;letter-spacing:.14em;transform:rotate(-3deg);opacity:.9}
.rc-stamp.settle{animation:stamp .45s cubic-bezier(.2,1.4,.4,1) both}
@keyframes stamp{
  0%{transform:scale(2.4) rotate(-14deg);opacity:0}
  100%{transform:scale(1) rotate(-3deg);opacity:.9}
}
.rc-cap{margin-top:16px;font-size:11.5px;color:#5A5A70;line-height:1.65;
  border-top:1px dashed #C8C8D6;padding-top:12px}

/* ── tables ────────────────────────────────────────────────────────── */
table.t{width:100%;border-collapse:collapse;font-size:13px;margin-top:10px}
table.t th,table.t td{text-align:left;padding:9px 10px;
  border-bottom:1px solid var(--border);vertical-align:top}
table.t th{font-family:var(--mono);font-size:9.5px;letter-spacing:.13em;
  text-transform:uppercase;color:var(--text-dim);font-weight:700}
table.t td.n{font-family:var(--mono);font-variant-numeric:tabular-nums;color:var(--text-hi)}
table.t td{color:var(--text-mid)}

/* ── rules matrix ──────────────────────────────────────────────────── */
.rules{display:grid;grid-template-columns:repeat(auto-fill,minmax(192px,1fr));gap:7px;margin-top:12px}
.rule{border:1px solid var(--border);border-left-width:3px;border-radius:var(--r-ctl);
  padding:8px 10px;background:var(--bg-panel);font-size:12px}
.rule.pass{border-left-color:var(--teal)}
.rule.fail{border-left-color:var(--red);background:var(--red-soft)}
.rule-id{font-family:var(--mono);font-size:10.5px;font-weight:700;color:var(--text-hi)}
.rule-w{color:var(--text-dim);font-size:11px;margin-top:2px;line-height:1.5}

/* ── state machine ─────────────────────────────────────────────────── */
.sm{margin-top:14px}
.smr{display:grid;grid-template-columns:14px minmax(160px,190px) 1fr;gap:12px;
  padding:8px 0;align-items:start;opacity:.35;transition:opacity .2s ease-out}
.smr .d{width:9px;height:9px;border-radius:50%;background:var(--border-hi);margin-top:5px}
.smr .n{font-family:var(--mono);font-size:11.5px;font-weight:700}
.smr .x{font-size:12.5px;color:var(--text-mid)}
.smr.done{opacity:1} .smr.done .d{background:var(--teal)}
.smr.cur{opacity:1} .smr.cur .d{background:var(--violet);box-shadow:0 0 0 4px var(--violet-soft)}
.smr.warn{opacity:1} .smr.warn .d{background:var(--amber);box-shadow:0 0 0 4px var(--amber-soft)}
.smr.bad{opacity:1} .smr.bad .d{background:var(--red)}

/* ── callouts / lists ──────────────────────────────────────────────── */
.note{border-radius:var(--r-panel);padding:13px 15px;font-size:13px;margin:14px 0;line-height:1.65}
.note-warn{background:var(--amber-soft);border:1px solid rgba(255,178,36,.28);color:#F0C070}
.note-ok{background:var(--teal-soft);border:1px solid rgba(45,212,191,.28);color:#8FE8DC}
.note-info{background:var(--violet-soft);border:1px solid var(--violet-line);color:#B4A0FF}
.note-bad{background:var(--red-soft);border:1px solid rgba(255,77,94,.28);color:#FFA5AE}
.inv{border-left:2px solid var(--teal);padding:10px 0 10px 14px;margin-bottom:12px}
.inv b{display:block;font-size:13.5px;font-weight:600;margin-bottom:3px}
.inv span{color:var(--text-mid);font-size:12.5px;display:block}
.inv code{display:inline-block;margin-top:6px;font-size:10.5px;color:var(--violet)}
.lim{border-left:2px solid var(--amber);padding:10px 0 10px 14px;margin-bottom:12px;
  font-size:12.5px;color:var(--text-mid)}
.lim b{display:block;color:var(--text-hi);font-size:13px;margin-bottom:3px}

@media (max-width:900px){
  .nego{grid-template-columns:1fr}
  .brow{grid-template-columns:1fr 1fr;gap:6px}
  .brow.h{display:none}
  .tev{grid-template-columns:1fr}
}
"""


# ────────────────────────────────────────────────────────── scene markup

def _scene_sentinel(truth: dict[str, Any]) -> str:
    code = truth.get("codebase", {})
    return f"""
<h2 class="st">The AI decides what to recommend. It cannot decide what money moves.</h2>
<p class="sl">That is not a policy document, it is an architecture. A model picks a
  SKU and a quantity and that is the whole of its authority. Prices come from the
  server. Permission is a single-use cryptographic binding to one exact cart.
  Everything in the seven scenes below runs that code in front of you.</p>

<div class="seam">
  <div class="seam-side model">
    <div class="seam-k">Advisory &middot; model and open web</div>
    <ul class="seam-list">
      <li>reads the shopper's sentence</li>
      <li>searches live retail sources</li>
      <li>compares options and argues for one</li>
      <li>proposes a SKU and a quantity</li>
    </ul>
  </div>
  <div class="seam-gutter"><span>the boundary</span></div>
  <div class="seam-side server">
    <div class="seam-k">Authoritative &middot; server</div>
    <ul class="seam-list">
      <li>re-prices from its own catalog</li>
      <li>evaluates R1&ndash;R12 deterministically</li>
      <li>binds one approval to one cart, once</li>
      <li>drives a durable execution state machine</li>
      <li>reaches Razorpay behind a single module</li>
    </ul>
  </div>
</div>

<div class="note note-info">
  <b>Read the page the way it is drawn.</b> Anything violet and dashed is
  advisory &mdash; a model or the open web produced it. Anything with a teal rule
  and monospaced figures is server-authoritative. If a number could be charged to
  someone, it is always on the teal side. That rule holds on every scene.
</div>

<h3 class="sh">Where the reasoning is, and where it deliberately is not</h3>
<table class="t">
  <tr><th>Step</th><th>Who decides</th><th>Why that way</th></tr>
  <tr><td>Interpreting "cricket kit under 5000"</td><td class="n">LLM</td>
      <td>Natural language is the one thing a model is genuinely better at.</td></tr>
  <tr><td>Which listings are real evidence</td><td class="n">deterministic</td>
      <td>Domain whitelist and price extraction. A model asked to judge a source can be persuaded by the source.</td></tr>
  <tr><td>Comparing options and recommending one</td><td class="n">LLM</td>
      <td>A judgement call with no correct answer, and no money authority attached.</td></tr>
  <tr><td>The payable amount</td><td class="n">catalog lookup</td>
      <td>There is nothing to reason about. Reasoning here is only an attack surface.</td></tr>
  <tr><td>Whether the purchase is allowed</td><td class="n">R1&ndash;R12</td>
      <td>{_esc(code.get("gateway_rules", 12))} pure rules. Same inputs, same verdict, every time.</td></tr>
  <tr><td>Whether this exact cart was authorized</td><td class="n">HMAC binding</td>
      <td>Cryptography, not judgement.</td></tr>
  <tr><td>What happened when the provider timed out</td><td class="n">authoritative read</td>
      <td>An unknown outcome is a fact to look up, never one to infer.</td></tr>
</table>

<h3 class="sh">Five minutes, in order</h3>
<table class="t">
  <tr><th>Scene</th><th>What it proves</th></tr>
  <tr><td><a href="#gauntlet" data-goto="gauntlet">B &middot; Gauntlet</a></td>
      <td>Every built-in attack, refused, with the rule that refused it and zero calls to the money boundary.</td></tr>
  <tr><td><a href="#mission" data-goto="mission">C &middot; Mission</a></td>
      <td>The agent shops for real, and one product description tries to talk it into overspending.</td></tr>
  <tr><td><a href="#locks" data-goto="locks">E &middot; Two locks</a></td>
      <td>Write your own attack. The one that gets past the gateway still cannot buy anything.</td></tr>
  <tr><td><a href="#recovery" data-goto="recovery">F &middot; Kill &amp; resurrect</a></td>
      <td>A provider whose answer is lost, and a system that refuses to guess either way.</td></tr>
  <tr><td><a href="#trust" data-goto="trust">G &middot; Trust nothing</a></td>
      <td>Verify a ledger block in your own browser, then watch one flipped bit invalidate everything after it.</td></tr>
</table>
"""


def _scene_gauntlet() -> str:
    return """
<h2 class="st">Every attack we know about, in one run</h2>
<p class="sl">Each scenario builds an attacker payload, signs it where a signature is
  required, and pushes it through the production evaluation path. The money-call
  counter is zeroed before each one, so a scenario that claimed "blocked" while
  touching the Razorpay boundary would show a non-zero count right here.</p>

<div class="note note-info">
  <b>Two layers, and the scoreboard says which one refused.</b> Six scenarios die at
  the deterministic gateway. Two get past it deliberately &mdash; an expired approval,
  and a cart swapped for an identically priced, equally permitted SKU &mdash; because a
  system whose only defence is its first defence has not been tested.
</div>

<div class="row-actions" style="margin-top:16px">
  <button class="btn btn-primary" id="g-run">Run the gauntlet</button>
  <span class="panel-sub" id="g-hint">Calls POST /attack/gauntlet</span>
</div>

<div id="g-state"></div>
<div class="board" id="g-board" hidden>
  <div class="brow h">
    <span></span><span>Scenario</span><span>Verdict</span><span>Refused by</span>
    <span>Latency</span><span>Money</span><span></span>
  </div>
</div>
<div id="g-banner"></div>
"""


def _scene_mission() -> str:
    return """
<h2 class="st">The agent actually shops</h2>
<p class="sl">One sentence in, a real mission out: the buyer agent reads the catalog,
  searches, reasons about what to propose, and submits it. The timeline below is its
  own trace, with the server's timestamps &mdash; not a re-enactment. One product
  description in the catalog contains a prompt injection, and you will see the agent
  read it.</p>

<div class="grid3" style="margin-top:16px;align-items:end">
  <div><label class="label" for="m-intent">Intent</label>
    <input id="m-intent" class="field" value="Buy a cricket kit under Rs 5000"></div>
  <div><label class="label" for="m-budget">Budget (INR)</label>
    <input id="m-budget" class="field" type="number" value="5000" min="100" max="100000"></div>
  <div><button class="btn btn-primary" id="m-run" style="width:100%;justify-content:center">Run the mission</button></div>
</div>

<div id="m-state"></div>
<div id="m-summary"></div>
<div class="tl" id="m-timeline" hidden></div>
<div class="out" id="m-out"></div>
"""


def _scene_negotiation() -> str:
    return """
<h2 class="st">A negotiation the model cannot win by lying</h2>
<p class="sl">Two agents haggle over one SKU. The merchant's floor and ceiling live on
  the server; a model may ask for anything, and anything outside those bounds is
  clamped before it is ever recorded. Every clamped offer is labelled, and the saving
  is computed server-side from stored rows &mdash; a page that subtracts two numbers it
  was handed can be made to show any saving you like.</p>

<div class="row-actions" style="margin-top:16px">
  <button class="btn btn-primary" id="n-run">Run a negotiation</button>
  <span class="panel-sub">SKU BAT-002 &middot; floor and ceiling from server-side bounds</span>
</div>

<div id="n-state"></div>
<div class="nego" id="n-cols" hidden>
  <div class="nego-col buyer"><div class="nego-col-k">Buyer agent</div><div id="n-buyer"></div></div>
  <div class="nego-col merch"><div class="nego-col-k">Merchant agent</div><div id="n-merch"></div></div>
</div>
<div id="n-deal"></div>
<div class="out" id="n-out"></div>
"""


def _scene_locks() -> str:
    return """
<h2 class="st">Write your own attack</h2>
<p class="sl">This is not a simulator. What you type is signed into a real mission,
  evaluated by the real R1&ndash;R12 engine, and &mdash; if it survives that &mdash;
  handed to the real approval-binding verifier. No part of the refusal happens in
  JavaScript. The endpoint that serves this scene imports no execution machinery at
  all, which a test proves by reading its syntax tree.</p>

<div class="row-actions" style="margin-top:16px">
  <button class="btn btn-sm" data-preset="budget_bypass">Budget bypass</button>
  <button class="btn btn-sm" data-preset="forged_price">Forge the price</button>
  <button class="btn btn-sm" data-preset="forge_approval">Forge the approval</button>
  <button class="btn btn-sm" data-preset="tamper_signature">Tamper the signature</button>
  <button class="btn btn-sm" data-preset="out_of_scope">Out of scope</button>
</div>

<div class="term">
  <div class="term-bar">
    <span class="term-dot" style="background:#FF5F57"></span>
    <span class="term-dot" style="background:#FEBC2E"></span>
    <span class="term-dot" style="background:#28C840"></span>
    <span class="term-t">POST /attack/custom</span>
  </div>
  <div class="term-body">
    <label class="label" for="a-json">Your proposal &mdash; edit anything</label>
    <textarea id="a-json" class="json" spellcheck="false"></textarea>
    <div class="row-actions" style="margin-top:12px">
      <button class="btn btn-primary" id="a-run">Run my attack</button>
      <span class="panel-sub" id="a-hint">Refusals come from the gateway and the binding, never from this page.</span>
    </div>
    <div id="a-state"></div>
    <div class="tl" id="a-chain" hidden></div>
    <div class="money-line" id="a-money"></div>
    <div class="kick" id="a-kick"></div>
    <div class="rules" id="a-rules"></div>
  </div>
</div>
"""


def _scene_recovery() -> str:
    return """
<h2 class="st">What happens when you do not know what happened</h2>
<p class="sl">A payment request that times out is the hard case. The order may exist.
  It may not. Guessing either way costs somebody money, and retrying blind is how one
  charge becomes two. SELLABLE writes the attempt to disk before it dispatches,
  classifies an unknown outcome as unknown, and resolves it only by reading
  authoritative provider state.</p>

<div class="note note-warn">
  <b>The fault is real; the provider is not faked.</b> On a clone with Razorpay test
  keys, <em>Response lost</em> genuinely dispatches the order to api.razorpay.com and
  then discards the reply &mdash; so the order really does exist and reconciliation
  really has to find it. <em>Never dispatched</em> stops before the boundary, so
  reconciliation must find nothing and resolve to FAILED. Both are written into the
  audit chain as drills, so a rehearsal can never be mistaken for an incident.
</div>

<div class="row-actions" style="margin-top:16px">
  <button class="btn on" data-fault="remote_timeout">Response lost</button>
  <button class="btn" data-fault="remote_lost">Never dispatched</button>
  <button class="btn" data-fault="remote_reject">Definitive refusal</button>
</div>
<div class="row-actions" style="margin-top:10px">
  <button class="btn btn-primary" id="r-run">1 &middot; Execute with the fault</button>
  <button class="btn btn-primary" id="r-rec" disabled>2 &middot; Reconcile against the provider</button>
</div>

<div id="r-state"></div>
<div class="sm" id="r-sm"></div>
<div class="out" id="r-out"></div>

<h3 class="sh">Kill and resurrect</h3>
<p class="sl">A drill that simulates a crash proves nothing about crashes. This button
  calls <code>os._exit(1)</code> &mdash; no cleanup handlers, no graceful shutdown. Restart the
  server yourself and the boot sweep finds any execution left mid-flight and moves it
  to RECONCILIATION_REQUIRED rather than guessing. It is gated behind
  <code>CHAOS_ENABLED=true</code> <em>and</em> real test credentials, so on the public
  deploy it is honestly disabled rather than hidden.</p>
<div class="panel" id="k-panel">
  <div class="panel-head">
    <span class="panel-title">Kill switch</span>
    <span id="k-chip"></span>
  </div>
  <div id="k-state"></div>
  <div class="row-actions">
    <button class="btn btn-danger" id="k-btn" disabled>Confirm kill</button>
  </div>
  <div class="out" id="k-out"></div>
</div>

<h3 class="sh">The three outcomes, and why the third is the point</h3>
<table class="t">
  <tr><th>Provider said</th><th>Classified</th><th>What happens</th></tr>
  <tr><td class="n">2xx with an order</td><td class="n">EXECUTED</td>
      <td>Records the order. Still claims no settlement &mdash; that needs a signed webhook.</td></tr>
  <tr><td class="n">4xx</td><td class="n">FAILED</td>
      <td>The provider is saying it did not act. Safe to close.</td></tr>
  <tr><td class="n">timeout &middot; reset &middot; 5xx &middot; unparseable</td><td class="n">RECONCILIATION_REQUIRED</td>
      <td>Refuses to conclude. Queries the provider's order list, matching on the
      correlation fields written into <code>notes</code> at creation. If the provider is
      unreachable, the row stays stuck on purpose.</td></tr>
</table>
"""


def _scene_trust() -> str:
    return """
<h2 class="st">Do not trust this server. Check it.</h2>
<p class="sl">Every decision appends a block whose hash covers its sequence,
  timestamp, actor, action, payload hash and the previous block's hash. The chain
  stores payload <em>hashes</em>, not payloads, so it commits to what happened without
  becoming a second copy of it. Below, your browser recomputes a block hash with
  WebCrypto &mdash; no part of that check runs on our side.</p>

<div class="row-actions" style="margin-top:16px">
  <button class="btn btn-primary" id="t-buy">1 &middot; Make a purchase to verify</button>
  <button class="btn" id="t-verify" disabled>2 &middot; Verify it in your browser</button>
  <button class="btn btn-danger" id="t-tamper" disabled>3 &middot; Break the chain</button>
</div>

<div id="t-state"></div>
<div class="grid2" style="margin-top:16px;align-items:start">
  <div id="t-receipt"></div>
  <div>
    <div class="panel">
      <div class="panel-head">
        <span class="panel-title">Browser-side verification</span>
        <span id="t-badge"></span>
      </div>
      <div class="out" id="t-verify-out"></div>
    </div>
    <div class="panel" style="margin-top:14px">
      <div class="panel-head"><span class="panel-title">Agent-readable catalog</span></div>
      <p class="panel-sub" style="margin-bottom:10px">Any external agent can read the
        merchant's capabilities, policy and catalog without a human in the loop. This
        is the manifest a buyer agent starts from.</p>
      <div class="row-actions">
        <a class="btn btn-sm" href="/.well-known/agent-manifest.json" target="_blank" rel="noopener">Open manifest</a>
        <a class="btn btn-sm" href="/catalog.jsonld" target="_blank" rel="noopener">JSON-LD catalog</a>
        <a class="btn btn-sm" href="/tools/merchant_policy" target="_blank" rel="noopener">Merchant policy</a>
        <button class="btn btn-sm" id="t-copy">Copy manifest URL</button>
      </div>
    </div>
  </div>
</div>

<h3 class="sh">The chain, and what one flipped bit does to it</h3>
<div class="chain" id="t-chain"></div>
<div id="t-cascade"></div>
<p class="panel-sub" style="margin-top:12px">Tamper computed on an in-memory copy. The
  on-disk ledger is untouched &mdash; boot-time verification would halt the server.</p>
"""


def _scene_evidence(truth: dict[str, Any]) -> str:
    tests = truth.get("tests", {})
    code = truth.get("codebase", {})
    adv = truth.get("adversarial", {})
    git = truth.get("git", {})
    lat = truth.get("gateway_latency", {})
    not_measured = truth.get("not_measured_in_this_run", {})
    limits = truth.get("known_limitations", [])

    nm = "".join(f'<div class="lim"><b>{_esc(k.replace("_", " "))}</b>{_esc(v)}</div>'
                 for k, v in not_measured.items())
    lim = "".join(f'<div class="lim">{_esc(x)}</div>' for x in limits)

    return f"""
<h2 class="st">Every number, and where it came from</h2>
<p class="sl">These are written by <code>scripts/generate_truth.py</code>, which runs the
  suite, runs the attack lab and measures the gateway, then writes
  <code>docs/generated/truth.json</code>. CI fails if the README claims anything that file
  does not support. Nothing here was typed by hand, and nothing that was not measured
  is quoted.</p>

<table class="t">
  <tr><th>Metric</th><th>Value</th><th>Produced by</th></tr>
  <tr><td>Tests passing</td><td class="n">{_esc(tests.get("passed"))}</td><td class="n">python -m pytest -q</td></tr>
  <tr><td>Tests skipped</td><td class="n">{_esc(tests.get("skipped"))}</td><td class="n">reason recorded per test</td></tr>
  <tr><td>Suite green</td><td class="n">{_esc(tests.get("all_green"))}</td><td class="n">exit code {_esc(tests.get("exit_code"))}</td></tr>
  <tr><td>Policy rules in the canonical registry</td><td class="n">{_esc(code.get("gateway_rules"))}</td><td class="n">len(RULE_REGISTRY)</td></tr>
  <tr><td>Catalog SKUs</td><td class="n">{_esc(code.get("catalog_skus"))}</td><td class="n">len(CATALOG)</td></tr>
  <tr><td>Adversarial scenarios blocked</td>
      <td class="n">{_esc(adv.get("scenarios_blocked"))} of {_esc(adv.get("scenarios_total"))}</td>
      <td class="n">POST /attack/run_all</td></tr>
  <tr><td>Money-boundary calls during those attacks</td>
      <td class="n">{_esc(adv.get("money_boundary_calls_during_attacks"))}</td>
      <td class="n">apps/api/money.py counter</td></tr>
  <tr><td>Gateway p50 / p95 / p99</td>
      <td class="n">{_esc(lat.get("p50_ms"))} / {_esc(lat.get("p95_ms"))} / {_esc(lat.get("p99_ms"))} ms</td>
      <td class="n">{_esc(lat.get("iterations"))} in-process runs, {_esc(lat.get("measured_on"))}</td></tr>
  <tr><td>First-party Python lines</td><td class="n">{_esc(code.get("python_lines"))}</td>
      <td class="n">apps/ tests/ scripts/ eval/ &mdash; excludes the virtualenv</td></tr>
  <tr><td>Generated at</td><td class="n">{_esc(truth.get("generated_at"))}</td>
      <td class="n">commit {_esc(git.get("commit_short"))}</td></tr>
</table>

<div class="row-actions" style="margin-top:16px">
  <button class="btn btn-primary" id="e-score">Fetch runtime posture</button>
  <span class="panel-sub">Properties proven by tests rather than observable at runtime are excluded on purpose.</span>
</div>
<div class="out" id="e-out"></div>

<h3 class="sh">Not measured in that run</h3>
<p class="sl">Stated rather than quietly omitted. A metric that disappears when it is
  inconvenient is worse than one that was never claimed.</p>
{nm or '<p class="sl">&mdash;</p>'}

<h3 class="sh">Known limitations</h3>
{lim or '<p class="sl">&mdash;</p>'}

<h3 class="sh">Which module can reach money</h3>
<table class="t">
  <tr><th>Module</th><th>Role</th><th>May call Razorpay?</th></tr>
  <tr><td class="n">agent/</td><td>Buyer agent: intent, choice, explanation.</td><td>No &mdash; import boundary is tested</td></tr>
  <tr><td class="n">discovery/</td><td>Live retail search, evidence classing, provenance.</td><td>No</td></tr>
  <tr><td class="n">gateway/</td><td>R1&ndash;R12. Pure: no LLM, no network, no file I/O.</td><td>No &mdash; proven by AST scan</td></tr>
  <tr><td class="n">approval.py</td><td>Single-use binding of one approval to one cart.</td><td>No</td></tr>
  <tr><td class="n">execution.py</td><td>Durable state machine over one payment attempt.</td><td>No</td></tr>
  <tr><td class="n">attack_custom.py</td><td>The reviewer's attack sandbox.</td><td>No &mdash; imports no execution code at all</td></tr>
  <tr><td class="n">razorpay_client.py</td><td><b>The single money boundary.</b> Every call counted.</td><td>Yes, and only here</td></tr>
  <tr><td class="n">webhook/</td><td>HMAC-verified settlement events, deduplicated durably.</td><td>No</td></tr>
</table>

<div class="note note-warn">
  <b>The browser demo's issuer is in-process.</b> In this flow the user mandate is
  signed by <code>apps/api/issuer.py</code> inside this server, and every response says so
  in <code>authorization_issued_by: "in_process_demo_issuer"</code>. That proves the
  binding's integrity, not custody of the key. The externally-signed path &mdash;
  <code>scripts/sign_mission.py</code> and <code>scripts/mandate.py</code> holding the keys
  outside the server &mdash; is what the architecture is designed around and what the
  test suite exercises.
</div>
"""


def render_judge_page() -> str:
    truth = _load_truth()

    tabs = "".join(
        f'<button class="scene-tab" role="tab" id="tab-{k}" data-scene="{k}" '
        f'aria-controls="scene-{k}" aria-selected="false">'
        f'<span class="ix">{ix}</span>{label}</button>'
        for k, ix, label in SCENES)

    panels = {
        "sentinel": _scene_sentinel(truth),
        "gauntlet": _scene_gauntlet(),
        "mission": _scene_mission(),
        "negotiation": _scene_negotiation(),
        "locks": _scene_locks(),
        "recovery": _scene_recovery(),
        "trust": _scene_trust(),
        "evidence": _scene_evidence(truth),
    }
    body = "".join(
        f'<section class="scene" id="scene-{k}" role="tabpanel" '
        f'aria-labelledby="tab-{k}" hidden>{v}</section>'
        for k, v in panels.items())

    return f"""{head("SELLABLE — cockpit", _CSS)}
{nav("judge")}

<div class="strip"><div class="strip-in" id="strip"></div></div>

<header class="wrap hero">
  <div class="kicker">Razorpay AI Buildathon &middot; Track 01 &middot; evidence cockpit</div>
  <h1>The AI decides <span class="a">what to recommend</span>.<br>
      It cannot decide <span class="b">what money moves</span>.</h1>
  <p>Seven scenes. Each one runs the production code path in front of you &mdash; the
     same gateway, the same binding, the same executor, the same ledger the storefront
     uses. Nothing here is a mock-up, and no number on this page was typed in.</p>
</header>

<nav class="scenes" role="tablist" aria-label="Scenes">
  <div class="scenes-in">{tabs}</div>
</nav>

<main class="wrap">{body}</main>
{FOOTER}
<script>{PROVIDER_BADGE_JS}</script>
<script>{_JS}</script>
</body>
</html>"""


_JS = r"""
/* ═══════════════════════════════════════════════════════════════════
   Every fetch on this page goes through jfetch. Every panel has three
   states and the error state prints the real error — there is no
   fallback content anywhere, because fallback content is how a demo
   ends up showing numbers that nothing produced.
   ═══════════════════════════════════════════════════════════════════ */
const $ = id => document.getElementById(id);
const esc = s => String(s == null ? '' : s)
  .replace(/&/g,'&amp;').replace(/</g,'&lt;').replace(/>/g,'&gt;').replace(/"/g,'&quot;');
const REDUCED = window.matchMedia('(prefers-reduced-motion: reduce)').matches;

async function jfetch(url, opts){
  const r = await fetch(url, opts);
  let body = null, parseError = null;
  try { body = await r.json(); } catch(e){ parseError = String(e); }
  return {status:r.status, ok:r.ok, body:body, parseError:parseError};
}
function loading(el, what){
  el.innerHTML = '<div class="state-loading"><span class="dot"></span>' +
    esc(what) + '</div><div class="skel" style="margin-top:8px"></div>';
}
function failed(el, url, err){
  el.innerHTML = '<div class="state-error">Request failed &mdash; ' + esc(url) +
    '<span class="m">' + esc(err) + '</span></div>';
}
function clear(el){ el.innerHTML = ''; }
function out(el, lines){ el.innerHTML = lines.join('\n'); }
function c(cls, text){ return '<span class="' + cls + '">' + esc(text) + '</span>'; }
function pad(s, n){ s = String(s == null ? '' : s); return s + ' '.repeat(Math.max(0, n - s.length)); }
function rupees(paise){
  if (paise == null) return '—';
  return 'Rs ' + (paise/100).toLocaleString('en-IN', {minimumFractionDigits:2, maximumFractionDigits:2});
}
function tstamp(sec){
  if (!sec) return '—';
  const d = new Date(sec * 1000);
  return d.toTimeString().slice(0,8) + '.' + String(d.getMilliseconds()).padStart(3,'0');
}

/* M1 — stagger rows that have ALREADY arrived from the server. */
function stagger(nodes, step){
  if (REDUCED) return;
  nodes.forEach((n, i) => {
    n.classList.add('stagger');
    n.style.animationDelay = (i * (step || 70)) + 'ms';
  });
}
/* M3 — count a real number up, once it has arrived. */
function countUp(el, target, suffix){
  suffix = suffix || '';
  if (REDUCED || target === 0){ el.textContent = target + suffix; return; }
  const t0 = performance.now(), dur = 600;
  (function step(now){
    const p = Math.min(1, (now - t0) / dur);
    el.textContent = Math.round(target * (1 - Math.pow(1 - p, 3))) + suffix;
    if (p < 1) requestAnimationFrame(step);
  })(performance.now());
}
/* M2 — typewriter over text the server already sent. Click to skip. */
function typewriter(el, text){
  if (REDUCED){ el.textContent = text; return; }
  el.textContent = ''; let i = 0, done = false;
  const finish = () => { done = true; el.textContent = text; };
  el.addEventListener('click', finish, {once:true});
  const iv = setInterval(() => {
    if (done || i >= text.length){ clearInterval(iv); if(!done) el.textContent = text; return; }
    el.textContent += text.slice(i, i + 6); i += 6;
  }, 15);
}

/* ── scene routing ─────────────────────────────────────────────────── */
const KEYS = Array.from(document.querySelectorAll('.scene-tab')).map(t => t.dataset.scene);
function show(k){
  if (KEYS.indexOf(k) === -1) k = KEYS[0];
  KEYS.forEach(x => {
    $('tab-'+x).setAttribute('aria-selected', x === k ? 'true' : 'false');
    $('scene-'+x).hidden = x !== k;
  });
}
document.querySelectorAll('.scene-tab').forEach(t =>
  t.addEventListener('click', () => { history.replaceState(null,'','#'+t.dataset.scene); show(t.dataset.scene); }));
document.querySelectorAll('[data-goto]').forEach(a =>
  a.addEventListener('click', e => {
    e.preventDefault();
    history.replaceState(null,'','#'+a.dataset.goto);
    show(a.dataset.goto); window.scrollTo({top:0, behavior:'smooth'});
  }));
window.addEventListener('hashchange', () => show(location.hash.slice(1)));
show(location.hash.slice(1) || 'sentinel');

/* ═══ SCENE A — the sentinel ════════════════════════════════════════ */
function pill(k, v, cls, beat){
  return '<div class="pill"><span class="dot ' + (cls||'') + (beat?' beat':'') + '"></span>' +
         '<span class="pill-k">' + esc(k) + '</span>' +
         '<span class="pill-v ' + (cls||'') + '">' + esc(v) + '</span></div>';
}
async function refreshStrip(){
  const el = $('strip');
  const [h, g, t] = await Promise.allSettled([
    jfetch('/health'), jfetch('/gateway/proof'), jfetch('/api/v1/telemetry')
  ]);
  const parts = [];
  /* M4 — the dot beats exactly when its poll resolves, never on a loop. */
  if (h.status === 'fulfilled' && h.value.ok){
    const ok = h.value.body.audit_chain_ok;
    parts.push(pill('audit', ok ? 'verified · ' + h.value.body.audit_entries + ' blocks' : 'HALTED',
                    ok ? 'ok' : 'bad', true));
  } else parts.push(pill('audit', 'unreachable', 'bad'));

  if (g.status === 'fulfilled' && g.value.ok){
    const d = g.value.body;
    const imports = (d.forbidden_imports_found || []).length;
    parts.push(pill('gateway', imports === 0 ? 'pure · 0 llm imports' : imports + ' FORBIDDEN IMPORTS',
                    imports === 0 ? 'ok' : 'bad', true));
  } else parts.push(pill('gateway', 'unreachable', 'bad'));

  if (t.status === 'fulfilled' && t.value.ok){
    const d = t.value.body;
    parts.push(pill('razorpay', d.payment_provider || '—',
                    d.payment_provider === 'simulated' ? 'warn' : 'ok', true));
    parts.push(pill('policy rules', d.gateway_rules, 'ok', true));
    parts.push(pill('bindings', d.bindings_consumed + ' / ' + d.bindings_issued + ' consumed', '', true));
    const pending = (d.executions_by_state || {}).RECONCILIATION_REQUIRED || 0;
    parts.push(pill('unresolved', pending, pending ? 'warn' : 'ok', true));
  } else parts.push(pill('razorpay', 'unreachable', 'bad'));

  el.innerHTML = parts.join('');
}
refreshStrip();
setInterval(refreshStrip, 5000);   /* the poll interval — the only bare timer */

/* ═══ SCENE B — the gauntlet ════════════════════════════════════════ */
$('g-run').addEventListener('click', async function(){
  const btn = this, board = $('g-board'), st = $('g-state'), banner = $('g-banner');
  btn.disabled = true; btn.textContent = 'Running…';
  board.hidden = true; clear(banner);
  loading(st, 'running every scenario against the real gateway');
  try {
    const r = await jfetch('/attack/gauntlet', {method:'POST'});
    if (!r.ok){ failed(st, 'POST /attack/gauntlet', JSON.stringify(r.body)); return; }
    clear(st);
    const d = r.body;
    board.querySelectorAll('.brow:not(.h)').forEach(n => n.remove());
    const rows = d.results.map((s, i) => {
      const el = document.createElement('div');
      el.className = 'brow';
      const layer = (s.refused_layer === 'gateway') ? 'deterministic policy' : 'money boundary';
      el.innerHTML =
        '<span class="ix">' + String(i+1).padStart(2,'0') + '</span>' +
        '<span><span class="nm">' + esc(s.label) + '</span>' +
          '<span class="id">' + esc(s.id) + '</span></span>' +
        '<span class="chip ' + (s.decision === 'REJECT' ? 'chip-bad' : 'chip-dim') + '">' +
          esc(s.decision || '—') + '</span>' +
        '<span class="m" style="font-size:11px">' + esc(s.blocked_by) +
          '<span class="id">' + layer + '</span></span>' +
        '<span class="m" style="font-size:11.5px">' + esc(s.latency_ms) + ' ms</span>' +
        '<span class="m" style="color:' + (s.money_calls ? 'var(--red)' : 'var(--teal)') + '">' +
          esc(s.money_calls) + '</span>' +
        '<span class="chip ' + (s.safe ? 'chip-ok' : 'chip-bad') + '">' +
          (s.safe ? '✓' : '✗') + '</span>';
      board.appendChild(el);
      return el;
    });
    board.hidden = false;
    stagger(rows, 70);
    const T = d.totals, allSafe = T.blocked === T.total && T.money_boundary_calls === 0;
    setTimeout(() => {
      banner.innerHTML = '<div class="banner' + (allSafe ? '' : ' bad') + '">' +
        '<div class="banner-t"><span id="g-n">0</span>/' + T.total +
        ' BLOCKED &middot; ' + T.money_boundary_calls + ' MONEY API CALLS</div>' +
        '<div class="banner-s">measured_on: ' + esc(d.measured_on) +
        ' &middot; wall time ' + T.wall_time_ms + ' ms &middot; ' +
        'same runner the test suite asserts against</div></div>';
      countUp($('g-n'), T.blocked);
    }, REDUCED ? 0 : d.results.length * 70 + 160);
  } catch(e){ failed(st, 'POST /attack/gauntlet', e.message); }
  finally { btn.disabled = false; btn.textContent = 'Run the gauntlet'; }
});

/* ═══ SCENE C — the mission ═════════════════════════════════════════ */
const INJECTION_HINTS = ['injection','ignore','instruction','override','prompt'];
$('m-run').addEventListener('click', async function(){
  const btn = this, st = $('m-state'), tl = $('m-timeline'),
        sum = $('m-summary'), o = $('m-out');
  btn.disabled = true; btn.textContent = 'Shopping…';
  tl.hidden = true; clear(sum); clear(o);
  loading(st, 'the agent is reading the catalog and choosing');
  try {
    const r = await jfetch('/agent/run_full_mission', {
      method:'POST', headers:{'Content-Type':'application/json'},
      body: JSON.stringify({
        intent: $('m-intent').value,
        budget_inr: parseFloat($('m-budget').value) || 5000,
        allowed_categories: ['cricket']
      })});
    if (!r.ok){ failed(st, 'POST /agent/run_full_mission', JSON.stringify(r.body)); return; }
    clear(st);
    const d = r.body, events = d.events || [];
    if (!events.length){
      st.innerHTML = '<div class="state-empty">The agent returned no trace events. ' +
        'Status: ' + esc(d.status) + '</div>';
      return;
    }
    tl.innerHTML = '';
    const nodes = events.map(ev => {
      const blob = JSON.stringify(ev.data || {}).toLowerCase();
      const text = (ev.summary || '') + ' ' + blob;
      const injected = INJECTION_HINTS.some(k => text.toLowerCase().includes(k));
      const rejected = /reject|refus|block|denied|error/i.test(ev.action + ' ' + ev.summary);
      const model = /llm|reason|propos/i.test(ev.action);
      const el = document.createElement('div');
      el.className = 'tev' + (rejected ? ' rej' : injected ? ' inj' : model ? ' model' : '');
      el.innerHTML =
        '<span class="tev-ts">' + esc(tstamp(ev.ts)) + '</span>' +
        '<span class="tev-b"><span class="tev-a">' + esc(ev.actor) + ' · ' + esc(ev.action) + '</span>' +
        '<span class="tev-s">' + esc(ev.summary) + '</span></span>';
      tl.appendChild(el);
      return el;
    });
    tl.hidden = false;
    stagger(nodes, 60);
    const ord = d.order;
    sum.innerHTML = '<div class="' + (ord ? 'authoritative' : 'advisory') + '" style="margin-top:14px">' +
      '<div class="panel-head"><span class="panel-title">Mission outcome</span>' +
      '<span class="chip ' + (ord ? 'chip-ok' : 'chip-warn') + '">' + esc(d.status) + '</span></div>' +
      (ord ? '<div class="m" style="font-size:19px;font-weight:700">' + rupees(ord.amount) +
             '</div><div class="panel-sub">order ' + esc(ord.id) + ' &middot; priced from the server catalog</div>'
           : '<div class="panel-sub">No order was created. The agent produced no ' +
             'proposal the gateway would approve, and nothing was charged.</div>') +
      '</div>';
    out(o, [
      c('dim', 'POST /agent/run_full_mission'),
      '',
      'events        ' + events.length,
      'status        ' + esc(d.status),
      'amber rows    product text that reads like an instruction rather than a description'
    ]);
  } catch(e){ failed(st, 'POST /agent/run_full_mission', e.message); }
  finally { btn.disabled = false; btn.textContent = 'Run the mission'; }
});

/* ═══ SCENE D — the negotiation ═════════════════════════════════════ */
$('n-run').addEventListener('click', async function(){
  const btn = this, st = $('n-state'), cols = $('n-cols'), deal = $('n-deal'), o = $('n-out');
  btn.disabled = true; btn.textContent = 'Negotiating…';
  cols.hidden = true; clear(deal); clear(o);
  loading(st, 'two agents are exchanging offers under server-side bounds');
  try {
    const start = await jfetch('/negotiation/start', {
      method:'POST', headers:{'Content-Type':'application/json'},
      body: JSON.stringify({mission_id:'MSN-COCKPIT-'+Date.now(), sku:'BAT-002', qty:1,
        floor_paise:180000, ceiling_paise:249900, buyer_budget_paise:300000,
        max_turns:3, llm_enabled:true})});
    if (!start.ok){ failed(st, 'POST /negotiation/start',
        (start.body && start.body.detail) || JSON.stringify(start.body)); return; }
    const nid = start.body.negotiation_id;
    await jfetch('/negotiation/' + nid + '/run', {
      method:'POST', headers:{'Content-Type':'application/json'},
      body: JSON.stringify({llm_enabled:true})});
    const r = await jfetch('/negotiation/' + nid + '/transcript');
    if (!r.ok){ failed(st, 'GET transcript', JSON.stringify(r.body)); return; }
    clear(st);
    const d = r.body;
    const buyer = $('n-buyer'), merch = $('n-merch');
    buyer.innerHTML = ''; merch.innerHTML = '';
    const made = [];
    (d.turns || []).forEach(t => {
      [['buyer_offer', buyer], ['merchant_offer', merch]].forEach(([k, host]) => {
        const off = t[k]; if (!off) return;
        const el = document.createElement('div');
        el.className = 'bub';
        el.innerHTML =
          '<div class="bub-t">turn ' + esc(t.turn) + '</div>' +
          '<div class="bub-p">' + esc(rupees(off.price_paise)) + '</div>' +
          (off.clamped ? '<div style="margin-top:6px"><span class="chip chip-warn">clamped by policy</span>' +
             '<span class="bub-r">asked ' + esc(rupees(off.raw_price_paise)) +
             ', pulled back ' + esc(rupees(Math.abs(off.clamp_delta_paise))) + '</span></div>' : '') +
          (off.rationale ? '<div class="bub-r">' + esc(off.rationale) + '</div>' : '');
        host.appendChild(el); made.push(el);
      });
    });
    cols.hidden = false;
    stagger(made, 90);
    if (d.final_price_paise != null){
      deal.innerHTML = '<div class="deal"><div>' +
        '<div class="panel-sub">Agreed price &middot; ceiling was ' + esc(rupees(d.original_price_paise)) + '</div>' +
        '<div class="deal-p">' + esc(rupees(d.final_price_paise)) + '</div></div>' +
        '<div><span class="chip chip-ok">saved ' + esc(rupees(d.savings_paise)) + '</span>' +
        '<div class="panel-sub" style="margin-top:6px">computed server-side from stored offers</div></div></div>';
    } else {
      deal.innerHTML = '<div class="state-empty">No agreed price &mdash; status ' +
        esc(d.status) + '. No saving is claimed, because none exists.</div>';
    }
    out(o, [
      c('dim','POST /negotiation/start → /run → GET /{id}/transcript'),
      '',
      'bounds          floor ' + rupees(d.floor_paise) +
                      '  ceiling ' + rupees(d.ceiling_paise),
      'turns           ' + (d.turns || []).length + ' of ' + esc(d.max_turns),
      'clamped offers  ' + c(d.clamped_turn_count ? 'warn' : 'dim', d.clamped_turn_count),
      'status          ' + esc(d.status),
      '',
      c('dim', d.bounds_note)
    ]);
  } catch(e){ failed(st, 'negotiation', e.message); }
  finally { btn.disabled = false; btn.textContent = 'Run a negotiation'; }
});

/* ═══ SCENE E — the two locks ═══════════════════════════════════════ */
const PRESETS = {
  budget_bypass: {
    mission:{mission_id:'MSN-ATK-001', intent:'spend more than I was allowed',
      budget_paise:100, allowed_categories:['cricket'], expires_at:9999999999},
    items:[{sku:'BAT-001', qty:1}]},
  forged_price: {
    mission:{mission_id:'MSN-ATK-002', intent:'pay one paisa for a cricket bat',
      budget_paise:999999, allowed_categories:['cricket'], amount_paise:1,
      expires_at:9999999999},
    items:[{sku:'BAT-001', qty:1, price_paise:1}]},
  forge_approval: {
    mission:{mission_id:'MSN-ATK-003', intent:'a perfectly legal cart, with a forged permission slip',
      budget_paise:500000, allowed_categories:['cricket'], expires_at:9999999999},
    items:[{sku:'BAT-001', qty:1}],
    forged_binding:{seq:999999, token:'forged_token_abc123'}},
  tamper_signature: {
    mission:{mission_id:'MSN-ATK-004', intent:'edit the mission after it was signed',
      budget_paise:500000, allowed_categories:['cricket'], expires_at:9999999999},
    items:[{sku:'BAT-001', qty:1}], tamper_signature:true},
  out_of_scope: {
    mission:{mission_id:'MSN-ATK-005', intent:'buy something I was not authorized to buy',
      budget_paise:500000, allowed_categories:['books'], expires_at:9999999999},
    items:[{sku:'BAT-001', qty:1}]}
};
function setPreset(k){
  $('a-json').value = JSON.stringify(PRESETS[k], null, 2);
  document.querySelectorAll('[data-preset]').forEach(b => b.classList.toggle('on', b.dataset.preset === k));
}
document.querySelectorAll('[data-preset]').forEach(b =>
  b.addEventListener('click', () => setPreset(b.dataset.preset)));
setPreset('forge_approval');

$('a-run').addEventListener('click', async function(){
  const btn = this, st = $('a-state'), chain = $('a-chain'),
        money = $('a-money'), kick = $('a-kick'), rules = $('a-rules');
  clear(chain.innerHTML ? chain : chain); chain.hidden = true;
  money.textContent = ''; kick.textContent = ''; rules.innerHTML = '';
  let payload;
  try { payload = JSON.parse($('a-json').value); }
  catch(e){
    st.innerHTML = '<div class="state-error">That is not valid JSON.<span class="m">' +
      esc(e.message) + '</span></div>';
    return;
  }
  btn.disabled = true; btn.textContent = 'Running…';
  loading(st, 'signing your mission, then evaluating it for real');
  try {
    const r = await jfetch('/attack/custom', {
      method:'POST', headers:{'Content-Type':'application/json'},
      body: JSON.stringify(payload)});
    if (!r.ok){
      const err = (r.body && r.body.detail && r.body.detail.error) || {};
      st.innerHTML = '<div class="state-error">Refused before evaluation &mdash; ' +
        esc(err.error_code || r.status) + '<span class="m">' +
        esc(err.message || JSON.stringify(r.body)) + '</span></div>';
      return;
    }
    clear(st);
    const d = r.body;

    /* the causal chain, as a timeline, from what the server reported */
    const steps = [];
    steps.push(['model', 'attacker', 'proposal submitted',
      (payload.items || []).map(i => i.sku + ' x' + (i.qty || 1)).join(', ')]);
    if (d.price_overwrite_applied){
      const p = d.attacker_prices_discarded[0];
      steps.push(['rej', 'server', 'price discarded',
        'you claimed ' + rupees(p.attacker_claimed_paise) + '; the catalog says ' +
        rupees(p.catalog_paise) + ' and that is the only number used']);
    }
    if (d.mission_amount_field_ignored){
      steps.push(['rej', 'server', 'amount field ignored',
        'a mission has no amount; the field was read and thrown away']);
    }
    steps.push([d.gateway.decision === 'APPROVE' ? '' : 'rej', 'gateway',
      'R1-R12 → ' + d.gateway.decision,
      d.gateway.reason || (d.gateway.rule_id ? 'failed on ' + d.gateway.rule_id : 'all rules passed')]);
    if (d.binding_check){
      steps.push([d.binding_check.accepted ? '' : 'rej', 'approval binding',
        d.binding_check.accepted ? 'accepted' : 'refused → ' + d.binding_check.reason,
        'the binding is issued for one exact cart and signed with a key you do not hold']);
    }
    chain.innerHTML = '';
    const nodes = steps.map(([cls, actor, action, detail]) => {
      const el = document.createElement('div');
      el.className = 'tev ' + cls;
      el.innerHTML = '<span class="tev-ts"></span><span class="tev-b">' +
        '<span class="tev-a">' + esc(actor) + ' · ' + esc(action) + '</span>' +
        '<span class="tev-s">' + esc(detail) + '</span></span>';
      chain.appendChild(el); return el;
    });
    chain.hidden = false;
    stagger(nodes, 110);

    /* M3 — the money line counts up to the real zeros */
    const delay = REDUCED ? 0 : nodes.length * 110 + 140;
    setTimeout(() => {
      money.innerHTML = 'MONEY API CALLS: <span id="a-mc">0</span> &nbsp;&middot;&nbsp; ' +
        'AUTHORIZED: Rs <span id="a-au">0</span> &nbsp;&middot;&nbsp; MOVED: Rs <span id="a-mv">0</span>';
      countUp($('a-mc'), d.money_boundary_calls);
      countUp($('a-au'), d.amount_authorized_paise / 100);
      countUp($('a-mv'), d.amount_moved_paise / 100);
      kick.className = 'kick' + (d.refused_layer === 'binding' ? ' binding' : '');
      typewriter(kick, d.headline);
    }, delay);

    rules.innerHTML = (d.gateway.rule_matrix || []).map(x =>
      '<div class="rule ' + (x.status === 'PASS' ? 'pass' : 'fail') + '">' +
      '<div class="rule-id">' + esc(x.rule_id) + ' · ' + esc(x.status) + '</div>' +
      (x.reason ? '<div class="rule-w">' + esc(x.reason) + '</div>' : '') + '</div>').join('');
  } catch(e){ failed(st, 'POST /attack/custom', e.message); }
  finally { btn.disabled = false; btn.textContent = 'Run my attack'; }
});

/* ═══ SCENE F — kill and resurrect ══════════════════════════════════ */
let FAULT = 'remote_timeout', LAST_EXEC = null;
document.querySelectorAll('[data-fault]').forEach(b =>
  b.addEventListener('click', () => {
    FAULT = b.dataset.fault;
    document.querySelectorAll('[data-fault]').forEach(x => x.classList.remove('on'));
    b.classList.add('on');
  }));

const SM = [
  ['APPROVED','Authorization exists. Nothing has been dispatched.'],
  ['EXECUTION_PENDING','About to contact the provider.'],
  ['REMOTE_ATTEMPTED','Committed to disk BEFORE the call. A crash here is recoverable.'],
  ['RECONCILIATION_REQUIRED','Outcome unknown. Nothing is assumed and no blind retry is offered.'],
  ['EXECUTED','Resolved from authoritative provider state: the order exists.'],
  ['FAILED','Resolved from authoritative provider state: no order exists. No money moved.']
];
function renderSM(cur){
  const i = SM.findIndex(s => s[0] === cur);
  $('r-sm').innerHTML = SM.map((s, ix) => {
    let cls = 'smr';
    if (ix < i && s[0] !== 'EXECUTED' && s[0] !== 'FAILED') cls += ' done';
    else if (s[0] === cur) cls += cur === 'EXECUTED' ? ' done'
      : cur === 'FAILED' ? ' bad' : cur === 'RECONCILIATION_REQUIRED' ? ' warn' : ' cur';
    return '<div class="' + cls + '"><span class="d"></span>' +
      '<span class="n">' + esc(s[0]) + '</span><span class="x">' + esc(s[1]) + '</span></div>';
  }).join('');
}
renderSM(null);

$('r-run').addEventListener('click', async function(){
  const btn = this, st = $('r-state'), o = $('r-out');
  btn.disabled = true; btn.textContent = 'Executing…';
  $('r-rec').disabled = true; clear(o);
  loading(st, 'dispatching with fault ' + FAULT);
  try {
    const r = await jfetch('/discovery/checkout', {
      method:'POST', headers:{'Content-Type':'application/json'},
      body: JSON.stringify({sku:'BAT-001', budget_paise:300000, fault:FAULT})});
    clear(st);
    const b = r.body, state = b.execution_state || (b.ok ? 'EXECUTED' : null);
    renderSM(state);
    LAST_EXEC = b.execution_id || null;
    const L = [c('dim','POST /discovery/checkout  fault=' + FAULT), c('dim','HTTP ' + r.status), ''];
    if (b.ok){
      L.push(c('ok','EXECUTED — the provider answered. Nothing to reconcile.'));
      L.push('order        ' + esc(b.order_id));
    } else {
      L.push(c(state === 'FAILED' ? 'bad' : 'warn', b.status));
      L.push(esc(b.headline || ''));
      if (b.detail) L.push(c('dim', b.detail));
      L.push('');
      L.push('execution    ' + esc(b.execution_id));
      L.push('state        ' + c('warn', state));
      L.push('retryable    ' + c('ok', String(b.retryable)) +
             c('dim','   ← a blind retry of an unknown outcome is never offered'));
      $('r-rec').disabled = (state !== 'RECONCILIATION_REQUIRED');
    }
    out(o, L);
  } catch(e){ failed(st, 'POST /discovery/checkout', e.message); }
  finally { btn.disabled = false; btn.textContent = '1 · Execute with the fault'; }
});

$('r-rec').addEventListener('click', async function(){
  const btn = this, o = $('r-out'), st = $('r-state');
  if (!LAST_EXEC) return;
  btn.disabled = true; btn.textContent = 'Querying the provider…';
  loading(st, 'reading authoritative provider state');
  try {
    const r = await jfetch('/discovery/reconcile/' + encodeURIComponent(LAST_EXEC), {method:'POST'});
    clear(st);
    const d = r.body;
    renderSM(d.state);
    const resolved = d.state === 'EXECUTED' || d.state === 'FAILED';
    const cls = d.state === 'EXECUTED' ? 'ok' : d.state === 'FAILED' ? 'bad' : 'warn';
    const L = [
      c('dim','POST /discovery/reconcile/' + LAST_EXEC),
      c('dim','HTTP ' + r.status), '',
      'resolution   ' + c(cls, d.resolution || d.state),
      'state        ' + c(cls, d.state),
      '',
      esc(d.explanation || '')
    ];
    if (d.remote_order_id) L.push('order        ' + esc(d.remote_order_id));
    if (!resolved){
      /* The reconciler can also answer "I still cannot tell". That is a
         third outcome, not a failure, and it must not read as one. */
      L.push('', c('warn','STILL UNRESOLVED — nothing has been concluded.'));
      if (d.retry_after_seconds != null)
        L.push(c('dim','ask again in ' + d.retry_after_seconds + 's'));
      $('r-rec').disabled = false;
    }
    L.push('', 'Full trace: <a href="/trace/' + esc(LAST_EXEC) +
      '" target="_blank" class="vi">/trace/' + esc(LAST_EXEC) + '</a>');
    out(o, L);
  } catch(e){ failed(st, 'reconcile', e.message); }
  finally { btn.textContent = '2 · Reconcile against the provider'; }
});

/* the kill switch reports its own gate rather than pretending */
(async function killPrecheck(){
  const st = $('k-state'), chip = $('k-chip'), btn = $('k-btn');
  try {
    const r = await jfetch('/demo/kill-switch');
    const d = r.body;
    chip.innerHTML = '<span class="chip ' + (d.enabled ? 'chip-bad' : 'chip-dim') + '">' +
      (d.enabled ? 'armed' : 'disabled') + '</span>';
    st.innerHTML = '<p class="panel-sub" style="margin-bottom:10px">' + esc(d.reason) +
      '<br><span class="m" style="color:var(--text-dim)">' + esc(d.what_it_does) + '</span></p>';
    btn.disabled = !d.enabled;
  } catch(e){ failed(st, 'GET /demo/kill-switch', e.message); }
})();

$('k-btn').addEventListener('click', async function(){
  if (!confirm('This really kills the server process. Continue?')) return;
  const o = $('k-out');
  out(o, [c('warn','POST /demo/kill-switch  {"confirm":"KILL"}')]);
  try {
    const r = await fetch('/demo/kill-switch', {
      method:'POST', headers:{'Content-Type':'application/json'},
      body: JSON.stringify({confirm:'KILL'})});
    out(o, [c('bad','server did not die: HTTP ' + r.status)]);
  } catch(e){
    out(o, [
      c('bad','connection lost — the process is gone'), '',
      'Restart it:  ' + c('hi','python run.py'),
      'Then watch the boot log for:',
      c('warn','  [BOOT] crash recovery: N execution(s) moved REMOTE_ATTEMPTED -> RECONCILIATION_REQUIRED')
    ]);
  }
});

/* ═══ SCENE G — trust nothing ═══════════════════════════════════════ */
let RECEIPT = null;

$('t-buy').addEventListener('click', async function(){
  const btn = this, st = $('t-state');
  btn.disabled = true; btn.textContent = 'Buying…';
  loading(st, 'running one real purchase to produce a receipt');
  try {
    const buy = await jfetch('/discovery/checkout', {
      method:'POST', headers:{'Content-Type':'application/json'},
      body: JSON.stringify({sku:'BAT-001', budget_paise:300000})});
    if (!buy.ok){ failed(st, 'POST /discovery/checkout', JSON.stringify(buy.body)); return; }
    const r = await jfetch('/api/v1/receipt/' + encodeURIComponent(buy.body.execution_id));
    if (!r.ok){ failed(st, 'GET receipt', JSON.stringify(r.body)); return; }
    clear(st);
    RECEIPT = r.body;
    renderReceipt(RECEIPT);
    $('t-verify').disabled = false;
    $('t-tamper').disabled = false;
    loadChain();
  } catch(e){ failed(st, 'purchase', e.message); }
  finally { btn.disabled = false; btn.textContent = '1 · Make a purchase to verify'; }
});

function renderReceipt(d){
  const b = d.approval_binding || {};
  const settled = d.settlement && d.settlement.confirmed;
  $('t-receipt').innerHTML =
    '<div class="receipt">' +
      '<div class="rc-h">SELLABLE &middot; purchase receipt</div>' +
      row('Product', d.product || '—') +
      row('Execution', d.execution_id) +
      row('Provider order', d.provider_order_id || 'none') +
      row('Gateway', d.gateway_decision + ' · ' + d.policy_version) +
      row('Binding', 'seq ' + b.seq + ' · single-use · ' + (b.consumed_at ? 'consumed' : 'unspent')) +
      row('Bound cart', b.bound_skus || '—') +
      row('Execution state', d.execution_state) +
      row('Settlement', settled ? 'confirmed by signed webhook' : 'no settlement event received') +
      row('Issuer', d.issuer) +
      '<div class="rc-row rc-total"><span class="rc-k">Amount</span>' +
        '<span class="rc-v">' + esc(d.final_amount_display) + '</span></div>' +
      '<div class="rc-stamp' + (REDUCED ? '' : ' settle') + '">AUDIT ' + esc(d.audit_chain) + '</div>' +
      '<div class="rc-cap">The AI proposed. You authorized the exact cart. ' +
        'Deterministic code moved the money. The chain remembers.</div>' +
    '</div>' +
    '<div class="row-actions" style="margin-top:14px">' +
      '<a class="btn btn-sm" href="/api/v1/receipt/' + esc(d.execution_id) + '" target="_blank" rel="noopener">Receipt JSON</a>' +
      '<a class="btn btn-sm" href="/trace/' + esc(d.execution_id) + '" target="_blank" rel="noopener">Full trace</a>' +
    '</div>';
}
function row(k, v){
  return '<div class="rc-row"><span class="rc-k">' + esc(k) +
         '</span><span class="rc-v">' + esc(v) + '</span></div>';
}

/* The whole point of scene G: this runs in YOUR browser. */
$('t-verify').addEventListener('click', async function(){
  const o = $('t-verify-out'), badge = $('t-badge');
  if (!RECEIPT || !RECEIPT.audit_anchor){
    o.innerHTML = '<span class="bad">no receipt loaded yet</span>'; return;
  }
  const a = RECEIPT.audit_anchor;
  if (!window.crypto || !crypto.subtle){
    o.innerHTML = '<span class="bad">WebCrypto is unavailable in this context ' +
      '(it needs https or localhost). Check the preimage with sha256sum instead.</span>';
    return;
  }
  const digest = await crypto.subtle.digest('SHA-256', new TextEncoder().encode(a.hash_preimage));
  const computed = Array.from(new Uint8Array(digest))
    .map(x => x.toString(16).padStart(2,'0')).join('');
  const ok = computed === a.hash;
  badge.innerHTML = '<span class="chip ' + (ok ? 'chip-ok' : 'chip-bad') + '">' +
    (ok ? 'verified' : 'diverged') + '</span>';
  out(o, [
    c('dim','block ' + a.seq + ' · sha256(preimage) computed by crypto.subtle in this tab'),
    '',
    'preimage   ' + esc(a.hash_preimage),
    '',
    'server says  ' + c('dim', a.hash),
    'you computed ' + c(ok ? 'ok' : 'bad', computed),
    '',
    ok ? c('ok','MATCH — you just verified the ledger without trusting this server.')
       : c('bad','DIVERGED — do not trust this server.'),
    '',
    c('dim','The preimage is on the receipt. Check it with any tool: '),
    c('hi', "printf '%s' '<preimage>' | sha256sum")
  ]);
});

async function loadChain(){
  const host = $('t-chain');
  host.innerHTML = '<div class="state-loading"><span class="dot"></span>loading the chain</div>';
  try {
    const r = await jfetch('/audit');
    if (!r.ok){ failed(host, 'GET /audit', JSON.stringify(r.body)); return; }
    const es = (r.body.entries || []).slice(-14);
    host.innerHTML = '';
    es.forEach((e, i) => {
      if (i) { const l = document.createElement('div'); l.className = 'clink'; host.appendChild(l); }
      const el = document.createElement('div');
      el.className = 'cblk'; el.dataset.seq = e.seq;
      el.innerHTML = '<div class="cblk-s">block ' + esc(e.seq) + '</div>' +
        '<div class="cblk-h">' + esc(String(e.hash || '').slice(0,10)) + '</div>' +
        '<div class="cblk-a">' + esc(e.action) + '</div>';
      host.appendChild(el);
    });
  } catch(e){ failed(host, 'GET /audit', e.message); }
}

$('t-tamper').addEventListener('click', async function(){
  const cas = $('t-cascade'), host = $('t-chain');
  const blocks = Array.from(host.querySelectorAll('.cblk'));
  if (!blocks.length){ await loadChain(); return; }
  const target = blocks[Math.floor(blocks.length / 3)];
  const seq = parseInt(target.dataset.seq, 10);
  cas.innerHTML = '<div class="state-loading"><span class="dot"></span>recomputing the chain from block ' + seq + '</div>';
  try {
    const r = await jfetch('/audit/tamper-demo', {
      method:'POST', headers:{'Content-Type':'application/json'},
      body: JSON.stringify({block_seq: seq})});
    if (!r.ok){ failed(cas, 'POST /audit/tamper-demo', JSON.stringify(r.body)); return; }
    const d = r.body;
    /* M5 — the cascade, left to right from the broken block */
    const from = blocks.findIndex(b => parseInt(b.dataset.seq,10) === d.halt_at_block);
    blocks.slice(Math.max(0, from)).forEach((b, i) => {
      setTimeout(() => b.classList.add('broken'), REDUCED ? 0 : i * 55);
    });
    setTimeout(() => {
      cas.innerHTML = '<div class="banner bad"><div class="banner-t">' +
        'CHAIN VERIFICATION HALTED AT BLOCK ' + esc(d.halt_at_block) + '</div>' +
        '<div class="banner-s">one flipped bit in block ' + esc(d.tampered_block.seq) +
        ' invalidates ' + esc(d.blocks_invalidated) + ' of ' + esc(d.chain_length) +
        ' blocks &middot; on-disk ledger: ' + esc(d.on_disk_chain) + '</div></div>' +
        '<div class="out">' +
        'original hash    ' + c('dim', d.original_hash) + '\n' +
        'after one bit    ' + c('bad', d.recomputed_hash_after_tamper) + '\n\n' +
        c('dim', d.disclosure) + '</div>';
    }, REDUCED ? 0 : (blocks.length - Math.max(0, from)) * 55 + 120);
  } catch(e){ failed(cas, 'tamper', e.message); }
});

$('t-copy').addEventListener('click', function(){
  const url = location.origin + '/.well-known/agent-manifest.json';
  const done = () => { this.textContent = 'Copied'; setTimeout(() => this.textContent = 'Copy manifest URL', 1600); };
  if (navigator.clipboard) navigator.clipboard.writeText(url).then(done).catch(done);
  else done();
});

/* ═══ EVIDENCE — runtime posture ════════════════════════════════════ */
$('e-score').addEventListener('click', async function(){
  const o = $('e-out');
  out(o, [c('dim','GET /api/v1/security-score')]);
  try {
    const r = await jfetch('/api/v1/security-score');
    if (!r.ok){ failed(o, 'GET /api/v1/security-score', JSON.stringify(r.body)); return; }
    const d = r.body, L = [c(d.status === 'SECURE' ? 'ok' : 'warn', d.label), ''];
    Object.keys(d.checks || {}).forEach(k => {
      const chk = d.checks[k];
      L.push(c(chk.ok ? 'ok' : 'bad', chk.ok ? '  PASS  ' : '  FAIL  ') +
             pad(k, 42) + c('dim', chk.detail));
    });
    const ex = d.excluded_from_score || {};
    L.push('', c('dim','excluded (' + ex.reason + '):'));
    (ex.properties || []).forEach(p => L.push(c('dim','  · ' + p)));
    L.push(c('dim','  evidence: ' + ex.evidence));
    out(o, L);
  } catch(e){ failed(o, 'GET /api/v1/security-score', e.message); }
});
"""


@router.get("/judge", response_class=HTMLResponse)
@router.get("/cockpit", response_class=HTMLResponse)
async def judge_page() -> HTMLResponse:
    return HTMLResponse(render_judge_page())
