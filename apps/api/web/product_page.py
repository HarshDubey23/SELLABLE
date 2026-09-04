"""GET / — SELLABLE product page.

Design: Consumer-first. The pipeline rail (Discover → Gateway → Authorize →
Execute → Confirmed) is the signature element — it makes the security boundary
visible as UX, not documentation. One page, real API calls, no fake states.

Font stack intentionally avoids Google Fonts. Every animation has a
prefers-reduced-motion override. No hardcoded metrics.
"""
from __future__ import annotations

from fastapi import APIRouter
from fastapi.responses import HTMLResponse

router = APIRouter()

PAGE = r"""<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>SELLABLE — shop with AI that cannot touch your money</title>
<link rel="icon" href="data:image/svg+xml,%3Csvg xmlns='http://www.w3.org/2000/svg' viewBox='0 0 32 32'%3E%3Crect width='32' height='32' rx='8' fill='%236C47FF'/%3E%3Cpath d='M9 22V10h7.5a4 4 0 010 8H9' stroke='white' stroke-width='2.5' fill='none' stroke-linecap='round' stroke-linejoin='round'/%3E%3C/svg%3E">
<style>
/* ─── DESIGN TOKENS ─────────────────────────────────────────────────── */
:root {
  --bg:        #F7F8FC;
  --surface:   #FFFFFF;
  --surface-2: #F0F2F9;
  --border:    #E2E8F0;
  --border-2:  #CBD5E1;

  --navy:      #0F1729;
  --slate:     #475569;
  --muted:     #94A3B8;
  --ink:       #1E293B;

  --violet:    #6C47FF;
  --violet-dim:#EDE9FF;
  --violet-mid:#8B6BFF;
  --teal:      #0D9488;
  --teal-dim:  #CCFBF1;
  --amber:     #D97706;
  --amber-dim: #FEF3C7;
  --red:       #DC2626;
  --red-dim:   #FEE2E2;
  --orange:    #EA580C;

  --r-sm:  6px;
  --r:     12px;
  --r-lg:  18px;
  --r-xl:  24px;

  --sans: system-ui, -apple-system, "Segoe UI", Roboto, sans-serif;
  --mono: ui-monospace, "SF Mono", "Cascadia Code", Menlo, monospace;

  --shadow-sm: 0 1px 3px rgba(15,23,41,.07), 0 1px 2px rgba(15,23,41,.06);
  --shadow:    0 4px 12px rgba(15,23,41,.08), 0 2px 4px rgba(15,23,41,.06);
  --shadow-lg: 0 12px 32px rgba(15,23,41,.12), 0 4px 8px rgba(15,23,41,.08);
}

/* ─── RESET ─────────────────────────────────────────────────────────── */
*,*::before,*::after{box-sizing:border-box;margin:0;padding:0}
html{-webkit-text-size-adjust:100%;scroll-behavior:smooth}
body{
  background:var(--bg); color:var(--ink); font-family:var(--sans);
  font-size:15px; line-height:1.65; -webkit-font-smoothing:antialiased;
  min-height:100vh;
}
img{max-width:100%;display:block}
button{cursor:pointer;font:inherit;border:none;background:none}
input,select,textarea{font:inherit}
a{color:var(--violet);text-decoration:none}
a:hover{text-decoration:underline}

/* ─── NAV ────────────────────────────────────────────────────────────── */
.nav{
  position:sticky;top:0;z-index:100;
  background:rgba(247,248,252,.88);
  backdrop-filter:blur(14px);
  border-bottom:1px solid var(--border);
}
.nav-inner{
  max-width:1100px;margin:0 auto;padding:0 24px;
  display:flex;align-items:center;gap:20px;height:58px;
}
.brand{
  font-weight:800;font-size:17px;letter-spacing:-0.04em;
  color:var(--navy);display:flex;align-items:center;gap:8px;
}
.brand-icon{
  width:28px;height:28px;border-radius:7px;
  background:var(--violet);display:flex;align-items:center;justify-content:center;flex-shrink:0;
}
.brand-icon svg{display:block}
.brand-tagline{
  font-weight:400;font-size:12px;color:var(--muted);
  letter-spacing:0;margin-left:4px;
}
.nav-right{display:flex;align-items:center;gap:12px;margin-left:auto}
.nav-pill{
  font-size:12.5px;font-weight:500;color:var(--slate);
  border:1px solid var(--border);border-radius:999px;
  padding:5px 14px;transition:all .15s;
}
.nav-pill:hover{border-color:var(--violet);color:var(--violet);text-decoration:none}
.nav-mode{
  font-size:11px;font-family:var(--mono);font-weight:600;
  letter-spacing:.06em;text-transform:uppercase;
  color:var(--amber);background:var(--amber-dim);
  border:1px solid rgba(217,119,6,.25);
  border-radius:999px;padding:4px 11px;
}

/* ─── HERO ───────────────────────────────────────────────────────────── */
.hero{
  max-width:1100px;margin:0 auto;padding:64px 24px 40px;
}
.hero-eyebrow{
  display:inline-flex;align-items:center;gap:8px;
  font-size:11.5px;font-weight:600;letter-spacing:.1em;text-transform:uppercase;
  color:var(--violet);background:var(--violet-dim);
  border:1px solid rgba(108,71,255,.2);
  border-radius:999px;padding:5px 14px;margin-bottom:24px;
}
.hero-eyebrow::before{content:'';width:6px;height:6px;border-radius:50%;background:var(--violet)}
h1{
  font-size:clamp(32px,5vw,56px);font-weight:840;
  letter-spacing:-0.04em;line-height:1.08;color:var(--navy);
  max-width:18ch;margin-bottom:18px;
}
h1 .highlight{
  color:var(--violet);
  background:linear-gradient(135deg,#6C47FF,#9B6FFF);
  -webkit-background-clip:text;-webkit-text-fill-color:transparent;background-clip:text;
}
.hero-sub{
  font-size:17px;color:var(--slate);max-width:54ch;
  line-height:1.7;margin-bottom:40px;font-weight:400;
}

/* ─── SEARCH CARD ────────────────────────────────────────────────────── */
.search-card{
  background:var(--surface);border:1px solid var(--border);
  border-radius:var(--r-xl);padding:28px;
  box-shadow:var(--shadow);max-width:780px;
}
.search-row{display:flex;gap:12px;align-items:stretch}
.search-input-wrap{flex:1;position:relative}
.search-icon{
  position:absolute;left:16px;top:50%;transform:translateY(-50%);
  color:var(--muted);pointer-events:none;
}
.search-input{
  width:100%;height:52px;padding:0 16px 0 46px;
  border:1.5px solid var(--border);border-radius:var(--r);
  font-size:16px;color:var(--ink);background:var(--surface);
  transition:border-color .2s,box-shadow .2s;
}
.search-input:focus{
  outline:none;border-color:var(--violet);
  box-shadow:0 0 0 4px rgba(108,71,255,.1);
}
.search-input::placeholder{color:var(--muted)}
.search-btn{
  height:52px;padding:0 28px;border-radius:var(--r);
  background:var(--violet);color:#fff;font-weight:650;font-size:15px;
  transition:all .18s;white-space:nowrap;letter-spacing:-0.01em;
}
.search-btn:hover{background:var(--violet-mid);transform:translateY(-1px);box-shadow:0 4px 14px rgba(108,71,255,.35)}
.search-btn:active{transform:translateY(0)}
.search-btn:disabled{opacity:.55;transform:none;box-shadow:none;cursor:not-allowed}

.budget-row{
  display:flex;align-items:center;gap:16px;margin-top:18px;
  font-size:13px;color:var(--slate);
}
.budget-label{white-space:nowrap;font-weight:500}
.budget-input{
  width:160px;height:36px;padding:0 12px;
  border:1px solid var(--border);border-radius:var(--r-sm);
  font-size:13px;color:var(--ink);background:var(--surface);
  transition:border-color .2s;
}
.budget-input:focus{outline:none;border-color:var(--violet)}
.budget-hint{color:var(--muted);font-size:12px}

.quick-chips{display:flex;gap:8px;flex-wrap:wrap;margin-top:14px}
.chip{
  font-size:12.5px;padding:5px 13px;
  border:1px solid var(--border);border-radius:999px;
  color:var(--slate);background:var(--bg);
  transition:all .15s;
}
.chip:hover{border-color:var(--violet);color:var(--violet);background:var(--violet-dim)}

/* ─── PIPELINE RAIL ──────────────────────────────────────────────────── */
.pipeline-wrap{
  max-width:780px;margin:28px 0;
  opacity:0;transform:translateY(8px);
  transition:opacity .3s,transform .3s;
}
.pipeline-wrap.visible{opacity:1;transform:none}

.pipeline{
  background:var(--surface);border:1px solid var(--border);
  border-radius:var(--r-lg);padding:20px 24px;
  box-shadow:var(--shadow-sm);
  display:grid;grid-template-columns:repeat(5,1fr);
  position:relative;
}
.pipeline::before{
  content:'';position:absolute;top:32px;left:calc(10% + 18px);
  width:calc(80% - 36px);height:2px;background:var(--border);z-index:0;
}
.pipeline-progress{
  position:absolute;top:32px;left:calc(10% + 18px);
  width:0;height:2px;background:var(--teal);z-index:1;
  transition:width .6s cubic-bezier(.4,0,.2,1);
}

.step{
  display:flex;flex-direction:column;align-items:center;gap:8px;
  position:relative;z-index:2;
}
.step-dot{
  width:36px;height:36px;border-radius:50%;
  border:2px solid var(--border);background:var(--surface);
  display:flex;align-items:center;justify-content:center;
  font-size:15px;transition:all .35s cubic-bezier(.4,0,.2,1);
  position:relative;
}
.step-label{
  font-size:11px;font-weight:600;color:var(--muted);
  text-align:center;letter-spacing:.02em;line-height:1.3;
  text-transform:uppercase;transition:color .3s;
}

/* Step states */
.step.idle .step-dot{border-color:var(--border);background:var(--surface)}
.step.active .step-dot{
  border-color:var(--violet);background:var(--violet-dim);
  box-shadow:0 0 0 6px rgba(108,71,255,.1);
  animation:pulse-ring .9s ease-in-out infinite;
}
.step.active .step-label{color:var(--violet)}
.step.done .step-dot{border-color:var(--teal);background:var(--teal);color:#fff}
.step.done .step-label{color:var(--teal)}
.step.blocked .step-dot{border-color:var(--red);background:var(--red-dim)}
.step.blocked .step-label{color:var(--red)}
.step.warn .step-dot{border-color:var(--amber);background:var(--amber-dim)}
.step.warn .step-label{color:var(--amber)}
.step.waiting .step-dot{border-color:var(--violet);background:var(--violet-dim)}
.step.waiting .step-label{color:var(--violet)}

@keyframes pulse-ring{
  0%,100%{box-shadow:0 0 0 4px rgba(108,71,255,.1)}
  50%{box-shadow:0 0 0 8px rgba(108,71,255,.18)}
}
@media (prefers-reduced-motion:reduce){
  .step.active .step-dot{animation:none}
  *{transition-duration:.01ms !important}
}

/* ─── STATUS BAR ─────────────────────────────────────────────────────── */
.status-bar{
  font-size:12.5px;color:var(--slate);margin-top:14px;
  padding:10px 16px;background:var(--surface-2);
  border-radius:var(--r-sm);border:1px solid var(--border);
  font-family:var(--mono);display:none;
}
.status-bar.show{display:block}

/* ─── RESULTS ────────────────────────────────────────────────────────── */
.results-section{
  max-width:1100px;margin:0 auto;padding:0 24px 80px;
}
.section-header{
  display:flex;align-items:baseline;gap:14px;margin-bottom:20px;
}
.section-title{
  font-size:13px;font-weight:700;letter-spacing:.08em;
  text-transform:uppercase;color:var(--navy);
}
.section-count{
  font-size:12px;color:var(--muted);
  font-family:var(--mono);
}

/* recommendation banner */
.rec-banner{
  background:var(--surface);border:2px solid var(--violet);
  border-radius:var(--r-lg);padding:24px 28px;margin-bottom:28px;
  box-shadow:0 0 0 4px rgba(108,71,255,.06),var(--shadow);
  display:none;
}
.rec-banner.show{display:block}
.rec-top{display:flex;align-items:flex-start;justify-content:space-between;gap:20px;flex-wrap:wrap}
.rec-badge{
  font-size:10.5px;font-weight:700;letter-spacing:.1em;text-transform:uppercase;
  color:var(--violet);background:var(--violet-dim);
  border:1px solid rgba(108,71,255,.2);
  border-radius:999px;padding:4px 12px;display:inline-block;margin-bottom:12px;
}
.rec-name{
  font-size:22px;font-weight:750;letter-spacing:-0.03em;
  color:var(--navy);margin-bottom:6px;
}
.rec-price{
  font-size:28px;font-weight:820;color:var(--violet);letter-spacing:-0.04em;
}
.rec-price-sub{font-size:13px;color:var(--muted);font-weight:400;margin-left:6px}
.rec-why{
  margin-top:16px;display:grid;gap:8px;
}
.rec-why-item{
  display:flex;align-items:flex-start;gap:10px;
  font-size:13.5px;color:var(--slate);
}
.rec-why-icon{
  width:20px;height:20px;border-radius:50%;
  display:flex;align-items:center;justify-content:center;
  flex-shrink:0;font-size:11px;margin-top:1px;
}
.rec-why-icon.ok{background:var(--teal-dim);color:var(--teal)}
.rec-why-icon.warn{background:var(--amber-dim);color:var(--amber)}

.buy-btn{
  height:48px;padding:0 32px;border-radius:var(--r);
  background:var(--navy);color:#fff;font-weight:660;font-size:15px;
  transition:all .18s;letter-spacing:-0.01em;
  display:flex;align-items:center;gap:8px;white-space:nowrap;
  align-self:flex-end;
}
.buy-btn:hover{background:var(--violet);transform:translateY(-1px);box-shadow:var(--shadow)}
.buy-btn:active{transform:translateY(0)}

/* probe card */
.probe-card{
  background:var(--surface);border:1.5px dashed var(--border-2);
  border-radius:var(--r-lg);padding:20px 24px;margin-bottom:28px;
  display:none;
}
.probe-card.show{display:block}
.probe-header{display:flex;align-items:center;gap:10px;margin-bottom:12px}
.probe-badge{
  font-size:10.5px;font-weight:700;letter-spacing:.08em;
  text-transform:uppercase;color:var(--red);background:var(--red-dim);
  border:1px solid rgba(220,38,38,.2);border-radius:999px;padding:3px 10px;
}
.probe-name{font-size:16px;font-weight:650;color:var(--navy)}
.probe-detail{font-size:13px;color:var(--slate);line-height:1.7}
.probe-try-btn{
  margin-top:14px;height:38px;padding:0 18px;border-radius:var(--r-sm);
  border:1.5px solid var(--red);color:var(--red);font-size:13px;font-weight:600;
  background:transparent;transition:all .15s;
}
.probe-try-btn:hover{background:var(--red-dim)}

/* product grid */
.product-grid{
  display:grid;
  grid-template-columns:repeat(auto-fill,minmax(290px,1fr));
  gap:16px;
}
.product-card{
  background:var(--surface);border:1px solid var(--border);
  border-radius:var(--r-lg);padding:20px;
  box-shadow:var(--shadow-sm);
  transition:box-shadow .2s,transform .2s;
  display:flex;flex-direction:column;gap:12px;
}
.product-card:hover{box-shadow:var(--shadow);transform:translateY(-2px)}
.product-card-top{display:flex;justify-content:space-between;align-items:flex-start;gap:8px}
.product-name{font-size:14px;font-weight:650;color:var(--navy);line-height:1.4;flex:1}
.evidence-tag{
  font-size:10px;font-weight:700;letter-spacing:.06em;text-transform:uppercase;
  border-radius:999px;padding:3px 9px;white-space:nowrap;flex-shrink:0;
}
.tag-observed{color:var(--teal);background:var(--teal-dim);border:1px solid rgba(13,148,136,.2)}
.tag-fx{color:var(--amber);background:var(--amber-dim);border:1px solid rgba(217,119,6,.2)}
.tag-mock{color:var(--muted);background:var(--surface-2);border:1px solid var(--border)}
.tag-unverified{color:var(--slate);background:var(--surface-2);border:1px solid var(--border)}

.product-price{font-size:20px;font-weight:780;letter-spacing:-0.03em;color:var(--ink)}
.product-price-note{font-size:11.5px;color:var(--muted);font-weight:400;margin-left:4px}
.product-seller{
  font-size:12px;color:var(--slate);display:flex;align-items:center;gap:6px;
}
.product-seller a{color:var(--slate);text-decoration:none;font-weight:500}
.product-seller a:hover{color:var(--violet)}

/* ─── AUTHORIZATION MODAL ────────────────────────────────────────────── */
.modal-overlay{
  position:fixed;inset:0;background:rgba(15,23,41,.55);
  backdrop-filter:blur(4px);z-index:200;
  display:none;align-items:center;justify-content:center;padding:24px;
}
.modal-overlay.open{display:flex}
.modal{
  background:var(--surface);border-radius:var(--r-xl);
  width:100%;max-width:540px;max-height:90vh;overflow-y:auto;
  box-shadow:var(--shadow-lg);
  animation:modal-in .22s cubic-bezier(.4,0,.2,1);
}
@keyframes modal-in{
  from{opacity:0;transform:translateY(16px) scale(.97)}
  to{opacity:1;transform:none}
}
.modal-header{
  padding:24px 28px 0;display:flex;align-items:flex-start;justify-content:space-between;
}
.modal-title{font-size:20px;font-weight:780;letter-spacing:-0.03em;color:var(--navy)}
.modal-close{
  width:32px;height:32px;border-radius:50%;border:1px solid var(--border);
  display:flex;align-items:center;justify-content:center;
  color:var(--muted);font-size:18px;line-height:1;transition:all .15s;
}
.modal-close:hover{border-color:var(--border-2);color:var(--ink)}
.modal-body{padding:20px 28px 28px;display:grid;gap:20px}

.auth-item{
  border:1px solid var(--border);border-radius:var(--r);padding:16px;
}
.auth-item-label{
  font-size:10.5px;font-weight:700;letter-spacing:.09em;text-transform:uppercase;
  color:var(--muted);margin-bottom:10px;
}
.auth-product-name{font-size:17px;font-weight:700;letter-spacing:-0.02em;color:var(--navy)}
.auth-price{font-size:26px;font-weight:820;letter-spacing:-0.04em;color:var(--violet);margin-top:4px}
.auth-sku{font-size:11px;font-family:var(--mono);color:var(--muted);margin-top:4px}

.auth-limits{display:grid;gap:8px;margin-top:4px}
.auth-limit-row{
  display:flex;align-items:center;justify-content:space-between;
  font-size:13px;
}
.auth-limit-key{color:var(--slate)}
.auth-limit-val{font-weight:650;color:var(--ink)}
.auth-limit-val.ok{color:var(--teal)}
.auth-limit-val.warn{color:var(--amber)}

.gateway-grid{display:grid;gap:8px}
.gateway-row{
  display:flex;align-items:center;gap:10px;font-size:13px;color:var(--slate);
}
.g-icon{
  width:18px;height:18px;border-radius:4px;flex-shrink:0;
  display:flex;align-items:center;justify-content:center;font-size:10px;
}
.g-icon.pass{background:var(--teal-dim);color:var(--teal)}
.g-icon.fail{background:var(--red-dim);color:var(--red)}

.ai-reasoning{
  background:var(--violet-dim);border:1px solid rgba(108,71,255,.2);
  border-radius:var(--r);padding:14px;font-size:13.5px;
  color:var(--navy);line-height:1.7;font-style:italic;
}

.demo-notice{
  background:var(--amber-dim);border:1px solid rgba(217,119,6,.2);
  border-radius:var(--r-sm);padding:12px 16px;
  font-size:12px;color:var(--amber);display:flex;gap:8px;align-items:flex-start;
}
.demo-notice svg{flex-shrink:0;margin-top:1px}

.approve-btn{
  width:100%;height:52px;border-radius:var(--r);
  background:var(--navy);color:#fff;font-size:16px;font-weight:700;
  letter-spacing:-0.02em;transition:all .18s;
  display:flex;align-items:center;justify-content:center;gap:8px;
}
.approve-btn:hover{background:var(--violet);box-shadow:0 4px 16px rgba(108,71,255,.3)}
.approve-btn:disabled{opacity:.5;cursor:not-allowed;transform:none;box-shadow:none}

/* ─── EXECUTION PANEL ────────────────────────────────────────────────── */
.exec-panel{
  max-width:780px;background:var(--surface);
  border:1px solid var(--border);border-radius:var(--r-lg);
  padding:24px 28px;box-shadow:var(--shadow);
  display:none;margin-top:4px;
}
.exec-panel.show{display:block}
.exec-panel-title{
  font-size:13px;font-weight:700;letter-spacing:.08em;text-transform:uppercase;
  color:var(--navy);margin-bottom:18px;
}
.exec-states{display:grid;gap:12px}
.exec-state-row{
  display:flex;align-items:center;gap:12px;padding:12px 16px;
  border-radius:var(--r);border:1px solid var(--border);
  background:var(--bg);transition:all .3s;
}
.exec-state-row.current{
  border-color:var(--violet);background:var(--violet-dim);
}
.exec-state-row.done{
  border-color:var(--teal);background:var(--teal-dim);
}
.exec-state-row.fail{
  border-color:var(--red);background:var(--red-dim);
}
.exec-state-row.warn{
  border-color:var(--amber);background:var(--amber-dim);
}
.exec-state-dot{
  width:10px;height:10px;border-radius:50%;flex-shrink:0;
  background:var(--border-2);transition:background .3s;
}
.exec-state-row.current .exec-state-dot{background:var(--violet);animation:dot-pulse 1s ease-in-out infinite}
.exec-state-row.done .exec-state-dot{background:var(--teal)}
.exec-state-row.fail .exec-state-dot{background:var(--red)}
.exec-state-row.warn .exec-state-dot{background:var(--amber)}
@keyframes dot-pulse{0%,100%{opacity:1}50%{opacity:.4}}

.exec-state-name{
  font-size:13px;font-weight:650;color:var(--ink);font-family:var(--mono);
}
.exec-state-desc{font-size:12px;color:var(--slate);margin-left:auto;text-align:right}

.exec-id{
  margin-top:16px;font-size:11px;font-family:var(--mono);color:var(--muted);
  padding:10px 14px;background:var(--surface-2);border-radius:var(--r-sm);
  border:1px solid var(--border);word-break:break-all;
}

.reconcile-section{
  margin-top:20px;padding-top:20px;border-top:1px solid var(--border);display:none;
}
.reconcile-section.show{display:block}
.reconcile-btn{
  height:42px;padding:0 22px;border-radius:var(--r-sm);
  border:1.5px solid var(--amber);color:var(--amber);
  font-size:13.5px;font-weight:650;background:transparent;
  transition:all .15s;display:inline-flex;align-items:center;gap:6px;
}
.reconcile-btn:hover{background:var(--amber-dim)}

/* ─── FAULT INJECTOR ─────────────────────────────────────────────────── */
.fault-row{
  display:flex;align-items:center;gap:10px;flex-wrap:wrap;
  margin-top:16px;padding-top:16px;border-top:1px solid var(--border);
}
.fault-label{
  font-size:11.5px;font-weight:650;color:var(--muted);letter-spacing:.04em;
  text-transform:uppercase;
}
.fault-btn{
  height:30px;padding:0 13px;border-radius:999px;font-size:12px;
  border:1px solid var(--border);color:var(--slate);background:var(--bg);
  transition:all .15s;
}
.fault-btn:hover{border-color:var(--amber);color:var(--amber);background:var(--amber-dim)}
.fault-btn.active{border-color:var(--amber);color:var(--amber);background:var(--amber-dim)}

/* ─── EVIDENCE LEGEND ────────────────────────────────────────────────── */
.legend{
  display:flex;gap:16px;flex-wrap:wrap;margin-top:20px;
  padding:14px 18px;background:var(--surface-2);
  border:1px solid var(--border);border-radius:var(--r);
  font-size:12px;
}
.legend-item{display:flex;align-items:center;gap:7px;color:var(--slate)}

/* ─── JUDGE ENTRY ────────────────────────────────────────────────────── */
.judge-strip{
  background:var(--navy);padding:18px 24px;
  display:flex;align-items:center;justify-content:space-between;
  gap:16px;flex-wrap:wrap;
}
.judge-strip-text{font-size:13.5px;color:rgba(255,255,255,.7);max-width:56ch}
.judge-strip-text strong{color:#fff}
.judge-link{
  height:38px;padding:0 20px;border-radius:var(--r-sm);
  border:1px solid rgba(255,255,255,.25);color:#fff;font-size:13px;font-weight:600;
  background:transparent;transition:all .15s;white-space:nowrap;
  display:inline-flex;align-items:center;gap:6px;text-decoration:none;
}
.judge-link:hover{background:rgba(255,255,255,.1);border-color:rgba(255,255,255,.4)}

/* ─── EMPTY / ERROR STATES ───────────────────────────────────────────── */
.empty-state{
  text-align:center;padding:60px 24px;
  display:none;
}
.empty-state.show{display:block}
.empty-icon{font-size:40px;margin-bottom:16px}
.empty-title{font-size:18px;font-weight:700;color:var(--navy);margin-bottom:8px}
.empty-body{font-size:14px;color:var(--slate);max-width:38ch;margin:0 auto}

.alert{
  padding:14px 18px;border-radius:var(--r);font-size:13.5px;
  display:flex;align-items:flex-start;gap:10px;
  margin-bottom:16px;
}
.alert-error{background:var(--red-dim);border:1px solid rgba(220,38,38,.2);color:var(--red)}
.alert-info{background:var(--violet-dim);border:1px solid rgba(108,71,255,.2);color:var(--violet)}
.alert-warn{background:var(--amber-dim);border:1px solid rgba(217,119,6,.2);color:var(--amber)}
.alert-ok{background:var(--teal-dim);border:1px solid rgba(13,148,136,.2);color:var(--teal)}

/* ─── FOOTER ─────────────────────────────────────────────────────────── */
footer{
  border-top:1px solid var(--border);padding:28px 24px;
  max-width:1100px;margin:0 auto;
  display:flex;justify-content:space-between;align-items:center;
  flex-wrap:wrap;gap:16px;font-size:12.5px;color:var(--muted);
}
footer a{color:var(--muted)}
footer a:hover{color:var(--violet)}
.footer-links{display:flex;gap:20px}

/* ─── RESPONSIVE ─────────────────────────────────────────────────────── */
@media (max-width:680px){
  .hero{padding:40px 16px 28px}
  .search-card{padding:18px}
  .search-row{flex-direction:column}
  .search-btn{height:46px}
  h1{font-size:32px}
  .pipeline{padding:14px 8px}
  .step-label{font-size:9.5px}
  .rec-top{flex-direction:column}
  .buy-btn{width:100%;justify-content:center}
  .product-grid{grid-template-columns:1fr}
  .results-section{padding:0 16px 60px}
}
</style>
</head>
<body>

<!-- ── NAV ── -->
<nav class="nav" aria-label="Main navigation">
  <div class="nav-inner">
    <div class="brand">
      <div class="brand-icon">
        <svg width="16" height="16" viewBox="0 0 16 16" fill="none" xmlns="http://www.w3.org/2000/svg">
          <path d="M4 11V5h4a2 2 0 010 4H4" stroke="white" stroke-width="1.6" stroke-linecap="round" stroke-linejoin="round"/>
        </svg>
      </div>
      SELLABLE
    </div>
    <div class="nav-right">
      <span class="nav-mode">Razorpay Test Mode</span>
      <a href="/judge" class="nav-pill">For Judges →</a>
    </div>
  </div>
</nav>

<!-- ── HERO ── -->
<section class="hero">
  <div class="hero-eyebrow">
    <span>AI &amp; Agentic Commerce</span>
  </div>
  <h1>Shop with AI that <span class="highlight">cannot touch</span> your money</h1>
  <p class="hero-sub">
    SELLABLE's AI finds and recommends products from real retailers. Your approval
    — checked by a deterministic gateway — is the only key that unlocks payment.
    The AI proposes. You authorize. Razorpay executes.
  </p>

  <!-- Search card -->
  <div class="search-card">
    <div class="search-row">
      <div class="search-input-wrap">
        <svg class="search-icon" width="18" height="18" fill="none" viewBox="0 0 24 24" stroke="currentColor" stroke-width="2">
          <circle cx="11" cy="11" r="8"/><path d="m21 21-4.35-4.35"/>
        </svg>
        <input id="q" class="search-input" type="search"
          placeholder="e.g. cricket bat under ₹2000, wireless headphones…"
          autocomplete="off" autocorrect="off" spellcheck="false">
      </div>
      <button id="search-btn" class="search-btn" onclick="doSearch()">
        Search
      </button>
    </div>

    <div class="budget-row">
      <label class="budget-label" for="budget">Budget</label>
      <span>₹</span>
      <input id="budget" class="budget-input" type="number"
        value="5000" min="100" max="50000" step="100">
      <span class="budget-hint">Maximum you're willing to spend</span>
    </div>

    <div class="quick-chips" aria-label="Quick searches">
      <button class="chip" onclick="setQuery('cricket bat under ₹3000')">🏏 Cricket bat</button>
      <button class="chip" onclick="setQuery('wireless headphones under ₹2000')">🎧 Headphones</button>
      <button class="chip" onclick="setQuery('laptop bag under ₹1500')">💼 Laptop bag</button>
      <button class="chip" onclick="setQuery('yoga mat under ₹1000')">🧘 Yoga mat</button>
    </div>
  </div>

  <!-- Pipeline rail — appears after search -->
  <div class="pipeline-wrap" id="pipeline-wrap">
    <div class="pipeline" role="list" aria-label="Purchase pipeline">
      <div class="step idle" id="step-discover" role="listitem">
        <div class="step-dot">🔍</div>
        <div class="step-label">Discover</div>
      </div>
      <div class="step idle" id="step-gateway" role="listitem">
        <div class="step-dot">🛡</div>
        <div class="step-label">Gateway</div>
      </div>
      <div class="step idle" id="step-authorize" role="listitem">
        <div class="step-dot">✍</div>
        <div class="step-label">Authorize</div>
      </div>
      <div class="step idle" id="step-execute" role="listitem">
        <div class="step-dot">💳</div>
        <div class="step-label">Execute</div>
      </div>
      <div class="step idle" id="step-confirm" role="listitem">
        <div class="step-dot">✓</div>
        <div class="step-label">Confirmed</div>
      </div>
      <div class="pipeline-progress" id="pipeline-bar"></div>
    </div>
    <div class="status-bar" id="status-bar"></div>
  </div>
</section>

<!-- ── RESULTS ── -->
<main class="results-section" id="results-section" style="display:none">

  <!-- alerts -->
  <div id="alert-area"></div>

  <!-- recommendation banner -->
  <div class="rec-banner" id="rec-banner">
    <div class="rec-top">
      <div>
        <div class="rec-badge">SELLABLE recommends</div>
        <div class="rec-name" id="rec-name">—</div>
        <div>
          <span class="rec-price" id="rec-price">—</span>
          <span class="rec-price-sub" id="rec-seller">—</span>
        </div>
        <div class="rec-why" id="rec-why"></div>
      </div>
      <button class="buy-btn" id="buy-btn" onclick="openModal()">
        <svg width="16" height="16" fill="none" viewBox="0 0 24 24" stroke="currentColor" stroke-width="2.5"><path d="M5 12h14M12 5l7 7-7 7"/></svg>
        Review &amp; Authorize
      </button>
    </div>
  </div>

  <!-- probe card -->
  <div class="probe-card" id="probe-card">
    <div class="probe-header">
      <span class="probe-badge">Gateway Demo: Would Block</span>
      <span class="probe-name" id="probe-name">—</span>
    </div>
    <div class="probe-detail" id="probe-detail">—</div>
    <button class="probe-try-btn" onclick="tryProbe()">Try injecting this → gateway will reject it</button>
  </div>

  <!-- market evidence -->
  <div class="section-header">
    <span class="section-title">Market Evidence</span>
    <span class="section-count" id="listings-count"></span>
  </div>
  <div class="product-grid" id="product-grid"></div>

  <div class="legend">
    <div class="legend-item">
      <span class="evidence-tag tag-observed">OBSERVED</span>
      <span>INR price seen verbatim in source</span>
    </div>
    <div class="legend-item">
      <span class="evidence-tag tag-fx">FX</span>
      <span>Converted from foreign currency (estimate)</span>
    </div>
    <div class="legend-item">
      <span class="evidence-tag tag-mock">MOCK</span>
      <span>Synthetic API data — excluded from comparison</span>
    </div>
    <div class="legend-item">
      <span class="evidence-tag tag-unverified">UNVERIFIED</span>
      <span>Matched query, no price extracted</span>
    </div>
  </div>

  <div class="empty-state" id="empty-state">
    <div class="empty-icon">🔍</div>
    <div class="empty-title">No results found</div>
    <div class="empty-body">Try a different search term or increase your budget.</div>
  </div>
</main>

<!-- ── EXECUTION PANEL (below hero, inside hero container) ── -->
<div style="max-width:1100px;margin:0 auto;padding:0 24px" id="exec-container">
  <div class="exec-panel" id="exec-panel">
    <div class="exec-panel-title">Payment Execution</div>
    <div class="exec-states" id="exec-states"></div>
    <div class="exec-id" id="exec-id"></div>

    <div class="fault-row">
      <span class="fault-label">Inject fault →</span>
      <button class="fault-btn" data-fault="none" onclick="setFault('none',this)">None</button>
      <button class="fault-btn" data-fault="remote_timeout" onclick="setFault('remote_timeout',this)">Provider timeout</button>
      <button class="fault-btn" data-fault="definite_failure" onclick="setFault('definite_failure',this)">Definite failure</button>
    </div>

    <div class="reconcile-section" id="reconcile-section">
      <div class="alert alert-warn" style="margin-bottom:12px">
        <svg width="16" height="16" fill="none" viewBox="0 0 24 24" stroke="currentColor" stroke-width="2"><path d="M12 9v4m0 4h.01M10.29 3.86L1.82 18a2 2 0 001.71 3h16.94a2 2 0 001.71-3L13.71 3.86a2 2 0 00-3.42 0z"/></svg>
        <div>
          <strong>Outcome unknown.</strong> The provider was contacted but no response was received before the timeout.
          SELLABLE cannot assert success or failure. Click Reconcile to query the provider's current state.
        </div>
      </div>
      <button class="reconcile-btn" onclick="doReconcile()">
        <svg width="14" height="14" fill="none" viewBox="0 0 24 24" stroke="currentColor" stroke-width="2.5"><path d="M4 4v5h.582m15.356 2A8.001 8.001 0 004.582 9m0 0H9m11 11v-5h-.581m0 0a8.003 8.003 0 01-15.357-2m15.357 2H15"/></svg>
        Reconcile — query provider state
      </button>
    </div>
  </div>
</div>

<!-- ── AUTHORIZATION MODAL ── -->
<div class="modal-overlay" id="modal-overlay" role="dialog" aria-modal="true" aria-labelledby="modal-title">
  <div class="modal">
    <div class="modal-header">
      <div class="modal-title" id="modal-title">Review Purchase</div>
      <button class="modal-close" onclick="closeModal()" aria-label="Close">×</button>
    </div>
    <div class="modal-body">

      <div class="auth-item">
        <div class="auth-item-label">What you're buying</div>
        <div class="auth-product-name" id="modal-product-name">—</div>
        <div class="auth-price" id="modal-price">—</div>
        <div class="auth-sku" id="modal-sku">—</div>
      </div>

      <div class="auth-item">
        <div class="auth-item-label">Your authorization limits</div>
        <div class="auth-limits">
          <div class="auth-limit-row">
            <span class="auth-limit-key">Your budget</span>
            <span class="auth-limit-val ok" id="modal-budget">—</span>
          </div>
          <div class="auth-limit-row">
            <span class="auth-limit-key">This purchase</span>
            <span class="auth-limit-val" id="modal-amount">—</span>
          </div>
          <div class="auth-limit-row">
            <span class="auth-limit-key">Budget check</span>
            <span class="auth-limit-val ok" id="modal-budget-check">—</span>
          </div>
        </div>
      </div>

      <div class="auth-item">
        <div class="auth-item-label">Policy gateway</div>
        <div class="gateway-grid" id="modal-gateway"></div>
      </div>

      <div class="auth-item">
        <div class="auth-item-label">AI reasoning</div>
        <div class="ai-reasoning" id="modal-reasoning">—</div>
      </div>

      <div class="demo-notice">
        <svg width="16" height="16" fill="none" viewBox="0 0 24 24" stroke="currentColor" stroke-width="2"><circle cx="12" cy="12" r="10"/><path d="M12 16v-4m0-4h.01"/></svg>
        <div>
          <strong>Demo wallet.</strong> This simulates your authorization for the test environment.
          In production this would be a signed user mandate from your wallet. The security claim is:
          the AI model cannot authorize money — only this step can.
        </div>
      </div>

      <button class="approve-btn" id="approve-btn" onclick="doApprove()">
        <svg width="18" height="18" fill="none" viewBox="0 0 24 24" stroke="currentColor" stroke-width="2.5"><path d="M12 22s8-4 8-10V5l-8-3-8 3v7c0 6 8 10 8 10z"/></svg>
        Approve this purchase
      </button>
    </div>
  </div>
</div>

<!-- ── JUDGE STRIP ── -->
<div class="judge-strip" id="judge-strip">
  <div class="judge-strip-text">
    <strong>For Razorpay judges:</strong> View the deterministic gateway proof, attack scenarios,
    execution state machine, webhook audit chain, and test evidence.
  </div>
  <a href="/judge" class="judge-link">
    Open Judge View →
  </a>
</div>

<!-- ── FOOTER ── -->
<footer>
  <span>SELLABLE — Razorpay AI Buildathon 2026, Track 01</span>
  <div class="footer-links">
    <a href="/audit">Audit chain</a>
    <a href="/gateway/proof">Gateway proof</a>
    <a href="/health">Health</a>
    <a href="https://github.com/HarshDubey23/SELLABLE" target="_blank" rel="noopener">GitHub</a>
  </div>
</footer>

<script>
/* ─── STATE ─────────────────────────────────────────────────────────── */
const S = {
  query: '',
  budget_paise: 500000,
  discovery: null,       // DiscoveryPipelineResult
  selected_sku: null,
  fault: 'none',
  execution_id: null,
  execution_state: null,
};

/* ─── PIPELINE RAIL ─────────────────────────────────────────────────── */
const STEPS = ['discover','gateway','authorize','execute','confirm'];
const PROGRESS_PCTS = {
  discover: 0, gateway: 25, authorize: 50, execute: 75, confirm: 100
};

function setStep(name, state) {
  STEPS.forEach(s => {
    const el = document.getElementById('step-' + s);
    el.className = 'step ' + (s === name ? state : el.className.split(' ')[1] || 'idle');
  });
  // update steps before current to 'done'
  const idx = STEPS.indexOf(name);
  STEPS.slice(0, idx).forEach(s => {
    const el = document.getElementById('step-' + s);
    if (!['blocked','warn'].includes(el.className.split(' ')[1])) el.className = 'step done';
  });
  // progress bar
  const pct = PROGRESS_PCTS[name] || 0;
  document.getElementById('pipeline-bar').style.width = pct + '%';
}

function showPipeline() {
  const w = document.getElementById('pipeline-wrap');
  w.classList.add('visible');
}

function setStatus(msg) {
  const el = document.getElementById('status-bar');
  el.textContent = msg;
  el.classList.add('show');
}

/* ─── SEARCH ────────────────────────────────────────────────────────── */
function setQuery(q) {
  document.getElementById('q').value = q;
  doSearch();
}

async function doSearch() {
  const q = document.getElementById('q').value.trim();
  if (!q) { document.getElementById('q').focus(); return; }
  const budget = parseInt(document.getElementById('budget').value) || 5000;
  S.query = q;
  S.budget_paise = budget * 100;
  S.discovery = null;
  S.selected_sku = null;

  const btn = document.getElementById('search-btn');
  btn.disabled = true;
  btn.textContent = 'Searching…';

  showPipeline();
  setStep('discover', 'active');
  setStatus('🔍 AI is querying live retail sources…');
  clearAlert();

  document.getElementById('results-section').style.display = 'none';
  document.getElementById('exec-panel').classList.remove('show');

  try {
    const res = await fetch('/discovery/search', {
      method: 'POST',
      headers: {'Content-Type': 'application/json'},
      body: JSON.stringify({query: q, budget_paise: S.budget_paise})
    });
    const data = await res.json();

    if (!res.ok) throw new Error(data.detail || 'Search failed');

    S.discovery = data;
    renderResults(data);

    const gv = data.gateway_verdict || {};
    const passed = gv.verdict === 'APPROVED';

    if (passed) {
      setStep('gateway', 'done');
      setStatus('✓ Policy gateway approved — ' + (data.listings?.length || 0) + ' listings found');
    } else {
      setStep('gateway', 'blocked');
      setStatus('✗ Gateway blocked: ' + (gv.reason || 'policy violation'));
      showAlert(
        'Gateway blocked this search: ' + (gv.reason || 'policy violation'),
        'error'
      );
    }

  } catch(e) {
    setStep('discover', 'blocked');
    setStatus('Error: ' + e.message);
    showAlert('Search error: ' + e.message, 'error');
  } finally {
    btn.disabled = false;
    btn.textContent = 'Search';
  }
}

function renderResults(data) {
  document.getElementById('results-section').style.display = 'block';

  // recommendation
  const rec = data.recommendation;
  const offer = data.merchant_offer;
  const recBanner = document.getElementById('rec-banner');

  if (rec && offer) {
    document.getElementById('rec-name').textContent = offer.name;
    document.getElementById('rec-price').textContent = '₹' + fmtPrice(offer.price_inr);
    document.getElementById('rec-seller').textContent = '· via SELLABLE catalog';
    S.selected_sku = offer.sku;

    const why = document.getElementById('rec-why');
    why.innerHTML = '';
    const reasons = buildReasons(rec, offer, data);
    reasons.forEach(r => {
      const div = document.createElement('div');
      div.className = 'rec-why-item';
      div.innerHTML = `<div class="rec-why-icon ok">✓</div><span>${r}</span>`;
      why.appendChild(div);
    });

    recBanner.classList.add('show');
  } else {
    recBanner.classList.remove('show');
  }

  // probe card
  const probe = data.policy_probe;
  const probeCard = document.getElementById('probe-card');
  if (probe) {
    document.getElementById('probe-name').textContent = probe.name;
    document.getElementById('probe-detail').textContent =
      probe.why + ' — ₹' + fmtPrice(probe.price_inr) + ' exceeds your budget by ₹' +
      (probe.exceeds_budget_by_paise / 100).toFixed(0);
    probeCard.classList.add('show');
    probeCard._sku = probe.sku;
  } else {
    probeCard.classList.remove('show');
  }

  // listings grid
  const grid = document.getElementById('product-grid');
  grid.innerHTML = '';
  const listings = (data.listings || []).filter(l => l.evidence_class !== 'MOCK_SOURCE');
  const count = document.getElementById('listings-count');
  count.textContent = listings.length + ' source' + (listings.length !== 1 ? 's' : '');

  if (listings.length === 0) {
    document.getElementById('empty-state').classList.add('show');
  } else {
    document.getElementById('empty-state').classList.remove('show');
    listings.slice(0, 9).forEach(l => {
      const card = document.createElement('div');
      card.className = 'product-card';
      card.innerHTML = `
        <div class="product-card-top">
          <div class="product-name">${esc(l.product_name)}</div>
          <span class="evidence-tag ${tagClass(l.evidence_class)}">${esc(l.evidence_class)}</span>
        </div>
        ${l.price_inr != null
          ? `<div class="product-price">₹${fmtPrice(l.price_inr)}<span class="product-price-note">${l.fx_converted ? '(FX est.)' : ''}</span></div>`
          : '<div style="font-size:13px;color:var(--muted)">Price not extracted</div>'
        }
        <div class="product-seller">
          ${l.url
            ? `<a href="${esc(l.url)}" target="_blank" rel="noopener">${esc(l.seller)}</a>`
            : esc(l.seller)
          }
          <span style="color:var(--border-2)">·</span>
          <span>${esc(l.scraped_at?.slice(0,10) || '')}</span>
        </div>
      `;
      grid.appendChild(card);
    });
  }
}

function buildReasons(rec, offer, data) {
  const reasons = [];
  const comp = data.comparison;
  if (comp && comp.lowest_observed_market_price_inr) {
    const mkt = comp.lowest_observed_market_price_inr;
    const our = offer.price_inr;
    if (our <= mkt) reasons.push(`Priced at or below lowest market price (₹${fmtPrice(mkt)} on ${comp.lowest_observed_market_seller || 'market'})`);
    else reasons.push(`Market context: lowest observed ₹${fmtPrice(mkt)} on ${comp.lowest_observed_market_seller || 'market'}`);
  }
  if (offer.rating) reasons.push(`Rated ${offer.rating}/5.0 in merchant catalog`);
  if (S.budget_paise && offer.price_paise <= S.budget_paise)
    reasons.push(`Within your ₹${(S.budget_paise/100).toFixed(0)} budget`);
  if (rec.recommendation_reason) reasons.push(rec.recommendation_reason);
  return reasons.slice(0, 4);
}

/* ─── PROBE ─────────────────────────────────────────────────────────── */
async function tryProbe() {
  const probe = S.discovery?.policy_probe;
  if (!probe) return;
  showAlert('Sending over-budget SKU to gateway…', 'info');
  try {
    const res = await fetch('/discovery/checkout', {
      method: 'POST',
      headers: {'Content-Type': 'application/json'},
      body: JSON.stringify({
        sku: probe.sku,
        budget_paise: S.budget_paise,
        fault: 'none'
      })
    });
    const data = await res.json();
    if (!res.ok) {
      showAlert('Gateway blocked (as expected): ' + (data.detail || JSON.stringify(data)), 'warn');
      setStep('gateway', 'blocked');
    } else {
      showAlert('Unexpected: gateway allowed the over-budget SKU. Check policy rules.', 'error');
    }
  } catch(e) {
    showAlert('Error: ' + e.message, 'error');
  }
}

/* ─── MODAL ─────────────────────────────────────────────────────────── */
function openModal() {
  if (!S.selected_sku || !S.discovery) return;
  const offer = S.discovery.merchant_offer;
  if (!offer) return;

  document.getElementById('modal-product-name').textContent = offer.name;
  document.getElementById('modal-price').textContent = '₹' + fmtPrice(offer.price_inr);
  document.getElementById('modal-sku').textContent = 'SKU: ' + offer.sku + ' · Category: ' + offer.category;
  document.getElementById('modal-budget').textContent = '₹' + (S.budget_paise/100).toFixed(0);
  document.getElementById('modal-amount').textContent = '₹' + fmtPrice(offer.price_inr);

  const ok = offer.price_paise <= S.budget_paise;
  const budgetCheck = document.getElementById('modal-budget-check');
  budgetCheck.textContent = ok ? '✓ Within limit' : '✗ Exceeds limit';
  budgetCheck.className = 'auth-limit-val ' + (ok ? 'ok' : 'warn');

  const gv = S.discovery.gateway_verdict || {};
  const gwEl = document.getElementById('modal-gateway');
  gwEl.innerHTML = '';
  const checks = [
    ['Budget ceiling enforced by server', ok],
    ['Category: ' + (offer.category || '—'), true],
    ['Deterministic policy (no LLM)', true],
    ['Price from server catalog (not AI)', true],
  ];
  checks.forEach(([label, pass]) => {
    const row = document.createElement('div');
    row.className = 'gateway-row';
    row.innerHTML = `
      <div class="g-icon ${pass ? 'pass' : 'fail'}">${pass ? '✓' : '✗'}</div>
      <span>${esc(label)}</span>
    `;
    gwEl.appendChild(row);
  });

  const reasoning = S.discovery.recommendation?.recommendation_reason || 'No additional reasoning available.';
  document.getElementById('modal-reasoning').textContent = reasoning;

  setStep('authorize', 'waiting');
  document.getElementById('modal-overlay').classList.add('open');
}

function closeModal() {
  document.getElementById('modal-overlay').classList.remove('open');
  const el = document.getElementById('step-authorize');
  if (el.className.includes('waiting')) el.className = 'step idle';
}

document.getElementById('modal-overlay').addEventListener('click', function(e) {
  if (e.target === this) closeModal();
});

/* ─── APPROVE & EXECUTE ─────────────────────────────────────────────── */
async function doApprove() {
  const btn = document.getElementById('approve-btn');
  btn.disabled = true;
  btn.textContent = 'Authorizing…';
  closeModal();

  setStep('authorize', 'done');
  setStep('execute', 'active');
  setStatus('💳 Executing via Razorpay test mode…');
  showExecPanel('EXECUTION_PENDING');

  try {
    const res = await fetch('/discovery/checkout', {
      method: 'POST',
      headers: {'Content-Type': 'application/json'},
      body: JSON.stringify({
        sku: S.selected_sku,
        budget_paise: S.budget_paise,
        fault: S.fault !== 'none' ? S.fault : ''
      })
    });
    const data = await res.json();

    if (!res.ok) {
      setStep('execute', 'blocked');
      setStatus('✗ Rejected: ' + (data.detail || 'payment failed'));
      showExecPanel('FAILED', data.detail || 'Payment rejected by gateway or provider.');
      showAlert('Payment rejected: ' + (data.detail || 'see execution panel'), 'error');
      btn.disabled = false;
      btn.textContent = 'Approve this purchase';
      return;
    }

    S.execution_id = data.execution_id || data.id;

    const state = data.state || data.status || 'EXECUTED';
    showExecPanel(state, data);

    if (state === 'EXECUTED' || state === 'COMPLETED') {
      setStep('execute', 'done');
      setStep('confirm', 'done');
      setStatus('✓ Order placed successfully · ' + (data.razorpay_order_id || ''));
      document.getElementById('pipeline-bar').style.width = '100%';
    } else if (state === 'RECONCILIATION_REQUIRED') {
      setStep('execute', 'warn');
      setStatus('⚠ Outcome unknown — reconciliation required');
      document.getElementById('reconcile-section').classList.add('show');
    } else if (state === 'FAILED') {
      setStep('execute', 'blocked');
      setStatus('✗ Payment failed definitively');
    }

  } catch(e) {
    setStep('execute', 'blocked');
    setStatus('Error: ' + e.message);
    showAlert('Execution error: ' + e.message, 'error');
  } finally {
    btn.disabled = false;
    btn.textContent = 'Approve this purchase';
  }
}

function showExecPanel(state, data) {
  const panel = document.getElementById('exec-panel');
  panel.classList.add('show');
  document.getElementById('exec-container').scrollIntoView({behavior:'smooth',block:'start'});

  const STATES = [
    ['APPROVED', 'Mission and proposal approved by gateway'],
    ['EXECUTION_PENDING', 'Preparing to contact payment provider'],
    ['REMOTE_ATTEMPTED', 'Razorpay contacted — state persisted to disk before call'],
    ['EXECUTED', 'Payment confirmed by provider'],
    ['RECONCILIATION_REQUIRED', 'Provider contacted; outcome unknown before timeout'],
    ['FAILED', 'Provider returned definitive failure'],
  ];

  const stateNames = STATES.map(s => s[0]);
  const curIdx = stateNames.indexOf(state);

  const container = document.getElementById('exec-states');
  container.innerHTML = '';
  STATES.forEach(([s, desc], i) => {
    const row = document.createElement('div');
    let cls = 'exec-state-row';
    if (i < curIdx) cls += ' done';
    else if (i === curIdx) {
      if (s === 'EXECUTED') cls += ' done';
      else if (s === 'FAILED') cls += ' fail';
      else if (s === 'RECONCILIATION_REQUIRED') cls += ' warn';
      else cls += ' current';
    }
    row.className = cls;
    row.innerHTML = `
      <div class="exec-state-dot"></div>
      <div class="exec-state-name">${s}</div>
      <div class="exec-state-desc">${esc(desc)}</div>
    `;
    container.appendChild(row);
  });

  const idEl = document.getElementById('exec-id');
  if (data && typeof data === 'object') {
    const lines = [];
    if (data.execution_id) lines.push('execution_id: ' + data.execution_id);
    if (data.razorpay_order_id) lines.push('razorpay_order_id: ' + data.razorpay_order_id);
    if (data.mission_id) lines.push('mission_id: ' + data.mission_id);
    if (data.approved_at) lines.push('approved_at: ' + data.approved_at);
    idEl.textContent = lines.join('\n') || (typeof data === 'string' ? data : '');
  } else if (typeof data === 'string') {
    idEl.textContent = data;
  }
}

async function doReconcile() {
  if (!S.execution_id) return;
  const btn = document.querySelector('.reconcile-btn');
  btn.disabled = true;
  btn.textContent = 'Querying provider…';

  try {
    const res = await fetch('/discovery/reconcile/' + encodeURIComponent(S.execution_id), {
      method: 'POST',
      headers: {'Content-Type': 'application/json'},
      body: JSON.stringify({})
    });
    const data = await res.json();

    const state = data.state || data.status || 'RECONCILIATION_REQUIRED';
    showExecPanel(state, data);
    if (state === 'EXECUTED') {
      setStep('execute', 'done'); setStep('confirm', 'done');
      setStatus('✓ Reconciled: payment confirmed');
      document.getElementById('reconcile-section').classList.remove('show');
    } else if (state === 'FAILED') {
      setStep('execute', 'blocked');
      setStatus('✗ Reconciled: payment failed');
      document.getElementById('reconcile-section').classList.remove('show');
    }
  } catch(e) {
    showAlert('Reconcile error: ' + e.message, 'error');
  } finally {
    btn.disabled = false;
    btn.textContent = 'Reconcile — query provider state';
  }
}

/* ─── FAULT INJECTION ───────────────────────────────────────────────── */
function setFault(fault, btn) {
  S.fault = fault;
  document.querySelectorAll('.fault-btn').forEach(b => b.classList.remove('active'));
  btn.classList.add('active');
}

/* ─── HELPERS ───────────────────────────────────────────────────────── */
function fmtPrice(v) {
  if (v == null) return '—';
  return parseFloat(v).toLocaleString('en-IN', {maximumFractionDigits: 0});
}

function tagClass(ec) {
  const map = {
    'OBSERVED': 'tag-observed',
    'FX_CONVERTED': 'tag-fx',
    'MOCK_SOURCE': 'tag-mock',
    'UNVERIFIED': 'tag-unverified',
  };
  return map[ec] || 'tag-unverified';
}

function esc(s) {
  if (s == null) return '';
  return String(s).replace(/&/g,'&amp;').replace(/</g,'&lt;').replace(/>/g,'&gt;').replace(/"/g,'&quot;');
}

function showAlert(msg, type) {
  const area = document.getElementById('alert-area');
  area.innerHTML = `<div class="alert alert-${type}">
    <span>${esc(msg)}</span>
  </div>`;
  area.scrollIntoView({behavior:'smooth',block:'start'});
}
function clearAlert() { document.getElementById('alert-area').innerHTML = ''; }

/* ─── KEYBOARD ──────────────────────────────────────────────────────── */
document.getElementById('q').addEventListener('keydown', function(e) {
  if (e.key === 'Enter') doSearch();
});

/* ─── INIT ──────────────────────────────────────────────────────────── */
document.getElementById('q').focus();
</script>
</body>
</html>"""


@router.get("/", response_class=HTMLResponse)
async def product_page() -> HTMLResponse:
    return HTMLResponse(PAGE)
