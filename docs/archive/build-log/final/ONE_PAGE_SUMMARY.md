# SELLABLE — One-Page Executive Summary

**Autonomous Commerce Without Autonomous Money**

### The Core Problem
Autonomous AI agents are increasingly tasked with finding and purchasing goods online. However, granting generative AI models (LLMs) direct financial authority introduces unacceptable risks: prompt injection, hallucinations, rogue budget overrides, cart tampering, and unconstrained spending loops.

### The Solution: SELLABLE
SELLABLE is an open-source, fail-closed security gateway that decouples probabilistic AI reasoning from deterministic payment authorization.

> **"The LLM proposes. Deterministic policy disposes. Cryptographic bindings authorize. Razorpay executes. The audit chain remembers."**

### End-to-End Architecture
1. **Buyer Agent (LLM):** Uses Google Gemini 2.5/3.5 to interpret natural language missions, discover merchant products, and propose a purchase cart.
2. **Policy Gateway (R1–R12):** Evaluates the proposal against a deterministic 12-rule matrix (budget caps, category integrity, expiry, and signature validation). Fails closed on any anomaly.
3. **Approval Binding:** Generates a cryptographic token linking Mission ID, Exact Quote ID, Cart Hash, Amount in Paise, Currency, and SKU Set.
4. **Execution Boundary:** Razorpay Test Mode orders are created ONLY when the request precisely matches an unconsumed, non-expired Approval Binding.
5. **Tamper-Evident Audit Ledger:** Every state transition is cryptographically chained via SHA-256 and verified at boot.

### Key Proof Points (Track 01 Requirements)
* **Explainable & Bounded:** 100% of money actions are bounded by signed user mandates and deterministic gateway checks.
* **0-Money Invariant Under Attack:** Adversarial prompt injections, budget overrides, and cart mutations result in strictly **0 Razorpay calls**.
* **Bounded Failure Recovery:** Payment failures trigger bounded recovery paths without expanding the original spending authority.
* **Auditability:** Complete cryptographic chain ensures non-repudiation.
