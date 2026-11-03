## What and why

<!-- One or two sentences. Link the issue: Fixes #123 -->

## How it was tested

<!-- Commands you ran and what they showed. `make ci` covers what CI runs. -->

## Checklist

- [ ] `make ci` passes locally
- [ ] New behaviour has a test (for money-path changes, the refusal path too)
- [ ] No AGENTS.md invariant is weakened (gateway purity, no model-fillable money fields, one door to payments, single-use bound approvals)
- [ ] If tests, rules or the catalog changed: `make truth` was run and `docs/generated/truth.json` is committed
- [ ] CHANGELOG.md has a line under `[Unreleased]` for user-visible changes
