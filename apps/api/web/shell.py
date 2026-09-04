"""PROJECT OBSIDIAN — the one visual system the SELLABLE pages share.

THE IDEA THE DESIGN HAS TO CARRY
--------------------------------
SELLABLE's whole argument is a boundary: a model may reason about what to
buy, and may not decide what money moves. A page that renders the model's
suggestion and the server's price in the same box asks the reader to take
that boundary on trust. So the boundary *is* the design.

Three rules, applied without exception:

  1. THE SEAM. Advisory content sits left of a literal vertical seam;
     authoritative content sits right of it. The seam is drawn, labelled,
     and never crossed. Where a two-column layout will not fit, the same
     distinction survives as surface treatment: `.advisory` is a dashed
     violet panel, `.authoritative` has a solid teal left rule.

  2. FACTS ARE MONOSPACED. Every hash, amount, timestamp, rule id, state
     name and latency renders in JetBrains Mono with tabular figures.
     Every sentence renders in Space Grotesk. You can tell what is a
     measurement and what is a claim without reading either.

  3. GLOW MEANS LIVE. Static elements never glow. A dot pulses at the
     moment its fetch resolves and at no other time, so motion on the
     page always corresponds to something actually happening.

Two type families from one Google Fonts link — the only external asset in
the product. Everything else is inline: no CDN, no build step, no
framework. Every animation has a `prefers-reduced-motion` override.
"""
from __future__ import annotations

BRAND_MARK = (
    '<svg width="15" height="15" viewBox="0 0 16 16" fill="none" '
    'xmlns="http://www.w3.org/2000/svg" aria-hidden="true">'
    '<path d="M4 11.5V4.5h4.2a2.1 2.1 0 010 4.2H4" stroke="currentColor" '
    'stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round"/></svg>'
)

FAVICON = (
    "data:image/svg+xml,%3Csvg xmlns='http://www.w3.org/2000/svg' "
    "viewBox='0 0 32 32'%3E%3Crect width='32' height='32' rx='9' "
    "fill='%2307070B'/%3E%3Cpath d='M9 23V9h7.6a4.2 4.2 0 010 8.4H9' "
    "stroke='%236C47FF' stroke-width='2.6' fill='none' "
    "stroke-linecap='round' stroke-linejoin='round'/%3E%3C/svg%3E"
)

FONT_LINK = (
    '<link rel="preconnect" href="https://fonts.googleapis.com">'
    '<link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>'
    '<link href="https://fonts.googleapis.com/css2?'
    'family=Space+Grotesk:wght@400;500;600;700&'
    'family=JetBrains+Mono:wght@400;500;700&display=swap" rel="stylesheet">'
)

TOKENS_CSS = """
:root{
  --bg-base:#07070B; --bg-panel:#0E0E16; --bg-inset:#0A0A10;
  --bg-raise:#141420;
  --border:#1C1C2A; --border-hi:#2A2A3E;

  --violet:#6C47FF; --violet-soft:rgba(108,71,255,.13);
  --violet-line:rgba(108,71,255,.42);
  --teal:#2DD4BF;   --teal-soft:rgba(45,212,191,.11);
  --red:#FF4D5E;    --red-soft:rgba(255,77,94,.11);
  --amber:#FFB224;  --amber-soft:rgba(255,178,36,.11);

  --text-hi:#ECECF4; --text-mid:#9A9AAC; --text-dim:#55556A;

  --r-panel:10px; --r-ctl:6px; --r-chip:3px;
  --shadow:0 8px 24px rgba(0,0,0,.45);

  --sans:"Space Grotesk",system-ui,-apple-system,"Segoe UI",Roboto,sans-serif;
  --mono:"JetBrains Mono",ui-monospace,"SF Mono",Consolas,Menlo,monospace;
}

*,*::before,*::after{box-sizing:border-box;margin:0;padding:0}
html{-webkit-text-size-adjust:100%;scroll-behavior:smooth}
body{
  background:var(--bg-base);color:var(--text-hi);font-family:var(--sans);
  font-size:15px;line-height:1.6;-webkit-font-smoothing:antialiased;
  min-height:100vh;
}
img{max-width:100%;display:block}
button{cursor:pointer;font:inherit;border:none;background:none;color:inherit}
input,select,textarea{font:inherit;color:inherit}
a{color:var(--violet);text-decoration:none}
a:hover{color:#8B6BFF}
::selection{background:var(--violet);color:#fff}
:focus-visible{outline:2px solid var(--violet);outline-offset:2px;border-radius:var(--r-ctl)}
.sr-only{position:absolute;width:1px;height:1px;overflow:hidden;clip:rect(0 0 0 0);white-space:nowrap}
.wrap{max-width:1440px;margin:0 auto;padding:0 24px}

/* RULE 2 — every fact is monospaced, every sentence is not. */
.m,.num,code,kbd,pre{
  font-family:var(--mono);font-variant-numeric:tabular-nums;
  font-feature-settings:"tnum" 1;letter-spacing:-.01em;
}
code{background:var(--bg-inset);border:1px solid var(--border);
  border-radius:var(--r-chip);padding:1px 5px;font-size:.88em;color:var(--text-mid)}

/* RULE 1 — the two surfaces, and the seam between them. */
.advisory{
  background:var(--violet-soft);border:1px dashed var(--violet-line);
  border-radius:var(--r-panel);padding:16px 18px;
}
.authoritative{
  background:var(--bg-panel);border:1px solid var(--border);
  border-left:3px solid var(--teal);border-radius:var(--r-panel);
  padding:16px 18px;
}
.seam{
  display:grid;grid-template-columns:1fr 132px 1fr;gap:0;align-items:stretch;
  border:1px solid var(--border);border-radius:var(--r-panel);
  background:var(--bg-panel);overflow:hidden;
}
.seam-side{padding:20px 22px 22px;min-width:0}
.seam-side.model{background:var(--violet-soft)}
.seam-gutter{
  background:var(--bg-inset);
  border-left:1px dashed var(--violet-line);border-right:1px solid var(--teal);
  display:flex;align-items:center;justify-content:center;padding:16px 8px;
}
.seam-gutter span{
  writing-mode:vertical-rl;text-orientation:mixed;transform:rotate(180deg);
  font-family:var(--mono);font-size:10px;font-weight:700;letter-spacing:.32em;
  color:var(--text-dim);text-transform:uppercase;
}
.seam-k{
  font-family:var(--mono);font-size:10px;font-weight:700;letter-spacing:.16em;
  text-transform:uppercase;margin-bottom:12px;
}
.seam-side.model .seam-k{color:var(--violet)}
.seam-side.server .seam-k{color:var(--teal)}
.seam-list{list-style:none;font-size:13.5px;line-height:1.95;color:var(--text-mid)}
.seam-list li{padding-left:16px;position:relative}
.seam-list li::before{content:"";position:absolute;left:0;top:.72em;
  width:6px;height:1px;background:currentColor;opacity:.55}

/* chips */
.chip{
  display:inline-flex;align-items:center;gap:5px;font-family:var(--mono);
  font-size:10px;font-weight:700;letter-spacing:.09em;text-transform:uppercase;
  border-radius:var(--r-chip);padding:3px 7px;white-space:nowrap;line-height:1.5;
}
.chip-ok{color:var(--teal);background:var(--teal-soft);border:1px solid rgba(45,212,191,.3)}
.chip-bad{color:var(--red);background:var(--red-soft);border:1px solid rgba(255,77,94,.3)}
.chip-warn{color:var(--amber);background:var(--amber-soft);border:1px solid rgba(255,178,36,.3)}
.chip-violet{color:var(--violet);background:var(--violet-soft);border:1px solid var(--violet-line)}
.chip-dim{color:var(--text-dim);background:var(--bg-inset);border:1px solid var(--border)}

/* panels */
.panel{background:var(--bg-panel);border:1px solid var(--border);
  border-radius:var(--r-panel);padding:18px 20px}
.panel-head{display:flex;align-items:center;justify-content:space-between;
  gap:12px;flex-wrap:wrap;margin-bottom:12px}
.panel-title{font-size:14px;font-weight:600;letter-spacing:-.01em}
.panel-sub{font-size:12.5px;color:var(--text-dim)}

/* buttons */
.btn{display:inline-flex;align-items:center;gap:7px;font-size:12.5px;
  font-weight:600;border-radius:var(--r-ctl);padding:8px 14px;
  border:1px solid var(--border-hi);background:var(--bg-raise);
  color:var(--text-hi);transition:border-color .15s ease-out,background .15s ease-out}
.btn:hover:not(:disabled){border-color:var(--violet);background:#1A1A2C}
.btn:disabled{opacity:.4;cursor:not-allowed}
.btn-primary{background:var(--violet);border-color:var(--violet);color:#fff}
.btn-primary:hover:not(:disabled){background:#7C5AFF;border-color:#7C5AFF}
.btn-danger{background:var(--red-soft);border-color:rgba(255,77,94,.4);color:var(--red)}
.btn-danger:hover:not(:disabled){background:rgba(255,77,94,.2);border-color:var(--red)}
.btn.on{background:var(--violet);border-color:var(--violet);color:#fff}
.btn-sm{padding:5px 10px;font-size:11.5px}

/* form controls */
.field{width:100%;background:var(--bg-inset);border:1px solid var(--border);
  border-radius:var(--r-ctl);padding:9px 11px;color:var(--text-hi);
  font-family:var(--mono);font-size:12.5px}
.field:focus{border-color:var(--violet);outline:none}
.label{display:block;font-family:var(--mono);font-size:10px;font-weight:700;
  letter-spacing:.12em;text-transform:uppercase;color:var(--text-dim);margin-bottom:5px}

/* console output */
.out{font-family:var(--mono);font-size:11.5px;background:var(--bg-inset);
  border:1px solid var(--border);border-radius:var(--r-ctl);
  padding:13px 15px;overflow-x:auto;white-space:pre-wrap;word-break:break-word;
  line-height:1.7;margin-top:12px;max-height:460px;overflow-y:auto;color:var(--text-mid)}
.out:empty{display:none}
.out .ok{color:var(--teal)} .out .bad{color:var(--red)}
.out .warn{color:var(--amber)} .out .dim{color:var(--text-dim)}
.out .hi{color:var(--text-hi)} .out .vi{color:#8B6BFF}

/* three-state panels: every fetch surface has all three */
.state-loading{display:flex;align-items:center;gap:9px;font-size:12.5px;
  color:var(--text-dim);font-family:var(--mono)}
.skel{height:9px;border-radius:2px;background:linear-gradient(90deg,
  var(--bg-raise) 25%,#1E1E2E 50%,var(--bg-raise) 75%);
  background-size:200% 100%;animation:shimmer 1.4s linear infinite}
@keyframes shimmer{to{background-position:-200% 0}}
.state-error{border:1px solid var(--red);background:var(--red-soft);
  border-radius:var(--r-ctl);padding:11px 13px;font-size:12.5px;color:var(--red)}
.state-error .m{display:block;margin-top:4px;color:var(--text-mid);font-size:11.5px}
.state-empty{border:1px dashed var(--border-hi);border-radius:var(--r-ctl);
  padding:14px;font-size:12.5px;color:var(--text-dim);text-align:center}

/* NAV */
.nav{position:sticky;top:0;z-index:100;background:rgba(7,7,11,.92);
  backdrop-filter:blur(14px);border-bottom:1px solid var(--border)}
.nav-inner{max-width:1440px;margin:0 auto;padding:0 24px;display:flex;
  align-items:center;gap:16px;height:52px}
.brand{font-weight:700;font-size:15px;letter-spacing:-.02em;color:var(--text-hi);
  display:flex;align-items:center;gap:8px}
.brand:hover{color:var(--text-hi)}
.brand-icon{width:24px;height:24px;border-radius:6px;background:var(--bg-raise);
  border:1px solid var(--violet-line);color:var(--violet);
  display:flex;align-items:center;justify-content:center;flex-shrink:0}
.nav-links{display:flex;align-items:center;gap:2px;margin-left:10px}
.nav-link{font-size:12.5px;font-weight:500;color:var(--text-mid);
  padding:6px 11px;border-radius:var(--r-ctl)}
.nav-link:hover{background:var(--bg-panel);color:var(--text-hi)}
.nav-link.on{background:var(--bg-raise);color:var(--text-hi);
  box-shadow:inset 0 -2px 0 var(--violet)}
.nav-right{display:flex;align-items:center;gap:9px;margin-left:auto}
.nav-mode{font-family:var(--mono);font-size:10px;font-weight:700;
  letter-spacing:.1em;text-transform:uppercase;border-radius:var(--r-chip);
  padding:4px 8px;color:var(--text-dim);background:var(--bg-inset);
  border:1px solid var(--border)}
.nav-mode.live{color:var(--teal);background:var(--teal-soft);border-color:rgba(45,212,191,.3)}
.nav-mode.sim{color:var(--amber);background:var(--amber-soft);border-color:rgba(255,178,36,.3)}

/* M4 — a dot pulses only at the moment its fetch resolves */
.dot{width:7px;height:7px;border-radius:50%;background:var(--text-dim);flex-shrink:0}
.dot.ok{background:var(--teal)} .dot.bad{background:var(--red)}
.dot.warn{background:var(--amber)}
.dot.beat{animation:beat .55s ease-out}
@keyframes beat{
  0%{transform:scale(1);box-shadow:0 0 0 0 currentColor}
  40%{transform:scale(1.5);box-shadow:0 0 0 5px rgba(45,212,191,.22)}
  100%{transform:scale(1);box-shadow:0 0 0 0 rgba(45,212,191,0)}
}

/* M1 — staggered reveal of rows that already arrived from the server */
.stagger{opacity:0;transform:translateY(8px);animation:rise .22s ease-out forwards}
@keyframes rise{to{opacity:1;transform:none}}

/* M5 — the tamper cascade */
.cascade{animation:redshift .3s ease-out forwards}
@keyframes redshift{
  to{border-color:var(--red);background:var(--red-soft);color:var(--red)}
}

/* FOOTER */
.foot{border-top:1px solid var(--border);margin-top:52px;padding:20px 24px 40px;
  max-width:1440px;margin-left:auto;margin-right:auto;display:flex;
  justify-content:space-between;align-items:center;flex-wrap:wrap;gap:14px;
  font-size:12px;color:var(--text-dim)}
.foot a{color:var(--text-dim)}
.foot a:hover{color:var(--violet)}
.foot-links{display:flex;gap:16px;flex-wrap:wrap}

@media (prefers-reduced-motion:reduce){
  *,*::before,*::after{
    animation-duration:.001ms!important;animation-iteration-count:1!important;
    transition-duration:.001ms!important;scroll-behavior:auto!important;
  }
  .stagger{opacity:1;transform:none}
}
@media (max-width:900px){
  .seam{grid-template-columns:1fr}
  .seam-gutter{border:none;border-top:1px dashed var(--violet-line);
    border-bottom:1px solid var(--teal);padding:9px}
  .seam-gutter span{writing-mode:horizontal-tb;transform:none}
}
@media (max-width:680px){
  .nav-links{display:none}
  .wrap{padding:0 14px}
}
"""


def nav(active: str = "") -> str:
    def link(href: str, label: str, key: str) -> str:
        return (f'<a class="nav-link{" on" if key == active else ""}" '
                f'href="{href}">{label}</a>')

    return f"""<nav class="nav" aria-label="Main">
  <div class="nav-inner">
    <a class="brand" href="/">
      <span class="brand-icon">{BRAND_MARK}</span>SELLABLE
    </a>
    <div class="nav-links">
      {link("/", "Shop", "shop")}
      {link("/judge", "Cockpit", "judge")}
    </div>
    <div class="nav-right">
      <a href="/diagnostics" id="nav-mode" class="nav-mode" target="_blank"
         rel="noopener"
         title="Provider read from /diagnostics on every load — never hardcoded"
        >checking…</a>
    </div>
  </div>
</nav>"""


FOOTER = """<footer class="foot">
  <span>SELLABLE &middot; Razorpay AI Buildathon &middot; Track 01</span>
  <div class="foot-links">
    <a href="/judge">Cockpit</a>
    <a href="/audit/verify" target="_blank" rel="noopener">Audit chain</a>
    <a href="/gateway/proof" target="_blank" rel="noopener">Gateway proof</a>
    <a href="/.well-known/agent-manifest.json" target="_blank" rel="noopener">Agent manifest</a>
    <a href="/diagnostics" target="_blank" rel="noopener">Diagnostics</a>
    <a href="/docs" target="_blank" rel="noopener">API</a>
    <a href="https://github.com/HarshDubey23/SELLABLE" target="_blank"
       rel="noopener">Source</a>
  </div>
</footer>"""


# The provider label is read at load. A hardcoded "Razorpay test mode"
# badge is exactly the thing that keeps saying "live" after the keys are
# gone, so this never writes a default into the HTML.
PROVIDER_BADGE_JS = """
(function(){
  var el=document.getElementById('nav-mode'); if(!el) return;
  fetch('/diagnostics').then(function(r){return r.json()}).then(function(d){
    var p=(d.payments)||{}, live=p.provider!=='simulated';
    el.textContent=live?'razorpay test':'simulated';
    el.classList.add(live?'live':'sim');
    el.title=(p.provider_description||'')+' - read from /diagnostics';
  }).catch(function(e){ el.textContent='provider unknown'; el.title=String(e); });
})();
"""


def head(title: str, extra_css: str = "") -> str:
    return f"""<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>{title}</title>
<link rel="icon" href="{FAVICON}">
{FONT_LINK}
<style>{TOKENS_CSS}{extra_css}</style>
</head>
<body>"""
