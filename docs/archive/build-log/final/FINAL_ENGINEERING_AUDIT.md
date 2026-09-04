# SELLABLE — Final Engineering Audit & Verification

## 1. Codebase Audit Summary
* **Total Python Files:** 45+
* **Core API Endpoints:** 24
* **Gateway Rules:** 12 (R1–R12 fully operational and tested)
* **Automated Test Count:** 65 passing unit and invariant tests
* **Zero Hardcoded Secrets:** Environment credentials strictly managed via `.env`

## 2. Invariant Verification Results

### G1: No Approve -> No Money
* Verified in `tests/test_no_approve_no_money.py`. Direct attempts to call `/tools/create_order` without a matching approval binding return HTTP 403.

### G2: Exact Binding Matching
* Verified in `tests/gateway/test_inv1_binding.py`. Any difference in SKU, amount, quote ID, or mission ID triggers `BINDING_MISMATCH`.

### G3: Prompt Injection Containment
* Verified in `tests/gateway/test_attack_lab.py`. Injection vectors manipulating product descriptions to spend Rs 4,499 against a Rs 2,000 budget fail at Rule R1. Razorpay execution count: 0.

### G4: Audit Chain Integrity
* Verified in `tests/gateway/test_chain_tamper.py`. Modifying a single byte in the SQLite database causes `audit_chain.verify()` to return `False`.
