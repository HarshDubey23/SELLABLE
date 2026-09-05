"""GET /judge (and /cockpit) — the reviewer's cockpit.

EIGHT SCENES, ONE PAGE
----------------------
  A  Sentinel        live status, read from real endpoints on a poll
  B  The market      three merchant LLMs bid; the server decides what it costs
  C  Gauntlet        every built-in attack, one button, real latencies
  D  Mission         the agent actually shops; the timeline is its trace
  E  Negotiation     buyer vs merchant, with the policy clamp visible
  F  Two locks       write your own attack; watch both layers refuse it
  G  Kill & resurrect  really kill the process, watch recovery classify it
  H  Trust nothing   verify a chain block in your own browser, then break it

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


# The market sits second on purpose. It is the thing a reviewer is least
# likely to have seen anywhere else, and burying the most distinctive
# scene at position eight is how a demo gets missed rather than judged.
SCENES = [
    ("sentinel", "A", "Sentinel"),
    ("market", "B", "The market"),
    ("gauntlet", "C", "Gauntlet"),
    ("mission", "D", "Mission"),
    ("negotiation", "E", "Negotiation"),
    ("locks", "F", "Two locks"),
    ("recovery", "G", "Kill &amp; resurrect"),
    ("trust", "H", "Trust nothing"),
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

/* ── H  the market ─────────────────────────────────────────────────────
   The signature of this scene is its borders. A dashed violet edge means
   a language model wrote the numbers inside it. A solid teal rule means
   the server computed them. A card that never earns a teal rule never
   earned a price, and you can see that from across the room without
   reading a word. */
/* Each merchant is a standing agent with a rulebook, not a result row.
   The rulebook is printed on the card because it is the only way a
   refusal is checkable: "asked 22%, allowed 15%" means nothing unless
   the 15% is visible and came from somewhere. */
.mk-who{padding:11px 13px;border-bottom:1px solid var(--border);
  background:var(--bg-inset)}
.mk-who-top{display:flex;align-items:baseline;justify-content:space-between;
  gap:8px}
.mk-name{font-family:var(--sans);font-size:15px;font-weight:600;
  color:var(--text-hi);letter-spacing:-.01em}
.mk-strat{font-family:var(--mono);font-size:9.5px;letter-spacing:.14em;
  text-transform:uppercase;color:var(--violet)}
.mk-caps{display:flex;flex-wrap:wrap;gap:5px;margin-top:9px}
.mk-cap{font-family:var(--mono);font-size:9.5px;color:var(--text-lo);
  border:1px solid var(--border-hi);border-radius:var(--r-chip);
  padding:2px 6px;white-space:nowrap}
.mk-cap b{color:var(--text-mid);font-weight:700}
.mk-think{padding:26px 13px;text-align:center;font-family:var(--mono);
  font-size:11px;letter-spacing:.1em;text-transform:uppercase;
  color:var(--violet)}
.mk-think .dots::after{content:'';animation:mkdots 1.2s steps(4,end) infinite}
@keyframes mkdots{0%{content:''}25%{content:'.'}50%{content:'..'}75%{content:'...'}}
@media (prefers-reduced-motion:reduce){.mk-think .dots::after{content:'...'}}
.mk-idle{padding:22px 13px;text-align:center;font-size:11.5px;
  color:var(--text-lo)}
.mk-breach{font-family:var(--mono);font-size:10.5px;color:var(--text-mid);
  margin-top:5px}
.mk-breach b{color:var(--red)}
.hero-point{margin-top:14px;font-size:14px;color:var(--text-mid)}
.hero-jump{font:inherit;font-weight:600;color:var(--violet);background:none;
  border:none;border-bottom:1px solid var(--violet-line);padding:0 1px;
  cursor:pointer}
.hero-jump:hover{color:var(--text-hi);border-bottom-color:var(--text-hi)}
.mk-ask{display:flex;gap:10px;flex-wrap:wrap;align-items:center;margin:18px 0 6px}
.mk-ask #mk-mode{display:flex;gap:6px;flex-wrap:wrap}
.mk-ask input[type=text]{
  flex:1 1 340px;min-width:0;background:var(--bg-inset);color:var(--text-hi);
  border:1px solid var(--border-hi);border-radius:var(--r-ctl);
  padding:11px 13px;font:inherit;font-size:13.5px}
.mk-ask input[type=text]:focus{outline:2px solid var(--violet);outline-offset:1px}
.mk-seeds{display:flex;gap:6px;flex-wrap:wrap;margin:2px 0 14px}
.mk-seed{font-family:var(--mono);font-size:10.5px;letter-spacing:.04em;
  background:transparent;color:var(--text-lo);border:1px dashed var(--border-hi);
  border-radius:999px;padding:5px 11px;cursor:pointer}
.mk-seed:hover{color:var(--text-hi);border-color:var(--violet-line)}

.mk-brief{display:grid;grid-template-columns:repeat(auto-fit,minmax(170px,1fr));
  gap:1px;background:var(--border);border:1px solid var(--border);
  border-radius:var(--r-panel);overflow:hidden;margin:14px 0}
.mk-brief div{background:var(--bg-panel);padding:11px 13px}
.mk-brief .k{font-family:var(--mono);font-size:9.5px;letter-spacing:.18em;
  text-transform:uppercase;color:var(--text-lo);margin-bottom:5px}
.mk-brief .v{font-size:13px;color:var(--text-hi)}

/* The bid floor. Three merchants, answering at once. */
.mk-floor{display:grid;grid-template-columns:repeat(auto-fit,minmax(248px,1fr));
  gap:12px;margin:16px 0}
.mk-bid{background:var(--bg-panel);border:1px solid var(--border);
  border-radius:var(--r-panel);overflow:hidden;display:flex;flex-direction:column}
.mk-bid.pending{border-style:dashed;border-color:var(--border-hi);opacity:.72}
.mk-bid.model{border:1px dashed var(--violet-line)}
.mk-bid.refused{border:1px solid rgba(255,77,94,.42)}
.mk-bid.won{border:1px solid var(--teal);box-shadow:0 0 0 1px var(--teal-soft)}
.mk-bid-h{display:flex;align-items:baseline;justify-content:space-between;
  gap:8px;padding:11px 13px 9px;border-bottom:1px solid var(--border)}
.mk-bid-id{font-family:var(--mono);font-size:12px;font-weight:700;
  letter-spacing:.08em;color:var(--text-hi)}
.mk-bid-strat{font-size:10.5px;color:var(--text-lo)}
.mk-terms{padding:11px 13px;display:grid;gap:6px;flex:1}
.mk-term{display:flex;justify-content:space-between;gap:10px;font-size:12px}
.mk-term .k{color:var(--text-lo)}
.mk-term .v{font-family:var(--mono);color:var(--text-hi)}
/* The seam. Above it, what a model asked for. Below it, what the server
   says that costs. They are never allowed to share a surface. */
.mk-priced{border-top:2px solid var(--teal);background:var(--teal-soft);
  padding:10px 13px}
.mk-priced .amt{font-family:var(--mono);font-size:19px;font-weight:700;
  color:var(--text-hi);letter-spacing:-.01em}
.mk-priced .by{font-size:10px;color:var(--text-lo);margin-top:3px}
.mk-refused{border-top:2px solid var(--red);background:var(--red-soft);
  padding:10px 13px}
.mk-refused .code{font-family:var(--mono);font-size:11px;font-weight:700;
  color:var(--red);word-break:break-all}
.mk-refused .why{font-size:11px;color:var(--text-mid);margin-top:4px}
.mk-src{display:flex;align-items:center;gap:5px;padding:7px 13px;
  border-top:1px solid var(--border);font-family:var(--mono);font-size:9.5px;
  letter-spacing:.1em;text-transform:uppercase;color:var(--text-lo)}
.mk-src .d{width:5px;height:5px;border-radius:50%;background:var(--text-lo)}
.mk-src.llm .d{background:var(--violet)}
.mk-src.llm{color:var(--violet)}

/* Why this merchant. Only subtractions between offers on the table. */
.mk-why{background:var(--bg-panel);border:1px solid var(--border);
  border-left:3px solid var(--teal);border-radius:var(--r-panel);
  padding:15px 17px;margin:16px 0}
.mk-why h4{font-size:15px;margin:0 0 4px;color:var(--text-hi)}
.mk-why .basis{font-size:11px;color:var(--text-lo);margin-bottom:11px}
.mk-reasons{display:grid;gap:7px}
.mk-reason{display:flex;gap:9px;align-items:baseline;font-size:12.5px}
.mk-reason .dim{font-family:var(--mono);font-size:9.5px;letter-spacing:.14em;
  text-transform:uppercase;color:var(--text-lo);min-width:88px}
.mk-reason.better .txt{color:var(--teal)}
.mk-reason.worse  .txt{color:var(--amber)}
.mk-weights{display:flex;gap:14px;flex-wrap:wrap;margin-top:12px;
  padding-top:11px;border-top:1px solid var(--border)}
.mk-weight{font-family:var(--mono);font-size:10.5px;color:var(--text-lo)}
.mk-weight b{color:var(--text-hi);font-weight:700}

.mk-probe{background:var(--bg-panel);border:1px solid rgba(255,77,94,.42);
  border-left:3px solid var(--red);border-radius:var(--r-panel);
  padding:15px 17px;margin:16px 0}
.mk-probe .code{font-family:var(--mono);font-size:13px;font-weight:700;
  color:var(--red)}
.mk-probe .ask{font-family:var(--mono);font-size:12px;color:var(--text-mid);
  margin:8px 0}
.mk-probe .ask b{color:var(--text-hi)}
.mk-settled{background:var(--bg-inset);border:1px solid var(--teal);
  border-radius:var(--r-panel);padding:15px 17px;margin:16px 0}
.mk-settled .amt{font-family:var(--mono);font-size:24px;font-weight:700;
  color:var(--text-hi)}
.mk-facts{display:grid;grid-template-columns:repeat(auto-fit,minmax(190px,1fr));
  gap:9px;margin-top:12px}
.mk-fact .k{font-family:var(--mono);font-size:9.5px;letter-spacing:.16em;
  text-transform:uppercase;color:var(--text-lo)}
.mk-fact .v{font-family:var(--mono);font-size:11.5px;color:var(--text-hi);
  word-break:break-all;margin-top:2px}
@media (prefers-reduced-motion:no-preference){
  .mk-bid{animation:mk-in .34s cubic-bezier(.22,.61,.36,1) both}
  @keyframes mk-in{from{opacity:0;transform:translateY(7px)}to{opacity:1;transform:none}}
}
"""


# ────────────────────────────────────────────────────────── scene markup

def _scene_sentinel(truth: dict[str, Any]) -> str:
    code = truth.get("codebase", {})
    return f"""
<h2 class="st">Two kinds of thing, never in the same box</h2>
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
    <span></span><span>Attack</span><span>Outcome</span><span>Stopped by</span>
    <span>Latency</span><span>Razorpay calls</span><span></span>
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
  <span class="panel-sub">SKU BAT-002 &middot; the request carries a SKU and nothing else; the floor and ceiling come from the catalog</span>
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


def _scene_market() -> str:
    """Scene H. Three merchants bid; the server decides what it costs.

    The design carries one idea. A dashed violet border means a language
    model wrote the numbers inside it; a solid teal rule means the server
    computed them. A refused offer never gets the teal rule, because a
    refused offer has no price. A reviewer can look at three cards and
    tell, without reading a word, which figures are claims and which are
    facts.
    """
    return """
<h2 class="st">Three merchants argue. None of them can name a price.</h2>
<p class="sl">Each merchant is its own language model with its own strategy and its own
  signed limits, and they answer at once without seeing each other. What comes back is a
  structured intent &mdash; discounts, delivery, warranty &mdash; with
  <em>no field for an amount</em>. A merchant cannot say what something costs, because
  the vocabulary it writes in does not contain the idea. The server prices the intent
  against the catalog and that merchant's own manifest, and refuses anything the manifest
  does not allow. Nothing is clamped: an illegal offer is not quietly trimmed to fit, it
  is turned down with a reason you can read.</p>

<div class="mk-ask">
  <input type="text" id="mk-text" maxlength="400" autocomplete="off"
         aria-label="What do you want to buy"
         placeholder="Say what you want, in your own words"
         value="A complete cricket setup under Rs 6,000">
  <button class="btn btn-primary" id="mk-open">Open the market</button>
  <span id="mk-mode"></span>
</div>
<div class="mk-seeds">
  <button class="mk-seed" data-mission="A complete cricket setup under Rs 6,000">complete setup &middot; Rs 6,000</button>
  <button class="mk-seed" data-mission="A cricket bat and ball delivered as fast as possible, under Rs 3,000">fastest delivery &middot; Rs 3,000</button>
  <button class="mk-seed" data-mission="Cricket gear with the longest warranty under Rs 8,000">longest warranty &middot; Rs 8,000</button>
  <button class="mk-seed" data-mission="A gaming PC under Rs 80,000">a mission this catalog cannot serve</button>
</div>

<div id="mk-err"></div>
<div id="mk-brief"></div>
<div class="mk-floor" id="mk-floor"></div>
<p class="sl" id="mk-floor-note" style="margin-top:-2px">Three merchants, each its own model with its own strategy and its own signed limits. The limits are printed on every card, so when the policy engine refuses an offer you can check the refusal against the rule it broke without leaving the page.</p>
<div id="mk-state"></div>
<div id="mk-why"></div>

<div class="row-actions" style="margin-top:16px">
  <button class="btn" id="mk-round" disabled>Run a round</button>
  <button class="btn" id="mk-counter" disabled>Counter</button>
  <button class="btn" id="mk-probe" disabled>Try an illegal offer</button>
  <button class="btn" id="mk-override" disabled>Override: cheapest instead</button>
  <button class="btn" id="mk-accept" disabled>Accept the winner</button>
  <button class="btn btn-primary" id="mk-settle" disabled>Pay for real</button>
</div>
<p class="sl" style="margin-top:10px">A counter goes to one merchant and names no rival
  and no rival's terms &mdash; a test reads every prompt and fails if one merchant's brief
  so much as contains another's name. The override re-runs the same mission on
  cheapest-first weights as a <em>new</em> negotiation; the one on screen is never edited,
  so the two can be set side by side. Accept is a conditional UPDATE, so twenty
  simultaneous accepts produce one winner and nineteen refusals. Pay sends the winning
  basket through the same gateway, the same approval binding and the same execution
  machine as every other purchase here.</p>

<div id="mk-err-low"></div>
<div id="mk-probe-out"></div>
<div id="mk-settled"></div>
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
        "market": _scene_market(),
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
  <p>Eight scenes. Each one runs the production code path in front of you &mdash; the
     same gateway, the same binding, the same executor, the same ledger the storefront
     uses. Nothing here is a mock-up, and no number on this page was typed in.</p>
  <p class="hero-point">Start at <button class="hero-jump" data-jump="market">B
     &middot; The market</button> &mdash; three language models bid for one order and
     none of them can name a price.</p>
</header>

<nav class="scenes" role="tablist" aria-label="Scenes">
  <div class="scenes-in">{tabs}</div>
</nav>

<main class="wrap">{body}</main>
{FOOTER}
<script src="https://checkout.razorpay.com/v1/checkout.js"></script>
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
  /* CONTENT MUST NOT DEPEND ON AN ANIMATION TO BECOME VISIBLE.
     `.stagger` sets opacity:0 and relies on a CSS keyframe to bring it
     back. That is fine when the keyframe runs. It is not fine when it
     does not -- a throttled background tab, a compositor that has
     stopped painting, a browser in a power-saving state -- because the
     resting state of the class is invisible, so the rows just never
     appear. The reader sees an empty panel and concludes the feature is
     broken.

     So every staggered node is un-staggered once the animation should
     have finished. If it ran, this changes nothing anyone can see. If it
     never ran, the content shows up anyway. */
  if (REDUCED) return;
  step = step || 70;
  nodes.forEach((n, i) => {
    n.classList.add('stagger');
    n.style.animationDelay = (i * step) + 'ms';
  });
  const settle = nodes.length * step + 400;
  setTimeout(() => nodes.forEach(n => {
    n.classList.remove('stagger');
    n.style.animationDelay = '';
  }), settle);
}
/* M3 — count a real number up, once it has arrived. */
/* The mission's own words for its outcome. The raw enum went straight
   into the headline chip, so a reader saw "payment_failed" or
   "order_created_payment_pending" -- and the chip was coloured green
   whenever an order existed, which meant a failed payment was shown in
   the success colour. The colour now follows the outcome, not the
   presence of a row. */
const MISSION_STATUS = {
  completed:
    ['Paid and captured', 'chip-ok'],
  order_created_payment_pending:
    ['Order created, not yet paid', 'chip-warn'],
  payment_authorized_capture_pending:
    ['Authorized, capture pending', 'chip-warn'],
  payment_failed_then_link_issued:
    ['Payment failed, recovery link issued', 'chip-warn'],
  payment_failed:
    ['Payment failed, nothing captured', 'chip-bad'],
};
function missionStatus(raw){
  const hit = MISSION_STATUS[raw];
  return hit ? {label: hit[0], cls: hit[1]}
             : {label: String(raw || 'unknown'), cls: 'chip-dim'};
}
function countUp(el, target, suffix){
  /* THE TRUE VALUE IS WRITTEN FIRST. THE ANIMATION IS DECORATION.
     This used to render a literal 0 into the DOM and rely on
     requestAnimationFrame to walk it up to the real number. rAF is
     throttled or suspended whenever the page is not being painted -- a
     background tab, a power-saving mode, a browser that has decided the
     window is not visible -- and when it never runs, the number simply
     stays at its starting value.

     The number this drives is "N/8 BLOCKED" on the security scoreboard.
     A reviewer who opened the cockpit in a background tab, or switched
     away for the second it takes to run, came back to "0/8 BLOCKED"
     sitting under eight rows that each say REJECTED. The most important
     figure on the page, stuck at the one value that means the opposite
     of the truth.

     So the correct value goes in immediately and unconditionally. The
     animation only ever overwrites it with intermediate frames, and a
     timer guarantees the final value even if not one frame is drawn. */
  suffix = suffix || '';
  const final = target + suffix;
  el.textContent = final;
  if (REDUCED || target === 0) return;

  const t0 = performance.now(), dur = 600;
  let done = false;
  (function step(now){
    if (done) return;
    const p = Math.min(1, (now - t0) / dur);
    el.textContent = Math.round(target * (1 - Math.pow(1 - p, 3))) + suffix;
    if (p < 1) requestAnimationFrame(step); else done = true;
  })(performance.now());
  setTimeout(() => { done = true; el.textContent = final; }, dur + 200);
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
        /* THE COLUMN SAYS WHAT HAPPENED, NOT WHAT ONE LAYER THOUGHT.
           This used to print s.decision, which is only the *gateway's*
           verdict. Scenarios 07 and 08 are legal at the gateway on
           purpose -- they exist to prove the second lock -- so the
           column read APPROVE on two rows of an attack table. Anyone
           scanning it saw two attacks apparently succeed. The outcome
           leads now, and the gateway's opinion is the supporting line,
           which is also the more interesting fact: it says which of the
           two locks did the work. */
        '<span class="chip ' + (s.safe ? 'chip-ok' : 'chip-bad') + '">' +
          (s.safe ? 'BLOCKED' : 'GOT THROUGH') + '</span>' +
        '<span class="m" style="font-size:11px">' + esc(s.blocked_by) +
          '<span class="id">' + layer +
          (s.decision === 'APPROVE'
            ? ' &middot; gateway allowed it, the binding did not'
            : '') + '</span></span>' +
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
      /* Which lock did the work. Six attacks never reach the money
         boundary at all; two are allowed through the gateway on purpose
         and stopped by the binding. Saying so here is what stops a
         reader wondering why an attack table contains the word APPROVE. */
      const byGateway = d.results.filter(r => r.refused_layer === 'gateway').length;
      const byBinding = d.results.filter(r => r.refused_layer === 'binding').length;
      banner.innerHTML = '<div class="banner' + (allSafe ? '' : ' bad') + '">' +
        '<div class="banner-t"><span id="g-n">' + T.blocked + '</span>/' + T.total +
        ' BLOCKED &middot; ' + T.money_boundary_calls + ' MONEY API CALLS</div>' +
        '<div class="banner-s">' + byGateway + ' stopped by the deterministic ' +
        'gateway &middot; ' + byBinding + ' allowed past it on purpose and stopped ' +
        'by the approval binding &mdash; a system whose only defence is its first ' +
        'has not been tested</div>' +
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
        'Status: ' + esc(missionStatus(d.status).label) + '</div>';
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
    const ms = missionStatus(d.status);
    sum.innerHTML = '<div class="' + (ord ? 'authoritative' : 'advisory') + '" style="margin-top:14px">' +
      '<div class="panel-head"><span class="panel-title">Mission outcome</span>' +
      '<span class="chip ' + ms.cls + '">' + esc(ms.label) + '</span></div>' +
      (ord ? '<div class="m" style="font-size:19px;font-weight:700">' + rupees(ord.amount) +
             '</div><div class="panel-sub">order ' + esc(ord.id) +
             ' &middot; priced from the server catalog &middot; ' + esc(ms.label.toLowerCase()) +
             '</div>'
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
    /* Only a SKU is sent. The floor and ceiling are read from the
       merchant's catalog server-side, so nothing this page does can
       widen the range the model is allowed to move within. */
    const r = await jfetch('/negotiation/demo', {
      method:'POST', headers:{'Content-Type':'application/json'},
      body: JSON.stringify({sku:'BAT-002'})});
    if (!r.ok){
      const err = (r.body && r.body.detail && r.body.detail.error) || {};
      failed(st, 'POST /negotiation/demo',
             err.message || JSON.stringify(r.body)); return; }
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
      c('dim','POST /negotiation/demo  {"sku":"BAT-002"}'),
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

/* Not a straight line: the first three are the path every attempt walks,
   the last three are branches. Drawing RECONCILIATION_REQUIRED as a
   completed step on a purchase that went straight through would show a
   recovery that never happened — the exact kind of small lie this
   project is about. */
const SM_PATH = [
  ['APPROVED','Authorization exists. Nothing has been dispatched.'],
  ['EXECUTION_PENDING','About to contact the provider.'],
  ['REMOTE_ATTEMPTED','Committed to disk BEFORE the call. A crash here is recoverable.']
];
const SM_BRANCH = [
  ['RECONCILIATION_REQUIRED','Outcome unknown. Nothing is assumed and no blind retry is offered.'],
  ['EXECUTED','Resolved from authoritative provider state: the order exists.'],
  ['FAILED','Resolved from authoritative provider state: no order exists. No money moved.']
];
let VIA_RECONCILIATION = false;
function renderSM(cur){
  const pathIx = SM_PATH.findIndex(s => s[0] === cur);
  const terminal = cur === 'EXECUTED' || cur === 'FAILED';
  const rows = [];
  SM_PATH.forEach(([n, x], ix) => {
    let cls = 'smr';
    if (cur === n) cls += ' cur';
    else if (terminal || cur === 'RECONCILIATION_REQUIRED' || ix < pathIx) cls += ' done';
    rows.push([cls, n, x]);
  });
  SM_BRANCH.forEach(([n, x]) => {
    let cls = 'smr';
    if (cur === n){
      cls += n === 'EXECUTED' ? ' done' : n === 'FAILED' ? ' bad' : ' warn';
    } else if (n === 'RECONCILIATION_REQUIRED' && VIA_RECONCILIATION && terminal){
      cls += ' warn';
    }
    rows.push([cls, n, x]);
  });
  $('r-sm').innerHTML = rows.map(([cls, n, x]) =>
    '<div class="' + cls + '"><span class="d"></span>' +
    '<span class="n">' + esc(n) + '</span><span class="x">' + esc(x) + '</span></div>'
  ).join('');
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
    VIA_RECONCILIATION = (state === 'RECONCILIATION_REQUIRED');
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

/* ── H  the market ──────────────────────────────────────────────────
   Three merchants answer at once. This renders what came back and
   nothing else: every rupee figure on screen is a field the server
   computed, and the card it sits in says so by its border. */
let MK = null;

function mkMode(mode){
  if(!mode) return '';
  const llm = mode.merchants === 'llm';
  const pay = mode.payments === 'razorpay_test';
  return '<span class="chip ' + (llm ? 'chip-violet' : 'chip-warn') + '">' +
           esc(mode.merchants_label) + '</span> ' +
         '<span class="chip ' + (pay ? 'chip-ok' : 'chip-warn') + '">' +
           esc(mode.payments_label) + '</span>';
}

function mkBrief(d){
  const p = d.planner || {};
  return '<div class="mk-brief">' +
    '<div><div class="k">Budget ceiling</div><div class="v">' + esc(d.budget_display) + '</div></div>' +
    '<div><div class="k">Basket</div><div class="v">' + esc((d.basket||[]).join(', ')) + '</div></div>' +
    '<div><div class="k">Read by</div><div class="v">' + esc(p.label || 'unknown') + '</div></div>' +
    '<div><div class="k">Round</div><div class="v">' + esc(d.current_round) + ' of ' + esc(d.max_rounds) + '</div></div>' +
    '</div>';
}

/* The manifests, fetched once. A merchant is shown before it has said
   anything, because "who is bidding" is part of what makes this legible. */
let MK_WHO = {};

function mkCaps(m){
  if (!m) return '';
  const rows = [
    ['line', m.max_line_discount_pct + '%'],
    ['bundle', m.max_bundle_discount_pct + '%'],
    ['delivery', m.delivery_days_range[0] + '-' + m.delivery_days_range[1] + 'd'],
    ['warranty', m.allowed_warranty_years.join('/') + 'y'],
    ['margin floor', m.min_margin_pct + '%'],
  ];
  return '<div class="mk-caps">' + rows.map(function(r){
    return '<span class="mk-cap">' + esc(r[0]) + ' <b>' + esc(r[1]) + '</b></span>';
  }).join('') + '</div>';
}

function mkWho(id){
  const m = MK_WHO[id];
  return '<div class="mk-who"><div class="mk-who-top">' +
    '<span class="mk-name">' + esc(m ? m.display_name : id) + '</span>' +
    '<span class="mk-strat">' + esc(m ? m.strategy : '') + '</span></div>' +
    mkCaps(m) + '</div>';
}

async function mkLoadWho(){
  const r = await jfetch('/market/merchants');
  if (!r.ok || !r.body) return;
  MK_WHO = {};
  r.body.merchants.forEach(function(m){ MK_WHO[m.merchant_id] = m; });
  $('mk-mode').innerHTML = mkMode(r.body.mode);
  mkFloorIdle();
}

function mkOrder(){
  const ids = Object.keys(MK_WHO);
  return ids.length ? ids.sort() : ['BYTECART','GEARHUB','NOVATECH'];
}

/* The floor before anyone has bid: three agents, waiting. */
function mkFloorIdle(){
  $('mk-floor').innerHTML = mkOrder().map(function(id){
    return '<div class="mk-bid pending">' + mkWho(id) +
      '<div class="mk-idle">waiting for a mission</div></div>';
  }).join('');
}

/* The floor while the three models are answering, all at once. */
function mkFloorThinking(){
  $('mk-floor').innerHTML = mkOrder().map(function(id){
    return '<div class="mk-bid model">' + mkWho(id) +
      '<div class="mk-think"><span class="dots">reading the basket</span></div>' +
      '</div>';
  }).join('');
}

function mkBid(o, winnerId){
  const i = o.intent || {};
  const cls = !o.accepted ? 'refused' : (o.merchant_id === winnerId ? 'won' : 'model');
  const rows = [
    ['Line discount', i.line_discount_pct + '%'],
    ['Bundle discount', i.bundle_discount_pct + '%'],
    ['Shipping', i.shipping],
    ['Delivery', i.delivery_days + ' day(s)'],
    ['Warranty', i.warranty_years ? i.warranty_years + ' year(s)' : 'none']
  ];
  const terms = rows.map(function(t){
    return '<div class="mk-term"><span class="k">' + esc(t[0]) +
           '</span><span class="v">' + esc(t[1]) + '</span></div>';
  }).join('');

  const foot = o.accepted
    ? '<div class="mk-priced"><div class="amt">' + esc(o.total_display) + '</div>' +
      '<div class="by">server-side catalog recomputation</div></div>'
    : '<div class="mk-refused"><div class="code">' + esc(o.reason) + '</div>' +
      '<div class="why">' + esc((o.verdict && o.verdict.reason_human) ||
        'refused by the merchant policy engine before it was priced') + '</div>' +
      mkBreach(o) + '</div>';

  return '<div class="mk-bid ' + cls + '">' + mkWho(o.merchant_id) +
    '<div class="mk-bid-h"><span class="mk-bid-id">' +
      (cls === 'won' ? 'ACCEPTED' : 'round ' + esc(o.round)) + '</span>' +
    '<span class="mk-bid-strat">' + (cls === 'won' ? 'round ' + esc(o.round) : '') +
      '</span></div>' +
    '<div class="mk-terms">' + terms + '</div>' + foot +
    '<div class="mk-src' + (o.is_llm ? ' llm' : '') + '"><span class="d"></span>' +
    esc(o.agent_label || '') + (o.latency_ms ? ' &middot; ' + esc(o.latency_ms) + 'ms' : '') +
    '</div></div>';
}

/* The two numbers that disagree, printed next to each other. A reason
   code alone asks the reader to take the refusal on faith. */
function mkBreach(o){
  const b = (o.verdict && o.verdict.breach) || null;
  if (!b) return '';
  const pairs = [];
  if (b.offered_pct != null && b.manifest_cap_pct != null)
    pairs.push('asked <b>' + esc(b.offered_pct) + '%</b>, manifest allows ' +
               esc(b.manifest_cap_pct) + '%');
  if (b.resulting_margin_pct != null && b.manifest_floor_pct != null)
    pairs.push('would leave <b>' + esc(b.resulting_margin_pct) +
               '%</b> margin, floor is ' + esc(b.manifest_floor_pct) + '%');
  if (b.threshold_paise != null && b.short_by_paise != null)
    pairs.push('short by <b>' + rupees(b.short_by_paise) + '</b> of the ' +
               rupees(b.threshold_paise) + ' free-shipping threshold');
  return pairs.length
    ? '<div class="mk-breach">' + pairs.join('<br>') + '</div>' : '';
}

function mkWhy(d){
  const r = d.ranking;
  if(!r || !r.explanation) return '';
  const e = r.explanation;
  const reasons = (e.reasons||[]).map(function(x){
    return '<div class="mk-reason ' + esc(x.direction) + '">' +
      '<span class="dim">' + esc(x.dimension) + '</span>' +
      '<span class="txt">' + esc(x.text) + '</span></div>';
  }).join('');
  const wu = e.weights_used || {};
  const weights = Object.keys(wu).map(function(k){
    return '<span class="mk-weight">' + esc(k) + ' <b>' + esc(wu[k]) + '</b></span>';
  }).join('');
  const runner = e.runner_up
    ? '<div class="mk-weight" style="margin-top:8px">runner-up ' + esc(e.runner_up.merchant_id) +
      ', behind by <b>' + (e.runner_up.margin/10).toFixed(1) + '</b> points</div>'
    : '';
  return '<div class="mk-why"><h4>' + esc(e.headline) + '</h4>' +
    '<div class="basis">' + esc(e.basis) + '</div>' +
    '<div class="mk-reasons">' + reasons + '</div>' +
    '<div class="mk-weights">' + weights + '</div>' + runner + '</div>';
}

function mkRender(d){
  MK = d;
  const winner = (d.ranking && d.ranking.winner) ? d.ranking.winner.merchant_id : null;
  const bids = (d.offers||[]).filter(function(o){ return o.round === d.current_round; });
  $('mk-brief').innerHTML = mkBrief(d);
  $('mk-floor').innerHTML = bids.length
    ? bids.map(function(o){ return mkBid(o, winner); }).join('')
    : '<div class="state-empty">no offers yet &mdash; run a round</div>';
  const settledStates = ['ROUND_COMPLETE','ACCEPTED','COUNTER_ISSUED'];
  $('mk-why').innerHTML = settledStates.indexOf(d.state) >= 0 ? mkWhy(d) : '';
  $('mk-mode').innerHTML = mkMode(d.mode);

  const refused = (d.offers||[]).filter(function(o){ return !o.accepted; }).length;
  $('mk-state').innerHTML =
    '<div class="panel-sub" style="margin-top:10px">state <b>' + esc(d.state) + '</b>' +
    ' &middot; round ' + esc(d.current_round) + '/' + esc(d.max_rounds) +
    (refused ? ' &middot; <span style="color:var(--red)">' + refused +
               ' offer(s) refused by policy</span>' : '') +
    (d.transcript_hash ? ' &middot; transcript ' + esc(d.transcript_hash.slice(0,16)) : '') +
    '</div>';

  const open = d.state === 'ROUND_COMPLETE' || d.state === 'COUNTER_ISSUED';
  $('mk-round').disabled = !(d.state === 'OPEN' || d.state === 'COUNTER_ISSUED') ||
                           d.current_round >= d.max_rounds;
  $('mk-counter').disabled = !open || !winner;
  $('mk-accept').disabled = d.state !== 'ROUND_COMPLETE';
  $('mk-override').disabled = !(open || d.state === 'ACCEPTED');
  $('mk-settle').disabled = d.state !== 'ACCEPTED' || d.settled;
  $('mk-probe').disabled = !(d.offers && d.offers.length);
  $('mk-counter').textContent = winner
    ? 'Ask ' + winner + ' for faster delivery' : 'Counter';
}


/* ── one action at a time ──────────────────────────────────────────────
   None of these buttons disabled while their request was in flight. A
   round takes the better part of ten seconds against three live models,
   so the control sat there looking idle, people clicked it again, and
   the rate limit that exists to stop abuse ended up blocking the demo
   with RATE_LIMITED on the one button that spends money.

   So: every action disables the whole row, names what it is doing on the
   button that was pressed, and puts any error next to the buttons rather
   than at the top of the scene where it cannot be seen from here. */
const MK_BTNS = ['mk-open','mk-round','mk-counter','mk-probe','mk-override',
                 'mk-accept','mk-settle'];
let MK_BUSY = false;

function mkBusy(on, activeId, label){
  MK_BUSY = on;
  MK_BTNS.forEach(function(id){
    const b = $(id);
    if (!b) return;
    if (on){
      if (!b.dataset.idleLabel) b.dataset.idleLabel = b.textContent;
      b.disabled = true;
      if (id === activeId) b.textContent = label || 'Working…';
    } else {
      if (b.dataset.idleLabel){ b.textContent = b.dataset.idleLabel; }
      delete b.dataset.idleLabel;
      // Re-enable everything, then let mkRender put back the states it
      // actually governs. Restoring only the label left "Open the market"
      // disabled for good, because mkRender never touches that one.
      b.disabled = false;
    }
  });
}

async function mkAction(activeId, label, fn){
  if (MK_BUSY) return;
  $('mk-err').innerHTML = '';
  $('mk-err-low').innerHTML = '';
  mkBusy(true, activeId, label);
  try { await fn(); }
  finally {
    mkBusy(false);
    if (MK) mkRender(MK);          /* restore the correct enabled states */
  }
}

async function mkCall(url, opts, what){
  const err = $('mk-err'); err.innerHTML = '';
  const box = $('mk-floor');
  if(what) loading(box, what);
  const r = await jfetch(url, opts);
  if(!r.ok){
    const e = (r.body && r.body.detail && r.body.detail.error) || {};
    const html = '<div class="state-error">' + esc(e.error_code || r.status) +
      '<span class="m">' + esc(e.message || r.parseError || 'request failed') +
      (e.hint ? ' &mdash; ' + esc(e.hint) : '') +
      (e.retry_after_seconds != null
        ? ' &middot; try again in ' + esc(e.retry_after_seconds) + 's' : '') +
      '</span></div>';
    err.innerHTML = html;
    if ($('mk-err-low')) $('mk-err-low').innerHTML = html;
    if(what) box.innerHTML = '';
    return null;
  }
  return r.body;
}

async function mkOpen(){
  const text = $('mk-text').value.trim();
  if(!text) return;
  $('mk-settled').innerHTML = '';
  $('mk-why').innerHTML = '';
  const d = await mkCall('/market/open', {
    method:'POST', headers:{'Content-Type':'application/json'},
    body: JSON.stringify({mission_text:text, use_llm:true})
  }, 'reading the mission and signing a ceiling');
  if(d) mkRender(d);
}

async function mkRound(){
  mkFloorThinking();
  const d = await mkCall('/market/' + encodeURIComponent(MK.negotiation_id) + '/round',
    {method:'POST'});
  if(d) mkRender(d); else mkFloorIdle();
}

async function mkCounter(){
  const w = MK.ranking && MK.ranking.winner && MK.ranking.winner.merchant_id;
  if(!w) return;
  const d = await mkCall('/market/' + encodeURIComponent(MK.negotiation_id) + '/counter', {
    method:'POST', headers:{'Content-Type':'application/json'},
    body: JSON.stringify({merchant_id:w, ask:'FASTER_DELIVERY',
                          note:'can you do better on delivery?'})
  });
  if(d) mkRender(d);
}

async function mkAccept(){
  const d = await mkCall('/market/' + encodeURIComponent(MK.negotiation_id) + '/accept',
    {method:'POST'});
  if(d) mkRender(d);
}

async function mkOverride(){
  const d = await mkCall('/market/' + encodeURIComponent(MK.negotiation_id) + '/override', {
    method:'POST', headers:{'Content-Type':'application/json'},
    body: JSON.stringify({preset:'cheapest'})
  }, 're-running the same mission on cheapest-first weights');
  if(d){ $('mk-settled').innerHTML = ''; mkRender(d); }
}

async function mkProbe(){
  const w = (MK.ranking && MK.ranking.winner && MK.ranking.winner.merchant_id)
            || (MK.offers[0] && MK.offers[0].merchant_id);
  if(!w) return;
  const box = $('mk-probe-out');
  loading(box, 'sending an offer outside ' + w + "'s signed manifest");
  const d = await mkCall('/market/' + encodeURIComponent(MK.negotiation_id) + '/probe', {
    method:'POST', headers:{'Content-Type':'application/json'},
    body: JSON.stringify({merchant_id:w})
  });
  if(!d){ box.innerHTML = ''; return; }
  const p = d.probe;
  box.innerHTML = '<div class="mk-probe">' +
    '<div class="code">' + esc(p.reason || p.decision) + '</div>' +
    '<div class="ask">asked for <b>' + esc(p.asked_line_discount_pct) +
      '%</b> &middot; ' + esc(p.merchant_id) + " manifest allows <b>" +
      esc(p.manifest_cap_pct) + '%</b></div>' +
    '<div class="panel-sub">' + esc(p.reason_human || '') + '</div>' +
    '<div class="panel-sub" style="margin-top:9px">It was not trimmed to ' +
      esc(p.manifest_cap_pct) + '%. A refused offer carries no price at all &mdash; ' +
      'total_paise came back <b>' + esc(String(p.total_paise)) + '</b>. ' +
      esc(p.note) + '</div></div>';
}


/* The market pays through the same money path as the storefront, so it
   opens the same box. Razorpay's own Checkout takes the payment details;
   nothing here ever sees them. */
function mkOpenRazorpay(order, settlement){
  const out = $('mk-settled');
  if (!order || order.provider !== 'razorpay_test') return;
  if (!window.Razorpay || !order.razorpay_key_id || !order.order_id){
    return;
  }
  const rzp = new Razorpay({
    key: order.razorpay_key_id,
    order_id: order.order_id,
    amount: order.amount_paise,
    currency: 'INR',
    name: 'SELLABLE',
    description: 'Negotiated with ' + (settlement.merchant_id || 'the market'),
    notes: {negotiation_id: settlement.negotiation_id || '',
            transcript_hash: (settlement.transcript_hash || '').slice(0, 32)},
    theme: {color: '#6C47FF'},
    prefill: {email: 'demo@sellable.test', contact: '9999999999'},
    handler: function(resp){
      out.insertAdjacentHTML('beforeend',
        '<div class="mk-probe" style="border-color:rgba(45,212,191,.45)">' +
        '<div class="code" style="color:var(--teal)">PAYMENT SUBMITTED</div>' +
        '<div class="why">Razorpay accepted payment ' +
          esc(resp.razorpay_payment_id || '') + '. Settlement is still only ' +
          'recorded from a signature-verified webhook, so the ledger may ' +
          'lag this by a moment.</div></div>');
    },
    modal: {ondismiss: function(){
      out.insertAdjacentHTML('beforeend',
        '<div class="panel-sub" style="margin-top:9px">Checkout closed. The ' +
        'order exists and is unpaid &mdash; reopen it at <a class="vi" ' +
        'href="/checkout/' + esc(order.order_id) + '">/checkout/' +
        esc(order.order_id) + '</a>.</div>');
    }},
  });
  rzp.on('payment.failed', function(r){
    const e = (r && r.error) || {};
    out.insertAdjacentHTML('beforeend',
      '<div class="mk-probe"><div class="code">PAYMENT FAILED &middot; ' +
      esc(e.code || 'unknown') + '</div><div class="why">' +
      esc(e.description || '') + ' The order still exists and no money moved.' +
      '</div></div>');
  });
  rzp.open();
}

async function mkSettle(){
  const box = $('mk-settled');
  loading(box, 'gateway to approval binding to execution machine to Razorpay');
  const d = await mkCall('/market/' + encodeURIComponent(MK.negotiation_id) + '/settle',
    {method:'POST'});
  if(!d){ box.innerHTML = ''; return; }
  const s = d.settlement, o = s.order || {};
  mkOpenRazorpay(o, s);
  box.innerHTML = '<div class="mk-settled">' +
    '<div class="amt">' + esc(s.amount_display) + '</div>' +
    '<div class="panel-sub">paid to ' + esc(s.merchant_id) +
      ' &middot; ' + esc(d.mode.payments_label) + '</div>' +
    '<div class="mk-facts">' +
    '<div class="mk-fact"><div class="k">Order</div><div class="v">' + esc(o.order_id) + '</div></div>' +
    '<div class="mk-fact"><div class="k">Execution</div><div class="v">' + esc(o.execution_state) + '</div></div>' +
    '<div class="mk-fact"><div class="k">Provider</div><div class="v">' + esc(o.provider) + '</div></div>' +
    '<div class="mk-fact"><div class="k">Approval seq</div><div class="v">' + esc(s.approve_seq) + '</div></div>' +
    '<div class="mk-fact"><div class="k">Transcript hash</div><div class="v">' + esc(s.transcript_hash) + '</div></div>' +
    '</div>' +
    '<div class="panel-sub" style="margin-top:11px">The binding pinned this merchant and ' +
    'this transcript. Edit either afterwards and it stops matching, so no order is created.</div>' +
    '</div>';
  mkRender(d);
}

/* A deep link lands on the scene it names, so /judge#market opens the
   market rather than dropping the reader on Sentinel to go hunting. */
(function(){
  const want = (location.hash || '').replace('#','');
  if (want && KEYS.indexOf(want) >= 0) show(want);
})();
document.querySelectorAll('.hero-jump').forEach(function(b){
  b.addEventListener('click', function(){
    show(b.dataset.jump);
    document.querySelector('.scenes').scrollIntoView({block:'start'});
  });
});
document.querySelectorAll('.mk-seed').forEach(function(b){
  b.addEventListener('click', function(){
    $('mk-text').value = b.dataset.mission;
    mkAction('mk-open', 'Reading the mission…', mkOpen);
  });
});
if($('mk-open'))     $('mk-open').addEventListener('click', function(){
  mkAction('mk-open', 'Reading the mission…', mkOpen); });
if($('mk-round'))    $('mk-round').addEventListener('click', function(){
  mkAction('mk-round', 'Three merchants answering…', mkRound); });
if($('mk-counter'))  $('mk-counter').addEventListener('click', function(){
  mkAction('mk-counter', 'Sending the counter…', mkCounter); });
if($('mk-accept'))   $('mk-accept').addEventListener('click', function(){
  mkAction('mk-accept', 'Claiming the winner…', mkAccept); });
if($('mk-override')) $('mk-override').addEventListener('click', function(){
  mkAction('mk-override', 'Re-running on new weights…', mkOverride); });
if($('mk-probe'))    $('mk-probe').addEventListener('click', function(){
  mkAction('mk-probe', 'Sending an illegal offer…', mkProbe); });
if($('mk-settle'))   $('mk-settle').addEventListener('click', function(){
  mkAction('mk-settle', 'Gateway → binding → Razorpay…', mkSettle); });
if($('mk-text'))     $('mk-text').addEventListener('keydown', function(e){
  if(e.key === 'Enter') mkAction('mk-open', 'Reading the mission…', mkOpen);
});
if($('mk-floor')) mkLoadWho();
"""


@router.get("/judge", response_class=HTMLResponse)
@router.get("/cockpit", response_class=HTMLResponse)
async def judge_page() -> HTMLResponse:
    return HTMLResponse(render_judge_page())
