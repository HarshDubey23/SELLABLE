# SELLABLE Eval Report

## Headline

- **Gated vs Ungated revenue delta**: Rs. 65,668.00
- **Gated vs Static revenue delta**: Rs. -39,834.00
- **Gated injection resistance**: 100.0%
- **Ungated injection resistance**: 0.0%
- **Fraud prevented (ungated loss)**: Rs. 74,861.00

## V2 Metrics

| Metric | Value |
|---|---|
| Acceptance rate | 48.0% |
| AOV uplift (%) | 45.02 |
| False block cost (₹) | 199268.0 |
| LLM fooled rate | 0.0% |
| Money loss rate | 0.0% |
| Negotiation margin (%) | 343.56 |
| p95 latency (ms) | 10.0% |
| Protocol pass rate | 1.0 |

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
| Trust-adj revenue (Rs.) | Rs. 126,420.00 | Rs. 20,918.00 | Rs. 86,586.00 |
| p95 latency (ms) | 0.0 | 0.0 | 0.1 |

## Interpretation

**Static arm** is the baseline: fixed catalog prices, no agent.
**Ungated arm** simulates the naive 'just let the LLM decide' approach.
**Gated arm** is SELLABLE — the gateway reads prices server-side.
**behavioral_ungated_llm** and **behavioral_gated_llm** track model-fooling vs money-loss separately.
