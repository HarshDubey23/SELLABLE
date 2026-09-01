# Day 9 — Phases 5-9 + hotfix: demo_ui tamper-demo CI red

Date: 2026-09-01

## Goal

Ship Phases 5–9 for the Razorpay AI Buildathon Track 01 submission kit:
demo UI (`/demo`), zero-dependency external buyer, honest eval V2 (8 required
metrics), judge-first README, and deployment artefacts (`render.yaml`,
`fly.toml`, `Dockerfile`, `scripts/smoke_test.sh`, `docs/submission/*`).
Then keep CI green.

## Built (Phases 5–9 summary)

- **Phase 5 — Demo UI (`apps/api/demo_ui.py`, `tests/test_demo_ui.py`):**
  `/demo` hub, `/demo/checkout` cinematic replay with server-side proxy
  (`POST /demo/checkout/api/{path}`), `/demo/failures` chaos page,
  `/demo/tamper-demo` on a temp DB copy, `/demo/attack_payloads`.
  19 tests. `_sign_mission` bridges `apps.api.gateway.mission_verify`.

- **Phase 6 — External buyer (`external_buyer/buyer.py`, `external_buyer/run.py`, `tests/test_external_agent_isolation.py`):**
  stdlib-only client (no SELLABLE imports), isolation test, `docs/log/external_agent.md`.

- **Phase 7 — Eval V2 (`eval/metrics.py`, `eval/run.py`, `eval/report.py`, `tests/test_eval.py`, `scripts/verify_numbers.py`):**
  5 arms (static/ungated/gated/behavioral_ungated_llm/behavioral_gated_llm),
  per-mission `records` (`llm_fooled`/`money_loss`), 8 required metrics
  (`acceptance_rate`, `aov_uplift`, `false_block_cost`, `llm_fooled_rate`,
  `money_loss_rate`, `negotiation_margin`, `p95_latency`, `protocol_pass_rate`),
  `methodology` (`llm_mode: "mock"`), `render_readme_numbers.py`,
  `--check-report`/`--check-readme`. `encoding="utf-8"` on all file I/O
  (Windows cp1252 fix). `eval/report.json` + `eval/report.md` generated.

- **Phase 8 — README (`README.md`, `scripts/render_readme_numbers.py`):**
  Judge-first routing table, numbers strip, protocol map (R1–R12), updated
  counts (40 SKUs, 12 rules, 143 tests), V2 metrics table, `verify --check-readme`
  with formatted candidates.

- **Phase 9 — Deploy + submission kit:**
  `render.yaml`, `fly.toml`, `Dockerfile`, `scripts/smoke_test.sh` (8-point),
  `docs/submission/DEPLOY_RUNBOOK.md`, `FORM_ANSWERS.md`,
  `PRE_SUBMISSION_CHECKLIST.md`, `RUN_REPORT.md`,
  `docs/submission/manifest.json`, `PITCH_VIDEO_SCRIPT.md`
  (+ `docs/PITCH_SCRIPT.md` updated). CI already had `sellable` remote;
  push `e5d68c0..dfaec90 main -> main` succeeded.

## What broke — CI red on `test_tamper_demo_detects_tampering`

### CI output (ubuntu-latest, Python 3.11, `python -m pytest -q`)

```
FAILED tests/test_demo_ui.py::test_tamper_demo_detects_tampering - KeyError: 'before_verified'
  d = r.json()
  > assert d["before_verified"] is True
    E KeyError: 'before_verified'
1 failed, 142 passed, 1 skipped
```

### Root cause

`apps/api/demo_ui.py:37` used `os.environ.get("SELLABLE_DB", "data/sellable.db")`
while the real store is `apps/api/store/db.py:26` → `SELLABLE_DB_PATH`
(`tests/conftest.py:25` sets `SELLABLE_DB_PATH` to a throwaway
`/tmp/sellable-test.db`). In CI `data/sellable.db` is gitignored and does not
exist, so `GET /demo/tamper-demo` hit the early:

```python
if not os.path.exists(_DB_PATH):
    return JSONResponse({"ok": False, "error": f"db not found: {_DB_PATH}"})
```

which lacked `before_verified`/`after_verified`/`conclusion`. The suite's
isolated DB had only `GENESIS` (no `seq=1`), but the code never reached the
`no seq=1` graceful branch because it bailed on the wrong path first.

Locally `data/sellable.db` existed (many audit entries), so the tamper copy
had `seq=1` and the test passed — classic “works on my machine”.

### Fix

`apps/api/demo_ui.py`:

- `_DB_PATH` now checks `SELLABLE_DB_PATH` first, then `SELLABLE_DB`
  (back-compat).
- `tamper_demo()` resolves `db_path = store.db_path()` dynamically
  (authoritative, reflects conftest's throwaway DB even if module was
  imported before the env was set) with fallback to `_DB_PATH`.
- `db not found` branch now returns the full contract:
  `before_verified`, `after_verified: None`, `conclusion`, `note`,
  `captured_at_utc` — same keys as the `no seq=1` branch.
- Copy now uses `db_path` (not stale `_DB_PATH`) for `shutil.copyfile`
  and WAL/SHM side-files.

Verified two paths:

- Fresh CI DB (only `GENESIS`): `before_verified True, after_verified None,
  conclusion "chain has no data entries to tamper"` → `assert after_verified in (False, None)` passes.
- Populated DB (local): `before True, after False, conclusion "money path halted (CHAIN_TAMPER)"` → passes.

### Verified

```
$ python -m pytest tests/test_demo_ui.py::test_tamper_demo_detects_tampering -v
1 passed

$ python -m pytest -q
143 passed, 1 skipped

$ ruff check apps/api/gateway/ apps/api/negotiation/ && mypy --strict apps/api/gateway/
All checks passed! Success: 9 files

$ python scripts/verify_catalog.py && python scripts/verify_numbers.py --check-report --check-readme
Catalog verification PASSED — 40 SKUs
OK report.json has all 8 metrics; OK README numbers match report.json
```

Simulated fresh CI DB in-process (`SELLABLE_DB_PATH` → `tempfile.mktemp`,
only `GENESIS`) also returned the expected graceful JSON.

## Learned

- A module-level `os.environ.get` is a snapshot, not a subscription.
  If the env can be set by `conftest` after import, resolve it at call time
  via the store's `db_path()` getter — single source of truth.
- Every early-return in an endpoint must honour the test contract.
  “db not found” is a valid test state in CI; it must still return the keys
  the test asserts.
- Keep `SELLABLE_DB` vs `SELLABLE_DB_PATH` consistent. One typo turns a
  passing local suite into a red CI.
