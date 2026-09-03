"""SELLABLE Master Layout & Page Renderer (Workstream B1).

Unified HTML page shell with shared design system, navigation bar, and footer.
"""
from __future__ import annotations

import os
from pathlib import Path

THEME_CSS_PATH = Path(__file__).resolve().parent / "theme.css"
_THEME_CSS = THEME_CSS_PATH.read_text(encoding="utf-8")


def render_page(title: str, active_tab: str, content: str) -> str:
    """Renders a complete HTML page wrapped in the unified master layout."""
    razorpay_key = os.environ.get("RAZORPAY_KEY_ID", "")
    is_simulated = not bool(razorpay_key and razorpay_key.startswith("rzp_test_"))

    simulated_badge = (
        '<div class="simulated-ribbon"><span>⚡</span> SIMULATED PAYMENTS (KEYLESS DEV MODE)</div>'
        if is_simulated
        else '<div class="badge badge-ok"><span>🟢</span> RAZORPAY TEST MODE LIVE</div>'
    )

    nav_items = [
        ("dashboard", "/", "Command Center"),
        ("mission", "/mission", "Live Mission"),
        ("judge", "/judge", "Judge Console"),
        ("chaos", "/chaos", "Chaos Room"),
        ("architecture", "/architecture", "Architecture"),
        ("attack", "/attack-ui", "Attack Lab"),
        ("audit", "/audit-ui", "Audit Ledger"),
        ("gateway", "/gateway-ui", "Policy Matrix"),
        ("products", "/products", "Catalog"),
        ("why", "/why", "Why SELLABLE"),
        ("demo", "/demo", "Demo Hub"),
    ]

    nav_links_html = ""
    for tab_id, url, label in nav_items:
        active_cls = "active" if active_tab == tab_id else ""
        cta_cls = "judge-cta" if tab_id == "judge" else ""
        nav_links_html += f'<a href="{url}" class="nav-link {active_cls} {cta_cls}">{label}</a>'

    return f"""<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <title>SELLABLE — {title}</title>
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <script src="https://checkout.razorpay.com/v1/checkout.js"></script>
  <style>
{_THEME_CSS}
  </style>
</head>
<body>
  <header class="navbar">
    <div class="nav-container">
      <a href="/" class="brand-badge">
        <div class="brand-icon">S</div>
        <div>
          <div class="brand-text">SELLABLE</div>
          <div style="font-size: 10px; color: var(--muted); font-family: var(--font-mono);">Agentic Commerce Security</div>
        </div>
        <span class="track-tag">Track 01</span>
      </a>

      <nav class="nav-menu">
        {nav_links_html}
      </nav>

      <div>
        {simulated_badge}
      </div>
    </div>
  </header>

  <main class="main-content">
    {content}
  </main>

  <footer class="footer">
    <div class="footer-wrap">
      <div>
        <strong>SELLABLE</strong> — Razorpay AI Buildathon 2026 (Track 01 - AI Growth & Agentic Commerce)
        <br><span style="font-size:11px; color:var(--dim);">Deterministic Policy Gateway & Cryptographic Approval Bindings | Solo Builder: Harsh Dubey</span>
      </div>
      <div class="footer-links">
        <a href="https://github.com/HarshDubey23/SELLABLE" target="_blank">GitHub Repo</a>
        <a href="/judge">Judge Console</a>
        <a href="/why">Why SELLABLE</a>
        <a href="/health">API Health</a>
      </div>
    </div>
  </footer>
</body>
</html>"""
