# SELLABLE — Comprehensive System Architecture

## 1. System Overview
SELLABLE establishes a secure runtime environment for autonomous e-commerce agents by enforcing strict architectural separation between untrusted intelligence and trusted execution.

## 2. Subsystem Breakdown

### 2.1 The Untrusted Layer (Probabilistic AI)
* **Buyer Agent (`apps/api/agent/buyer.py`):** Runs autonomous discovery loops, calls catalog tools, and formulates structured JSON purchase proposals.
* **LLM Engine (`apps/api/llm/`):** Interfaces with Google GenAI SDK (Gemini 2.5/3.5 Flash). Operates in a read-only sandbox with zero monetary authority.

### 2.2 The Deterministic Trust Layer (Gateway & Bindings)
* **Policy Gateway (`apps/api/gateway/`):** Evaluates proposals against R1–R12:
  * R1: Budget Cap
  * R2: Category Scope
  * R3: Forbidden Categories
  * R4: SKU Catalog Existence
  * R5: Stock Availability
  * R6: Quantity Bounds
  * R7: Price Sanity & Ceiling
  * R8: Upsell Cap Multiplier
  * R9: User Mission Signature
  * R10: Temporal Expiry
  * R11: Protocol Compliance
  * R12: State Hash Integrity
* **Approval Binding Engine (`apps/api/approval.py`):** Issues cryptographically signed approval records persisted to SQLite (`data/sellable.db`).

### 2.3 The Execution Layer (Razorpay Integration)
* **Razorpay Client (`apps/api/razorpay_client.py`):** Communicates with `api.razorpay.com/v1/orders` using authenticated test-mode keys.
* **Webhook Receiver (`apps/api/webhook/receiver.py`):** Validates HMAC signatures on incoming Razorpay payment events.

### 2.4 The Durable Audit Layer
* **Tamper-Evident Ledger (`apps/api/audit/`):** Maintains an immutable SHA-256 hash-chained log of every system action.
