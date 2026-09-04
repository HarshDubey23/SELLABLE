"""Structured output from a language model, or an honest failure.

Wraps the LLM boundary the repo already has (`apps.api.llm.gemini.ask`,
which talks to OpenRouter) rather than opening a second one. What this
adds is the part that matters for a negotiation: the answer must parse
into a declared schema or it does not count.

THE CONTRACT
------------
`ask_model` returns an `LLMResult`. It never raises and never blocks
forever. Exactly one of these is true of every result:

    ok=True   -> `parsed` is a validated instance of the model you asked
                 for. Nothing unvalidated is ever handed back.
    ok=False  -> `error` says what went wrong in words, and the caller
                 falls back to its deterministic strategy.

There is no third state where a caller has to guess. A negotiation
finishes whether the provider is fast, slow, rate-limited, unreachable,
or returning prose where JSON was asked for.

WHY THE PARSING IS FORGIVING AND THE VALIDATION IS NOT
-----------------------------------------------------
Models wrap JSON in prose and code fences constantly, and refusing those
would mean falling back on a perfectly good answer. So extraction tries
hard. But once a candidate object exists, it is validated strictly
against the schema with `extra="forbid"` — an object carrying a field the
schema does not declare is rejected outright rather than quietly
filtered, because a merchant model that has started inventing fields is
exactly the situation the schema exists for.
"""
from __future__ import annotations

import asyncio
import json
import re
import time
from dataclasses import dataclass, field
from typing import Any, TypeVar

from pydantic import BaseModel, ValidationError

T = TypeVar("T", bound=BaseModel)

# Per-call ceiling. The underlying client has its own shorter timeout and
# its own model fallbacks; this is the outer bound the negotiation relies
# on so a round cannot overrun its deadline because one merchant hung.
CALL_TIMEOUT_SECONDS = 15.0
MAX_ATTEMPTS = 2          # one try, one retry
ROUND_DEADLINE_SECONDS = 45.0

LLM_OK = "llm"
LLM_UNAVAILABLE = "fallback_llm_unavailable"
LLM_MALFORMED = "fallback_llm_malformed"
LLM_DISABLED = "fallback_llm_not_configured"

_FENCE = re.compile(r"```(?:json)?\s*(.*?)```", re.S)


@dataclass
class LLMResult:
    ok: bool
    parsed: Any = None
    error: str | None = None
    mode: str = LLM_OK
    model: str | None = None
    latency_ms: int = 0
    attempts: int = 0
    raw_excerpt: str = ""          # first 240 chars, for the transcript
    meta: dict[str, Any] = field(default_factory=dict)


def configured() -> bool:
    """True when a key is present. Checked, never assumed."""
    import os

    from ...config import is_placeholder

    for name in ("OPENROUTER_API_KEY", "OPENROUTER_API_KEYS",
                 "GEMINI_API_KEY", "LLM_API_KEY"):
        if not is_placeholder(os.environ.get(name, "")):
            return True
    return False


def extract_json_object(text: str) -> dict[str, Any] | None:
    """Pull the first JSON object out of whatever the model said."""
    if not text:
        return None

    candidates: list[str] = []
    for m in _FENCE.finditer(text):
        candidates.append(m.group(1))
    candidates.append(text)

    for candidate in candidates:
        candidate = candidate.strip()
        start = candidate.find("{")
        if start == -1:
            continue
        # Walk to the matching brace so trailing prose does not break it.
        depth, in_str, esc = 0, False, False
        for i in range(start, len(candidate)):
            ch = candidate[i]
            if in_str:
                if esc:
                    esc = False
                elif ch == "\\":
                    esc = True
                elif ch == '"':
                    in_str = False
                continue
            if ch == '"':
                in_str = True
            elif ch == "{":
                depth += 1
            elif ch == "}":
                depth -= 1
                if depth == 0:
                    blob = candidate[start:i + 1]
                    try:
                        obj = json.loads(blob)
                    except ValueError:
                        break
                    return obj if isinstance(obj, dict) else None
    return None


def _ask_sync(system: str, user: str) -> dict[str, Any]:
    from ...llm.gemini import ask
    return ask(system, user)


async def ask_model(*, system: str, user: str, schema: type[T],
                    coerce: Any = None,
                    timeout_s: float = CALL_TIMEOUT_SECONDS) -> LLMResult:
    """Ask for one object of `schema`. Always returns; never raises.

    `coerce` is an optional callable applied to the raw dict before
    validation, for filling fields the model is not asked to supply (a
    merchant does not choose its own id or round number, for instance).
    """
    if not configured():
        return LLMResult(ok=False, error="no LLM API key configured",
                         mode=LLM_DISABLED)

    started = time.perf_counter()
    last_error = "unknown"
    raw = ""
    model_used: str | None = None

    for attempt in range(1, MAX_ATTEMPTS + 1):
        remaining = timeout_s - (time.perf_counter() - started)
        if remaining <= 0.5:
            last_error = f"timed out after {timeout_s:.0f}s"
            break
        try:
            resp = await asyncio.wait_for(
                asyncio.to_thread(_ask_sync, system, user), timeout=remaining)
        except TimeoutError:
            last_error = f"timed out after {timeout_s:.0f}s"
            break
        except Exception as exc:                       # provider blew up
            last_error = f"{type(exc).__name__}: {exc}"
            continue

        model_used = resp.get("model")
        if resp.get("error"):
            last_error = str(resp["error"])[:200]
            continue

        raw = resp.get("text") or ""
        obj = extract_json_object(raw)
        if obj is None:
            last_error = "response contained no JSON object"
            continue

        if coerce is not None:
            try:
                obj = coerce(obj)
            except Exception as exc:
                last_error = f"could not normalise response: {exc}"
                continue

        try:
            parsed = schema.model_validate(obj)
        except ValidationError as exc:
            # Strict on purpose. A model inventing fields is the situation
            # the schema exists for, so it is refused rather than filtered.
            last_error = f"did not match {schema.__name__}: " \
                         f"{exc.errors()[0].get('msg', 'invalid')}"
            continue

        return LLMResult(
            ok=True, parsed=parsed, mode=LLM_OK, model=model_used,
            latency_ms=int((time.perf_counter() - started) * 1000),
            attempts=attempt, raw_excerpt=raw[:240])

    mode = (LLM_UNAVAILABLE
            if ("timed out" in last_error or "HTTP" in last_error
                or "Error" in last_error)
            else LLM_MALFORMED)
    return LLMResult(
        ok=False, error=last_error, mode=mode, model=model_used,
        latency_ms=int((time.perf_counter() - started) * 1000),
        attempts=MAX_ATTEMPTS, raw_excerpt=raw[:240])


def mode_label(mode: str) -> str:
    """What a reader is told. Never dress a fallback up as a live model."""
    return {
        LLM_OK: "LLM merchant",
        LLM_UNAVAILABLE: "scripted fallback merchant (LLM unavailable)",
        LLM_MALFORMED: "scripted fallback merchant (LLM output rejected)",
        LLM_DISABLED: "scripted fallback merchant (no API key configured)",
    }.get(mode, "scripted fallback merchant")


def provider_configured() -> bool:
    """Is a usable provider key present?

    A placeholder counts as absent. The point of this is the badge the
    page shows, and a badge that says "live LLM merchants" because
    someone left `your-key-here` in a .env would be a lie told by
    omission.
    """
    from ...config import is_placeholder
    from ...llm.gemini import _get_keys

    return any(k and not is_placeholder(k) for k in _get_keys())
