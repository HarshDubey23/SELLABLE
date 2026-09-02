# SELLABLE — Comprehensive Baseline Engineering Audit

**Audit Date:** 2026-09-02  
**Commit Baseline:** 1761135  
**Review Standard:** Razorpay AI Buildathon Track 01 (Autonomous Commerce Security)

---

## 1. System Inventory & Classification

| Component | Reality Status | Verification Evidence |
|---|---|---|
| **Buyer Agent (LLM)** | **PROVEN** | Live execution via Gemini 2.5/3.5 Flash |
| **Merchant Catalog & Quoting** | **PROVEN** | Exact server-side quoting with SHA-256 price locks |
| **Deterministic Gateway (R1–R12)** | **PROVEN** | 12 fail-closed rules evaluated across 82 automated tests |
| **Approval Binding Engine** | **PROVEN** | Atomic SQL update (`UPDATE bindings SET consumed_at ... WHERE consumed_at IS NULL`) |
| **Single Money Boundary** | **PROVEN** | All order creation strictly gated via `apps/api/approval.py` -> `apps/api/gateway_service.py` |
| **Razorpay Test Mode Integration** | **PROVEN — TEST MODE** | Live authenticated API calls to `api.razorpay.com/v1/orders` |
| **Gateway Simulator & Fault Injection** | **PROVEN** | 10 deterministic fault modes (`CREATE_ORDER_TIMEOUT`, `GATEWAY_429`, etc.) |
| **Strict Money Type (`Money` / `Paise`)** | **PROVEN** | Integer paise internally, no float arithmetic, INR currency constraint |
| **Webhook HMAC Verification** | **PROVEN** | Raw-body HMAC-SHA256 signature verification & deduplication |
| **Tamper-Evident Audit Ledger** | **PROVEN** | SHA-256 hash-chained block storage with boot-time self-verification |
| **User Wallet Mandate Signing** | **SIMULATED** | Intent and cart mandates signed out-of-band |
| **Payment Failure Recovery** | **PROVEN** | Bounded recovery policy halts without budget escalation |

---

## 2. Invariants Audit Summary
* **Invariant I1 (No Autonomous Money):** Direct client/agent requests to `/tools/create_order` without a matching binding return HTTP 403 Forbidden.
* **Invariant I2 (Exact Binding Match):** Any change in SKU, price, cart hash, or quote ID invalidates the binding.
* **Invariant I3 (Replay Protection):** Atomic single-use consumption prevents race conditions (proven under 20-thread concurrency).
* **Invariant I4 (Zero Money Calls Under Attack):** All 8 adversarial scenarios reject before touching the money boundary.
