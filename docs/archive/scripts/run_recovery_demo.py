"""Run the live failure-recovery scenario and save the trace."""
import json
import sys
import urllib.request

scenario = sys.argv[1] if len(sys.argv) > 1 else "payment_failure_recovery"
out = (sys.argv[2] if len(sys.argv) > 2 else
       "docs/log/day03/scenario_payment_failure_recovery.json")

req = urllib.request.Request(
    f"http://localhost:8000/agent/run-scenario/{scenario}",
    data=b"", method="POST")
d = json.load(urllib.request.urlopen(req, timeout=300))
with open(out, "w", encoding="utf-8") as f:
    json.dump(d, f, indent=1)

print("STATUS:", d.get("status"))
print("ORDER:", d.get("order_id"), "| amount_paise:", d.get("amount_paise"))
print()
rec = d.get("recovery") or {}
print("=== RECOVERY SUMMARY ===")
for k in ("outcome", "failed_payment_action_id", "reasoning_action_id",
          "link_action_id", "failure", "llm_decision", "payment_link"):
    print(f"{k}: {json.dumps(rec.get(k), default=str)[:220]}")
print()
print("=== TRACE ===")
for e in d.get("trace", {}).get("events", []):
    print(f"[{e['seq']:02d}] {e['actor']}/{e['action']}: "
          f"{e['summary'][:105]}")
