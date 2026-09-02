"""API-key dependency for mutating endpoints (F-08, Phase 3).

Design:
- Missing or wrong X-API-Key  -> 401 (constant-time comparison).
- APP_API_KEY unset in env    -> 503 fail-closed: the API refuses mutations
  rather than silently allowing them. The error names the env var.
- Applied ONLY to mutating (POST) routes. GET routes stay open (read-only).
  The webhook receiver is exempt: it is protected by Razorpay's HMAC on the
  raw body plus event-id dedup — an API key there would break event delivery.
  See docs/SECURITY_CLAIMS.md "Trust Boundary".
"""
import hmac
import os

from fastapi import Header, HTTPException


def require_api_key(x_api_key: str | None = Header(default=None)) -> str:
    expected = os.environ.get("APP_API_KEY")
    if not expected:
        raise HTTPException(
            status_code=503,
            detail=(
                "APP_API_KEY is not configured; mutating endpoints are fail-closed. "
                "Set APP_API_KEY in the environment. Generate one with: "
                'python -c "import secrets; print(secrets.token_hex(32))"'
            ),
        )
    if x_api_key is None or not hmac.compare_digest(
        x_api_key.encode(), expected.encode()
    ):
        raise HTTPException(status_code=401, detail="Missing or invalid X-API-Key header")
    return x_api_key
