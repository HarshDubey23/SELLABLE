# Security claims, and what backs each one

Every row names a file that exists and a test that runs. The table is
itself checked: `tests/test_security_claims_doc.py` parses this document,
resolves every path in the Code and Test columns, and fails the build if
one of them stops existing. Documentation that can silently rot is worse
than no documentation, because a reviewer who finds one dead reference
stops trusting the rest.

## Claims

| Claim | Code | Test |
|---|---|---|
| An agent cannot set a price — every price is overwritten from the catalog | `apps/api/tools.py` | `tests/gateway/test_matrix.py` |
| A claimed price that differs from the catalog is rejected at ±0 paise | `apps/api/gateway/rules.py` | `tests/gateway/test_matrix.py` |
| A forged or absent mission signature is rejected (fail-closed) | `apps/api/gateway/rules.py` | `tests/gateway/test_r9_signature.py` |
| An expired mission is rejected | `apps/api/gateway/rules.py` | `tests/gateway/test_r10_expiry.py` |
| A proposal over the effective budget is rejected | `apps/api/gateway/rules.py` | `tests/gateway/test_r1_budget.py` |
| A proposal outside the mission's category scope is rejected | `apps/api/gateway/rules.py` | `tests/gateway/test_matrix.py` |
| The gateway makes no LLM call, no network call and no file read | `apps/api/gateway/` | `tests/invariants/test_gateway_purity.py` |
| The gateway is deterministic: same inputs, same verdict and hash | `apps/api/gateway/engine.py` | `tests/invariants/test_gateway_purity.py` |
| A missing input is a REJECT, never a pass | `apps/api/gateway/engine.py` | `tests/invariants/test_gateway_purity.py` |
| A tampered audit chain halts the money path | `apps/api/audit/chain.py` | `tests/test_audit_chain_true_tamper.py` |
| No APPROVE binding means no order and no provider call | `apps/api/tools.py` | `tests/test_no_approve_no_money.py` |
| Changing **any** bound field breaks authorization | `apps/api/approval.py` | `tests/gateway/test_binding_field_matrix.py` |
| A binding is single-use, atomically | `apps/api/approval.py` | `tests/gateway/test_binding_field_matrix.py` |
| A failed binding check does not burn the authorization | `apps/api/approval.py` | `tests/gateway/test_binding_field_matrix.py` |
| Concurrent callers cannot both spend one authorization | `apps/api/execution.py` | `tests/concurrency/test_concurrency_100.py` |
| Concurrent create_order produces exactly one order | `apps/api/tools.py` | `tests/execution/test_execution_e2e.py` |
| A user mandate is required before any order exists | `apps/api/mandates/mandates.py` | `tests/test_mandates.py` |
| The buyer agent never reads a signing key and never signs | `apps/api/agent/` | `tests/invariants/test_agent_custody.py` |
| The buyer agent cannot reach the money boundary directly | `apps/api/agent/` | `tests/invariants/test_agent_custody.py` |
| Only one module talks to a money API | `apps/api/razorpay_client.py` | `tests/test_architecture_guard.py` |
| Protocol adapters translate and never decide | `apps/api/protocols/` | `tests/invariants/test_protocol_adapter_invariants.py` |
| A webhook signature is verified against the raw body before parsing | `apps/api/webhook/receiver.py` | `tests/test_webhook.py` |
| A duplicate webhook event is a no-op | `apps/api/webhook/receiver.py` | `tests/test_webhook.py` |
| A crash between webhook persist and audit leaves the event replayable | `apps/api/webhook/receiver.py` | `tests/test_webhook_crash_recovery.py` |
| An ambiguous provider outcome never becomes success or failure by itself | `apps/api/execution.py` | `tests/execution/test_execution_state_machine.py` |
| A crash mid-payment is recovered as unknown, not lost | `apps/api/execution.py` | `tests/execution/test_execution_state_machine.py` |
| Reconciliation resolves against authoritative remote state, both ways | `apps/api/execution_api.py` | `tests/execution/test_execution_e2e.py` |
| Retrying an ambiguous outcome is refused | `apps/api/tools.py` | `tests/execution/test_execution_e2e.py` |
| A replayed authorization returns the original order, not a second one | `apps/api/execution.py` | `tests/execution/test_execution_e2e.py` |
| Placeholder credentials are not treated as configured | `apps/api/config.py` | `tests/execution/test_execution_e2e.py` |
| Fault injection is refused when a real provider is configured | `apps/api/execution_provider.py` | `tests/execution/test_execution_e2e.py` |
| A failed search is reported as a failed search | `apps/api/discovery/pipeline.py` | `tests/test_discovery_pipeline.py` |
| An FX-converted price is never reported as verified | `apps/api/discovery/pipeline.py` | `tests/test_discovery_pipeline.py` |
| Mock-source data is excluded from market comparison | `apps/api/discovery/pipeline.py` | `tests/test_discovery_pipeline.py` |
| The storefront checkout uses the canonical executor, not a shortcut | `apps/api/discovery/api.py` | `tests/test_discovery_checkout_canonical.py` |
| Mutating endpoints require the API key | `apps/api/deps.py` | `tests/test_authz.py` |
| Adversarial scenarios reach the money boundary zero times | `apps/api/attack.py` | `tests/gateway/test_attack_lab.py` |

## What is deliberately not claimed

**"Tamper-proof."** The audit chain is tamper-*evident*. Someone with
write access to the database and the keys can rewrite it. What they
cannot do is rewrite it without `verify_strict()` noticing at boot, at
which point the gateway rejects everything with `CHAIN_TAMPER`.

**"The AI cannot be fooled."** It can be, easily. The claim is that being
fooled costs nothing, because nothing the model says is load-bearing for
money.

**"Custody everywhere."** The browser demo path signs in-process via
`apps/api/issuer.py` — integrity without custody, disclosed in every
response as `authorization_issued_by`.

**"Distributed-safe."** Single-use consumption and the execution dispatch
claim are conditional `UPDATE`s against one SQLite file. Correct for one
process; a multi-node deployment needs the same guards at the database
layer.

**Rate limiting is per-process.** `R6_RATE_LIMIT` counts in memory. A
distributed deployment needs shared state for it to mean anything.

**Clock skew is not handled.** `R10_EXPIRY` trusts the system clock.
