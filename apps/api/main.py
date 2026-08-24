import os
from pathlib import Path
from dotenv import load_dotenv

# .env from project root (2 levels up from apps/api/main.py)
load_dotenv(Path(__file__).resolve().parents[2] / ".env")

from fastapi import FastAPI
from .manifest import router as manifest_router
from .tools import router as tools_router
from .webhook.receiver import router as webhook_router, processed_event_ids, payment_ledger
from .audit import chain as audit_chain
from .gateway.proof import compute_proof

app = FastAPI(title="SELLABLE Merchant Storefront API", version="1.0.0")

# G6: chain self-verifies at boot; tamper halts the money path
CHAIN_OK_AT_BOOT = audit_chain.verify()
print(f"[BOOT] audit chain verify -> {CHAIN_OK_AT_BOOT}")

app.include_router(manifest_router)
app.include_router(tools_router)
app.include_router(webhook_router)


@app.get("/health")
def health():
    return {
        "status": "alive",
        "events_processed": len(processed_event_ids),
        "orders_tracked": len(payment_ledger),
        "audit_chain_ok": audit_chain.verify(),
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
