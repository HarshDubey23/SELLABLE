# SELLABLE — Razorpay AI Buildathon 2026 Demo Script

## Thesis
> **Autonomous intelligence without autonomous money.**  
> *"The LLM proposes. Deterministic policy disposes. Cryptographic authorization binds. Razorpay executes. Reconciliation establishes truth. The audit chain remembers."*

---

## Stage Demo Flow (3 Minutes)

### Step 1: The Core Contract & Happy Path (45s)
- **Action**: Open `http://localhost:8000/` (Command Center) or `http://localhost:8000/mission`.
- **What to say**:
  > *"Welcome to SELLABLE — the agent-safe commerce layer built for Razorpay. Standard AI agents cannot be trusted with money directly because LLMs fail nondeterministically under prompt injection or market drift. SELLABLE puts a 100% pure, deterministic Policy Gateway in front of every money action."*
- **Visual**: Show real Razorpay order ID `order_...` generated on payment capture.

---

### Step 2: Chaos Drill 1 — Duplicate Storm (30s)
- **Action**: Open `http://localhost:8000/chaos` -> Click **DUPLICATE_STORM**.
- **What to say**:
  > *"When network hiccups cause an agent to retry 5 times concurrently with the same signed mandate and idempotency key, what happens? Let's inject a duplicate storm."*
- **Visual**: Show live stream: 5 concurrent submits -> Exactly **1 Razorpay order created**; 4 replays return `DUPLICATE_IDEM` cached response (HTTP 200).

---

### Step 3: Chaos Drill 2 — Price Flip (The Money Moment) (45s)
- **Action**: Click **PRICE_FLIP** on `/chaos`.
- **What to say**:
  > *"Here is the money moment. The buyer agent inspects a cricket bat at Rs 1,299. Mid-flight, the merchant changes the price to Rs 1,499. The agent submits its signed Rs 1,299 intent mandate."*
  > *"Our gateway intercepts the price drift before Razorpay execution, issuing a structured `409 PRICE_STALE` refusal with a cryptographic `fresh_quote`. The agent re-quotes, re-signs at Rs 1,499, and the gateway approves."*
- **Visual**: Show red `PRICE_STALE` refusal turning green on fresh quote re-signature in the live feed.

---

### Step 4: Chaos Drill 3 — Multi-Agent Last Unit Race (30s)
- **Action**: Click **LAST_UNIT_RACE** on `/chaos`.
- **What to say**:
  > *"What if 3 AI agents attempt to buy the last remaining item concurrently? SELLABLE holds atomic stock reservations with a 30-second TTL."*
- **Visual**: Show 1 agent approved with stock reservation; 2 agents receive structured `OUT_OF_STOCK` refusals.

---

### Step 5: The Invariant Machine Verdict & Interactive Architecture (30s)
- **Action**: Open `http://localhost:8000/architecture` -> Click **FAILURE DRILL**.
- **What to say**:
  > *"At the end of every drill, our Invariant Engine automatically verifies all 8 non-negotiable guarantees — zero double captures, zero stock drift, 100% HMAC-verified webhooks, and an untampered SQLite audit ledger."*
- **Visual**: Show green banner **SURVIVED — 8/8 INVARIANTS HELD**, and live SVG step lighting on the architecture diagram.
