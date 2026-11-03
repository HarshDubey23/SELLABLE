# Contributing to SELLABLE

Thanks for helping. SELLABLE is a safety layer that sits between an AI agent
and money, so the bar for changes to the money path is high and the bar for
everything else is low. Docs fixes, new tests, MCP client setup notes,
examples for other agent frameworks and bug reports are all welcome.

## Start here

- Issues labelled [`good first issue`](https://github.com/HarshDubey23/SELLABLE/labels/good%20first%20issue)
  are scoped to one area and avoid the money path.
- Found a way to make the agent move money it shouldn't? That is a security
  issue: follow [SECURITY.md](SECURITY.md) instead of opening a public issue.
- For anything bigger than a bug fix, open an issue first so we can agree on
  the approach before you spend time on it.

## Set up

```bash
git clone https://github.com/HarshDubey23/SELLABLE.git
cd SELLABLE
python -m venv .venv && source .venv/bin/activate   # Windows: .venv\Scripts\activate
make install
make test
```

`python run.py` boots the full app with no keys at all (simulated payments,
scripted merchants). The MCP server alone needs nothing beyond the standard
library: `pytest -q tests/mcp`.

## Before you open a pull request

1. `make ci` passes. It runs what CI runs, in the same order.
2. New behaviour has a test. For anything near money, test the refusal path
   as well as the happy path.
3. If you changed tests, rules or the catalog, run `make truth` so the README's
   numbers still match `docs/generated/truth.json`. Never edit that file by hand.
4. Read the invariants in [AGENTS.md](AGENTS.md). A change that breaks one of
   them will not be merged, however useful it is otherwise.

Keep pull requests small and focused; one change per PR is easiest to review.
Every PR gets an automated review comment plus a human review.

## Areas that need extra care

`apps/api/gateway/`, `approval.py`, `execution*.py`, `razorpay_client.py`,
`webhook/`, `mandates/`, `audit/` and `mcp_server/store.py`. Changes here need
a clear explanation of why the change is safe, and tests that would fail if it
were not.

## Code of conduct

Everyone taking part agrees to the [Code of Conduct](CODE_OF_CONDUCT.md).

## License

By contributing you agree that your contributions are licensed under the
[MIT License](LICENSE).
