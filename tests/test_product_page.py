"""GET / must be the product, and it must tell the truth about the provider."""

import pytest
from fastapi.testclient import TestClient


@pytest.fixture
def client(monkeypatch):
    monkeypatch.setenv("RAZORPAY_KEY_ID", "")
    monkeypatch.setenv("RAZORPAY_KEY_SECRET", "")
    from apps.api.main import app
    return TestClient(app)


def test_root_serves_the_product_not_the_console(client):
    r = client.get("/")
    assert r.status_code == 200
    body = r.text
    assert 'id="q"' in body and 'class="sinput"' in body, \
        "/ must open on an intent input, not a dashboard"
    assert "cannot" in body and "touch your money" in body
    # The landing page must lead with the product, not with the evidence.
    assert body.index("Shop with an AI") < body.index("Reviewing this for Razorpay")


def test_console_redirects_into_the_cockpit(client):
    """The console was retired; its old path must still land somewhere."""
    r = client.get("/console", follow_redirects=False)
    assert r.status_code == 307
    assert r.headers["location"] == "/judge"
    assert client.get("/console").status_code == 200


def test_product_page_declares_no_metrics_it_cannot_back(client):
    """No hardcoded counts on the landing page.

    The numbers that belong to this project live in
    docs/generated/truth.json and are read at runtime; a landing page
    that hardcodes '142 tests passed' goes stale the moment someone
    writes a test.
    """
    import re

    body = client.get("/").text
    # Strip the stylesheet first: a CSS colour like #141420 is not a claim,
    # and matching it made this guard fire on the design tokens rather than
    # on anything a reader would ever see.
    prose = re.sub(r"<style>.*?</style>", "", body, flags=re.S)
    for stale in ("142 ", "20 exploits", "20/20", "0.1ms", "45.02",
                  "100% secure", "unhackable", "zero vulnerabilities"):
        assert stale not in prose, f"hardcoded claim {stale!r} on the landing page"

    # And nothing may present a bare metric-looking figure outside a fetch.
    # Every number a shopper sees is written by JS from a response body.
    for hardcoded in ("tests passed", "attacks blocked", "% uptime"):
        assert hardcoded not in prose.lower(), \
            f"the landing page states {hardcoded!r} without fetching it"


def test_page_reads_the_provider_from_diagnostics(client):
    body = client.get("/").text
    assert "/diagnostics" in body, "the provider label must come from runtime state"
    d = client.get("/diagnostics").json()
    assert d["payments"]["provider"] == "simulated"


def test_policy_probe_is_a_real_over_budget_catalog_sku(client):
    """The 'break it' button must propose genuine catalog data."""
    from apps.api.products import CATALOG

    r = client.post("/discovery/search",
                    json={"query": "cricket bat", "budget_paise": 200000})
    probe = r.json()["policy_probe"]
    assert probe is not None
    assert probe["sku"] in CATALOG
    assert probe["price_paise"] == CATALOG[probe["sku"]]["price_paise"]
    assert probe["price_paise"] > 200000
    assert probe["exceeds_budget_by_paise"] == probe["price_paise"] - 200000


def test_probing_with_the_over_budget_sku_is_actually_rejected(client):
    """The demonstration has to be a real refusal, not a staged one."""
    from apps.api import execution as ex

    probe = client.post("/discovery/search",
                        json={"query": "cricket bat", "budget_paise": 200000}
                        ).json()["policy_probe"]

    r = client.post("/discovery/checkout",
                    json={"sku": probe["sku"], "budget_paise": 200000})
    assert r.status_code == 422
    body = r.json()
    assert body["ok"] is False
    assert body["status"] == "POLICY_GATEWAY_REJECT"
    assert body["rule_id"] == "R1_BUDGET"
    assert len(body["rule_matrix"]) == 12
    assert body["execution_state"] is None
    assert body["money_boundary_calls_during_request"] == 0, \
        "a staged refusal would still have called the provider"
    assert ex.list_executions() == [], "a refused proposal must open no execution"


def test_no_ui_page_quotes_the_eval_simulation_as_a_headline_number(client):
    """eval/ is a seeded simulation. It must not appear as a KPI anywhere.

    The judge page used to render an 'Evaluation Snapshot (300 missions)'
    panel with figures like '48% acceptance' and 'Rs 74,861 naive LLM
    loss' straight from eval/report.json — numbers whose provenance did
    not survive review, sitting next to real ones.
    """
    for path in ("/", "/judge", "/console", "/metrics"):  # last two redirect into /judge
        body = client.get(path).text
        assert "Evaluation Snapshot" not in body, f"{path} quotes the simulation"
        assert "NAIVE LLM LOSS" not in body, f"{path} quotes the simulation"


def test_judge_page_reads_the_generated_evidence(client):
    body = client.get("/judge").text
    assert "docs/generated/truth.json" in body
    assert "seeded simulation" in body, \
        "the judge page must say what eval/ is when it mentions it at all"
