"""Machine-checked isolation test for external_buyer/.

Every file under external_buyer/ must contain ZERO imports from
the SELLABLE codebase, eval, or MCP server. The buyer must also
run as a real subprocess over HTTP when a server is available.
"""
import os
import subprocess
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
EXTERNAL_BUYER_DIR = ROOT / "external_buyer"

FORBIDDEN = [
    "from apps",
    "import apps",
    "from eval",
    "import eval",
    "mcp_server",
    "MISSION_HMAC_KEY",
    "USER_MANDATE_KEY",
    "APP_API_KEY",
    "RAZORPAY_KEY_SECRET",
    "GEMINI_API_KEY",
]


def _collect_py_files() -> list[Path]:
    files: list[Path] = []
    for p in EXTERNAL_BUYER_DIR.rglob("*.py"):
        files.append(p)
    return files


def test_no_forbidden_imports():
    """Machine-check every file under external_buyer/ for forbidden imports."""
    bad: list[str] = []
    for p in _collect_py_files():
        text = p.read_text(encoding="utf-8", errors="replace")
        for pat in FORBIDDEN:
            if pat in text:
                bad.append(f"{p.name}: contains {pat!r}")
    assert not bad, "\n".join(bad)


def _server_up() -> bool:
    try:
        import urllib.request
        urllib.request.urlopen(
            "http://127.0.0.1:8000/health", timeout=1)
        return True
    except Exception:
        return False


@pytest.mark.skipif(not _server_up(), reason="no live SELLABLE server — offline-safe skip")
def test_buyer_completes_purchase_subprocess() -> None:
    """Run the buyer as a real subprocess against the live server."""
    env = os.environ.copy()
    # The buyer should only see the keys it needs, never secrets.
    env["APP_API_KEY"] = os.environ.get("APP_API_KEY", "test-key-ci")
    env["SELLABLE_MISSION_KEY"] = os.environ.get("SELLABLE_MISSION_KEY", "")
    for secret in ("RAZORPAY_KEY_SECRET", "RAZORPAY_WEBHOOK_SECRET",
                   "GEMINI_API_KEY", "USER_MANDATE_KEY"):
        env.pop(secret, None)
    if not env.get("SELLABLE_MISSION_KEY"):
        pytest.skip("SELLABLE_MISSION_KEY not set — cannot sign mission")

    proc = subprocess.run(
        [sys.executable, "-m", "external_buyer.run",
         "--base", "http://127.0.0.1:8000",
         "--mission", "missions/happy_path.json"],
        capture_output=True, text=True, env=env,
        cwd=str(ROOT), timeout=60,
    )
    out = proc.stdout + proc.stderr
    assert "EXTERNAL_BUYER_RESULT" in out, (
        f"missing EXTERNAL_BUYER_RESULT in output:\n{out[-500:]}")
    assert proc.returncode in (0, 3), (
        f"unexpected exit code {proc.returncode}:\n{out[-500:]}")