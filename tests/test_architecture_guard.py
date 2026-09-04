"""
Architecture Guard Tests for SELLABLE.

Enforces:
1. Single Money Boundary: Only approved modules (razorpay_client, gateway_service) may initiate Razorpay network calls.
2. No LLM Money Authority: Agent reasoning modules do not have direct access to payment creation functions.
3. No committed secret credentials in python source files.
"""
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
APPS_API = PROJECT_ROOT / "apps" / "api"

APPROVED_GATEWAY_MODULES = {
    "razorpay_client.py",
    "gateway_service.py",
}

def test_single_money_boundary_architecture():
    """Ensure no unapproved module initiates direct requests to api.razorpay.com in code lines (excluding docstrings)."""
    for py_file in APPS_API.rglob("*.py"):
        if py_file.name in APPROVED_GATEWAY_MODULES:
            continue
        lines = py_file.read_text(encoding="utf-8").splitlines()
        for line_no, line in enumerate(lines, 1):
            sline = line.strip()
            if sline.startswith("#") or sline.startswith('"""') or sline.startswith("'''"):
                continue
            assert "https://api.razorpay.com" not in line, f"Direct Razorpay URL in code line at {py_file}:{line_no}"
            if "requests." in line or "httpx." in line or "urllib" in line:
                assert "api.razorpay.com" not in line, f"Direct Razorpay API call in {py_file}:{line_no}"

def test_no_hardcoded_live_secrets_in_source():
    """Ensure no live Razorpay credentials or private keys are hardcoded in source code."""
    for py_file in APPS_API.rglob("*.py"):
        content = py_file.read_text(encoding="utf-8")
        assert "rzp_live_" not in content, f"Hardcoded live Razorpay key found in {py_file}"
        assert "-----BEGIN RSA PRIVATE KEY-----" not in content, f"Hardcoded private key found in {py_file}"

def test_no_real_looking_api_key_is_embedded_anywhere():
    """A test key is still somebody's actual credential.

    apps/api/chaos/engine.py carried a real rzp_test_ key as the default
    for its own safety check. It was in a public repository, and it also
    meant that with no key configured at all the check answered "SAFE" --
    arming chaos in an environment whose credential state was unknown. A
    safety check that passes when it has nothing to look at is not one.

    This looks for a vendor prefix followed by enough characters to be a
    usable key. The masked form the diagnostics print, rzp_test_****, is
    not one and passes.
    """
    import re

    patterns = {
        "Razorpay": re.compile(r"rzp_(?:test|live)_[A-Za-z0-9]{10,}"),
        "OpenRouter": re.compile(r"sk-or-v1-[A-Za-z0-9]{20,}"),
        "Google": re.compile(r"AIza[A-Za-z0-9_\-]{30,}"),
    }
    roots = [PROJECT_ROOT / "apps", PROJECT_ROOT / "scripts",
             PROJECT_ROOT / "tests", PROJECT_ROOT / "docs"]

    found = []
    for root in roots:
        if not root.exists():
            continue
        for path in root.rglob("*"):
            if not path.is_file() or path.suffix not in (
                    ".py", ".md", ".json", ".yml", ".yaml", ".toml", ".txt"):
                continue
            try:
                content = path.read_text(encoding="utf-8-sig")
            except (OSError, UnicodeDecodeError):
                continue
            for vendor, rx in patterns.items():
                if rx.search(content):
                    found.append(f"{vendor} key in {path}")

    assert found == [], (
        "a real-looking credential is embedded in the repository: "
        + "; ".join(found))


def test_the_chaos_safety_check_refuses_when_it_cannot_prove_test_mode():
    """No key means no proof, and no proof means no arming."""
    import os

    from apps.api.chaos.engine import ChaosEngine

    engine = ChaosEngine()
    previous = os.environ.pop("RAZORPAY_KEY_ID", None)
    try:
        safe, message = engine.check_safety()
        assert not safe, "armed with no credential to check against"
        assert "not set" in message
    finally:
        if previous is not None:
            os.environ["RAZORPAY_KEY_ID"] = previous


def test_deterministic_gateway_has_no_llm_imports():
    """Ensure gateway engine is 100% deterministic with zero LLM/probabilistic dependencies."""
    gateway_dir = APPS_API / "gateway"
    for py_file in gateway_dir.rglob("*.py"):
        content = py_file.read_text(encoding="utf-8")
        assert "google.genai" not in content, f"LLM SDK imported inside deterministic gateway module: {py_file}"
        assert "genai" not in content, f"LLM SDK imported inside deterministic gateway module: {py_file}"


def test_the_demo_harness_never_invents_a_binding_primary_key():
    """`bindings.seq` is an audit-chain sequence, not a number to make up.

    scripts/final_demo.py used to mint one per scenario from the clock,
    modulo a million, with a small per-scenario offset. Since seq is a
    PRIMARY KEY, two scenarios whose gap equalled the difference of their
    offsets wrote the same key and SQLite raised UNIQUE constraint failed.
    It hit at gaps of 8 and 9 ms - routine on a fast runner, never on a
    slow one - which is why the release gate passed on three CI machines
    and failed on the fourth.

    Production was never exposed: it passes the sequence the audit chain
    returns. This asserts the harness does the same, so the gate cannot go
    back to being a coin flip.

    Checked against the syntax tree rather than the text, so the
    explanation above cannot trip the assertion it is explaining.
    """
    import ast
    import pathlib

    source = pathlib.Path("scripts/final_demo.py").read_text(encoding="utf-8")
    tree = ast.parse(source)

    offenders = []
    for node in ast.walk(tree):
        if not isinstance(node, ast.Assign):
            continue
        if not any(getattr(t, "id", "") == "seq_id" for t in node.targets):
            continue
        expr = ast.unparse(node.value)
        if "time" in expr or "%" in expr:
            offenders.append(expr)

    assert offenders == [], (
        f"final_demo.py assigns seq_id from the clock again: {offenders}. "
        f"Use demo_seq(), which returns a real audit-chain sequence.")

    names = {n.name for n in ast.walk(tree)
             if isinstance(n, ast.FunctionDef)}
    assert "demo_seq" in names, "the helper that replaced it is gone"
    assert 'chain.append("demo_harness"' in source,         "demo_seq must take its sequence from the audit chain"
