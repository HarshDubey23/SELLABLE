"""Day 2 evidence capture: 3 PNG screenshots + 3 TXT "screenshots".

Boots uvicorn on :8000 in a subprocess (or reuses a running server),
waits for /health, then captures:
  docs/log/day02_audit_timeline.png   - /audit/timeline HTML cards
  docs/log/day02_openapi.png          - /docs Swagger UI
  docs/log/day02_gateway_proof.txt    - JSON from /gateway/proof
  docs/log/day02_smoke.txt            - stdout of bash scripts/smoke.sh
  docs/log/day02_injection_demo.txt   - JSON from /demo/injection/I1
  docs/log/day02_pytest.txt           - stdout of python -m pytest -q
"""
import os
import subprocess
import sys
import time
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
LOG = ROOT / "docs" / "log"

os.environ.setdefault("MISSION_HMAC_KEY", "test")
os.environ.setdefault("RAZORPAY_KEY_ID", "test")
os.environ.setdefault("RAZORPAY_KEY_SECRET", "test")
os.environ.setdefault("RAZORPAY_WEBHOOK_SECRET", "test")

BASE = "http://localhost:8000"


def server_up() -> bool:
    try:
        with urllib.request.urlopen(f"{BASE}/health", timeout=2) as r:
            return r.status == 200
    except Exception:
        return False


def ensure_server():
    if server_up():
        print("[screenshots] reusing server already on :8000")
        return None
    env = {**os.environ}
    proc = subprocess.Popen(
        [sys.executable, "-m", "uvicorn", "apps.api.main:app",
         "--port", "8000"],
        cwd=ROOT, env=env,
        stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
    )
    for _ in range(60):
        if server_up():
            print("[screenshots] uvicorn booted")
            return proc
        time.sleep(0.5)
    proc.terminate()
    raise RuntimeError("uvicorn did not become healthy within 30s")


def _find_bash() -> str:
    """Prefer Git Bash on Windows; fall back to whatever 'bash' resolves to."""
    for cand in (r"C:\Program Files\Git\bin\bash.exe",
                 r"C:\Program Files\Git\usr\bin\bash.exe"):
        if Path(cand).exists():
            return cand
    return "bash"


def main() -> int:
    LOG.mkdir(parents=True, exist_ok=True)
    proc = ensure_server()
    try:
        from playwright.sync_api import sync_playwright

        # Warm the audit chain with real entries so the timeline
        # screenshot shows actual traffic, not just GENESIS.
        for path in ("/gateway/proof", "/demo/injection/I1",
                     "/tools/quote"):
            try:
                if path == "/tools/quote":
                    req = urllib.request.Request(
                        f"{BASE}{path}",
                        data=b'{"items":[{"sku":"BAT-001","qty":1}],'
                             b'"mission_id":"shot"}',
                        headers={"Content-Type": "application/json"})
                    urllib.request.urlopen(req, timeout=5).read()
                else:
                    urllib.request.urlopen(f"{BASE}{path}", timeout=5).read()
            except Exception as exc:  # noqa: BLE001 - best-effort warmup
                print(f"[screenshots] warmup {path} skipped: {exc}")

        with sync_playwright() as p:
            browser = p.chromium.launch(headless=True)
            page = browser.new_page(viewport={"width": 1280, "height": 900})

            page.goto(f"{BASE}/audit/timeline", wait_until="networkidle")
            page.screenshot(path=str(LOG / "day02_audit_timeline.png"),
                            full_page=True)
            print("[screenshots] day02_audit_timeline.png")

            page.goto(f"{BASE}/docs", wait_until="networkidle")
            page.wait_for_timeout(1500)  # let swagger render
            page.screenshot(path=str(LOG / "day02_openapi.png"),
                            full_page=False)
            print("[screenshots] day02_openapi.png")

            page.goto(f"{BASE}/demo/injection/I1", wait_until="networkidle")
            page.screenshot(path=str(LOG / "day02_injection_demo.png"),
                            full_page=True)
            print("[screenshots] day02_injection_demo.png")

            browser.close()

        # TXT / JSON evidence
        proof = urllib.request.urlopen(
            f"{BASE}/gateway/proof", timeout=5).read().decode()
        (LOG / "day02_gateway_proof.txt").write_text(proof, encoding="utf-8")

        inj = urllib.request.urlopen(
            f"{BASE}/demo/injection/I1", timeout=5).read().decode()
        (LOG / "day02_injection_demo.txt").write_text(inj, encoding="utf-8")
        try:
            inj_json = json.dumps(json.loads(inj), indent=2)
            (LOG / "day02_injection_demo.json").write_text(inj_json, encoding="utf-8")
        except Exception:
            (LOG / "day02_injection_demo.json").write_text(inj, encoding="utf-8")

        smoke = subprocess.run([_find_bash(), "scripts/smoke.sh"], cwd=ROOT,
                               capture_output=True, text=True)
        (LOG / "day02_smoke.txt").write_text(smoke.stdout + smoke.stderr,
                                             encoding="utf-8")

        tests = subprocess.run([sys.executable, "-m", "pytest", "-q"],
                               cwd=ROOT, capture_output=True, text=True)
        (LOG / "day02_pytest.txt").write_text(tests.stdout + tests.stderr,
                                              encoding="utf-8")
        print("[screenshots] txt artifacts written")
        return 0
    finally:
        if proc is not None:
            proc.terminate()


if __name__ == "__main__":
    raise SystemExit(main())
