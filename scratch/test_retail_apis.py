"""Test real live e-commerce search APIs and direct retailer endpoints."""
import urllib.request
import urllib.parse
import json
import re

def test_amazon_suggestions(q):
    try:
        url = f"https://completion.amazon.in/api/2017/suggestions?prefix={urllib.parse.quote(q)}&mid=A21TJRUUN4KGV&alias=aps"
        req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
        with urllib.request.urlopen(req, timeout=5) as r:
            data = json.loads(r.read())
        print(f"Amazon Suggestions for {q!r}:")
        for s in data.get("suggestions", [])[:5]:
            print(f"  - {s.get('value')}")
    except Exception as e:
        print(f"Amazon Suggestions err: {e}")

def test_open_products(q):
    try:
        url = f"https://world.openfoodfacts.org/cgi/search.pl?search_terms={urllib.parse.quote(q)}&search_simple=1&action=process&json=1&page_size=5"
        req = urllib.request.Request(url, headers={"User-Agent": "SELLABLE/1.0"})
        with urllib.request.urlopen(req, timeout=5) as r:
            data = json.loads(r.read())
        prods = data.get("products", [])
        print(f"Open Products DB for {q!r}: {len(prods)} products")
        for p in prods[:3]:
            print(f"  - {p.get('product_name')} | Brand: {p.get('brands')} | Stores: {p.get('stores')}")
    except Exception as e:
        print(f"Open Products DB err: {e}")

def test_ddg_shopping(q):
    """Test DuckDuckGo with strict site: filter on real e-commerce sites only."""
    from duckduckgo_search import DDGS
    strict_q = f"{q} site:amazon.in OR site:flipkart.com OR site:croma.com OR site:decathlon.in"
    try:
        with DDGS() as ddgs:
            results = list(ddgs.text(strict_q, max_results=5))
        print(f"DDG Strict Ecom for {q!r}: {len(results)} results")
        for r in results:
            print(f"  - Title: {r.get('title')}")
            print(f"    URL: {r.get('href')}")
            print(f"    Body: {r.get('body')[:100]}...")
    except Exception as e:
        print(f"DDG Strict Ecom err: {e}")

if __name__ == "__main__":
    queries = ["65w fast charger", "bluetooth headphones", "cricket bat", "mechanical keyboard"]
    for q in queries:
        print("\n" + "="*50)
        test_amazon_suggestions(q)
        test_ddg_shopping(q)
