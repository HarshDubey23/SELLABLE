"""Append-only hash chain. GENESIS on first use. verify() at boot.

In-memory for Day 2 (honest: demo scale). JSONL persistence + halt-on-tamper
wiring into the request path lands with the full gateway on Day 3.
"""
import hashlib
import json
import threading
import time

_lock = threading.Lock()
_chain = []          # list of entry dicts


def _hash(entry: dict) -> str:
    raw = f"{entry['seq']}|{entry['ts']}|{entry['actor']}|{entry['action']}|" \
          f"{entry['payload_hash']}|{entry['prev_hash']}"
    return hashlib.sha256(raw.encode()).hexdigest()


def _genesis():
    return {"seq": 0, "ts": 0, "actor": "system", "action": "GENESIS",
            "payload_hash": hashlib.sha256(b"GENESIS").hexdigest(),
            "prev_hash": "0" * 64}


if not _chain:
    _chain.append(_genesis())


def append(actor: str, action: str, payload) -> int:
    payload_hash = hashlib.sha256(
        json.dumps(payload, sort_keys=True, separators=(",", ":")).encode()
    ).hexdigest()
    with _lock:
        prev = _chain[-1]
        entry = {"seq": prev["seq"] + 1, "ts": _now(), "actor": actor,
                 "action": action, "payload_hash": payload_hash,
                 "prev_hash": _head_hash()}
        entry["hash"] = _hash(entry)
        _chain.append(entry)
        return entry["seq"]


def _head_hash() -> str:
    head = _chain[-1]
    if "hash" not in head:
        head["hash"] = _hash(head)
    return head["hash"]


def _now() -> int:
    return int(time.time())


def entries() -> list:
    return list(_chain)


def verify() -> bool:
    """Recompute every hash from GENESIS. One flipped byte => False."""
    prev = "0" * 64
    for e in _chain:
        if e["seq"] == 0:
            if e["action"] != "GENESIS":
                return False
        expected = _hash(e)
        if e.get("hash") and e["hash"] != expected:
            return False
        if e["prev_hash"] != prev:
            return False
        prev = e.get("hash", expected)
    return True


def tail(n: int = 10) -> list:
    return _chain[-n:]
