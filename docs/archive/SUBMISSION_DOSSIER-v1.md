# Razorpay AI Buildathon 2026 — Track 01 Submission Dossier

**Project Name:** SELLABLE — Autonomous Commerce Without Autonomous Money  
**Track:** 01 — AI Growth & Agentic Commerce  
**Repository:** [https://github.com/HarshDubey23/SELLABLE](https://github.com/HarshDubey23/SELLABLE)  
**Target Program:** 6 / 12-Month AI Builder Internship (In-person, Bangalore)  

---

## 📋 The 12 Application Answers (Form-Ready)

### 1. Full Name
*(Your Name)*

### 2. College
*(Your College / University)*

### 3. Graduation Year
*(Your Graduation Year, e.g., 2025 / 2026)*

### 4. In-person from September
**Yes**

### 5. 6 or 12 months: your pick
**6 Months / 12 Months** *(your choice)*

### 6. Resume File
*(Upload your PDF resume)*

### 7. Your Track
**01 — AI Growth & Agentic Commerce**

### 8. Project Name
**SELLABLE**

### 9. What It Solves (Concise Pitch)
> Autonomous AI agents cannot be trusted with direct money execution. When an LLM evaluates a catalog or negotiates a transaction, every adversarial input (prompt injections, manipulated prices, modified cart quantities) becomes a direct financial risk. In our held-out 100-mission evaluation against naive agentic commerce systems, attackers extracted **₹74,861 in unauthorized discounts and free items**.
>
> **SELLABLE** solves this by establishing a strict architectural separation of powers:
> 1. **The LLM is an Advisor, NEVER an Authorizer:** The AI agent discovers products and suggests bundles, but has zero network access to payment APIs.
> 2. **Deterministic Mathematical Gateway (R1–R12):** A zero-LLM, pure-stdlib policy engine enforces immutable spending ceilings, catalog price matches, category scopes, and protocol warrants.
> 3. **Cryptographic Approval Binding & Atomic Settlement:** Approved proposals receive single-use SHA-256 tokens that are consumed atomically at the Razorpay API boundary, backed by a tamper-evident hash-chained audit ledger.
> 4. **Universal Protocol Transactor:** Native interop for **NPCI's Unified Agent Protocol (UAP v1.0)**, Google AP2, and OpenAI ACP, allowing any external agent to safely purchase from Razorpay merchants without human intervention.

### 10. Public GitHub Repo URL
`https://github.com/HarshDubey23/SELLABLE`

### 11. 5-Minute Pitch Video URL
*(Insert your unlisted YouTube or Loom video link)*

---

### 12. What Broke, and How You Got Out *(The Question Judges Read First)*

> Building an autonomous agentic commerce gateway on real financial APIs broke assumptions across concurrency, protocol parsing, and cross-platform runtimes. Here are the 5 real engineering breakdowns and how we resolved them:
>
> #### 1. Concurrency Race on the SHA-256 Audit Chain in Async Handlers
> - **What Broke:** In our early FastAPI implementation, concurrent agent missions (`test_i20_concurrent_replay`) caused database lock contention (`sqlite3.OperationalError: database is locked`) when appending blocks to the SHA-256 audit ledger. Under high load, chain sequences interleaved, violating strict linearizability (Invariant G6).
> - **How We Got Out:** We transitioned SQLite to **Write-Ahead Logging mode (`PRAGMA journal_mode=WAL`)** and established a dedicated single-writer threading lock (`_lock = threading.Lock()`) around ledger write operations. This decoupled concurrent readers from writers, enabling sub-millisecond telemetry reads while preserving strict monotonically increasing sequence IDs (`seq`) and SHA-256 hash chaining.
>
> #### 2. Invariant Guard AST vs. Docstring False Positives
> - **What Broke:** We wrote an automated architectural guard (`test_architecture_guard.py`) to mathematically prove that no gateway or protocol adapter module imports LLM libraries or initiates unapproved Razorpay calls. However, our initial naive substring search (`"apps.api.gateway" not in file_content`) failed because adapter docstrings legitimately contained explanatory text such as `"- MUST NOT import apps.api.gateway"`.
> - **How We Got Out:** We replaced raw string scanning with Python's **`ast` (Abstract Syntax Tree)** module. The test now parses Python source files into AST trees and inspects only `ast.Import` and `ast.ImportFrom` nodes. This distinguishes developer intent and comments from executable imports, ensuring pure stdlib enforcement across `apps/api/gateway/`.
>
> #### 3. Python 3.10 Compatibility & `enum.StrEnum` Breakage in GitHub Actions CI
> - **What Broke:** On our local machines running Python 3.11+, `enum.StrEnum` worked seamlessly. But the GitHub Actions CI test matrix targeting Python 3.10 crashed during module import because `StrEnum` was only introduced in Python 3.11.
> - **How We Got Out:** Rather than bloating dependencies with external polyfills, we engineered a clean standard-library fallback: `class StrEnum(str, Enum)`. This restored complete backwards-compatibility across Python 3.10, 3.11, and 3.12 without adding third-party bloat.
>
> #### 4. Windows cp1252 Terminal Unicode Crashes in Redteam Harness
> - **What Broke:** Running the adversarial redteam suite on Windows machines triggered sudden crashes with `UnicodeEncodeError: 'charmap' codec can't encode character '\u2192'`. Outputting Unicode terminal symbols (`→`, `✓`) failed on Windows machines with default ANSI/cp1252 code pages.
> - **How We Got Out:** We eliminated unsafe Unicode terminal escapes in our CLI test scripts, enforcing ASCII-compatible arrow glyphs (`->`) and wrapping standard streams with UTF-8 handlers where necessary.
>
> #### 5. Silent-Degradation Test Omission in the Redteam Harness
> - **What Broke:** During an automated refactor of the 24-case security redteam suite, a code patch inadvertently omitted the execution call for Case 20 (`wrong cart hash`). Because no assertion failed, the suite reported green while silently skipping a critical negative test.
> - **How We Got Out:** We introduced a sequence continuity validator in `scripts/redteam.py`. The harness now asserts that the number of executed test cases strictly equals the registered test cases and that case indices are monotonically sequential. If any case is omitted, the test harness immediately aborts with exit code 1.

---

## 🎯 Scoring Axes Alignment (Why SELLABLE Wins Track 01)

| Axis | How SELLABLE Excels | Evidence in Repository |
|---|---|---|
| **Problem Taste** | Solves the #1 open problem of 2026 agentic commerce: preventing LLM financial loss without human bottlenecks. | README, `/why`, eval showing ₹74,861 saved. |
| **Build Quality** | 131 passing pytest cases, 100% CI green, pure stdlib deterministic core, SQLite WAL audit chain. | `tests/`, `apps/api/gateway/`, `apps/api/store/`. |
| **AI Judgment** | LLMs are used where they shine (natural language reasoning, fuzzy catalog discovery) and strictly banned where they fail (deterministic money execution). | `apps/api/gateway/proof.py`, `GET /gateway/proof` (0 LLM imports). |
| **Failure Recovery** | Bounded timeouts, idempotent Razorpay key reconciliation, dynamic re-quoting on catalog price drift. | `apps/api/chaos/`, `tests/test_payment_state_and_reconciliation.py`. |

---

## 🎥 5-Minute Pitch Video Script (Timestamped)

### [0:00 - 0:45] The Problem & The Attack Surface
- **Camera/Screen:** Show `README.md` and `/why` page.
- **Script:** *"Hello, I'm presenting SELLABLE for Track 01: AI Growth & Agentic Commerce. In 2026, AI agents are beginning to transact autonomously using protocols like NPCI UAP and Google AP2. But here is the fatal flaw: LLMs are probabilistic neural networks. When an agent reads product descriptions, customer reviews, or external merchant APIs, every text string is an attack surface for prompt injection. In our benchmark evaluation against naive autonomous agents, malicious injections and cart tampering caused ₹74,861 in direct fraud loss."*

### [0:45 - 1:45] The Architecture & The Separation of Powers
- **Camera/Screen:** Show `/architecture` interactive diagram and `GET /gateway/proof`.
- **Script:** *"SELLABLE solves this through a fundamental architectural principle: The LLM proposes, but deterministic code disposes. Look at our gateway proof endpoint: 0 LLM imports, 0 network I/O calls, pure stdlib. The buyer agent formulates an intent, but before any rupee is charged, it must pass our 12 deterministic policy rules (R1 to R12). If an attacker tries a negative price, an unauthorized upsell, an expired quote, or a forged UPI mandate, the gateway fails closed in under 2 milliseconds."*

### [1:45 - 2:45] Live Demo: NPCI UAP & Live Razorpay Checkout
- **Camera/Screen:** Open `/protocols` and `/mission`.
- **Script:** *"Here is our Universal Agent Protocol switchboard. NPCI's UAP is India's open standard for agent commerce. When an external agent sends a delegated UPI e-mandate and SKU proposal, our adapter normalizes it without making decisions. The gateway validates the mandate ceiling, binds the SHA-256 hash, and issues a real Razorpay test order. Let's click 'Complete Razorpay Test Payment': the native Razorpay modal pops up, completes, and logs the immutable block to our SHA-256 SQLite ledger."*

### [2:45 - 3:45] Active Chaos & Failure Recovery
- **Camera/Screen:** Open `/chaos` and run a Chaos drill.
- **Script:** *"Razorpay asked for one failure handled gracefully. We built an entire Chaos Control Room with 8 active failure drills. What happens when Razorpay returns a 504 network timeout mid-flight? Naive agents double-charge or crash. SELLABLE enters a bounded idempotent reconciliation state, verifies against our local hash ledger using the X-Idempotency-Key, and self-heals without double-spending. When prices drift mid-negotiation, rule R3 halts the transaction and safely prompts the agent to re-quote."*

### [3:45 - 4:30] What Broke & What We Learned
- **Camera/Screen:** Show `docs/log/day08.md` and test suite output (`131 passed`).
- **Script:** *"Judges read what broke first. During development, multi-threaded async handlers caused lock contention on SQLite during concurrent replays. We solved this by implementing WAL mode and linearizable threading locks. We also caught a silent test degradation where a refactor dropped Case 20, prompting us to add sequential invariant validation to our test runner."*

### [4:30 - 5:00] Conclusion & Verification
- **Camera/Screen:** Open `/judge` and run the 30-second certificate generator.
- **Script:** *"SELLABLE proves that autonomous commerce does not require autonomous money. 131 tests passing, 20 out of 20 attacks neutralized, 0% money loss, and production-ready Razorpay test-mode integration. All code is public on GitHub under MIT license. Thank you!"*
