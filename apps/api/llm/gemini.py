"""Single import boundary for LLM calling.

Rewritten to use OpenRouter for extreme speed and reliability during the demo,
using a pool of API keys to avoid rate limits.
"""
import os
import random
import re
import time

import requests


def _get_keys() -> list[str]:
    raw = os.environ.get("OPENROUTER_API_KEYS", "")
    if raw:
        return [k.strip() for k in raw.split(",") if k.strip()]
    single = (
        os.environ.get("OPENROUTER_API_KEY")
        or os.environ.get("GEMINI_API_KEY")
        or os.environ.get("GOOGLE_API_KEY")
        or os.environ.get("LLM_API_KEY")
    )
    return [single] if single else []


from dotenv import load_dotenv
load_dotenv()


def _model_name() -> str:
    m = os.environ.get("OPENROUTER_MODEL") or os.environ.get("LLM_MODEL") or "openai/gpt-4o-mini"
    if "gemini" in m or "3.6" in m:
        return "openai/gpt-4o-mini"
    return m


def _fallback_models() -> list[str]:
    return [
        "deepseek/deepseek-chat",
        "meta-llama/llama-3.3-70b-instruct",
        "openai/gpt-4o-mini",
    ]


def ask(system: str, user: str) -> dict:
    t0 = time.time()

    candidates = [_model_name()] + _fallback_models()
    last_error = None

    keys = _get_keys()
    if not keys:
        return {
            "text": "",
            "latency_ms": 0,
            "model": _model_name(),
            "error": "no LLM API key in env",
        }

    # Shuffle keys to load balance
    shuffled_keys = list(keys)
    random.shuffle(shuffled_keys)

    for model in candidates:
        for key in shuffled_keys:
            try:
                resp = requests.post(
                    "https://openrouter.ai/api/v1/chat/completions",
                    headers={
                        "Authorization": f"Bearer {key}",
                        "HTTP-Referer": "https://github.com/HarshDubey23/SELLABLE",
                        "X-Title": "SELLABLE Buildathon",
                    },
                    json={
                        "model": model,
                        "messages": [
                            {"role": "system", "content": system},
                            {"role": "user", "content": user}
                        ],
                        "temperature": 0.1,
                    },
                    timeout=8.0
                )
                if resp.status_code == 200:
                    data = resp.json()
                    text = data["choices"][0]["message"]["content"]
                    return {
                        "text": text,
                        "latency_ms": int((time.time() - t0) * 1000),
                        "model": model,
                        "error": None
                    }
                else:
                    last_error = f"{model}: HTTP {resp.status_code} {resp.text}"
                    if resp.status_code not in (429, 502, 503):
                        break  # If it's a bad request, don't try other keys for the same model
            except Exception as e:
                last_error = f"{model}: {str(e)}"

    return {
        "text": "",
        "latency_ms": int((time.time() - t0) * 1000),
        "model": _model_name(),
        "error": last_error
    }


def parse_sku(text: str) -> str | None:
    m = re.search(r"SKU:\s*([A-Z]+-\d+)", text or "")
    return m.group(1) if m else None


def parse_reason(text: str) -> str:
    m = re.search(r"REASON:\s*(.+?)(?:\n|$)", text or "")
    return m.group(1).strip()[:200] if m else "could not parse"
