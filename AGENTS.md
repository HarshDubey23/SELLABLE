# AGENTS.md

Instructions for coding agents (Codex, Claude Code, Copilot and others) and
for automated pull request review on this repository. Humans: see
[CONTRIBUTING.md](CONTRIBUTING.md).

## What this project is

SELLABLE lets an LLM agent shop without being able to move money on its own.
The agent proposes `{sku, qty}`; deterministic code prices it from the
server-side catalog, gates it through rules R1-R12, binds a single-use
approval to the exact basket, and only then executes. The safety claims are
structural, and the tests check them by parsing the source.

## Commands

```bash
make install        # runtime + dev dependencies
make test           # full pytest suite
make ci             # everything CI runs, in CI's order. Run this before pushing.
pytest -q tests/mcp # the MCP server alone (standard library only, fast)
make truth          # regenerate docs/generated/truth.json after changing tests or rules
```

Python 3.10+. CI runs Ubuntu and Windows on 3.10 and 3.12, so keep paths,
encodings (always `encoding="utf-8"`) and subprocess calls portable.

## Invariants. A change that breaks one of these is wrong, whatever else it fixes.

1. **The gateway is pure.** `apps/api/gateway/` imports no LLM client, no
   network library, does no file I/O and reads no clock it was not given.
   Enforced by `tests/invariants/test_gateway_purity.py`, `ruff` and
   `mypy --strict` on that package.
2. **The model never states money.** No tool, schema or intent the model can
   fill may carry an amount, price, total, currency or payee. Prices come
   from `apps/api/products.py`. Merchant intents (`apps/api/market/intents.py`)
   have no amount field, by design.
3. **One door to money.** `apps/api/razorpay_client.py` is the only module that
   talks to a payment API. `apps/api/agent/` holds no money authority and must
   not import executors; recovery lives in `apps/api/recovery/`, not under
   `agent/`.
4. **Approvals are single use and bound.** The binding hashes mission, cart,
   quote, amount, currency and SKU set. Nothing may be recomputed or widened
   between approval and execution.
5. **Unknown is not failure.** `REMOTE_ATTEMPTED` is written before dispatch;
   a timeout goes to `RECONCILIATION_REQUIRED`, never to a guessed outcome.
6. **Fail closed.** A rule that cannot decide rejects.
7. **Numbers in docs come from evidence.** Every figure in `README.md` comes
   from `docs/generated/truth.json` (`scripts/verify_readme.py` enforces it).
   Never edit `truth.json` by hand, and never add unfalsifiable security
   claims; `tests/test_docs_do_not_drift.py` rejects them.
8. **Protocol adapters translate, they never decide.** ACP/AP2/UAP adapters
   hand requests to the canonical submit path.

## Style

- Small, direct changes. Reuse what exists before adding a module or a dependency.
- The MCP server (`mcp_server/`) is standard library only. Keep it that way.
- Tests for money-path changes assert the refusal path, not just the happy path.
- Commit messages: imperative, specific ("Reject a binding whose SKU set changed").

## Reviewing a pull request

Lead with anything that touches the invariants above, the money path
(`gateway/`, `approval.py`, `execution*.py`, `razorpay_client.py`,
`webhook/`, `mandates/`, `mcp_server/store.py`) or the audit chain. For each
finding give the file and line, what can go wrong, and the smallest fix.
Then missing tests for changed behaviour. Skip style nits that `ruff` would
catch. If nothing is wrong, say so in one line.
