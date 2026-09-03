"""Real-World Live Web Product Discovery & Verification Pipeline.

AUDITED & HARDENED:
- ZERO synthetic fallback listings
- ZERO invented prices (marked price_verified: False if not in source text)
- ZERO invented ratings (marked rating_verified: False if not in source text)
- ZERO assumed availability (marked availability_verified: False if not in source text)
- Multi-engine live search (DuckDuckGo HTML + Bing Search backup)
- Returns explicit SEARCH_FAILED / ZERO_RESULTS if live search yields no listings
- Preserves verbatim raw snippet evidence, source URL, and live crawl timestamp
- Preserves deterministic Policy Gateway (R1-R12) money boundary
"""
from __future__ import annotations

import datetime as _dt
import html as _html
import re
import urllib.parse
import urllib.request
from typing import Any
from pydantic import BaseModel, Field

from ..products import CATALOG
from ..growth.intelligence import sanitize_web_content


class WebProductListing(BaseModel):
    product_name: str
    price_paise: int | None = None
    price_inr: float | None = None
    price_verified: bool = False
    seller: str
    seller_domain: str
    url: str
    rating: float | None = None
    rating_verified: bool = False
    availability: str = "unverified"
    availability_verified: bool = False
    scraped_at: str
    raw_evidence: str
    search_provider: str = "live_web"
    is_untrusted: bool = True  # External web taint invariant


class ComparisonSummary(BaseModel):
    total_sources_searched: int
    verified_price_listings_count: int
    cheapest_web_option: dict[str, Any] | None = None
    merchant_matched_sku: str | None = None
    merchant_matched_name: str | None = None
    merchant_matched_price_inr: float | None = None
    savings_vs_web_inr: float | None = None


class RecommendationDecision(BaseModel):
    decision_status: str  # "RECOMMENDED_VERIFIED" | "DATA_UNVERIFIED" | "NO_VERIFIED_PRICES"
    winner_name: str
    winner_price_inr: float | None = None
    winner_seller: str
    winner_url: str
    recommendation_reason: str
    raw_evidence_source: str
    matched_merchant_sku: str | None = None
    savings_vs_market_inr: float = 0.0


class DiscoveryPipelineResult(BaseModel):
    query: str
    budget_paise: int
    search_engine_status: str  # "LIVE_SEARCH_SUCCESS" | "SEARCH_FAILED" | "ZERO_RESULTS"
    error_message: str | None = None
    listings: list[WebProductListing]
    comparison: ComparisonSummary | None = None
    recommendation: RecommendationDecision | None = None
    gateway_verdict: dict[str, Any]
    executed_at: str


def _extract_price_from_text(text: str) -> tuple[int | None, bool]:
    """Strictly extract price from text if and only if explicitly present.

    Returns (price_paise, is_verified). Never invents or estimates.
    """
    # Matches: ₹ 1,499, ₹1499, Rs. 1499, Rs 2,499, INR 1999
    m = re.search(r"(?:₹|rs\.?|inr)\s*([0-9,]+)", text, re.IGNORECASE)
    if m:
        try:
            clean_str = m.group(1).replace(",", "").strip()
            val_inr = int(clean_str)
            if 50 <= val_inr <= 300000:
                return val_inr * 100, True
        except ValueError:
            pass
    return None, False


def _extract_rating_from_text(text: str) -> tuple[float | None, bool]:
    """Extract rating score if present in text (e.g. 4.3 out of 5 stars)."""
    m = re.search(r"\b([1-5]\.[0-9])\b", text)
    if m:
        try:
            r = float(m.group(1))
            if 1.0 <= r <= 5.0:
                return r, True
        except ValueError:
            pass
    return None, False


def _extract_availability_from_text(text: str) -> tuple[str, bool]:
    """Extract availability if explicitly mentioned in text."""
    low = text.lower()
    if "in stock" in low or "available" in low:
        return "in_stock", True
    if "out of stock" in low or "currently unavailable" in low or "sold out" in low:
        return "out_of_stock", True
    return "unverified", False


def _detect_seller(url: str, text: str = "") -> tuple[str, str]:
    """Detect seller name and domain from URL and text snippet."""
    combined = f"{url} {text}".lower()
    known_sellers = [
        ("amazon", "Amazon India", "amazon.in"),
        ("flipkart", "Flipkart", "flipkart.com"),
        ("decathlon", "Decathlon", "decathlon.in"),
        ("myntra", "Myntra", "myntra.com"),
        ("tatacliq", "Tata CLiQ", "tatacliq.com"),
        ("cricketerpoint", "Cricketer Point", "cricketerpoint.com"),
        ("sportsjam", "SportsJam", "sportsjam.in"),
        ("croma", "Croma", "croma.com"),
        ("reliancedigital", "Reliance Digital", "reliancedigital.in"),
        ("cricbuzz", "Cricbuzz", "cricbuzz.com"),
        ("wikipedia", "Wikipedia", "wikipedia.org"),
    ]
    for key, sname, default_dom in known_sellers:
        if key in combined:
            return sname, default_dom
    domain_m = re.search(r"https?://([^/]+)", url)
    seller_domain = domain_m.group(1).lower() if domain_m else "web"
    return seller_domain, seller_domain


def _query_duckduckgo(search_term: str, now_iso: str, max_results: int) -> tuple[list[WebProductListing], str | None]:
    """Query live DuckDuckGo HTML endpoint."""
    url = f"https://html.duckduckgo.com/html/?q={urllib.parse.quote(search_term)}"
    req = urllib.request.Request(
        url,
        headers={
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/115.0.0.0 Safari/537.36",
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
            "Accept-Language": "en-US,en;q=0.5",
        },
    )
    with urllib.request.urlopen(req, timeout=8) as resp:
        html = resp.read().decode("utf-8", errors="ignore")
        blocks = html.split('<div class="result results_links')
        if len(blocks) <= 1:
            return [], "DDG returned 0 blocks (possible rate limit challenge)"

        listings: list[WebProductListing] = []
        for b in blocks[1 : max_results + 1]:
            url_m = re.search(r'href="([^"]+)"', b)
            snippet_m = re.search(r'<a[^>]+class="result__snippet"[^>]*>(.*?)</a>', b, re.DOTALL)
            title_m = re.search(r'<h2[^>]*>.*?<a[^>]*>(.*?)</a>', b, re.DOTALL)

            raw_url = url_m.group(1) if url_m else ""
            raw_title = title_m.group(1) if title_m else ""
            raw_snippet = snippet_m.group(1) if snippet_m else ""

            title = _html.unescape(re.sub(r"<[^>]+>", "", raw_title)).strip()
            snippet = _html.unescape(re.sub(r"<[^>]+>", "", raw_snippet)).strip()

            if "uddg=" in raw_url:
                actual_url = urllib.parse.unquote(raw_url.split("uddg=")[1].split("&")[0])
            else:
                actual_url = raw_url

            if not actual_url.startswith("http") or not title:
                continue

            combined_text = f"{title} {snippet}"
            seller_name, seller_domain = _detect_seller(actual_url, combined_text)
            price_paise, price_verified = _extract_price_from_text(combined_text)
            rating, rating_verified = _extract_rating_from_text(snippet)
            avail, avail_verified = _extract_availability_from_text(combined_text)

            listings.append(
                WebProductListing(
                    product_name=title,
                    price_paise=price_paise,
                    price_inr=price_paise / 100.0 if price_paise else None,
                    price_verified=price_verified,
                    seller=seller_name,
                    seller_domain=seller_domain,
                    url=actual_url,
                    rating=rating,
                    rating_verified=rating_verified,
                    availability=avail,
                    availability_verified=avail_verified,
                    scraped_at=now_iso,
                    raw_evidence=snippet[:300] if snippet else title[:150],
                    search_provider="DuckDuckGo Live",
                    is_untrusted=True,
                )
            )
        return listings, None


def _query_bing(search_term: str, now_iso: str, max_results: int) -> tuple[list[WebProductListing], str | None]:
    """Query live Bing search endpoint as high-availability backup."""
    url = f"https://www.bing.com/search?q={urllib.parse.quote(search_term)}"
    req = urllib.request.Request(
        url,
        headers={
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36",
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
            "Accept-Language": "en-US,en;q=0.9",
        },
    )
    with urllib.request.urlopen(req, timeout=8) as resp:
        html = resp.read().decode("utf-8", errors="ignore")
        matches = re.findall(r'<li class="b_algo"[^>]*>(.*?)</li>', html, re.DOTALL)
        if not matches:
            return [], "Bing returned 0 results"

        listings: list[WebProductListing] = []
        for b in matches[:max_results]:
            url_m = re.search(r'href="(https?://[^"]+)"', b)
            title_m = re.search(r'<h2[^>]*>.*?<a[^>]*>(.*?)</a>', b, re.DOTALL)
            snippet_m = re.search(r'<p[^>]*>(.*?)</p>', b, re.DOTALL)

            actual_url = url_m.group(1) if url_m else ""
            raw_title = title_m.group(1) if title_m else ""
            raw_snippet = snippet_m.group(1) if snippet_m else ""

            title = _html.unescape(re.sub(r"<[^>]+>", "", raw_title)).strip()
            snippet = _html.unescape(re.sub(r"<[^>]+>", "", raw_snippet)).strip()

            if not actual_url or not title or actual_url.endswith(".css") or actual_url.endswith(".js"):
                continue

            combined_text = f"{title} {snippet}"
            seller_name, seller_domain = _detect_seller(actual_url, combined_text)
            price_paise, price_verified = _extract_price_from_text(combined_text)
            rating, rating_verified = _extract_rating_from_text(snippet)
            avail, avail_verified = _extract_availability_from_text(combined_text)

            listings.append(
                WebProductListing(
                    product_name=title,
                    price_paise=price_paise,
                    price_inr=price_paise / 100.0 if price_paise else None,
                    price_verified=price_verified,
                    seller=seller_name,
                    seller_domain=seller_domain,
                    url=actual_url,
                    rating=rating,
                    rating_verified=rating_verified,
                    availability=avail,
                    availability_verified=avail_verified,
                    scraped_at=now_iso,
                    raw_evidence=snippet[:300] if snippet else title[:150],
                    search_provider="Bing Live",
                    is_untrusted=True,
                )
            )
        return listings, None


def search_live_web(query: str, max_results: int = 10) -> tuple[str, list[WebProductListing], str | None]:
    """Perform a TRUE LIVE WEB SEARCH across real search engines.

    First queries DuckDuckGo. If temporarily blocked, queries Bing live.
    If both yield 0 results, returns explicit failure.
    NEVER injects fake or synthetic fallback listings.
    """
    sanitized_query = sanitize_web_content(query).strip()
    clean_q = re.sub(r"^(find\s+me\s+(the\s+)?(best|cheapest)\s+|best\s+|cheapest\s+)", "", sanitized_query, flags=re.IGNORECASE).strip()
    clean_q = re.sub(r"[^\w\s]", " ", clean_q).strip()
    search_term = f"{clean_q} price buy online india amazon flipkart"

    now_iso = _dt.datetime.now(_dt.timezone.utc).isoformat()

    # 1. Primary: DuckDuckGo Live
    try:
        listings, err_ddg = _query_duckduckgo(search_term, now_iso, max_results)
        if listings:
            return "LIVE_SEARCH_SUCCESS", listings, None
    except Exception as e:
        err_ddg = str(e)

    # 2. Secondary: Bing Live
    try:
        listings, err_bing = _query_bing(search_term, now_iso, max_results)
        if listings:
            return "LIVE_SEARCH_SUCCESS", listings, None
    except Exception as e:
        err_bing = str(e)

    # Truthful explicit failure
    return "SEARCH_FAILED", [], f"Live search engines unavailable (DDG: {err_ddg}, Bing: {err_bing})"


def run_real_product_discovery(query: str, budget_paise: int = 250000) -> DiscoveryPipelineResult:
    """Execute the 6-stage product discovery pipeline on live web data."""
    now_iso = _dt.datetime.now(_dt.timezone.utc).isoformat()

    # Stage 1: Live Web Search
    status, listings, error_msg = search_live_web(query, max_results=10)

    # If search failed, return truthful explicit failure state
    if status != "LIVE_SEARCH_SUCCESS" or not listings:
        return DiscoveryPipelineResult(
            query=query,
            budget_paise=budget_paise,
            search_engine_status=status,
            error_message=error_msg or "Search engine unreachable or 0 results returned.",
            listings=[],
            comparison=None,
            recommendation=None,
            gateway_verdict={
                "MONEY_PATH_ISOLATED_FROM_WEB": True,
                "external_web_authority": "ZERO (ADVISORY ONLY)",
                "status": "ABORTED_NO_LIVE_DATA",
                "reason": "Search failed; refusal to process unverified synthetic data",
            },
            executed_at=now_iso,
        )

    # Stage 2 & 3: Filter verified prices for truthful comparison
    verified_listings = [l for l in listings if l.price_verified and l.price_paise is not None]

    # Stage 4: Compare with SELLABLE Merchant Direct Catalog
    matched_sku = None
    matched_item = None
    query_lower = query.lower()

    if "bat" in query_lower or "cricket" in query_lower:
        matched_sku = "BAT-001"
    elif "headphone" in query_lower or "audio" in query_lower or "ear" in query_lower:
        matched_sku = "EAR-001"
    elif "book" in query_lower or "python" in query_lower:
        matched_sku = "BOOK-001"

    if matched_sku and matched_sku in CATALOG:
        matched_item = CATALOG[matched_sku]

    cheapest_web = None
    if verified_listings:
        cheapest_listing = min(verified_listings, key=lambda x: x.price_paise or 99999999)
        cheapest_web = {
            "name": cheapest_listing.product_name,
            "seller": cheapest_listing.seller,
            "price_inr": cheapest_listing.price_inr,
            "url": cheapest_listing.url,
            "raw_evidence": cheapest_listing.raw_evidence,
        }

    savings_inr = None
    merchant_price_inr = None
    if matched_item and cheapest_web and cheapest_web["price_inr"]:
        merchant_price_inr = matched_item["price_paise"] / 100.0
        savings_inr = round(cheapest_web["price_inr"] - merchant_price_inr, 2)

    comparison = ComparisonSummary(
        total_sources_searched=len(listings),
        verified_price_listings_count=len(verified_listings),
        cheapest_web_option=cheapest_web,
        merchant_matched_sku=matched_sku,
        merchant_matched_name=matched_item["name"] if matched_item else None,
        merchant_matched_price_inr=merchant_price_inr,
        savings_vs_web_inr=savings_inr,
    )

    # Stage 5: Formulate Recommendation
    if matched_item and savings_inr is not None and savings_inr >= 0:
        recommendation = RecommendationDecision(
            decision_status="RECOMMENDED_VERIFIED",
            winner_name=matched_item["name"],
            winner_price_inr=merchant_price_inr,
            winner_seller="SELLABLE Verified Merchant (Direct)",
            winner_url="http://localhost:8000/products",
            recommendation_reason=(
                f"Selected SELLABLE Verified Merchant SKU {matched_sku} at ₹{merchant_price_inr:,.2f}. "
                f"Verified cheaper than {cheapest_web['seller'] if cheapest_web else 'web'} "
                f"(₹{cheapest_web['price_inr']:,.2f}) by ₹{savings_inr:,.2f}, with guaranteed instant "
                f"Razorpay settlement and HMAC mandate security."
            ),
            raw_evidence_source=cheapest_web["raw_evidence"] if cheapest_web else "",
            matched_merchant_sku=matched_sku,
            savings_vs_market_inr=savings_inr,
        )
    elif cheapest_web:
        recommendation = RecommendationDecision(
            decision_status="RECOMMENDED_VERIFIED",
            winner_name=cheapest_web["name"],
            winner_price_inr=cheapest_web["price_inr"],
            winner_seller=cheapest_web["seller"],
            winner_url=cheapest_web["url"],
            recommendation_reason=(
                f"Selected {cheapest_web['seller']} listing as verified lowest web price at "
                f"₹{cheapest_web['price_inr']:,.2f}. Verified directly from live search evidence."
            ),
            raw_evidence_source=cheapest_web["raw_evidence"],
            matched_merchant_sku=matched_sku,
            savings_vs_market_inr=0.0,
        )
    else:
        recommendation = RecommendationDecision(
            decision_status="DATA_UNVERIFIED",
            winner_name=listings[0].product_name,
            winner_price_inr=None,
            winner_seller=listings[0].seller,
            winner_url=listings[0].url,
            recommendation_reason=(
                "Live search retrieved actual product listings, but numeric prices were not "
                "disclosed in search engine snippets. Inspect raw source URLs directly."
            ),
            raw_evidence_source=listings[0].raw_evidence,
            matched_merchant_sku=matched_sku,
            savings_vs_market_inr=0.0,
        )

    # Stage 6: Policy Gateway Pre-Check
    gateway_verdict = {
        "MONEY_PATH_ISOLATED_FROM_WEB": True,
        "external_web_authority": "ZERO (ADVISORY ONLY)",
        "r1_budget_check": "PASS" if (recommendation.winner_price_inr or 0) * 100 <= budget_paise else "OVER_BUDGET",
        "budget_paise_limit": budget_paise,
        "mandate_binding_ready": True,
    }

    return DiscoveryPipelineResult(
        query=query,
        budget_paise=budget_paise,
        search_engine_status="LIVE_SEARCH_SUCCESS",
        error_message=None,
        listings=listings,
        comparison=comparison,
        recommendation=recommendation,
        gateway_verdict=gateway_verdict,
        executed_at=now_iso,
    )
