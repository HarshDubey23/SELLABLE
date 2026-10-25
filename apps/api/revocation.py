"""Durable mission revocation.

Revoking a mission must stop everything it could still pay for, including
approvals issued before the revocation. So the fact lives in SQLite, the
gateway reads it into R8 for new proposals, and the executor re-reads it
at the money boundary, inside the same transaction that opens the
execution row.

Revocation only ever removes authority, so it is idempotent and never
un-revoked here.
"""
from __future__ import annotations

import time

from .store import db as store


def revoke(mission_id: str, reason: str = "", now_ts: int | None = None) -> bool:
    """Revoke a mission. Returns True if this call revoked it, False if it
    was already revoked."""
    now_ts = now_ts if now_ts is not None else int(time.time())
    affected = store.execute_rowcount(
        "INSERT OR IGNORE INTO mission_revocations (mission_id, reason, revoked_at) "
        "VALUES (?, ?, ?)",
        (mission_id, reason[:500], now_ts))
    return affected == 1


def is_revoked(mission_id: str) -> bool:
    return store.query_one(
        "SELECT 1 FROM mission_revocations WHERE mission_id = ?",
        (mission_id,)) is not None
