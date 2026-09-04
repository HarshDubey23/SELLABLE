"""Verify the audit chain linkage failure -> diagnosis -> recovery."""
import json
import urllib.request

audit = json.load(urllib.request.urlopen("http://localhost:8000/audit",
                                         timeout=30))
print("chain verified:", audit["verified"], "| entries:",
      len(audit["entries"]))
print()
print("--- enriched rows (seq >= 62) ---")
for e in audit["entries"]:
    if e["seq"] >= 62:
        print(f"[{e['action_id'] if 'action_id' in e else 'aud_' + str(e['seq'])}] "
              f"{e['actor']}/{e['action']}")
        print(f"    parent={e.get('parent_action_id')} "
              f"idem={str(e.get('idempotency_key'))[:20]} "
              f"error_code={e.get('error_code')} "
              f"review={e.get('review_state')}")
        rt = e.get("reasoning_trace")
        if rt:
            print(f"    reasoning_trace: {rt[:160]}...")
print()
# explicit linkage assertion
rows = {f"aud_{e['seq']}": e for e in audit["entries"]}
fail, reason, link = (rows.get("aud_67"), rows.get("aud_68"),
                      rows.get("aud_69"))
assert fail and fail["action"] == "payment_attempt_failed", fail
assert reason and reason.get("parent_action_id") == "aud_67", reason
assert link and link.get("parent_action_id") == "aud_67", link
print("LINKAGE VERIFIED: aud_68(recovery_reasoned) -> aud_67(failure)")
print("LINKAGE VERIFIED: aud_69(payment_link_issued) -> aud_67(failure)")
