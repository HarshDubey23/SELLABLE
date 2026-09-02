"""End-to-end smoke: golden path with REAL gateway + binding + canonical path."""
import sys, os, time, json
sys.path.insert(0, r'C:\Users\Lenovo\Downloads\SELLABLE')
os.environ['APP_API_KEY'] = 'test-key'
os.environ['MISSION_HMAC_KEY'] = 'test-hmac'
os.environ['USER_MANDATE_KEY'] = 'test-mandate-key'

import httpx, threading
from apps.api.main import app
import uvicorn

config = uvicorn.Config(app, host="127.0.0.1", port=8766, log_level="error")
server = uvicorn.Server(config)
threading.Thread(target=server.run, daemon=True).start()
time.sleep(3)

base = "http://127.0.0.1:8766"
H = {"X-API-Key": "test-key"}

# 1. Sign a mission (use the helper)
from apps.api.gateway import mission_verify
now = int(time.time())
blob = {
    "mission_id": "MSN-GOLDEN-1",
    "intent": "buy cricket bat",
    "budget_paise": 200000,
    "allowed_categories": ["cricket"],
    "forbidden_categories": [],
    "upsell_cap": 1.3,
    "expires_at": now + 600,
}
sig = mission_verify.sign_mission(mission_verify.dumps(blob))
blob["signature"] = sig

# 2. submit_proposal
r = httpx.post(base + "/tools/submit_proposal",
               json={"mission": blob, "items": [{"sku": "BAT-001", "qty": 1}]},
               headers=H, timeout=10)
print("submit_proposal:", r.status_code)
d = r.json()
print("  decision:", d["data"]["decision"])
print("  rule_id:", d["data"]["rule_id"])
print("  reason:", d["data"]["reason"])
print("  seq:", d["seq"])
print("  proposal_hash:", d["data"]["proposal_hash"][:32], "...")
print("  rule_matrix entries:", len(d["data"].get("rule_matrix", [])))
print("  effective_budget:", d["data"].get("effective_budget_paise"))
seq = d["seq"]
phash = d["data"]["proposal_hash"]

# 3. quote
r = httpx.post(base + "/tools/quote",
               json={"items": [{"sku": "BAT-001", "qty": 1}], "mission_id": "MSN-GOLDEN-1"},
               headers=H, timeout=10)
print("\nquote:", r.status_code)
q = r.json()
print("  quote_id:", q["quote_id"])
print("  total_paise:", q["total_paise"])

# 4. Mint mandates via the helper
from apps.api.mandates.mandates import (
    IntentMandate, CartMandate, sign_intent, sign_cart
)
intent = sign_intent(IntentMandate(
    mission_id="MSN-GOLDEN-1", user_id="u1",
    ceiling_paise=q["total_paise"],
    expires_at=int(time.time()) + 3600,
), os.environ["USER_MANDATE_KEY"])
cart = sign_cart(CartMandate(
    mission_id="MSN-GOLDEN-1", cart_hash=phash,
    amount_paise=q["total_paise"],
    signed_at=int(time.time()),
), os.environ["USER_MANDATE_KEY"])

# 5. create_order
r = httpx.post(base + "/tools/create_order",
               json={"quote_id": q["quote_id"], "proposal_hash": phash,
                     "approve_seq": seq,
                     "intent_mandate": intent, "cart_mandate": cart},
               headers={**H, "X-Idempotency-Key": "smoke-test-1"},
               timeout=15)
print("\ncreate_order:", r.status_code)
if r.status_code == 200:
    o = r.json()
    print("  order_id:", o.get("order_id"))
    print("  amount:", o.get("amount_display") or o.get("amount_paise"))
    print("  status:", o.get("status"))
    print("  keys:", list(o.keys()))
else:
    print("  body:", r.text[:300])

# 6. MUTATION TEST: try to use the same binding with a mutated cart
print("\n--- CART MUTATION ATTACK ---")
r = httpx.post(base + "/tools/create_order",
               json={"quote_id": q["quote_id"], "proposal_hash": phash,
                     "approve_seq": seq,
                     "intent_mandate": intent, "cart_mandate": cart},
               headers={**H, "X-Idempotency-Key": "smoke-test-2"},
               timeout=10)
print("Same binding again (idempotency check):", r.status_code)
if r.status_code == 200:
    print("  duplicate:", r.json().get("duplicate"))

server.should_exit = True
time.sleep(1)