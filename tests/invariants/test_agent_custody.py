"""INV-3 custody: the agent carries signing material, it never holds it.

The user's mandate key is what makes "the user consented to this exact
cart at this exact amount" mean anything. If the buyer agent could read
that key, it could sign its own consent, and the mandate layer would be
decoration.

`apps/api/mandates/mandates.py` states this as "machine-verified by
tests/invariants/test_agent_custody.py". This file is that verification.
It previously existed as an empty file, so the claim was unbacked.
"""
import ast
from pathlib import Path

import pytest

APPS = Path(__file__).resolve().parents[2] / "apps" / "api"
AGENT_DIR = APPS / "agent"

SIGNING_KEYS = {"USER_MANDATE_KEY", "MISSION_HMAC_KEY"}
SIGNING_FUNCTIONS = {"sign_intent", "sign_cart", "sign_mission", "_sign"}


def agent_files() -> list[Path]:
    files = sorted(p for p in AGENT_DIR.rglob("*.py")
                   if "__pycache__" not in p.parts)
    assert files, "no agent sources found"
    return files


def _string_constants(tree: ast.AST) -> set[str]:
    return {node.value for node in ast.walk(tree)
            if isinstance(node, ast.Constant) and isinstance(node.value, str)}


def _called_names(tree: ast.AST) -> set[str]:
    names: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Call):
            if isinstance(node.func, ast.Name):
                names.add(node.func.id)
            elif isinstance(node.func, ast.Attribute):
                names.add(node.func.attr)
    return names


@pytest.mark.parametrize("path", agent_files(), ids=lambda p: p.name)
def test_agent_never_names_a_signing_key(path):
    """Reading the key is the same as holding it."""
    tree = ast.parse(path.read_text(encoding="utf-8"))
    leaked = _string_constants(tree) & SIGNING_KEYS
    assert not leaked, (
        f"{path.name} references {sorted(leaked)}. The agent must receive "
        f"signed blobs, never the material that signs them.")


@pytest.mark.parametrize("path", agent_files(), ids=lambda p: p.name)
def test_agent_never_signs_anything(path):
    tree = ast.parse(path.read_text(encoding="utf-8"))
    signing = _called_names(tree) & SIGNING_FUNCTIONS
    assert not signing, (
        f"{path.name} calls {sorted(signing)}. An agent that can sign its "
        f"own consent has no consent to obtain.")


@pytest.mark.parametrize("path", agent_files(), ids=lambda p: p.name)
def test_agent_never_imports_the_mandate_signer(path):
    tree = ast.parse(path.read_text(encoding="utf-8"))
    for node in ast.walk(tree):
        if isinstance(node, ast.ImportFrom) and node.module:
            assert "mandates" not in node.module, (
                f"{path.name} imports {node.module}; the agent carries "
                f"mandate blobs opaquely and must not reach the signer")


@pytest.mark.parametrize("path", agent_files(), ids=lambda p: p.name)
def test_agent_never_calls_the_money_boundary_directly(path):
    """The agent is an HTTP client of the storefront, like any other buyer."""
    source = path.read_text(encoding="utf-8")
    assert "razorpay_client" not in source, (
        f"{path.name} reaches the money boundary directly; it must go "
        f"through the storefront's canonical endpoints")


def test_the_signer_lives_outside_the_server_process():
    """Custody is a deployment fact, so check the CLI signers exist."""
    scripts = Path(__file__).resolve().parents[2] / "scripts"
    assert (scripts / "sign_mission.py").exists(), \
        "missions are meant to be signed out of band"
    assert (scripts / "mandate.py").exists(), \
        "mandates are meant to be minted by a wallet stand-in, not the server"


def test_in_process_issuer_discloses_itself():
    """The one place the server does sign, it must say so.

    apps/api/issuer.py exists so the browser demo does not require two
    CLIs. That is a weaker guarantee than out-of-band signing — integrity
    without custody — and it is only acceptable if every response says so.
    """
    from apps.api import issuer

    assert issuer.ISSUER_LABEL == "in_process_demo_issuer"
    source = (APPS / "issuer.py").read_text(encoding="utf-8")
    assert "custody" in source.lower(), \
        "the issuer module must explain what it does and does not prove"

    api = (APPS / "discovery" / "api.py").read_text(encoding="utf-8")
    assert "authorization_issued_by" in api, (
        "every response produced through the in-process issuer must be "
        "tagged, otherwise the weaker guarantee is invisible")
