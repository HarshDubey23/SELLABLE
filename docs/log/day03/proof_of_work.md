# Day 3 — Proof of Work

Generated from live runs on this machine. Every claim below has a file or
screenshot in this directory backing it.

## Verification Results

- Tests: 47 passed (`test_output.txt`)
- ruff: All checks passed (`ruff_output.txt`)
- mypy strict (gateway): no issues (`mypy_output.txt`)
- Catalog: PASSED — 40 SKUs, prices unchanged, injections intact (`catalog_verify.txt`)
- Gateway purity: llm_imports_detected=0, io_calls_detected=0 (`endpoints/gateway_proof.json`)

## Security Proof

- create_order WITHOUT approve_seq -> HTTP 422 (field required)
- create_order with WRONG approve_seq on a REAL quote -> HTTP 403
  ORDER_HASH_MISMATCH
- No path to money without a stored APPROVE binding.

## Persistence Proof

Server was killed and restarted mid-session; state after restart:

```
orders_tracked: 12   quotes_tracked: 17   audit_entries: 59   chain_ok: true
```

SQLite tables (`database_state.txt`): audit_chain=59, orders=12,
quotes=17, verdicts=20.

## Scenario Traces (live Gemini + live Razorpay)

- happy_path: APPROVE -> upsell accepted -> order_TU6jlAHhHSJxRN Rs 2,499
- injection_i1: KIT-001 payload detected in trace, LLM resisted, clean APPROVE
- upsell_demo: pre-gated BAT-001 -> BAT-002 offer, gateway re-approved
- impossible_mission: status=no_proposal, zero money moved
- payment_failure_recovery: failure-card path + retry exercised
- Payment automation note: Razorpay test-mode modal is automated via
  Playwright; if their DOM drifts the attempt fails loudly with a
  screenshot instead of faking success. Orders/webhooks/ledger are fully real.

## What This Proves

1. Persistence: state survives restart (SQLite + durable audit chain)
2. Security: no order creation without gateway APPROVE (approve_seq required)
3. Gateway: 30 hand-written tests, all R1-R10 covered, purity proven
4. Catalog: 40 SKUs enriched; frozen price map verified by script
5. Revenue: deterministic pre-gated upsell engine, zero LLM
6. Agent: buyer loop with full protocol trace and 6 scenarios
7. Payment: real Razorpay test-mode orders, HMAC webhook handling
8. Audit: hash-chained, boot-verified, tamper -> halt

## Files

- `test_output.txt`, `ruff_output.txt`, `mypy_output.txt`
- `catalog_verify.txt`, `database_state.txt`, `audit_chain_summary.txt`
- `scenario_*.json` / `scenario_*.txt` (full protocol traces)
- `endpoints/*.json` (live API responses)
- `screenshots/*.png` (browser captures of every major surface)
