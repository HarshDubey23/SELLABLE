"""Protocol adapters translate. They never decide.

ACP, AP2 and NPCI-UAP adapters exist to accept a differently-shaped
request and hand it to the canonical submit path. The moment an adapter
constructs its own verdict, or contains its own rule logic, there are two
policy engines and only one of them is tested.

Each adapter's docstring names this file as the enforcement point. It
previously existed as an empty file.
"""
import ast
from pathlib import Path

import pytest

PROTOCOLS = Path(__file__).resolve().parents[2] / "apps" / "api" / "protocols"


def adapter_files() -> list[Path]:
    files = sorted(p for p in PROTOCOLS.glob("*.py")
                   if p.name != "__init__.py")
    assert files, "no protocol adapters found"
    return files


@pytest.mark.parametrize("path", adapter_files(), ids=lambda p: p.name)
def test_adapter_does_not_import_the_gateway(path):
    """Translate, never decide."""
    source = path.read_text(encoding="utf-8")
    tree = ast.parse(source)
    for node in ast.walk(tree):
        if isinstance(node, ast.ImportFrom) and node.module:
            assert "gateway" not in node.module, (
                f"{path.name} imports {node.module}; adapters must reach the "
                f"gateway only through the canonical submit path")


@pytest.mark.parametrize("path", adapter_files(), ids=lambda p: p.name)
def test_adapter_does_not_construct_a_verdict(path):
    source = path.read_text(encoding="utf-8")
    for forbidden in ("Verdict(", "Decision.APPROVE", "decision = \"APPROVE\""):
        assert forbidden not in source, (
            f"{path.name} contains {forbidden!r}; an adapter that can mint an "
            f"APPROVE is a second, untested policy engine")


@pytest.mark.parametrize("path", adapter_files(), ids=lambda p: p.name)
def test_adapter_does_not_reach_the_money_boundary(path):
    source = path.read_text(encoding="utf-8")
    assert "razorpay_client" not in source
    assert "create_order(" not in source or "tool_create_order" in source


@pytest.mark.parametrize("path", adapter_files(), ids=lambda p: p.name)
def test_adapter_contains_no_rule_logic(path):
    """No adapter may re-implement a budget, scope or price check."""
    source = path.read_text(encoding="utf-8")
    for smell in ("budget_paise <", "budget_paise >", "price_paise >",
                  "allowed_categories", "forbidden_categories"):
        assert smell not in source, (
            f"{path.name} contains {smell!r} — money rules live in the "
            f"gateway registry, in one place, or they drift")
