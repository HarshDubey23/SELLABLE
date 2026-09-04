# RECONCILIATION — Blueprint vs Repo

Generated: 2026-08-29 · HEAD: a75209e · tracked files: 223

Method: full working tree + git ls-files + targeted grep + live pytest in a clean venv.
Every evidence cell is re-runnable — run the command, expect the stated result.

## Verdict

**The improvement blueprint's assumption of a mature codebase is TRUE.**
The gateway (R1–R11), 65-test suite, 600-line buyer agent, eval harness, MCP server,
and purity-proof endpoint exist and pass. Phases 1–2 are therefore VERIFY + HARDEN,
not build. The genuinely MISSING items are the v2 additions: protocol adapter layer,
R12/R13, conversational checkout UI, chaos page, external buyer, eval v2 arms, deploy
configs, and the submission kit. Phases 4–9 build those.

## Table 1 — Doc-referenced files (16 mandatory checks)

| # | Path | Status | Evidence (re-run to confirm) |
|---|------|--------|------------------------------|
| 1 | apps/api/gateway/engine.py | EXISTS | `grep -n "except ImportError" apps/api/gateway/engine.py` → 1 hit, line 93 (F-06; fix owned by Phase 3) |
| 2 | apps/api/gateway/registry.py | EXISTS | `.venv/bin/python -c "from apps.api.gateway.registry import rules_count; print(rules_count())"` → 11 |
| 3 | apps/api/manifest.py | EXISTS | `grep -n "acp_ap2_x402" apps/api/manifest.py` → 1 hit, line 22, value `"tracked; patterns (mandates, bounded offers) "` (F-01; Phase 4 rewrites) |
| 4 | apps/api/agent/buyer.py | EXISTS | `wc -l apps/api/agent/buyer.py` → 515 (blueprint claimed 600 — see day06 What broke); `grep -n "_deterministic_pick" apps/api/agent/buyer.py` → 4 hits (def + 3 call sites) |
| 5 | apps/api/negotiation/ | EXISTS | `ls apps/api/negotiation/` → 9 files: __init__.py, api.py, bounds.py, catalog_pricing.py, engine.py, llm.py, persist.py, strategies.py, types.py |
| 6 | mcp_server/server.py | EXISTS | present; stdlib JSON-RPC over stdio, read-only by design |
| 7 | eval/run.py | EXISTS | `grep -n "INJECTION_FAKE_PRICE" eval/run.py` → 3 hits, line 41 `INJECTION_FAKE_PRICE = 100`; simulated_ungated arm has no LLM (line 119 `_arm_simulated_ungated`, synthetic baseline note line 275) |
| 8 | eval/report.py | PARTIAL | renders md from results.json; `grep -c "llm_fooled_rate" eval/report.py` → 0 (v2 metrics missing → Phase 7) |
| 9 | scripts/redteam.py | EXISTS | 291-line adversarial CLI, 20 cases (all 20 PASS against the live server this session) |
| 10 | scripts/verify_numbers.py | EXISTS | present; `grep -c "verify_numbers" README.md` → 1 (README line 399 already links it: "## Numbers (derived, not claimed — run `python scripts/verify_numbers.py`)") — blueprint claimed 0; see day06 What broke |
| 11 | docs/ARCHITECTURE.md | EXISTS | lines 171–172: adapters "not yet implemented (documented Day-6 stretch goal)" (F-01 evidence) |
| 12 | docs/SECURITY_CLAIMS.md | PARTIAL | exists; `grep -c "Trust Boundary" docs/SECURITY_CLAIMS.md` → 0 (F-08 → Phase 3) |
| 13 | docs/WHAT_BROKE.md | EXISTS | 10 incidents; incident 2 = "Evaluation was rigged — `injections_blocked +=1` without verdict" (F-14 source) |
| 14 | docs/PITCH_SCRIPT.md | PARTIAL | v1 script; first minute is problem + architecture, no product moment (F-15 → Phase 9) |
| 15 | apps/api/requirements.txt | EXISTS (defective) | `grep -c "==" apps/api/requirements.txt` → 0 pins; dev tools mixed in under `# dev` (ruff, mypy, playwright) (F-07 → Phase 3) |
| 16 | docker-compose.yml | EXISTS | + apps/api/Dockerfile present; no deployed instance (F-04 → Phase 9) |

## Table 2 — v2 target components (MISSING today; phase that builds each)

| Component | Status | Built in |
|-----------|--------|----------|
| apps/api/protocols/ (ACP/AP2/x402 adapters) | MISSING | Phase 4 |
| Rule R12_PROTOCOL_SCOPE | MISSING | Phase 4 |
| Rule R13_WALLET_VELOCITY | MISSING (cut-line-able) | Phase 4 |
| Conversational checkout UI (GET /demo/checkout) | MISSING | Phase 5 |
| Chaos page (GET /demo/failures, 6 classes) | MISSING | Phase 5 |
| external_buyer/ (zero-import HTTP buyer) | MISSING | Phase 6 |
| Eval v2 behavioral arm + llm_fooled_rate / money_loss_rate | MISSING | Phase 7 |
| README restructure (growth-first, GIF, numbers strip, Known Open Holes) | MISSING | Phase 8 |
| render.yaml / fly.toml / live smoke / deploy runbook | MISSING | Phase 9 |
| Submission kit (video script v2, form answers, checklist) | MISSING | Phase 9 |

## Verified baseline (this session)

- `pytest -q` → 65 passed, 1 warning in 3.94s
- `ruff check apps/api/gateway/` → All checks passed!
- `mypy --strict apps/api/gateway/` → Success: no issues found in 8 source files
- Planted injections: I1–I8 (eight) — proven by `apps/api/products.py` `INJECTION_INDEX`
  which enumerates exactly 8 entries (I1–I7 embedded in product descriptions as
  hand-authored payloads, I8 at proposal time). Note: the raw grep
  `grep -c "INJECTION\|injection" apps/api/products.py` returns 4 string hits, not ≥ 8 —
  the payloads don't all contain the word "injection"; the index is the source of truth.
- apps/api/mandates/mandates.py already implements IntentMandate + CartMandate (INV-3,
  the AP2 pattern, native) with scripts/mandate.py and USER_MANDATE_KEY — Phase 4's
  AP2 adapter extends this; it does not start from zero.

## Discovered gap (NOT in the blueprint's audit — found during reconciliation)

apps/api/mandates/mandates.py docstring cites tests/invariants/test_agent_custody.py,
which does not exist in the tree → Phase 2 must create it.
