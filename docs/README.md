# Documentation

Four things a reviewer usually wants, in the order they usually want them.

| | |
|---|---|
| [`WHAT_BROKE.md`](WHAT_BROKE.md) | Fifteen real failures from building this, including the two that would have cost someone money. Start here if you want to know whether the engineering is honest. |
| [`ARCHITECTURE.md`](ARCHITECTURE.md) | How the pieces fit, and which of them can reach a payment API. |
| [`architecture/security-claims.md`](architecture/security-claims.md) | Every security claim with the file and the test that backs it. `tests/test_security_claims_doc.py` parses this table and fails the build when a path in it stops existing. |
| [`generated/truth.json`](generated/truth.json) | Every number in the README, produced by `scripts/generate_truth.py` running the thing it measures. Nothing in the README is typed by hand. |

## The rest

| | |
|---|---|
| `architecture/` | Diagrams and the deeper notes: the trust boundary, the execution lifecycle, the money-safety argument, and the Mermaid sources they render from. |
| `engineering/` | Failure recovery in detail, and where SELLABLE sits relative to the agent-payment protocols. |
| `submission/` | Buildathon form answers, the pitch script, and the deploy runbook. |
| `archive/` | The build log, and every document a later one replaced. Kept because the history is part of the evidence, separated because a reviewer should never have to work out which generation they are reading. |

Nothing under `archive/` is current. If a document there disagrees with one
above it, the one above it is right.
