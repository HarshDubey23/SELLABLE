"""R1-R10 pure rule functions. Violation | None. stdlib only."""

from collections.abc import Callable, Iterable
from typing import Any

from .types import Mission, Proposal, ProposalItem, Violation

VerifyFn = Callable[[str, str], bool]
Catalog = dict[str, dict[str, Any]]


def rule_r9_signature(mission: Mission | None,
                      verify_fn: VerifyFn) -> Violation | None:
    if mission is None or not getattr(mission, "signature", ""):
        return Violation("R9_SIGNATURE", "mission signature missing (fail-closed)")
    blob = {k: v for k, v in vars(mission).items() if k != "signature"}
    from .types import canonical_json
    if not verify_fn(canonical_json(blob), mission.signature):
        return Violation("R9_SIGNATURE", "mission HMAC does not verify")
    return None


def rule_r10_expiry(mission: Mission, now_ts: int) -> Violation | None:
    # == also rejects: fail-closed at the boundary
    if now_ts >= mission.expires_at:
        return Violation(
            "R10_EXPIRY",
            f"mission expired at {mission.expires_at}, now {now_ts}",
            attempted_value=now_ts, limit_value=mission.expires_at,
            hint="request a fresh signed mission",
        )
    return None


def rule_r8_abort(mission_id: str, aborted_ids: frozenset[str]) -> Violation | None:
    if mission_id in aborted_ids:
        return Violation("R8_ABORT", f"mission {mission_id} is aborted; terminal")
    return None


def _total(catalog: Catalog, items: Iterable[ProposalItem]) -> int:
    return sum(catalog[i.sku]["price_paise"] * i.qty for i in items)


def rule_r1_budget(proposal: Proposal, catalog: Catalog, mission: Mission) -> Violation | None:
    total = _total(catalog, proposal.items)
    if total > mission.budget_paise:
        over = total - mission.budget_paise
        return Violation(
            "R1_BUDGET",
            f"total {total} paise exceeds budget {mission.budget_paise} paise by {over}",
            attempted_value=total, limit_value=mission.budget_paise,
            hint="drop an item, reduce qty, or pick a cheaper sku",
        )
    return None


def rule_r2_forbidden(proposal: Proposal, catalog: Catalog, mission: Mission) -> Violation | None:
    for i in proposal.items:
        cat = catalog[i.sku]["category"]
        if cat in mission.forbidden_categories:
            return Violation(
                "R2_FORBIDDEN",
                f"{i.sku} is category '{cat}' which is forbidden on this mission",
                hint="pick from allowed categories only",
            )
    return None


def rule_r5_scope(proposal: Proposal, catalog: Catalog, mission: Mission) -> Violation | None:
    for i in proposal.items:
        cat = catalog[i.sku]["category"]
        if mission.allowed_categories and cat not in mission.allowed_categories:
            return Violation(
                "R5_SCOPE",
                f"{i.sku} is category '{cat}' outside mission scope",
                hint="stay within allowed_categories",
            )
    return None


def rule_r4_upsell_cap(proposal: Proposal, catalog: Catalog, mission: Mission,
                       baseline_total: int) -> Violation | None:
    cap = int(mission.budget_paise * mission.upsell_cap)
    total = _total(catalog, proposal.items)
    if total > cap:
        return Violation(
            "R4_UPSELL_CAP",
            f"total {total} exceeds upsell cap {cap} "
            f"(budget x{mission.upsell_cap}, baseline {baseline_total})",
            attempted_value=total, limit_value=cap,
            hint="remove upsell items",
        )
    return None


def rule_r3_price_drift(proposal: Proposal, catalog: Catalog) -> Violation | None:
    for i in proposal.items:
        truth = catalog[i.sku]["price_paise"]
        if i.price_paise != truth:
            return Violation(
                "R3_PRICE_DRIFT",
                f"{i.sku}: claimed {i.price_paise} != catalog {truth} paise",
                attempted_value=i.price_paise, limit_value=truth,
                hint="re-request quote; prices come from the server only",
            )
    return None


def rule_r6_rate_limit(mission_id: str, state: dict[str, Any], now_ts: int,
                       max_per_window: int = 5, window_s: int = 60) -> Violation | None:
    recent = [t for t in state.get("proposal_ts", {}).get(mission_id, [])
              if now_ts - t < window_s]
    if len(recent) >= max_per_window:
        return Violation(
            "R6_RATE_LIMIT",
            f"{len(recent)} proposals in last {window_s}s (max {max_per_window})",
            attempted_value=len(recent), limit_value=max_per_window,
            hint=f"wait {window_s - (now_ts - recent[-1])}s",
        )
    return None


def rule_r7_allowlist(merchant_id: str, allowlist: frozenset[str]) -> Violation | None:
    if merchant_id not in allowlist:
        return Violation("R7_ALLOWLIST", f"merchant '{merchant_id}' not allowlisted")
    return None
