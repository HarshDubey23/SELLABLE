# SELLABLE — Comprehensive Cryptographic & Runtime Evidence Report

**Generated:** 2026-09-02 13:12:54 UTC  
**Repository:** `https://github.com/HarshDubey23/SELLABLE`  
**Security Posture:** 9 / 9 Active Controls Verified  

---

## 1. Verified Runtime Metrics

* **Automated Tests:** 115 Passed, 0 Failed, 1 Skipped
* **Audit Ledger:** 1 SHA-256 blocks chained from genesis (`abd47b0...`)
* **Policy Engine Rules:** 12 / 12 fail-closed deterministic checks active
* **Adversarial Red Team Attacks:** 20 executed, 20 blocked, **0 unauthorized money calls**
* **Concurrency Protection:** 100-thread race test verified atomic single-use token consumption
* **Reconciliation State Machine:** 8 explicit states, 0 blind retry loops on ambiguous timeouts

---

## 2. Evidence Files Index

| Evidence File | Contents Description |
|---|---|
| [`artifacts/evidence/summary.json`](file:///artifacts/evidence/summary.json) | High-level execution & security posture summary |
| [`artifacts/evidence/security-matrix.json`](file:///artifacts/evidence/security-matrix.json) | R1-R12 deterministic policy registry |
| [`artifacts/evidence/attack-results.json`](file:///artifacts/evidence/attack-results.json) | 20-scenario adversarial attack containment proof |
| [`artifacts/evidence/money-boundary.json`](file:///artifacts/evidence/money-boundary.json) | Authoritative money boundary call accounting |
| [`artifacts/evidence/audit-verification.json`](file:///artifacts/evidence/audit-verification.json) | SHA-256 hash-chain verification against SQLite |
| [`artifacts/evidence/reconciliation.json`](file:///artifacts/evidence/reconciliation.json) | Payment state machine and recovery specifications |
| [`artifacts/evidence/test-results.json`](file:///artifacts/evidence/test-results.json) | Pytest automated test run statistics |
| [`artifacts/evidence/architecture-check.json`](file:///artifacts/evidence/architecture-check.json) | Static AST scan assertions (pure policy, 1 money gate) |

---
