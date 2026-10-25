"""Regression tests for the hardening of the /tools money path.

Each test pins one fix for a gap the certification baseline found at tag
`baseline-2429725` (see research/certification_baseline/). They call the
real route functions on the simulated provider; nothing reaches a network.
"""
import asyncio
import importlib
import sqlite3
import threading
import time

import pytest
from fastapi import HTTPException

SKU = "BAT-001"                # Rs 1,499
PRICE = 149900


# ------------------------------------------------------------------ helpers

@pytest.fixture(autouse=True)
def _clean(monkeypatch):
    monkeypatch.setenv("RAZORPAY_KEY_ID", "")
    monkeypatch.setenv("RAZORPAY_KEY_SECRET", "")
    monkeypatch.delenv("USER_MANDATE_PUBLIC_KEY", raising=False)
    from apps.api import execution_provider as ep
    ep._SIMULATED_SINGLETON._orders.clear()
    yield
    ep._SIMULATED_SINGLETON._orders.clear()


def _call(fn, *args, **kwargs):
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


def _mission(mid, budget):
    from apps.api.gateway.mission_verify import sign_mission
    from apps.api.gateway.types import canonical_json
    blob = {"mission_id": mid, "intent": "buy cricket gear", "budget_paise": budget,
            "allowed_categories": ("cricket",), "forbidden_categories": (),
            "upsell_cap": 1.0, "expires_at": int(time.time()) + 3600}
    out = {k: (list(v) if isinstance(v, tuple) else v) for k, v in blob.items()}
    out["signature"] = sign_mission(canonical_json(blob))
    return out


def _hmac_intent(mid, ceiling):
    import os

    from apps.api.mandates.mandates import IntentMandate, sign_intent
    return sign_intent(IntentMandate(mission_id=mid, user_id="u1", ceiling_paise=ceiling,
                                     expires_at=int(time.time()) + 3600),
                       os.environ["USER_MANDATE_KEY"])


def _hmac_cart(mid, phash, amount):
    import os

    from apps.api.mandates.mandates import CartMandate, sign_cart
    now = int(time.time())
    return sign_cart(CartMandate(mission_id=mid, cart_hash=phash, amount_paise=amount,
                                 signed_at=now, expires_at=now + 3600),
                     os.environ["USER_MANDATE_KEY"])


def _propose(mission):
    from apps.api import tools
    return _call(tools.tool_submit_proposal,
                 tools.ProposalReq(mission=mission, items=[{"sku": SKU, "qty": 1}]))


def _authorize(mid, mission, *, sign=True):
    from apps.api import tools
    s, q = _call(tools.tool_quote,
                 tools.QuoteReq(items=[{"sku": SKU, "qty": 1}], mission_id=mid))
    assert s == 200, q
    s, p = _propose(mission)
    assert s == 200 and p["data"]["decision"] == "APPROVE", p
    ph = p["data"]["proposal_hash"]
    a = {"quote_id": q["quote_id"], "proposal_hash": ph, "approve_seq": p["seq"],
         "_mid": mid, "_total": q["total_paise"]}
    if sign:
        a["intent_mandate"] = _hmac_intent(mid, mission["budget_paise"])
        a["cart_mandate"] = _hmac_cart(mid, ph, q["total_paise"])
    return a


def _order(auth, idem, fault=""):
    from apps.api import tools
    body = {k: v for k, v in auth.items() if not k.startswith("_")}
    return _call(tools.tool_create_order, tools.CreateOrderReq(**body),
                 x_idempotency_key=idem, x_sellable_fault=fault)


def _consumed(seq):
    from apps.api.store import db as store
    return store.query_one("SELECT consumed_at FROM bindings WHERE seq = ?",
                           (seq,))["consumed_at"]


def _orders_for(phash):
    from apps.api import execution_provider as ep
    return [o for o in ep._SIMULATED_SINGLETON._orders.values()
            if o["notes"].get("proposal_hash") == phash]


def _exec_id(a):
    from apps.api import execution as ex
    return ex.derive_execution_id(a["_mid"], a["proposal_hash"], a["approve_seq"])


# ------------------------------------------------------- cumulative budget

def test_a_purchase_past_the_mission_budget_is_refused_without_burning_it():
    from apps.api import execution as ex
    mid = "h-budget"
    mission = _mission(mid, 300000)
    first, second = _authorize(mid, mission), _authorize(mid, mission)
    assert _order(first, "i1")[1]["execution_state"] == ex.EXECUTED
    assert _order(second, "i2")[1]["execution_state"] == ex.EXECUTED
    third = _authorize(mid, mission)
    s, out = _order(third, "i3")
    assert (s, _code(out)) == (409, "MISSION_BUDGET_EXHAUSTED")
    assert out["error"]["committed_paise"] == 2 * PRICE
    assert _consumed(third["approve_seq"]) is None, "a budget refusal must not burn the approval"
    assert ex.committed_spend(mid) == 2 * PRICE


def test_two_racing_purchases_cannot_both_take_the_last_of_the_budget():
    from apps.api import execution as ex
    mid = "h-race"
    mission = _mission(mid, 200000)                  # room for exactly one
    a1, a2 = _authorize(mid, mission), _authorize(mid, mission)
    results = []
    barrier = threading.Barrier(2)

    def run(a, idem):
        barrier.wait()
        results.append(_order(a, idem))

    threads = [threading.Thread(target=run, args=(a1, "r1")),
               threading.Thread(target=run, args=(a2, "r2"))]
    for t in threads:
        t.start()
    for t in threads:
        t.join()
    executed = [r for r in results if r[0] == 200 and r[1]["execution_state"] == ex.EXECUTED]
    refused = [r for r in results if _code(r[1]) == "MISSION_BUDGET_EXHAUSTED"]
    assert (len(executed), len(refused)) == (1, 1), results
    assert ex.committed_spend(mid) == PRICE


# ------------------------------------------------------------- revocation

def test_revocation_is_durable_and_stops_approvals_issued_before_it():
    from apps.api import tools
    mid = "h-revoke"
    mission = _mission(mid, 300000)
    a = _authorize(mid, mission)
    s, out = _call(tools.tool_revoke_mission, tools.RevokeReq(mission_id=mid, reason="test"))
    assert s == 200 and out["already_revoked"] is False
    importlib.reload(tools)                                # survives a restart
    s, p = _propose(mission)
    assert p["data"]["rule_id"] == "R8_ABORT"
    s, out = _order(a, "rv1")
    assert (s, _code(out)) == (409, "MISSION_REVOKED")
    assert _orders_for(a["proposal_hash"]) == []
    s, again = _call(tools.tool_revoke_mission, tools.RevokeReq(mission_id=mid))
    assert again["already_revoked"] is True


# ---------------------------------------------------------- reconciliation

def test_reconciliation_does_not_adopt_another_purchases_order():
    from apps.api import execution as ex
    from apps.api import execution_api
    mid = "h-collide"
    mission = _mission(mid, 900000)
    first = _authorize(mid, mission)
    assert _order(first, "c1")[1]["execution_state"] == ex.EXECUTED
    second = _authorize(mid, mission)
    assert second["proposal_hash"] == first["proposal_hash"]
    _order(second, "c2", fault="remote_lost")              # never left
    s, rec = _call(execution_api.reconcile, _exec_id(second))
    assert s == 200 and rec["state"] == ex.FAILED and rec["resolution"] == "NO_REMOTE_ORDER"
    assert len(_orders_for(first["proposal_hash"])) == 1


def test_reconciliation_still_recovers_its_own_lost_order():
    from apps.api import execution as ex
    from apps.api import execution_api
    mid = "h-own"
    a = _authorize(mid, _mission(mid, 300000))
    _order(a, "o1", fault="remote_timeout")                # order made, reply lost
    s, rec = _call(execution_api.reconcile, _exec_id(a))
    assert s == 200 and rec["state"] == ex.EXECUTED
    (order,) = _orders_for(a["proposal_hash"])
    assert order["notes"]["execution_id"] == _exec_id(a)
    assert rec["remote_order_id"] == order["id"]


def test_order_matching_uses_execution_identity_with_a_legacy_fallback():
    from apps.api.execution_provider import order_matches
    base = {"proposal_hash": "p", "quote_id": "q1"}
    kw = dict(proposal_hash="p", amount_paise=100)
    assert order_matches({**base, "execution_id": "e1"}, 100, execution_id="e1", **kw)
    assert not order_matches({**base, "execution_id": "e1"}, 100, execution_id="e2", **kw)
    assert order_matches(base, 100, execution_id="e9", quote_id="q1", **kw)   # legacy order
    assert not order_matches(base, 100, execution_id="e9", quote_id="q2", **kw)
    assert order_matches(base, 100, **kw)                                      # legacy caller
    assert not order_matches({**base, "execution_id": "e1"}, 101, execution_id="e1", **kw)


# ---------------------------------------------------------- replay/restore

def test_a_restored_database_cannot_pay_an_executed_approval_twice(tmp_path):
    from apps.api import execution as ex
    from apps.api import tools
    from apps.api.audit import chain
    from apps.api.store import db as store
    mid = "h-restore"
    a = _authorize(mid, _mission(mid, 300000))
    backup = sqlite3.connect(":memory:")
    with sqlite3.connect(str(store._DB_PATH)) as live:
        live.backup(backup)
    s1, first = _order(a, "rs")
    with sqlite3.connect(str(store._DB_PATH)) as live:
        backup.backup(live)
    chain._chain.clear()
    chain._load_from_db()
    importlib.reload(tools)
    s2, second = _order(a, "rs")
    assert first["execution_state"] == second["execution_state"] == ex.EXECUTED
    assert second["order_id"] == first["order_id"] and second["adopted_from_provider"] is True
    assert len(_orders_for(a["proposal_hash"])) == 1


def test_an_unreadable_provider_blocks_dispatch_and_the_retry_completes(monkeypatch):
    from apps.api import execution as ex
    from apps.api import execution_provider as ep
    mid = "h-precheck"
    a = _authorize(mid, _mission(mid, 300000))
    real = ep._SIMULATED_SINGLETON.find_order_by_correlation

    def down(**kw):
        raise ConnectionError("provider listing unavailable")

    monkeypatch.setattr(ep._SIMULATED_SINGLETON, "find_order_by_correlation", down)
    s, out = _order(a, "pc1")
    assert (s, _code(out)) == (503, "REPLAY_CHECK_UNAVAILABLE")
    assert _orders_for(a["proposal_hash"]) == []
    assert ex.get(_exec_id(a))["state"] == ex.EXECUTION_PENDING
    monkeypatch.setattr(ep._SIMULATED_SINGLETON, "find_order_by_correlation", real)
    s, out = _order(a, "pc1")
    assert s == 200 and out["execution_state"] == ex.EXECUTED
    assert len(_orders_for(a["proposal_hash"])) == 1


# ------------------------------------------------------------ proof memory

def test_the_rate_window_survives_a_restart():
    from apps.api import tools
    mission = _mission("h-rate", 300000)
    for _ in range(10):
        s, p = _propose(mission)
        if p["data"]["rule_id"] == "R6_RATE_LIMIT":
            break
    else:
        pytest.fail("R6 never fired")
    importlib.reload(tools)
    assert _propose(mission)[1]["data"]["rule_id"] == "R6_RATE_LIMIT"


# ---------------------------------------------------------- policy lineage

def test_a_policy_change_after_approval_invalidates_it_without_consuming(monkeypatch):
    from apps.api import approval
    from apps.api import execution as ex
    mid = "h-policy"
    a = _authorize(mid, _mission(mid, 300000))
    assert approval.get(a["approve_seq"]).policy_digest == approval.current_policy_digest()
    original = approval.current_policy_digest
    monkeypatch.setattr(approval, "current_policy_digest", lambda: "0" * 64)
    s, out = _order(a, "pol1")
    assert (s, _code(out)) == (403, "POLICY_CHANGED")
    assert _consumed(a["approve_seq"]) is None and _orders_for(a["proposal_hash"]) == []
    monkeypatch.setattr(approval, "current_policy_digest", original)
    s, out = _order(a, "pol2")
    assert s == 200 and out["execution_state"] == ex.EXECUTED


def test_a_legacy_binding_without_lineage_or_budget_still_executes():
    from apps.api import execution as ex
    from apps.api.store import db as store
    mid = "h-legacy"
    a = _authorize(mid, _mission(mid, 300000))
    store.execute("UPDATE bindings SET policy_digest = NULL, mission_budget_paise = NULL "
                  "WHERE seq = ?", (a["approve_seq"],))
    s, out = _order(a, "leg")
    assert s == 200 and out["execution_state"] == ex.EXECUTED


# ----------------------------------------------------------------- custody

def test_user_held_keys_accept_the_wallet_and_refuse_the_server(monkeypatch):
    from apps.api import execution as ex
    from apps.api.mandates.mandates import (
        CartMandate,
        IntentMandate,
        custody_mode,
        generate_keypair,
        sign_cart_ed25519,
        sign_intent_ed25519,
    )
    assert custody_mode() == "shared-hmac"
    wallet_private, public = generate_keypair()
    monkeypatch.setenv("USER_MANDATE_PUBLIC_KEY", public)
    assert custody_mode() == "user-held-ed25519"
    mid = "h-custody"
    a = _authorize(mid, _mission(mid, 300000), sign=False)
    now = int(time.time())
    intent = sign_intent_ed25519(IntentMandate(mission_id=mid, user_id="u1",
                                               ceiling_paise=300000,
                                               expires_at=now + 3600), wallet_private)
    cart = sign_cart_ed25519(CartMandate(mission_id=mid, cart_hash=a["proposal_hash"],
                                         amount_paise=a["_total"], signed_at=now,
                                         expires_at=now + 3600), wallet_private)
    # The server's own secrets cannot stand in for the wallet ...
    s, out = _order(dict(a, intent_mandate=_hmac_intent(mid, 300000),
                         cart_mandate=_hmac_cart(mid, a["proposal_hash"], a["_total"])), "k1")
    assert (s, out["code"]) == (403, "MANDATE_ALG_NOT_ALLOWED")
    # ... a forged Ed25519 signature fails ...
    forged = dict(cart, sig=cart["sig"][:-4] + ("AAAA" if not cart["sig"].endswith("AAAA") else "BBBB"))
    s, out = _order(dict(a, intent_mandate=intent, cart_mandate=forged), "k2")
    assert (s, out["code"]) == (403, "MANDATE_BAD_SIGNATURE")
    # ... and the wallet's signatures pay, with the approval still intact.
    s, out = _order(dict(a, intent_mandate=intent, cart_mandate=cart), "k3")
    assert s == 200 and out["execution_state"] == ex.EXECUTED


# -------------------------------------------------------------- completion

def test_a_corrected_mandate_completes_but_a_changed_cart_needs_new_consent():
    from apps.api import execution as ex
    mid = "h-retry"
    a = _authorize(mid, _mission(mid, 300000))
    s, out = _order(dict(a, cart_mandate=_hmac_cart(mid, a["proposal_hash"], a["_total"] + 1)), "t1")
    assert (s, out["code"]) == (403, "MANDATE_AMOUNT_MISMATCH")
    s, out = _order(dict(a, cart_mandate=_hmac_cart(mid, "f" * 64, a["_total"])), "t2")
    assert (s, out["code"]) == (403, "MANDATE_CART_MISMATCH")
    assert _consumed(a["approve_seq"]) is None
    s, out = _order(a, "t3")
    assert s == 200 and out["execution_state"] == ex.EXECUTED
