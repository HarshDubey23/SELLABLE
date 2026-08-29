"""Agent-side mandate CARRIER — simulated wallet boundary (prototype).

For this prototype, the wallet trust boundary is simulated locally as a
separate process (`scripts/mandate.py`). This is NOT a production
multi-device custody model. The buyer agent NEVER holds the wallet key
(USER_MANDATE_KEY); it only shells out to the wallet CLI and reads the
resulting JSON blob. The trace must show `simulated_user`/`wallet_process`
as the actor, never `buyer_agent` as `user`.

In production this would be a separate device / secure enclave / user
confirmation. Here we simulate the consent ceremony locally so the
money path can be exercised end-to-end without a human in the loop.
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
    """Simulated user pre-authorization: wallet CLI (separate process) mints IntentMandate."""
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
    """Simulated user consent: wallet CLI (separate process) signs the final cart."""
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    subprocess.run(
        [sys.executable, str(CLI), "approve-cart",
         "--mission", mission_id, "--cart-hash", cart_hash,
         "--amount-paise", str(amount_paise),
         "--out-dir", str(OUT_DIR)],
        check=True, capture_output=True,
    )
    return json.loads((OUT_DIR / f"{mission_id}_cart_mandate.json").read_text())
