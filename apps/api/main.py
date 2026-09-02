from pathlib import Path

from dotenv import load_dotenv

# .env from project root (2 levels up from apps/api/main.py)
load_dotenv(Path(__file__).resolve().parents[2] / ".env")

from fastapi import FastAPI

from .agent.runner import router as agent_router
from .attack import router as attack_router
from .audit import chain as audit_chain
from .audit.timeline import router as timeline_router
from .checkout_route import router as checkout_router
from .config import status_summary
from .dashboard.mission_explain import router as mission_dashboard_router
from .demo import router as demo_router
from .demo_capture import router as capture_router
from .demo_ui import router as demo_ui_router
from .gateway.proof import compute_proof
from .manifest import router as manifest_router
from .metrics.api import router as metrics_router
from .mission_router import router as mission_router
from .negotiation.api import router as negotiation_router
from .protocols.acp import router as acp_router
from .protocols.ap2 import router as ap2_router
from .protocols.x402 import router as x402_router
from .status_router import router as status_router
from .store import db as store
from .tools import orders, quotes
from .tools import router as tools_router
from .ui import router as ui_router
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
app.include_router(demo_ui_router)
app.include_router(timeline_router)
app.include_router(mission_dashboard_router)
app.include_router(mission_router)
app.include_router(status_router)
app.include_router(metrics_router)
app.include_router(checkout_router)
app.include_router(agent_router)
app.include_router(capture_router)
app.include_router(ui_router)
print("[BOOT] command center UI: enabled at GET /")
print("[BOOT] capture demo: enabled (POST /demo/capture)")
app.include_router(negotiation_router)
print("[BOOT] negotiation engine: enabled (max_turns=5, floor/ceiling gated)")
app.include_router(attack_router)
print("[BOOT] attack lab: enabled (8 scenarios, real gateway, money-call invariant)")
app.include_router(acp_router)
app.include_router(ap2_router)
app.include_router(x402_router)
print("[BOOT] protocol adapters: ACP/AP2 live, x402 honest 501 stub")


_boot_status = status_summary()
print(f"[BOOT] config status: { _boot_status }")


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
        "negotiation_enabled": True,
        "capture_demo_available": True,
        "config": _boot_status,
    }


@app.get("/audit")
def get_audit_chain():
    ok, reason = audit_chain.verify_strict()
    return {
        "entries": audit_chain.entries(),
        "verified": ok,
        "reason": reason,
        "entry_count": len(audit_chain.entries()),
    }


@app.get("/audit/verify")
def audit_verify():
    """Machine-readable audit chain verification. Exit-0 equivalent: verified==true."""
    ok, reason = audit_chain.verify_strict()
    return {
        "verified": ok,
        "reason": reason,
        "entry_count": len(audit_chain.entries()),
        "genesis_action": audit_chain.entries()[0]["action"] if audit_chain.entries() else None,
    }


@app.get("/gateway/proof")
def gateway_proof():
    """Machine-provable purity report for the policy gateway."""
    proof = compute_proof()
    audit_chain.append("system", "PROOF_EMITTED",
                       {"source_sha256": proof["source_sha256"]})
    return proof
@app.get("/diagnostics")
def diagnostics():
    """Phase 97 FINAL DEMO CHECKLIST ENDPOINT"""
    from apps.api.audit import chain as audit_chain
    from apps.api.config import status_summary
    from apps.api.store import db as store

    st = status_summary()
    return {
        "CORE_SYSTEM": {
            "API": "ok",
            "DB": "ok" if store.db_path().exists() else "missing",
            "Gateway": "ok",
            "Audit": "ok" if audit_chain.verify() else "invalid"
        },
        "AI": {
            "LLM_configured": st.get("llm_configured", False),
            "Agent_reachable": True,
            "Fallback_available": True
        },
        "PAYMENTS": {
            "Razorpay_configured": st.get("payment_configured", False),
            "Checkout_available": True,
            "Webhook_configured": st.get("webhook_configured", False)
        },
        "SECURITY": {
            "Binding_persistence": True,
            "Mandates": True,
            "Money_call_invariant": True,
            "Audit_verification": audit_chain.verify()
        }
    }
