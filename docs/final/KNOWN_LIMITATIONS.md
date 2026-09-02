# SELLABLE — Known Limitations & Production Roadmap

### Current Prototype Limitations
1. **Catalog Scope:** Prototype catalog currently contains 50 curated SKUs across sports, electronics, and apparel. Production requires distributed search integration (e.g., Elasticsearch / Algolia).
2. **Payment Rails:** Prototype focuses on Razorpay Orders, UPI, and Cards. Production would extend to automated subscription mandates (e-Mandate / UPI AutoPay).
3. **Multi-Merchant Settlement:** Single merchant storefront simulated. Production requires multi-merchant routing and escrow management.

### Production Roadmap
* Hardware Security Module (HSM) key storage for approval binding signatures.
* Zero-Knowledge proofs for user budget privacy.
* Distributed Raft consensus for multi-node audit ledger replication.
