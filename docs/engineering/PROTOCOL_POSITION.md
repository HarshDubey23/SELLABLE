# SELLABLE -- Protocol Position & Alignment

## Executive Summary
SELLABLE is a fail-closed, protocol-agnostic security gateway for agentic commerce.
It decouples probabilistic LLM buyer reasoning from deterministic payment authorization.

## Protocol Alignment Matrix

| Protocol | Publisher / Standards Body | Security Risk in Naive Flow | SELLABLE Enforcement |
| :--- | :--- | :--- | :--- |
| **NPCI UAP** | NPCI (India UPI) | Agent spending delegation without policy bounds | Signed user mandates, R1 budget caps, SHA-256 audit ledger |
| **AP2** | Google & 60+ Partners | Unbounded payment execution across agent rails | Cryptographic approval binding (exact cart + amount match) |
| **ACP** | Stripe, OpenAI, Meta | Prompt injection in merchant catalog feeds | R3 price drift check against server catalog, R12 protocol scope |
| **x402** | Coinbase | Machine microtransaction replay / scope creep | R12 protocol artifact isolation, single-use binding consumption |

## India Timing Advantage
With NPCI preparing the rollout of the Unified Agent Protocol (UAP) on UPI (24.5 billion monthly transactions), India is poised to lead global agentic commerce. SELLABLE provides the exact fail-closed policy layer required on Day 1.
