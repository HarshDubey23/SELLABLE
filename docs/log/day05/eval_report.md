# SELLABLE Eval Report

## Headline

- **Gated vs Ungated revenue delta**: Rs. 87,497.00
- **Gated vs Static revenue delta**: Rs. 18,477.00
- **Gated injection resistance**: 100.0%
- **Ungated injection resistance**: 0.0%
- **Fraud prevented (ungated loss)**: Rs. 34,510.00

## Per-Arm Metrics

| Metric | Static | Ungated | Gated |
|---|---|---|---|
| Missions run | 300 | 300 | 300 |
| Approved | 218 | 218 | 229 |
| Rejected | 82 | 82 | 71 |
| Acceptance rate | 72.7% | 72.7% | 76.3% |
| Injections attempted | 0 | 45 | 45 |
| Injections blocked | 0 | 0 | 45 |
| Injection resistance | 100.0% | 0.0% | 100.0% |
| Gross revenue (Rs.) | Rs. 132,882.00 | Rs. 98,372.00 | Rs. 147,971.00 |
| Fraud loss (Rs.) | Rs. 0.00 | Rs. 34,510.00 | Rs. 0.00 |
| Recovery revenue (Rs.) | Rs. 0.00 | Rs. 0.00 | Rs. 3,394.00 |
| Recovery cost (Rs.) | Rs. 0.00 | Rs. 0.00 | Rs. 6.00 |
| Trust-adjusted revenue (Rs.) | Rs. 132,882.00 | Rs. 63,862.00 | Rs. 151,359.00 |
| Avg turns/negotiation | 0.0 | 0.0 | 0.0 |
| p95 latency (ms) | 0.0 | 0.0 | 0.07 |

## Interpretation

**Static arm** is the baseline: fixed catalog prices, no agent. It earns gross revenue but has zero injection resistance and zero recovery capability.

**Ungated arm** simulates the naive 'just let the LLM decide' approach. Every injected price slips through, causing fraud loss equal to the catalog price minus the injected price. This is the cost of not having a gateway.

**Gated arm** is SELLABLE. The gateway reads prices server-side (R3 price drift), so injections in the justification have NO effect on the transaction. Injection resistance is ~100% by construction. Recovery revenue from failed-then-link flows adds trust-adjusted revenue the other arms cannot match.
