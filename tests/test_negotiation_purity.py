"""Invariant N-1: negotiation/types.py and negotiation/bounds.py and
negotiation/strategies.py must NOT import fastapi, requests, httpx,
google.genai, sqlite3, or any I/O module.
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

PURE_FILES = [
    "apps/api/negotiation/types.py",
    "apps/api/negotiation/bounds.py",
    "apps/api/negotiation/strategies.py",
]

FORBIDDEN = [
    "fastapi", "requests", "httpx", "urllib3", "socket", "subprocess",
    "os.system", "google.genai", "generativeai",
    "sqlite3", "asyncio",
]


def test_negotiation_purity():
    repo = Path(__file__).resolve().parents[1]
    violations = []
    for rel in PURE_FILES:
        p = repo / rel
        if not p.exists():
            violations.append(f"{rel}: FILE MISSING")
            continue
        src = p.read_text()
        for pat in FORBIDDEN:
            if pat in src:
                violations.append(f"{rel}: forbidden pattern '{pat}'")
    assert not violations, "N-1 purity violations:\n  " + "\n  ".join(violations)
