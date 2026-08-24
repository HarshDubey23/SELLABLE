"""Single import boundary for google.genai (new SDK).

The gateway never imports this; only apps/api/demo.py does.
Failures return error dicts, never raise.
"""
import os
import re
import time


def _key() -> str | None:
    return (os.environ.get("GEMINI_API_KEY")
            or os.environ.get("GOOGLE_API_KEY")
            or os.environ.get("LLM_API_KEY"))


def _model_name() -> str:
    return os.environ.get("GEMINI_MODEL", "gemini-3.6-flash")


def ask(system: str, user: str) -> dict:
    t0 = time.time()
    key = _key()
    if not key:
        return {"text": "", "latency_ms": 0, "model": _model_name(),
                "error": "no gemini api key in env"}
    try:
        from google import genai  # type: ignore[import-untyped]
        client = genai.Client(api_key=key)
        full = f"{system}\n\n---\n\n{user}"
        resp = client.models.generate_content(
            model=_model_name(),
            contents=full,
        )
        text = resp.text if hasattr(resp, "text") else str(resp)
        return {"text": text, "latency_ms": int((time.time() - t0) * 1000),
                "model": _model_name(), "error": None}
    except Exception as e:
        return {"text": "", "latency_ms": int((time.time() - t0) * 1000),
                "model": _model_name(), "error": str(e)}


def parse_sku(text: str) -> str | None:
    m = re.search(r"SKU:\s*([A-Z]+-\d+)", text or "")
    return m.group(1) if m else None


def parse_reason(text: str) -> str:
    m = re.search(r"REASON:\s*(.+?)(?:\n|$)", text or "")
    return m.group(1).strip()[:200] if m else "could not parse"
