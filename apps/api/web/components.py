"""Signature UI Components for SELLABLE Console.
Includes: Warrant Flow SVG, StatBlocks, Sparklines, Block Chips, and Event Cards.
"""
from __future__ import annotations

import html

from .icons import render_icon


def warrant_flow_svg(current_stage: int = 0, is_rejected: bool = False) -> str:
    """Render the 6-stage Warrant Flow SVG representing the money custody path."""
    stages = [
        ("Mandate", "HMAC Intent"),
        ("Buyer Agent", "Proposes Only"),
        ("Gateway R1-R12", "Pure Policy"),
        ("Binding", "SHA-256 Lock"),
        ("Money Gate", "Single Use"),
        ("Audit Chain", "SHA-256 Block"),
    ]

    nodes_svg = []
    step_x = 180
    start_x = 50

    for i, (name, sub) in enumerate(stages):
        x = start_x + (i * step_x)
        cls = "warrant-node"
        if i < current_stage:
            cls += " passed"
        elif i == current_stage:
            cls += " rejected" if is_rejected else " active"

        nodes_svg.append(f'''
        <g class="{cls}" data-stage="{i}" transform="translate({x}, 50)">
            <circle class="warrant-node-circle" cx="0" cy="0" r="16" />
            <text x="0" y="-24" font-weight="600" font-size="12">{html.escape(name)}</text>
            <text x="0" y="32" font-size="10" fill="var(--text-3)">{html.escape(sub)}</text>
        </g>
        ''')

    nodes_str = "\\n".join(nodes_svg)

    return f'''
    <div class="warrant-container" role="region" aria-label="Cryptographic Warrant Flow">
      <svg class="warrant" viewBox="0 0 1000 100" role="img" aria-label="Money path: mandate, agent, gateway, binding, money gate, audit">
        <path class="warrant-track" d="M50 50 H950" />
        {nodes_str}
        <circle class="warrant-dot" cx="50" cy="50" r="6" />
      </svg>
    </div>
    '''

def stat_block(label: str, value: str, sub: str = "", tint: str = "blue", icon: str = "") -> str:
    """Render a single StatBlock component with semantic left-tint border."""
    icon_html = render_icon(icon, 14) if icon else ""
    sub_html = f'<div class="stat-sub">{html.escape(sub)}</div>' if sub else ""
    return f'''
    <div class="stat-block tint-{tint}">
      <div class="stat-label">
        <span>{html.escape(label)}</span>
        {icon_html}
      </div>
      <div class="stat-value tabular-nums">{html.escape(str(value))}</div>
      {sub_html}
    </div>
    '''

def block_chip(seq: int, block_hash: str, is_genesis: bool = False) -> str:
    """Render an audit block chip with copy-to-clipboard functionality."""
    short_hash = block_hash[:8] if block_hash else "genesis"
    icon = render_icon("lock", 12) if is_genesis else ""
    return f'''
    <span class="block-chip" title="Block {seq} — Click to copy full hash: {block_hash}"
          onclick="navigator.clipboard.writeText('{block_hash}'); this.style.borderColor='var(--mint)'; setTimeout(() => this.style.borderColor='', 1000);">
      {icon} #{seq} <code>{short_hash}</code>
    </span>
    '''

def event_row_html(actor: str, action: str, reason: str = "", is_approved: bool = True) -> str:
    """Render a structured event row for execution log streams."""
    cls = "approve" if is_approved else "reject"
    icon_name = "check" if is_approved else "x-octagon"
    icon_html = render_icon(icon_name, 14)
    reason_html = f'<span class="event-reason">&mdash; {html.escape(reason)}</span>' if reason else ""
    return f'''
    <div class="event-row {cls}">
      {icon_html}
      <span class="event-actor font-mono">{html.escape(actor)}</span>
      <span class="event-action">{html.escape(action)}</span>
      {reason_html}
    </div>
    '''
