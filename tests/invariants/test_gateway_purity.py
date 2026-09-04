"""INV-2: the policy gateway is a pure function of its inputs.

`apps/api/gateway/` is the only thing standing between an adversarial
proposal and a payment. If it can call an LLM, open a socket, or read a
file, then its verdict depends on something an attacker might control,
and "deterministic" becomes marketing.

So this is checked structurally, by parsing the source, rather than by
trusting a comment. Several docstrings across the codebase cite this file
as the machine-verified proof of that claim — it needs to actually be one.

(This module previously existed as an empty file. The claim was cited in
`gateway/proof.py`, in the README and in the architecture docs while
nothing verified it.)
"""
import ast
from pathlib import Path

import pytest

GATEWAY_DIR = Path(__file__).resolve().parents[2] / "apps" / "api" / "gateway"

# Anything that would make a verdict depend on the outside world.
FORBIDDEN_MODULES = {
    # network
    "requests", "httpx", "urllib", "urllib.request", "socket", "http",
    "http.client", "aiohttp", "websockets",
    # model SDKs
    "openai", "anthropic", "google", "google.genai", "google.generativeai",
    "langchain", "llama_index", "cohere", "transformers", "litellm",
    # process / filesystem escape hatches
    "subprocess", "shutil", "tempfile", "sqlite3",
    # the money boundary itself
    "razorpay",
}

# Calls that reach outside the process.
FORBIDDEN_CALLS = {"open", "exec", "eval", "compile", "__import__", "input"}

# proof.py legitimately reads its sibling sources to hash them; it is a
# reporter, not a decision path. Nothing in it is reachable from evaluate().
IO_EXEMPT_FILES = {"proof.py"}


def gateway_files() -> list[Path]:
    files = sorted(GATEWAY_DIR.glob("*.py"))
    assert files, "no gateway sources found — has the package moved?"
    return files


def _imported_modules(tree: ast.AST) -> set[str]:
    found: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                found.add(alias.name)
                found.add(alias.name.split(".")[0])
        elif isinstance(node, ast.ImportFrom):
            if node.level:      # relative import, stays inside the package
                continue
            if node.module:
                found.add(node.module)
                found.add(node.module.split(".")[0])
    return found


@pytest.mark.parametrize("path", gateway_files(), ids=lambda p: p.name)
def test_gateway_module_imports_nothing_from_the_outside_world(path):
    tree = ast.parse(path.read_text(encoding="utf-8"))
    offending = _imported_modules(tree) & FORBIDDEN_MODULES
    assert not offending, (
        f"{path.name} imports {sorted(offending)}. The gateway must decide "
        f"from its arguments alone — a rule that can call out is a rule an "
        f"attacker can influence.")


@pytest.mark.parametrize("path", gateway_files(), ids=lambda p: p.name)
def test_gateway_module_performs_no_io(path):
    if path.name in IO_EXEMPT_FILES:
        pytest.skip(f"{path.name} is a reporter, not on the decision path")
    tree = ast.parse(path.read_text(encoding="utf-8"))
    hits = [
        node.func.id
        for node in ast.walk(tree)
        if isinstance(node, ast.Call) and isinstance(node.func, ast.Name)
        and node.func.id in FORBIDDEN_CALLS
    ]
    assert not hits, f"{path.name} calls {sorted(set(hits))}"


def test_evaluate_never_reaches_a_non_gateway_apps_module():
    """Relative imports must stay inside the gateway package.

    `from ..razorpay_client import ...` would be a relative import, so the
    module check above would miss it. Depth matters: `.` is the package,
    `..` is everything else.
    """
    offenders = []
    for path in gateway_files():
        tree = ast.parse(path.read_text(encoding="utf-8"))
        for node in ast.walk(tree):
            if isinstance(node, ast.ImportFrom) and node.level and node.level > 1:
                offenders.append(f"{path.name}: level-{node.level} import "
                                 f"of {node.module}")
    assert not offenders, (
        "the gateway reaches outside its own package: " + "; ".join(offenders))


def test_repeated_evaluation_is_identical():
    """Same inputs, same verdict — 100 times, including the proposal hash."""
    import time

    from apps.api.gateway.engine import evaluate
    from apps.api.gateway.types import Mission, Proposal, ProposalItem
    from apps.api.products import CATALOG

    now = int(time.time())
    mission = Mission(
        mission_id="PURITY-1", intent="determinism check",
        budget_paise=500000, allowed_categories=("cricket",),
        forbidden_categories=(), upsell_cap=1.0,
        expires_at=now + 3600, signature="stub")
    proposal = Proposal(
        mission_id="PURITY-1",
        items=(ProposalItem(sku="BAT-001", qty=1, price_paise=149900),))

    verdicts = [
        evaluate(mission=mission, proposal=proposal, catalog=CATALOG,
                 verify_fn=lambda blob, sig: True, state={}, now_ts=now,
                 chain_ok=True)
        for _ in range(100)
    ]
    first = verdicts[0]
    assert all(v.decision == first.decision for v in verdicts)
    assert all(v.rule_id == first.rule_id for v in verdicts)
    assert len({v.proposal_hash for v in verdicts}) == 1


def test_missing_input_fails_closed():
    """G3: absence of an input is a REJECT, never a pass."""
    from apps.api.gateway.engine import evaluate
    from apps.api.gateway.types import Decision, Proposal, ProposalItem
    from apps.api.products import CATALOG

    proposal = Proposal(mission_id="X",
                        items=(ProposalItem(sku="BAT-001", qty=1,
                                            price_paise=149900),))
    for kwargs in (
        {"mission": None, "proposal": proposal, "catalog": CATALOG},
        {"mission": None, "proposal": None, "catalog": CATALOG},
        {"mission": None, "proposal": proposal, "catalog": {}},
    ):
        verdict = evaluate(verify_fn=lambda blob, sig: True, **kwargs)
        assert verdict.decision == Decision.REJECT


def test_tampered_audit_chain_halts_the_money_path():
    """G6: if the ledger cannot be trusted, nothing is approved."""
    import time

    from apps.api.gateway.engine import evaluate
    from apps.api.gateway.types import Decision, Mission, Proposal, ProposalItem
    from apps.api.products import CATALOG

    now = int(time.time())
    mission = Mission(
        mission_id="CHAIN-1", intent="x", budget_paise=500000,
        allowed_categories=("cricket",), forbidden_categories=(),
        upsell_cap=1.0, expires_at=now + 3600, signature="stub")
    proposal = Proposal(
        mission_id="CHAIN-1",
        items=(ProposalItem(sku="BAT-001", qty=1, price_paise=149900),))

    verdict = evaluate(mission=mission, proposal=proposal, catalog=CATALOG,
                       verify_fn=lambda blob, sig: True, state={}, now_ts=now,
                       chain_ok=False)
    assert verdict.decision == Decision.REJECT
    assert verdict.rule_id == "CHAIN_TAMPER"


def test_proof_endpoint_agrees_with_this_test():
    """The runtime purity report and this test must not disagree."""
    from apps.api.gateway.proof import compute_proof

    proof = compute_proof()
    assert proof["llm_imports_detected"] == 0
    assert proof["io_calls_detected"] == 0
