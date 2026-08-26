"""E2E proof: sign mission -> propose (approve+reject) -> quote -> order -> replay."""
import json
import os
import sys
import time

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from pathlib import Path

import requests
from dotenv import load_dotenv

load_dotenv(Path(__file__).resolve().parents[1] / ".env")
from apps.api.gateway import mission_verify as mv

BASE = "http://localhost:8000"


def signed_mission(budget_paise):
    m = {"mission_id": f"e2e_{int(time.time())}", "intent": "cricket gift",
         "budget_paise": budget_paise,
         "allowed_categories": ["cricket"], "forbidden_categories": [],
         "upsell_cap": 1.3, "expires_at": int(time.time()) + 600}
    m["signature"] = mv.sign_mission(mv.dumps(m))
    return m


def show(tag, r):
    print(f"--- {tag}: HTTP {r.status_code}")
    print(json.dumps(r.json(), indent=1)[:400])


# 1. APPROVE path: BAT-001 (149900) under 200000 budget
mission = signed_mission(200000)
r = requests.post(f"{BASE}/tools/submit_proposal",
                  json={"mission": mission, "items": [{"sku": "BAT-001", "qty": 1}]})
show("PROPOSE under-budget", r)
v = r.json()
assert v["data"]["decision"] == "APPROVE", v
seq, phash = v["seq"], v["data"]["proposal_hash"]

# 2. REJECT path: KIT-001 (449900) over budget -> R1_BUDGET
mission_hi = signed_mission(200000)
r = requests.post(f"{BASE}/tools/submit_proposal",
                  json={"mission": mission_hi, "items": [{"sku": "KIT-001", "qty": 1}]})
show("PROPOSE over-budget", r)
d = r.json()["data"]
assert d["decision"] == "REJECT" and d["rule_id"] == "R1_BUDGET", d

# 3. explain_reject for the reject verdict
r = requests.get(f"{BASE}/tools/explain_reject", params={"seq": seq + 1})
show("EXPLAIN_REJECT", r)

# 4. /policy introspection
r = requests.get(f"{BASE}/policy")
print(f"--- POLICY: {r.status_code}, rules_count={r.json()['rules_count']}")

# 5. quote + create_order with the APPROVE binding
r = requests.post(f"{BASE}/tools/quote",
                  json={"items": [{"sku": "BAT-001", "qty": 1}],
                        "mission_id": mission["mission_id"]})
show("QUOTE", r)
quote_id = r.json()["quote_id"]

r = requests.post(f"{BASE}/tools/create_order",
                  json={"quote_id": quote_id, "proposal_hash": phash,
                        "approve_seq": seq},
                  headers={"X-Idempotency-Key": f"idem-{seq}"})
show("CREATE_ORDER (gated)", r)
order_id = r.json().get("order_id")

# 6. idempotency replay
r = requests.post(f"{BASE}/tools/create_order",
                  json={"quote_id": quote_id, "proposal_hash": phash,
                        "approve_seq": seq},
                  headers={"X-Idempotency-Key": f"idem-{seq}"})
show("CREATE_ORDER replay", r)
assert r.json().get("duplicate") is True

# 7. G1 gate: wrong approve_seq must 403
r = requests.post(f"{BASE}/tools/create_order",
                  json={"quote_id": quote_id, "proposal_hash": phash,
                        "approve_seq": 99999},
                  headers={"X-Idempotency-Key": f"idem-bad-{seq}"})
print(f"--- CREATE_ORDER no-binding: HTTP {r.status_code} (expect 403)")

# 8. unsigned/tampered mission must fail R9
bad = signed_mission(200000); bad["budget_paise"] = 999999999  # tamper AFTER signing
r = requests.post(f"{BASE}/tools/submit_proposal",
                  json={"mission": bad, "items": [{"sku": "BAT-001", "qty": 1}]})
show("PROPOSE tampered-mission", r)
assert r.status_code == 200 and r.json()["data"]["rule_id"] == "R9_SIGNATURE"

# 9. health with chain status
r = requests.get(f"{BASE}/health")
print("--- HEALTH:", json.dumps(r.json()))

print("\nE2E COMPLETE: approve/reject/explain/policy/order/replay/gate/R9 all exercised.")
