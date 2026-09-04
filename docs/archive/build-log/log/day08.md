# Day 8 - Phase 4: protocol adapter layer + R12_PROTOCOL_SCOPE

Date: 2026-08-31

## Goal

Build the v2 additions Phase 4 owns (per RECONCILIATION Table 2 and the frozen
gateway contract in ARCHITECTURE.md): the ACP/AP2/x402 protocol adapter layer
(F-01 included — the agent manifest now tells the truth), and R12_PROTOCOL_SCOPE
registered Phase 3 FATAL. Adapters translate; the gateway decides.

## Built

- **apps/api/gateway/rules_r12.py** — R12_PROTOCOL_SCOPE: binds protocol
  artifacts (merchant scope, category scope, amount ceiling, validity window),
  rejects citing the drifted field path, FAILS CLOSED on malformed scope
  (non-dict or wrongly-typed fields are violations, never passes). scope=None
  (native sellable-v1 traffic) skips the rule — same back-compat contract as
  R11's floor/ceiling skip. Pure stdlib.
- **apps/api/gateway/registry.py** — R12 entry: phase 3, FATAL. Registry count
  is now 12; `rules_count()` stays derived.
- **apps/api/gateway/engine.py** — module-top import of rules_r12 (Phase 3's
  hard-import discipline); R12 call in Phase 3 integrity after R11, before R7
  (first violation wins); `evaluate()` gains `protocol_scope: dict | None =
  None` — additive, zero behavior change for existing callers.
- **apps/api/tools.py** — `ProposalReq.protocol_scope` (optional) passed
  through to evaluate(); native clients omit it, so the money path is
  byte-identical for existing traffic.
- **apps/api/protocols/acp.py** — ACP-style adapter:
  POST /protocol/acp/checkout_sessions. Translates ACP line items
  ({id, quantity}) to sellable ({sku, qty}) and hands off to the canonical
  executor (`tool_submit_proposal`). The executor's verdict passes through
  untouched. API-key gated (F-08).
- **apps/api/protocols/ap2.py** — AP2-style adapter:
  POST /protocol/ap2/mandates/evaluate. Verifies the wallet-signed intent
  mandate (native mandates.py, signed out-of-band by scripts/mandate.py),
  enforces mission binding (mandate.mission_id must match), extracts the
  protocol scope (ceiling, validity window) and hands off to the same
  executor path. API-key gated.
- **apps/api/protocols/x402.py** — honest partial stub:
  POST /protocol/x402/authorize -> 501 {"implemented": false, ...}.
  x402 needs an irreversible payment rail; the stub refuses rather than
  simulate. Honesty over theater.
- **apps/api/main.py** — three routers hard-imported and mounted (Phase 3
  discipline: no try/except anywhere).
- **apps/api/manifest.py** — F-01 rewritten: `acp_ap2_x402` now states the
  adapters are live (with x402 as an honest stub) instead of the stale
  "tracked; patterns" claim.
- **tests/gateway/test_r12_protocol_scope.py** — 13 cases: registry entry
  (phase 3 FATAL), scope=None skip, merchant/category/ceiling/validity drifts
  each rejected citing the drifted path, ceiling-respected and future-window
  passes, malformed scope and each malformed field fail closed, full-scope
  happy path, first-violation-wins (R3 beats R12), rule-level unit case.
- **tests/test_protocols.py** — 11 HTTP cases: ACP happy path (translated
  items + APPROVE passthrough), unknown sku 400, protocol_scope binding
  through the adapter (executor REJECT R12_PROTOCOL_SCOPE on ceiling drift —
  the adapter never decided), ACP 401 without key; AP2 happy path (intent
  verified + APPROVE), ceiling exceeded refused by the wallet verifier (403
  MANDATE_CEILING_EXCEEDED), bad signature 403, mission mismatch 403, AP2 401
  without key; x402 honest 501 + 401 without key.
- **tests/invariants/test_protocol_adapter_invariants.py** — 5 structural
  cases: the three adapter files exist; NO gateway imports (AST-checked —
  docstrings may state the ban, only real imports violate); no verdict/
  decision construction and no evaluate() calls in adapters; no rule logic
  (no rule functions, registry access, or rule_id emission); both live
  adapters hand off to tool_submit_proposal.
- **tests/gateway/test_registry_reachability.py** — EXPECTED_RULE_COUNT 11 -> 12.
- **scripts/smoke.sh V6 + Makefile demo-check** — rules_count expectation
  11 -> 12 (updated, not weakened; the count change is deliberate Phase 4 work).
- **scripts/redteam.py** — cases 23 (x402 honest 501) and 24 (ACP adapter
  requires API key); arrow glyphs in case names replaced with ASCII after a
  cp1252 console crash (see What broke).
- **docs/ARCHITECTURE.md** — "Known limitations" bullet rewritten: adapters
  are implemented (was: "not yet implemented, Day-6 stretch goal"); R12
  registration note now factual; R13 cut recorded.
- **R13_WALLET_VELOCITY: CUT** (explicitly cut-line-able per RECONCILIATION):
  R6_RATE_LIMIT already bounds proposal velocity per mission at the gateway;
  per-wallet velocity would need a new persistent user-event store wired into
  the money path — real risk, marginal demo value, compressed sprint.

## Verified

```
$ .venv\Scripts\python.exe -m pytest tests\gateway\test_r12_protocol_scope.py -q
13 passed in 0.12s

$ .venv\Scripts\python.exe -m pytest tests\test_protocols.py -q
11 passed, 1 warning in 2.15s

$ .venv\Scripts\python.exe -m pytest tests\invariants\... -q
6 passed in 0.09s      (gateway purity 1 + adapter invariants 5)

$ full suite: 120 passed, 1 warning in 7.64s
  (Phase 3 head: 91; +13 R12, +11 protocols, +5 invariants = 120)

$ ruff check apps/api/gateway/ && mypy --strict apps/api/gateway/
All checks passed!
Success: no issues found in 9 source files   (rules_r12.py included)

$ GET /gateway/proof (live): {"files":9,"total_lines":643,
  "llm_imports_detected":0,"io_calls_detected":0,"forbidden_patterns_seen":[],...}

$ redteam (live server, all cases): PASS 1..24 (24/24), including
  PASS 20 wrong cart hash             403      (case restored — see What broke)
  PASS 23 x402 honest 501 stub        501 implemented=False
  PASS 24 ACP adapter requires API key -> 401  401

$ smoke.sh (live server): ==== smoke: 8 passed, 0 failed ==== (V6 now expects 12)
```

## What broke

- **cp1252 console crash in redteam.py**: the arrow glyph in case names
  ("missing API key -> 401", originally written with a Unicode arrow) crashed
  `print()` with UnicodeEncodeError on the Windows console (cp1252). Fixed by
  using ASCII arrows in case names — matching the ASCII style of cases 1-20.
- **My own encoding round-trip bug (same defect class as Phase 3's)**: I read
  redteam.py with PowerShell's Get-Content (ANSI default) and wrote it back
  UTF-8, mojibake-ing the arrows into `â†'`. Found because the redteam output
  printed the mojibake. Repaired byte-level (as in Phase 3); the file now has
  exactly one non-ASCII codepoint, the legitimate em-dash. Lesson reinforced:
  NEVER read/write source through PS 5.1 content cmdlets without explicit
  -Encoding UTF-8; use the editor tools or byte-explicit .NET calls.
- **redteam case 20 was silently skipped**: the Phase 3 session's edit had
  DELETED the `check("20 wrong cart hash", t20)` call while inserting cases
  21/22 — the def remained, the case never ran, nothing failed. The live run
  exposed it (output jumped 19 -> 21). Restored; case passes (403). This is
  exactly the silent-degradation failure mode this phase's tests hunt.
- **redteam cases 8, 9, 18, 20 hit 401 instead of mandate errors**: their
  create_order POSTs lacked the X-API-Key header (missed in Phase 3's sweep —
  the merge-style `headers={"X-Idempotency-Key": ...}` lines). Fixed by
  merging DEFAULT_HEADERS into all four; all now exercise their real target
  (403/422).
- **AST over substring for the import invariant**: the first draft failed on
  the adapters' own docstrings ("MUST NOT import apps.api.gateway"). The
  invariant now parses imports via ast, so the ban text doesn't count — only
  real imports do.

## Learned

An adapter that decides is a second gateway with no tests; an honest 501 is
worth more than a simulated 200 — and the fastest way to find a silently
skipped check is to actually run the whole suite against the live server and
read the gaps between the numbers.
