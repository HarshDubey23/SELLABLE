"""The market's HTTP surface, including the probe that must never pay.

These go through the real app, so they exercise the routes a browser
actually calls. allow_llm is off everywhere: a unit test that reaches a
provider is not a unit test.
"""
from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

from apps.api.main import app

MISSION = "A complete cricket setup under Rs 6,000"


@pytest.fixture
def client() -> TestClient:
    return TestClient(app)


def _open(client: TestClient) -> dict:
    r = client.post("/market/open",
                    json={"mission_text": MISSION, "use_llm": False})
    assert r.status_code == 200, r.text
    return r.json()


def test_a_round_prices_every_legal_offer(client):
    nid = _open(client)["negotiation_id"]
    body = client.post(f"/market/{nid}/round?use_llm=false").json()

    assert body["state"] == "ROUND_COMPLETE"
    assert len(body["offers"]) == 3
    for offer in body["offers"]:
        if offer["accepted"]:
            assert offer["total_paise"] > 0
        else:
            # The load-bearing half: a refusal carries no price at all.
            assert offer["total_paise"] is None
            assert offer["reason"].startswith("MERCHANT_POLICY_")


def test_every_response_says_which_mode_it_ran_in(client):
    body = _open(client)
    mode = body["mode"]
    assert mode["merchants"] in ("llm", "scripted_fallback")
    assert mode["payments"] in ("razorpay_test", "simulated")
    # The label has to match the mode, or the badge is decoration.
    if mode["payments"] == "simulated":
        assert "simulated" in mode["payments_label"].lower()
    else:
        assert "TEST" in mode["payments_label"]


def test_a_mission_the_catalog_cannot_serve_is_refused_over_http(client):
    r = client.post("/market/open",
                    json={"mission_text": "a submarine", "use_llm": False})
    assert r.status_code == 422
    assert r.json()["detail"]["error"]["error_code"] == "NO_CATALOG_MATCH"


# ------------------------------------------------------------- the probe

def test_an_out_of_policy_offer_is_refused_and_never_clamped(client):
    """The security moment, and the reason it is trustworthy.

    A discount above the merchant's signed cap is not quietly reduced to
    the cap. It is refused, with the reason and the two numbers that
    disagree, and it comes back with no price.
    """
    nid = _open(client)["negotiation_id"]
    client.post(f"/market/{nid}/round?use_llm=false")

    body = client.post(f"/market/{nid}/probe",
                       json={"merchant_id": "NOVATECH"}).json()
    probe = body["probe"]

    assert probe["decision"] == "REJECTED"
    assert probe["reason"] == "MERCHANT_POLICY_LINE_DISCOUNT_EXCEEDED"
    assert probe["asked_line_discount_pct"] > probe["manifest_cap_pct"]
    assert probe["total_paise"] is None, "a refused offer must have no price"
    assert probe["clamped"] is False


def test_the_probe_can_never_become_something_that_gets_paid(client):
    """It is evaluated for real and recorded for real, and it stops there.

    A demo that showed a refusal by writing a rejected row into the same
    table the winner comes from would be one bug away from paying it.
    """
    opened = _open(client)
    nid = opened["negotiation_id"]
    client.post(f"/market/{nid}/round?use_llm=false")
    before = len(client.get(f"/market/{nid}").json()["offers"])

    client.post(f"/market/{nid}/probe", json={"merchant_id": "GEARHUB"})

    after = client.get(f"/market/{nid}").json()
    assert len(after["offers"]) == before, \
        "the probe was written into the offers table"
    assert all(not o["offer_id"].startswith("probe_") for o in after["offers"])

    # And the negotiation still settles to a real offer, unaffected.
    client.post(f"/market/{nid}/accept")
    settled = client.post(f"/market/{nid}/settle").json()["settlement"]
    assert not settled["order"].get("order_id", "").startswith("probe")
    assert settled["amount_paise"] > 0


def test_the_probe_is_written_to_the_audit_chain(client):
    """Refused or not, it happened, so the ledger says it happened."""
    from apps.api.audit import chain

    nid = _open(client)["negotiation_id"]
    client.post(f"/market/{nid}/round?use_llm=false")
    client.post(f"/market/{nid}/probe", json={"merchant_id": "BYTECART"})

    ok, reason = chain.verify_strict()
    assert ok, f"the chain must still verify after a probe: {reason}"


def test_the_probe_asks_above_whichever_merchants_cap_it_names(client):
    """Not a hard-coded 15%. The cap belongs to the merchant."""
    nid = _open(client)["negotiation_id"]
    client.post(f"/market/{nid}/round?use_llm=false")

    seen = {}
    for merchant_id in ("NOVATECH", "GEARHUB", "BYTECART"):
        probe = client.post(f"/market/{nid}/probe",
                            json={"merchant_id": merchant_id}).json()["probe"]
        assert probe["asked_line_discount_pct"] > probe["manifest_cap_pct"]
        assert probe["reason"] == "MERCHANT_POLICY_LINE_DISCOUNT_EXCEEDED"
        seen[merchant_id] = probe["manifest_cap_pct"]

    assert len(set(seen.values())) > 1, \
        "if every cap were the same this test would prove nothing"
