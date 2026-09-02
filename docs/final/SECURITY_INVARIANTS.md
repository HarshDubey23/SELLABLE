# SELLABLE — Security Invariants Specification

This document details the twelve fundamental security invariants enforced across the SELLABLE platform.

### Invariant Table

| ID | Invariant Name | Enforcement Mechanism | Failure Result |
|---|---|---|---|
| **I1** | **No Autonomous Money** | Gateway Gate (`apps/api/tools.py`) | Agent direct money execution is impossible. |
| **I2** | **Deterministic Approval Gate** | 12-Rule Matrix (`apps/api/gateway/engine.py`) | Any rule failure triggers HTTP 403 / REJECT. |
| **I3** | **Exact Binding Matching** | Cryptographic Token (`apps/api/approval.py`) | Mismatched quote/cart/amount blocks Razorpay order. |
| **I4** | **Replay Protection** | SQLite `consumed` flag & Idempotency Key | Second execution attempt rejected as ALREADY_CONSUMED. |
| **I5** | **Temporal Expiry** | Timestamp comparison against `expires_at` | Expired quotes/bindings immediately rejected. |
| **I6** | **Cart Mutation Resistance** | SHA-256 Cart Hash verification | Altered SKUs or prices invalidate the approval hash. |
| **I7** | **Budget Ceiling Guard** | Rule R1 (`price <= budget_paise`) | Over-budget proposals blocked with 0 money calls. |
| **I8** | **Category Boundary** | Rule R2 (`category in allowed_categories`) | Off-category product selections rejected. |
| **I9** | **Prompt Injection Defense** | Deterministic rule overrides probabilistic output | Injected prompts fail gateway rules before payment. |
| **I10** | **Webhook Idempotency** | Event ID tracking & raw-body HMAC | Duplicate webhooks produce no duplicate ledger side effects. |
| **I11** | **Audit Chain Tamper-Evidence** | Chained SHA-256 blocks with genesis block | Any modified SQLite record halts boot and audit verification. |
| **I12** | **Bounded Recovery** | Strict recovery cap matching original mandate | Recovery cannot authorize amounts higher than original mission. |
