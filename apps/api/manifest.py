"""Agent-native discovery: /.well-known/agent-manifest.json
and the schema.org JSON-LD catalog at /catalog.jsonld."""

import json

from fastapi import APIRouter, Response

from .products import CATALOG

router = APIRouter()

MANIFEST = {
    "merchant": {
        "name": "SELLABLE Demo Dukaan",
        "description": "Agent-readable, agent-transactable, agent-safe merchant on Razorpay test mode.",
        "version": "1.0.0",
        "protocol": "sellable-v1",
    },
    "supported_protocols": {
        "sellable-v1": "native (this manifest)",
        "schema.org": "Product/Offer JSON-LD via /catalog.jsonld",
        "npci_uap": "NPCI Universal Agent Protocol v1.0 live at /protocol/uap/transact with delegated UPI e-mandates",
        "acp_ap2_x402": "ACP + AP2 adapters live at /protocol/* (translate "
                        "to the canonical executor; the gateway decides); "
                        "x402 is an honest 501 stub",
    },
    "capabilities": ["search", "get_product", "quote", "propose",
                     "checkout", "payment_status", "market_intelligence", "aov_growth_bundling"],
    "tools": [
        {"name": "search_products", "method": "GET",
         "endpoint": "/tools/search_products",
         "params": {"query": "string?", "category": "string?", "max_price_paise": "int?"}},
        {"name": "get_product", "method": "GET",
         "endpoint": "/tools/get_product/{sku}",
         "params": {"sku": "string"}},
        {"name": "merchant_policy", "method": "GET",
         "endpoint": "/tools/merchant_policy", "params": {}},
        {"name": "request_quote", "method": "POST",
         "endpoint": "/tools/quote",
         "params": {"items": [{"sku": "string", "qty": "int"}], "mission_id": "string"}},
        {"name": "submit_proposal", "method": "POST",
         "endpoint": "/tools/submit_proposal",
         "params": {"mission": "object", "items": [{"sku": "string", "qty": "int"}]}},
        {"name": "create_order", "method": "POST",
         "endpoint": "/tools/create_order",
         "params": {"quote_id": "string", "proposal_hash": "string", "approve_seq": "int"},
         "headers": {"X-Idempotency-Key": "required"}},
        {"name": "check_payment", "method": "GET",
         "endpoint": "/tools/check_payment/{order_id}",
         "params": {"order_id": "string"}},
        {"name": "injection_demo", "method": "GET",
         "endpoint": "/demo/injection/{n}",
         "params": {"n": "string (I1-I8 or 1-8)"},
         "description": "Shows one adversarial injection payload and the deterministic gateway verdict that neutralizes it"},
        {"name": "gateway_proof", "method": "GET",
         "endpoint": "/gateway/proof", "params": {},
         "description": "Machine-provable purity report for the policy gateway (no LLM/network/IO patterns, source SHA-256)"},
        {"name": "audit_timeline", "method": "GET",
         "endpoint": "/audit/timeline", "params": {},
         "description": "Human-readable HTML rendering of the hash-chained audit ledger"},
        {"name": "demo_e2e", "method": "POST",
         "endpoint": "/demo/e2e", "params": {}, "auth": "X-API-Key required",
         "description": "Runs one complete end-to-end mission flow with real Razorpay test order creation"},
        {"name": "market_intelligence_radar", "method": "GET",
         "endpoint": "/growth/market-radar", "params": {},
         "description": "Real-world competitor benchmarks (Amazon, Flipkart) with verified timestamps and source URLs"},
        {"name": "merchant_growth_evaluate", "method": "POST",
         "endpoint": "/growth/evaluate",
         "params": {"intent": "string", "budget_paise": "int", "preferred_sku": "string?"},
         "description": "Analyzes intent, discovers competitor benchmarks, and synthesizes high-AOV cross-sell bundles"},
    ],
    "payment": {
        "gateway": "razorpay_test",
        "currency": "INR",
        "methods": ["card", "netbanking", "upi"],
        "webhook": "/webhook",
    },
    "policies": {
        "returns": "7-day return, unused, original packaging",
        "shipping": "Free above Rs 500, else Rs 49",
        "cancellation": "Allowed before payment capture",
        "upsell": "Max +30% of budget, max 2 proposals per mission",
    },
}


@router.get("/.well-known/agent-manifest.json")
async def agent_manifest():
    return MANIFEST


@router.get("/tools/merchant_policy")
async def merchant_policy():
    return MANIFEST["policies"]


@router.get("/catalog.jsonld")
async def catalog_jsonld():
    """schema.org Product + Offer JSON-LD for every SKU.

    Machine-readable catalog per the agent-commerce direction: prices in
    INR subunits, availability from stock, ratings and category linkage
    included so external agents can reason without bespoke parsing.
    """
    products = []
    for sku, p in CATALOG.items():
        products.append({
            "@type": "Product",
            "name": p["name"],
            "sku": sku,
            "category": p["category"],
            "description": p["description"],
            "aggregateRating": {
                "@type": "AggregateRating",
                "ratingValue": p["rating"],
                "bestRating": 5,
            },
            "offers": {
                "@type": "Offer",
                "priceCurrency": "INR",
                "price": p["price_paise"] / 100,
                "availability": ("https://schema.org/InStock"
                                 if p.get("stock", 0) > 0 else
                                 "https://schema.org/OutOfStock"),
            },
        })
    payload = {
        "@context": "https://schema.org",
        "@type": "ItemList",
        "itemListElement": products,
    }
    return Response(content=json.dumps(payload, indent=1),
                    media_type="application/ld+json")
