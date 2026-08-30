# Day 6 — Reconciliation, baseline certification, v2 scaffold

Date: 2026-08-29

## Goal

Compressed sprint to the 5 Sep Razorpay Buildathon deadline. Today: reconcile the
improvement blueprint against the live repo, certify the 65-test baseline, scaffold
every directory the v2 architecture needs, and verify CI tells the truth — so Phases
1–9 never operate on an unverified base.

## Built

- **RECONCILIATION.md** — 16-row doc-referenced file audit + v2 target map, every cell re-runnable.
- **apps/api/protocols/__init__.py** — Protocol Adapter Layer v0 scaffold (docstring only; Phase 4 fills it).
- **external_buyer/, docs/submission/, docs/assets/** — scaffolds with .gitkeep (Phases 6/8/9 fill them).

## Verified

```
$ git ls-files | wc -l        (git ls-files | Measure-Object -Line)
223

$ pytest -q
65 passed, 1 warning in 3.94s

$ ruff check apps/api/gateway/
All checks passed!

$ mypy --strict apps/api/gateway/
Success: no issues found in 8 source files

$ make test                   (make not on Windows PATH — ran .venv\Scripts\python.exe -m pytest -q)
65 passed, 1 warning in 4.41s

$ make audit-verify           (ran python -m apps.api.audit.verify)
FAILED — No module named apps.api.audit.verify
(Makefile defect: apps/api/audit/ contains only chain.py, timeline.py,
 __init__.py — verify.py does not exist. Recorded, not fixed — scope.)

$ make redteam                (ran python scripts/redteam.py)
[redteam] base=http://localhost:8000
PASS 1 invalid signature ... PASS 20 wrong cart hash  403
20/20 PASS — "[redteam] done", exit 0
(live server was already running on localhost:8000)
```

CI (.github/workflows/ci.yml) read and confirmed:
- installs from apps/api/requirements.txt → **yes** (line 10)
- runs pytest → **yes** (line 12, `python -m pytest -q`)
- ruff on gateway → **yes** (line 13, `ruff check apps/api/gateway/`)
- mypy strict on gateway → **yes** (line 14, `mypy --strict apps/api/gateway/`)

F-06 confirmed still present (intentionally — Phase 3 owns the fix):
`grep -n "except ImportError" apps/api/gateway/engine.py` → exactly 1 hit, line 93

## What broke

- Blueprint numeric drift found during reconciliation (statuses unchanged, evidence
  corrected in RECONCILIATION.md):
  - `apps/api/agent/buyer.py` is **515 lines**, not 600 as claimed.
  - README **already links** `scripts/verify_numbers.py` (1 hit, line 399) — the
    blueprint claimed grep count 0 / "not linked" (F-09 is weaker than stated).
  - `grep -c "INJECTION\|injection" apps/api/products.py` → 4, not ≥ 8; the real
    proof of I1–I8 is `INJECTION_INDEX` (exactly 8 entries) + embedded I1–I7 payloads.
- `make audit-verify` is **broken**: it runs `python -m apps.api.audit.verify` but
  `apps/api/audit/verify.py` does not exist (No module named apps.api.audit.verify).
  Recorded honestly; not fixed (Phase 0 scope = audit + scaffold only).
- `make` itself is not on this Windows machine's PATH; all three Makefile targets
  were executed via their underlying commands with `.venv\Scripts\python.exe`.
- Environment note: venv layout is `.venv\Scripts\` (Windows), not `.venv/bin/`.

## Learned

The blueprint's structural map is accurate (all 16 paths exist, 65 tests green,
11 rules, purity intact) but its specific numbers have drifted from the tree, and
the audit surfaced two live defects it missed entirely: a Makefile target pointing
at a nonexistent module and a custody-invariant test that the mandates docstring
promises but the repo never delivered.
