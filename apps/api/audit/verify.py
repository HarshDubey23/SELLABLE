"""`make audit-verify` — thin CLI wrapper around the audit chain's own verify().

Prints one JSON line {"verified": bool, "entries": int} and exits 0 when the
chain verifies, else 1. No new verification logic, no DB writes, no new
dependencies.
"""
import json
import sys

from . import chain as audit_chain


def main() -> int:
    verified = audit_chain.verify()
    print(json.dumps({"verified": verified,
                      "entries": len(audit_chain.entries())}))
    return 0 if verified else 1


if __name__ == "__main__":
    sys.exit(main())
