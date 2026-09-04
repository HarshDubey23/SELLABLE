# SELLABLE Chaos Monkey — Technical Recon & Architecture Notes

## Phase 0 Recon Summary

### 1. Stack & Architecture
- **Language & Framework**: Python 3.13, FastAPI, Uvicorn ASGI server.
- **Database & Persistence**: SQLite (`data/sellable.db`) with WAL mode.
- **Policy Gateway**: `apps/api/gateway/engine.py` (pure deterministic fail-closed rule evaluation engine R1-R12) + `apps/api/approval.py` (SHA-256 exact approval binding).
- **Money Boundary & Razorpay**: `apps/api/gateway_service.py` + `apps/api/razorpay_client.py` (authenticated test mode calls to `api.razorpay.com`) + `apps/api/webhook/receiver.py` (HMAC-SHA256 signature verification & 8-state payment machine).
- **Audit Ledger**: `apps/api/audit/chain.py` (tamper-evident SHA-256 append-only block ledger in SQLite `audit_chain` table).
- **Catalog & Inventory**: `apps/api/products.py` (40 SKUs with real stock counts, prices in paise, category tags, and floor/ceiling caps).
- **Idempotency & Traceability**: `X-Idempotency-Key` header on `/tools/create_order` + `mission_id` / `trace_id` emitted across all `TraceEvent` objects (`apps/api/agent/trace.py`).
- **Frontend Stack**: Fast, dependency-free vanilla HTML/CSS/JS served directly via FastAPI `HTMLResponse` (`apps/api/ui.py`, `apps/api/demo_ui.py`).

### 2. Injection Points & Chaos Bus Architecture
- **Chaos Middleware Choke Point**: `apps/api/chaos/bus.py` (FastAPI/ASGI Middleware intercepting all inbound & outbound agent/gateway/webhook requests).
- **Fault Management**: `apps/api/chaos/engine.py` (arms, disarms, auto-expires 9 faults, evaluates I1-I8 invariants).
- **Scenario Runner**: `apps/api/chaos/scenarios.py` (deterministic scenario scripts 1-7).
- **Event Stream**: `apps/api/chaos/events.py` (SSE live feed at `/api/events/stream`).
- **API Router**: `apps/api/chaos/api.py` (mounted at `/api/chaos/`).
- **UI & Architecture Interactive Page**: `apps/api/chaos/ui.py` (mounted at `/chaos` and `/architecture`).

### 3. Implementation Blueprint
- Isolated `apps/api/chaos/` module (zero refactoring of stable core logic).
- Safe by default: Armed only if `CHAOS_ENABLED=true` and Razorpay key starts with `rzp_test_`.
- Complete 8-invariant evaluation engine (`I1` to `I8`) for machine-checkable verdicts (`SURVIVED` vs `BREACH`).
- Interactive `/architecture` page rendering the real system flow with live SVG step lighting, drill triggers, and event streams.
