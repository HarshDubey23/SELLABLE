"""
Append-only hash chain with SQLite persistence.

GENESIS on first use. verify() at boot and on demand.
Disk is truth: append() writes to the DB FIRST, then memory.
If the DB write fails, memory is NOT updated — the two can never diverge.

Entry: {seq, ts, actor, action, payload_hash, prev_hash, hash}
Each entry's hash covers seq|ts|actor|action|payload_hash|prev_hash,
so flipping a single byte anywhere breaks verify() from that point on.
"""
import hashlib
import json
import threading
import time

from ..store import db as store

_lock = threading.Lock()
_chain: list[dict] = []  # in-memory mirror of the audit_chain table


def _hash(entry: dict) -> str:
    raw = f"{entry['seq']}|{entry['ts']}|{entry['actor']}|{entry['action']}|" \
          f"{entry['payload_hash']}|{entry['prev_hash']}"
    return hashlib.sha256(raw.encode()).hexdigest()


def _genesis() -> dict:
    return {
        "seq": 0, "ts": 0, "actor": "system", "action": "GENESIS",
        "payload_hash": hashlib.sha256(b"GENESIS").hexdigest(),
        "prev_hash": "0" * 64,
    }


def _load_from_db() -> None:
    """Load all entries from the audit_chain table into _chain."""
    global _chain
    rows = store.query(
        "SELECT seq, ts, actor, action, payload_hash, prev_hash, hash "
        "FROM audit_chain ORDER BY seq"
    )
    if rows:
        _chain = [dict(r) for r in rows]
    elif not _chain:
        # Fresh database — write GENESIS before anything else can append.
        genesis = _genesis()
        genesis["hash"] = _hash(genesis)
        store.execute(
            "INSERT OR IGNORE INTO audit_chain "
            "(seq, ts, actor, action, payload_hash, prev_hash, hash) "
            "VALUES (?, ?, ?, ?, ?, ?, ?)",
            (genesis["seq"], genesis["ts"], genesis["actor"],
             genesis["action"], genesis["payload_hash"],
             genesis["prev_hash"], genesis["hash"])
        )
        _chain = [genesis]


def append(actor: str, action: str, payload) -> int:
    """Append an entry. DB write FIRST, then memory. Returns seq."""
    payload_hash = hashlib.sha256(
        json.dumps(payload, sort_keys=True, separators=(",", ":")).encode()
    ).hexdigest()

    with _lock:
        prev = _chain[-1] if _chain else _genesis()
        entry = {
            "seq": prev["seq"] + 1,
            "ts": int(time.time()),
            "actor": actor,
            "action": action,
            "payload_hash": payload_hash,
            "prev_hash": _head_hash(),
        }
        entry["hash"] = _hash(entry)

        # DB write FIRST — if this raises, memory stays unchanged.
        store.execute(
            "INSERT INTO audit_chain "
            "(seq, ts, actor, action, payload_hash, prev_hash, hash) "
            "VALUES (?, ?, ?, ?, ?, ?, ?)",
            (entry["seq"], entry["ts"], entry["actor"], entry["action"],
             entry["payload_hash"], entry["prev_hash"], entry["hash"])
        )

        # Only after a successful DB write, update memory.
        _chain.append(entry)
        return entry["seq"]


def _head_hash() -> str:
    if not _chain:
        return "0" * 64
    head = _chain[-1]
    if "hash" not in head:
        head["hash"] = _hash(head)
    return head["hash"]


def entries() -> list[dict]:
    return list(_chain)


def verify() -> bool:
    """Recompute every hash from GENESIS. One flipped byte => False."""
    if not _chain:
        return True
    prev = "0" * 64
    for e in _chain:
        if e["seq"] == 0 and e["action"] != "GENESIS":
            return False
        expected = _hash(e)
        if e.get("hash") and e["hash"] != expected:
            return False
        if e["prev_hash"] != prev:
            return False
        prev = e.get("hash", expected)
    return True


def tail(n: int = 10) -> list[dict]:
    return _chain[-n:]


# Load the existing chain from the DB on module import.
_load_from_db()
