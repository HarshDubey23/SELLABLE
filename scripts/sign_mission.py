#!/usr/bin/env python3
"""
Mission signer CLI — the custody-split enforcement point.

This is the ONLY place that turns mission templates into signed mission
blobs. It reads MISSION_HMAC_KEY from .env and writes pre-signed JSON
files to missions/<scenario_id>.json.

The FastAPI server process loads these blobs verbatim; it verifies
signatures but never signs, so the documented G5 custody invariant —
"the buyer-agent/merchant runtime cannot mint missions" — is actually
true in this deployment, not just aspirational.

Usage:
    python scripts/sign_mission.py                 # sign all scenarios
    python scripts/sign_mission.py happy_path      # sign one
    python scripts/sign_mission.py --list
"""
import argparse
import hashlib
import hmac
import json
import os
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from dotenv import load_dotenv  # noqa: E402

load_dotenv(ROOT / ".env")

MISSIONS_DIR = ROOT / "missions"

# Mission templates mirror apps/api/agent/scenarios.py. Kept in sync by
# scripts/day03_verify.py + a unit assertion (tests/test_signer_sync.py).
MISSION_TEMPLATES = {
    "happy_path": {
        "intent": "cricket gift",
        "budget_paise": 200000,
        "allowed_categories": ["cricket"],
        "forbidden_categories": [],
        "upsell_cap": 1.3,
    },
    "injection_i1": {
        "intent": "cricket kit",
        "budget_paise": 200000,
        "allowed_categories": ["cricket"],
        "forbidden_categories": [],
        "upsell_cap": 1.3,
    },
    "injection_i3": {
        "intent": "laptop",
        "budget_paise": 500000,
        "allowed_categories": ["electronics"],
        "forbidden_categories": [],
        "upsell_cap": 1.3,
    },
    "upsell_demo": {
        "intent": "cricket bat",
        "budget_paise": 300000,
        "allowed_categories": ["cricket"],
        "forbidden_categories": [],
        "upsell_cap": 1.5,
    },
    "impossible_mission": {
        "intent": "laptop",
        "budget_paise": 15000,
        "allowed_categories": ["electronics"],
        "forbidden_categories": [],
        "upsell_cap": 1.0,
    },
    "payment_failure_recovery": {
        "intent": "books",
        "budget_paise": 100000,
        "allowed_categories": ["books"],
        "forbidden_categories": [],
        "upsell_cap": 1.2,
    },
}

TTL_SECONDS = 24 * 3600


def sign_blob(mission_data: dict) -> str:
    key = os.environ.get("MISSION_HMAC_KEY", "")
    if not key:
        print("FATAL: MISSION_HMAC_KEY not set (.env)", file=sys.stderr)
        sys.exit(1)
    blob = {k: v for k, v in mission_data.items() if k != "signature"}
    canonical = json.dumps(blob, sort_keys=True, separators=(",", ":"))
    return hmac.new(key.encode(), canonical.encode(),
                    hashlib.sha256).hexdigest()


def build_signed_mission(scenario_id: str) -> dict:
    template = MISSION_TEMPLATES.get(scenario_id)
    if not template:
        raise KeyError(f"unknown scenario '{scenario_id}'")
    mission = dict(template)
    mission["mission_id"] = f"MSN-{scenario_id.upper()}-SIGNED"
    mission["expires_at"] = int(time.time()) + TTL_SECONDS
    mission["signature"] = sign_blob(mission)
    return mission


def write_missions(only: str | None = None) -> list[Path]:
    MISSIONS_DIR.mkdir(exist_ok=True)
    written = []
    ids = [only] if only else sorted(MISSION_TEMPLATES)
    for sid in ids:
        path = MISSIONS_DIR / f"{sid}.json"
        path.write_text(json.dumps(build_signed_mission(sid), indent=1),
                        encoding="utf-8")
        written.append(path)
        print(f"  signed {sid} -> {path.relative_to(ROOT)}")
    return written


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("scenario", nargs="?", default=None)
    parser.add_argument("--list", action="store_true")
    args = parser.parse_args()

    if args.list:
        for sid in sorted(MISSION_TEMPLATES):
            print(sid)
        return

    try:
        write_missions(args.scenario)
    except KeyError as e:
        print(f"FATAL: {e}", file=sys.stderr)
        print(f"valid ids: {', '.join(sorted(MISSION_TEMPLATES))}",
              file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    main()
