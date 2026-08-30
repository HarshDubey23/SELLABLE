"""
Protocol Trace — every action in a buyer agent mission, recorded.

These events power the Mission Control visualization and give judges a
step-by-step, replayable story of one agentic purchase: discovery,
search, reasoning, gateway verdicts, upsell negotiation, order, payment.
"""
import time
from dataclasses import dataclass


@dataclass
class TraceEvent:
    """A single event in the buyer-agent-to-merchant protocol."""
    ts: float           # time.time() when the event occurred
    seq: int            # monotonically increasing within a mission
    actor: str          # who did it
    action: str         # what they did
    summary: str        # one-line human-readable description
    data: dict          # full structured payload (JSON-serializable)
    used_fallback: bool = False   # True when this event's outcome came from
                                  # the deterministic fallback, not the LLM


class MissionTrace:
    """Collects trace events for one mission run."""

    def __init__(self, mission_id: str):
        self.mission_id = mission_id
        self.events: list[TraceEvent] = []
        self._seq = 0

    def emit(self, actor: str, action: str, summary: str,
             data: dict | None = None,
             used_fallback: bool = False) -> TraceEvent:
        """Record an event and return it."""
        self._seq += 1
        event = TraceEvent(
            ts=time.time(),
            seq=self._seq,
            actor=actor,
            action=action,
            summary=summary,
            data=data or {},
            used_fallback=used_fallback,
        )
        self.events.append(event)
        return event

    def to_dict(self) -> dict:
        """Serialize for JSON response."""
        return {
            "mission_id": self.mission_id,
            "event_count": len(self.events),
            "events": [
                {
                    "ts": e.ts,
                    "seq": e.seq,
                    "actor": e.actor,
                    "action": e.action,
                    "summary": e.summary,
                    "data": e.data,
                    "used_fallback": e.used_fallback,
                }
                for e in self.events
            ],
        }
