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
import time
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
                    consumed_at INTEGER,
                    merchant_id TEXT,
                    negotiation_transcript_hash TEXT
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
                    created_at INTEGER NOT NULL,
                    negotiated_json TEXT
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
                CREATE TABLE IF NOT EXISTS payment_executions (
                    execution_id TEXT PRIMARY KEY,
                    mission_id TEXT NOT NULL,
                    approve_seq INTEGER NOT NULL,
                    proposal_hash TEXT NOT NULL,
                    quote_id TEXT NOT NULL,
                    amount_paise INTEGER NOT NULL,
                    currency TEXT NOT NULL,
                    idempotency_key TEXT NOT NULL,
                    state TEXT NOT NULL,
                    provider TEXT NOT NULL,
                    remote_order_id TEXT,
                    remote_error_code TEXT,
                    attempts INTEGER NOT NULL DEFAULT 0,
                    last_error TEXT,
                    created_at INTEGER NOT NULL,
                    updated_at INTEGER NOT NULL,
                    reconciled_at INTEGER,
                    terminal_at INTEGER
                );
                CREATE TABLE IF NOT EXISTS growth_actions (
                    action_id TEXT PRIMARY KEY,
                    title TEXT NOT NULL,
                    base_sku TEXT NOT NULL,
                    bundle_skus TEXT NOT NULL,
                    proposed_price_paise INTEGER NOT NULL,
                    baseline_aov_paise INTEGER NOT NULL,
                    status TEXT NOT NULL,
                    approved_at INTEGER,
                    deployed_at INTEGER,
                    created_at INTEGER NOT NULL
                );
                -- SELLABLE Market. Declared here with every other table so
                -- a fresh database - a clone, a test tmpdir - has them from
                -- the first boot. The market modules also call their own
                -- CREATE IF NOT EXISTS, which is harmless and keeps them
                -- usable in isolation.
                CREATE TABLE IF NOT EXISTS market_merchants (
                    merchant_id TEXT PRIMARY KEY,
                    version INTEGER NOT NULL,
                    manifest_json TEXT NOT NULL,
                    signature TEXT NOT NULL,
                    seeded_at INTEGER NOT NULL
                );
                CREATE TABLE IF NOT EXISTS market_negotiations (
                    negotiation_id TEXT PRIMARY KEY,
                    state TEXT NOT NULL,
                    mission_text TEXT NOT NULL,
                    mission_id TEXT NOT NULL,
                    budget_paise INTEGER NOT NULL,
                    basket_json TEXT NOT NULL,
                    weights_json TEXT NOT NULL,
                    planner_json TEXT NOT NULL,
                    current_round INTEGER NOT NULL DEFAULT 0,
                    winner_merchant_id TEXT,
                    winner_offer_id TEXT,
                    transcript_hash TEXT,
                    parent_negotiation_id TEXT,
                    override_of TEXT,
                    -- The settlement claim. Set once, by whichever caller
                    -- wins the conditional UPDATE; everyone else replays
                    -- the authorization recorded here instead of minting
                    -- a second one.
                    settlement_approve_seq INTEGER,
                    settlement_quote_id TEXT,
                    settlement_proposal_hash TEXT,
                    settled_at INTEGER,
                    created_at INTEGER NOT NULL,
                    updated_at INTEGER NOT NULL,
                    expires_at INTEGER NOT NULL,
                    last_error TEXT
                );
                -- offer_id is the PRIMARY KEY on purpose: it is derived
                -- deterministically from (negotiation, merchant, round), so a
                -- replayed round collides here and is refused by the database
                -- rather than by a check someone can forget to write.
                CREATE TABLE IF NOT EXISTS market_offers (
                    offer_id TEXT PRIMARY KEY,
                    negotiation_id TEXT NOT NULL,
                    merchant_id TEXT NOT NULL,
                    round INTEGER NOT NULL,
                    intent_json TEXT NOT NULL,
                    verdict_json TEXT NOT NULL,
                    accepted INTEGER NOT NULL,
                    reason TEXT,
                    total_paise INTEGER,
                    provenance_json TEXT NOT NULL,
                    created_at INTEGER NOT NULL
                );
                CREATE TABLE IF NOT EXISTS market_counters (
                    counter_id TEXT PRIMARY KEY,
                    negotiation_id TEXT NOT NULL,
                    merchant_id TEXT NOT NULL,
                    round INTEGER NOT NULL,
                    ask TEXT NOT NULL,
                    note TEXT,
                    created_at INTEGER NOT NULL
                );
                CREATE INDEX IF NOT EXISTS idx_market_offers_neg
                    ON market_offers(negotiation_id);
                CREATE INDEX IF NOT EXISTS idx_market_neg_state
                    ON market_negotiations(state);
                CREATE INDEX IF NOT EXISTS idx_orders_idem
                    ON orders(idempotency_key);
                CREATE INDEX IF NOT EXISTS idx_events_order
                    ON webhook_events(order_id);
                CREATE INDEX IF NOT EXISTS idx_exec_state
                    ON payment_executions(state);
                CREATE INDEX IF NOT EXISTS idx_exec_mission
                    ON payment_executions(mission_id);
            """)
            conn.commit()
        finally:
            conn.close()
    # Outside the lock: the migrators take the lock themselves
    # (threading.Lock is NOT reentrant — calling it inside would deadlock).
    _migrate_audit_columns()
    _migrate_webhook_columns()
    _migrate_binding_columns()
    _migrate_quote_columns()
    _migrate_market_columns()


_MARKET_NEG_EXTRA_COLUMNS = {
    "settlement_approve_seq": "INTEGER",
    "settlement_quote_id": "TEXT",
    "settlement_proposal_hash": "TEXT",
    "settled_at": "INTEGER",
}

_QUOTE_EXTRA_COLUMNS = {
    # The negotiated facts a market quote carries: which merchant won and
    # the transcript hash that binding pins. NULL on every other quote.
    "negotiated_json": "TEXT",
}

_BINDING_EXTRA_COLUMNS = {
    # The market extension. Both stay NULL for every non-market binding,
    # which is what keeps this additive: a flow that never negotiated has
    # nothing to pin, and the executor skips a check it has no subject for.
    "merchant_id": "TEXT",
    "negotiation_transcript_hash": "TEXT",
}

_WEBHOOK_EXTRA_COLUMNS = {
    # Durable webhook lifecycle: RECEIVED -> AUDITED -> APPLIED.
    # A crash between persistence and audit must NOT look like a completed
    # event on the next boot, so processing_state is tracked on disk.
    "processing_state": "TEXT",
    "applied_at": "INTEGER",
}

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


def _migrate_binding_columns() -> None:
    """Add the market fields to the binding (idempotent).

    A database written before the market existed keeps working: the new
    columns read NULL, and a binding with nothing pinned is exactly what
    a pre-market approval was.
    """
    with _lock:
        conn = _connect()
        try:
            existing = {
                row["name"] for row in
                conn.execute("PRAGMA table_info(bindings)").fetchall()
            }
            for col, coltype in _BINDING_EXTRA_COLUMNS.items():
                if col not in existing:
                    conn.execute(
                        f"ALTER TABLE bindings ADD COLUMN {col} {coltype}"
                    )
            conn.commit()
        finally:
            conn.close()


def _migrate_market_columns() -> None:
    """Add the settlement claim columns to market_negotiations (idempotent)."""
    with _lock:
        conn = _connect()
        try:
            existing = {
                row["name"] for row in
                conn.execute(
                    "PRAGMA table_info(market_negotiations)").fetchall()
            }
            if not existing:
                return  # table not created yet; the DDL above will carry it
            for col, coltype in _MARKET_NEG_EXTRA_COLUMNS.items():
                if col not in existing:
                    conn.execute(
                        f"ALTER TABLE market_negotiations "
                        f"ADD COLUMN {col} {coltype}"
                    )
            conn.commit()
        finally:
            conn.close()


def _migrate_quote_columns() -> None:
    """Add the negotiated-quote column (idempotent)."""
    with _lock:
        conn = _connect()
        try:
            existing = {
                row["name"] for row in
                conn.execute("PRAGMA table_info(quotes)").fetchall()
            }
            for col, coltype in _QUOTE_EXTRA_COLUMNS.items():
                if col not in existing:
                    conn.execute(
                        f"ALTER TABLE quotes ADD COLUMN {col} {coltype}"
                    )
            conn.commit()
        finally:
            conn.close()


def _migrate_webhook_columns() -> None:
    """Add the durable webhook lifecycle columns (idempotent)."""
    with _lock:
        conn = _connect()
        try:
            existing = {
                row["name"] for row in
                conn.execute("PRAGMA table_info(webhook_events)").fetchall()
            }
            for col, coltype in _WEBHOOK_EXTRA_COLUMNS.items():
                if col not in existing:
                    conn.execute(
                        f"ALTER TABLE webhook_events ADD COLUMN {col} {coltype}"
                    )
            # Rows written before this migration were only ever marked seen
            # after audit+apply succeeded, so treating them as APPLIED is
            # accurate for historical data.
            conn.execute(
                "UPDATE webhook_events SET processing_state = 'APPLIED' "
                "WHERE processing_state IS NULL"
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


def save_growth_action(action: dict[str, Any]) -> None:
    """Save or update a merchant growth action recommendation."""
    execute(
        """INSERT OR REPLACE INTO growth_actions
           (action_id, title, base_sku, bundle_skus, proposed_price_paise,
            baseline_aov_paise, status, approved_at, deployed_at, created_at)
           VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
        (
            action["action_id"],
            action["title"],
            action["base_sku"],
            action["bundle_skus"],
            action["proposed_price_paise"],
            action["baseline_aov_paise"],
            action.get("status", "PENDING"),
            action.get("approved_at"),
            action.get("deployed_at"),
            action.get("created_at", int(time.time())),
        ),
    )


def approve_growth_action(action_id: str) -> bool:
    """Merchant approves and deploys a growth action."""
    import time
    now_ts = int(time.time())
    count = execute(
        "UPDATE growth_actions SET status = 'APPROVED', approved_at = ?, deployed_at = ? WHERE action_id = ?",
        (now_ts, now_ts, action_id),
    )
    return count > 0


def get_growth_action(action_id: str) -> dict[str, Any] | None:
    """Retrieve a specific growth action by ID."""
    return query_one("SELECT * FROM growth_actions WHERE action_id = ?", (action_id,))


def list_growth_actions() -> list[dict[str, Any]]:
    """List all growth actions ordered by creation timestamp descending."""
    return query("SELECT * FROM growth_actions ORDER BY created_at DESC")



# Initialize schema on import
init_schema()
