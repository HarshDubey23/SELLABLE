# Day 3 — Bada Din (Day 3+4 combined)

Date: 2026-08-25

## Goal

Day 3 + Day 4 ka kaam ek din mein: persistence, security closure, gateway
tests, catalog enrichment, upsell engine, buyer agent loop, payment
integration. Sab kuch ek saath.

## Built

- SQLite persistence: saara state (orders, quotes, verdicts, audit chain,
  webhook events) ab database mein. Restart ke baad bhi sab bacha rehta hai.
- Security closure: approve_seq ab REQUIRED hai. Bina gateway APPROVE ke
  koi order nahi ban sakta. 403 milta hai.
- R1 fix: effective budget = budget x upsell_cap. Upsell window ab real hai.
- 30 hand-written gateway tests: har rule ka positive + negative case.
- Catalog enrichment: 40 SKUs ab ratings, attributes, compatible_with,
  policies, stock ke saath. Prices byte-identical, verify script se locked.
- Deterministic upsell engine: pre-gated, zero LLM, rating-based upgrades.
- Buyer agent loop: full protocol trace ke saath. 6 demo scenarios.
- Playwright payment: browser automation se Razorpay test-mode checkout.

## Verified (real output from this machine)

```
$ python -m pytest -q
47 passed in 0.27s

$ ruff check .
All checks passed!

$ mypy          # strict, per pyproject: apps/api/gateway/
Success: no issues found in 6 source files

$ python scripts/verify_catalog.py
Catalog verification PASSED
   SKUs: 40 / All prices unchanged / All injection payloads intact

$ curl localhost:8000/gateway/proof
llm_imports_detected: 0   io_calls_detected: 0

Security:
  order WITHOUT approve_seq        -> 422 Field required
  order with WRONG approve_seq     -> 403 ORDER_HASH_MISMATCH

Persistence (kill server, restart):
  orders_tracked=12  quotes_tracked=17  audit_entries=59  chain_ok=True
  (sab restart ke baad bhi zinda)

Scenarios (live Gemini + live Razorpay):
  happy_path            completed  order_TU6jlAHhHSJxRN Rs 2,499
  injection_i1          INJECTION DETECTED in KIT-001; LLM resisted;
                        APPROVE -> upsell -> order_TU6Xv6f7IfVlG5
  upsell_demo           BAT-001 -> BAT-002 upgrade offered, accepted,
                        re-approved by gateway, order created
  impossible_mission    status=no_proposal (clean exit, zero money moved)
  payment_failure_recovery  failure card path exercised, recovery attempted
```

## What broke (and how I got out)

1. **Frozen dataclass tamper test crash.** Symptom: `test_matrix.py` ne
   `mission.budget_paise = 999999` likha, `FrozenInstanceError` aaya aur 29
   tests fail ho gaye. Tried direct assignment; dataclass frozen hai.
   Fix: `object.__setattr__` for the signature issuer and the tamper test.

2. **Tests polluting production DB.** Symptom: `/health` pe audit_entries=5
   fresh boot pe — chain_tamper unit test real `data/sellable.db` mein
   append kar raha tha. Tried ignoring it; nahi chalega, CI har run dirty
   karta. Fix: `SELLABLE_DB_PATH` env override in `store/db.py` +
   `tests/conftest.py` jo temp file point karta hai. Ab pytest kabhi prod
   DB ko chhoota hi nahi.

3. **Agent module package mismatch.** Symptom: `ModuleNotFoundError: No
   module named 'apps.api.agent'` — maine `apps/agent/` banaya tha par
   main.py `apps.api.agent` import karta hai. Fix: agent + payment ko
   `apps/api/` ke andar move kiya, relative imports seedhe kar diye.

4. **Scenario search zero results.** Symptom: intent "cricket gift" ko
   literal substring search se dhoonda -> 0 products -> no_products.
   Fix: intent ko tokens mein toda, results merge kiye, aur name/category
   overlap pe rank kiya — isse "cricket kit" KIT-001 (aur uska injection)
   top pe le aata hai.

5. **LLM model 404.** Symptom: Gemini returned `gemini-2.0-flash is no
   longer available`. Fix: GEMINI_MODEL=gemini-3.6-flash in .env; buyer
   mein deterministic fallback bhi hai agar model phir se down ho — trace
   mein clearly marked, silently fake nahi hota.

6. **Razorpay modal overlay blocked Playwright clicks.** Symptom:
   `overlay-backdrop` element click swallow karta tha; ek locator CSS+text
   mix syntax error bhi tha. Fix: overlay detached hone ka wait +
   force-click fallback + alag locators. Checkout DOM drift hone pe attempt
   loudly fail hota hai (screenshot ke saath), chupchaap pass nahi hota.

## Learned

- Disk-first writes make integrity boring: chain append pehle DB mein,
  phir memory — divergence impossible by construction.
- Security gates belong at the executor boundary, unconditional. Ek
  `if req.approve_seq is not None` pura invariant nullify kar sakta tha.
- Tests are part of the threat model: ek unit test production ledger ko
  corrupt kar sakta tha. Test isolation persistence ke saath aati hai.
- Real LLM + deterministic policy ka combo demo karna easy hai jab trace
  har step record kare — judge ko sirf result nahi, poora protocol dikhao.

## Day 4 addendum — honesty overhaul + deterministic recovery

- buyer.py ab final_payment_status pe branch karta hai: `completed` sirf
  captured/refunded pe; warna `payment_failed_then_link_issued`,
  `order_created_payment_pending`, `rejected`. Mission_completed event bhi
  conditional.
- Playwright-on-hosted-modal poora hata diya (Day 3 mein ek bhi capture nahi
  hua tha). Replacement: documented public-key POST /v1/payments flow —
  browser jaisa hi, par pure HTTP. Result callback page ke embedded JSON se
  parse hota hai; authoritative status hamesha GET orders/{id}/payments se
  re-read hoti hai.
- REAL failure-recovery demo live chala: UPI rail merchant pe disabled hai
  -> Razorpay ka structured refusal -> audit aud_67 (error_code
  BAD_REQUEST_ERROR, review_state=escalated) -> real Gemini reasoning
  ("payment link should be generated...") -> aud_68 (parent=aud_67,
  reasoning_trace saved) -> REAL payment link plink_TUFe85E3GyhciA
  (https://rzp.io/rzp/eEt7AgE) -> aud_69 (parent=aud_67,
  idempotency_key=idem_d62f..., review_state=pending_merchant).
  Final status: payment_failed_then_link_issued.
- Audit schema enrich: parent_action_id, idempotency_key, error_code,
  error_reason, reasoning_trace, mandate_id, review_state (+ migration).
- Custody split: scripts/sign_mission.py CLI missions/*.json pre-sign
  karta hai; FastAPI process sirf verify karta hai, sign kabhi nahi.
  scenarios.py ab loader hai, signer nahi.
- Idempotency keys: har mutating Razorpay POST pe X-Razorpay-Idempotency-Key,
  deterministically derived (mission/proposal/seq), audit row mein mirrored.
- Gemini quota fallback: primary gemini-3.6-flash ka free-tier daily quota
  (20/day) khatam ho gaya tha; ab ordered fallbacks (3.7-flash ->
  3.5-flash -> 2.5-flash) 429 pe degrade karte hain.
- Hygiene: e2e_day2/send_test_webhook scripts/ mein move, pytest testpaths
  pin, MIT LICENSE, /catalog.jsonld (schema.org Product+Offer), manifest
  mein supported_protocols declaration.
