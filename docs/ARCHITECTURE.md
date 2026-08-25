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
apps/api/tools.py           Storefront tools (search/quote/proposal/order/
                            upsell endpoints). G1 gate lives here.
apps/api/gateway/
  engine.py                 evaluate(): 4 phases, first violation wins,
                            fail-closed. The ONLY code that emits APPROVE.
  rules.py                  R1-R10 as pure functions.
  types.py                  Mission, Proposal, Verdict, canonical_json.
  mission_verify.py         HMAC sign/verify against MISSION_HMAC_KEY.
  proof.py                  Purity report + source hash.
apps/api/products.py        40-SKU catalog with ratings, attributes,
                            compatible_with, policies, stock. Injection
                            payloads I1-I7 planted in descriptions.
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
apps/api/payment/checkout.py Playwright automation of Razorpay test-mode
                            checkout (success/failure test cards).
apps/api/webhook/receiver.py Raw-body HMAC verify, event dedup on
                            X-Razorpay-Event-Id, status hierarchy
                            (created < authorized < captured < refunded).
apps/api/store/db.py        SQLite persistence (stdlib sqlite3, WAL,
                            thread-safe). Path override via SELLABLE_DB_PATH
                            so tests never touch production data.
apps/api/audit/chain.py     Append-only SHA-256 hash chain. DB write first,
                            memory second. GENESIS at seq 0.
```

## Gateway execution order

```
PRE : INPUT_MISSING (fail-closed), CHAIN_TAMPER (halt)
Ph0 : R9_SIGNATURE (HMAC), R10_EXPIRY          FATAL
Ph1 : R8_ABORT                                 FATAL
Ph2 : R1_BUDGET (effective = budget x cap),
      R2_FORBIDDEN, R5_SCOPE, R4_UPSELL_CAP    REVISABLE
Ph3 : R3_PRICE_DRIFT, R7_ALLOWLIST, R6_RATE_LIMIT  FATAL
```

First violation wins; its rule_id is cited. On APPROVE the verdict binds
`proposal_hash`; the executor re-checks that binding at order time.

### R1 semantics (Day 3 fix)

R1 checks the EFFECTIVE budget: `budget_paise x upsell_cap`. Before the fix
R1 checked base budget, which made the upsell window impossible and R4 dead
code. R4 remains as defense-in-depth at the same threshold.

## Data flow (happy path)

```
buyer agent -> GET /.well-known/agent-manifest.json
buyer agent -> GET /tools/search_products?query=...   (intent-token ranked)
buyer agent -> GET /tools/get_product/{sku}           (injections visible)
buyer agent -> [LLM] propose items
buyer agent -> POST /tools/submit_proposal            (prices filled SERVER-side)
gateway     -> evaluate() -> verdict_emitted (chained)
merchant    -> GET /tools/upsell_offers               (pre-gated offers)
buyer agent -> [LLM] accept/decline -> if accept: full gateway pass again
buyer agent -> POST /tools/quote                      (signed price lock)
buyer agent -> POST /tools/create_order               (approve_seq REQUIRED)
executor    -> Razorpay order.create (test mode) -> order_created (chained)
browser     -> GET /checkout/{order_id} -> Razorpay Checkout JS
razorpay    -> POST /webhook (HMAC'd) -> ledger update -> payment_captured (chained)
```

## Persistence

Everything durable lives in `data/sellable.db`: audit_chain, orders, quotes,
verdicts, webhook_events. Boot reloads quotes/orders/verdicts/bindings and
rebuilds the webhook dedup set + payment ledger from disk. Restart loses
nothing. Tests run against a throwaway DB (`tests/conftest.py`) so CI can
never pollute demo state.

## Known limitations

- Playwright checkout automation targets today's Razorpay DOM; if their
  markup drifts, attempts fail loudly (status "failed"/"unknown" +
  screenshot) instead of silently passing.
- Upsell offer endpoints resolve the mission from in-memory state; after a
  restart they return "mission not found" until a fresh proposal is
  submitted. Orders/verdicts themselves survive restarts.
