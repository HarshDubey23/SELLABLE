from pathlib import Path

from dotenv import load_dotenv

# .env from project root (2 levels up from apps/api/main.py)
load_dotenv(Path(__file__).resolve().parents[2] / ".env")

from fastapi import FastAPI

from .agent.runner import router as agent_router
from .audit import chain as audit_chain
from .audit.timeline import router as timeline_router
from .checkout_route import router as checkout_router
from .dashboard.mission_explain import router as mission_dashboard_router
from .demo import router as demo_router
from .demo_capture import router as capture_router
from .gateway.proof import compute_proof
from .manifest import router as manifest_router
from .metrics.api import router as metrics_router
from .negotiation.api import router as negotiation_router
from .protocols.acp import router as acp_router
from .protocols.ap2 import router as ap2_router
from .protocols.x402 import router as x402_router
from .store import db as store
from .tools import orders, quotes
from .tools import router as tools_router
from .webhook.receiver import payment_ledger, processed_event_ids
from .webhook.receiver import router as webhook_router

app = FastAPI(title="SELLABLE Merchant Storefront API", version="1.0.0")

# G6: chain self-verifies at boot; tamper halts the money path
CHAIN_OK_AT_BOOT = audit_chain.verify()
print(f"[BOOT] audit chain verify -> {CHAIN_OK_AT_BOOT}")
print(f"[BOOT] durable store -> {store.db_path()} "
      f"({len(audit_chain.entries())} chain entries, {len(orders)} orders, "
      f"{len(quotes)} quotes)")

app.include_router(manifest_router)
app.include_router(tools_router)
app.include_router(webhook_router)
app.include_router(demo_router)
app.include_router(timeline_router)
app.include_router(mission_dashboard_router)
app.include_router(metrics_router)
app.include_router(checkout_router)
app.include_router(agent_router)
app.include_router(capture_router)
print("[BOOT] capture demo: enabled (POST /demo/capture)")
app.include_router(negotiation_router)
print("[BOOT] negotiation engine: enabled (max_turns=5, floor/ceiling gated)")
app.include_router(acp_router)
app.include_router(ap2_router)
app.include_router(x402_router)
print("[BOOT] protocol adapters: ACP/AP2 live, x402 honest 501 stub")


@app.get("/health")
def health():
    return {
        "status": "alive",
        "events_processed": len(processed_event_ids),
        "orders_tracked": len(orders),
        "ledger_entries": len(payment_ledger),
        "quotes_tracked": len(quotes),
        "audit_entries": len(audit_chain.entries()),
        "audit_chain_ok": audit_chain.verify(),
        # Both routers are hard imports now (Phase 3): always available.
        "negotiation_enabled": True,
        "capture_demo_available": True,
    }


@app.get("/audit")
def get_audit_chain():
    return {"entries": audit_chain.entries(), "verified": audit_chain.verify()}


@app.get("/gateway/proof")
def gateway_proof():
    """Machine-provable purity report for the policy gateway."""
    proof = compute_proof()
    audit_chain.append("system", "PROOF_EMITTED",
                       {"source_sha256": proof["source_sha256"]})
    return proof
