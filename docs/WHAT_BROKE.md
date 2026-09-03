# WHAT BROKE — and how I got out

Real failures from building SELLABLE, not sanitized.

## 1. Gemini model 404 — `gemini-2.0-flash is no longer available`
- **Problem:** Every LLM call returned `404 NOT_FOUND` — buyer agent fell back to deterministic proposer, negotiation rationales were `Buyer offers Rs...` (fallback), not real Gemini.
- **Why:** Google retired `2.0-flash`/`2.5-flash` for new users; our `.env.example` still listed them. Fallback chain only caught `429`, not `404`.
- **Detected:** `client.models.list()` showed `google/gemini-1.5-flash` as current; direct `ask()` with fallback showed `404` then fallback `503` then success on `3.6`.
- **Fixed:** `apps/api/llm/gemini.py:57` now catches `404`/`NOT_FOUND` as fallback trigger, `.env.example:7` updated to `google/gemini-1.5-flash`, fallback `gemini-3.5-flash`. Verified live: `ask()` returns `model=google/gemini-1.5-flash latency 3939ms`.
- **Test:** `scripts/redteam.py` includes LLM-unavailable case; `pytest -q` still 65 pass via fallback path.

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

---
*All above now have tests/gating: `pytest`, `redteam.py`, `verify_numbers.py`, `GET /gateway/proof`, `GET /policy`.*
