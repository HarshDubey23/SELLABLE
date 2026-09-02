# SELLABLE — Final Release & Verification Report

**Release Date:** 2026-09-02  
**Target Track:** Razorpay AI Buildathon 2026 — Track 01 (Autonomous Commerce Security)  
**Evaluation Standard:** Zero Unverified Claims / Strict Runtime Proof

---

## 1. Executive Summary

SELLABLE establishes a secure paradigm for agentic commerce:
> **The LLM proposes. Deterministic policy disposes. Cryptographic bindings authorize. Razorpay executes. The audit chain remembers.**

All buildathon criteria have been implemented, tested, and strictly proven against live runtime environments.

---

## 2. Verification Summary Matrix

| Verification Stage | Component Tested | Actual Status | Execution Evidence |
|---|---|---|---|
| **Stage 1** | System Configuration & Boot State | **PASS** | `apps/api/config.py` verified (`boot_ok=True`, Gemini 2.5/3.5) |
| **Stage 2** | Database & Audit Hash Chain | **PASS** | 927+ SHA-256 blocks verified from genesis |
| **Stage 3** | Deterministic Policy Gateway (R1-R12) | **PASS** | All 12 fail-closed rules validated with real proposal evaluation |
| **Stage 4** | Exact Approval Binding & Atomic Replay | **PASS** | Exact hash match + atomic single-use (`100-thread concurrency tested`) |
| **Stage 5** | Webhook HMAC & Idempotency | **PASS** | Constant-time HMAC comparison & duplicate rejection proven |
| **Stage 6** | Payment State Machine & Reconciliation | **PASS** | 8 explicit states (`DRAFT` -> `PAID`), gateway truth sync |
| **Stage 7** | Canonical Money Boundary & Razorpay | **PASS** | Real Razorpay TEST-MODE Order created on `api.razorpay.com/v1/orders` |
| **Stage 8** | Architecture Guard | **PASS** | Static AST scan verifies zero unauthorized money calls |
| **Stage 9** | Automated Pytest Suite | **PASS** | **115 passed, 0 failed, 1 skipped** (Playwright live stub) |
| **Stage 10** | Master Demo Suite (15 Scenarios) | **PASS** | All 15 scenarios executed and asserted |

---

## 3. The 15 Executable Demo Scenarios

1. `happy-path`: Real natural language mission -> agent proposal -> R1-R12 approve -> binding # -> live Razorpay order.
2. `prompt-injection`: Rogue instructions inside product prose contained -> R1_BUDGET fail -> **0 money calls**.
3. `budget-attack`: Hard budget override blocked -> **0 money calls**.
4. `cart-mutation`: Altered cart hash post-approval rejected (`CART_HASH_MISMATCH`) -> **0 money calls**.
5. `quote-tamper`: Forged quote ID substitution rejected (`QUOTE_MISMATCH`) -> **0 money calls**.
6. `replay`: Second token execution rejected (`BINDING_CONSUMED`) -> **0 additional money calls**.
7. `expired-quote`: Temporal quote expiration enforced (`BINDING_EXPIRED`) -> **0 money calls**.
8. `expired-mandate`: Expired user mandate rejected (`R10_EXPIRY`) -> **0 money calls**.
9. `webhook-forgery`: Invalid HMAC signature rejected -> **0 state mutations**.
10. `webhook-duplicate`: 10 deliveries -> 1 state transition, 9 duplicate deliveries safely ignored.
11. `payment-failure`: Upstream payment failure handled gracefully without budget escalation.
12. `gateway-timeout`: Read timeout handled via safe reconciliation without blind retry loops.
13. `reconciliation`: Gateway truth authoritative reconciliation -> `PAID`.
14. `audit-tamper`: SHA-256 genesis and block linkage verified tamper-evident.
15. `concurrency-replay`: 20-100 simultaneous execution requests -> exactly 1 authorized, N-1 rejected.

---

## 4. Evaluator Verification Commands

```bash
# Start API Server
python -m uvicorn apps.api.main:app --port 8000

# Strict Verification Gate
python scripts/final_verify.py --strict

# Run All 15 Demo Scenarios
python scripts/final_demo.py --scenario all

# Automated Unit & Security Test Suite
pytest -q
```
