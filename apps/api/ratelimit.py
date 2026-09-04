"""A small in-process token bucket for the publicly reachable demo routes.

Scope, stated plainly: this is per-process and in-memory. It stops a
reviewer's held-down Enter key and a casual script from hammering the
attack lab; it is not a defence against a distributed attacker, and it
resets when the process restarts. Anything stronger belongs in front of
the app, not inside it.

It is here because /attack/custom, /attack/gauntlet and the tamper demo
are unauthenticated by design — a reviewer must be able to attack the
system without being issued a key first — and an unauthenticated route
that does real work needs a ceiling.
"""
from __future__ import annotations

import threading
import time

_lock = threading.Lock()
_buckets: dict[tuple[str, str], list[float]] = {}


def allow(client: str, *, bucket: str, limit: int,
          per_seconds: int = 60, now: float | None = None) -> bool:
    """True when `client` may make another call to `bucket`.

    A plain sliding window: keep the timestamps inside the window and
    compare the count. At these limits the list never grows enough for
    the O(n) prune to matter.
    """
    now = time.monotonic() if now is None else now
    key = (bucket, client or "unknown")
    with _lock:
        hits = [t for t in _buckets.get(key, []) if now - t < per_seconds]
        if len(hits) >= limit:
            _buckets[key] = hits
            return False
        hits.append(now)
        _buckets[key] = hits
        return True


def retry_after(client: str, *, bucket: str, per_seconds: int = 60,
                now: float | None = None) -> int:
    """Whole seconds until the oldest hit in the window falls out."""
    now = time.monotonic() if now is None else now
    with _lock:
        hits = _buckets.get((bucket, client or "unknown"), [])
        if not hits:
            return 0
        return max(0, int(per_seconds - (now - min(hits))) + 1)


def reset() -> None:
    """Tests only."""
    with _lock:
        _buckets.clear()
