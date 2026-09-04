"""POST /demo/kill-switch — kill the process, for real, to prove recovery.

The crash-recovery claim is that an execution left in REMOTE_ATTEMPTED
when the process dies comes back as RECONCILIATION_REQUIRED rather than
as a guessed success. A drill that simulates the crash proves nothing
about the crash; only actually dying does. So this endpoint calls
`os._exit`, which skips every cleanup handler — the closest thing to
`kill -9` a process can do to itself.

That is obviously dangerous, so it is gated twice and cannot be reached
by accident:

  * CHAOS_ENABLED must be exactly "true", and
  * the provider must be razorpay_test, i.e. someone deliberately put
    test credentials on this machine.

The public keyless deploy satisfies neither, so it answers 403 with the
reason — and the cockpit uses that same 403 to render the button
disabled with an honest explanation rather than pretending.

Durability does not depend on a clean shutdown: the audit chain and the
execution state machine write to SQLite in WAL mode before they act, and
the recovery sweep at boot is what turns those writes back into a
correct state. That is precisely what this button exists to show.
"""
from __future__ import annotations

import os
from typing import Any

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field

from . import execution_provider as provider_mod

router = APIRouter(tags=["chaos"])


class KillBody(BaseModel):
    confirm: str = Field(default="", max_length=32)


def _gate() -> tuple[bool, str]:
    """Both conditions, and the reason when either fails."""
    if os.environ.get("CHAOS_ENABLED", "").strip().lower() != "true":
        return False, ("kill switch requires CHAOS_ENABLED=true; it is off on "
                       "the public deploy so a visitor cannot stop the server")
    if provider_mod.provider_name() != provider_mod.LIVE_TEST:
        return False, ("kill switch requires the razorpay_test provider, so it "
                       "only runs on a machine someone deliberately configured "
                       "with test credentials")
    return True, "enabled"


@router.get("/demo/kill-switch")
def kill_switch_status() -> dict[str, Any]:
    """Whether the drill is available here. Read-only, always safe to call."""
    enabled, reason = _gate()
    return {
        "ok": True,
        "enabled": enabled,
        "reason": reason,
        "provider": provider_mod.provider_name(),
        "confirm_token": "KILL",
        "what_it_does": ("os._exit(1) — no cleanup handlers, no graceful "
                         "shutdown. Restart with `python run.py`; the boot "
                         "sweep moves any REMOTE_ATTEMPTED execution to "
                         "RECONCILIATION_REQUIRED."),
    }


@router.post("/demo/kill-switch")
def kill_switch(body: KillBody) -> dict[str, Any]:
    enabled, reason = _gate()
    if not enabled:
        raise HTTPException(403, detail={
            "ok": False,
            "error": {"error_code": "CHAOS_DISABLED", "reason": reason}})
    if body.confirm != "KILL":
        raise HTTPException(422, detail={
            "ok": False,
            "error": {"error_code": "CONFIRM_REQUIRED",
                      "message": 'send {"confirm": "KILL"} to actually die'}})

    # Everything that matters is already committed. WAL mode means the
    # last write is durable before this line runs; there is nothing to
    # flush, and pretending otherwise would weaken the demonstration.
    print("[CHAOS] kill switch fired - os._exit(1), no cleanup handlers")
    os._exit(1)
