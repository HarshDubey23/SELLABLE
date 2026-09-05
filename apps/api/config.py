"""Single source of truth for runtime configuration.

All environment-variable reads must go through this module. Other modules
import the helpers (no scattered `os.environ.get(...)`calls).

This eliminates the previous pain of inconsistent env-var names (e.g.
APP_API_KEY vs SELLABLE_API_KEY, GEMINI_MODEL hard-coded in two places)
and gives us:

- One canonical model name
- One canonical API key variable
- One canonical Razorpay variable set
- Explicit boot-time validation with FAIL-CLOSED semantics

The boot status distinguishes REQUIRED (must be set to start) from
OPTIONAL (degrades gracefully when missing).
"""
from __future__ import annotations

import os
from dataclasses import dataclass

REQUIRED_TO_BOOT = (
    "MISSION_HMAC_KEY",
    "APP_API_KEY",
)

REQUIRED_FOR_PAYMENT = (
    "RAZORPAY_KEY_ID",
    "RAZORPAY_KEY_SECRET",
    "RAZORPAY_WEBHOOK_SECRET",
    "USER_MANDATE_KEY",
)

OPTIONAL_LLM = (
    "OPENROUTER_API_KEYS",
    "OPENROUTER_API_KEY",
    "GEMINI_API_KEY",
    "GOOGLE_API_KEY",
    "LLM_API_KEY",
    "OPENROUTER_MODEL",
    "GEMINI_MODEL",
    "GEMINI_FALLBACK_MODELS",
)

OPTIONAL_DEMO = (
    "PORT",
    "SELLABLE_BASE_URL",
    "SELLABLE_DB_PATH",
)

# The default must be the model that actually gets called. config.py
# used to fall back to google/gemini-1.5-flash while llm/gemini.py fell
# back to openai/gpt-4o-mini, so a fresh clone with no OPENROUTER_MODEL
# set printed one model in the boot banner and on /diagnostics while
# sending every request to a different one. A banner naming a model that
# never runs is the same species of untruth as a badge saying "live"
# when it is simulated.
_CANONICAL_GEMINI_MODEL = "openai/gpt-4o-mini"
_CANONICAL_GEMINI_FALLBACKS = (
    "openai/gpt-4o-mini,meta-llama/llama-3.1-8b-instruct,anthropic/claude-3-haiku"
)


# Values that ship in .env.example. Treating one of these as a configured
# credential is how a demo ends up announcing "Razorpay test mode LIVE"
# with a fake key, or firing 700 doomed requests at an LLM provider
# because a placeholder string looked like an API key.
PLACEHOLDER_VALUES = frozenset({
    "",
    "rzp_test_xxxxxxxx",
    "your_secret_here",
    "your_webhook_secret_here",
    "generate_with_python_secrets_token_hex_32",
    "your_openrouter_keys_comma_separated",
    "your_gemini_api_key_here",
    "your_openrouter_key_here",
    "changeme",
    # The values tests/conftest.py sets. Without them here the suite
    # selects the LIVE provider and every checkout test reaches out to
    # api.razorpay.com, which answers 401 — so whether a test passes
    # depends on the runner's network rather than on the code. A test
    # suite that talks to a payment API is not a test suite.
    "rzp_test_dummy",
    "dummy_secret",
    "test_webhook_secret",
})


def is_placeholder(value: str) -> bool:
    """True when a value is absent or is one of the .env.example stand-ins."""
    return (value or "").strip() in PLACEHOLDER_VALUES


def _env(name: str, default: str = "") -> str:
    """Read an env var, treating placeholder values as unset.

    Fail-closed on configuration: an unset credential degrades to a clearly
    labelled mode, whereas a placeholder that passes for real produces
    confident nonsense.
    """
    val = os.environ.get(name, default)
    val = val if val is not None else default
    return "" if is_placeholder(val) else val


def _env_int(name: str, default: int) -> int:
    raw = os.environ.get(name)
    if raw is None or raw == "":
        return default
    try:
        return int(raw)
    except (TypeError, ValueError):
        return default


@dataclass(frozen=True)
class Config:
    """Resolved runtime configuration. Read-only."""

    app_api_key: str = ""
    mission_hmac_key: str = ""
    user_mandate_key: str = ""

    razorpay_key_id: str = ""
    razorpay_key_secret: str = ""
    razorpay_webhook_secret: str = ""

    gemini_api_key: str = ""
    gemini_model: str = _CANONICAL_GEMINI_MODEL
    gemini_fallback_models: tuple[str, ...] = ()

    port: int = 8000
    base_url: str = ""
    db_path: str = ""

    mandate_version: int = 1
    approval_ttl_seconds: int = 30 * 60
    upsell_default_cap: float = 1.3
    policy_version: str = "sellable-v1.0"

    boot_missing_required: tuple[str, ...] = ()
    payment_missing_required: tuple[str, ...] = ()
    llm_configured: bool = False
    payment_configured: bool = False
    razorpay_mode: str = "test"


def _resolve() -> Config:
    api_key = _env("APP_API_KEY") or _env("SELLABLE_API_KEY")
    gemini_key = (
        _env("OPENROUTER_API_KEYS")
        or _env("OPENROUTER_API_KEY")
        or _env("GEMINI_API_KEY")
        or _env("GOOGLE_API_KEY")
        or _env("LLM_API_KEY")
    )
    gemini_model = _env("OPENROUTER_MODEL") or _env("GEMINI_MODEL") or _CANONICAL_GEMINI_MODEL
    if "3.6" in gemini_model:
        gemini_model = "google/gemini-2.0-flash-001"
    fallbacks_raw = _env("GEMINI_FALLBACK_MODELS") or _CANONICAL_GEMINI_FALLBACKS
    fallbacks = tuple(
        m.strip() for m in fallbacks_raw.split(",")
        if m.strip() and m.strip() != gemini_model and "3.6" not in m
    )

    port = _env_int("PORT", 8000)
    base_url = _env("SELLABLE_BASE_URL") or f"http://localhost:{port}"
    db_path = _env("SELLABLE_DB_PATH") or "data/sellable.db"

    boot_missing = tuple(
        n for n in REQUIRED_TO_BOOT if not _env(n)
    )
    payment_missing = tuple(
        n for n in REQUIRED_FOR_PAYMENT if not _env(n)
    )
    payment_ok = not payment_missing
    llm_ok = bool(gemini_key)

    return Config(
        app_api_key=api_key,
        mission_hmac_key=_env("MISSION_HMAC_KEY"),
        user_mandate_key=_env("USER_MANDATE_KEY"),
        razorpay_key_id=_env("RAZORPAY_KEY_ID"),
        razorpay_key_secret=_env("RAZORPAY_KEY_SECRET"),
        razorpay_webhook_secret=_env("RAZORPAY_WEBHOOK_SECRET"),
        gemini_api_key=gemini_key,
        gemini_model=gemini_model,
        gemini_fallback_models=fallbacks,
        port=port,
        base_url=base_url,
        db_path=db_path,
        boot_missing_required=boot_missing,
        payment_missing_required=payment_missing,
        llm_configured=llm_ok,
        payment_configured=payment_ok,
    )


_CONFIG: Config | None = None


def get() -> Config:
    global _CONFIG
    if _CONFIG is None:
        _CONFIG = _resolve()
    return _CONFIG


def refresh() -> Config:
    """Re-read env. Useful in tests."""
    global _CONFIG
    _CONFIG = _resolve()
    return _CONFIG


def mask_secret(value: str) -> str:
    """Show enough to identify an environment, never enough to use.

    Keeps a recognisable prefix (rzp_test_, sk-or-) so a reader can tell
    test from live at a glance, and replaces everything that identifies
    the particular account.
    """
    v = (value or "").strip()
    if not v:
        return ""
    # Structural, not a list of known prefixes. Vendors separate their
    # structured prefix from the random part with _ or -, so keeping only
    # up to the last separator near the front shows the environment and
    # none of the entropy: rzp_test_**** , sk-or-v1-**** . A key with no
    # such separator gets nothing at all rather than a lucky guess.
    #
    # Enumerating literal vendor prefixes here would also put credential-
    # shaped strings in the source, which the architecture guard forbids
    # outright -- correctly, since it cannot tell a masking table from a
    # pasted credential, and should not have to.
    head = v[:12]
    cut = max(head.rfind("_"), head.rfind("-"))
    return f"{head[:cut + 1]}****" if cut > 0 else "****"


def status_summary() -> dict:
    """Human-readable boot status. The UI's Command Center reads this."""
    cfg = get()
    return {
        "boot_ok": not cfg.boot_missing_required,
        "boot_missing_required": list(cfg.boot_missing_required),
        "payment_configured": cfg.payment_configured,
        "payment_missing_required": list(cfg.payment_missing_required),
        "llm_configured": cfg.llm_configured,
        "llm_model": cfg.gemini_model if cfg.llm_configured else "deterministic fallback (no LLM key configured)",
        "policy_version": cfg.policy_version,
        "mandate_version": cfg.mandate_version,
        "razorpay_mode": "test" if cfg.payment_configured else "unconfigured",
        # Masked. This is a diagnostic surface -- it goes to stdout at boot
        # and out over an HTTP status route -- and nothing reading it needs
        # more than "which environment, and is a key present". The checkout
        # page is the one place the full key_id is genuinely required,
        # because Razorpay's own browser SDK takes it, and it is served
        # only there.
        "razorpay_key_id": mask_secret(cfg.razorpay_key_id),
    }
