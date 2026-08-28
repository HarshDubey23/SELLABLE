"""Agent-side mandate CARRIER. Never signs. Never holds the wallet key.

Mirrors the Day-4 mission-signer custody split: minting happens in a
separate process (`scripts/mandate.py`). This module only shells out to
that CLI and reads the resulting JSON blob.
"""
from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
CLI = ROOT / "scripts" / "mandate.py"
OUT_DIR = ROOT / "missions"


def carry_intent(mission_id: str, ceiling_paise: int) -> dict:
    """USER PRE-AUTHORIZATION (out-of-band): wallet CLI mints IntentMandate."""
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    subprocess.run(
        [sys.executable, str(CLI), "issue-intent",
         "--mission", mission_id, "--user", f"user_{mission_id}",
         "--ceiling-paise", str(ceiling_paise), "--expiry-hours", "24",
         "--out-dir", str(OUT_DIR)],
        check=True, capture_output=True,
    )
    return json.loads((OUT_DIR / f"{mission_id}_intent_mandate.json").read_text())


def carry_cart_consent(mission_id: str, cart_hash: str, amount_paise: int) -> dict:
    """USER CONSENT STEP (out-of-band): wallet CLI signs the final cart."""
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    subprocess.run(
        [sys.executable, str(CLI), "approve-cart",
         "--mission", mission_id, "--cart-hash", cart_hash,
         "--amount-paise", str(amount_paise),
         "--out-dir", str(OUT_DIR)],
        check=True, capture_output=True,
    )
    return json.loads((OUT_DIR / f"{mission_id}_cart_mandate.json").read_text())
