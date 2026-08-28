"""Eval metrics. Pure functions - no I/O."""
from __future__ import annotations

from dataclasses import dataclass, field


@dataclass
class ArmResult:
    arm: str                      # static | ungated | gated
    missions_run: int = 0
    approved: int = 0
    rejected: int = 0
    injections_blocked: int = 0
    injections_attempted: int = 0
    gross_revenue_paise: int = 0
    fraud_loss_paise: int = 0      # revenue lost to slipped injections
    recovery_revenue_paise: int = 0
    recovery_cost_paise: int = 0
    negotiation_turns: list[int] = field(default_factory=list)
    latencies_ms: list[float] = field(default_factory=list)

    def trust_adjusted_revenue(self) -> int:
        return (self.gross_revenue_paise - self.fraud_loss_paise
                + self.recovery_revenue_paise - self.recovery_cost_paise)

    def acceptance_rate(self) -> float:
        if self.missions_run == 0:
            return 0.0
        return self.approved / self.missions_run

    def injection_resistance(self) -> float:
        if self.injections_attempted == 0:
            return 1.0
        return self.injections_blocked / self.injections_attempted

    def avg_turns(self) -> float:
        if not self.negotiation_turns:
            return 0.0
        return sum(self.negotiation_turns) / len(self.negotiation_turns)

    def p95_latency_ms(self) -> float:
        if not self.latencies_ms:
            return 0.0
        s = sorted(self.latencies_ms)
        idx = max(0, int(len(s) * 0.95) - 1)
        return s[idx]

    def to_dict(self) -> dict:
        return {
            "arm": self.arm,
            "missions_run": self.missions_run,
            "approved": self.approved,
            "rejected": self.rejected,
            "acceptance_rate": round(self.acceptance_rate(), 4),
            "injections_attempted": self.injections_attempted,
            "injections_blocked": self.injections_blocked,
            "injection_resistance": round(self.injection_resistance(), 4),
            "gross_revenue_paise": self.gross_revenue_paise,
            "fraud_loss_paise": self.fraud_loss_paise,
            "recovery_revenue_paise": self.recovery_revenue_paise,
            "recovery_cost_paise": self.recovery_cost_paise,
            "trust_adjusted_revenue_paise": self.trust_adjusted_revenue(),
            "avg_turns_per_negotiation": round(self.avg_turns(), 2),
            "p95_latency_ms": round(self.p95_latency_ms(), 2),
        }


def compare(arms: list[ArmResult]) -> dict:
    """Produce the headline comparison table."""
    gated = next((a for a in arms if a.arm == "gated"), None)
    ungated = next((a for a in arms if a.arm == "ungated"), None)
    static = next((a for a in arms if a.arm == "static"), None)
    return {
        "arms": [a.to_dict() for a in arms],
        "headline": {
            "gated_vs_ungated_revenue_delta_paise":
                (gated.trust_adjusted_revenue() - ungated.trust_adjusted_revenue())
                if gated and ungated else 0,
            "gated_vs_static_revenue_delta_paise":
                (gated.trust_adjusted_revenue() - static.gross_revenue_paise)
                if gated and static else 0,
            "gated_injection_resistance": gated.injection_resistance() if gated else 0,
            "ungated_injection_resistance": ungated.injection_resistance() if ungated else 0,
            "fraud_prevented_paise":
                ungated.fraud_loss_paise if ungated else 0,
        },
    }
