# Certification baseline

Which payment-trace properties SELLABLE guarantees, each asserted as the
property a trace certifier should provide. The tests call the real route
functions in `apps/api/tools.py` and `apps/api/execution_api.py` on the
simulated provider, and live outside `tests/`, so `make ci`, the README test
count and `docs/generated/truth.json` are unaffected.

```bash
pytest research/certification_baseline -v -rxX
```

The original audit is preserved on the `certification-baseline` branch
(commit 2429725), where the 8 gaps are marked `xfail(strict=True)` and the run gives 3 passed, 8 xfailed. On the
`hardening` branch all 8 were fixed as ordinary engineering (no certifier),
the markers removed, and all 11 pass. Fixes, severity and what remains
trusted: [`research/hardening/REPORT.md`](../hardening/REPORT.md).

| Property | Baseline (commit 2429725) | Hardened |
|---|---|---|
| Replaying an executed authorization returns the same order | holds | holds |
| A lost provider response is recovered without a second charge | holds | holds |
| Cumulative spend in a mission stays within its budget | no: three Rs 1,499 orders execute under a Rs 3,000 mission | holds |
| Revoking a mission stops payments it already approved | no: no revoke route; an earlier approval still executes | holds |
| Reconciliation accepts only the execution's own order | no: an identical basket's order is adopted, so an unpaid purchase is recorded as executed | holds |
| An executed approval cannot pay again after a database restore | no: two provider orders for one approval (simulated provider) | holds, by checking the provider before dispatch |
| The gateway's rate window survives a restart | no: in process memory only | holds |
| An approval records the policy it passed | no: no policy field stored | holds (policy digest) |
| The verifier cannot mint the user's mandates | no: HMAC checked with the signing key | holds in user-held Ed25519 mode; default is still HMAC |
| A refused mandate does not burn a valid approval | no: consumed before mandates were checked | holds |

The MCP server path (`mcp_server/`) already re-checked cumulative spend and
revocation at execution at the baseline;
`test_mcp_path_rechecks_cumulative_spend_and_revocation` pins that.
