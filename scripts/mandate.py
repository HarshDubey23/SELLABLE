#!/usr/bin/env python3
"""Out-of-band mandate signer — simulates the user's wallet app (AP2 pattern).

Only this CLI and the executor's verifier touch USER_MANDATE_KEY. The buyer
agent never reads it and never signs (machine-verified by
tests/invariants/test_agent_custody.py).

With USER_MANDATE_PRIVATE_KEY set (an Ed25519 key from `keygen`), mandates
are signed with the user's private key and the server needs only the public
half (USER_MANDATE_PUBLIC_KEY): it can verify a mandate but cannot forge one.
Without it, the shared USER_MANDATE_KEY (HMAC) is used, as before.

Usage:
  python scripts/mandate.py keygen
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
    generate_keypair,
    sign_cart,
    sign_cart_ed25519,
    sign_intent,
    sign_intent_ed25519,
)


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    sub = ap.add_subparsers(dest="cmd", required=True)
    sub.add_parser("keygen", help="new Ed25519 keypair for user-held custody")
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

    if args.cmd == "keygen":
        private_key, public_key = generate_keypair()
        print(f"USER_MANDATE_PRIVATE_KEY={private_key}   # wallet only, never the server")
        print(f"USER_MANDATE_PUBLIC_KEY={public_key}    # the server's .env")
        return 0

    private_key = os.environ.get("USER_MANDATE_PRIVATE_KEY", "").strip()
    key = os.environ.get("USER_MANDATE_KEY", "")
    if not private_key and not key:
        print("ERROR: set USER_MANDATE_PRIVATE_KEY (Ed25519) or USER_MANDATE_KEY (HMAC)",
              file=sys.stderr)
        return 2
    out_dir = Path(args.out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)

    if args.cmd == "issue-intent":
        expires = args.expires_at or int(time.time() + args.expiry_hours * 3600)
        intent = IntentMandate(mission_id=args.mission, user_id=args.user,
                               ceiling_paise=args.ceiling_paise, expires_at=expires)
        blob = (sign_intent_ed25519(intent, private_key) if private_key
                else sign_intent(intent, key))
        path = out_dir / f"{args.mission}_intent_mandate.json"
    else:
        cart = CartMandate(mission_id=args.mission, cart_hash=args.cart_hash,
                           amount_paise=args.amount_paise,
                           signed_at=int(time.time()),
                           expires_at=int(time.time()) + 3600)
        blob = (sign_cart_ed25519(cart, private_key) if private_key
                else sign_cart(cart, key))
        path = out_dir / f"{args.mission}_cart_mandate.json"
    path.write_text(json.dumps(blob, indent=2), encoding="utf-8")
    print(f"signed -> {path}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
