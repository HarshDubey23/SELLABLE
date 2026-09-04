"""Capture final submission screenshots from live SELLABLE routes."""
from __future__ import annotations

import os
import subprocess
import sys
import time
import urllib.request
from pathlib import Path
from urllib.parse import urlparse

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "docs" / "submission" / "screenshots"
BASE = os.environ.get("SCREENSHOT_BASE_URL", "http://127.0.0.1:8010").rstrip("/")
PORT = urlparse(BASE).port or 8010

os.environ.setdefault("MISSION_HMAC_KEY", "test-mission-hmac")
os.environ.setdefault("APP_API_KEY", "sellable_demo_key")
os.environ.setdefault("USER_MANDATE_KEY", "test-user-mandate")
os.environ.setdefault("RAZORPAY_KEY_ID", "test")
os.environ.setdefault("RAZORPAY_KEY_SECRET", "test")
os.environ.setdefault("RAZORPAY_WEBHOOK_SECRET", "test-webhook-secret")
os.environ.setdefault("SELLABLE_BASE_URL", BASE)


def server_up() -> bool:
    try:
        with urllib.request.urlopen(f"{BASE}/health", timeout=2) as response:
            return response.status == 200
    except Exception:
        return False


def ensure_server() -> subprocess.Popen | None:
    if server_up():
        print(f"[screenshots] reusing server at {BASE}")
        return None

    proc = subprocess.Popen(
        [
            sys.executable,
            "-m",
            "uvicorn",
            "apps.api.main:app",
            "--host",
            "127.0.0.1",
            "--port",
            str(PORT),
        ],
        cwd=ROOT,
        env={**os.environ},
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
    )
    for _ in range(80):
        if server_up():
            print(f"[screenshots] uvicorn booted at {BASE}")
            return proc
        time.sleep(0.5)
    proc.terminate()
    raise RuntimeError("uvicorn did not become healthy within 40s")


def main() -> int:
    OUT.mkdir(parents=True, exist_ok=True)
    capture_db = OUT / ".capture_runtime.db"
    if capture_db.exists():
        capture_db.unlink()
    os.environ["SELLABLE_DB_PATH"] = str(capture_db)
    proc = ensure_server()
    try:
        from playwright.sync_api import sync_playwright

        targets = [
            ("01_command_center.png", "/"),
            ("02_judge_mode.png", "/judge"),
            ("03_live_mission.png", "/mission"),
            ("04_attack_lab.png", "/attack-ui"),
            ("05_gateway_rules.png", "/gateway-ui"),
            ("06_audit_ledger.png", "/audit-ui"),
        ]
        with sync_playwright() as playwright:
            browser = playwright.chromium.launch(headless=True)
            page = browser.new_page(viewport={"width": 1440, "height": 1000})
            for filename, route in targets:
                page.goto(f"{BASE}{route}", wait_until="networkidle")
                page.wait_for_timeout(750)
                page.screenshot(path=str(OUT / filename), full_page=True)
                print(f"[screenshots] wrote {OUT / filename}")
            browser.close()
        return 0
    finally:
        if proc is not None:
            proc.terminate()
        if capture_db.exists():
            capture_db.unlink()


if __name__ == "__main__":
    raise SystemExit(main())
