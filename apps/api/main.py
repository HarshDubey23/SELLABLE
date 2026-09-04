import os
from pathlib import Path

from dotenv import load_dotenv

# .env from project root (2 levels up from apps/api/main.py)
load_dotenv(Path(__file__).resolve().parents[2] / ".env")

from fastapi import FastAPI
from fastapi.middleware.gzip import GZipMiddleware

from .agent.runner import router as agent_router
from .attack import router as attack_router
from .attack_custom import router as attack_custom_router
from .audit import chain as audit_chain
from .audit_demo import router as audit_demo_router
from .chaos import ChaosFaultBusMiddleware, chaos_api_router
from .checkout_route import router as checkout_router
from .config import status_summary
from .demo import router as demo_router
from .demo_capture import router as capture_router
from .demo_kill import router as kill_router
from .discovery import discovery_router
from .execution import recover_stranded
from .execution_api import router as execution_router
from .gateway.proof import compute_proof
from .growth import growth_router
from .manifest import router as manifest_router
from .metrics.api import router as metrics_router
from .mission_router import router as mission_router
from .negotiation.api import router as negotiation_router
from .protocols.acp import router as acp_router
from .protocols.ap2 import router as ap2_router
from .protocols.uap import router as uap_router
from .protocols.x402 import router as x402_router
from .receipt import router as receipt_router
from .status_router import router as status_router
from .store import db as store
from .tools import orders, quotes
from .tools import router as tools_router
from .web.judge_page import router as judge_page_router
from .web.product_page import router as product_router
from .web.redirects import router as redirect_router
from .web.trace_page import router as trace_router
from .webhook.receiver import payment_ledger, processed_event_ids
from .webhook.receiver import router as webhook_router

app = FastAPI(title="SELLABLE Merchant Storefront API", version="1.0.0")

# Mount GZip Compression Middleware (Performance)
app.add_middleware(GZipMiddleware, minimum_size=1024)

# Mount Chaos Fault Bus Middleware (Single Choke Point)
app.add_middleware(ChaosFaultBusMiddleware)

# G6: chain self-verifies at boot; tamper halts the money path
CHAIN_OK_AT_BOOT, _boot_reason = audit_chain.verify_strict()
print(f"[BOOT] audit chain verify_strict -> {CHAIN_OK_AT_BOOT} ({_boot_reason})")
print(f"[BOOT] durable store -> {store.db_path()} "
      f"({len(audit_chain.entries())} chain entries, {len(orders)} orders, "
      f"{len(quotes)} quotes)")

app.include_router(manifest_router)
app.include_router(tools_router)
app.include_router(webhook_router)
app.include_router(demo_router)
app.include_router(mission_router)
app.include_router(status_router)
app.include_router(metrics_router)
app.include_router(checkout_router)
app.include_router(agent_router)
app.include_router(capture_router)
# Three HTML surfaces, and nothing else. Everything the retired pages
# showed now lives inside one of them; `redirect_router` keeps their old
# paths pointing at wherever the capability moved to.
app.include_router(trace_router)        # GET /trace/{ref} one purchase, end to end
app.include_router(judge_page_router)   # GET /judge       the evidence console
app.include_router(redirect_router)     # retired paths -> the three above
app.include_router(chaos_api_router)
print("[BOOT] pages: GET /trace/{ref}  |  GET /judge")
print("[BOOT] capture demo: enabled (POST /demo/capture)")
app.include_router(negotiation_router)
print("[BOOT] negotiation engine: enabled (max_turns=5, floor/ceiling gated)")
app.include_router(attack_router)
app.include_router(attack_custom_router)   # reviewer-authored attacks
app.include_router(audit_demo_router)      # block preimage + tamper cascade
app.include_router(receipt_router)
app.include_router(kill_router)
print("[BOOT] attack lab: enabled (8 scenarios, real gateway, money-call invariant)")
print("[BOOT] reviewer attack sandbox: POST /attack/custom, POST /attack/gauntlet")
app.include_router(acp_router)
app.include_router(ap2_router)
app.include_router(uap_router)
app.include_router(x402_router)
print("[BOOT] protocol adapters: NPCI UAP/ACP/AP2 live, x402 honest 501 stub")
app.include_router(growth_router)
print("[BOOT] merchant growth & market intelligence engine: live at /growth")
app.include_router(discovery_router)
print("[BOOT] discovery pipeline: live at /discovery")
app.include_router(execution_router)
app.include_router(product_router)      # GET /            the shop (included last so / takes precedence)

# Crash recovery: any execution still sitting in REMOTE_ATTEMPTED means the
# process died with a payment in flight. We cannot know the outcome, so it
# becomes RECONCILIATION_REQUIRED rather than a guessed success or failure.
_recovered = recover_stranded()
if _recovered:
    print(f"[BOOT] crash recovery: {len(_recovered)} execution(s) moved "
          f"REMOTE_ATTEMPTED -> RECONCILIATION_REQUIRED {_recovered}")
print("[BOOT] execution state machine: live at /executions")

_boot_status = status_summary()
if _boot_status["boot_missing_required"]:
    # Not fatal — the server still serves its read-only surfaces — but the
    # signing and mandate paths cannot function, so say so loudly rather
    # than letting it look healthy.
    print("[BOOT] *** DEGRADED: missing required configuration: "
          f"{_boot_status['boot_missing_required']} ***")
    print("[BOOT] *** R9 will reject every mission and INV-3 cannot verify "
          "a mandate. Run 'python run.py' to generate them. ***")
print(f"[BOOT] config status: {_boot_status}")


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
    """Machine-provable purity report for the policy gateway (read-only)."""
    return compute_proof()


@app.get("/diagnostics")
def diagnostics():
    """Runtime facts only.

    Everything here is read from live state. Nothing is asserted because
    it ought to be true — an earlier version of this endpoint returned
    hardcoded `True` for agent reachability, checkout availability and the
    money-call invariant, which made it worse than useless.
    """
    from . import execution as _ex
    from . import execution_provider as _prov
    from .audit import chain as _ac
    from .config import status_summary as _status
    from .gateway.registry import RULE_REGISTRY
    from .store import db as _store
    from .webhook.receiver import pending_events

    st = _status()
    chain_ok, chain_reason = _ac.verify_strict()
    exec_summary = _ex.summary()

    return {
        "core": {
            "database_path": _store.db_path(),
            "database_present": Path(_store.db_path()).exists(),
            "audit_chain_verified": chain_ok,
            "audit_chain_reason": chain_reason,
            "audit_entries": len(_ac.entries()),
            "gateway_rules_registered": len(RULE_REGISTRY),
        },
        "ai": {
            "llm_configured": st["llm_configured"],
            "llm_model": st["llm_model"],
            "note": ("with no LLM key the buyer agent falls back to a "
                     "deterministic picker; it never gains money authority "
                     "either way"),
        },
        "payments": {
            "provider": _prov.provider_name(),
            "provider_description": _prov.mode_description(),
            "razorpay_credentials_present": _prov.razorpay_credentials_present(),
            "webhook_secret_configured": bool(
                os.environ.get("RAZORPAY_WEBHOOK_SECRET", "").strip()),
            "executions_by_state": exec_summary,
            "executions_awaiting_reconciliation": exec_summary.get(
                _ex.RECONCILIATION_REQUIRED, 0),
            "webhook_events_pending_apply": len(pending_events()),
        },
    }


@app.get("/api/v1/telemetry")
def telemetry():
    """Real-time telemetry for dashboard auto-refresh. Polled every 5s by the UI."""
    from . import execution as _ex
    from . import execution_provider as _prov
    from . import money as _m
    from .approval import all_bindings as _ab
    from .attack import SCENARIOS as _scenarios
    from .audit import chain as _ac
    from .gateway.registry import RULE_REGISTRY
    from .store import db as _store
    _ok, _reason = _ac.verify_strict()
    bindings = _ab()
    consumed_count = _store.query_one("SELECT COUNT(*) as c FROM bindings WHERE consumed_at IS NOT NULL")
    c_num = consumed_count["c"] if consumed_count else 0
    return {
        "ok": True,
        "audit_blocks": len(_ac.entries()),
        "chain_valid": _ok,
        "money_calls": _m.snapshot().get("total", 0),
        "bindings_issued": len(bindings),
        "bindings_consumed": c_num,
        "gateway_rules": len(RULE_REGISTRY),
        "orders_tracked": len(orders),
        "quotes_tracked": len(quotes),
        # This is how many adversarial scenarios the Attack Lab can RUN.
        # It is not a count of attacks blocked at runtime — that number only
        # exists after you actually run them.
        "attack_scenarios_available": len(_scenarios),
        "payment_provider": _prov.provider_name(),
        "executions_by_state": _ex.summary(),
    }


@app.get("/api/v1/security-score", operation_id="security_posture")
@app.get("/api/v1/security_score", operation_id="security_posture_snake",
         include_in_schema=False)
@app.get("/security_score", operation_id="security_posture_legacy",
         include_in_schema=False)
def security_score():
    """Runtime security posture, computed from things that are actually true.

    An earlier version of this endpoint scored itself with expressions like
    `bool(cfg.razorpay_webhook_secret or True)` — which is `True` no matter
    what — alongside hardcoded `concurrency_safe: True` and
    `architecture_guard: True`. A score that cannot go down is not a score.

    Properties that are proven by the test suite rather than observable at
    runtime (concurrency safety, gateway purity, architecture boundaries)
    are deliberately NOT counted here. They live in the test evidence,
    where they can fail.
    """
    import os as _os

    from . import execution as _ex
    from . import execution_provider as _prov
    from .audit import chain as _ac
    from .gateway.registry import RULE_REGISTRY
    from .store import db as _store
    from .webhook.receiver import pending_events

    chain_ok, chain_reason = _ac.verify_strict()
    exec_summary = _ex.summary()

    checks = {
        "audit_chain_verifies": {
            "ok": chain_ok,
            "detail": chain_reason,
        },
        "twelve_policy_rules_registered": {
            "ok": len(RULE_REGISTRY) == 12,
            "detail": f"{len(RULE_REGISTRY)} rules in the canonical registry",
        },
        "mission_signing_key_configured": {
            "ok": bool(_os.environ.get("MISSION_HMAC_KEY", "").strip()),
            "detail": "R9 rejects every mission when this is unset (fail-closed)",
        },
        "user_mandate_key_configured": {
            "ok": bool(_os.environ.get("USER_MANDATE_KEY", "").strip()),
            "detail": "INV-3 mandates cannot be verified without it",
        },
        "webhook_secret_configured": {
            "ok": bool(_os.environ.get("RAZORPAY_WEBHOOK_SECRET", "").strip()),
            "detail": "POST /webhook returns 503 fail-closed when unset",
        },
        "durable_store_present": {
            "ok": Path(_store.db_path()).exists(),
            "detail": _store.db_path(),
        },
        "no_executions_awaiting_reconciliation": {
            "ok": exec_summary.get(_ex.RECONCILIATION_REQUIRED, 0) == 0,
            "detail": f"{exec_summary.get(_ex.RECONCILIATION_REQUIRED, 0)} "
                      f"execution(s) with an unresolved outcome",
        },
        "no_webhook_events_awaiting_apply": {
            "ok": len(pending_events()) == 0,
            "detail": f"{len(pending_events())} event(s) persisted but not applied",
        },
    }

    passed = sum(1 for c in checks.values() if c["ok"])
    total = len(checks)
    return {
        "score": passed,
        "max_score": total,
        "label": f"{passed}/{total} runtime security controls active",
        "status": "SECURE" if passed == total else "DEGRADED",
        "checks": checks,
        "payment_provider": _prov.provider_name(),
        "excluded_from_score": {
            "reason": "verified by tests, not observable at runtime",
            "properties": ["gateway purity (no LLM/network/IO in R1-R12)",
                           "single-use binding under concurrency",
                           "money-call invariant on rejection",
                           "architecture import boundaries"],
            "evidence": "pytest tests/invariants tests/concurrency tests/gateway",
        },
    }


@app.post("/api/v1/gateway/simulate")
async def simulate_gateway(payload: dict):
    """Interactive rule simulator: submit a proposal, see which rules fire."""
    import time

    from .gateway import engine as gw_engine
    from .gateway.types import Mission, Proposal, ProposalItem
    from .products import CATALOG

    now_ts = int(time.time())
    budget = int(payload.get("budget_paise", 200000))
    amount = int(payload.get("amount_paise", 150000))
    payload.get("category", "cricket")
    allowed = payload.get("allowed_categories", ["cricket"])
    sku = payload.get("sku", "BAT-001")

    try:
        from .gateway.mission_verify import dumps as _dumps
        from .gateway.mission_verify import sign_mission as _sign
        mission_dict = {
            "mission_id": "SIM-001",
            "intent": "simulation",
            "budget_paise": budget,
            "allowed_categories": allowed,
            "forbidden_categories": [],
            "upsell_cap": 1.0,
            "expires_at": now_ts + 3600,
        }
        sig = _sign(_dumps(mission_dict))
        mission = Mission(
            mission_id="SIM-001",
            intent="simulation",
            budget_paise=budget,
            allowed_categories=tuple(allowed),
            forbidden_categories=(),
            upsell_cap=1.0,
            expires_at=now_ts + 3600,
            signature=sig,
        )
        proposal = Proposal(
            mission_id="SIM-001",
            items=(ProposalItem(sku=sku, qty=1, price_paise=amount),),
            justification="simulation",
        )
        verdict = gw_engine.evaluate(mission=mission, proposal=proposal, catalog=CATALOG, verify_fn=lambda msg, s: True)
        return {
            "decision": verdict.decision.value,
            "rule_id": verdict.rule_id,
            "reason": verdict.reason,
            "proposal_hash": verdict.proposal_hash,
        }
    except Exception as e:
        return {"decision": "ERROR", "reason": str(e), "rule_id": None}
