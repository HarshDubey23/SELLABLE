"""Product discovery: real network calls, honestly labelled evidence.

WHAT THIS LAYER IS
------------------
Market evidence gathering. It queries live sources at runtime and returns
what they actually said. It is *not* a purchasing channel: SELLABLE can
only sell what is in the merchant catalog, so external listings exist to
justify and pressure-test the merchant's price, never to become a
payable amount. Nothing here can authorize money.

EVIDENCE HONESTY RULES
----------------------
Every listing carries an `evidence_class` that says how much the field
set can be trusted:

  OBSERVED       price appeared verbatim, in INR, in the source text
  FX_CONVERTED   price came from a non-INR source and was converted with
                 a static reference rate — an estimate, not a quote
  MOCK_SOURCE    the provider serves synthetic catalog data (DummyJSON).
                 Useful for exercising the pipeline offline; it is NOT a
                 retail listing and is never counted as market evidence
  UNVERIFIED     the source matched the query but published no price

Three rules follow from this and are enforced below:

  1. `price_source_verified` is true ONLY for OBSERVED. An FX-converted
     figure is never described as a verified INR merchant price.
  2. The merchant's own catalog entry is NEVER injected into `listings`.
     It is returned separately as `merchant_offer`. A storefront quoting
     itself as a discovered market listing is circular evidence.
  3. Search status is derived from the live RETAIL providers alone. If
     every provider failed, the status is SEARCH_UNAVAILABLE — even when
     the merchant catalog has a perfectly good match to sell. If only the
     synthetic mock APIs answered, it is MOCK_SOURCES_ONLY, never
     LIVE_SEARCH_SUCCESS.

Rule 3 is the one that matters most. The previous implementation
appended the merchant's own SKU to the results list, so a run in which
every network provider timed out still reported LIVE_SEARCH_SUCCESS.
A search failure must look like a search failure.

TAINT
-----
Everything returned from an external source is `is_untrusted: True` and
carries zero money authority. It reaches the money path only as a SKU
reference that the deterministic gateway re-prices from the server-side
catalog.
"""
from __future__ import annotations

import concurrent.futures
import datetime as _dt
import html as _html
import json
import re
import urllib.parse
import urllib.request
import xml.etree.ElementTree as ET
from typing import Any

from pydantic import BaseModel, Field

from ..growth.intelligence import sanitize_web_content
from ..products import CATALOG

# A static reference rate, not a live FX quote. Any price derived from it
# is an estimate and is labelled FX_CONVERTED, never "verified".
USD_INR_REFERENCE_RATE = 85.0
USD_INR_RATE_NOTE = "static reference rate; not a live FX quote"

EVIDENCE_OBSERVED = "OBSERVED"
EVIDENCE_FX_CONVERTED = "FX_CONVERTED"
EVIDENCE_MOCK_SOURCE = "MOCK_SOURCE"
EVIDENCE_UNVERIFIED = "UNVERIFIED"

PROVIDER_WEB_SEARCH = "web_search"
PROVIDER_MOCK_API = "mock_api"



class WebProductListing(BaseModel):
    """One piece of external market evidence, with its provenance attached."""

    product_name: str

    # What the source actually published, before any transformation.
    source_price: float | None = None
    source_currency: str | None = None
    price_present: bool = False

    # The normalised INR figure we compare with. May be an estimate.
    price_paise: int | None = None
    price_inr: float | None = None

    # True ONLY when an INR price was observed verbatim in the source.
    price_source_verified: bool = False
    fx_converted: bool = False
    fx_rate_used: float | None = None

    evidence_class: str = EVIDENCE_UNVERIFIED

    seller: str
    seller_domain: str
    url: str
    rating: float | None = None
    rating_verified: bool = False
    availability: str = "unverified"
    availability_verified: bool = False
    scraped_at: str
    raw_evidence: str
    search_provider: str = "Live Web Discovery"
    provider_kind: str = PROVIDER_WEB_SEARCH
    is_untrusted: bool = True  # External web taint invariant

    @property
    def is_market_evidence(self) -> bool:
        """Only real retail sources count when comparing against the market."""
        return (self.provider_kind == PROVIDER_WEB_SEARCH
                and self.price_paise is not None)


class MerchantOffer(BaseModel):
    """The merchant's own catalog match — returned separately, never as a
    'discovered' web listing. This is the only thing SELLABLE can sell."""

    sku: str
    name: str
    category: str
    price_paise: int
    price_inr: float
    rating: float | None = None
    in_stock: bool = True
    url: str
    is_untrusted: bool = False  # server-side catalog is authoritative


class ComparisonSummary(BaseModel):
    live_providers_queried: int
    live_providers_responded: int
    external_listings_count: int
    market_evidence_count: int          # real retail listings with a price
    mock_source_count: int              # synthetic records, excluded from comparison
    fx_converted_count: int
    lowest_observed_market_price_inr: float | None = None
    lowest_observed_market_seller: str | None = None
    lowest_observed_market_url: str | None = None
    merchant_price_inr: float | None = None
    delta_vs_lowest_observed_inr: float | None = None
    comparison_basis: str


class RecommendationDecision(BaseModel):
    decision_status: str  # "RECOMMENDED_VERIFIED" | "DATA_UNVERIFIED"
    winner_name: str
    winner_price_inr: float | None = None
    winner_price_paise: int | None = None
    winner_seller: str
    winner_url: str
    recommendation_reason: str
    raw_evidence_source: str
    matched_merchant_sku: str | None = None
    matched_category: str | None = None
    savings_vs_market_inr: float = 0.0


class PolicyProbe(BaseModel):
    """A real catalog SKU that would violate the signed mandate.

    Offered so the gateway can be demonstrated refusing something, using
    genuine catalog data rather than a staged rejection. Proposing this
    is exactly what a prompt-injected agent would do: pick the expensive
    thing and justify it convincingly.
    """

    sku: str
    name: str
    price_paise: int
    price_inr: float
    exceeds_budget_by_paise: int
    why: str


class DiscoveryPipelineResult(BaseModel):
    query: str
    budget_paise: int
    # Derived from the LIVE providers alone. A merchant catalog match can
    # never turn a failed search into a successful one.
    # LIVE_SEARCH_SUCCESS | MOCK_SOURCES_ONLY | ZERO_RESULTS | SEARCH_UNAVAILABLE
    search_engine_status: str
    providers_queried: list[str] = Field(default_factory=list)
    providers_hit: list[str] = Field(default_factory=list)
    provider_errors: list[str] = Field(default_factory=list)
    error_message: str | None = None
    listings: list[WebProductListing]          # EXTERNAL evidence only
    merchant_offer: MerchantOffer | None = None
    policy_probe: PolicyProbe | None = None
    comparison: ComparisonSummary | None = None
    recommendation: RecommendationDecision | None = None
    gateway_verdict: dict[str, Any]
    executed_at: str
    evidence_legend: dict[str, str] = Field(default_factory=lambda: {
        EVIDENCE_OBSERVED: "price appeared verbatim in INR in the source",
        EVIDENCE_FX_CONVERTED: (
            "price converted from another currency using a static reference "
            "rate; an estimate, not a quote"),
        EVIDENCE_MOCK_SOURCE: (
            "synthetic catalog data from a mock API; not a retail listing "
            "and excluded from market comparison"),
        EVIDENCE_UNVERIFIED: "source matched the query but published no price",
    })


# Non-product domains to strictly filter out from retail search
# STRICT RETAIL WHITELIST — domain -> the seller name we will display.
#
# A whitelist, not a blocklist. Blocklists lose: the previous version
# enumerated ~50 non-retail domains to exclude and still let casino pages
# and SEO keyword-stuffing farms through, because you cannot enumerate the
# open web. Anything not named here is simply not market evidence.
#
# Ported from HarshDubey23's commit ed163a7, which is the right call.
VERIFIED_RETAIL_DOMAINS: dict[str, str] = {
    "amazon.in": "Amazon India",
    "amazon.com": "Amazon",
    "flipkart.com": "Flipkart",
    "croma.com": "Croma",
    "decathlon.in": "Decathlon India",
    "decathlon.com": "Decathlon",
    "myntra.com": "Myntra",
    "tatacliq.com": "Tata CLiQ",
    "reliancedigital.in": "Reliance Digital",
    "nykaa.com": "Nykaa",
    "nykaafashion.com": "Nykaa Fashion",
    "ajio.com": "AJIO",
    "boat-lifestyle.com": "boAt Lifestyle",
    "apple.com": "Apple Store",
    "samsung.com": "Samsung Store",
    "lenovo.com": "Lenovo Store",
    "dell.com": "Dell Store",
    "meesho.com": "Meesho",
    "jiomart.com": "JioMart",
}

# Words that describe how to shop rather than what to buy. Stripping them
# leaves the product nouns, which is what a listing actually has to match.
SEARCH_MODIFIERS = {
    "best", "buy", "under", "cheap", "cheapest", "price", "inr", "rs", "online",
    "india", "top", "good", "for", "with", "the", "and", "fast", "new", "latest",
    "official", "original", "genuine", "set", "pack", "mini", "pro", "max",
    "reviews", "rating", "quality",
}


def _extract_tokens(query: str) -> tuple[list[str], list[str]]:
    """Split a query into all tokens and the product nouns among them."""
    tokens = [t.lower() for t in re.split(r"[^\w]+", query)
              if len(t) > 2 and not t.isdigit()]
    nouns = [t for t in tokens if t not in SEARCH_MODIFIERS]
    return tokens, (nouns or tokens)


def _whole_word(term: str, text: str) -> bool:
    return re.search(rf"\b{re.escape(term)}\b", text, re.I) is not None


def _matches_query_intent(text: str, tokens: list[str],
                          primary_nouns: list[str]) -> bool:
    """Does this listing actually match what was asked for?

    Two rules, in order of how much they matter:

    1. **Whole words only.** Substring matching makes "bat" match
       "batteries". Commit ed163a7 introduced this fix and it is right.

    2. **The head noun must match.** ed163a7 accepted a listing if *any*
       primary noun matched, which still let a search for "cricket shoes"
       return a cricket bat — "cricket" matched and nothing checked the
       thing being bought. In an English noun phrase the last noun is the
       head: "cricket shoes" is a kind of shoe, not a kind of cricket. So
       the head noun is required, and the qualifiers are a bonus.

    With a single noun the two rules collapse into the same check.
    """
    if primary_nouns:
        head = primary_nouns[-1]
        if not _whole_word(head, text):
            return False
        return True
    return any(_whole_word(t, text) for t in tokens)


def _extract_price_from_text(text: str) -> dict[str, Any]:
    """Pull a price out of source text and record exactly where it came from.

    An INR figure found verbatim is OBSERVED. A USD figure is converted
    with a static reference rate and marked FX_CONVERTED — it is an
    estimate, and `price_source_verified` stays False for it. No price
    means UNVERIFIED, never a guess.
    """
    none_result = {
        "source_price": None, "source_currency": None, "price_present": False,
        "price_paise": None, "price_inr": None,
        "price_source_verified": False, "fx_converted": False,
        "fx_rate_used": None, "evidence_class": EVIDENCE_UNVERIFIED,
    }

    m_inr = re.search(r"(?:₹|rs\.?|inr)\s*([0-9,]+(?:\.[0-9]{2})?)", text,
                      re.IGNORECASE)
    if m_inr:
        try:
            val_inr = float(m_inr.group(1).replace(",", "").strip())
            if 50.0 <= val_inr <= 500000.0:
                return {
                    "source_price": round(val_inr, 2), "source_currency": "INR",
                    "price_present": True,
                    "price_paise": int(val_inr * 100),
                    "price_inr": round(val_inr, 2),
                    "price_source_verified": True,
                    "fx_converted": False, "fx_rate_used": None,
                    "evidence_class": EVIDENCE_OBSERVED,
                }
        except ValueError:
            pass

    m_usd = re.search(r"\$\s*([0-9,]+(?:\.[0-9]{2})?)", text)
    if m_usd:
        try:
            val_usd = float(m_usd.group(1).replace(",", "").strip())
            val_inr = val_usd * USD_INR_REFERENCE_RATE
            if 50.0 <= val_inr <= 500000.0:
                return {
                    "source_price": round(val_usd, 2), "source_currency": "USD",
                    "price_present": True,
                    "price_paise": int(val_inr * 100),
                    "price_inr": round(val_inr, 2),
                    # An estimate derived from a static rate is NOT verified.
                    "price_source_verified": False,
                    "fx_converted": True,
                    "fx_rate_used": USD_INR_REFERENCE_RATE,
                    "evidence_class": EVIDENCE_FX_CONVERTED,
                }
        except ValueError:
            pass

    return none_result


def _extract_rating_from_text(text: str) -> tuple[float | None, bool]:
    """Extract rating score if explicitly present in text."""
    m = re.search(r"\b([1-5]\.[0-9])\b\s*(?:out of 5|stars|\*|/5|★)?", text)
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
    if "in stock" in low or "available" in low or "in-stock" in low:
        return "in_stock", True
    if "out of stock" in low or "sold out" in low:
        return "out_of_stock", True
    return "unverified", False


def _query_dummyjson(clean_q: str, tokens: list[str], primary_nouns: list[str],
                     now_iso: str) -> tuple[list[WebProductListing], str | None, str | None]:
    """Provider: DummyJSON.

    DummyJSON is a public *mock* product API. Its catalog is synthetic and
    its prices are USD test data. It is included so the pipeline can be
    exercised end-to-end without depending on a search engine being
    reachable — not because it is a retail source.

    Everything it returns is therefore tagged MOCK_SOURCE, has
    `price_source_verified=False` and `rating_verified=False`, and is
    excluded from market comparisons by `is_market_evidence`. Calling this
    data a real listing would be fabricating product listings.
    """
    try:
        # Search per product noun rather than on the whole phrase, and stop
        # at the first term that returns anything (from commit ed163a7).
        listings: list[WebProductListing] = []
        for term in (primary_nouns[:3] or tokens[:3]):
            p_url = ("https://dummyjson.com/products/search?q="
                     + urllib.parse.quote(term) + "&limit=6")
            req_p = urllib.request.Request(p_url, headers={
                "User-Agent": "Mozilla/5.0 (compatible; SELLABLE-DiscoveryAgent/1.0)",
                "Accept": "application/json"
            })
            with urllib.request.urlopen(req_p, timeout=4) as r:
                data = json.loads(r.read())

            prods = data.get("products", [])
            for p in prods:
                if not _matches_query_intent(
                        f"{p.get('title','')} {p.get('description','')} "
                        f"{p.get('brand','')} {p.get('category','')}",
                        tokens, primary_nouns):
                    continue
                usd_price = float(p.get("price", 0))
                inr_estimate = round(usd_price * USD_INR_REFERENCE_RATE, 2)

                raw_ev = (f"{p.get('description')} Brand: {p.get('brand')}. "
                          f"Stock: {p.get('stock')} units. "
                          f"Category: {p.get('category')}.")

                listings.append(
                    WebProductListing(
                        product_name=p["title"],
                        source_price=usd_price,
                        source_currency="USD",
                        price_present=usd_price > 0,
                        price_paise=int(inr_estimate * 100),
                        price_inr=inr_estimate,
                        price_source_verified=False,
                        fx_converted=True,
                        fx_rate_used=USD_INR_REFERENCE_RATE,
                        evidence_class=EVIDENCE_MOCK_SOURCE,
                        seller="DummyJSON (synthetic catalog, not a retailer)",
                        seller_domain="dummyjson.com",
                        url=f"https://dummyjson.com/products/{p['id']}",
                        rating=(float(p["rating"])
                                if p.get("rating") is not None else None),
                        rating_verified=False,
                        availability=("in_stock" if p.get("stock", 0) > 0
                                      else "out_of_stock"),
                        availability_verified=False,
                        scraped_at=now_iso,
                        raw_evidence=raw_ev[:280],
                        search_provider="DummyJSON mock product API",
                        provider_kind=PROVIDER_MOCK_API,
                        is_untrusted=True,
                    )
                )
            if listings:
                break

        hit_msg = (f"DummyJSON mock API ({len(listings)} synthetic records)"
                   if listings else None)
        return listings, hit_msg, None
    except Exception as e:
        return [], None, f"DummyJSON mock API: {type(e).__name__}: {str(e)[:80]}"


def _query_bing_rss(clean_q: str, tokens: list[str], primary_nouns: list[str],
                    now_iso: str) -> tuple[list[WebProductListing], str | None, str | None]:
    """Provider: Bing RSS, restricted to whitelisted retail storefronts.

    Two filters, both from commit ed163a7 and both worth keeping:

      1. The domain must be in VERIFIED_RETAIL_DOMAINS. Previously a
         result was accepted if it merely contained a "shopping cue" word
         like "buy" or "price", which is how casino pages and SEO
         keyword-stuffing farms got in.
      2. The title/description must match the query's primary nouns as
         whole words, so a search for cricket *shoes* stops returning a
         cricket *bat*.
    """
    try:
        site_filter = " OR ".join(f"site:{d}" for d in VERIFIED_RETAIL_DOMAINS)
        encoded_q = urllib.parse.quote(f"{clean_q} ({site_filter})")
        bing_url = f"https://www.bing.com/search?q={encoded_q}&format=rss"
        req_b = urllib.request.Request(bing_url, headers={
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                          "AppleWebKit/537.36 (KHTML, like Gecko) "
                          "Chrome/124.0.0.0 Safari/537.36",
            "Accept": "application/rss+xml, application/xml, text/xml",
        })
        with urllib.request.urlopen(req_b, timeout=4) as r:
            xml_data = r.read()

        if not xml_data.strip():
            # An empty body is a broken endpoint, not an empty market. The
            # two must never be reported the same way: one means "nobody
            # sells this", the other means "we could not look".
            return [], None, ("Live web search: the search endpoint returned "
                              "an empty response body")

        root = ET.fromstring(xml_data)
        feed_items = root.findall(".//item")
        if not feed_items:
            # Parsed cleanly and contained no results at all. Bing has been
            # observed serving a well-formed but resultless feed for every
            # query, which is indistinguishable from a genuine miss unless
            # we say so here.
            return [], None, ("Live web search: the feed parsed but carried "
                              "no result items at all, which usually means "
                              "the endpoint is no longer serving results")

        listings = []
        rejected_domain = 0
        rejected_intent = 0
        for it in feed_items:
            title = it.find("title").text if it.find("title") is not None else ""
            link = it.find("link").text if it.find("link") is not None else ""
            desc = it.find("description").text if it.find("description") is not None else ""

            clean_title = _html.unescape(re.sub(r"<[^>]+>", "", title)).strip()
            clean_desc = _html.unescape(re.sub(r"<[^>]+>", "", desc)).strip()
            domain = urllib.parse.urlparse(link).netloc.replace("www.", "").lower()

            # 1. whitelist only — anything not a known retailer is not evidence
            seller = next((name for d, name in VERIFIED_RETAIL_DOMAINS.items()
                           if domain == d or domain.endswith("." + d)), None)
            if seller is None:
                rejected_domain += 1
                continue

            # 2. the listing must actually be about what was asked for
            if not _matches_query_intent(f"{clean_title} {clean_desc}",
                                         tokens, primary_nouns):
                rejected_intent += 1
                continue

            price = _extract_price_from_text(f"{clean_title} {clean_desc}")
            r_val, r_ver = _extract_rating_from_text(f"{clean_title} {clean_desc}")
            avail, avail_ver = _extract_availability_from_text(
                f"{clean_title} {clean_desc}")

            listings.append(
                WebProductListing(
                    product_name=clean_title,
                    seller=seller,
                    seller_domain=domain,
                    url=link,
                    rating=r_val,
                    rating_verified=r_ver,
                    availability=avail,
                    availability_verified=avail_ver,
                    scraped_at=now_iso,
                    raw_evidence=clean_desc[:280] if clean_desc else clean_title,
                    search_provider="Live web search (Bing RSS)",
                    provider_kind=PROVIDER_WEB_SEARCH,
                    is_untrusted=True,
                    **price,
                )
            )
            if len(listings) >= 6:
                break

        if listings:
            hit_msg = (f"Live web search: {len(listings)} whitelisted "
                       f"storefront result(s) from {len(feed_items)} raw "
                       f"result(s); {rejected_domain} rejected as non-retail "
                       f"domains, {rejected_intent} as off-intent")
            return listings, hit_msg, None

        # Results came back and every one of them was filtered out. That is
        # the whitelist working, not a failure, and it is reported as such.
        return [], (f"Live web search: {len(feed_items)} raw result(s), none "
                    f"from a whitelisted retailer matching the query "
                    f"({rejected_domain} off-domain, {rejected_intent} "
                    f"off-intent)"), None
    except Exception as e:
        return [], None, f"Live web search: {type(e).__name__}: {str(e)[:80]}"


def _query_platzi(clean_q: str, tokens: list[str], primary_nouns: list[str],
                  now_iso: str) -> tuple[list[WebProductListing], str | None, str | None]:
    """Provider: Platzi FakeStore.

    Added in commit ed163a7 as an "Open Retail Storefront". It is not one —
    api.escuelajs.co is a teaching sandbox with invented products and USD
    test prices, in the same category as DummyJSON. So it is kept for
    offline coverage and tagged MOCK_SOURCE, with nothing marked verified
    and no contribution to market comparison.
    """
    try:
        listings: list[WebProductListing] = []
        for term in (primary_nouns[:2] or tokens[:2]):
            url = ("https://api.escuelajs.co/api/v1/products/?title="
                   + urllib.parse.quote(term))
            req = urllib.request.Request(url, headers={
                "User-Agent": "Mozilla/5.0 (compatible; SELLABLE-DiscoveryAgent/1.0)",
                "Accept": "application/json",
            })
            with urllib.request.urlopen(req, timeout=4) as r:
                data = json.loads(r.read())

            for item in data[:4]:
                title = item.get("title", "")
                desc = item.get("description", "")
                if not _matches_query_intent(f"{title} {desc}", tokens, primary_nouns):
                    continue

                usd = float(item.get("price", 0))
                inr_estimate = round(usd * USD_INR_REFERENCE_RATE, 2)
                category = (item.get("category") or {}).get("name", "unknown")

                listings.append(
                    WebProductListing(
                        product_name=title,
                        source_price=usd,
                        source_currency="USD",
                        price_present=usd > 0,
                        price_paise=int(inr_estimate * 100),
                        price_inr=inr_estimate,
                        price_source_verified=False,
                        fx_converted=True,
                        fx_rate_used=USD_INR_REFERENCE_RATE,
                        evidence_class=EVIDENCE_MOCK_SOURCE,
                        seller="Platzi FakeStore (teaching sandbox, not a retailer)",
                        seller_domain="escuelajs.co",
                        url=f"https://api.escuelajs.co/api/v1/products/{item.get('id')}",
                        rating=None,
                        rating_verified=False,
                        availability="unverified",
                        availability_verified=False,
                        scraped_at=now_iso,
                        raw_evidence=f"{desc} Category: {category}"[:280],
                        search_provider="Platzi FakeStore mock API",
                        provider_kind=PROVIDER_MOCK_API,
                        is_untrusted=True,
                    )
                )
            if listings:
                break

        hit_msg = (f"Platzi FakeStore mock API ({len(listings)} synthetic records)"
                   if listings else None)
        return listings, hit_msg, None
    except Exception as e:
        return [], None, f"Platzi mock API: {type(e).__name__}: {str(e)[:80]}"


def search_live_web_providers(query: str, max_results: int = 10) -> tuple[list[WebProductListing], list[str], list[str]]:
    """Execute concurrent runtime network requests to live search providers and product APIs.

    Returns: (listings, providers_hit, errors)
    """
    now_iso = _dt.datetime.now(_dt.timezone.utc).isoformat()
    clean_q = sanitize_web_content(query).strip()
    listings: list[WebProductListing] = []
    providers_hit: list[str] = []
    errors: list[str] = []

    tokens, primary_nouns = _extract_tokens(clean_q)

    # Run the providers concurrently. Each returns (listings, hit, error);
    # a provider that fails contributes an error string and nothing else,
    # which is what lets the caller distinguish "found nothing" from
    # "could not look".
    with concurrent.futures.ThreadPoolExecutor(max_workers=3) as executor:
        futures = [
            executor.submit(_query_bing_rss, clean_q, tokens, primary_nouns, now_iso),
            executor.submit(_query_dummyjson, clean_q, tokens, primary_nouns, now_iso),
            executor.submit(_query_platzi, clean_q, tokens, primary_nouns, now_iso),
        ]

        for f in concurrent.futures.as_completed(futures):
            res_items, hit_msg, err_msg = f.result()
            if res_items:
                listings.extend(res_items)
            if hit_msg:
                providers_hit.append(hit_msg)
            if err_msg:
                errors.append(err_msg)

    # Deduplicate listings by clean title
    unique_listings: list[WebProductListing] = []
    seen_titles: set[str] = set()
    for item in listings:
        t_key = re.sub(r"[^\w]+", "", item.product_name.lower())[:25]
        if t_key and t_key not in seen_titles:
            seen_titles.add(t_key)
            unique_listings.append(item)

    return unique_listings[:max_results], providers_hit, errors


def _match_merchant_catalog(query: str, budget_paise: int) -> tuple[str | None, dict | None]:
    """Token-overlap match against the server-side catalog."""
    q_tokens = [t for t in re.split(r"[^\w]+", query.lower()) if len(t) > 2]
    best_sku, best_item, best_score = None, None, 0
    for sku, item in CATALOG.items():
        text = (f"{item['name']} {item['category']} "
                f"{item.get('description', '')}").lower()
        score = sum(2 for token in q_tokens if token in text)
        if score > best_score:
            best_sku, best_item, best_score = sku, item, score
    if best_score < 2 or best_item is None:
        return None, None
    if best_item["price_paise"] > budget_paise:
        return None, None
    return best_sku, best_item


def _find_policy_probe(category: str | None,
                       budget_paise: int) -> PolicyProbe | None:
    """Cheapest catalog SKU that still breaks the budget. Real data only."""
    candidates = [
        (sku, item) for sku, item in CATALOG.items()
        if item["price_paise"] > budget_paise
        and (category is None or item["category"] == category)
    ]
    if not candidates:
        candidates = [(sku, item) for sku, item in CATALOG.items()
                      if item["price_paise"] > budget_paise]
    if not candidates:
        return None
    sku, item = min(candidates, key=lambda kv: kv[1]["price_paise"])
    over = item["price_paise"] - budget_paise
    return PolicyProbe(
        sku=sku,
        name=item["name"],
        price_paise=item["price_paise"],
        price_inr=item["price_paise"] / 100.0,
        exceeds_budget_by_paise=over,
        why=(f"{item['name']} costs Rs {item['price_paise'] / 100:,.2f}, which is "
             f"Rs {over / 100:,.2f} over the signed budget. An agent that has been "
             f"talked into proposing it will be refused by R1_BUDGET before any "
             f"approval binding exists."),
    )


def run_real_product_discovery(query: str,
                               budget_paise: int = 500000) -> DiscoveryPipelineResult:
    """Gather market evidence, then state plainly what was and wasn't found.

    The status reported here describes the LIVE PROVIDERS ONLY. If the
    merchant happens to stock a matching product, that is reported
    separately as `merchant_offer` — it never launders a failed search
    into a successful one.
    """
    now_iso = _dt.datetime.now(_dt.timezone.utc).isoformat()
    sanitized_query = sanitize_web_content(query).strip()
    providers_queried = [
        "Live web search (Bing RSS, whitelisted retail domains)",
        "DummyJSON mock product API",
        "Platzi FakeStore mock API",
    ]

    external, providers_hit, errors = search_live_web_providers(
        sanitized_query, max_results=10)

    # ---- status is a function of the RETAIL providers, nothing else ----
    # A run in which only the synthetic mock APIs answered is not a
    # successful retail search, and saying LIVE_SEARCH_SUCCESS would be the
    # same class of lie rule 3 was written to stop: it would let a demo
    # with no real market evidence read as a working discovery pipeline.
    retail = [x for x in external if x.provider_kind != PROVIDER_MOCK_API]
    if retail:
        status = "LIVE_SEARCH_SUCCESS"
        error_message = " | ".join(errors) if errors else None
    elif errors:
        # A retail provider failed. Whether the market is empty is now
        # unknown, and "unknown" outranks "we found some synthetic records"
        # — the mock APIs were never market evidence in the first place.
        status = "SEARCH_UNAVAILABLE"
        error_message = " | ".join(errors)
    elif external:
        status = "MOCK_SOURCES_ONLY"
        error_message = (
            "no whitelisted retail source returned a usable listing; only "
            "synthetic mock-API records were retrieved, and those are "
            "excluded from market comparison"
            + (" | " + " | ".join(errors) if errors else ""))
    elif errors and len(errors) >= len(providers_queried):
        status = "SEARCH_UNAVAILABLE"
        error_message = " | ".join(errors)
    elif errors:
        status = "SEARCH_UNAVAILABLE"
        error_message = " | ".join(errors)
    else:
        status = "ZERO_RESULTS"
        error_message = "providers responded but published no matching products"

    matched_sku, matched_item = _match_merchant_catalog(
        sanitized_query, budget_paise)

    merchant_offer = None
    if matched_sku and matched_item:
        merchant_offer = MerchantOffer(
            sku=matched_sku,
            name=matched_item["name"],
            category=matched_item["category"],
            price_paise=matched_item["price_paise"],
            price_inr=matched_item["price_paise"] / 100.0,
            rating=matched_item.get("rating"),
            in_stock=matched_item.get("stock", 0) > 0,
            url=f"/products#{matched_sku}",
        )

    # ---- comparison uses REAL retail evidence only ----
    market = [x for x in external if x.is_market_evidence]
    observed = [x for x in market if x.evidence_class == EVIDENCE_OBSERVED]
    cheapest = min(observed, key=lambda x: x.price_paise) if observed else None

    if cheapest is not None:
        basis = ("lowest INR price observed verbatim across the searched "
                 "retail sources")
    elif market:
        basis = ("no INR price was observed verbatim; remaining listings are "
                 "FX-converted estimates and are not comparable")
    else:
        basis = "no external market evidence was retrieved"

    comparison = ComparisonSummary(
        live_providers_queried=len(providers_queried),
        live_providers_responded=len(providers_hit),
        external_listings_count=len(external),
        market_evidence_count=len(market),
        mock_source_count=len([x for x in external
                               if x.provider_kind == PROVIDER_MOCK_API]),
        fx_converted_count=len([x for x in external if x.fx_converted]),
        lowest_observed_market_price_inr=cheapest.price_inr if cheapest else None,
        lowest_observed_market_seller=cheapest.seller if cheapest else None,
        lowest_observed_market_url=cheapest.url if cheapest else None,
        merchant_price_inr=merchant_offer.price_inr if merchant_offer else None,
        delta_vs_lowest_observed_inr=(
            round(cheapest.price_inr - merchant_offer.price_inr, 2)
            if cheapest and merchant_offer and cheapest.price_inr else None),
        comparison_basis=basis,
    )

    # ---- recommendation ----
    recommendation = None
    if merchant_offer is not None:
        if cheapest is not None and comparison.delta_vs_lowest_observed_inr is not None:
            delta = comparison.delta_vs_lowest_observed_inr
            if delta > 0:
                evidence_line = (
                    f"Rs {delta:,.2f} below the lowest verbatim INR price "
                    f"observed in this search ({cheapest.seller}, "
                    f"Rs {cheapest.price_inr:,.2f}).")
            else:
                evidence_line = (
                    f"Rs {abs(delta):,.2f} above the lowest verbatim INR price "
                    f"observed in this search ({cheapest.seller}, "
                    f"Rs {cheapest.price_inr:,.2f}).")
            decision_status = "RECOMMENDED_WITH_MARKET_EVIDENCE"
        else:
            evidence_line = ("No verbatim INR market price was observed in this "
                             "search, so no price comparison is claimed.")
            decision_status = "RECOMMENDED_WITHOUT_MARKET_EVIDENCE"

        recommendation = RecommendationDecision(
            decision_status=decision_status,
            winner_name=merchant_offer.name,
            winner_price_inr=merchant_offer.price_inr,
            winner_price_paise=merchant_offer.price_paise,
            winner_seller="SELLABLE merchant catalog",
            winner_url=merchant_offer.url,
            recommendation_reason=(
                f"SKU {merchant_offer.sku} at Rs {merchant_offer.price_inr:,.2f}, "
                f"within the signed budget mandate of "
                f"Rs {budget_paise / 100:,.2f}. {evidence_line}"),
            raw_evidence_source=(cheapest.raw_evidence if cheapest
                                 else "no external price evidence retrieved"),
            matched_merchant_sku=merchant_offer.sku,
            matched_category=merchant_offer.category,
            savings_vs_market_inr=max(
                comparison.delta_vs_lowest_observed_inr or 0.0, 0.0),
        )

    gateway_verdict = {
        "external_web_authority": "NONE — advisory evidence only",
        "money_path_isolated_from_web": True,
        "priced_from": "server-side merchant catalog, not from any listing",
        "budget_paise_limit": budget_paise,
        "proposed_amount_paise": (merchant_offer.price_paise
                                  if merchant_offer else None),
        "within_budget": (merchant_offer.price_paise <= budget_paise
                          if merchant_offer else None),
        "note": ("this is a pre-check only; the deterministic gateway R1-R12 "
                 "re-evaluates the proposal at /tools/submit_proposal and is "
                 "the only thing that can authorize an amount"),
    }

    probe = _find_policy_probe(
        merchant_offer.category if merchant_offer else None, budget_paise)

    return DiscoveryPipelineResult(
        query=query,
        budget_paise=budget_paise,
        search_engine_status=status,
        providers_queried=providers_queried,
        providers_hit=providers_hit,
        provider_errors=errors,
        error_message=error_message,
        listings=external,
        merchant_offer=merchant_offer,
        policy_probe=probe,
        comparison=comparison,
        recommendation=recommendation,
        gateway_verdict=gateway_verdict,
        executed_at=now_iso,
    )
