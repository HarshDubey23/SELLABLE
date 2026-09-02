# -*- coding: utf-8 -*-
"""
scripts/clean_start.py — Safe Clean-Room Reset Script

Resets development/evaluation SQLite state and initializes fresh genesis block.
Does NOT touch sensitive configuration or test credentials.
"""
import sys
import os
import shutil
from pathlib import Path

# Add project root to path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from apps.api.store import db as store
from apps.api.audit import chain as audit_chain

def clean_start():
    print("[Clean-Start] Resetting local evaluation database...")
    db_p = Path(store.db_path())
    
    # Remove db files
    for suffix in ["", "-wal", "-shm"]:
        f = Path(str(db_p) + suffix)
        if f.exists():
            try:
                f.unlink()
                print(f"  Removed: {f.name}")
            except Exception as e:
                print(f"  Warning: could not remove {f.name}: {e}")

    # Re-init schema and chain
    store.init_schema()
    audit_chain._load_from_db()
    
    entries = audit_chain.entries()
    chain_ok = audit_chain.verify()
    print("[Clean-Start] Verification:")
    print(f"  Audit Total Blocks    : {len(entries)}")
    if entries:
        print(f"  Audit Genesis Block   : {entries[0]['hash'][:16]}...")
    print(f"  Audit Chain Integrity : {'VALID' if chain_ok else 'FAIL'}")
    print("[Clean-Start] Database clean and ready for verification.")

if __name__ == "__main__":
    clean_start()
