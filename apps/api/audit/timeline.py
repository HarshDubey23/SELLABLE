"""GET /audit/timeline — human-visible audit chain as an HTML card list.

Inline CSS only, no JS framework. Each entry renders its truncated
hashes; any entry whose stored hash does not match a fresh recompute is
flagged TAMPERED so tampering is visible to a reviewer's eyes, not just
to /audit's JSON.
"""
import html

from fastapi import APIRouter
from fastapi.responses import HTMLResponse

from . import chain as audit_chain

router = APIRouter()

_CSS = """
body { font-family: Consolas, monospace; background: #0f1117; color: #e6e6e6;
       margin: 2rem auto; max-width: 720px; }
h1 { font-size: 1.4rem; border-bottom: 1px solid #333; padding-bottom: .5rem; }
.card { background: #161a23; border: 1px solid #2a2f3a; border-radius: 8px;
        padding: .8rem 1rem; margin: .7rem 0; }
.card.genesis { border-color: #4a5568; }
.seq { color: #63b3ed; font-weight: bold; }
.actor { color: #9ae6b4; }
.action { color: #f6ad55; }
.hashline { color: #718096; font-size: .85rem; margin-top: .35rem;
            word-break: break-all; }
.tampered { color: #fc8181; font-weight: bold; }
footer { margin-top: 1.5rem; padding-top: .75rem; border-top: 1px solid #333;
         color: #a0aec0; }
.ok { color: #9ae6b4; } .bad { color: #fc8181; }
"""


def _render_entry(e: dict) -> str:
    recomputed = audit_chain._hash(e)
    stored = e.get("hash", "")
    ok = (stored == recomputed) if stored else True
    flag = ('<div class="tampered">&#9888; TAMPERED</div>' if not ok else "")
    genesis = " genesis" if e["seq"] == 0 else ""
    return f"""<div class="card{genesis}">
  <span class="seq">[{e['seq']:04d}]</span>
  <span class="actor">{html.escape(e['actor'])}</span> @
  <span>{e['ts']}</span> |
  <span class="action">{html.escape(e['action'])}</span>
  {flag}
  <div class="hashline">payload_hash: {e['payload_hash'][:16]}</div>
  <div class="hashline">prev_hash:&nbsp;&nbsp;{e['prev_hash'][:16]}</div>
  <div class="hashline">hash:&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;{(stored or recomputed)[:16]}</div>
</div>"""


@router.get("/audit/timeline", response_class=HTMLResponse)
def audit_timeline() -> HTMLResponse:
    entries = audit_chain.entries()
    verified = audit_chain.verify()
    body = "\n".join(_render_entry(e) for e in entries)
    cls = "ok" if verified else "bad"
    page = f"""<!DOCTYPE html>
<html lang="en">
<head><meta charset="utf-8">
<title>SELLABLE Audit Chain</title>
<style>{_CSS}</style></head>
<body>
<h1>SELLABLE Audit Chain</h1>
{body}
<footer>Chain verified: <span class="{cls}">{verified}</span></footer>
</body></html>"""
    return HTMLResponse(content=page)
