"""
Gateway Test Matrix — 30 hand-written cases covering all R1-R10 rules.

These tests are HAND-WRITTEN. They use the real CATALOG from products.py
and the real gateway evaluate() function.

Each test has a one-line comment explaining what it proves.
"""
import hashlib
import hmac
import json
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from apps.api.gateway.engine import evaluate
from apps.api.gateway.types import Decision, Mission, Proposal, ProposalItem

TEST_KEY = "test-hmac-matrix-key-only-for-tests"


def _sign(blob: dict) -> str:
    """Sign a mission blob with the test key."""
    canonical = json.dumps(blob, sort_keys=True, separators=(",", ":"))
    return hmac.new(
        TEST_KEY.encode(), canonical.encode(), hashlib.sha256
    ).hexdigest()


def make_mission(
    budget: int = 200000,
    allowed: tuple = ("cricket",),
    forbidden: tuple = (),
    upsell_cap: float = 1.3,
    expires_in: int = 3600,
    sign: bool = True,
    mission_id: str = "MSN-TEST-001",
) -> Mission:
    """Build a Mission with optional signing."""
    mission = Mission(
        mission_id=mission_id,
        intent="test mission",
        budget_paise=budget,
        allowed_categories=tuple(allowed),
        forbidden_categories=tuple(forbidden),
        upsell_cap=upsell_cap,
        expires_at=int(time.time()) + expires_in,
        signature="",
    )
    if sign:
        blob = {k: v for k, v in vars(mission).items() if k != "signature"}
        # Mission is frozen; the issuer is allowed to set the signature once.
        object.__setattr__(mission, "signature", _sign(blob))
    return mission


def make_proposal(skus_with_qty: list[tuple[str, int]],
                  mission_id: str = "MSN-TEST-001") -> Proposal:
    """Build a Proposal with prices from CATALOG (server-side truth)."""
    from apps.api.products import CATALOG

    items = []
    for sku, qty in skus_with_qty:
        if sku not in CATALOG:
            raise ValueError(f"unknown sku {sku}")
        items.append(ProposalItem(
            sku=sku, qty=qty, price_paise=CATALOG[sku]["price_paise"]
        ))
    return Proposal(mission_id=mission_id, items=tuple(items))


def run_gateway(
    mission: Mission | None,
    proposal: Proposal | None,
    state: dict | None = None,
    now_ts: int | None = None,
    chain_ok: bool = True,
    merchant_id: str = "SELLABLE-DEMO",
):
    """Run evaluate() with a test verification function."""
    from apps.api.products import CATALOG

    def verify_fn(blob: str, sig: str) -> bool:
        expected = hmac.new(
            TEST_KEY.encode(), blob.encode(), hashlib.sha256
        ).hexdigest()
        return hmac.compare_digest(expected, sig)

    return evaluate(
        mission=mission,
        proposal=proposal,
        catalog=CATALOG,
        verify_fn=verify_fn,
        state=state or {},
        now_ts=now_ts if now_ts is not None else int(time.time()),
        merchant_id=merchant_id,
        chain_ok=chain_ok,
    )


# ============================================================
# R1_BUDGET TESTS (4 tests)
# ============================================================

def test_r1_under_effective_budget():
    """Total below effective budget (budget x cap) -> APPROVE."""
    mission = make_mission(budget=200000, upsell_cap=1.3)
    # BAT-001 = 149900, effective budget = 260000
    proposal = make_proposal([("BAT-001", 1)])
    verdict = run_gateway(mission, proposal)
    assert verdict.decision == Decision.APPROVE


def test_r1_exactly_effective_budget():
    """Total exactly equal to effective budget -> APPROVE (boundary)."""
    # cap=1.0 makes the effective budget the base budget; BAT-001 at
    # exactly 149900 hits the ceiling without exceeding it.
    mission2 = make_mission(budget=149900, upsell_cap=1.0)
    proposal2 = make_proposal([("BAT-001", 1)])
    verdict2 = run_gateway(mission2, proposal2)
    assert verdict2.decision == Decision.APPROVE


def test_r1_over_effective_budget():
    """Total above effective budget -> REJECT R1_BUDGET."""
    mission = make_mission(budget=200000, upsell_cap=1.3)
    # Effective budget = 260000. BAT-002 (249900) + GRIP-001 (29900) = 279800
    proposal = make_proposal([("BAT-002", 1), ("GRIP-001", 1)])
    verdict = run_gateway(mission, proposal)
    assert verdict.decision == Decision.REJECT
    assert verdict.rule_id == "R1_BUDGET"


def test_r1_injection_inflates_total():
    """KIT-001 (carries the I1 injection) costs 449900 — way over budget."""
    mission = make_mission(budget=200000, upsell_cap=1.3)
    # Effective budget = 260000. KIT-001 = 449900.
    proposal = make_proposal([("KIT-001", 1)])
    verdict = run_gateway(mission, proposal)
    assert verdict.decision == Decision.REJECT
    assert verdict.rule_id == "R1_BUDGET"


# ============================================================
# R2_FORBIDDEN TESTS (2 tests)
# ============================================================

def test_r2_forbidden_rejected():
    """Item in forbidden category -> REJECT R2_FORBIDDEN."""
    mission = make_mission(
        budget=500000,
        allowed=("electronics",),
        forbidden=("electronics",),  # electronics is both allowed and forbidden
    )
    proposal = make_proposal([("EAR-001", 1)])
    verdict = run_gateway(mission, proposal)
    assert verdict.decision == Decision.REJECT
    assert verdict.rule_id == "R2_FORBIDDEN"


def test_r2_not_forbidden_passes():
    """Item NOT in forbidden list -> APPROVE (if other rules pass)."""
    mission = make_mission(
        budget=200000,
        allowed=("cricket",),
        forbidden=("electronics",),  # cricket not forbidden
    )
    proposal = make_proposal([("BAT-001", 1)])
    verdict = run_gateway(mission, proposal)
    assert verdict.decision == Decision.APPROVE


# ============================================================
# R3_PRICE_DRIFT TESTS (2 tests)
# ============================================================

def test_r3_drift_detected():
    """Manually crafted price different from catalog -> REJECT R3."""
    mission = make_mission(budget=500000)
    # Create a proposal with WRONG price
    items = (ProposalItem(sku="BAT-001", qty=1, price_paise=99900),)  # wrong!
    proposal = Proposal(mission_id=mission.mission_id, items=items)
    verdict = run_gateway(mission, proposal)
    assert verdict.decision == Decision.REJECT
    assert verdict.rule_id == "R3_PRICE_DRIFT"


def test_r3_no_drift_passes():
    """Prices from CATALOG -> no drift -> APPROVE."""
    mission = make_mission(budget=200000)
    proposal = make_proposal([("BAT-001", 1)])
    verdict = run_gateway(mission, proposal)
    assert verdict.decision == Decision.APPROVE


# ============================================================
# R4_UPSELL_CAP TESTS (3 tests)
# ============================================================

def test_r4_within_cap():
    """Total between budget and effective budget -> APPROVE (upsell window)."""
    mission = make_mission(budget=200000, upsell_cap=1.3)
    # Effective budget = 260000. BAT-002 (249900) alone = 249900.
    # 200000 < 249900 < 260000 -> inside the upsell window.
    proposal = make_proposal([("BAT-002", 1)])
    verdict = run_gateway(mission, proposal)
    assert verdict.decision == Decision.APPROVE


def test_r4_exceeds_cap():
    """Total above effective budget -> REJECT (R1 fires with same threshold)."""
    mission = make_mission(budget=200000, upsell_cap=1.3)
    # Effective budget = 260000. BAT-002 (249900) + GRIP-001 (29900) = 279800.
    proposal = make_proposal([("BAT-002", 1), ("GRIP-001", 1)])
    verdict = run_gateway(mission, proposal)
    assert verdict.decision == Decision.REJECT
    # R1 fires first (same threshold as R4 after the effective-budget fix)
    assert verdict.rule_id == "R1_BUDGET"


def test_r4_cap_1_means_budget_only():
    """When cap=1.0, effective budget = budget -> standard budget check."""
    mission = make_mission(budget=200000, upsell_cap=1.0)
    # Effective budget = 200000. Total 249900 > 200000 -> REJECT.
    proposal = make_proposal([("BAT-002", 1)])
    verdict = run_gateway(mission, proposal)
    assert verdict.decision == Decision.REJECT
    assert verdict.rule_id == "R1_BUDGET"


# ============================================================
# R5_SCOPE TESTS (2 tests)
# ============================================================

def test_r5_out_of_scope():
    """Item category not in allowed_categories -> REJECT R5_SCOPE."""
    mission = make_mission(budget=500000, allowed=("cricket",))
    # BOOK-001 is in "books" category, not allowed
    proposal = make_proposal([("BOOK-001", 1)])
    verdict = run_gateway(mission, proposal)
    assert verdict.decision == Decision.REJECT
    assert verdict.rule_id == "R5_SCOPE"


def test_r5_in_scope():
    """Item category in allowed_categories -> APPROVE."""
    mission = make_mission(budget=200000, allowed=("cricket",))
    proposal = make_proposal([("BAT-001", 1)])
    verdict = run_gateway(mission, proposal)
    assert verdict.decision == Decision.APPROVE


# ============================================================
# R6_RATE_LIMIT TESTS (3 tests)
# ============================================================

def test_r6_within_limit():
    """4 proposals in last 60s (below limit of 5) -> APPROVE."""
    mission = make_mission(budget=200000)
    now = int(time.time())
    state = {
        "proposal_ts": {
            mission.mission_id: [now - 10, now - 20, now - 30, now - 40]
        }
    }
    proposal = make_proposal([("BAT-001", 1)])
    verdict = run_gateway(mission, proposal, state=state, now_ts=now)
    assert verdict.decision == Decision.APPROVE


def test_r6_over_limit():
    """5 proposals in last 60s (at limit) -> REJECT R6_RATE_LIMIT."""
    mission = make_mission(budget=200000)
    now = int(time.time())
    state = {
        "proposal_ts": {
            mission.mission_id: [now - 10, now - 20, now - 30, now - 40, now - 50]
        }
    }
    proposal = make_proposal([("BAT-001", 1)])
    verdict = run_gateway(mission, proposal, state=state, now_ts=now)
    assert verdict.decision == Decision.REJECT
    assert verdict.rule_id == "R6_RATE_LIMIT"


def test_r6_window_expired():
    """5 proposals but all older than 60s -> APPROVE (window cleared)."""
    mission = make_mission(budget=200000)
    now = int(time.time())
    state = {
        "proposal_ts": {
            mission.mission_id: [now - 70, now - 80, now - 90, now - 100, now - 110]
        }
    }
    proposal = make_proposal([("BAT-001", 1)])
    verdict = run_gateway(mission, proposal, state=state, now_ts=now)
    assert verdict.decision == Decision.APPROVE


# ============================================================
# R7_ALLOWLIST TESTS (2 tests)
# ============================================================

def test_r7_merchant_allowlisted():
    """Merchant ID in allowlist -> APPROVE."""
    mission = make_mission(budget=200000)
    proposal = make_proposal([("BAT-001", 1)])
    verdict = run_gateway(mission, proposal, merchant_id="SELLABLE-DEMO")
    assert verdict.decision == Decision.APPROVE


def test_r7_merchant_not_allowlisted():
    """Merchant ID NOT in allowlist -> REJECT R7_ALLOWLIST."""
    mission = make_mission(budget=200000)
    proposal = make_proposal([("BAT-001", 1)])
    verdict = run_gateway(mission, proposal, merchant_id="UNKNOWN-MERCHANT")
    assert verdict.decision == Decision.REJECT
    assert verdict.rule_id == "R7_ALLOWLIST"


# ============================================================
# R8_ABORT TESTS (2 tests)
# ============================================================

def test_r8_mission_active():
    """Mission NOT in aborted set -> APPROVE."""
    mission = make_mission(budget=200000)
    proposal = make_proposal([("BAT-001", 1)])
    state = {"aborted_missions": frozenset({"OTHER-MISSION"})}
    verdict = run_gateway(mission, proposal, state=state)
    assert verdict.decision == Decision.APPROVE


def test_r8_mission_aborted():
    """Mission IS in aborted set -> REJECT R8_ABORT."""
    mission = make_mission(budget=200000)
    proposal = make_proposal([("BAT-001", 1)])
    state = {"aborted_missions": frozenset({mission.mission_id})}
    verdict = run_gateway(mission, proposal, state=state)
    assert verdict.decision == Decision.REJECT
    assert verdict.rule_id == "R8_ABORT"


# ============================================================
# R9_SIGNATURE TESTS (3 tests)
# ============================================================

def test_r9_valid_signature():
    """Properly signed mission -> passes R9, overall APPROVE."""
    mission = make_mission(budget=200000, sign=True)
    proposal = make_proposal([("BAT-001", 1)])
    verdict = run_gateway(mission, proposal)
    assert verdict.decision == Decision.APPROVE


def test_r9_tampered_signature():
    """Sign mission, then mutate budget -> signature breaks -> REJECT R9."""
    mission = make_mission(budget=200000, sign=True)
    # Mission is a frozen dataclass; bypass the freeze to simulate tamper.
    object.__setattr__(mission, "budget_paise", 999999)
    proposal = make_proposal([("BAT-001", 1)])
    verdict = run_gateway(mission, proposal)
    assert verdict.decision == Decision.REJECT
    assert verdict.rule_id == "R9_SIGNATURE"


def test_r9_missing_signature():
    """Empty signature string -> REJECT R9_SIGNATURE."""
    mission = make_mission(budget=200000, sign=False)
    proposal = make_proposal([("BAT-001", 1)])
    verdict = run_gateway(mission, proposal)
    assert verdict.decision == Decision.REJECT
    assert verdict.rule_id == "R9_SIGNATURE"


# ============================================================
# R10_EXPIRY TESTS (3 tests)
# ============================================================

def test_r10_not_expired():
    """Expiry in future -> APPROVE."""
    mission = make_mission(budget=200000, expires_in=3600)
    proposal = make_proposal([("BAT-001", 1)])
    verdict = run_gateway(mission, proposal)
    assert verdict.decision == Decision.APPROVE


def test_r10_expired():
    """Expiry in past -> REJECT R10_EXPIRY."""
    mission = make_mission(budget=200000, expires_in=-100)
    proposal = make_proposal([("BAT-001", 1)])
    verdict = run_gateway(mission, proposal)
    assert verdict.decision == Decision.REJECT
    assert verdict.rule_id == "R10_EXPIRY"


def test_r10_boundary_exact():
    """Expiry exactly equals now -> REJECT (>= comparison, == rejects)."""
    now = int(time.time())
    mission = make_mission(budget=200000, expires_in=0)
    # expires_at will be now + 0 = now
    proposal = make_proposal([("BAT-001", 1)])
    verdict = run_gateway(mission, proposal, now_ts=now)
    assert verdict.decision == Decision.REJECT
    assert verdict.rule_id == "R10_EXPIRY"


# ============================================================
# CROSS-CUTTING TESTS (4 tests)
# ============================================================

def test_first_violation_wins():
    """Both R1 and R2 would fire -> R1 cited (runs first in Phase 2)."""
    mission = make_mission(
        budget=10000,  # very low — R1 will fire
        allowed=("cricket",),
        forbidden=("cricket",),  # also forbidden — R2 would fire too
    )
    proposal = make_proposal([("BAT-001", 1)])  # 149900 > 13000 effective
    verdict = run_gateway(mission, proposal)
    assert verdict.decision == Decision.REJECT
    # R1 runs before R2 in Phase 2, so R1 is cited
    assert verdict.rule_id == "R1_BUDGET"


def test_guardrail_before_commerce():
    """Expired AND over budget -> R10 cited (Phase 0 before Phase 2)."""
    mission = make_mission(budget=10000, expires_in=-100)
    proposal = make_proposal([("BAT-001", 1)])
    verdict = run_gateway(mission, proposal)
    assert verdict.decision == Decision.REJECT
    # R10 (Phase 0) fires before R1 (Phase 2)
    assert verdict.rule_id == "R10_EXPIRY"


def test_fail_closed_missing_input():
    """Missing proposal -> REJECT INPUT_MISSING (fail-closed)."""
    mission = make_mission(budget=200000)
    verdict = run_gateway(mission, None)
    assert verdict.decision == Decision.REJECT
    assert verdict.rule_id == "INPUT_MISSING"


def test_chain_tamper_halts():
    """chain_ok=False -> REJECT CHAIN_TAMPER (system halt)."""
    mission = make_mission(budget=200000)
    proposal = make_proposal([("BAT-001", 1)])
    verdict = run_gateway(mission, proposal, chain_ok=False)
    assert verdict.decision == Decision.REJECT
    assert verdict.rule_id == "CHAIN_TAMPER"
