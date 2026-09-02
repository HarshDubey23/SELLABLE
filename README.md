# SELLABLE — Autonomous Commerce Without Autonomous Money

[![Deterministic Gateway](https://img.shields.io/badge/Security_Gateway-12%20Rules%20Fail--Closed-blue.svg)](#security-invariants)
[![Razorpay Test Mode](https://img.shields.io/badge/Razorpay-Test%20Mode%20Orders-0C2340.svg?logo=razorpay)](#razorpay-integration)
[![Audit Chain](https://img.shields.io/badge/Audit_Ledger-SHA--256%20Tamper--Evident-success.svg)](#audit-chain-integrity)
[![Verification Suite](https://img.shields.io/badge/Test_Suite-74%2F74%20Passing-brightgreen.svg)](#verification)
[![Track 01](https://img.shields.io/badge/Razorpay_Buildathon-Track_01_AI_Growth-blueviolet.svg)](#track-01-compliance)

> **"The LLM proposes. Deterministic policy disposes. Cryptographic bindings authorize. Razorpay executes. The audit chain remembers."**

---

## 🚀 Executive Summary

As generative AI models evolve into autonomous agents capable of browsing the web, selecting products, and making purchasing decisions, a critical security vulnerability emerges: **granting probabilistic AI models direct monetary authority is fundamentally unsafe.**

LLMs hallucinate, suffer from prompt injections hidden in untrusted product descriptions, and cannot guarantee deterministic invariant enforcement.

**SELLABLE** is an open-source, fail-closed security gateway designed for the agentic commerce era. It completely decouples **probabilistic AI reasoning** from **deterministic payment authorization**.

* **The AI Buyer Agent** has full intelligence to understand user intent, search merchant catalogs, reason about specifications, and formulate purchase proposals.
* **The Deterministic Policy Gateway (R1–R12)** mathematically enforces budget caps, category boundaries, price locks, and mandate signatures.
* **The Approval Binding Engine** generates an immutable cryptographic token locking the exact mission, quote, amount, cart hash, and expiry.
* **Razorpay Execution Gate** verifies the binding before creating or settling test-mode orders.
* **Tamper-Evident Ledger** anchors every state transition into a SHA-256 block chain verified at boot.

---

## 🏛️ System Architecture

```text
                         USER
                           |
                           v
                  +----------------+
                  | Mission/Intent |
                  +-------+--------+
                          |
                          v
                  +----------------+
                  |  BUYER AGENT   |
                  |                |
                  | LLM Reasoning  |
                  | Search         |
                  | Ranking        |
                  | Proposal       |
                  +-------+--------+
                          |
                          | proposal only
                          v
                 +-------------------+
                 | MERCHANT/CATALOG  |
                 | TOOLS + QUOTING   |
                 +---------+---------+
                           |
                           v
                 +-------------------+
                 | DETERMINISTIC     |
                 | POLICY GATEWAY    |
                 |                   |
                 | R1 ... R12        |
                 | FAIL CLOSED       |
                 +---------+---------+
                           |
                    APPROVE / REJECT
                           |
                           v
                 +-------------------+
                 | APPROVAL BINDING  |
                 |                   |
                 | Mission           |
                 | Quote             |
                 | Amount            |
                 | Currency          |
                 | Cart Hash         |
                 | Proposal Hash     |
                 | SKU Set           |
                 | Expiry            |
                 +---------+---------+
                           |
                           v
                 +-------------------+
                 | MONEY EXECUTION   |
                 | BOUNDARY          |
                 +---------+---------+
                           |
                           v
                 +-------------------+
                 | RAZORPAY          |
                 | TEST MODE         |
                 +-------------------+

        +--------------------------------------+
        | DURABLE PERSISTENCE + AUDIT          |
        | bindings / state / events / hashes   |
        +--------------------------------------+
```

---

## 🛡️ Security Boundary (Probabilistic vs Deterministic)

| Capability / Responsibility | AI Buyer Agent (LLM) | Deterministic Gateway (SELLABLE) |
|---|:---:|:---:|
| **Intent Understanding & Parsing** | ✅ | ❌ |
| **Catalog Search & Semantic Ranking** | ✅ | ❌ |
| **Product Recommendation & Reason** | ✅ | ❌ |
| **Purchase Cart Proposal** | ✅ (Proposal Only) | ❌ |
| **Budget Ceiling Enforcement** | ❌ (Untrusted) | ✅ (Strict R1 Invariant) |
| **Category & Scope Enforcement** | ❌ (Untrusted) | ✅ (Strict R2/R5 Invariant) |
| **Price Lock & Quote Validation** | ❌ | ✅ (Strict R3/R10 Invariant) |
| **Cryptographic Approval Binding** | ❌ | ✅ (Exact Token Hash) |
| **Replay & Single-Use Enforcement** | ❌ | ✅ (Durable Consumption Flag) |
| **Razorpay Money Execution** | ❌ (0 Authority) | ✅ (Gated by Active Binding) |
| **Tamper-Evident Audit Logging** | ❌ | ✅ (SHA-256 Block Chain) |

---

## 🔍 The Reality Boundary

To maintain complete transparency for evaluators and judges:

| Subsystem | Implementation Reality | Notes |
|---|---|---|
| **Buyer Agent Reasoning** | **LIVE (REAL)** | Google Gemini 2.5/3.5 Flash via `google-genai` SDK |
| **Merchant Catalog & Quoting** | **LIVE (REAL)** | Exact quote generation with floor/ceiling checks |
| **Deterministic Gateway (R1–R12)** | **LIVE (REAL)** | 12 fail-closed rules evaluated in pure Python |
| **Approval Binding Engine** | **LIVE (REAL)** | Cryptographic tokens persisted to SQLite (`data/sellable.db`) |
| **Razorpay Order Creation** | **LIVE (REAL TEST MODE)** | Authenticated API calls to `api.razorpay.com/v1/orders` |
| **Interactive Checkout Modal** | **LIVE (REAL)** | Embedded `checkout.js` with auto-opening payment modal |
| **Webhook Signature Verification** | **LIVE (REAL)** | Raw-body HMAC-SHA256 signature verification |
| **Audit Ledger** | **LIVE (REAL)** | SHA-256 chained blocks with boot-time genesis verification |
| **User Wallet / Mandate Signing** | **SIMULATED** | Simulated wallet signing intent/cart mandates out-of-band |

---

## ⚡ Quick Start & Evaluator Route

### 1. Prerequisites
* Python 3.11+ (Tested on Python 3.13)
* Google Gemini API Key (`GEMINI_API_KEY`)
* Razorpay Test Mode Credentials (`RAZORPAY_KEY_ID`, `RAZORPAY_KEY_SECRET`)

### 2. Installation
```bash
# Clone the repository
git clone https://github.com/HarshDubey23/SELLABLE.git
cd SELLABLE

# Create and activate virtual environment
python -m venv venv
# On Windows:
.\venv\Scripts\activate
# On macOS/Linux:
source venv/bin/activate

# Install dependencies
pip install -r apps/api/requirements.txt
```

### 3. Configure Environment
```bash
cp .env.example .env
# Ensure GEMINI_API_KEY and Razorpay Test keys are present
```

### 4. Start the Application
```bash
python -m uvicorn apps.api.main:app --port 8000
```

### 5. Run the Automated Verification Suite
```bash
python scripts/final_verify.py --strict
```

---

## 🎮 CLI Demo Scenarios

SELLABLE includes an automated scenario runner for rapid evaluator inspection:

```bash
# 1. Run full suite of scenarios
python scripts/final_demo.py --scenario all

# 2. Test Happy Path (Agent discovery -> Approval -> Razorpay order)
python scripts/final_demo.py --scenario happy-path

# 3. Test Prompt Injection Defense (Zero money execution under attack)
python scripts/final_demo.py --scenario prompt-injection

# 4. Test Cart Mutation Defense (Post-approval price alteration blocked)
python scripts/final_demo.py --scenario cart-mutation

# 5. Test Replay Attack Defense (Single-use token consumption)
python scripts/final_demo.py --scenario replay

# 6. Test Audit Chain Tamper Detection
python scripts/final_demo.py --scenario audit-tamper
```

---

## 🖥️ Web UI & Operations Center

Navigate to `http://localhost:8000/` in your browser:

* **Command Center (`/`):** Real-time operational overview, Razorpay test mode status, audit verification, and money call counters.
* **Live Mission (`/mission`):** Interactive buyer agent workspace with natural language input, live trace visualizer, policy verdict card, and automatic Razorpay checkout modal.
* **Policy Gateway (`/gateway-ui`):** Interactive visualizer of the 12 deterministic rules (R1–R12).
* **Attack Lab (`/attack-ui`):** 8 live adversarial attack scenarios demonstrating mathematical containment and 0 money calls.
* **Audit Ledger (`/audit-ui`):** Cryptographic event timeline with one-click SHA-256 chain verification.
* **Catalog (`/products`):** Merchant product feed and pricing metadata.

---

## 🎯 Razorpay AI Buildathon — Track 01 Compliance

| Criterion | Implementation in SELLABLE |
|---|---|
| **Grow merchant revenue & make transactable by AI buyers** | Exposes agent-native discovery (`/.well-known/agent-manifest.json`), schema.org JSON-LD catalog, and pre-gated upsell recommendation engine. |
| **Every money action explainable, bounded, and gated** | 100% of money calls require signed mandates, R1–R12 gateway approval, and exact quote-to-binding cryptographic match. |
| **Show the audit trail** | SHA-256 chained ledger records mission, proposal, verdict, binding, order, payment, and webhook events with boot-time self-verification. |
| **Handle failure gracefully** | Bounded recovery loop captures payment rail failures and falls back safely without expanding spending authorization. |

---

## 📚 Complete Documentation Suite

Detailed architectural, security, and verification artifacts are located in `docs/`:

* [`docs/final/ONE_PAGE_SUMMARY.md`](docs/final/ONE_PAGE_SUMMARY.md) — One-page executive summary.
* [`docs/final/SECURITY_INVARIANTS.md`](docs/final/SECURITY_INVARIANTS.md) — Complete specification of all 12 security invariants.
* [`docs/final/FINAL_ARCHITECTURE.md`](docs/final/FINAL_ARCHITECTURE.md) — Deep architectural specification.
* [`docs/final/DEMO_RUNBOOK.md`](docs/final/DEMO_RUNBOOK.md) — Step-by-step evaluator runbook.
* [`docs/final/VIDEO_SCRIPT.md`](docs/final/VIDEO_SCRIPT.md) — 5-minute video pitch and demonstration script.
* [`docs/final/PRESENTER_CHEATSHEET.md`](docs/final/PRESENTER_CHEATSHEET.md) — Presenter quick-reference guide.
* [`docs/final/TEST_MATRIX.md`](docs/final/TEST_MATRIX.md) — Comprehensive automated test matrix.
* [`docs/final/FAILURE_RECOVERY.md`](docs/final/FAILURE_RECOVERY.md) — Real failure recovery analysis.
* [`docs/final/JUDGE_QA.md`](docs/final/JUDGE_QA.md) — Technical evaluator FAQ.
* [`docs/architecture/`](docs/architecture/) — Mermaid source diagrams and trust boundary specifications.

---

## 📄 License
MIT License. Built for the Razorpay AI Buildathon 2026.
