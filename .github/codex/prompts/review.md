You are reviewing a pull request to SELLABLE, a payment-safety layer for LLM shopping agents.

Read AGENTS.md first. Its invariants are the review checklist.

Review only the changes in this pull request (compare the PR head with its base branch), reading
surrounding code where you need it to judge a change.

Report, in this order:
1. Anything that weakens an AGENTS.md invariant or the money path: gateway purity, a model-fillable
   field that carries money, a second route to a payment API, approval binding or single use,
   execution state ordering, webhook verification, mandate custody, the audit chain.
2. Bugs: wrong logic, unhandled errors, encoding or path problems on Windows.
3. Changed behaviour without a test, especially a missing refusal-path test.
4. Docs that state a number not backed by docs/generated/truth.json.

For each finding: file and line, what can go wrong, the smallest fix. No style nits a linter would
catch. Keep it short. If you find nothing, reply with one line saying the change looks safe and why.
