#!/usr/bin/env python3
"""Out-of-band mandate signer — simulates the user's wallet app (AP2 pattern).

Only this CLI and the executor's verifier touch USER_MANDATE_KEY. The buyer
agent never reads it and never signs (machine-verified by
tests/invariants/test_agent_custody.py).

Usage:
  python scripts/mandate.py issue-intent --mission m_001 --user u_001 \\
      --ceiling-paise 500000 [--expiry-hours 24 | --expires-at 1735689600] [--out-dir missions]
  python scripts/mandate.py approve-cart --mission m_001 \\
      --cart-hash <approved proposal hash> --amount-paise 249900 [--out-dir missions]
"""
from __future__ import annotations

import argparse
import json
import os
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from apps.api.mandates.mandates import (  # noqa: E402
    CartMandate,
    IntentMandate,
    sign_cart,
    sign_intent,
)


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    sub = ap.add_subparsers(dest="cmd", required=True)
    p1 = sub.add_parser("issue-intent")
    p1.add_argument("--mission", required=True)
    p1.add_argument("--user", required=True)
    p1.add_argument("--ceiling-paise", type=int, required=True)
    p1.add_argument("--expiry-hours", type=float, default=24.0)
    p1.add_argument("--expires-at", type=int, default=None,
                    help="unix seconds (overrides --expiry-hours; allows past for demos)")
    p1.add_argument("--out-dir", default="missions")
    p2 = sub.add_parser("approve-cart")
    p2.add_argument("--mission", required=True)
    p2.add_argument("--cart-hash", required=True)
    p2.add_argument("--amount-paise", type=int, required=True)
    p2.add_argument("--out-dir", default="missions")
    args = ap.parse_args()

    key = os.environ.get("USER_MANDATE_KEY", "")
    if not key:
        print("ERROR: USER_MANDATE_KEY is not set", file=sys.stderr)
        return 2
    out_dir = Path(args.out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)

    if args.cmd == "issue-intent":
        expires = args.expires_at or int(time.time() + args.expiry_hours * 3600)
        blob = sign_intent(IntentMandate(mission_id=args.mission, user_id=args.user,
                                         ceiling_paise=args.ceiling_paise,
                                         expires_at=expires), key)
        path = out_dir / f"{args.mission}_intent_mandate.json"
    else:
        blob = sign_cart(CartMandate(mission_id=args.mission, cart_hash=args.cart_hash,
                                     amount_paise=args.amount_paise,
                                     signed_at=int(time.time()),
                                     expires_at=int(time.time()) + 3600), key)
        path = out_dir / f"{args.mission}_cart_mandate.json"
    path.write_text(json.dumps(blob, indent=2), encoding="utf-8")
    print(f"signed -> {path}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
