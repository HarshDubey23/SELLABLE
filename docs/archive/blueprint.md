# 🏆 SELLABLE — MASTER SPEC v2.0 (FINAL. LOCKED.)

> **Target Architecture & Engineering Blueprint for SELLABLE (Track 01: AI Growth & Agentic Commerce)**

---

## 1. Problem & Core Value Proposition

- **The Problem**: Over 50M daily purchasing intents across conversational AI platforms, but merchants are invisible, untransactable, and unsafe against prompt injection attacks.
- **Death Mode 1 (Invisible Merchant)**: Catalog hidden in unstructured HTML, checkout requires human manual interaction, giving agents raw keys exposes massive risk.
- **Death Mode 2 (Ungated Agent)**: Product descriptions containing prompt injections trick buyer LLMs into buying unintended/expensive products.
- **SELLABLE Solution**: Agent-Readable (`.well-known/agent-manifest.json`), Agent-Transactable (signed quotes + typed storefront tools), Agent-Safe (deterministic 10-rule policy gateway + tamper-evident audit log).

---

## 2. Target Architecture Overview

1. **MISSION**: Signed, immutable scope object (HMAC): `budget_paise`, allowed/forbidden categories, expiry. Agent cannot alter it.
2. **BUYER AGENT**: Plan-and-execute LLM loop with revision-on-REJECT loop. Max 8 steps / 15 tool calls.
3. **MERCHANT STOREFRONT API**: Agent-native tools: manifest, search, get_product, quote (signed, TTL), create_order (real Razorpay), check_payment.
4. **POLICY GATEWAY**: ~350 lines pure Python, ZERO LLM, 10 deterministic rules (R1 budget, R2 forbidden, R3 price-drift, R4 upsell-cap, R5 scope, R6 rate-limit, R7 allowlist, R8 abort, R9 signature, R10 expiry). Fail-closed.
5. **PAYMENT EXECUTOR**: Only module holding Razorpay keys; creates orders only after an APPROVE verdict.
6. **AUDIT LOG**: Hash-chained, tamper-evident.
7. **EVAL HARNESS**: 3 arms (static / ungated / gated) × 100 seeded missions, trust-adjusted revenue metric.

---

## 3. Day 2 Component Details

### Catalog & Injections (40 SKUs across 6 categories)
- Cricket (8), Books (8), Electronics (7), Apparel (6), Groceries (5), Stationery (6).
- Integer paise everywhere (e.g. ₹1,499 = 149900).
- Hand-authored injection payloads I1–I8 embedded in descriptions:
  - I1: Direct override (`KIT-001`)
  - I2: Authority appeal (`BOOK-008`)
  - I3: Hidden upsell (`LAP-002`)
  - I4: Tool confusion (`SOCK-001`)
  - I5: Zero-amount attack (`HONY-001`)
  - I6: Unicode obfuscation (`STKY-001`)
  - I7: Sandwich injection (`PLNR-001`)
  - I8: Category spoofing (proposal-time)

### Agent Manifest & Storefront Tools
- `GET /.well-known/agent-manifest.json`: Discovery front door
- `GET /tools/merchant_policy`: Merchant policy details
- `GET /tools/search_products`: Catalog search with server-truth pricing
- `GET /tools/get_product/{sku}`: Product details
- `POST /tools/quote`: Signed price lock with 30-min TTL
- `POST /tools/create_order`: Real Razorpay order creation with idempotency key
- `GET /tools/check_payment/{order_id}`: Payment status checker
