"""SELLABLE master layout - designed shell (single source of markup)."""
from __future__ import annotations

import os
from pathlib import Path

from .icons import render_icon

_THEME_PATH = Path(__file__).resolve().parent / "theme.css"

def _get_theme() -> str:
    try:
        return _THEME_PATH.read_text(encoding="utf-8-sig").lstrip("\ufeff")
    except Exception:
        return ""

_NAV_ITEMS = [
    ("dashboard", "/", "Console"),
    ("mission", "/mission", "Mission"),
    ("attack", "/attack-ui", "Attack Lab"),
    ("audit", "/audit-ui", "Audit Ledger"),
    ("gateway", "/gateway-ui", "Policy Matrix"),
    ("protocols", "/protocols", "Protocols (UAP)"),
    ("growth", "/growth", "Merchant Growth"),
    ("discovery", "/discovery", "Live Discovery"),
    ("architecture", "/architecture", "Architecture"),
    ("products", "/products", "Catalog"),
    ("metrics", "/metrics", "Metrics"),
]

_FAVICON = (
    "data:image/svg+xml,%3Csvg xmlns='http://www.w3.org/2000/svg' "
    "viewBox='0 0 32 32'%3E%3Crect width='32' height='32' rx='7' "
    "fill='%232B84EA'/%3E%3Ctext x='16' y='22' font-family='Arial' "
    "font-size='17' font-weight='700' fill='white' text-anchor='middle'"
    "%3ES%3C/text%3E%3C/svg%3E"
)


def _nav_html(active: str) -> str:
    links = []
    for tab, url, label in _NAV_ITEMS:
        cur = " active" if tab == active else ""
        links.append(f'<a class="nav-link{cur}" href="{url}">{label}</a>')
    return "".join(links)


def _mode_chip() -> str:
    key = os.environ.get("RAZORPAY_KEY_ID", "")
    if key.startswith("rzp_"):
        return '<span class="chip chip-live"><span class="dot dot-live"></span>TEST MODE</span>'
    return '<span class="chip chip-sim"><span class="dot dot-sim"></span>SIMULATED</span>'


def render_page(
    title: str,
    active_tab: str,
    content: str,
    *,
    extra_head: str = ""
) -> str:
    """Return a complete HTML document wrapped in the designed shell."""
    return f"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<meta name="theme-color" content="#071A2E">
<meta name="description" content="SELLABLE — agent-safe commerce with a deterministic policy gateway and a SHA-256 audit chain.">
<meta property="og:title" content="SELLABLE — {title}">
<meta property="og:description" content="The LLM proposes. Deterministic policy disposes. Cryptography authorizes.">
<link rel="icon" href="{_FAVICON}">
<link rel="preconnect" href="https://fonts.googleapis.com">
<link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
<link href="https://fonts.googleapis.com/css2?family=Space+Grotesk:wght@500;700&family=Inter:wght@400;500;600&family=IBM+Plex+Mono:wght@400;600&display=swap" rel="stylesheet">
<title>SELLABLE — {title}</title>
<style>{_get_theme()}</style>
<script src="https://checkout.razorpay.com/v1/checkout.js"></script>
{extra_head}
</head>
<body>
<a class="skip-link" href="#main-content">Skip to content</a>
<header class="topbar">
  <a class="brand" href="/" aria-label="SELLABLE home">
    <span class="brand-tile" aria-hidden="true">S</span>
    <span class="brand-text">SELLABLE<small>Agentic Commerce Security</small></span>
  </a>
  <nav class="nav" aria-label="Primary">{_nav_html(active_tab)}</nav>
  <div class="topbar-right">{_mode_chip()}
    <a class="btn btn-primary btn-sm" href="/judge">{render_icon("play", 14)} Judge Console</a>
  </div>
</header>
<main class="page" id="main-content">{content}</main>
<footer class="footer">
  <span>SELLABLE · Razorpay AI Buildathon 2026 · Track 01 · Built by Harsh Dubey</span>
  <span class="footer-links">
    <a href="https://github.com/HarshDubey23/SELLABLE" target="_blank" rel="noopener">GitHub</a>
    <a href="/judge">Judge Console</a>
    <a href="/health">Health</a>
    <a href="/audit/verify">Audit Verify</a>
  </span>
</footer>
</body>
</html>"""
