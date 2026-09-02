# SELLABLE — Judge & Technical Evaluator FAQ

### Q1: What makes SELLABLE different from a standard AI shopping bot?
**A:** Traditional AI shopping bots give the LLM API keys or browser automation tools to execute purchases directly. SELLABLE treats the LLM as an **untrusted proposer**. All financial execution is strictly gated behind a deterministic 12-rule policy gateway and an immutable cryptographic approval binding.

### Q2: Why not use the LLM to verify its own budget?
**A:** LLMs are probabilistic models vulnerable to prompt injection, semantic confusion, and hallucination. Safety-critical monetary boundaries MUST be deterministic, mathematical, and fail-closed.

### Q3: What happens if an attacker mutates the cart after approval?
**A:** The Approval Binding binds the exact SHA-256 hash of the approved cart. If even one SKU or price is altered, the hash mismatch causes the execution gate to reject the order immediately with 0 money calls.

### Q4: How is Razorpay integrated?
**A:** SELLABLE integrates directly with Razorpay's Test-Mode API (`/v1/orders`), validates webhooks via raw-body HMAC-SHA256 signatures, and embeds the live `checkout.js` modal for real-time payment capture.

### Q5: Does the audit log survive restarts?
**A:** Yes. The audit log is stored in a durable SQLite database (`data/sellable.db`) with SHA-256 block chaining and genesis verification executed on every server boot.
