"""Types and Data Structures for SELLABLE Chaos Monkey Engine."""
from __future__ import annotations

import time
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Dict, List, Optional


class FaultType(str, Enum):
    LATENCY_SPIKE = "latency_spike"
    PRICE_FLIP = "price_flip"
    DUPLICATE_STORM = "duplicate_storm"
    WEBHOOK_BLACKHOLE = "webhook_blackhole"
    WEBHOOK_DUPE = "webhook_dupe"
    AGENT_KILL = "agent_kill"
    BOUND_BREACH = "bound_breach"
    STOCK_RACE = "stock_race"
    CLOCK_JUMP = "clock_jump"
    FLAKE_5XX = "5xx_flake"


@dataclass
class FaultConfig:
    fault_id: str
    type: FaultType
    target_route: str
    params: Dict[str, Any] = field(default_factory=dict)
    duration_ms: int = 60000
    created_at: float = field(default_factory=time.time)
    expires_at: float = field(default_factory=lambda: time.time() + 60)
    armed: bool = True

    def is_expired(self, now_ts: Optional[float] = None) -> bool:
        now_ts = now_ts if now_ts is not None else time.time()
        return not self.armed or now_ts >= self.expires_at


@dataclass
class InvariantResult:
    id: str  # I1 to I8
    name: str
    held: bool
    evidence: str
    event_ids: List[str] = field(default_factory=list)


@dataclass
class RunVerdict:
    run_id: str
    scenario_id: str
    outcome: str  # "SURVIVED" or "BREACH"
    invariants: List[InvariantResult]
    counts: Dict[str, int]
    timeline: List[Dict[str, Any]]
    created_at: float = field(default_factory=time.time)


@dataclass
class ChaosEvent:
    ts: float
    trace_id: str
    kind: str  # "chaos_injection", "gateway_decision", "agent_action", "ledger_append", "verdict"
    actor: str  # "chaos_monkey", "buyer_agent", "policy_gateway", "razorpay_executor"
    summary: str
    data: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "ts": self.ts,
            "trace_id": self.trace_id,
            "kind": self.kind,
            "actor": self.actor,
            "summary": self.summary,
            "data": self.data,
        }
