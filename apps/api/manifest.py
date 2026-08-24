"""Agent-native discovery: /.well-known/agent-manifest.json"""

from fastapi import APIRouter
from .products import get_categories

router = APIRouter()

MANIFEST = {
    "merchant": {
        "name": "SELLABLE Demo Dukaan",
        "description": "Agent-readable, agent-transactable, agent-safe merchant on Razorpay test mode.",
        "version": "1.0.0",
        "protocol": "sellable-v1",
    },
    "capabilities": ["search", "get_product", "quote", "propose", "checkout", "payment_status"],
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
