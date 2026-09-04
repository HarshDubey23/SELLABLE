# SELLABLE — Critical Security Invariants & Guarantees (G1–G16)

**Evaluation Standard:** Zero Unverified Claims / 100% Executable Proof

---

## 🛡️ Machine-Readable Invariant Mapping Matrix

| Guarantee ID | Invariant Name | Security Rule / Boundary | Executable Test Location | Test Function |
|---|---|---|---|---|
| **G1** | Denied Policy | `0 Money Calls` on Gateway Rejection | `tests/security/test_all_20_attacks.py` | `test_i1_budget_override` |
| **G2** | Invalid Binding | `0 Money Calls` on Binding Mismatch | `tests/security/test_all_20_attacks.py` | `test_i11_quote_substitution` |
| **G3** | Expired Binding | `0 Money Calls` on Expiration | `tests/security/test_all_20_attacks.py` | `test_i13_expired_quote` |
| **G4** | Replayed Binding | `0 Additional Money Calls` on Reuse | `tests/security/test_all_20_attacks.py` | `test_i12_replay_attack` |
| **G5** | Quote Mutation | Server Quote ID / Amount Tamper Rejected | `tests/security/test_all_20_attacks.py` | `test_i10_quote_mutation` |
| **G6** | Cart Mutation | SKU / Cart Hash Tamper Rejected | `tests/security/test_all_20_attacks.py` | `test_i9_cart_mutation` |
| **G7** | Amount Mutation | Client Claimed Price Override Rejected | `tests/security/test_all_20_attacks.py` | `test_i5_free_price_attack` |
| **G8** | SKU / Quantity Mutation | Non-Positive / Unlisted SKU Rejected | `tests/security/test_all_20_attacks.py` | `test_i17_quantity_manipulation` |
| **G9** | Invalid Webhook | Forged HMAC Signature Rejected | `tests/test_webhook.py` | `test_invalid_webhook_signature_rejected` |
| **G10** | Duplicate Webhook | Webhook Delivery Idempotency | `tests/test_webhook.py` | `test_duplicate_webhook_event_ignored` |
| **G11** | Idempotency Key | Single Logical Order per Key | `tests/concurrency/test_concurrency_100.py` | `test_100_concurrent_idempotency_key_requests` |
| **G12** | Concurrent Replay | Exactly 1 Succeeded, N-1 Rejected | `tests/concurrency/test_concurrency_100.py` | `test_100_concurrent_binding_consumption_attempts` |
| **G13** | Gateway Timeout | No Blind Retries on Ambiguity | `tests/test_payment_state_and_reconciliation.py` | `test_gateway_timeout_requires_reconciliation` |
| **G14** | Payment State | State Derived Solely from Gateway Truth | `tests/test_payment_state_and_reconciliation.py` | `test_reconciliation_resolves_gateway_truth` |
| **G15** | Audit Tampering | Disk Ledger Tamper Detected | `tests/test_audit_chain_true_tamper.py` | `test_true_sqlite_tamper_detection` |
| **G16** | LLM Claim ≠ Authority | Agent Reasoning Isolated from Money Gateway | `tests/test_architecture_guard.py` | `test_pure_deterministic_gateway_no_llm_imports` |

---

## 🔍 Invariant Verification Command

To execute and assert all G1 through G16 guarantees in a single run:

```bash
pytest tests/security/test_all_20_attacks.py tests/test_payment_state_and_reconciliation.py tests/concurrency/test_concurrency_100.py tests/test_audit_chain_true_tamper.py tests/test_architecture_guard.py tests/test_webhook.py -v
```
