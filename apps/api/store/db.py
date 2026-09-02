"""
SQLite persistence layer for SELLABLE.

Stdlib only (sqlite3). Thread-safe for uvicorn's threaded handlers.
Every piece of state that must survive a restart lives here:

- audit_chain     : the append-only hash chain (disk is truth)
- webhook_events  : every verified webhook event (dedup + ledger rebuild)
- orders          : real Razorpay orders with their APPROVE bindings
- quotes          : signed price locks
- verdicts        : gateway verdicts, incl. the reason string

One connection per call keeps this dead simple and safe; WAL mode gives
concurrent readers while the single writer holds the lock.
"""
import os
import sqlite3
import threading
from pathlib import Path
from typing import Any

# Database path: repo_root/data/sellable.db
# Override with SELLABLE_DB_PATH (tests use a throwaway file so unit runs
# never pollute production state).
_DB_PATH = Path(
    os.environ.get(
        "SELLABLE_DB_PATH",
        str(Path(__file__).resolve().parents[3] / "data" / "sellable.db"),
    )
)
_lock = threading.Lock()


def _connect() -> sqlite3.Connection:
    _DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(str(_DB_PATH), check_same_thread=False)
    conn.execute("PRAGMA journal_mode=WAL")
    conn.row_factory = sqlite3.Row
    return conn


def init_schema() -> None:
    """Idempotent schema creation. Safe to call multiple times."""
    with _lock:
        conn = _connect()
        try:
            conn.executescript("""
                CREATE TABLE IF NOT EXISTS audit_chain (
                    seq INTEGER PRIMARY KEY,
                    ts INTEGER NOT NULL,
                    actor TEXT NOT NULL,
                    action TEXT NOT NULL,
                    payload_hash TEXT NOT NULL,
                    prev_hash TEXT NOT NULL,
                    hash TEXT NOT NULL
                );
                CREATE TABLE IF NOT EXISTS webhook_events (
                    event_id TEXT PRIMARY KEY,
                    event_type TEXT,
                    order_id TEXT,
                    payment_id TEXT,
                    amount_paise INTEGER,
                    status TEXT,
                    received_at INTEGER NOT NULL
                );
                CREATE TABLE IF NOT EXISTS bindings (
                    seq INTEGER PRIMARY KEY,
                    mission_id TEXT NOT NULL,
                    proposal_hash TEXT NOT NULL,
                    cart_hash TEXT NOT NULL,
                    quote_id TEXT NOT NULL,
                    amount_paise INTEGER NOT NULL,
                    currency TEXT NOT NULL,
                    skus TEXT NOT NULL,
                    mandate_version TEXT NOT NULL,
                    issued_at INTEGER NOT NULL,
                    expires_at INTEGER NOT NULL,
                    consumed_at INTEGER
                );
                CREATE TABLE IF NOT EXISTS orders (
                    order_id TEXT PRIMARY KEY,
                    idempotency_key TEXT UNIQUE,
                    amount_paise INTEGER NOT NULL,
                    status TEXT NOT NULL,
                    quote_id TEXT,
                    mission_id TEXT,
                    proposal_hash TEXT,
                    approve_seq INTEGER,
                    created_at INTEGER NOT NULL
                );
                CREATE TABLE IF NOT EXISTS quotes (
                    quote_id TEXT PRIMARY KEY,
                    mission_id TEXT,
                    items TEXT NOT NULL,
                    total_paise INTEGER NOT NULL,
                    expires_at INTEGER NOT NULL,
                    signature TEXT NOT NULL,
                    created_at INTEGER NOT NULL
                );
                CREATE TABLE IF NOT EXISTS verdicts (
                    seq INTEGER PRIMARY KEY,
                    decision TEXT NOT NULL,
                    rule_id TEXT,
                    reason TEXT,
                    proposal_hash TEXT NOT NULL,
                    mission_id TEXT,
                    created_at INTEGER NOT NULL
                );
                CREATE INDEX IF NOT EXISTS idx_orders_idem
                    ON orders(idempotency_key);
                CREATE INDEX IF NOT EXISTS idx_events_order
                    ON webhook_events(order_id);
            """)
            conn.commit()
        finally:
            conn.close()
    # Outside the lock: _migrate_audit_columns takes the lock itself
    # (threading.Lock is NOT reentrant — calling it inside would deadlock).
    _migrate_audit_columns()


_AUDIT_EXTRA_COLUMNS = {
    "parent_action_id": "TEXT",
    "idempotency_key": "TEXT",
    "error_code": "TEXT",
    "error_reason": "TEXT",
    "reasoning_trace": "TEXT",
    "mandate_id": "TEXT",
    "review_state": "TEXT",
}


def _migrate_audit_columns() -> None:
    """Add enriched audit columns to pre-existing tables (idempotent)."""
    with _lock:
        conn = _connect()
        try:
            existing = {
                row["name"] for row in
                conn.execute("PRAGMA table_info(audit_chain)").fetchall()
            }
            for col, coltype in _AUDIT_EXTRA_COLUMNS.items():
                if col not in existing:
                    conn.execute(
                        f"ALTER TABLE audit_chain ADD COLUMN {col} {coltype}"
                    )
            conn.commit()
        finally:
            conn.close()


def execute(sql: str, params: tuple = ()) -> int:
    """Execute a write statement. Returns lastrowid. Thread-safe."""
    with _lock:
        conn = _connect()
        try:
            cur = conn.execute(sql, params)
            conn.commit()
            return cur.lastrowid or 0
        finally:
            conn.close()


def execute_rowcount(sql: str, params: tuple = ()) -> int:
    """Execute a write statement. Returns rowcount (number of rows affected). Thread-safe."""
    with _lock:
        conn = _connect()
        try:
            cur = conn.execute(sql, params)
            conn.commit()
            return cur.rowcount
        finally:
            conn.close()


def query(sql: str, params: tuple = ()) -> list[dict[str, Any]]:
    """Execute a read statement. Returns list of dicts. Thread-safe."""
    with _lock:
        conn = _connect()
        try:
            cur = conn.execute(sql, params)
            return [dict(row) for row in cur.fetchall()]
        finally:
            conn.close()


def query_one(sql: str, params: tuple = ()) -> dict[str, Any] | None:
    """Execute a read, return first row or None."""
    rows = query(sql, params)
    return rows[0] if rows else None


def db_path() -> str:
    return str(_DB_PATH)


# Initialize schema on import
init_schema()
