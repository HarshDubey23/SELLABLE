"""SELLABLE Eval Harness - Day 5.

Three arms x N seeded missions, measuring trust-adjusted revenue.

ARMS:
  static   : merchant publishes a fixed-price catalog; no agent, no gateway.
             Revenue = sum of catalog prices for missions that would have
             succeeded (budget >= price). This is the baseline.
  ungated  : an LLM agent proposes with NO gateway (the naive approach).
             Revenue = sum of LLM-proposed prices, but ANY injection that
             slips through counts as a LOSS (negative revenue, the cost of
             fraud). This shows why "just let the LLM decide" loses money.
  gated    : SELLABLE's actual architecture. Revenue = sum of APPROVED
             proposals at server-authoritative prices, with injections
             rejected by the gateway. Recovery revenue from failed-then-
             link flows is added. This is the trust-adjusted number.

METRICS (reported per arm + overall):
  - gross_revenue_paise     : sum of all accepted transaction values
  - trust_adjusted_revenue  : gross - fraud_loss - recovery_cost
  - acceptance_rate         : approved / total_missions
  - injection_resistance    : injections_blocked / injections_attempted
  - avg_turns_per_negotiation
  - p95_latency_ms

USAGE:
  python -m eval.missions.generate --count 100 --seed 42
  python -m eval.run --missions 100 --reps 3 --seed 42
  python -m eval.report --out eval/report.md
"""
