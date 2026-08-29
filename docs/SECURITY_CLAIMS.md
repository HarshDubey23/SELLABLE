# Security Claims — Evidence Map

Every claim below is defensible via code, test, or live demo. No marketing language without proof.

| Claim | Evidence | Test | Live Demo | Limitation |
|-------|----------|------|-----------|------------|
| No APPROVE → no order | `apps/api/tools.py:376` `if approved_bindings.get(seq)!=hash: 403` | `tests/test_gateway_money.py::test_no_approve_no_order` | `curl POST /tools/create_order` without seq → 422/403 (`scripts/redteam.py:8,9`) | — |
| Client cannot set price | `tools.py:254` `price_paise=CATALOG[sku]["price_paise"]` | `tests/test_gateway_matrix.py::test_r3_price_drift` | `POST /demo/injection/I5` fake 0 → `R3_PRICE_DRIFT` (`docs/log/day05/endpoints/injection_I5.json`) | — |
| Invalid mandate → no order | `tools.py:397` `verify_intent`+`verify_cart` | `tests/test_mandate.py` | `redteam 18` missing mandate → 422 | Prototype wallet is simulated locally |
| Invalid webhook sig → reject | `webhook/receiver.py:102` HMAC raw body | `tests/test_webhook.py` | `redteam 15` forged → 400 | Requires `RAZORPAY_WEBHOOK_SECRET` set; empty → 503 fail-closed |
| Audit tamper → money path halts | `audit/chain.py:verify()` → `gateway/engine.py:51` `CHAIN_TAMPER` | `tests/test_audit_tamper.py` | `GET /audit` `verified:true`, flip byte → `false` | Tamper-evident, not tamper-proof; admin with DB+keys can rewrite chain (documented) |
| Zero LLM inside gateway | `apps/api/gateway/proof.py` scans 8 files, `llm_imports_detected:0` | `tests/invariants/test_gateway_purity.py` | `GET /gateway/proof` live `files:8, llm:0, sha:b275ea5a...` | Negotiation `llm.py` is allowed (only rationales, not prices) |
| Replay protection (proposal) | `tools.py:354` `X-Idempotency-Key` + `idempotency_seen` | `tests/test_idempotency.py` | `redteam 13` duplicate key → `duplicate:true` | — |
| Replay protection (webhook) | `webhook/receiver.py:119` `processed_event_ids` after DB persist | `tests/test_webhook_replay.py` | `redteam 12` duplicate event → ack 200 duplicate:true | — |
| Rate limit 5/60s | `gateway/rules.py:132` `R6_RATE_LIMIT` | `tests/test_rate_limit.py` | `redteam 14` burst 6 → `R6_RATE_LIMIT` | In-memory per process; distributed limit needs Redis in prod |
| Category spoof blocked | `rules.py:84` `R5_SCOPE` reads `CATALOG[sku].category` | `tests/test_scope.py` | `demo/injection/I8` relabel `books` → `R5_SCOPE` (`injection_I8.json`) | — |
| Negotiation bounded | `negotiation/bounds.py:clamp_offer` + `R11` | `tests/test_negotiation.py` 9 cases | `POST /negotiation/start` floor 119900 ceiling 149900 → final `135464` bounded | Negotiation is opt-in; normal flow bypasses it |
| Unicode obfuscation blocked | `products.py:KIT-001` fullwidth `ＢＵＹ` | `tests/test_injection.py` | `demo/injection/I6` → `REJECT R1_BUDGET` (price from catalog, not prose) | — |
| Expired mission rejected | `rules.py:23` `R10_EXPIRY` | `tests/test_expiry.py` | `redteam 2` expired → `R10_EXPIRY` | Clock skew not handled (NTP assumed) |
| Forged signature rejected | `rules.py:12` `R9_SIGNATURE` HMAC | `tests/test_signature.py` | `redteam 1` bad sig → `R9_SIGNATURE` | — |

*All above verified via `make test` (65), `scripts/redteam.py` (20), and live `GET /gateway/proof`.*
