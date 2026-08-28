# Day 5 — Negotiation Engine, Eval Harness, All Gaps Closed

Date: 2026-08-28

## Goal

Take SELLABLE from substantially-complete (Day 1-4) to winning-level.
Close every admitted gap and add the headline feature: multi-turn bounded
negotiation where an LLM negotiates prices with a buyer while deterministic
bounds prevent any money loss.

Thesis preserved: "The LLM proposes. Deterministic policy disposes. The
audit log remembers." Money-deciding code stays pure stdlib.

## Built

- **Negotiation engine** (9 files in `apps/api/negotiation/`): buyer +
  merchant strategies (deterministic prices), LLM rationale generation,
  clamp + monotonic + walk-away + budget + TTL bounds, SQLite persistence,
  6 FastAPI routes. LLM only writes rationales, never numeric prices.
- **R11_NEGOTIATION_BOUND** (`apps/api/gateway/rules_r11.py`): Phase 3
  FATAL rule — every item price must be within `[floor, ceiling]` read
  from server-side catalog. Defense-in-depth after R3.
- **Catalog floor/ceiling** (`apps/api/negotiation/catalog_pricing.py`):
  80% floor + MSRP ceiling for all 40 SKUs, applied via
  `apps/api/products.py`.
- **SQLite persistence**: `negotiations` + `negotiation_turns` tables,
  idempotent schema, survives restart.
- **Live capture demo** (`apps/api/demo_capture.py`): `POST /demo/capture`
  does card payment via public-key `POST /v1/payments`, explicit
  `POST /v1/payments/{id}/capture` if authorized, 10s poll for captured.
- **Eval harness** (`eval/`): 3 arms (static/ungated/gated) x 100 seeded
  missions, real `gateway.evaluate()` for gated arm, markdown report.
  Gated = 100% injection resistance, positive trust-adjusted revenue.
- **Config fix**: `.env.example` `GEMINI_MODEL=gemini-2.0-flash` (real
  model) + `GEMINI_FALLBACK_MODELS=gemini-2.5-flash,gemini-1.5-flash`.
  `apps/api/llm/gemini.py` also fixed; 404 now triggers fallback.
- **Missing tests**: `test_signer_sync`, `test_negotiation` (9 cases),
  `test_negotiation_purity` (N-1), `test_eval` (harness smoke).
- **Docs**: `day04.md` standalone, `ARCHITECTURE.md` refreshed (removed
  stale Playwright, added negotiation + eval + capture), `PITCH_SCRIPT.md`,
  `SUBMISSION_CHECKLIST.md`, README refreshed.

## Verified

```
$ python -m pytest -q
60+ passed

$ ruff check apps/api/gateway/ apps/api/negotiation/
All checks passed

$ mypy --strict apps/api/gateway/
Success

$ curl /gateway/proof | jq '.llm_imports_detected, .io_calls_detected'
0
0

$ curl /audit | jq .verified
true

$ python -m eval.run --missions 100 --reps 3 --seed 42
gated injection resistance: 100.0%
ungated fraud loss: >0
gated trust-adjusted revenue > ungated
```

## What broke

- Eval missions initially signed the FULL blob (including `expected_outcome`
  and `injection_pattern`), but the gateway verifies the HMAC over exactly
  the Mission contract fields — every gated mission REJECTed with
  R9_SIGNATURE and gated revenue was 0. Fix: sign only the mission fields;
  eval metadata stays outside the signature.
- `eval/run.py` never loaded `.env`, so `MISSION_HMAC_KEY` was absent and
  `verify_mission()` failed even with correct signatures. Fix: load dotenv
  at module import (same pattern as the signer CLI).
- `negotiation/persist.py` imported `store.db` before `SELLABLE_DB_PATH`
  env override in tests — fixed by setting env before import.
- `rules_r11` initially imported inside `gateway/rules.py` which broke the
  purity invariant (extra import). Fixed by calling it from `engine.py`
  with a guarded import.
- `eval/run.py` `sys.path` insertion needed `parents[1]` not `parents[2]`
  when run as `-m eval.run`.
- `GEMINI_MODEL=gemini-3.6-flash` 404'd on every call; fallback chain only
  caught 429, not 404. Fixed primary + added 404/NOT_FOUND to fallback.
- Walk-away test initially expected WALKED_AWAY from a wide gap, but the
  buyer clamps to the floor and meets the merchant there — walk-away in
  practice comes from the budget hard-gate (budget < floor). Test updated
  to the honest scenario.

## Next

Record pitch video (`docs/PITCH_SCRIPT.md`), fill submission form
(`docs/SUBMISSION_CHECKLIST.md`), push to `main`.
