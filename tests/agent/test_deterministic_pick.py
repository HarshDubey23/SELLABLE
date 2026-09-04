"""The no-LLM fallback must be deterministic and still budget-aware.

A judge cloning this repository has no model key. The buyer agent then
falls back to a deterministic picker, and the demo has to remain
reproducible: the same mission must always produce the same proposal, or
"deterministic fallback" is just a different kind of randomness.

Note what this test does NOT need to check: that the fallback picks a
*good* product. It has no money authority, so a bad pick costs nothing.
"""
import pytest

from apps.api.products import CATALOG, search


def test_catalog_search_is_deterministic():
    runs = [ [r["sku"] for r in search("cricket bat", "cricket", 300000)]
             for _ in range(25) ]
    assert len({tuple(r) for r in runs}) == 1, \
        "the same query must always return the same ordering"


def test_catalog_search_respects_the_price_ceiling():
    results = search("", "cricket", 100000)
    assert results, "expected at least one cricket item under Rs 1,000"
    assert all(r["price_paise"] <= 100000 for r in results)


def test_catalog_search_respects_the_category():
    for item in search("", "cricket", 10_000_000):
        assert item["category"] == "cricket"


def test_catalog_prices_are_integer_paise():
    """G4: money is int paise. A float here becomes a rounding bug later."""
    for sku, item in CATALOG.items():
        assert isinstance(item["price_paise"], int), \
            f"{sku} has a non-integer price: {item['price_paise']!r}"
        assert not isinstance(item["price_paise"], bool)
        assert item["price_paise"] > 0


@pytest.mark.parametrize("query", ["", "   ", "!!!", "a" * 500])
def test_catalog_search_never_raises_on_hostile_input(query):
    """Search input arrives from an untrusted agent."""
    assert isinstance(search(query, None, None), list)
