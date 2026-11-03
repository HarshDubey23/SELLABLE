# Security policy

SELLABLE's whole purpose is to stop an AI agent from moving money it
shouldn't. A bypass of that is the most valuable bug report this project can
get, and it should be reported privately.

## What counts

Anything that lets an agent, a prompt-injected listing, a merchant model or an
unauthenticated caller:

- cause a payment the signed mission or user mandate does not allow (amount,
  payee, category, budget, expiry, revocation);
- reuse, widen or forge an approval, mission or mandate;
- make the gateway's verdict depend on attacker-controlled input it should not
  read;
- execute a payment twice, or record a payment that did not happen;
- alter the audit chain without `verify_audit_log` / boot verification noticing.

Limitations already documented in the README (in-process demo issuer,
single-node SQLite concurrency, the catalog as trust root, rate-limited
browser routes) are known; reports that go beyond them are still welcome.

## How to report

Use GitHub's private reporting:
[**Report a vulnerability**](https://github.com/HarshDubey23/SELLABLE/security/advisories/new).
If that is not available to you, email **harshimp123455@gmail.com** with
"SELLABLE security" in the subject.

Please include the version or commit, the steps or a script that reproduces
it, and what moved (or could move) that should not have. Do not test against
other people's deployments, and use only the simulated provider or Razorpay
test mode.

## What to expect

- Acknowledgement within 3 days.
- An assessment and a planned fix date within 10 days.
- Credit in the release notes and the advisory, unless you prefer otherwise.

## Supported versions

Fixes go to the latest release on PyPI (`sellable-mcp`) and to `main`.
