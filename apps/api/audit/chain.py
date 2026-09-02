"""
Append-only hash chain with SQLite persistence.

GENESIS on first use. verify() at boot and on demand.
Disk is truth: append() writes to the DB FIRST, then memory.
If the DB write fails, memory is NOT updated — the two can never diverge.

Entry: {seq, ts, actor, action, payload_hash, prev_hash, hash, ...}
Each entry's hash covers seq|ts|actor|action|payload_hash|prev_hash,
so flipping a single byte anywhere breaks verify() from that point on.

Enriched audit fields (Razorpay-grade trail):
- parent_action_id : links failure -> diagnosis -> recovery in one chain
- idempotency_key  : deterministic replay guard for mutating calls
- error_code / error_reason : Razorpay error surface (payment_declined etc.)
- reasoning_trace  : JSON blob of the agent's (out-of-money-path) reasoning
- mandate_id       : reserved for AP2-style mandates
- review_state     : auto_approved/pending_merchant/approved/rejected/executed
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
    """Load all entries from the audit_chain table into _chain.

    Selects the enriched columns too, so the in-memory mirror matches
    what disk already stores (parent linkage, idempotency, error surface,
    reasoning trace, review state survive a module reload).
    """
    global _chain
    rows = store.query(
        "SELECT seq, ts, actor, action, payload_hash, prev_hash, hash, "
        "parent_action_id, idempotency_key, error_code, error_reason, "
        "reasoning_trace, mandate_id, review_state "
        "FROM audit_chain ORDER BY seq"
    )
    if rows:
        _chain = [dict(r) for r in rows]
    elif not _chain:
        # Fresh database — write GENESIS before anything else can append.
        genesis = _genesis()
        genesis["hash"] = _hash(genesis)
        store.execute(
            "INSERT INTO audit_chain "
            "(seq, ts, actor, action, payload_hash, prev_hash, hash) "
            "VALUES (?, ?, ?, ?, ?, ?, ?)",
            (genesis["seq"], genesis["ts"], genesis["actor"],
             genesis["action"], genesis["payload_hash"],
             genesis["prev_hash"], genesis["hash"])
        )
        _chain = [genesis]


def action_id(seq: int) -> str:
    """Stable external id for an audit row (used by parent_action_id)."""
    return f"aud_{seq}"


def append(actor: str, action: str, payload,
           parent_action_id: str | None = None,
           idempotency_key: str | None = None,
           error_code: str | None = None,
           error_reason: str | None = None,
           reasoning_trace=None,
           mandate_id: str | None = None,
           review_state: str | None = None) -> int:
    """Append an entry. DB write FIRST, then memory. Returns seq."""
    payload_hash = hashlib.sha256(
        json.dumps(payload, sort_keys=True, separators=(",", ":")).encode()
    ).hexdigest()

    trace_json = None
    if reasoning_trace is not None:
        if not isinstance(reasoning_trace, str):
            reasoning_trace = json.dumps(
                reasoning_trace, sort_keys=True, separators=(",", ":"))
        trace_json = reasoning_trace

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
            "(seq, ts, actor, action, payload_hash, prev_hash, hash, "
            " parent_action_id, idempotency_key, error_code, error_reason, "
            " reasoning_trace, mandate_id, review_state) "
            "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
            (entry["seq"], entry["ts"], entry["actor"], entry["action"],
             entry["payload_hash"], entry["prev_hash"], entry["hash"],
             parent_action_id, idempotency_key, error_code, error_reason,
             trace_json, mandate_id, review_state)
        )

        # Only after a successful DB write, update memory.
        entry.update({
            "parent_action_id": parent_action_id,
            "idempotency_key": idempotency_key,
            "error_code": error_code,
            "error_reason": error_reason,
            "reasoning_trace": trace_json,
            "mandate_id": mandate_id,
            "review_state": review_state,
        })
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


def find_by_action_id(aid: str) -> dict | None:
    """Resolve an aud_<seq> id back to its chain entry."""
    if not aid or not aid.startswith("aud_"):
        return None
    try:
        seq = int(aid[4:])
    except ValueError:
        return None
    for e in _chain:
        if e["seq"] == seq:
            return e
    return None


def _load_entries(db_path: str) -> list[dict]:
    """Load audit_chain entries from a specific DB file for offline verification."""
    import sqlite3
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    rows = conn.execute(
        "SELECT seq, ts, actor, action, payload_hash, prev_hash, hash "
        "FROM audit_chain ORDER BY seq"
    ).fetchall()
    conn.close()
    return [dict(r) for r in rows] if rows else []


def verify(db_path: str | None = None) -> bool:
    """Recompute every hash from GENESIS. One flipped byte => False.

    If db_path is given, verify that file's chain instead of the live in-memory chain.
    The live database is never touched by this parameter path.

    Strict genesis enforcement:
    - seq 0 MUST exist
    - action MUST be "GENESIS"
    - prev_hash MUST be "0" * 64
    - hash MUST match _hash(genesis_entry)
    """
    entries_to_check = _load_entries(db_path) if db_path else _chain
    if not entries_to_check:
        return True
    # Genesis must be first entry
    genesis = entries_to_check[0]
    if genesis["seq"] != 0:
        return False
    if genesis["action"] != "GENESIS":
        return False
    if genesis["prev_hash"] != "0" * 64:
        return False
    expected_genesis_hash = _hash(genesis)
    if genesis.get("hash") != expected_genesis_hash:
        return False

    prev = genesis["hash"]
    for e in entries_to_check[1:]:
        if e["seq"] == 0:
            return False  # duplicate genesis — tampered
        expected = _hash(e)
        if e.get("hash") and e["hash"] != expected:
            return False
        if e["prev_hash"] != prev:
            return False
        prev = e.get("hash", expected)
    return True


def verify_strict(db_path: str | None = None) -> tuple[bool, str]:
    """Like verify(), but returns (ok, reason) for diagnostics."""
    entries_to_check = _load_entries(db_path) if db_path else _chain
    if not entries_to_check:
        return True, "empty chain (ok)"
    genesis = entries_to_check[0]
    if genesis["seq"] != 0:
        return False, f"first entry has seq={genesis['seq']}, expected 0"
    if genesis["action"] != "GENESIS":
        return False, f"first entry action={genesis['action']!r}, expected GENESIS"
    if genesis["prev_hash"] != "0" * 64:
        return False, "genesis prev_hash is not all-zeros"
    if genesis.get("hash") != _hash(genesis):
        return False, "genesis hash mismatch"
    prev = genesis["hash"]
    for e in entries_to_check[1:]:
        expected = _hash(e)
        if e.get("hash") != expected:
            return False, f"seq {e['seq']}: hash mismatch"
        if e["prev_hash"] != prev:
            return False, f"seq {e['seq']}: prev_hash mismatch (chain broken)"
        prev = e["hash"]
    return True, "ok"


def tail(n: int = 10) -> list[dict]:
    return _chain[-n:]


# Load the existing chain from the DB on module import.
_load_from_db()
