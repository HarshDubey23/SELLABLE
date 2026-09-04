# Day 6 — Reconciliation, baseline certification, v2 scaffold

Date: 2026-08-29

## Goal

Compressed sprint to the 5 Sep Razorpay Buildathon deadline. Today: reconcile the
improvement blueprint against the live repo, certify the 65-test baseline, scaffold
every directory the v2 architecture needs, and verify CI tells the truth — so Phases
1–9 never operate on an unverified base.

## Built

- **RECONCILIATION.md** — 16-row doc-referenced file audit + v2 target map, every cell re-runnable.
- **apps/api/protocols/__init__.py** — Protocol Adapter Layer v0 scaffold (docstring only; Phase 4 fills it).
- **external_buyer/, docs/submission/, docs/assets/** — scaffolds with .gitkeep (Phases 6/8/9 fill them).

## Verified

```
$ git ls-files | wc -l        (git ls-files | Measure-Object -Line)
223

$ pytest -q
65 passed, 1 warning in 3.94s

$ ruff check apps/api/gateway/
All checks passed!

$ mypy --strict apps/api/gateway/
Success: no issues found in 8 source files

$ make test                   (make not on Windows PATH — ran .venv\Scripts\python.exe -m pytest -q)
65 passed, 1 warning in 4.41s

$ make audit-verify           (ran python -m apps.api.audit.verify)
FAILED — No module named apps.api.audit.verify
(Makefile defect: apps/api/audit/ contains only chain.py, timeline.py,
 __init__.py — verify.py does not exist. Recorded, not fixed — scope.)

$ make redteam                (ran python scripts/redteam.py)
[redteam] base=http://localhost:8000
PASS 1 invalid signature ... PASS 20 wrong cart hash  403
20/20 PASS — "[redteam] done", exit 0
(live server was already running on localhost:8000)
```

CI (.github/workflows/ci.yml) read and confirmed:
- installs from apps/api/requirements.txt → **yes** (line 10)
- runs pytest → **yes** (line 12, `python -m pytest -q`)
- ruff on gateway → **yes** (line 13, `ruff check apps/api/gateway/`)
- mypy strict on gateway → **yes** (line 14, `mypy --strict apps/api/gateway/`)

F-06 confirmed still present (intentionally — Phase 3 owns the fix):
`grep -n "except ImportError" apps/api/gateway/engine.py` → exactly 1 hit, line 93

## What broke

- Blueprint numeric drift found during reconciliation (statuses unchanged, evidence
  corrected in RECONCILIATION.md):
  - `apps/api/agent/buyer.py` is **515 lines**, not 600 as claimed.
  - README **already links** `scripts/verify_numbers.py` (1 hit, line 399) — the
    blueprint claimed grep count 0 / "not linked" (F-09 is weaker than stated).
  - `grep -c "INJECTION\|injection" apps/api/products.py` → 4, not ≥ 8; the real
    proof of I1–I8 is `INJECTION_INDEX` (exactly 8 entries) + embedded I1–I7 payloads.
- `make audit-verify` is **broken**: it runs `python -m apps.api.audit.verify` but
  `apps/api/audit/verify.py` does not exist (No module named apps.api.audit.verify).
  Recorded honestly; not fixed (Phase 0 scope = audit + scaffold only).
- `make` itself is not on this Windows machine's PATH; all three Makefile targets
  were executed via their underlying commands with `.venv\Scripts\python.exe`.
- Environment note: venv layout is `.venv\Scripts\` (Windows), not `.venv/bin/`.

## Learned

The blueprint's structural map is accurate (all 16 paths exist, 65 tests green,
11 rules, purity intact) but its specific numbers have drifted from the tree, and
the audit surfaced two live defects it missed entirely: a Makefile target pointing
at a nonexistent module and a custody-invariant test that the mandates docstring
promises but the repo never delivered.

---

## Phase 1 — Gateway verification

Date: 2026-08-30 (session 2 of day 6)

**Goal:** prove gateway completeness/purity/binding, not claim it — registry→test
coverage closed with a permanent guard, purity proof made live + test-enforced,
INV-1 approve-binding tested against the real executor path, F-06 documented
(read-only), gateway contract frozen for v2.

### Built — STEP 0 DISCOVERY, the four facts (verbatim from the code)

- **FACT 1 — Constructors** (`apps/api/gateway/types.py`, frozen dataclasses):
  `Mission(mission_id: str, intent: str, budget_paise: int, allowed_categories: tuple[str, ...], forbidden_categories: tuple[str, ...], upsell_cap: float, expires_at: int, signature: str = "")`;
  `ProposalItem(sku: str, qty: int, price_paise: int)`;
  `Proposal(mission_id: str, items: tuple[ProposalItem, ...], justification: str = "")`;
  `Verdict(decision: Decision, rule_id: str | None, reason: str, proposal_hash: str | None, seq: int | None)`;
  `Decision` = StrEnum {APPROVE, REJECT}.
- **FACT 2 — Registry**: `RULE_REGISTRY: list[dict[str, Any]]`; entries are dicts
  keyed `"rule_id"` (plus `"phase"`, `"severity"`, `"check_description"`). Exact ids:
  R9_SIGNATURE, R10_EXPIRY, R8_ABORT, R1_BUDGET, R2_FORBIDDEN, R5_SCOPE,
  R4_UPSELL_CAP, R3_PRICE_DRIFT, R11_NEGOTIATION_BOUND, R7_ALLOWLIST, R6_RATE_LIMIT.
  Violations emit the SAME full strings (rules.py passes e.g. "R1_BUDGET" as
  Violation.rule_id; engine copies v.rule_id into the verdict). `RULE_BY_ID` is
  `dict[str, entry]`. The coverage guard therefore reads `entry["rule_id"]`.
- **FACT 3 — GET /gateway/proof** (200): exactly these JSON keys —
  `files`, `total_lines`, `llm_imports_detected`, `io_calls_detected`,
  `forbidden_patterns_seen`, `source_sha256`, `invariant_test`. There are NO
  `purity` / `forbidden_imports` / `rule_count` keys — the blueprint's sketch
  was adapted to the real shape (registry agreement asserted via `GET /policy`,
  which serves `{"rules_count": len(RULE_REGISTRY), "rules": RULE_REGISTRY}`).
- **FACT 4 — INV-1 binding (executor)**: `POST /tools/create_order`
  (apps/api/tools.py ~326–451) is the single money boundary. Its G1 gate
  (~line 357) refuses unless `approved_bindings.get(approve_seq) == proposal_hash`
  → HTTP 403 `{"ok": false, "error": {"error_code": "ORDER_HASH_MISMATCH", ...}}`.
  `approved_bindings` is written ONLY by `submit_proposal` on APPROVE
  (~line 294), seq → `verdict.proposal_hash`, where the hash is
  `sha256_hex(canonical_json(proposal))` (engine.py). **Enforcement already
  exists — tools.py was NOT modified this phase** (Task 3c honest check: no
  change needed, tests written against the real behavior).

### Built — rule → test coverage mapping (11 rows, from grep of tests/)

| Rule | Test file(s) + test name(s) |
|------|-----------------------------|
| R1_BUDGET | tests/gateway/test_matrix.py::test_r1_over_effective_budget, ::test_r1_injection_inflates_total (+R1 cited in test_r4_exceeds_cap, test_r4_cap_1_means_budget_only, test_first_violation_wins); tests/gateway/test_r1_budget.py (direct rule unit) |
| R2_FORBIDDEN | tests/gateway/test_matrix.py::test_r2_forbidden_rejected |
| R3_PRICE_DRIFT | tests/gateway/test_matrix.py::test_r3_drift_detected |
| R4_UPSELL_CAP | tests/gateway/test_matrix.py::test_r4_within_cap, ::test_r4_exceeds_cap, ::test_r4_cap_1_means_budget_only (exercised; cannot fire independently by design — rules.py ~99–104: same threshold as R1 after the effective-budget fix, kept as redundant safety) |
| R5_SCOPE | tests/gateway/test_matrix.py::test_r5_out_of_scope |
| R6_RATE_LIMIT | tests/gateway/test_matrix.py::test_r6_over_limit |
| R7_ALLOWLIST | tests/gateway/test_matrix.py::test_r7_merchant_not_allowlisted |
| R8_ABORT | tests/gateway/test_matrix.py::test_r8_mission_aborted |
| R9_SIGNATURE | tests/gateway/test_matrix.py::test_r9_tampered_signature, ::test_r9_missing_signature; tests/gateway/test_r9_signature.py |
| R10_EXPIRY | tests/gateway/test_matrix.py::test_r10_expired, ::test_r10_boundary_exact; tests/gateway/test_r10_expiry.py (×2) |
| R11_NEGOTIATION_BOUND | tests/gateway/test_matrix.py::test_r11_negotiation_bound_rejected (added Phase 1: forces ceiling below catalog price so R11 fires while R3 still passes) |

### Built — tests added

- `tests/gateway/test_registry_coverage.py` — permanent guard: every
  RULE_REGISTRY rule id must appear (bare id, full name, any case) somewhere in
  `tests/**/test_*.py`, or the test fails listing the uncovered ids. A future
  rule can never be registered without a test.
- `tests/gateway/test_matrix.py::test_r11_negotiation_bound_rejected` — the one
  coverage gap (R11) closed: catalog ceiling forced below catalog price, asserts
  `REJECT` + `rule_id == "R11_NEGOTIATION_BOUND"`.
- `tests/test_api_surface.py::test_gateway_proof_live` — /gateway/proof is 200,
  `llm_imports_detected == 0`, `io_calls_detected == 0`,
  `forbidden_patterns_seen == []`, `invariant_test` points at the purity test,
  and `GET /policy.rules_count == rules_count()`.
- `tests/gateway/test_inv1_binding.py` — 2 tests against the REAL HTTP surface
  (TestClient): `test_tampered_proposal_refused` (APPROVE recorded for 1×BAT-001;
  mutated proposal hash → 403, error_code ORDER_HASH_MISMATCH, retryable false,
  message cites the seq) and `test_valid_binding_proceeds` (control: untampered
  seq+hash + valid signed INV-3 mandates → 200, Razorpay boundary reached with
  `create_order` monkeypatched offline, called once with the quote total and
  notes.proposal_hash == approved hash). An autouse fixture reloads the audit
  chain from SQLite (memory = disk truth) because T30 corrupts the in-memory
  chain for the rest of the session.

## Verified

```json
GET /gateway/proof → 200
{
  "files": 8,
  "total_lines": 517,
  "llm_imports_detected": 0,
  "io_calls_detected": 0,
  "forbidden_patterns_seen": [],
  "source_sha256": "c13caa99ddaa3dc724e47c64cfb8e5192940f7906fa66180bbd207e03515bd73",
  "invariant_test": "tests/invariants/test_gateway_purity.py"
}
```

```
$ .venv\Scripts\python.exe -c "…PURITY_OK script (rules_count()==11, banned-source scan)…"
PURITY_OK

$ .venv\Scripts\python.exe -m pytest -q
70 passed, 1 warning in 2.48s

$ .venv\Scripts\python.exe -m pytest tests/test_api_surface.py::test_gateway_proof_live tests/gateway/test_inv1_binding.py tests/gateway/test_registry_coverage.py -q
4 passed, 1 warning in 1.12s

$ .venv\Scripts\python.exe -m ruff check apps/api/gateway/
All checks passed!

$ .venv\Scripts\python.exe -m mypy --strict apps/api/gateway/
Success: no issues found in 8 source files

$ grep -c "except ImportError" apps/api/gateway/engine.py  (Select-String count)
1   ← F-06 untouched, still exactly one hit (line 93)
```

## What broke

- **Blueprint key drift (Task 2b):** the sketch asserted `purity`,
  `forbidden_imports`, `rule_count` — none exist in the real proof payload.
  Adapted to the real keys (FACT 3) + `/policy` for registry agreement; no
  endpoint was changed to fit the test.
- **Full-suite interaction:** `tests/gateway/test_chain_tamper.py` (T30)
  reloads the audit chain, appends, then corrupts the IN-MEMORY entry and
  leaves it broken — verify() is False for the rest of the session. Pre-existing
  tests never noticed (they call `evaluate()` offline with `chain_ok=True`);
  the new INV-1 tests drive the real path where `tools.py` gates on
  `chain.verify()`. Fix inside my file only: autouse fixture reloads the chain
  module (repo's own pattern) — SQLite holds the true bytes, memory restored.
- **FastAPI error envelope:** the 403 refusal body nests under `detail`
  (`r.json()["detail"]["error"]["error_code"]`), not at top level. Test fixed,
  server behavior untouched.
- No BLOCKERS raised. INV-1 enforcement was found already in place at the
  executor boundary → `apps/api/tools.py` NOT modified (Task 3c recorded: no
  change made).

## Learned

Discovery beats blueprints: the registry, proof payload, and executor binding
all matched their docs in structure but not in exact key names, and one "green"
suite was hiding a test-order landmine (T30's corrupted in-memory chain) that
only a new test driving the real money path could expose.

### Phase 1 — R11 reachability audit note (F-06, fix owned by Phase 3)

R11_NEGOTIATION_BOUND is registered in RULE_REGISTRY, but its engine call site sits
inside a try/except ImportError:

```
    # Day 5: R11 negotiation bound (defense-in-depth after R3)
    try:
        from .rules_r11 import rule_r11_negotiation_bound
        v = rule_r11_negotiation_bound(proposal, catalog, mission)
        if v:
            return reject(v.rule_id, v.message)
    except ImportError:
        pass
```

(apps/api/gateway/engine.py lines 87–94, extracted verbatim via sed-equivalent)

Structural reachability is therefore NOT guaranteed: if rules_r11.py ever failed to
import, the engine would silently skip R11 instead of crashing. This is finding
F-06. It is intentionally left in place this phase; Phase 3 converts it to a hard
module-top import and proves CI goes red when rules_r11.py is deleted.

---

## Phase 2 — Money path verification

Date: 2026-08-30 (session 3 of day 6)

**Goal:** prove the full money path end to end — mission → agent → gateway
verdict → Razorpay test-mode order → webhook → audit chain — not claim it.

### Built

- `scripts/verify_catalog.py` — added the two missing checks: (b) injection
  resolvability now covers I8 via `INJECTION_INDEX` (exactly I1–I8; I8 is
  proposal-time by design, no description marker) and (c) every
  `price_paise` is an int (paise-only, G4). Existing 40-SKU / frozen-price /
  I1–I7 checks unchanged.
- `tests/invariants/test_agent_custody.py` — the test mandates.py's docstring
  promised but never shipped. Part (a): structural grep — no file under
  apps/api/agent may reference `USER_MANDATE_KEY` / `sign_intent` /
  `sign_cart`. Part (b): executor-level — create_order with no mandates →
  422 MANDATE_REQUIRED; tampered cart mandate (mutated after signing) →
  403 MANDATE_BAD_SIGNATURE; re-signed wrong cart_hash → 403
  MANDATE_CART_MISMATCH; and NO order row created in any case (asserted
  against the real SQLite orders table).
- `apps/api/agent/trace.py` + `buyer.py` — added ONE field,
  `used_fallback: bool` (default False), to trace-event construction and
  serialization; set True on the three `_deterministic_pick`-derived events
  (llm outage fallback, off-search-SKU fallback, bounded revision pick).
  Touches nothing else. This is the hook Phase 7's counterfactual measures.
- `tests/agent/test_deterministic_pick.py` — with the LLM stubbed to gemini.ask's
  own outage shape (its contract is never-raise; buyer switches to
  _deterministic_pick on the error dict) and the Razorpay boundary mocked at
  apps/api/razorpay_client.*, the run still produces a proposal (BAT-*)
  and the trace event carries `used_fallback: true`; order still created.
- `tests/test_money_path_offline.py` — REAL buyer agent + REAL wallet CLI
  subprocess (mandate custody) + REAL gateway/executor/audit chain/SQLite,
  driven over in-process HTTP; ONLY the outbound Razorpay boundary is mocked
  (create_order, deterministic UPI refusal, list/fetch). Asserts: APPROVE
  verdict row (verdicts table, mission-linked), order row persisted with
  approve_seq ↔ chain seq alignment, chain verified, parent linkage
  failure → recovery_reasoned via parent_action_id, /audit/timeline renders
  "Chain verified: True", and the run reports an HONEST non-captured status.
- `tests/test_injections_structural.py` — 8 parametrized cases: for I1–I8 the
  demo endpoint's REAL gateway verdict is REJECT and no order id appears.

### Executor reality found in discovery (Task 2)

The cart-mandate gate ALREADY EXISTS at the executor boundary (tools.py
~371–395: verify_intent + verify_cart before any order; 422/403 refusals).
**apps/api/tools.py was NOT modified this phase.** Custody grep
(`USER_MANDATE_KEY|sign_intent|sign_cart` under apps/api/agent/) found ONE
hit — a docstring mention in wallet_bridge.py ("(USER_MANDATE_KEY)"),
comment-only, no executable reference (the agent shells out to
scripts/mandate.py, a separate process). Per task contract the misleading
mention was deleted from the docstring; no code was touched.

## Verified

```
$ .venv\Scripts\python.exe scripts\verify_catalog.py
Catalog verification PASSED
   SKUs: 40
   All prices unchanged
   All prices are int paise (no floats)
   All injection payloads intact (I1-I7 markers)
   INJECTION_INDEX complete: I1-I8 (I8 proposal-time)
   All compatible_with targets valid
   All ratings in range [3.0, 5.0]
   All stock values in range [3, 40]
CATALOG_EXIT=0

$ custody one-liner (grep USER_MANDATE_KEY over apps/api/agent/*.py)
CUSTODY_OK

$ .venv\Scripts\python.exe -m pytest -q
82 passed, 1 warning in 3.87s

$ .venv\Scripts\python.exe -m pytest tests/test_money_path_offline.py tests/invariants/test_agent_custody.py tests/test_injections_structural.py tests/agent/test_deterministic_pick.py -q
12 passed, 1 warning in 2.70s

$ .venv\Scripts\python.exe -m ruff check apps/api/gateway/ apps/api/agent/ scripts/verify_catalog.py tests/...
All checks passed!

$ .venv\Scripts\python.exe -m mypy --strict apps/api/gateway/
Success: no issues found in 8 source files

$ grep -c "except ImportError" apps/api/gateway/engine.py  → 1 (F-06 untouched)
```

### Live branch (KEYS_PRESENT — rzp_test keys in .env)

Fresh server on :8000 (a stale day-5 server was found holding the port and
killed; the fresh boot reports `audit_chain_ok: true`).

```
$ bash scripts/smoke.sh                    (Git Bash)
--- V1: PASS  /health alive, chain ok
--- V2: PASS  manifest
--- V3: PASS  search cricket
--- V4: PASS  BAT-001 = 149900
--- V5: PASS  KIT-001 injection visible
--- V6: FAIL: http=200 rules_count=11        ← smoke.sh hardcodes 10 (stale)
--- V7: PASS  quote signed, total 179800
--- V8: PASS  check_payment 200
==== smoke: 7 passed, 1 failed ====
```

Real test-mode orders (order ids from the live runs, never typed by hand):

```
GET /demo/e2e →
  sign_mission ok → submit_proposal APPROVE seq=461 → quote 4b6ca78d11b7ce90
  → create_order ok order_id="order_TVy0c3wFQnALy0" (296ms)
  → check_payment ok → {"audit_chain_seq_after": 462, "audit_verified": true}

FULL EXECUTOR PATH (real custody: scripts/mandate.py wallet CLI signed both
mandates out-of-band; INV-1 + INV-3 gates passed):
  mission  MSN-LIVE-1788089861 (signed with MISSION_HMAC_KEY)
  POST /tools/submit_proposal → {"decision":"APPROVE","seq":464,
        "proposal_hash":"9b457217829c155808240cb362946493ebacad504624b18d0fea4b1d319bce24"}
  POST /tools/quote           → quote_id 90b41f075f44e417, total 149900
  scripts/mandate.py issue-intent + approve-cart (USER_MANDATE_KEY, separate process)
  POST /tools/create_order    → {"order_id":"order_TVy2xzsEsduPFK",
        "amount_paise":149900,"status":"created",
        "razorpay_key_id":"rzp_test_...","checkout_url":"/checkout/order_TVy2xzsEsduPFK"}
  GET  /tools/check_payment/order_TVy2xzsEsduPFK → status created, paid false

$ python scripts/send_test_webhook.py once / replay   (RAZORPAY_WEBHOOK_SECRET)
payment.authorized  evt_AAA111 -> 200 ok
payment.captured    evt_BBB222 -> 200 ok
payment.captured    evt_BBB222 -> 200 {"duplicate": true}   ← dedup works
payment.captured    evt_BBB222 -> 200 {"duplicate": true}

GET /audit → {"verified": true, "entries": 467}
tail: seq=464 gateway/verdict_emitted · seq=465 executor/mandate_verified ·
      seq=466 executor/order_created
```

## What broke

- **Stale day-5 server on :8000** silently answered the first health check and
  500'd /demo/e2e; killed it (PID 30036) and re-ran against a fresh boot.
- **smoke.sh V6 is stale**: hardcodes `rules_count == 10`; the registry holds
  11 since R11 (Day 5). Recorded, NOT fixed (out of Phase 2 scope) — Phase 3
  should update the expectation to 11.
- **/demo/e2e bypasses the executor registry**: its order (order_TVy0c3wFQnALy0)
  hits Razorpay and the chain but never enters tools.orders, so
  /tools/check_payment 404s for it. Structural gap of the demo endpoint
  (the real /tools/create_order path persists correctly — proven by the live
  executor-path transcript and the offline e2e test). Recorded, not fixed.
- **`chain._load_from_db()` does not re-select the enriched columns**
  (parent_action_id, review_state, ...): after any module reload (e.g. the
  T30 reset pattern) pre-reload entries lose parent linkage in memory. Disk
  is unaffected. Recorded as a small persistence gap; Phase 3 candidate.
- **Two of my first-draft tests failed in the full suite** and were fixed in
  the tests only: (1) mandate signing must read USER_MANDATE_KEY from the
  live env (module collection order decides which test module seeds it);
  (2) a fixed-id signed mission made verdict rows accumulate across tests,
  so the offline e2e now signs a UNIQUE mission id with the signer's own
  sign_blob, and picks THIS run's failure entry for the parent-linkage assert.
- No BLOCKERS.md needed: keys were present, the live branch ran for real.

## Learned

The money path is real end to end, but only the executor path (not the demo
path) is the durable one — and every "obviously fine" helper (a hardcoded
expectation in smoke, a fixed mission id, an env value read at a different
moment) is a test-order landmine waiting for the next phase.
