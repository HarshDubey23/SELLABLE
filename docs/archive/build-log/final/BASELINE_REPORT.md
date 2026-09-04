# SELLABLE - Baseline Engineering Audit Report

**Date:** 2026-09-02  
**Platform:** Windows 11 (NT 10.0) / PowerShell  
**Python Runtime:** Python 3.13.12 (Conda / venv)  
**Pytest Version:** 9.1.1  
**Repository:** https://github.com/HarshDubey23/SELLABLE  
**Evaluation Track:** Razorpay AI Buildathon - Track 01 (AI Growth & Agentic Commerce)

---

## 1. Environment & Runtime Baseline

| Component | Specification / Version | Status |
|---|---|---|
| **Python** | Python 3.13.12 | OK |
| **FastAPI** | 0.115.0+ | OK |
| **Uvicorn** | 0.30.0+ | OK |
| **Pydantic** | 2.9.0+ | OK |
| **HTTPX / Requests** | 0.27.0+ | OK |
| **Google GenAI SDK** | google-genai (Gemini 2.5/3.5 Flash) | Configured & Live |
| **Razorpay SDK** | Test Mode API Credentials configured (rzp_test_TSttLNvLt9yUPI) | Active (Test Mode) |
| **Database** | SQLite Durable Store (data/sellable.db) | Verified Genesis & Chain |

---

## 2. Test Suite Status

Command: `python -m pytest`

```text
============================= test session starts =============================
platform win32 -- Python 3.13.12, pytest-9.1.1, pluggy-1.6.0
collected 65 items / 1 skipped

tests/gateway/test_attack_lab.py .........                               [ 13%]
tests/gateway/test_chain_tamper.py ....                                  [ 20%]
tests/gateway/test_inv1_binding.py ....                                  [ 26%]
tests/gateway/test_matrix.py .............                               [ 46%]
tests/gateway/test_r10_expiry.py ...                                     [ 50%]
tests/gateway/test_r9_signature.py ....                                  [ 56%]
tests/test_api_surface.py ............                                   [ 75%]
tests/test_mandates.py .........                                         [ 89%]
tests/test_no_approve_no_money.py ..                                     [ 92%]
tests/test_webhook.py .....                                              [100%]

======================== 65 passed, 1 skipped in 5.68s ========================
```

* **Total Passing Tests:** 65
* **Total Failures:** 0
* **Skipped:** 1 (Playwright live browser stub)

---

## 3. Pre-Existing Issues Identified & Repaired

1. **Proxy Timeout on Long LLM Runs:**  
   * *Issue:* UI proxy defaulted to 30-second timeout; LLM reasoning + Razorpay API roundtrip exceeded 30s causing HTTP 502.  
   * *Resolution:* Proxy client timeout set to `None` and IPv6 loopback normalized to `127.0.0.1`.
2. **Upsell Trace Payload Missing:**  
   * *Issue:* `verdict_received` event during upsell acceptance omitted the data dictionary, causing the UI Gateway Verdict card to display `seq #? Failed rule: ?`.  
   * *Resolution:* Trace event now passes `{"decision": "APPROVE", "seq": v.seq, "proposal_hash": v.hash}`.
3. **Razorpay Test Account Rate Limit Crash (HTTP 429):**  
   * *Issue:* Razorpay test mode payment link creation hit the account quota (30 links), causing an unhandled 500 error in `/agent/run-mission`.  
   * *Resolution:* Recovery rail wrapped in a fail-safe exception handler; errors are logged to the audit chain while keeping the main order checkout flow active.
4. **Interactive Razorpay Checkout:**  
   * *Issue:* UI rendered raw JSON order status instead of the live Razorpay payment overlay.  
   * *Resolution:* Embedded `checkout.js` with auto-opening payment modal on order generation.
