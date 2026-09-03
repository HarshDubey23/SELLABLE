"""Test multi-provider live e-commerce APIs and strict whitelisted storefront search."""
import urllib.request
import urllib.parse
import json
import xml.etree.ElementTree as ET
import re
import html

RETAIL_WHITELIST = {
    "amazon.in", "flipkart.com", "croma.com", "decathlon.in",
    "myntra.com", "tatacliq.com", "reliancedigital.in", "nykaa.com",
    "nykaafashion.com", "ajio.com", "dummyjson.com", "boat-lifestyle.com",
    "apple.com", "samsung.com", "lenovo.com", "dell.com", "fakestoreapi.com",
    "escuelajs.co", "meesho.com", "jiomart.com", "smartprix.com",
}

def query_platzi_api(q):
    try:
        url = f"https://api.escuelajs.co/api/v1/products/?title={urllib.parse.quote(q)}"
        req = urllib.request.Request(url, headers={"User-Agent": "SELLABLE/1.0"})
        with urllib.request.urlopen(req, timeout=5) as r:
            data = json.loads(r.read())
        print(f"Platzi API for {q!r}: {len(data)} items")
        for it in data[:3]:
            print(f"  - {it.get('title')} | Price: ${it.get('price')} (INR {it.get('price') * 85})")
            print(f"    Desc: {it.get('description')[:80]}")
    except Exception as e:
        print(f"Platzi err: {e}")

def query_dummyjson(q):
    try:
        url = f"https://dummyjson.com/products/search?q={urllib.parse.quote(q)}"
        req = urllib.request.Request(url, headers={"User-Agent": "SELLABLE/1.0"})
        with urllib.request.urlopen(req, timeout=5) as r:
            data = json.loads(r.read())
        prods = data.get("products", [])
        print(f"DummyJSON for {q!r}: {len(prods)} items")
        for p in prods[:3]:
            print(f"  - {p.get('title')} ({p.get('brand')}) | Price: ${p.get('price')} (INR {p.get('price') * 85}) | Rating: {p.get('rating')}")
            print(f"    Stock: {p.get('stock')} | Desc: {p.get('description')[:80]}")
    except Exception as e:
        print(f"DummyJSON err: {e}")

def query_strict_bing_rss(q):
    try:
        encoded_q = urllib.parse.quote(f"{q} site:amazon.in OR site:flipkart.com OR site:croma.com OR site:decathlon.in OR site:myntra.com OR site:tatacliq.com OR site:reliancedigital.in buy online price")
        url = f"https://www.bing.com/search?q={encoded_q}&format=rss"
        req = urllib.request.Request(url, headers={
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 Chrome/124.0",
            "Accept": "application/rss+xml"
        })
        with urllib.request.urlopen(req, timeout=5) as r:
            xml_data = r.read()
        root = ET.fromstring(xml_data)
        items = root.findall(".//item")
        valid = []
        for it in items:
            link = it.find("link").text if it.find("link") is not None else ""
            domain = urllib.parse.urlparse(link).netloc.replace("www.", "").lower()
            if any(w in domain for w in RETAIL_WHITELIST):
                title = it.find("title").text if it.find("title") is not None else ""
                desc = it.find("description").text if it.find("description") is not None else ""
                valid.append((title, link, domain, desc))
        print(f"Strict Bing RSS for {q!r}: {len(valid)} verified retail items")
        for t, l, d, desc in valid[:3]:
            print(f"  - {t}")
            print(f"    Storefront: {d} | URL: {l[:60]}")
            print(f"    Evidence: {desc[:90]}...")
    except Exception as e:
        print(f"Strict Bing RSS err: {e}")

if __name__ == "__main__":
    queries = [
        "65w fast charger",
        "wireless bluetooth headphones",
        "cricket bat",
        "laptop",
        "perfume",
    ]
    for q in queries:
        print("\n" + "="*60)
        print(f"QUERY: {q}")
        query_dummyjson(q)
        query_platzi_api(q)
        query_strict_bing_rss(q)
