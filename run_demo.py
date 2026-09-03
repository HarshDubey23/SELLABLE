#!/usr/bin/env python3
"""SELLABLE — Single Entry Point Demo Launcher & Reliability Runner.

Standard library only. Cross-platform parity (Windows, macOS, Linux).
ASCII output only for cp1252 compatibility.

Usage:
    python run_demo.py [--port 8000] [--no-browser]
"""
from __future__ import annotations

import argparse
import os
import secrets
import subprocess
import sys
import time
import urllib.request
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent
ENV_PATH = REPO_ROOT / ".env"
REQUIREMENTS_PATH = REPO_ROOT / "apps" / "api" / "requirements.txt"
VENV_DIR = REPO_ROOT / ".venv"


def check_python_version():
    v = sys.version_info
    if v.major < 3 or (v.major == 3 and v.minor < 10):
        print(f"[ERROR] Python >= 3.10 is required. Found Python {v.major}.{v.minor}.{v.micro}")
        print("Remediation: Install Python 3.10 or newer from https://python.org")
        sys.exit(1)


def ensure_env_file():
    if not ENV_PATH.exists():
        print("[SETUP] .env file missing — auto-generating dev environment keys...")
        hmac_key = secrets.token_hex(32)
        mandate_key = secrets.token_hex(32)
        api_key = secrets.token_hex(32)

        content = f"""# SELLABLE Auto-Generated Environment
RAZORPAY_KEY_ID=""
RAZORPAY_KEY_SECRET=""
RAZORPAY_WEBHOOK_SECRET=""
MISSION_HMAC_KEY={hmac_key}
USER_MANDATE_KEY={mandate_key}
APP_API_KEY={api_key}
PORT=8000
SELLABLE_BASE_URL="http://127.0.0.1:8000"
GEMINI_MODEL=google/gemini-1.5-flash
OPENROUTER_MODEL=google/gemini-1.5-flash
"""
        ENV_PATH.write_text(content, encoding="utf-8")
        print("[NOTICE] Demo mode: payments SIMULATED, reasoning deterministic.")
        print("         Add real test-mode keys to .env to call the live Razorpay test API.")
    else:
        print("[SETUP] Existing .env file loaded.")


def ensure_virtualenv():
    # If already running inside virtualenv or requirements installed, proceed
    try:
        import fastapi
        import uvicorn
        return
    except ImportError:
        pass

    print("[SETUP] Virtualenv or requirements missing. Setting up environment...")
    if not VENV_DIR.exists():
        print("[SETUP] Creating .venv virtual environment...")
        try:
            subprocess.run([sys.executable, "-m", "venv", str(VENV_DIR)], check=True)
        except Exception as e:
            print(f"[ERROR] Failed to create virtual environment: {e}")
            print("Remediation: Run 'python -m venv .venv' manually.")
            sys.exit(1)

    py_bin = (VENV_DIR / ("Scripts" if sys.platform == "win32" else "bin") / ("python.exe" if sys.platform == "win32" else "python"))
    print("[SETUP] Installing pinned runtime dependencies...")
    try:
        subprocess.run([str(py_bin), "-m", "pip", "install", "-q", "-r", str(REQUIREMENTS_PATH)], check=True)
    except Exception as e:
        print(f"[ERROR] Failed to install dependencies: {e}")
        print(f"Remediation: Activate virtualenv and run 'pip install -r {REQUIREMENTS_PATH}'")
        sys.exit(1)

    # Re-exec under virtualenv python
    print("[SETUP] Environment ready. Restarting process under virtualenv...")
    os.execv(str(py_bin), [str(py_bin)] + sys.argv)


def seed_and_sign_missions():
    print("[SETUP] Idempotently seeding database and signing demo missions...")
    sign_script = REPO_ROOT / "scripts" / "sign_mission.py"
    if sign_script.exists():
        try:
            subprocess.run([sys.executable, str(sign_script)], cwd=str(REPO_ROOT), check=True)
            print("[SETUP] Demo missions signed successfully.")
        except Exception as e:
            print(f"[WARN] Mission signing script notice: {e}")


def poll_health(url: str, max_seconds: float = 30.0) -> bool:
    start = time.time()
    while time.time() - start < max_seconds:
        try:
            req = urllib.request.Request(f"{url}/health")
            with urllib.request.urlopen(req, timeout=1.0) as resp:
                if resp.status == 200:
                    return True
        except Exception:
            time.sleep(0.5)
    return False


def port_in_use(port: int, host: str = "127.0.0.1") -> bool:
    import socket
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        s.settimeout(0.5)
        return s.connect_ex((host, port)) == 0


def run_smoke_checks(url: str) -> bool:
    print("[SMOKE] Running automated system health smoke checks...")
    endpoints = ["/health", "/api/v1/telemetry", "/gateway/proof", "/audit/verify", "/judge"]
    all_ok = True
    for ep in endpoints:
        try:
            req = urllib.request.Request(f"{url}{ep}")
            with urllib.request.urlopen(req, timeout=3.0) as resp:
                if resp.status == 200:
                    print(f"  [ PASS ] {ep:<24s} -> HTTP 200 OK")
                else:
                    print(f"  [ FAIL ] {ep:<24s} -> HTTP {resp.status}")
                    all_ok = False
        except Exception as e:
            print(f"  [ FAIL ] {ep:<24s} -> {e}")
            all_ok = False
    return all_ok


def main():
    parser = argparse.ArgumentParser(description="SELLABLE Single Entry Point Demo Launcher")
    parser.add_argument("--host", type=str, default="127.0.0.1", help="Server host (default: 127.0.0.1)")
    parser.add_argument("--port", type=int, default=8000, help="Server port (default: 8000)")
    parser.add_argument("--no-browser", action="store_true", help="Do not automatically open browser")
    args = parser.parse_args()

    print("=" * 72)
    print("      SELLABLE — AGENT-SAFE COMMERCE PLATFORM (RAZORPAY BUILDATHON)")
    print("=" * 72)

    check_python_version()
    ensure_env_file()
    ensure_virtualenv()
    seed_and_sign_missions()

    port = args.port
    host = args.host
    base_url = f"http://{host}:{port}"

    if port_in_use(port, host=host):
        print(f"[ERROR] Port {port} is already in use on {host}.")
        print(f"Try: python run_demo.py --port {port + 1}")
        sys.exit(1)

    os.environ["PORT"] = str(port)
    os.environ["SELLABLE_BASE_URL"] = base_url

    print(f"\n[BOOT] Starting Uvicorn server daemon on {host}:{port}...")
    server_proc = subprocess.Popen(
        [sys.executable, "-m", "uvicorn", "apps.api.main:app", "--host", host, "--port", str(port)],
        cwd=str(REPO_ROOT),
    )

    try:
        print("[BOOT] Waiting for server health check (max 30s)...")
        if not poll_health(base_url, max_seconds=30.0):
            print("[ERROR] Server failed to become healthy within 30 seconds.")
            server_proc.terminate()
            server_proc.wait()
            sys.exit(1)

        print("[BOOT] Server is LIVE and healthy!")
        print("-" * 72)
        if not run_smoke_checks(base_url):
            print("[ERROR] Critical smoke checks failed. Stopping server.")
            server_proc.terminate()
            server_proc.wait()
            sys.exit(1)

        print("=" * 72)
        print("                SELLABLE DEMO URL DIRECTORY MENU")
        print("=" * 72)
        print(f"  1. JUDGE CONSOLE (30s Demo) : {base_url}/judge")
        print(f"  2. COMMAND CENTER           : {base_url}/")
        print(f"  3. LIVE MISSION RUNNER      : {base_url}/mission")
        print(f"  4. CHAOS CONTROL ROOM       : {base_url}/chaos")
        print(f"  5. INTERACTIVE ARCHITECTURE : {base_url}/architecture")
        print(f"  6. ADVERSARIAL ATTACK LAB   : {base_url}/attack-ui")
        print(f"  7. SHA-256 AUDIT LEDGER     : {base_url}/audit-ui")
        print(f"  8. POLICY MATRIX (R1-R12)   : {base_url}/gateway-ui")
        print(f"  9. MERCHANT CATALOG         : {base_url}/products")
        print(f" 10. WHY SELLABLE PHILOSOPHY  : {base_url}/why")
        print(f" 11. METRICS & TELEMETRY      : {base_url}/metrics")
        print("=" * 72)
        print("  Press Ctrl+C to stop the server cleanly.")

        server_proc.wait()
    except KeyboardInterrupt:
        print("\n[SHUTDOWN] Received Ctrl+C — shutting down SELLABLE server cleanly...")
        server_proc.terminate()
        server_proc.wait()
        print("[SHUTDOWN] Server stopped. Goodbye!")
        sys.exit(0)


if __name__ == "__main__":
    main()
