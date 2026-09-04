# Day 7 - Phase 3 hygiene: F-06 dead, F-07 pinned, F-08 gated

Date: 2026-08-31

## Goal

Kill the three silent-rot findings a reviewer greps for in under a minute:
the fail-open R11 import (F-06), the unpinned runtime manifest (F-07), and
the unauthenticated mutating API surface (F-08) — each with a machine-checked
acceptance test, including the red-CI proof (delete rules_r11.py, suite goes RED).

## Built

- **apps/api/gateway/engine.py** — F-06 dead: the try/except ImportError around
  the R11 import deleted; `from .rules_r11 import rule_r11_negotiation_bound`
  hoisted to module top (column 0, alongside the other rule imports); the call
  kept verbatim in its exact evaluation position (after R3, before R7), now
  unguarded. Zero behavior change when the module exists; a missing module now
  crashes at import instead of silently skipping R11.
- **apps/api/main.py, apps/api/products.py** — the other two fail-open imports
  in the app (demo_capture router, negotiation router, catalog floor/ceiling
  pricing) hard-imported the same way. `except ImportError` count under
  apps/api/ is now ZERO (repo-wide grep).
- **tests/gateway/test_registry_reachability.py** — the permanent F-06 guard:
  (a) every RULE_REGISTRY rule has a call site in engine.py (entries are dicts
  keyed "rule_id"; engine calls `rule_<lowercased id>(...)`), (b) the rules_r11
  import must be at module top, (c) "except ImportError" may never reappear in
  engine.py, (d) EXPECTED_RULE_COUNT = 11 pinned (Phase 4 bumps it for R12/R13).
- **apps/api/requirements.txt** — runtime-only, pinned exact from `pip freeze`:
  fastapi 0.141.1, uvicorn 0.52.4, python-dotenv 1.2.3, pydantic 2.13.5,
  requests 2.34.2, httpx 0.28.1, google-genai 2.20.0. razorpay SDK deliberately
  absent (nothing imports it; razorpay_client.py speaks raw HTTPS via requests
  — import grep is the authority). Dev tools (pytest/ruff/mypy/playwright) gone.
- **apps/api/requirements-dev.txt** — dev/test tooling pinned exact: pytest
  9.1.1, httpx 0.28.1, ruff 0.16.5, mypy 2.3.1, playwright 1.62.0. No pytest
  plugin beyond the core is imported by the suite (grep checked).
- **.github/workflows/ci.yml, Makefile** — install both files:
  `pip install -r apps/api/requirements.txt -r apps/api/requirements-dev.txt`.
- **apps/api/deps.py** — `require_api_key` FastAPI dependency: missing/wrong
  X-API-Key → 401 (hmac.compare_digest); APP_API_KEY unset → 503 fail-closed
  naming the env var. No default key anywhere in code.
- **Route gate applied (FACT 3 inventory — 12 POST routes, the authority):**

  | Route | File | Key required | Why |
  |---|---|---|---|
  | POST /tools/quote | tools.py | YES | creates signed price lock |
  | POST /tools/submit_proposal | tools.py | YES | gateway verdict / money path entry |
  | POST /tools/create_order | tools.py | YES | THE money boundary |
  | POST /tools/scan_copy | tools.py | YES | mutates nothing but is a write-style tool surface; gated uniformly |
  | POST /negotiation/start | negotiation/api.py | YES | opens a negotiation |
  | POST /negotiation/{nid}/turn | negotiation/api.py | YES | advances negotiation |
  | POST /negotiation/{nid}/run | negotiation/api.py | YES | runs to completion |
  | POST /negotiation/{nid}/accept_at | negotiation/api.py | YES | merchant accepts offer |
  | POST /agent/run-mission | agent/runner.py | YES | runs buyer agent |
  | POST /agent/run-scenario/{id} | agent/runner.py | YES | runs scenario |
  | POST /demo/capture | demo_capture.py | YES | creates real test-mode order |
  | POST /webhook | webhook/receiver.py | EXEMPT | Razorpay HMAC over raw body + event-id dedup protect it; an API key would break event delivery |

  All 24 GET routes (health, proof, catalog, search, explain_reject, policy,
  check_payment, upsell/crosssell offers, ledger, timeline, missions,
  metrics/revenue, checkout, demo/*, manifest, scenarios, negotiation state)
  left open — read-only.
- **tests/conftest.py** — sets APP_API_KEY=test-key-ci via setdefault BEFORE the
  app imports anywhere in the suite.
- **tests/test_api_surface.py, tests/gateway/test_inv1_binding.py,
  tests/invariants/test_agent_custody.py** — their TestClient constructions now
  attach `X-API-Key` from the env (minimal edit: 4 constructions total).
- **tests/agent/test_deterministic_pick.py, tests/test_money_path_offline.py**
  — the buyer agent's httpx.AsyncClient gets the X-API-Key header injected in
  tests (module-level patch of __init__ in each file) so protected routes are
  exercised successfully; production buyer code untouched.
- **tests/test_authz.py** — 4 tests: no key → 401, wrong key → 401, env unset →
  503 fail-closed (detail names APP_API_KEY), good key → passes the gate (422
  body validation, NOT 401/503).
- **scripts/smoke.sh** — sources .env, POSTs with
  `-H "X-API-Key: ${APP_API_KEY:?APP_API_KEY not set}"` (fails loudly).
- **scripts/redteam.py** — DEFAULT_HEADERS on every POST to protected routes;
  refuses to run (exit 1, names APP_API_KEY) when the key is absent; new cases
  21 (no key → 401) and 22 (wrong key → 401). Webhook case untouched (exempt).
- **scripts/e2e_day2.py** — HEADERS={"X-API-Key": ...} on all 7 POSTs; exits
  loudly when APP_API_KEY is unset.
- **Makefile demo-capture** — now sends X-API-Key (fails loudly if unset).
- **docs/SECURITY_CLAIMS.md** — "Trust Boundary" section appended (F-08 part b).
- **.env.example** — APP_API_KEY= added (name only; generated at deploy time).

## Verified

```
$ RED-CI proof (delete rules_r11.py, run suite, restore):
RED_OK (exit=2)                    # suite correctly RED without R11
$ .venv\Scripts\python.exe -m pytest -q   (restored)
91 passed, 1 warning in 26.95s

$ except-ImportError sweep:
engine.py count: 0
apps/api/ repo-wide count: 0      (the word "ImportError" appears nowhere)

$ ruff check apps/api/gateway/ && mypy --strict apps/api/gateway/
All checks passed!
Success: no issues found in 8 source files

$ cold venv (fresh venv, install both manifests, run suite):
install_exit=0
91 passed, 1 warning in 4.02s      (identical count to .venv)

$ live 401s (uvicorn started with APP_API_KEY in env):
no_key=401  wrong_key=401  good_key_gate=422
body_no_key: {"detail":"Missing or invalid X-API-Key header"}

$ pytest tests/test_authz.py tests/gateway/test_registry_reachability.py -q
8 passed, 1 warning in 1.57s

$ pins vs pip freeze — every line of both manifests matches freeze exactly
  (3 drift corrections during the phase: google-genai 2.19.0→2.20.0,
   pydantic 2.13.4→2.13.5, ruff 0.16.4→0.16.5)

$ secrets hygiene:
test-key-ci occurrences under apps/api/: 0
git check-ignore .env → ENV_IGNORED

$ suite delta: Phase 2 HEAD collected 83 tests; +4 reachability +4 authz
  = 91. (day06's last inline count said 82 — one Phase 2 test was committed
  after that log line; the committed tree collected 83.)
```

## What broke

- **The prior session's edits corrupted file encodings** (UTF-8 BOM + cp1252
  mojibake: em-dash `—` became the three-char sequence `â€"`) in tools.py,
  demo_capture.py, negotiation/api.py, agent/runner.py, test_inv1_binding.py,
  test_agent_custody.py. The mojibake bytes were invalid as cp1252, so the
  EXISTING tests/gateway/test_registry_coverage.py (which read_text()s the whole
  suite) crashed with UnicodeDecodeError and the full suite was RED at 87/1.
  Repaired byte-level: BOM stripped, `â€"` → `—`, written back as UTF-8 without
  BOM; git diffs now show only the intended changes.
- **Three pin values in the draft manifests did not match the working venv's
  freeze** (google-genai, pydantic, ruff) — corrected verbatim from freeze
  before any commit.
- **Task 7 fallout was exactly the predicted shape**: 4 TestClient constructions
  + the buyer agent's httpx client needed the header; every failure was a
  missing-header failure; no non-header failures occurred.
- **redteam.py case 20's comment lost its indentation** in the prior session's
  edit — restored to 4 spaces.
- eval/seeded/missions.json appeared untracked (artifact of a seed run, not
  part of this phase's task list) — left untracked, not committed.

## Learned

Fail-open hides rot until it costs money (a vanished module silently skipping
R11 would have unbounded negotiations); fail-closed makes the same defect a
loud crash, a red suite, or a 503 that names the missing variable — always
prefer the failure you can see.
