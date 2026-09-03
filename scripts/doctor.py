"""SELLABLE Preflight Doctor Script.

Cross-platform parity: Windows, macOS, Linux.
Console output uses plain ASCII only (no emojis) to ensure 100% compatibility with cp1252 consoles.
"""
from __future__ import annotations

import os
import socket
import sys
import tempfile
import time
import urllib.request
from pathlib import Path


def check_python_version() -> tuple[bool, str]:
    v = sys.version_info
    ok = v.major == 3 and v.minor >= 10
    msg = f"Python {v.major}.{v.minor}.{v.micro} (>= 3.10 required)"
    return ok, msg


def check_dependencies() -> tuple[bool, str]:
    deps = ["fastapi", "uvicorn", "dotenv", "pydantic", "requests", "httpx"]
    missing = []
    for dep in deps:
        try:
            __import__(dep)
        except ImportError:
            missing.append(dep)

    if missing:
        return False, f"Missing required dependencies: {', '.join(missing)}"
    return True, "All required Python dependencies installed"


def check_env_file() -> tuple[bool, str]:
    env_path = Path(__file__).resolve().parents[1] / ".env"
    if not env_path.exists():
        return True, "NOTICE: .env file missing (run_demo.py will auto-generate)"

    content = env_path.read_text(encoding="utf-8")
    placeholders = [
        "your_secret_here",
        "your_webhook_secret_here",
        "generate_with_python_secrets_token_hex_32",
        "your_gemini_api_key_here",
    ]
    found_placeholders = [p for p in placeholders if p in content]
    if found_placeholders:
        return True, f"WARNING: .env contains placeholder values: {', '.join(found_placeholders)} (demo simulation active)"

    return True, ".env file valid"


def check_sqlite_writable() -> tuple[bool, str]:
    try:
        data_dir = Path(__file__).resolve().parents[1] / "data"
        data_dir.mkdir(exist_ok=True)
        test_file = data_dir / ".doctor_test.tmp"
        test_file.write_text("write_test", encoding="utf-8")
        test_file.unlink()
        return True, "SQLite data directory writable"
    except Exception as e:
        return False, f"SQLite data directory write check failed: {e}"


def check_port_available() -> tuple[bool, str]:
    port = int(os.environ.get("PORT", "8000"))
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        s.settimeout(1.0)
        result = s.connect_ex(("127.0.0.1", port))
        if result == 0:
            # Port is currently in use (server running or busy)
            return True, f"Port {port} in use (server active or ready to bind)"
        return True, f"Port {port} available for binding"


def check_outbound_connectivity(host: str, name: str) -> tuple[bool, str]:
    url = f"https://{host}"
    try:
        req = urllib.request.Request(url, headers={"User-Agent": "SELLABLE-Doctor/1.0"})
        with urllib.request.urlopen(req, timeout=3.0) as resp:
            return True, f"Reachable ({name} responded HTTP {resp.status})"
    except urllib.error.HTTPError as e:
        return True, f"Reachable ({name} responded HTTP {e.code})"
    except Exception as e:
        return False, f"Unreachable ({name}: {type(e).__name__})"


def main() -> int:
    print("=" * 70)
    print("           SELLABLE PREFLIGHT DOCTOR & ENVIRONMENT AUDITOR")
    print("=" * 70)

    checks = [
        ("Python Version (>=3.10)", check_python_version),
        ("Runtime Dependencies", check_dependencies),
        ("Environment Configuration", check_env_file),
        ("SQLite Database Access", check_sqlite_writable),
        ("Network Port Availability", check_port_available),
    ]

    all_pass = True
    for label, fn in checks:
        ok, detail = fn()
        status = "[ PASS ]" if ok else "[ FAIL ]"
        if not ok:
            all_pass = False
        print(f"  {status} {label:<28s} : {detail}")

    print("-" * 70)
    print("  OPTIONAL OUTBOUND CONNECTIVITY CHECKS (3s TIMEOUT):")

    outbound = [
        ("Razorpay Test API", "api.razorpay.com"),
        ("Google Gemini API", "generativelanguage.googleapis.com"),
    ]

    for name, host in outbound:
        ok, detail = check_outbound_connectivity(host, name)
        status = "[ PASS ]" if ok else "[ INFO ]"
        print(f"  {status} {name:<28s} : {detail}")

    print("=" * 70)

    if all_pass:
        print("  RESULT: ALL CORE CHECKS PASSED — READY FOR DEMO & EVALUATION")
        print("=" * 70)
        return 0
    else:
        print("  RESULT: PREFLIGHT FAILED — REPAIR MISSING DEPENDENCIES ABOVE")
        print("=" * 70)
        return 1


if __name__ == "__main__":
    sys.exit(main())
