"""
G5 enforcement point: verify a mission's HMAC using MISSION_HMAC_KEY.

Key Custody Note (G5):
Note: The custody invariant (separating the signer from the verifier
process) is enforced in this deployment via scripts/sign_mission.py —
missions are signed out-of-band by the CLI into missions/*.json, and
the FastAPI process only verifies signatures; it never signs one. The
signing key lives in .env, read exclusively by the CLI.
"""
import hashlib
import hmac
import json
import os


def dumps(obj: object) -> str:
    if isinstance(obj, str):
        return obj
    return json.dumps(obj, sort_keys=True, separators=(",", ":"))


def verify_mission(canonical_blob: object, signature: str) -> bool:
    key = os.environ.get("MISSION_HMAC_KEY")
    if not key or not signature:
        return False  # fail-closed: no key or missing signature, no trust
    raw_str = dumps(canonical_blob)
    expected = hmac.new(key.encode("utf-8"), raw_str.encode("utf-8"), hashlib.sha256).hexdigest()
    return hmac.compare_digest(expected, signature)


def sign_mission(canonical_blob: object) -> str:
    """Issuer-side helper (CLI / human side). The agent process NEVER calls this."""
    key = os.environ.get("MISSION_HMAC_KEY", "")
    if not key:
        raise ValueError("MISSION_HMAC_KEY not set in environment")
    raw_str = dumps(canonical_blob)
    return hmac.new(key.encode("utf-8"), raw_str.encode("utf-8"), hashlib.sha256).hexdigest()
