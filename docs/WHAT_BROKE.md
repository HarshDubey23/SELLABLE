# WHAT BROKE — and how I got out

Real failures from building SELLABLE, not sanitized.

## 1. Gemini model 404 — `gemini-2.0-flash is no longer available`
- **Problem:** Every LLM call returned `404 NOT_FOUND` — buyer agent fell back to deterministic proposer, negotiation rationales were `Buyer offers Rs...` (fallback), not real Gemini.
- **Why:** Google retired `2.0-flash`/`2.5-flash` for new users; our `.env.example` still listed them. Fallback chain only caught `429`, not `404`.
- **Detected:** `client.models.list()` showed `google/gemini-1.5-flash` as current; direct `ask()` with fallback showed `404` then fallback `503` then success on `3.6`.
- **Fixed:** `apps/api/llm/gemini.py:57` now catches `404`/`NOT_FOUND` as fallback trigger, `.env.example:7` updated to `google/gemini-1.5-flash`, fallback `gemini-3.5-flash`. Verified live: `ask()` returns `model=google/gemini-1.5-flash latency 3939ms`.
- **Test:** `scripts/redteam.py` includes LLM-unavailable case; `pytest -q` still 65 pass via fallback path.
- **Superseded:** the LLM boundary later moved to OpenRouter, so the model
  name in this entry no longer matches `.env.example`. The finding stands;
  the configuration does not.

## 2. Evaluation was rigged — `injections_blocked +=1` without verdict
- **Problem:** `eval/run.py:123` did `if injected: injections_blocked+=1` regardless of gateway decision. Also used `hash() %20` lottery for recovery revenue and fake `fraud_loss` via `INJECTION_PRICE_DROP`.
- **Why:** Copied naive harness that counted strings, not security.
- **Detected:** Critical review flagged it; manual audit showed gated always 100% even if gateway was bypassed in code.
- **Fixed:** `eval/run.py` now builds adversarial proposals with fake price `100` (R3 violation), calls `evaluate()`, and only counts `blocked` if `verdict==REJECT`. Ungated renamed `simulated_ungated` (synthetic, not LLM). Removed `hash()` → `random.Random(seed)`, removed fake recovery (`0`). Methodology documented in `eval/results.json:methodology`.
- **Test:** `python -m eval.run --missions 100 --reps 3` now honestly shows `gated 100% (45/45) vs ungated 0%` derived from verdicts.

## 3. Policy said 10 rules, engine had 11 (R11)
- **Problem:** `apps/api/tools.py:318` hardcoded `rules_count:10` while `apps/api/gateway/engine.py:88` called `R11_NEGOTIATION_BOUND`. Docs, README, and endpoint disagreed.
- **Why:** R11 added in Day 5 but policy list not updated; no single source.
- **Detected:** `curl /policy | jq .rules_count` vs `grep -r R11`.
- **Fixed:** `apps/api/gateway/registry.py` canonical `RULE_REGISTRY` (11 entries). `tools.py:315` now `len(RULE_REGISTRY)`. `engine.py` order matches registry. README updated to 11.
- **Test:** `GET /policy` now `11`, `gateway/proof` `files:8` includes `registry.py`.

## 4. Webhook fail-open on empty secret
- **Problem:** `apps/api/webhook/receiver.py:98` used `os.getenv(..., "")` — empty secret → HMAC with empty key, any attacker could forge.
- **Why:** Default to empty for convenience.
- **Detected:** Review + manual test with `RAZORPAY_WEBHOOK_SECRET=""`.
- **Fixed:** Fail-closed `503 WEBHOOK_SECRET_MISSING` if empty (`receiver.py:15`). Added raw-body HMAC before JSON parse (already did), replay protection only after `store.execute` succeeds (so DB failure allows retry), audit `payment_captured` append failure returns `503` not `200`.
- **Test:** `scripts/redteam.py:15` forged webhook → `400`, missing secret → `503` (redteam).

## 5. Custody story was fake — `user` was `buyer_agent`
- **Problem:** Trace said `"actor":"user"` but code was `wallet_bridge` spawning `scripts/mandate.py` locally as `buyer_agent` — not a separate trust boundary, not out-of-band.
- **Why:** Copied AP2 wording without implementing separation.
- **Detected:** Review flagged `out-of-band` while `wallet_bridge.py` just did `subprocess.run` in same host.
- **Fixed:** `wallet_bridge.py:1` now documents `simulated locally (separate process, NOT production)`, `buyer.py:152` emits `simulated_user` + `wallet_process` actors, not `user`. README notes `Prototype wallet is simulated locally`.
- **Test:** `tests/test_custody.py` (new) asserts server never calls signing, mandates verify.

## 6. Playwright payment never captured
- **Problem:** Day 3 `happy_path` used Playwright on Razorpay hosted modal — overlay blocked clicks, `overlay-backdrop` swallow, zero captures, status always `order_created_payment_pending`.
- **Why:** Hosted modal DOM is private and changes; relying on selectors is brittle.
- **Detected:** Every `scenario_happy_path.json` showed `order_created` but no `captured`; `docs/log/day03/proof_of_work.md:47` admitted it.
- **Fixed:** Day 4 replaced with public-key `POST /v1/payments` + `var data = {...}` parse (`apps/api/razorpay_client.py:attempt_checkout_payment`), `POST /v1/payments/{id}/capture` if authorized, poll `GET /v1/orders/{id}/payments`. Recovery still via `POST /v1/payment_links`.
- **Test:** `scenario_payment_failure_recovery.json` now shows real `BAD_REQUEST_ERROR` → `plink_...`.

## 7. Makefile lied — `13 verifications` but smoke has 8
- **Problem:** `Makefile:16` echoed `13 curl verifications` but `scripts/smoke.sh` only had V1-V8.
- **Why:** Copied old comment, never updated.
- **Detected:** `bash scripts/smoke.sh` vs `make smoke` output.
- **Fixed:** `Makefile:16` now `8`, removed dead `demo-*` targets, added `make verify` (test + smoke + eval 30x2).
- **Test:** `make verify` runs successfully.

## 8. Stale missions — `expires_at` 2 days ago
- **Problem:** `missions/*.json` had `expires_at` in past, every `POST /tools/submit_proposal` returned `R10_EXPIRY`.
- **Why:** Signed once, never re-signed; TTL 24h.
- **Detected:** `curl /agent/run-scenario/happy_path` returned `REJECT R10_EXPIRY` in logs.
- **Fixed:** `python scripts/sign_mission.py` re-signs all 6 with fresh `expires_at`, `.gitignore` now ignores `*_mandate.json` side-effects.
- **Test:** `pytest tests/test_signer_sync.py` now ignores mandate files.

## 9. Negotiation disconnected from money
- **Problem:** `POST /negotiation/{id}/run` returned `final_price` but nothing forced that price through `R11` or `create_order` — demo could claim negotiation without money path.
- **Why:** Feature was side surface.
- **Detected:** Review asked “can negotiated price be spent?”
- **Fixed:** Documented in `docs/ARCHITECTURE.md:125` that negotiated price MUST go through `POST /tools/submit_proposal` → `R11` → `APPROVE` → `create_order`. Added `tests/test_negotiation_integration.py` that forces negotiated price through gateway and asserts `R11` rejects out-of-bounds.
- **Test:** `make test` includes negotiation integration.

## 10. Documentation drift — numbers, model names, endpoints
- **Problem:** README said `61 tests`, `files:6`, `gemini-2.0-flash`, `10 rules`, `31 endpoints` — code had `65`, `8`, `3.6`, `11`, `32`.
- **Why:** Hand-maintained prose, no derivation.
- **Detected:** `python -m pytest -q` vs README, `GET /gateway/proof` vs README.
- **Fixed:** README now says `65`, `8`, `google/gemini-1.5-flash`, `11`, `32`, adds `RULE_REGISTRY` note, adds judge map, clarifies `simulated_ungated` vs real live demo.
- **Test:** `scripts/verify_numbers.py` (new) derives numbers from code and fails if README drifts.

## 11. The reconciler wrote off a payment that had actually gone through

This is the worst bug in the list, because it is the exact failure the
project exists to prevent, committed by the code that was supposed to
prevent it.

- **Problem:** I injected a lost provider response against the real
  Razorpay test API. The order was dispatched and created; only the reply
  was discarded. The execution correctly landed in
  `RECONCILIATION_REQUIRED`. Seventeen seconds later I reconciled. The
  authoritative read came back empty, the reconciler concluded
  `NO_REMOTE_ORDER`, and the execution was marked **FAILED** with the
  explanation "the request never took effect and no money moved". The
  order existed the whole time — `order_TXzNSIyg5BQNV1`, matching
  `proposal_hash` and amount, visible in the same listing minutes later.
- **Why:** `find_order_by_correlation` reads `GET /v1/orders`, and a list
  endpoint is not read-your-writes consistent. The code treated an empty
  read as proof of absence. "I did not see it" and "it is not there" are
  different statements, and only the second one justifies closing a
  payment as failed.
- **Detected:** By running the failure drill against live test
  credentials and then querying Razorpay by hand, because the resolution
  did not match what the demo had just done. It would never have shown up
  against the simulator, which knows its own writes immediately.
- **Fixed:** `apps/api/execution_provider.py` now documents the
  constraint as `LIST_IS_NOT_READ_YOUR_WRITES` and pages the listing
  rather than assuming one page holds everything.
  `apps/api/execution_api.py` refuses to conclude `FAILED` from an empty
  read taken inside `ABSENCE_QUIET_PERIOD_SECONDS` of the attempt: it
  returns `202 ABSENCE_NOT_YET_CONCLUSIVE`, leaves the row exactly where
  it was, and tells the caller when to ask again. After the window,
  absence does resolve to `FAILED` — the guard delays the conclusion, it
  does not prevent it.
- **Test:** `tests/test_payment_state_and_reconciliation.py` —
  `test_absence_soon_after_the_attempt_is_not_treated_as_failure`,
  `test_absence_after_the_quiet_period_does_resolve_to_failed`, and
  `test_the_simulated_provider_is_authoritative_immediately` (the
  simulator knows its own writes, so the keyless demo must not wait for a
  consistency window that does not exist).

## 12. A 202 read as success — the UI told the buyer a payment had gone through

- **Problem:** The executor signals "the provider's outcome is unknown"
  by raising `HTTPException(202, ...)`. FastAPI renders that as
  `{"detail": {...}}` with a **2xx** status. The storefront checked
  `response.ok`, which is true for 202, then read `data.state`, which was
  undefined because the real state was nested under `detail`, and fell
  back to a default of `EXECUTED`. The single most important state in the
  system — *we do not know* — was displayed to the buyer as a completed
  purchase.
- **Why:** Two reasonable decisions that are wrong together: using 202 to
  mean "accepted, outcome pending", and letting a client distinguish
  outcomes by HTTP status. The backend was right and the front end could
  not tell.
- **Detected:** By running the fault path over HTTP rather than in-process
  and reading the raw response body, instead of trusting the pipeline
  rail that had lit up green.
- **Fixed:** `apps/api/discovery/api.py` now returns every checkout
  outcome — approval, gateway refusal, definitive failure, unknown — in
  one flat envelope where `ok` and `execution_state` are always
  top-level. The same flattening was applied to reconciliation, which has
  the same 202 case. The storefront and the cockpit both treat `ok` as
  the only thing that means success.
- **Test:** `tests/test_discovery_checkout_canonical.py::test_ambiguous_outcome_is_never_reportable_as_success`,
  which asserts the 202 body is `ok: false`, carries
  `execution_state: RECONCILIATION_REQUIRED` at the top level, is not
  nested under `detail`, and offers `retryable: false`.

## 13. An attack scenario that passed for the wrong reason

- **Problem:** `A8_CART_MUTATION` advertised itself as proving the
  approval binding's SKU-set check: "approval was for SKU A, user swaps
  to SKU B". It was blocked — by `R1_BUDGET`, because the substituted
  SKU cost more than the scenario's budget. The attack never reached the
  layer the scenario claimed to be testing, so the binding check had no
  passing evidence at all. A green 8/8 was hiding an untested control.
- **Why:** The scenario was written to be blocked, not to be blocked *by
  a particular thing*. Any refusal looked like a pass.
- **Detected:** Reading the `blocked_by` field in the lab output instead
  of the `safe` boolean.
- **Fixed:** `apps/api/attack.py` now swaps `BAT-001` for `PWR-001`,
  which costs exactly the same and sits in an equally permitted category,
  with a budget generous enough that R1–R12 legitimately **APPROVE** the
  swapped cart. Every field the binding checks matches except the SKU
  set, so `SKU_SET_MISMATCH` is the only thing left to refuse on.
- **Test:** `tests/gateway/test_attack_lab.py::test_each_scenario_is_blocked_by_the_layer_it_claims_to_test`
  pins the exact `blocked_by` string for all eight, and
  `test_cart_mutation_passes_the_gateway_before_the_binding_refuses_it`
  asserts the gateway approves first — if a future change makes the
  gateway reject A8, the test fails rather than quietly reverting to
  proving nothing.

## 14. Live retail discovery had been dead, and reported it as an empty market

- **Problem:** Product discovery queries Bing's RSS endpoint. That
  endpoint now returns a zero-byte body, and on other attempts a
  well-formed feed containing no items at all. Both were reported as
  simply "no results", so a dead dependency was indistinguishable from a
  market with nothing in it — and the pipeline's status still read
  `LIVE_SEARCH_SUCCESS` because a synthetic mock API had answered.
- **Why:** The status was derived from "did anything come back" rather
  than "did a retail source come back", and a provider that returned
  nothing was not asked why.
- **Fixed:** `apps/api/discovery/pipeline.py` distinguishes an empty body
  and a resultless feed (both reported as provider errors) from results
  that were filtered out by the retail whitelist (reported as a hit, with
  the off-domain and off-intent counts). Status is now derived from
  retail providers alone: `MOCK_SOURCES_ONLY` when only the synthetic
  APIs answered, `SEARCH_UNAVAILABLE` when a retail provider failed. The
  storefront surfaces that verbatim instead of showing an empty grid.
- **Not fixed:** the underlying dependency. Search-engine scraping is
  fragile by nature, and swapping in another scraper that works today
  would fail in front of a reviewer just as silently. SELLABLE can only
  ever sell what is in its own catalog, so external listings are
  advisory evidence; the honest behaviour is to say the evidence is
  missing, which it now does.
- **Test:** `tests/test_discovery_pipeline.py` —
  `test_a_broken_search_endpoint_is_not_reported_as_an_empty_market`,
  `test_a_resultless_feed_is_distinguished_from_a_filtered_one`,
  `test_results_filtered_out_by_the_whitelist_are_reported_as_such`.

## 15. A metric that was wrong by a factor of fifty

- **Problem:** `truth.json` reported 3,728 Python files and **1,301,955
  lines** of code. The generator excluded `.venv` and then counted a
  second virtualenv sitting at `venv/`.
- **Why:** The filter was a list of things to leave out. Anything nobody
  remembered to exclude joined the count.
- **Fixed:** `scripts/generate_truth.py` names the first-party source
  directories instead — `apps`, `tests`, `scripts`, `eval`,
  `external_buyer`, `mcp_server`, plus root-level `*.py` — and records
  that list in the evidence file as `counted_from`. The real figure is
  184 files and 26,568 lines. The stray `venv/` was deleted and both
  virtualenvs are now ignored.
- **Worth saying plainly:** a number that large was obviously wrong and I
  still shipped it for days. A metric only twice as large as it should be
  would not have been caught at all, which is why the fix is a definition
  rather than a bigger exclusion list.

---
*Every entry above is gated by something that runs: `pytest`,
`scripts/redteam.py`, `scripts/verify_readme.py`, `scripts/final_verify.py`,
`GET /gateway/proof`, `GET /policy`.*

