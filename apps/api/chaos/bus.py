"""Single Choke Point Chaos Fault Bus Middleware for FastAPI/ASGI."""
from __future__ import annotations

import asyncio
import time
from typing import Any

from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import JSONResponse, Response

from .engine import chaos_engine
from .events import event_bus
from .types import FaultType


class ChaosFaultBusMiddleware(BaseHTTPMiddleware):
    """Intercepts all incoming/outgoing HTTP traffic and injects active faults."""

    async def dispatch(self, request: Request, call_next) -> Response:
        path = request.url.path
        method = request.method
        trace_id = request.headers.get("X-Trace-Id", f"t-{int(time.time()*1000)%1000000:06d}")

        # 1. Check Latency Spike Fault
        lat_cfg = chaos_engine.get_fault_for_route(path, FaultType.LATENCY_SPIKE)
        if lat_cfg:
            delay_ms = lat_cfg.params.get("delay_ms", 3000)
            event_bus.emit(
                kind="chaos_injection",
                actor="chaos_monkey",
                summary=f"INJECTED latency_spike ({delay_ms}ms) on {method} {path}",
                trace_id=trace_id,
                data={"route": path, "delay_ms": delay_ms},
            )
            await asyncio.sleep(delay_ms / 1000.0)

        # 2. Check 5xx Flake Fault
        flake_cfg = chaos_engine.get_fault_for_route(path, FaultType.FLAKE_5XX)
        if flake_cfg:
            event_bus.emit(
                kind="chaos_injection",
                actor="chaos_monkey",
                summary=f"INJECTED 5xx_flake (503 Service Unavailable) on {method} {path}",
                trace_id=trace_id,
                data={"route": path},
            )
            return JSONResponse(
                {
                    "error": {
                        "code": "VELOCITY_BLOCKED",
                        "message": "Gateway temporarily unavailable due to simulated 5xx flake",
                        "trace_id": trace_id,
                        "retryable": True,
                    }
                },
                status_code=503,
            )

        # 3. Check Bound Breach Fault
        bound_cfg = chaos_engine.get_fault_for_route(path, FaultType.BOUND_BREACH)
        if bound_cfg and path.endswith("/submit_proposal"):
            event_bus.emit(
                kind="chaos_injection",
                actor="chaos_monkey",
                summary=f"INJECTED bound_breach refusal (403 OVER_BOUND) on {path}",
                trace_id=trace_id,
                data={"route": path},
            )
            return JSONResponse(
                {
                    "error": {
                        "code": "OVER_BOUND",
                        "message": "Proposed amount exceeds user mandate spend cap",
                        "trace_id": trace_id,
                        "retryable": False,
                    }
                },
                status_code=403,
            )

        # 4. Check Webhook Blackhole Fault
        if path.startswith("/webhook"):
            bh_cfg = chaos_engine.get_fault_for_route(path, FaultType.WEBHOOK_BLACKHOLE)
            if bh_cfg:
                event_bus.emit(
                    kind="chaos_injection",
                    actor="chaos_monkey",
                    summary=f"INJECTED webhook_blackhole — dropping webhook delivery for {path}",
                    trace_id=trace_id,
                    data={"route": path},
                )
                return JSONResponse({"status": "dropped_by_chaos_blackhole", "ok": True}, status_code=200)

        # Execute standard pipeline
        response = await call_next(request)
        return response


# Helper functions to build structured gateway refusal payloads adhering strictly to contract
def make_gateway_refusal(
    code: str,
    message: str,
    trace_id: str,
    retryable: bool = False,
    fresh_quote: dict[str, Any] | None = None,
    status_code: int = 400,
) -> JSONResponse:
    err_dict: dict[str, Any] = {
        "code": code,
        "message": message,
        "trace_id": trace_id,
        "retryable": retryable,
    }
    if fresh_quote:
        err_dict["fresh_quote"] = fresh_quote

    return JSONResponse({"error": err_dict}, status_code=status_code)
