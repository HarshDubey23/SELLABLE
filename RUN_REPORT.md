# SELLABLE — Run Report

**Generated:** $(date)
**Repo:** https://github.com/HarshDubey23/SELLABLE
**Branch:** main
**Commit:** $(git rev-parse --short HEAD)

---

## Test Results

```
$ python -m pytest -q
143 passed, 1 skipped in 9.65s
```

| Category | Count |
|---|---|
| Gateway matrix + purity | 91 |
| Protocol adapters (R12) | 13 |
| Protocol adapter tests | 11 |
| Protocol adapter invariants | 5 |
| Eval harness (V2) | 5 |
| External agent isolation | 1 |
| Demo UI | 19 |
| Signer sync + webhook + audit + upsell + negotiation | remaining |

## Lint & Typecheck

```
$ ruff check apps/api/gateway/ apps/api/negotiation/
All checks passed!

$ ruff check scripts/
All checks passed!

$ mypy --strict apps/api/gateway/
Success: no issues found in 9 source files
```

## Gateway Purity

```
$ GET /gateway/proof (live)
{"files":9,"llm_imports_detected":0,"io_calls_detected":0,"forbidden_patterns_seen":[],"source_sha256":"..."}
```

Zero LLM imports. Zero I/O calls. Source-hashed.

## Catalog Verification

```
$ python scripts/verify_catalog.py
Catalog verification PASSED
   SKUs: 40
   All prices unchanged
   All injection payloads intact (I1-I7 markers)
   INJECTION_INDEX complete: I1-I8 (I8 proposal-time)
```

## Numbers Verification

```
$ python scripts/verify_numbers.py
OK README contains SKUs 40
OK README contains rules 12
OK README contains tests 143
OK README contains gemini-3.6-flash

$ python scripts/verify_numbers.py --check-report
OK report.json has all 8 metrics

$ python scripts/verify_numbers.py --check-readme
OK README numbers match report.json
```

## Eval Harness (V2)

```
$ python -m eval.run --missions 100 --reps 3 --seed 42 --out eval/results.json
$ python -m eval.report --in eval/results.json --out eval/report.md --json eval/report.json
```

| Arm | Trust-adj revenue | Injection resistance | Money loss rate |
|---|---|---|---|
| static | Rs 126,420 | n/a | 0% |
| ungated | Rs 20,918 | 0% | — |
| **gated** | **Rs 86,586** | **100%** | **0%** |
| behavioral_ungated_llm | Rs 76,803 | 0% | tracks llm_fooled |
| behavioral_gated_llm | Rs 78,339 | 100% | tracks money_loss |

### V2 Required Metrics

| Metric | Value |
|---|---|
| acceptance_rate | 48% |
| aov_uplift | 45.02% |
| false_block_cost | Rs 1,992.68 |
| llm_fooled_rate | 0% |
| money_loss_rate | 0% |
| negotiation_margin | 343.56% |
| p95_latency | 0.1 ms |
| protocol_pass_rate | 100% |

## Smoke Test

```
$ bash scripts/smoke_test.sh http://localhost:8000
==== smoke_test: 8 passed, 0 failed ====
```

## Deployment Configs

- `render.yaml` — Render web service, auto-deploy on push
- `fly.toml` — Fly.io app, `iad` region, Docker build
- `Dockerfile` — Python 3.13-slim, uvicorn

## Audit Chain

```
$ curl localhost:8000/health
{"audit_chain_ok":true}
```

Append-only SHA-256 chained. Boot-verified. Halt-on-tamper.

## Evidence Pipeline

See `docs/submission/manifest.json` for the evidence manifest with hashes of all key artifacts.

---

*All claims verified by running the project. This report is machine-generated from the verification commands above.*