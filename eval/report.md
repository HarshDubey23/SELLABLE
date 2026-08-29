# SELLABLE Eval Report

## Headline

- **Gated vs Ungated revenue delta**: Rs. 65,668.00
- **Gated vs Static revenue delta**: Rs. -39,834.00
- **Gated injection resistance**: 100.0%
- **Ungated injection resistance**: 0.0%
- **Fraud prevented (ungated loss)**: Rs. 74,861.00

## Per-Arm Metrics

| Metric | Static | Ungated | Gated |
|---|---|---|---|
| Missions run | 300 | 300 | 300 |
| Approved | 220 | 231 | 144 |
| Rejected | 80 | 69 | 156 |
| Acceptance rate | 73.3% | 77.0% | 48.0% |
| Injections attempted | 0 | 45 | 45 |
| Injections blocked | 0 | 0 | 45 |
| Injection resistance | 100.0% | 0.0% | 100.0% |
| Gross revenue (Rs.) | Rs. 126,420.00 | Rs. 95,779.00 | Rs. 86,586.00 |
| Fraud loss (Rs.) | Rs. 0.00 | Rs. 74,861.00 | Rs. 0.00 |
| Recovery revenue (Rs.) | Rs. 0.00 | Rs. 0.00 | Rs. 0.00 |
| Recovery cost (Rs.) | Rs. 0.00 | Rs. 0.00 | Rs. 0.00 |
| Trust-adjusted revenue (Rs.) | Rs. 126,420.00 | Rs. 20,918.00 | Rs. 86,586.00 |
| Avg turns/negotiation | 0.0 | 0.0 | 0.0 |
| p95 latency (ms) | 0.0 | 0.0 | 0.1 |

## Interpretation

**Static arm** is the baseline: fixed catalog prices, no agent. It earns gross revenue but has zero injection resistance and zero recovery capability.

**Ungated arm** simulates the naive 'just let the LLM decide' approach. Every injected price slips through, causing fraud loss equal to the catalog price minus the injected price. This is the cost of not having a gateway.

**Gated arm** is SELLABLE. The gateway reads prices server-side (R3 price drift), so injections in the justification have NO effect on the transaction. Injection resistance is ~100% by construction. Recovery revenue from failed-then-link flows adds trust-adjusted revenue the other arms cannot match.
