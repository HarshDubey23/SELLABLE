"""Audit chain demos: verify a block yourself, and watch tampering cascade.

TWO ENDPOINTS, ONE POINT
------------------------
`GET /audit/block/{seq}` hands back a block together with the exact byte
string its hash was computed over. Anything that can do SHA-256 — the
browser, `sha256sum`, a phone — can then check the hash without trusting
this server's answer. That is the difference between "we verified it"
and "verify it yourself".

`POST /audit/tamper-demo` flips one bit in a copy of the chain and walks
it exactly as the real verifier walks it, showing where verification
halts and how many blocks are invalidated downstream.

THE COPY IS THE WHOLE ETHIC
---------------------------
The tamper demo never writes. It loads rows, mutates a Python list, and
recomputes with the imported hash function — the same one the real
verifier uses, never a reimplementation. It then re-runs the real
on-disk verification and returns that result too, so the response itself
proves the ledger was not touched. Doing this destructively would be a
one-way demo: the server verifies its chain at boot and refuses to come
up on a broken one.
"""
from __future__ import annotations

from typing import Any

from fastapi import APIRouter, HTTPException, Request
from pydantic import BaseModel, Field

from . import ratelimit
from .audit import chain as audit_chain

router = APIRouter(tags=["audit"])

_TAMPER_LIMIT = 20  # per minute per client


def hash_preimage(entry: dict[str, Any]) -> str:
    """The exact string `audit.chain._hash` digests, rebuilt field by field.

    Kept beside a test that asserts sha256(this) equals the stored hash
    for every block on the chain, so it cannot drift from the real
    implementation without the suite going red.
    """
    return (f"{entry['seq']}|{entry['ts']}|{entry['actor']}|"
            f"{entry['action']}|{entry['payload_hash']}|{entry['prev_hash']}")


@router.get("/audit/block/{seq}")
def audit_block(seq: int) -> dict[str, Any]:
    """One block, plus everything needed to check its hash elsewhere."""
    entries = audit_chain.entries()
    match = next((e for e in entries if e["seq"] == seq), None)
    if match is None:
        raise HTTPException(404, detail={
            "ok": False,
            "error": {"error_code": "UNKNOWN_BLOCK",
                      "message": f"no audit block with seq {seq}",
                      "chain_length": len(entries)}})

    preimage = hash_preimage(match)
    return {
        "ok": True,
        "seq": match["seq"],
        "ts": match["ts"],
        "actor": match["actor"],
        "action": match["action"],
        "payload_hash": match["payload_hash"],
        "prev_hash": match["prev_hash"],
        "hash": match.get("hash"),
        "hash_algorithm": "sha256",
        "hash_preimage": preimage,
        "hash_preimage_format": (
            "seq|ts|actor|action|payload_hash|prev_hash, UTF-8, no trailing "
            "newline"),
        "verify_it_yourself": (
            "printf '%s' '<hash_preimage>' | sha256sum  — or "
            "crypto.subtle.digest('SHA-256', ...) in your own browser"),
        "note": ("the chain commits to a hash of the payload, not the "
                 "payload itself; that is what lets it prove nothing was "
                 "edited without becoming a second copy of the data"),
    }


class TamperBody(BaseModel):
    block_seq: int = Field(ge=0)


@router.post("/audit/tamper-demo")
def tamper_demo(body: TamperBody, request: Request) -> dict[str, Any]:
    """Flip one bit in a copy of the chain; report where verification halts."""
    who = request.client.host if request.client else "unknown"
    if not ratelimit.allow(who, bucket="tamper_demo", limit=_TAMPER_LIMIT):
        raise HTTPException(429, detail={
            "ok": False,
            "error": {"error_code": "RATE_LIMITED",
                      "retry_after_seconds": ratelimit.retry_after(
                          who, bucket="tamper_demo")}})

    entries = audit_chain.entries()
    if not entries:
        raise HTTPException(404, detail={
            "ok": False,
            "error": {"error_code": "EMPTY_CHAIN"}})
    target_index = next((i for i, e in enumerate(entries)
                         if e["seq"] == body.block_seq), None)
    if target_index is None:
        raise HTTPException(404, detail={
            "ok": False,
            "error": {"error_code": "UNKNOWN_BLOCK",
                      "message": f"no audit block with seq {body.block_seq}",
                      "chain_length": len(entries)}})

    # An in-memory copy. Nothing below touches SQLite.
    copied = [dict(e) for e in entries]
    target = copied[target_index]
    original_payload_hash = target["payload_hash"]
    original_hash = target.get("hash")

    # Flip the low bit of one hex digit in the middle of the committed
    # payload hash: the smallest possible edit to what the block attests.
    digits = list(original_payload_hash)
    pos = len(digits) // 2
    digits[pos] = "0" if digits[pos] != "0" else "1"
    target["payload_hash"] = "".join(digits)
    tampered_hash = audit_chain._hash(target)

    # Walk exactly as verify_strict walks: a block is broken when its
    # stored hash no longer matches a recompute, or when its prev_hash no
    # longer matches the previous block's (recomputed) hash.
    halt_at: int | None = None
    prev_actual = None
    for blk in copied:
        recomputed = audit_chain._hash(blk)
        if blk.get("hash") != recomputed:
            halt_at = blk["seq"]
            break
        if prev_actual is not None and blk["prev_hash"] != prev_actual:
            halt_at = blk["seq"]
            break
        prev_actual = recomputed

    on_disk_ok, on_disk_reason = audit_chain.verify_strict()

    invalidated = 0 if halt_at is None else len(entries) - target_index
    return {
        "ok": True,
        "tampered_block": {
            "seq": body.block_seq,
            "actor": target["actor"],
            "action": target["action"],
        },
        "original_payload_hash": original_payload_hash,
        "tampered_payload_hash": target["payload_hash"],
        "original_hash": original_hash,
        "recomputed_hash_after_tamper": tampered_hash,
        "halt_at_block": halt_at if halt_at is not None else -1,
        "blocks_invalidated": invalidated,
        "chain_length": len(entries),
        "on_disk_chain": "VERIFIED" if on_disk_ok else "HALTED",
        "on_disk_reason": on_disk_reason,
        "disclosure": ("Tamper computed on an in-memory copy. The on-disk "
                       "ledger is untouched — boot-time verification would "
                       "halt the server."),
    }
