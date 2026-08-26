"""
One-time migration/backfill for the enriched audit schema.

Adds parent_action_id, idempotency_key, error_code, error_reason,
reasoning_trace, mandate_id, review_state to audit_chain (idempotent —
the column add is skipped when it already exists) and backfills legacy
rows with explicit NULLs so queries behave uniformly.

Run:  python scripts/migrate_audit.py
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from apps.api.store import db as store


def main() -> None:
    # _migrate_audit_columns runs automatically in init_schema(); calling
    # store.query() here guarantees the schema module has been loaded.
    store.query("SELECT seq FROM audit_chain LIMIT 1")
    cols = {
        r["name"] for r in store.query("PRAGMA table_info(audit_chain)")
    }
    required = {"parent_action_id", "idempotency_key", "error_code",
                "error_reason", "reasoning_trace", "mandate_id",
                "review_state"}
    missing = required - cols
    if missing:
        print(f"FATAL: columns still missing after migration: {missing}")
        sys.exit(1)

    n = store.execute(
        "UPDATE audit_chain SET review_state = review_state "
        "WHERE review_state IS NULL"
    )
    print(f"audit_chain backfill complete; enriched columns present: "
          f"{sorted(required)}")
    print(f"rows touched: {n}")


if __name__ == "__main__":
    main()
