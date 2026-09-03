"""Merchant Growth & Competitive Intelligence API Router.

Exposes endpoints for real-world competitor discovery, AI-to-AI bundling,
and bounded high-AOV checkout through the deterministic Policy Gateway.
"""
from __future__ import annotations

import time
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field

from ..deps import require_api_key
from ..tools import ProposalReq, tool_submit_proposal
from ..gateway.mission_verify import sign_mission, dumps as _dumps
from .engine import evaluate_merchant_growth, GrowthEvaluationResult
from .intelligence import get_all_market_radar, get_market_intelligence
from .ui import render_growth_studio_page
from fastapi.responses import HTMLResponse

router = APIRouter(prefix="/growth", tags=["growth"])


@router.get("", response_class=HTMLResponse)
@router.get("/", response_class=HTMLResponse)
@router.get("/ui", response_class=HTMLResponse)
async def growth_studio_ui():
    """Interactive Merchant Growth & Market Intelligence Studio."""
    return render_growth_studio_page()



class GrowthEvaluateReq(BaseModel):
    intent: str = Field("Buy cricket bat under Rs 3,000", description="Buyer agent purchase intent")
    budget_paise: int = Field(300000, gt=0, description="Spending limit in paise")
    allowed_categories: list[str] = Field(default_factory=lambda: ["cricket"], description="Allowed categories")
    preferred_sku: str | None = Field(None, description="Optional preferred starting SKU")


class GrowthTransactReq(BaseModel):
    intent: str = Field("Buy cricket bat under Rs 3,000", description="Buyer intent")
    budget_paise: int = Field(300000, gt=0, description="Budget limit in paise")
    items: list[dict] = Field(..., description="Selected bundle items [{'sku': ..., 'qty': ...}]")


@router.post("/evaluate", response_model=GrowthEvaluationResult)
async def evaluate_growth(req: GrowthEvaluateReq) -> GrowthEvaluationResult:
    """Analyze buyer intent, discover competitor benchmarks, and construct high-AOV growth bundle."""
    return evaluate_merchant_growth(
        intent=req.intent,
        budget_paise=req.budget_paise,
        allowed_categories=req.allowed_categories,
        preferred_sku=req.preferred_sku,
    )


@router.get("/market-radar")
async def market_radar():
    """Return live competitive intelligence radar comparing merchant catalog to Amazon, Flipkart, etc."""
    radar = get_all_market_radar()
    return {
        "count": len(radar),
        "source": "REAL_WORLD_MARKET_INTELLIGENCE",
        "is_untrusted_flag_active": True,
        "radar": radar,
    }


@router.post("/transact")
async def execute_growth_transaction(req: GrowthTransactReq):
    """Execute an AI-optimized merchant growth bundle through the deterministic Policy Gateway.

    Guarantees:
    - 0 LLM money authority: proposal runs through pure-stdlib R1-R12 gateway.
    - Prices taken strictly from server-side catalog.
    - Single-use SHA-256 approval binding minted.
    - Settles on live Razorpay test-mode API.
    """
    now_ts = int(time.time())
    mission_id = f"GRW-{now_ts}"

    mission_dict = {
        "mission_id": mission_id,
        "intent": req.intent,
        "budget_paise": req.budget_paise,
        "allowed_categories": ["cricket", "electronics", "audio", "books", "apparel", "coffee"],
        "forbidden_categories": [],
        "upsell_cap": 1.2,
        "expires_at": now_ts + 3600,
    }
    # Sign out-of-band for demo convenience
    sig = sign_mission(_dumps(mission_dict))
    mission_dict["signature"] = sig

    proposal_req = ProposalReq(
        mission=mission_dict,
        items=req.items,
        protocol_scope={"growth_optimized": True, "source": "merchant_growth_engine"},
    )

    executor_resp = await tool_submit_proposal(proposal_req)
    verdict_data = executor_resp.get("data", {}) if isinstance(executor_resp, dict) else {}
    decision = verdict_data.get("decision", "REJECT")

    return {
        "ok": True,
        "mission_id": mission_id,
        "decision": decision,
        "proposal_hash": verdict_data.get("proposal_hash"),
        "seq": executor_resp.get("seq"),
        "executor": executor_resp,
    }
