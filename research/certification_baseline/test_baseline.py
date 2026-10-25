"""Certification baseline: which payment-trace properties SELLABLE holds.

Every test asserts the property a trace certifier should guarantee.

History: in the original audit (branch `certification-baseline`, commit
2429725) 8 of these were
marked xfail(strict=True) because the system did not hold them. On the
`hardening` branch every one of the 8 now passes, so the markers are gone;
check out that branch to reproduce the original 3 passed / 8 xfailed.

Run from the repo root:
    pytest research/certification_baseline -v -rxX

The tests call the real route functions in apps/api/tools.py and
apps/api/execution_api.py on the simulated provider (no network).
"""
import asyncio
import importlib
import sqlite3
import time

import pytest
from fastapi import HTTPException

SKU = "BAT-001"                       # Rs 1,499 in apps/api/products.py
BUDGET = 300000                       # Rs 3,000: room for two, not three


# ------------------------------------------------------------------ helpers

def _call(fn, *args, **kwargs):
    """(status, body) as an HTTP client would see it."""
    try:
        out = fn(*args, **kwargs)
        if asyncio.iscoroutine(out):
            out = asyncio.run(out)
        return 200, out
    except HTTPException as exc:
        return exc.status_code, exc.detail


def _code(body):
    if isinstance(body, dict):
        err = body.get("error")
        if isinstance(err, dict):
            return err.get("error_code")
        return body.get("code") or err
    return body


def _mission(mid, budget=BUDGET):
    from apps.api.gateway.mission_verify import sign_mission
    from apps.api.gateway.types import canonical_json
    now = int(time.time())
    blob = {"mission_id": mid, "intent": "buy cricket gear", "budget_paise": budget,
            "allowed_categories": ("cricket",), "forbidden_categories": (),
            "upsell_cap": 1.0, "expires_at": now + 3600}
    out = {k: (list(v) if isinstance(v, tuple) else v) for k, v in blob.items()}
    out["signature"] = sign_mission(canonical_json(blob))
    return out


def _intent(mid, ceiling=BUDGET):
    import os

    from apps.api.mandates.mandates import IntentMandate, sign_intent
    now = int(time.time())
    return sign_intent(IntentMandate(mission_id=mid, user_id="u1", ceiling_paise=ceiling,
                                     expires_at=now + 3600), os.environ["USER_MANDATE_KEY"])


def _cart(mid, proposal_hash, amount):
    import os

    from apps.api.mandates.mandates import CartMandate, sign_cart
    now = int(time.time())
    return sign_cart(CartMandate(mission_id=mid, cart_hash=proposal_hash, amount_paise=amount,
                                 signed_at=now, expires_at=now + 3600),
                     os.environ["USER_MANDATE_KEY"])


def _propose(mission):
    from apps.api import tools
    return _call(tools.tool_submit_proposal,
                 tools.ProposalReq(mission=mission, items=[{"sku": SKU, "qty": 1}]))


def _authorize(mid, mission=None, intent=None):
    """Honest path up to, not including, create_order."""
    from apps.api import tools
    mission = mission or _mission(mid)
    s, q = _call(tools.tool_quote,
                 tools.QuoteReq(items=[{"sku": SKU, "qty": 1}], mission_id=mid))
    assert s == 200, q
    s, p = _propose(mission)
    assert s == 200 and p["data"]["decision"] == "APPROVE", p
    ph = p["data"]["proposal_hash"]
    return {"quote_id": q["quote_id"], "proposal_hash": ph, "approve_seq": p["seq"],
            "intent_mandate": intent or _intent(mid),
            "cart_mandate": _cart(mid, ph, q["total_paise"]),
            "_mid": mid, "_total": q["total_paise"]}


def _order(auth, idem, fault=""):
    from apps.api import tools
    body = {k: v for k, v in auth.items() if not k.startswith("_")}
    return _call(tools.tool_create_order, tools.CreateOrderReq(**body),
                 x_idempotency_key=idem, x_sellable_fault=fault)


def _provider_orders(proposal_hash):
    from apps.api import execution_provider as ep
    return [o for o in ep._SIMULATED_SINGLETON._orders.values()
            if o["notes"].get("proposal_hash") == proposal_hash]


def _exec_id(auth):
    from apps.api import execution as ex
    return ex.derive_execution_id(auth["_mid"], auth["proposal_hash"], auth["approve_seq"])


# ---------------------------------------------------------- properties held

def test_replaying_an_executed_authorization_returns_the_same_order():
    from apps.api import execution as ex
    a = _authorize("m-replay")
    s1, first = _order(a, "idem-a")
    s2, second = _order(a, "idem-b-different-header")
    assert s1 == 200 and first["execution_state"] == ex.EXECUTED
    assert s2 == 200 and second["order_id"] == first["order_id"]
    assert len(_provider_orders(a["proposal_hash"])) == 1


def test_a_lost_response_is_recovered_without_a_second_charge():
    from apps.api import execution as ex
    from apps.api import execution_api
    a = _authorize("m-lost-response")
    _order(a, "idem-1", fault="remote_timeout")
    assert ex.get(_exec_id(a))["state"] == ex.RECONCILIATION_REQUIRED
    s_retry, retry = _order(a, "idem-2")
    assert s_retry == 409 and _code(retry) == "RECONCILIATION_REQUIRED"
    s, rec = _call(execution_api.reconcile, _exec_id(a))
    assert s == 200 and rec["state"] == ex.EXECUTED
    assert len(_provider_orders(a["proposal_hash"])) == 1


def test_mcp_path_rechecks_cumulative_spend_and_revocation(tmp_path, monkeypatch):
    """The MCP server path enforces both properties the API path misses."""
    monkeypatch.setenv("SELLABLE_HOME", str(tmp_path / "mcp_home"))
    from mcp_server import server, store

    rec = store.new_mission(intent="cricket gear", budget_paise=BUDGET,
                            allowed=["cricket"], forbidden=[], hours=1)
    results = []
    for _ in range(3):
        p = server.tool_propose_purchase(rec["mission_id"], [{"sku": SKU, "qty": 1}])
        results.append(server.tool_place_order(p["approval_id"])["status"]
                       if p.get("approval_id") else p["rule_id"])
    assert results == ["PAID", "PAID", "SPEND"]
    assert store.spent_paise(rec["mission_id"]) <= BUDGET

    rec = store.new_mission(intent="cricket gear", budget_paise=BUDGET,
                            allowed=["cricket"], forbidden=[], hours=1)
    p = server.tool_propose_purchase(rec["mission_id"], [{"sku": SKU, "qty": 1}])
    missions = store.missions()
    missions[rec["mission_id"]]["revoked"] = True          # `sellable-mcp mission revoke`
    store.save_missions(missions)
    assert server.tool_place_order(p["approval_id"])["status"] == "REFUSED"


# ------------------------------- properties that were gaps at the baseline

def test_cumulative_spend_in_a_mission_stays_within_its_budget():
    """Trace non-compositionality: each order passes R1 and the intent
    ceiling alone; three of them exceed the mission budget together."""
    from apps.api import execution as ex
    mid = "m-cumulative"
    mission, intent = _mission(mid), _intent(mid, BUDGET)
    spent = 0
    for i in range(3):
        s, p = _propose(mission)
        if s != 200 or p["data"]["decision"] != "APPROVE":
            continue
        from apps.api import tools
        _, q = _call(tools.tool_quote,
                     tools.QuoteReq(items=[{"sku": SKU, "qty": 1}], mission_id=mid))
        ph = p["data"]["proposal_hash"]
        a = {"quote_id": q["quote_id"], "proposal_hash": ph, "approve_seq": p["seq"],
             "intent_mandate": intent, "cart_mandate": _cart(mid, ph, q["total_paise"])}
        so, out = _order(a, f"idem-cum-{i}")
        if so == 200 and out["execution_state"] == ex.EXECUTED:
            spent += out["amount_paise"]
    assert spent <= BUDGET, f"executed {spent} paise against a {BUDGET} paise budget"


def test_revoking_a_mission_stops_payments_it_already_approved():
    """Stale approval. At the baseline the API path had no revoke route at
    all; the hardened path revokes durably and re-checks at execution."""
    from apps.api import execution as ex
    from apps.api import tools
    mid = "m-revoked"
    mission = _mission(mid)
    a = _authorize(mid, mission)
    _call(tools.tool_revoke_mission, tools.RevokeReq(mission_id=mid, reason="user changed mind"))
    s, p = _propose(mission)
    assert p["data"]["rule_id"] == "R8_ABORT"                  # gateway refuses new ones
    so, out = _order(a, "idem-revoked")
    assert not (so == 200 and out["execution_state"] == ex.EXECUTED)


def test_reconciliation_only_accepts_the_executions_own_order():
    """Execution conformance on recovery. Two identical baskets in one
    mission share a proposal hash; the second request never leaves the
    process, and reconciliation must not adopt the first order as its own."""
    from apps.api import execution as ex
    from apps.api import execution_api
    mid = "m-collision"
    mission, intent = _mission(mid), _intent(mid, 10 * BUDGET)
    first = _authorize(mid, mission, intent)
    assert _order(first, "idem-c1")[1]["execution_state"] == ex.EXECUTED
    second = _authorize(mid, mission, intent)
    assert second["proposal_hash"] == first["proposal_hash"]
    _order(second, "idem-c2", fault="remote_lost")              # never dispatched
    s, rec = _call(execution_api.reconcile, _exec_id(second))
    real_orders = len(_provider_orders(first["proposal_hash"]))
    assert real_orders == 1
    assert not (s == 200 and rec["state"] == ex.EXECUTED), \
        f"unpaid purchase recorded as paid via {rec.get('remote_order_id')}"


def test_an_executed_approval_cannot_pay_again_after_a_database_restore(_isolated):
    from apps.api import tools
    from apps.api.audit import chain
    a = _authorize("m-restore")
    backup = sqlite3.connect(":memory:")
    with sqlite3.connect(str(_isolated)) as live:
        live.backup(backup)                                    # backup after approval
    _order(a, "idem-restore")
    with sqlite3.connect(str(_isolated)) as live:
        backup.backup(live)                                    # routine restore
    chain._chain.clear()
    chain._load_from_db()
    importlib.reload(tools)                                    # restart after restore
    _order(a, "idem-restore")
    assert len(_provider_orders(a["proposal_hash"])) <= 1


def test_the_rate_window_survives_a_restart():
    """Proof memory: R6 can only hold if the proposal history persists."""
    from apps.api import tools
    mission = _mission("m-restart")
    for _ in range(10):
        s, p = _propose(mission)
        if p["data"]["rule_id"] == "R6_RATE_LIMIT":
            break
    else:
        pytest.fail("R6 never fired")
    importlib.reload(tools)                                    # restart
    s, p = _propose(mission)
    assert p["data"]["rule_id"] == "R6_RATE_LIMIT"


def test_an_approval_records_the_policy_version_it_passed():
    """Policy lineage: needed to audit or re-certify after a rule change.
    (The baseline test looked for a `policy_version` column; the hardened
    binding records a digest of the whole policy instead.)"""
    from apps.api import approval
    a = _authorize("m-lineage")
    b = approval.get(a["approve_seq"])
    assert b.policy_digest == approval.current_policy_digest()
    assert len(b.policy_digest) == 64


def test_the_verifier_cannot_mint_the_users_mandates(monkeypatch):
    """Custody. At the baseline, mandates were HMACs checked with the key
    that signs them. In user-held mode the server has only the user's
    public key: whatever it can sign with its own secrets is refused."""
    from apps.api import execution as ex
    from apps.api.mandates.mandates import generate_keypair
    _wallet_private, public = generate_keypair()
    monkeypatch.setenv("USER_MANDATE_PUBLIC_KEY", public)
    a = _authorize("m-custody")
    minted = dict(a, intent_mandate=_intent("m-custody"),
                  cart_mandate=_cart("m-custody", a["proposal_hash"], a["_total"]))
    s, out = _order(minted, "idem-custody")
    assert not (s == 200 and out["execution_state"] == ex.EXECUTED)
    assert s == 403 and out["code"] == "MANDATE_ALG_NOT_ALLOWED"


def test_a_refused_mandate_does_not_burn_a_valid_approval():
    """Completion: the binding is consumed before the mandates are checked."""
    a = _authorize("m-burn")
    bad = dict(a, cart_mandate=_cart("m-burn", a["proposal_hash"], a["_total"] + 1))
    s1, b1 = _order(bad, "idem-burn-1")
    assert s1 == 403 and _code(b1) == "MANDATE_AMOUNT_MISMATCH"
    s2, b2 = _order(a, "idem-burn-2")
    assert s2 == 200, _code(b2)
