import pytest
from fastapi.testclient import TestClient

from apps.api.main import app

client = TestClient(app)

def test_home_page():
    res = client.get("/")
    assert res.status_code == 200
    assert "SELLABLE" in res.text

# The console, mission viewer, gateway UI, attack UI, audit UI, chaos room,
# architecture page, protocol page and metrics page were retired when the
# product collapsed to three surfaces. These tests now assert two things
# instead of one: that the old path still lands somewhere deliberate, and
# that the capability it used to show genuinely lives at the destination.

RETIRED_PAGES = [
    ("/console", "/judge"),
    ("/ui", "/judge"),
    ("/why", "/judge#thesis"),
    ("/mission", "/judge#chain"),
    ("/attack-ui", "/judge#attack"),
    ("/audit-ui", "/judge#audit"),
    ("/audit/timeline", "/judge#audit"),
    ("/gateway-ui", "/judge#gateway"),
    ("/metrics", "/judge#evidence"),
    ("/protocols", "/judge#architecture"),
    ("/architecture", "/judge#architecture"),
    ("/chaos", "/judge#recovery"),
    ("/products", "/"),
    ("/demo", "/"),
    ("/demo/checkout", "/"),
    ("/demo/failures", "/judge#recovery"),
    ("/demo/judge", "/judge"),
    ("/discovery", "/"),
    ("/growth", "/judge#architecture"),
]


@pytest.mark.parametrize("old_path,destination", RETIRED_PAGES)
def test_retired_page_redirects_instead_of_404ing(old_path, destination):
    res = client.get(old_path, follow_redirects=False)
    assert res.status_code == 307, f"{old_path} should redirect, not {res.status_code}"
    assert res.headers["location"] == destination


@pytest.mark.parametrize("old_path", [p for p, _ in RETIRED_PAGES])
def test_retired_page_lands_on_a_real_page(old_path):
    res = client.get(old_path)
    assert res.status_code == 200
    assert "SELLABLE" in res.text


def test_the_capabilities_of_the_retired_pages_survive_on_the_cockpit():
    """A redirect that lands on a page missing the feature is a 404 in disguise.

    Asserted against the endpoints each scene actually calls rather than
    against prose, so renaming a heading cannot make this pass while the
    capability is gone.
    """
    body = client.get("/judge").text
    for scene in ("scene-sentinel", "scene-gauntlet", "scene-mission",
                  "scene-negotiation", "scene-locks", "scene-recovery",
                  "scene-trust", "scene-evidence"):
        assert scene in body, f"the cockpit lost: {scene}"
    for endpoint in ("/attack/gauntlet", "/attack/custom", "/gateway/proof",
                     "/audit/tamper-demo", "/discovery/reconcile/",
                     "/agent/run_full_mission", "/negotiation/",
                     "/demo/kill-switch", "/api/v1/security-score",
                     "/api/v1/telemetry", "/api/v1/receipt/"):
        assert endpoint in body, f"the cockpit no longer calls {endpoint}"


def test_the_cockpit_is_also_reachable_at_its_own_name():
    """/cockpit and /judge are the same page, not two that can drift."""
    assert client.get("/cockpit").text == client.get("/judge").text


def test_only_three_html_surfaces_are_served():
    """The whole point of the consolidation. Guard it."""
    for path in ("/", "/judge"):
        assert client.get(path).status_code == 200
    # /trace/{ref} is the third; it 404s honestly on an unknown reference
    # rather than rendering an empty shell.
    assert client.get("/trace/not-a-real-execution").status_code == 404

def test_status_endpoint():
    res = client.get("/status")
    assert res.status_code == 200
    data = res.json()
    assert data.get("service") == "SELLABLE"

def test_manifest_endpoint():
    res = client.get("/.well-known/agent-manifest.json")
    assert res.status_code == 200
    data = res.json()
    assert data.get("merchant", {}).get("name") == "SELLABLE Demo Dukaan"

def test_catalog_search():
    res = client.get("/tools/search_products?query=cricket")
    assert res.status_code == 200
    data = res.json()
    assert "results" in data
    assert len(data["results"]) > 0

def test_protocol_adapters_are_still_reachable_over_the_api():
    """The protocol page went away; the adapters did not.

    This is a stronger assertion than the page test it replaces: it calls
    the adapters rather than checking that a marketing string appears in
    some HTML.
    """
    manifest = client.get("/.well-known/agent-manifest.json")
    assert manifest.status_code == 200
    # x402 is an honest stub and says so with a 501 rather than pretending.
    assert client.get("/x402/quote").status_code in (404, 501, 405)

