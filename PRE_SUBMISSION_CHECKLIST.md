# SELLABLE — Pre-Submission Checklist

## Judges will verify each item. Run the commands before submitting.

### 1. Tests pass
```bash
$ python -m pytest -q
# Expected: 115 passed, 4 skipped
```

### 2. Lint and typecheck
```bash
$ ruff check .
# Expected: All checks passed!

$ mypy --strict apps/api/gateway/
# Expected: Success: no issues found in 9 source files
```

### 3. Catalog verification
```bash
$ python scripts/verify_catalog.py
# Expected: Catalog verification PASSED
```

### 4. Numbers verification
```bash
$ python scripts/verify_numbers.py
# Expected: OK README contains SKUs 40, rules 12, tests 115...

$ python scripts/verify_numbers.py --check-report
# Expected: OK report.json has all 8 metrics

$ python scripts/verify_numbers.py --check-readme
# Expected: OK README numbers match report.json
```

### 5. Eval harness (generates eval/report.json)
```bash
$ python -m eval.run --missions 100 --reps 3 --seed 42 --out eval/results.json
$ python -m eval.report --in eval/results.json --out eval/report.md --json eval/report.json
# Expected: gated money_loss_rate == 0.0, protocol_pass_rate == 1.0
```

### 6. Smoke test (requires running server)
```bash
$ uvicorn apps.api.main:app --port 8000 &
$ bash scripts/smoke_test.sh http://localhost:8000
# Expected: 8 passed, 0 failed
```

### 7. Gateway proof (live endpoint)
```bash
$ curl localhost:8000/gateway/proof
# Expected: llm_imports_detected: 0, io_calls_detected: 0
```

### 8. Audit chain verified
```bash
$ curl localhost:8000/health
# Expected: audit_chain_ok: true
```

### 9. Submission files present
- [x] `render.yaml`
- [x] `fly.toml`
- [x] `Dockerfile`
- [x] `scripts/smoke_test.sh`
- [x] `docs/submission/DEPLOY_RUNBOOK.md`
- [x] `PITCH_VIDEO_SCRIPT.md`
- [x] `FORM_ANSWERS.md`
- [x] `PRE_SUBMISSION_CHECKLIST.md`
- [x] `RUN_REPORT.md`
- [x] `docs/submission/manifest.json`
- [x] `scripts/render_readme_numbers.py`

### 10. No secrets committed
```bash
$ git grep -i "rzp_test_\|sk-" -- '*.py' '*.md' '*.yaml' '*.toml' '*.json' 2>/dev/null
# Expected: no output
```

### 11. Commit history clean
```bash
$ git log --oneline -10
# Expected: phase commits visible
```

---

## Final step

After all checks pass, tag the submission:
```bash
$ git tag -a v1.0-submission -m "SELLABLE submission — Razorpay AI Buildathon Track 01"
$ git push origin v1.0-submission
```
