# Certification baseline

Which payment-trace properties SELLABLE guarantees today, measured before any
certifier exists. Each test asserts the property a trace certifier should
provide; the ones the system does not yet hold are marked
`xfail(strict=True)`, so the suite stays green while a gap exists and goes red
when a change closes it.

```bash
pytest research/certification_baseline -v -rxX
```

The tests call the real route functions in `apps/api/tools.py` and
`apps/api/execution_api.py` on the simulated provider. They live outside
`tests/`, so `make ci`, the README test count and `docs/generated/truth.json`
are unaffected.

| Property | API path (`/tools`) |
|---|---|
| Replaying an executed authorization returns the same order | holds |
| A lost provider response is recovered without a second charge | holds |
| Cumulative spend in a mission stays within its budget | **no**: three Rs 1,499 orders execute under a Rs 3,000 mission |
| Revoking a mission stops payments it already approved | **no**: new proposals fail R8; an earlier approval still executes |
| Reconciliation only accepts the execution's own order | **no**: an identical basket's order is adopted, so an unpaid purchase is recorded as executed |
| An executed approval cannot pay again after a database restore | **no**: two provider orders for one approval (simulated provider) |
| The gateway's rate window survives a restart | **no**: `mission_state` is in process memory only |
| An approval records the policy version it passed | **no**: `bindings` has no policy-version column |
| The verifier cannot mint the user's mandates | **no**: HMAC mandates are checked with the signing key |
| A refused mandate does not burn a valid approval | **no**: the binding is consumed before mandates are checked |

The MCP server path (`mcp_server/`) re-checks cumulative spend and revocation
at execution; `test_mcp_path_rechecks_cumulative_spend_and_revocation` pins
that. Neither path records which policy a payment satisfied.
