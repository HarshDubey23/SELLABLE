"""SELLABLE Master Layout & Page Renderer — Unified Design System Shell.

Single source of HTML shell wrapping all pages.  Every page calls render_page();
the chaos pages (which previously had their own full-HTML) are refactored onto this.
"""
from __future__ import annotations

import os
from pathlib import Path

_THEME_CSS_PATH = Path(__file__).resolve().parent / "theme.css"
_THEME_CSS = _THEME_CSS_PATH.read_text(encoding="utf-8")

# Navigation items: (tab_id, url, label, special_class)
_NAV_ITEMS = [
    ("dashboard",    "/",             "Command Center",  ""),
    ("mission",      "/mission",      "Live Mission",    ""),
    ("attack",       "/attack-ui",    "Attack Lab",      ""),
    ("audit",        "/audit-ui",     "Audit Ledger",    ""),
    ("gateway",      "/gateway-ui",   "Policy Matrix",   ""),
    ("chaos",        "/chaos",        "Chaos Room",      ""),
    ("architecture", "/architecture", "Architecture",    ""),
    ("products",     "/products",     "Catalog",         ""),
    ("why",          "/why",          "Why SELLABLE",    ""),
    ("demo",         "/demo",         "Demo Hub",        ""),
    ("judge",        "/judge",        "Judge Console",   "judge-cta"),
]


def render_page(title: str, active_tab: str, content: str, *, extra_head: str = "") -> str:
    """Return a complete HTML document wrapped in the unified master layout.

    Args:
        title:      Page title (suffix after SELLABLE —).
        active_tab: Tab ID string that matches _NAV_ITEMS[0] to set .active class.
        content:    Inner HTML body content.
        extra_head: Optional extra <head> elements (e.g. <meta> tags, inline scripts).
    """
    razorpay_key = os.environ.get("RAZORPAY_KEY_ID", "")
    is_simulated = not (razorpay_key and razorpay_key.startswith("rzp_"))

    if is_simulated:
        status_html = (
            '<div class="simulated-ribbon" title="Add real Razorpay test keys to .env for live payments">'
            '<span>&#9889;</span> SIMULATED PAYMENTS'
            '</div>'
        )
    else:
        status_html = (
            '<div class="live-badge">'
            '<span class="live-dot"></span> RAZORPAY TEST LIVE'
            '</div>'
        )

    nav_html = ""
    for tab_id, url, label, extra_cls in _NAV_ITEMS:
        active_cls = "active" if active_tab == tab_id else ""
        classes = f"nav-link {active_cls} {extra_cls}".strip()
        nav_html += f'<a href="{url}" class="{classes}">{label}</a>\n        '

    return f"""<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <meta name="description" content="SELLABLE — Agent-safe commerce with deterministic policy gateway and SHA-256 audit chain. Razorpay AI Buildathon 2026.">
  <title>SELLABLE &mdash; {title}</title>
  <script src="https://checkout.razorpay.com/v1/checkout.js" defer></script>
  {extra_head}
  <style>
{_THEME_CSS}
  </style>
</head>
<body>

  <header class="navbar" role="banner">
    <div class="nav-container">
      <a href="/" class="brand-badge" aria-label="SELLABLE home">
        <div class="brand-icon" aria-hidden="true">S</div>
        <div>
          <div class="brand-text">SELLABLE</div>
          <div style="font-size:9px;color:var(--muted);font-family:var(--font-mono);line-height:1.2;">Agentic Commerce Security</div>
        </div>
        <span class="track-tag">Track 01</span>
      </a>

      <nav class="nav-menu" role="navigation" aria-label="Main navigation">
        {nav_html}
      </nav>

      <div class="nav-status-wrap" aria-live="polite">
        {status_html}
      </div>
    </div>
  </header>

  <main class="main-content" id="main-content" role="main">
    {content}
  </main>

  <footer class="footer" role="contentinfo">
    <div class="footer-wrap">
      <div class="footer-left">
        <strong>SELLABLE</strong> &mdash; Razorpay AI Buildathon 2026 &middot; Track 01: AI Growth &amp; Agentic Commerce<br>
        <span style="font-size:11px;color:var(--dim);">
          Deterministic Policy Gateway (R1&ndash;R12) &middot; SHA-256 Audit Chain &middot; Cryptographic Approval Bindings &middot;
          Builder: Harsh Dubey
        </span>
      </div>
      <div class="footer-links" role="list">
        <a href="https://github.com/HarshDubey23/SELLABLE" target="_blank" rel="noopener" role="listitem">GitHub</a>
        <a href="/judge" role="listitem">Judge Console</a>
        <a href="/why" role="listitem">Why SELLABLE</a>
        <a href="/health" role="listitem">API Health</a>
        <a href="/gateway/proof" role="listitem">Gateway Proof</a>
        <a href="/audit/verify" role="listitem">Audit Verify</a>
      </div>
    </div>
  </footer>

</body>
</html>"""
