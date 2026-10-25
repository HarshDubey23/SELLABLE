# Hardening report: the eight baseline findings

The certification baseline (tag `baseline-2429725`, folder
`research/certification_baseline/`) found that 8 of 10 payment-trace
properties did not hold on SELLABLE's `/tools` API path. This branch
(`hardening`) fixes them as ordinary engineering, **without** a trace
certifier, so that a later certifier can be measured against a hardened
system rather than against bugs.

The original evidence is not rewritten: `git checkout baseline-2429725`
and `pytest research/certification_baseline -v -rxX` still gives 3 passed,
8 xfailed.

## Results

| | Baseline (`baseline-2429725`) | Hardened (`hardening`) |
|---|---|---|
| Baseline properties holding (`research/certification_baseline`) | 2 of 10 on the API path (+1 MCP test) | 10 of 10 (+1 MCP test) |
| New regression tests (`tests/hardening`) | none | 13 passed |
| Existing tests runnable without FastAPI's TestClient | 360 passed, 1 skipped | 360 passed, 1 skipped (same set) |
| Full suite (578 tests incl. TestClient) | passes in CI | **see CI on the `hardening` branch** |

The one environment failure in both columns
(`test_the_chaos_safety_check_refuses_when_it_cannot_prove_test_mode`) comes
from the audit environment lacking FastAPI, not from the code. Every new
test was run three times with the same result.

## Findings, classification and fixes

| # | Finding | Kind | Severity | Fix | Regression test |
|---|---|---|---|---|---|
| 1 | Cumulative spend: three Rs 1,499 orders executed under a Rs 3,000 mission | Missing guarantee | High | Binding records the mission's effective budget; the executor sums committed (non-failed) executions for the mission and checks it inside the `BEGIN IMMEDIATE` transaction that opens the execution row, with a non-consuming pre-check | `test_a_purchase_past_the_mission_budget_is_refused_without_burning_it`, `test_two_racing_purchases_cannot_both_take_the_last_of_the_budget` |
| 2 | An approval issued before revocation still executed | Missing feature and guarantee: the API path had no revocation at all (R8 read a set nothing wrote) and the executor never re-read mission state | Medium | Durable `mission_revocations`, `POST /tools/revoke_mission`, R8 reads it, the executor re-checks before consuming and inside the open transaction | `test_revocation_is_durable_and_stops_approvals_issued_before_it` |
| 3 | Reconciliation recorded a never-dispatched purchase as executed, using an identical basket's order | Confirmed bug (correctness): matching on proposal hash + amount, which two identical purchases share | High | The execution id rides in the provider order's notes; reconciliation accepts only an order carrying it (legacy orders fall back to the unique quote id) | `test_reconciliation_does_not_adopt_another_purchases_order`, `test_reconciliation_still_recovers_its_own_lost_order`, `test_order_matching_uses_execution_identity_with_a_legacy_fallback` |
| 4 | After a database restore, a used approval paid again | Threat-model dependent: all single-use state lived inside the file a restore rolls back | Medium | Before dispatch, the executor asks the provider (outside the rollback boundary) for an order carrying this deterministic execution id and adopts it instead of paying again. If the provider cannot be read, nothing is dispatched and the row stays retryable | `test_a_restored_database_cannot_pay_an_executed_approval_twice`, `test_an_unreadable_provider_blocks_dispatch_and_the_retry_completes` |
| 5 | The R6 rate window reset on restart | Confirmed bug: in-process dict never reloaded | Low | `proposal_events` table read back into the (still pure) gateway | `test_the_rate_window_survives_a_restart` |
| 6 | Approvals recorded no policy version | Missing guarantee (lineage) | Low to medium | Each binding stores a SHA-256 digest over the policy version, rule registry and gateway source hash; a mismatch at execution refuses with `POLICY_CHANGED` without consuming | `test_a_policy_change_after_approval_invalidates_it_without_consuming`, `test_a_legacy_binding_without_lineage_or_budget_still_executes` |
| 7 | The verifier could mint the user's mandates | Architectural limitation: HMAC is symmetric | Medium to high under a server-compromise threat model | User-held Ed25519 mode: with `USER_MANDATE_PUBLIC_KEY` set the server holds only the public key and refuses HMAC mandates; `scripts/mandate.py keygen` and Ed25519 signing for the wallet | `test_user_held_keys_accept_the_wallet_and_refuse_the_server` |
| 8 | A refused mandate consumed a valid approval | Confirmed bug (ordering) | Medium (completion) | The binding is checked without consuming; mandates, revocation and budget run first; consumption is the last step before the execution row opens. A changed cart is still refused | `test_a_corrected_mandate_completes_but_a_changed_cart_needs_new_consent` |

None of the eight was a test-harness artifact. Findings 2 and 4 needed a
simulated trigger (marking a mission aborted; restoring the database file)
because the original system had no route for the first and the second is an
operational event, but the code paths exercised are the real ones.

## What is still trusted or open

- **Default custody is unchanged.** Without `USER_MANDATE_PUBLIC_KEY` the
  server still verifies HMAC mandates it could forge, and the browser demo's
  in-process issuer still signs both missions and mandates (disclosed in
  every response). Missions remain HMAC-signed with `MISSION_HMAC_KEY`.
- **The replay check trusts the provider's listing.** The live lookup pages
  a bounded number of recent orders, so an order older than that window, or
  one the provider dropped notes from, would be missed. It also adds one
  provider read per purchase.
- **Cumulative spend is enforced at execution, not in the gateway.** R1 still
  judges one proposal, so the gateway can approve a purchase the executor
  then refuses for budget. Folding committed spend into R1 as proof memory is
  the natural next step.
- **Single-node concurrency.** Atomicity relies on one SQLite file and an
  in-process lock plus `BEGIN IMMEDIATE`; a multi-node deployment needs the
  same guarantees from its database.
- **R6 allows 4 proposals a minute, not the documented 5.** The current
  proposal is counted before the check. Behaviour unchanged here, noted for a
  separate fix.
- **The catalog is still the trust root**, and the user's intent-mandate
  ceiling is still checked per order rather than cumulatively.

## Reproduce

```bash
git checkout baseline-2429725 && pytest research/certification_baseline -v -rxX   # 3 passed, 8 xfailed
git checkout hardening && pytest research/certification_baseline tests/hardening -v # 24 passed
make test                                                                         # full suite
```
