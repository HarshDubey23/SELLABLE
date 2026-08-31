# SELLABLE Architecture

Single source of truth for how the system works. If code and this document
disagree, one of them is wrong — fix it the same day.

## Thesis

The LLM proposes. The policy engine disposes. The audit log remembers.

## Invariant INV-1 (never break this)

For every money action M in the audit log, there exists a gateway Verdict V
with `hash(V.proposal) == hash(M.proposal)` and `V.decision == APPROVE`.
No LLM call appears in the causal path between V and M.

Enforcement layers:

1. `apps/api/gateway/` imports ZERO LLM SDKs, zero network clients, zero
   FastAPI. `tests/invariants/test_gateway_purity.py` greps every gateway
   file; CI fails on any match.
2. `/gateway/proof` returns the same purity report live with a SHA-256 of
   the gateway source — any byte change is detectable.
3. `create_order` REQUIRES an `approve_seq` whose stored binding matches
   `proposal_hash`. No APPROVE binding -> 403. This check is unconditional.
4. The audit chain self-verifies at boot (`[BOOT] audit chain verify ->
   True`). Tamper -> `verify()` False -> every `evaluate()` returns
   `CHAIN_TAMPER` -> money path halts.

## Component map

```
apps/api/main.py            FastAPI shell. Routers, /health, /audit,
                            /gateway/proof. Boot-verifies the chain.
                            Day 5: registers /negotiation/* + /demo/capture.
apps/api/tools.py           Storefront tools (search/quote/proposal/order/
                            upsell endpoints). G1 gate lives here.
apps/api/gateway/
  engine.py                 evaluate(): 4 phases, first violation wins,
                            fail-closed. Day 5: calls R11 after R3.
  rules.py                  R1-R10 as pure functions.
  rules_r11.py              R11_NEGOTIATION_BOUND (Phase 3 FATAL, Day 5).
  types.py                  Mission, Proposal, Verdict, canonical_json.
  mission_verify.py         HMAC sign/verify against MISSION_HMAC_KEY.
  proof.py                  Purity report + source hash.
apps/api/products.py        40-SKU catalog with ratings, attributes,
                            compatible_with, policies, stock. Injection
                            payloads I1-I7 planted in descriptions.
                            Day 5: floor_paise + ceiling_paise per SKU.
apps/api/negotiation/       Bounded negotiation engine (Day 5, 9 files):
  types.py                  NegotiationState, Offer, Turn, Result (pure stdlib, N-1).
  bounds.py                 clamp, monotonic, walk-away, budget, TTL (pure stdlib, N-1).
  strategies.py             Merchant anchor-concede + buyer concession (pure stdlib, N-1).
  llm.py                    LLM rationale generation (ONLY genai import in negotiation/).
  persist.py                SQLite save/load (negotiations + negotiation_turns tables).
  engine.py                 start_negotiation, run_turn, run_to_completion.
  api.py                    6 /negotiation/* FastAPI routes.
  catalog_pricing.py        FLOOR_CEILING for 40 SKUs + apply_floor_ceiling().
apps/api/demo_capture.py    POST /demo/capture — live captured-payment demo (Day 5).
apps/api/razorpay_client.py THE money boundary. Day 5: added capture_payment().
apps/api/upsell/
  engine.py                 Deterministic upgrades, pre-gated to
                            budget x upsell_cap. Zero LLM.
  crosssell.py              compatible_with-based add-ons, pre-gated.
apps/api/agent/
  buyer.py                  Buyer agent loop: discover -> search -> details
                            -> reason -> propose -> revise once -> upsell
                            decision -> order -> payment -> status poll.
  trace.py                  Protocol trace events per mission.
  scenarios.py              6 demo missions, freshly signed per run.
  runner.py                 /agent/* HTTP endpoints.
apps/api/webhook/receiver.py Raw-body HMAC verify, event dedup on
                            X-Razorpay-Event-Id, status hierarchy
                            (created < authorized < captured < refunded).
apps/api/store/db.py        SQLite persistence (stdlib sqlite3, WAL,
                            thread-safe). Path override via SELLABLE_DB_PATH
                            so tests never touch production data.
                            Day 5: also holds negotiations + turns tables.
apps/api/audit/chain.py     Append-only SHA-256 hash chain. DB write first,
                            memory second. GENESIS at seq 0.
eval/                       Three-arm eval harness (Day 5):
  missions/generate.py      100 seeded missions (5 categories).
  run.py                    Three-arm runner (static/ungated/gated).
  metrics.py                ArmResult + compare() + trust-adjusted revenue.
  report.py                 Markdown report generator.
```

## Gateway execution order (Day 5, with R11)

```
PRE : INPUT_MISSING (fail-closed), CHAIN_TAMPER (halt)
Ph0 : R9_SIGNATURE (HMAC), R10_EXPIRY          FATAL
Ph1 : R8_ABORT                                 FATAL
Ph2 : R1_BUDGET (effective = budget x cap),
      R2_FORBIDDEN, R5_SCOPE, R4_UPSELL_CAP    REVISABLE
Ph3 : R3_PRICE_DRIFT, R11_NEGOTIATION_BOUND, R7_ALLOWLIST, R6_RATE_LIMIT  FATAL
```

First violation wins; its rule_id is cited. On APPROVE the verdict binds
`proposal_hash`; the executor re-checks that binding at order time.

### R1 semantics (Day 3 fix)

R1 checks the EFFECTIVE budget: `budget_paise x upsell_cap`. Before the fix
R1 checked base budget, which made the upsell window impossible and R4 dead
code. R4 remains as defense-in-depth at the same threshold.

### R11 semantics (Day 5)

R11 checks every item price is within `[floor_paise, ceiling_paise]` read
from the server-side catalog. It runs after R3 (so price drift is already
checked) and before R7. A violation is FATAL (no revision) — a price
outside bounds is a bug or attack, not a negotiable disagreement.

## Data flow (happy path + Day 5 negotiation + capture)

```
buyer agent -> GET /.well-known/agent-manifest.json
buyer agent -> GET /tools/search_products?query=...   (intent-token ranked)
buyer agent -> GET /tools/get_product/{sku}           (injections visible)
buyer agent -> [LLM] propose items
buyer agent -> POST /tools/submit_proposal            (prices filled SERVER-side)
gateway     -> evaluate() (R1-R11) -> verdict_emitted (chained)
  |
  |-- OPTIONAL: multi-turn bounded negotiation (Day 5)
  |     POST /negotiation/start   (floor, ceiling, budget, max_turns)
  |     loop (max_turns):
  |       engine.run_turn():
  |         buyer offer (deterministic price, LLM rationale) -> audit
  |         merchant counter (deterministic price, LLM rationale) -> audit
  |         check accept / walk_away / ttl
  |     if ACCEPTED: final_price = merchant's last offer (still <= budget)
  |     if WALKED_AWAY: no order created, audit shows impasse
  |     [Agreed price STILL goes through /tools/submit_proposal -> evaluate() -> create_order]
  |
merchant    -> GET /tools/upsell_offers               (pre-gated offers)
buyer agent -> [LLM] accept/decline -> if accept: full gateway pass again
buyer agent -> POST /tools/quote                      (signed price lock)
buyer agent -> POST /tools/create_order               (approve_seq REQUIRED)
executor    -> Razorpay order.create (test mode) -> order_created (chained)
  |
  |-- /demo/capture path (Day 5): card payment via public-key POST /v1/payments
  |     -> if authorized: POST /v1/payments/{id}/capture
  |     -> poll GET /v1/orders/{id}/payments until captured
  |     -> payment_captured (audit-chained, parent_action_id links chain)
  |
razorpay    -> POST /webhook (HMAC'd) -> ledger update -> payment_captured (chained)
```

### Three failure modes demonstrated (Day 5)

| # | Failure | Detection | Recovery | Demo |
|---|---------|-----------|----------|------|
| 1 | Prompt injection (I1-I8) | R3 reads price server-side | No money effect | /demo/injection/{n} |
| 2 | Payment failure (UPI refusal) | Razorpay BAD_REQUEST_ERROR | Gemini -> Payment Link | /agent/run-scenario/payment_failure_recovery |
| 3 | Negotiation walk-away | bounds.check_walk_away() | No order, audit shows impasse | /negotiation/{id}/run |

## Persistence

Everything durable lives in `data/sellable.db`: audit_chain, orders, quotes,
verdicts, webhook_events, negotiations, negotiation_turns. Boot reloads
quotes/orders/verdicts/bindings and rebuilds the webhook dedup set + payment
ledger from disk. Restart loses nothing. Tests run against a throwaway DB
(`tests/conftest.py`) so CI can never pollute demo state.

## Known limitations

- Upsell offer endpoints resolve the mission from in-memory state; after a
  restart they return "mission not found" until a fresh proposal is
  submitted. Orders/verdicts themselves survive restarts.
- Protocol adapters (Phase 4): ACP and AP2 are live at
  /protocol/acp/checkout_sessions and /protocol/ap2/mandates/evaluate —
  they translate protocol payloads into the canonical executor
  (`tool_submit_proposal`) and the gateway decides; x402 is an honest 501
  stub (refuses rather than simulate an irreversible rail). Adapters never
  import the gateway, never construct verdicts, and contain no rule logic
  (machine-checked in tests/invariants/test_protocol_adapter_invariants.py).
  R12_PROTOCOL_SCOPE (Phase 3 slot, FATAL) re-binds the adapters' protocol
  artifacts (merchant scope, category scope, amount ceiling, validity
  window) at decision time, rejecting with the drifted field path.
  R13_WALLET_VELOCITY was CUT (cut-line-able per RECONCILIATION): R6
  already bounds proposal velocity per mission, and a per-wallet event
  store would add money-path risk for marginal demo value.
- Negotiation persists to SQLite; the in-memory `NegotiationState` mirror is
  rebuilt from DB on `GET /negotiation/{id}`.

## Gateway contract consumed by v2

(Added Phase 1 — frozen so Phases 4 and 7 build against a stated contract.
Corrected during Phase 1 to describe the code as it actually is.)

- **Registry is the single source of truth.** `apps/api/gateway/registry.py::RULE_REGISTRY` enumerates every rule that can produce a verdict. Adding a rule means: a rule module + a registry entry + a module-top import in `engine.py`. Nothing else. `rules_count()` is derived, never hardcoded. `GET /policy` serves the registry verbatim.
- **Evaluation is four phases (0–3), in order.** Phase 0 guardrails (R9_SIGNATURE, R10_EXPIRY), Phase 1 mission state (R8_ABORT), Phase 2 commerce (R1_BUDGET, R2_FORBIDDEN, R5_SCOPE, R4_UPSELL_CAP), Phase 3 integrity (R3_PRICE_DRIFT, R11_NEGOTIATION_BOUND, R7_ALLOWLIST, R6_RATE_LIMIT). Before the phases, two fail-closed guards reject without consulting any rule: `INPUT_MISSING` (no mission/proposal/empty catalog) and `CHAIN_TAMPER` (audit chain verification failed). **First violation wins**: any violation short-circuits evaluation immediately, regardless of severity. Callers and adapters must never reorder, skip, or cherry-pick phases.
- **Verdict vocabulary is APPROVE | REJECT — nothing else.** `gateway/types.py::Decision` has exactly these two values. Severity (`FATAL` vs `REVISABLE` in the registry) is advisory metadata for callers, not a verdict: a violation of either severity yields `REJECT` with `rule_id`, `reason`, and the bound `proposal_hash`. `REVISABLE` means the caller MAY revise the proposal and re-submit (`seq`/`proposal_hash` of the rejected attempt stay chained for `GET /tools/explain_reject`); `FATAL` means revision cannot help (signature, expiry, abort, price drift, bounds, allowlist, rate limit). On APPROVE, `rule_id` is `None` and `proposal_hash` binds the exact approved bytes.
- **R12 registration (Phase 4).** `R12_PROTOCOL_SCOPE` registers as **Phase 3, FATAL** — it binds protocol artifacts (merchant scope, category scope, amount ceiling, validity window) and rejects citing the drifted field path. R13 (if built) registers the same way.
- **INV-1 binding (executor side).** A verdict alone moves no money. `POST /tools/create_order` requires `approve_seq` + `proposal_hash` matching the recorded APPROVE binding (`approved_bindings`, written only by `submit_proposal` on APPROVE); mismatch → HTTP 403 `ORDER_HASH_MISMATCH`. This is enforced at `apps/api/tools.py` and covered by `tests/gateway/test_inv1_binding.py` (tamper refused, untampered pair proceeds to the Razorpay boundary offline-mocked).
- **Purity invariant.** `apps/api/gateway/` stays pure stdlib — no LLM, no network, no file I/O — enforced by `tests/invariants/test_gateway_purity.py`, the Phase 1 coverage guard (`tests/gateway/test_registry_coverage.py`: every registry rule must appear in the suite), and exposed live at `GET /gateway/proof` (real keys: `files`, `total_lines`, `llm_imports_detected`, `io_calls_detected`, `forbidden_patterns_seen`, `source_sha256`, `invariant_test`).
- **Known engine defect (F-06, owned by Phase 3).** The R11 call site sits inside `try/except ImportError` at `apps/api/gateway/engine.py` (~lines 88–94); if `rules_r11.py` ever failed to import, R11 would be silently skipped. Phase 3 converts it to a hard module-top import with a red-CI acceptance test.
