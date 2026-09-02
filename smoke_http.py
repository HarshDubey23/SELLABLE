"""Smoke test: spin up the FastAPI app in a background thread and hit
the key endpoints with httpx. Verifies the UI pages render and the
backend endpoints respond.
"""
import sys, os, threading, time
sys.path.insert(0, r'C:\Users\Lenovo\Downloads\SELLABLE')
os.environ['APP_API_KEY'] = 'test-key'
os.environ['MISSION_HMAC_KEY'] = 'test-hmac'

import httpx
from apps.api.main import app
import uvicorn

config = uvicorn.Config(app, host="127.0.0.1", port=8765, log_level="error")
server = uvicorn.Server(config)
t = threading.Thread(target=server.run, daemon=True)
t.start()
time.sleep(3)

base = "http://127.0.0.1:8765"

def hit(path, method="GET", **kw):
    try:
        r = httpx.request(method, base + path, timeout=10, **kw)
        return r.status_code, len(r.content), r.headers.get("content-type", "")
    except Exception as e:
        return 0, 0, str(e)

tests = [
    ("GET", "/"),
    ("GET", "/mission"),
    ("GET", "/products"),
    ("GET", "/gateway-ui"),
    ("GET", "/audit-ui"),
    ("GET", "/attack-ui"),
    ("GET", "/metrics"),
    ("GET", "/status"),
    ("GET", "/catalog"),
    ("GET", "/rules"),
    ("GET", "/invariant/money-calls"),
    ("GET", "/metrics/summary"),
    ("GET", "/attack/scenarios"),
    ("GET", "/audit"),
    ("GET", "/health"),
    ("GET", "/policy"),
    ("GET", "/.well-known/agent-manifest.json"),
]
print(f"{'METHOD':<6} {'PATH':<40} {'STATUS':<6} {'SIZE':<8} {'TYPE':<20}")
print("-" * 90)
for method, path in tests:
    code, size, ctype = hit(path, method)
    ctype_short = ctype.split(";")[0] if ctype else "—"
    print(f"{method:<6} {path:<40} {code:<6} {size:<8} {ctype_short:<20}")

# Try one attack scenario
import json
r = httpx.post(base + "/attack/run_all", timeout=15)
print()
print("Attack lab /run_all:", r.status_code)
data = r.json()
print(f"  Scenarios: {data.get('scenarios_total')}, blocked: {data.get('scenarios_blocked')}")
print(f"  Block rate: {data.get('block_rate')}")

server.should_exit = True
time.sleep(1)
print("\nSmoke test complete.")