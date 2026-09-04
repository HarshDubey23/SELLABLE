"""The negotiation transcript does its own arithmetic.

A saving is a claim about money, so the server computes it from the
stored ceiling and the stored final offer. A page that subtracts two
numbers it was handed can be made to show any saving at all; a number
derived from rows cannot.

The other thing the transcript has to carry is `clamped`: the flag that
says a model asked for a price outside the merchant's bounds and the
bounds layer pulled it back. That is the entire negotiation safety story,
so it is reported per offer rather than summarised away.
"""
from __future__ import annotations

import pytest
from fastapi.testclient import TestClient


@pytest.fixture
def client(monkeypatch):
    monkeypatch.setenv("RAZORPAY_KEY_ID", "")
    monkeypatch.setenv("RAZORPAY_KEY_SECRET", "")
    from apps.api.main import app
    c = TestClient(app)
    # conftest sets APP_API_KEY, so the mutating negotiation routes are
    # gated. The transcript read is deliberately open.
    c.headers.update({"X-API-Key": "test_app_api_key"})
    return c


CEILING = 249900
FLOOR = 180000


def _start(client, **over):
    body = {"mission_id": "MSN-NEG-T1", "sku": "BAT-002", "qty": 1,
            "floor_paise": FLOOR, "ceiling_paise": CEILING,
            "buyer_budget_paise": 300000, "max_turns": 3,
            "llm_enabled": False}
    body.update(over)
    r = client.post("/negotiation/start", json=body)
    assert r.status_code == 200, r.text
    return r.json()["negotiation_id"]


def test_transcript_reports_savings_computed_from_stored_rows(client):
    nid = _start(client)
    client.post(f"/negotiation/{nid}/run", json={"llm_enabled": False})

    r = client.get(f"/negotiation/{nid}/transcript")
    assert r.status_code == 200
    t = r.json()

    assert t["original_price_paise"] == CEILING, \
        "the baseline is the merchant's stored ceiling, not a client input"
    if t["final_price_paise"] is not None:
        assert t["savings_paise"] == max(0, CEILING - t["final_price_paise"])
        assert t["savings_paise"] >= 0, "a negotiation never invents a loss"
    else:
        assert t["savings_paise"] is None, \
            "no agreed price means no saving may be claimed"


def test_every_offer_declares_whether_policy_clamped_it(client):
    nid = _start(client)
    client.post(f"/negotiation/{nid}/run", json={"llm_enabled": False})
    t = client.get(f"/negotiation/{nid}/transcript").json()

    assert t["turns"], "a completed negotiation has turns"
    for turn in t["turns"]:
        for side in ("buyer_offer", "merchant_offer"):
            offer = turn.get(side)
            if offer is None:
                continue
            assert "clamped" in offer
            assert offer["clamped"] == (
                offer["price_paise"] != offer["raw_price_paise"])
            assert offer["clamp_delta_paise"] == (
                offer["raw_price_paise"] - offer["price_paise"])


def test_no_recorded_price_ever_escapes_the_merchant_bounds(client):
    """The clamp is the point: raw may be anything, recorded may not."""
    nid = _start(client)
    client.post(f"/negotiation/{nid}/run", json={"llm_enabled": False})
    t = client.get(f"/negotiation/{nid}/transcript").json()

    for turn in t["turns"]:
        for side in ("buyer_offer", "merchant_offer"):
            offer = turn.get(side)
            if offer is None:
                continue
            assert FLOOR <= offer["price_paise"] <= CEILING, (
                f"{side} recorded {offer['price_paise']} outside "
                f"[{FLOOR}, {CEILING}] — the bounds layer did not hold")


def test_clamped_turn_count_matches_the_offers(client):
    nid = _start(client)
    client.post(f"/negotiation/{nid}/run", json={"llm_enabled": False})
    t = client.get(f"/negotiation/{nid}/transcript").json()

    counted = sum(1 for turn in t["turns"]
                  for side in ("buyer_offer", "merchant_offer")
                  if (turn.get(side) or {}).get("clamped"))
    assert t["clamped_turn_count"] == counted


def test_an_unknown_negotiation_is_404(client):
    assert client.get("/negotiation/neg_nope/transcript").status_code == 404
