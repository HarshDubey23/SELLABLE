# Day 4 — Honesty Overhaul + Deterministic Recovery

Date: 2026-08-27

## Goal

Hardening after the big Day 3 push: make every demo honest, close the
custody and idempotency gaps, and replace the flaky Playwright checkout
with a real HTTP-only payment flow.

## Built

- **Honest mission statuses**: buyer.py now branches on `final_payment_status`:
  `completed` only on `captured`/`refunded`; otherwise
  `payment_failed_then_link_issued`, `order_created_payment_pending`, or
  `rejected`. The `mission_completed` event is conditional on real capture.
- **Deterministic recovery**: replaced Playwright-on-hosted-modal (zero
  captures on Day 3) with the documented public-key `POST /v1/payments`
  flow. Result is parsed from the embedded `var data = {...}` JSON on the
  callback page; authoritative status is re-read from
  `GET /v1/orders/{id}/payments`.
- **Real failure-recovery demo live**: UPI rail disabled on the test
  merchant -> Razorpay structured refusal -> audit `aud_67`
  (`error_code=BAD_REQUEST_ERROR`, `review_state=escalated`) -> real
  Gemini reasoning ("payment link should be generated...") -> `aud_68`
  (`parent=aud_67`, `reasoning_trace` saved) -> REAL payment link
  `plink_TUFe85E3GyhciA` (`https://rzp.io/rzp/eEt7AgE`) -> `aud_69`
  (`parent=aud_67`, `idempotency_key=idem_d62f...`,
  `review_state=pending_merchant`). Final status:
  `payment_failed_then_link_issued`.
- **Audit schema enriched**: `parent_action_id`, `idempotency_key`,
  `error_code`, `error_reason`, `reasoning_trace`, `mandate_id`,
  `review_state` (+ migration for pre-existing DBs).
- **Custody split**: `scripts/sign_mission.py` CLI pre-signs
  `missions/*.json`; FastAPI process only verifies, never signs.
  `scenarios.py` is now a loader, not a signer.
- **Idempotency keys**: every mutating Razorpay POST carries
  `X-Razorpay-Idempotency-Key`, deterministically derived from
  mission/proposal/seq, mirrored into the audit row.
- **Gemini quota fallback**: primary `gemini-3.6-flash` quota (20/day)
  degraded via ordered fallbacks `3.7-flash -> 3.5-flash -> 2.5-flash`
  on `429`/`RESOURCE_EXHAUSTED`.
- **Hygiene**: moved `e2e_day2`/`send_test_webhook` to `scripts/`,
  pinned `pyproject.toml` testpaths, added MIT `LICENSE`,
  `GET /catalog.jsonld` (schema.org Product+Offer), manifest
  `supported_protocols` declaration.

## Verified

```
$ python -m pytest -q
47 passed

$ curl /agent/run-scenario/payment_failure_recovery | jq .final_status
"payment_failed_then_link_issued"

$ curl /audit | jq '.entries[-3:] | map({seq, action, parent_action_id})'
aud_67 payment_attempt_failed  parent=null
aud_68 recovery_reasoned       parent=aud_67
aud_69 payment_link_issued     parent=aud_67
```

## What broke

- Playwright checkout never produced a single `captured` payment in any
  Day 3 run. Every `happy_path` ended `order_created_payment_pending`.
  Fix: dropped Playwright, went HTTP-only.
- Gemini `gemini-3.6-flash` daily free-tier quota hit mid-demo. Fix:
  ordered fallback chain on 429.
- Mission signing inside the FastAPI process violated the documented G5
  custody claim. Fix: out-of-band CLI signer.

## Next

Day 5: negotiation engine, eval harness, live captured-payment demo,
`GEMINI_MODEL` fix, missing tests, pitch video script.
