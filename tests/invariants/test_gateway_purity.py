"""T29 (INV-1): gateway/ must contain ZERO llm/network/io imports.

Machine-enforced purity — grep the source, fail the build on violation.
Allowlist: mission_verify.py may reference os.environ (key custody, G5).
"""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

FORBIDDEN = ["openai", "anthropic", "langchain", "requests", "httpx",
             "urllib", "socket", "open(", "subprocess", "os.system",
             "fastapi", "razorpay", "pydantic", "google", "genai", "generativeai"]
ALLOW = {"mission_verify.py": {"os.environ"}}


def test_T29_inv1_no_llm_or_io_in_gateway():
    gw_dir = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(
        os.path.abspath(__file__)))), "apps", "api", "gateway")
    violations = []
    for fname in sorted(os.listdir(gw_dir)):
        if not fname.endswith(".py"):
            continue
        src = open(os.path.join(gw_dir, fname), encoding="utf-8").read()
        allowed = ALLOW.get(fname, set())
        for bad in FORBIDDEN:
            if bad in src and bad not in allowed:
                violations.append(f"{fname}: contains '{bad}'")
    assert not violations, f"INV-1 violated: {violations}"
