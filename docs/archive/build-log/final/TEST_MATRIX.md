# SELLABLE — Comprehensive Test Matrix

| Test Suite / Scenario | Invariant Checked | Expected Result | Actual Result | Status |
|---|---|---|---|---|
| `test_no_approve_no_money.py` | G1: Money Boundary Gate | HTTP 403 Forbidden | HTTP 403 Forbidden | PASS |
| `test_inv1_binding.py` | G2: Approval Binding Match | Binding Mismatch Blocked | Blocked (0 calls) | PASS |
| `test_attack_lab.py` | G3: Attack Containment | All 8 attacks rejected | All 8 rejected | PASS |
| `test_chain_tamper.py` | G4: Audit Tamper Detection | `verify() == False` | `verify() == False` | PASS |
| `test_matrix.py` | R1–R12 Rule Matrix | 12/12 rules enforced | 12/12 enforced | PASS |
| `test_r10_expiry.py` | R10: Temporal Expiry | Expired quote rejected | HTTP 409 Expired | PASS |
| `test_r9_signature.py` | R9: Mission Signature | Invalid signature rejected | HTTP 403 Invalid Sig | PASS |
| `test_webhook.py` | Webhook HMAC Idempotency | Duplicate webhooks safe | 1 update, 9 ignored | PASS |
| `test_mandates.py` | User Intent & Cart Mandates | Missing mandate rejected | HTTP 422 Required | PASS |
