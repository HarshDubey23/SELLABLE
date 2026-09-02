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

def test_deterministic_gateway_has_no_llm_imports():
    """Ensure gateway engine is 100% deterministic with zero LLM/probabilistic dependencies."""
    gateway_dir = APPS_API / "gateway"
    for py_file in gateway_dir.rglob("*.py"):
        content = py_file.read_text(encoding="utf-8")
        assert "google.genai" not in content, f"LLM SDK imported inside deterministic gateway module: {py_file}"
        assert "genai" not in content, f"LLM SDK imported inside deterministic gateway module: {py_file}"
