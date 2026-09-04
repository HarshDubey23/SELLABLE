"""API-key dependency — fail-closed when configured."""
from __future__ import annotations

import hmac
import os

from fastapi import Header, HTTPException


def require_api_key(x_api_key: str | None = Header(default=None)) -> None:
    expected = (os.environ.get("APP_API_KEY") or "").strip()
    if not expected:
        return  # demo mode: open, and the UI labels itself SIMULATED
    if x_api_key is None or not hmac.compare_digest(x_api_key, expected):
        raise HTTPException(status_code=401, detail="invalid or missing X-API-Key")

