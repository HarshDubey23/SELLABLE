"""Protocol adapter invariants (Phase 4).

The protocols package translates; the gateway decides. Machine-checked:
  (a) no adapter source imports apps.api.gateway (directly or via relative
      gateway imports) — adapters never touch the deciding layer
  (b) no adapter constructs verdicts or decisions
  (c) no adapter contains rule logic (no rule functions, no registry writes)
Mirrors the structural style of tests/invariants/test_agent_custody.py.
"""
import ast
import pathlib

PROTOCOLS_DIR = pathlib.Path("apps/api/protocols")

FORBIDDEN_DECISIONS = ["Verdict(", "Decision(", "evaluate("]
FORBIDDEN_RULE_LOGIC = ["def rule_", "RULE_REGISTRY", "RULE_BY_ID",
                        "rule_id="]

# The adapter surface files (every module in the package except __init__).
_ADAPTER_FILES = sorted(p for p in PROTOCOLS_DIR.glob("*.py")
                        if p.name != "__init__.py")


def _sources() -> list[tuple[str, str]]:
    return [(p.name, p.read_text(encoding="utf-8")) for p in _ADAPTER_FILES]


def _imported_modules(src: str) -> list[str]:
    """Real imports only (AST) — docstrings may legitimately state the ban."""
    mods: list[str] = []
    for node in ast.walk(ast.parse(src)):
        if isinstance(node, ast.Import):
            mods.extend(a.name for a in node.names)
        elif isinstance(node, ast.ImportFrom):
            # Relative imports: node.module is the resolved sub-path after
            # the dots (e.g. `from ..gateway import x` -> module="gateway").
            if node.module:
                mods.append(node.module)
    return mods


def test_adapter_packages_exist():
    names = {name for name, _ in _sources()}
    assert {"acp.py", "ap2.py", "x402.py"} <= names, (
        f"expected the three adapters, found {sorted(names)}")


def test_adapters_never_import_the_gateway():
    """(a) Translate, never decide: zero gateway imports in adapters.
    AST-checked so the docstring bans don't count — only real imports."""
    violations = []
    for name, src in _sources():
        for mod in _imported_modules(src):
            if "gateway" in mod:
                violations.append(f"{name}: imports {mod!r}")
    assert not violations, f"Gateway import inside adapters: {violations}"


def test_adapters_never_construct_verdicts():
    """(b) The executor's response passes through untouched; adapters never
    build Verdict/Decision objects or call evaluate() themselves."""
    violations = []
    for name, src in _sources():
        for needle in FORBIDDEN_DECISIONS:
            if needle in src:
                violations.append(f"{name}: constructs/calls {needle!r}")
    assert not violations, f"Verdict construction inside adapters: {violations}"


def test_adapters_contain_no_rule_logic():
    """(c) No rule functions, no registry access, no rule_id emission from
    adapter code — every money decision stays behind the gateway."""
    violations = []
    for name, src in _sources():
        for needle in FORBIDDEN_RULE_LOGIC:
            if needle in src:
                violations.append(f"{name}: contains {needle!r}")
    assert not violations, f"Rule logic inside adapters: {violations}"


def test_adapters_translate_to_the_canonical_executor():
    """The ONLY sanctioned path to a verdict is the canonical submit tool."""
    acp = dict(_sources())["acp.py"]
    ap2 = dict(_sources())["ap2.py"]
    for name, src in (("acp.py", acp), ("ap2.py", ap2)):
        assert "tool_submit_proposal" in src, (
            f"{name} must hand off to the canonical executor path")
