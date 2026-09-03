"""Unified Event Broadcaster and SSE Manager for Chaos Control Room."""
from __future__ import annotations

import asyncio
import json
import time
from collections.abc import AsyncGenerator
from typing import Any

from .types import ChaosEvent


class EventBroadcaster:
    """Manages live SSE subscriber queues and historical event buffer."""

    def __init__(self, max_history: int = 1000):
        self._history: list[ChaosEvent] = []
        self._subscribers: set[asyncio.Queue] = set()
        self._max_history = max_history

    def emit(
        self,
        kind: str,
        actor: str,
        summary: str,
        trace_id: str = "t-system",
        data: dict[str, Any] | None = None,
        now_ts: float | None = None,
    ) -> ChaosEvent:
        event = ChaosEvent(
            ts=now_ts if now_ts is not None else time.time(),
            trace_id=trace_id,
            kind=kind,
            actor=actor,
            summary=summary,
            data=data or {},
        )
        self._history.append(event)
        if len(self._history) > self._max_history:
            self._history.pop(0)

        # Notify active SSE queues
        dead_queues = set()
        for q in self._subscribers:
            try:
                q.put_nowait(event)
            except Exception:
                dead_queues.add(q)

        for q in dead_queues:
            self._subscribers.discard(q)

        return event

    def subscribe(self) -> asyncio.Queue:
        q: asyncio.Queue = asyncio.Queue()
        self._subscribers.add(q)
        return q

    def unsubscribe(self, q: asyncio.Queue) -> None:
        self._subscribers.discard(q)

    def get_history(self, limit: int = 200, trace_id: str | None = None) -> list[dict[str, Any]]:
        evs = self._history
        if trace_id:
            evs = [e for e in evs if e.trace_id == trace_id]
        return [e.to_dict() for e in evs[-limit:]]

    def clear(self) -> None:
        self._history.clear()


# Global event bus singleton
event_bus = EventBroadcaster()


async def sse_event_generator(q: asyncio.Queue) -> AsyncGenerator[str, None]:
    """Generates SSE text/event-stream chunks."""
    try:
        # First send historical replay batch so new subscribers catch up immediately
        for ev in event_bus.get_history(limit=50):
            yield f"data: {json.dumps(ev)}\n\n"

        while True:
            ev: ChaosEvent = await q.get()
            yield f"data: {json.dumps(ev.to_dict())}\n\n"
    except asyncio.CancelledError:
        event_bus.unsubscribe(q)
        raise
