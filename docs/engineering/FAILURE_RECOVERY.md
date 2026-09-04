> **Historical engineering log.** These are real failures diagnosed during
> the build, kept because how a system broke is evidence about how it
> works. Current limitations live in the README; the current failure
> *design* lives in [docs/architecture/execution-lifecycle.md](../architecture/execution-lifecycle.md).

# SELLABLE — Failure Analysis & Recovery Log

During the final engineering pass, the following real failure modes were diagnosed, contained, and permanently resolved:

### 1. Razorpay Test-Mode Payment Link Rate Limit (HTTP 429)
* **What broke:** The automatic fallback rail attempted to create a test payment link on an account that had reached its 30-link quota.
* **Root Cause:** Razorpay sandbox enforces a ceiling of 30 payment links per test key.
* **Resolution:** Wrapped `run_recovery` (now `apps/api/recovery/engine.py`) in a fail-safe exception handler that logs the failure to the audit ledger while allowing the interactive checkout modal to proceed.

### 2. Reverse-Proxy Timeout on Long LLM Invocations
* **What broke:** UI proxy returned HTTP 502 Bad Gateway during multi-step reasoning missions.
* **Root Cause:** Default `httpx` async client timeout was 30 seconds, while Gemini API calls + catalog retrieval took up to 45 seconds.
* **Resolution:** Configured `httpx.AsyncClient(timeout=None)` on internal proxy routes and normalized host binding to IPv4 `127.0.0.1`.

### 3. Missing Upsell Trace Payload
* **What broke:** Gateway Verdict UI card displayed `seq #? Failed rule: ?` after an upsell offer was accepted.
* **Root Cause:** `trace.emit` in `buyer.py` omitted the `data` dictionary on upsell approval.
* **Resolution:** Passed full verdict dictionary into the event payload.
