"""Inline SVG icon system based on Lucide icons - zero emoji, zero external fonts."""
from __future__ import annotations

_PATHS = {
    "shield-check": (
        '<path d="M20 13v6a1 8 0 0 1-8 8 8 8 0 0 1-8-8v-6l8-3 8 3z"/>'
        '<path d="m9 12 2 2 4-4"/>'
    ),
    "terminal": (
        '<polyline points="4 17 10 11 4 5"/>'
        '<line x1="12" x2="20" y1="19" y2="19"/>'
    ),
    "zap": (
        '<polygon points="13 2 3 14 12 14 11 22 21 10 12 10 13 2"/>'
    ),
    "x-octagon": (
        '<polygon points="7.86 2 16.14 2 22 7.86 22 16.14 16.14 22 7.86 22 2 16.14 2 7.86 7.86 2"/>'
        '<line x1="15" x2="9" y1="9" y2="15"/>'
        '<line x1="9" x2="15" y1="9" y2="15"/>'
    ),
    "check": (
        '<polyline points="20 6 9 17 4 12"/>'
    ),
    "x": (
        '<line x1="18" x2="6" y1="6" y2="18"/>'
        '<line x1="6" x2="18" y1="6" y2="18"/>'
    ),
    "lock": (
        '<rect width="18" height="11" x="3" y="11" rx="2" ry="2"/>'
        '<path d="M7 11V7a5 5 0 0 1 10 0v4"/>'
    ),
    "link-2": (
        '<path d="M9 17H7A5 5 0 0 1 7 7h2m6 0h2a5 5 0 0 1 0 10h-2"/>'
        '<line x1="8" x2="16" y1="12" y2="12"/>'
    ),
    "activity": (
        '<path d="M22 12 18 12 15 21 9 3 6 12 2 12"/>'
    ),
    "database": (
        '<ellipse cx="12" cy="5" rx="9" ry="3"/>'
        '<path d="M3 5v14c8 3 18 3 18 0V5"/>'
        '<path d="M3 12v1c8 3 18 3 18 0v-1"/>'
    ),
    "arrow-right": (
        '<line x1="5" x2="19" y1="12" y2="12"/>'
        '<polyline points="12 5 19 12 12 19"/>'
    ),
    "play": (
        '<polygon points="5 3 19 12 5 21 5 3"/>'
    ),
    "copy": (
        '<rect width="14" height="14" x="8" y="8" rx="2" ry="2"/>'
        '<path d="M4 16H6a2 2 0 0 0 2-2V4a2 2 0 0 0-2-2H4a2 2 0 0 0-2 2v8a2 2 0 0 0 2 2z"/>'
    ),
}

def render_icon(name: str, size: int = 16, cls: str = "") -> str:
    """Render a pure inline SVG icon."""
    paths = _PATHS.get(name)
    if not paths:
        paths = _PATHS.get("shield-check", "")
    cls_attr = f' class="{cls}"' if cls else ""
    return (
        f'<svg xmlns="http://www.w3.org/2000/svg" width="{size}" height="{size}" '
        f'viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" '
        f'stroke-linecap="round" stroke-linejoin="round" role="img" aria-hidden="true"'
        f'{cls_attr}>{paths}</svg>'
    )

__all__ = ["render_icon", "_PATHS"]
