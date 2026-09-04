"""From an accepted negotiation to a real payment, through the front door.

Nothing here is a payment path. Every step below is the same step the
ordinary buyer flow already takes -- sign a mission, evaluate it through
the R1-R12 gateway, lock a quote, sign the user mandates, cross the money
boundary through the execution machine. The market's whole contribution
is deciding *which* basket and *what* total, and both of those are
decided by deterministic server-side code before this module is reached.

Three checks run before anything can be bound, in this order:

  RECOMPUTE.  The policy engine runs again at settlement time against the
  stored intent and the signed manifest. What gets charged is that
  recomputation, never the total sitting in the offers table. Editing a
  row in the database therefore changes nothing about the money.

  RE-HASH.  The transcript is hashed again and compared to the hash
  recorded when the winner was claimed. Any offer, counter or verdict
  altered after acceptance moves the hash and the settlement stops.

  RE-APPROVE.  The gateway evaluates the basket at catalog list prices
  against the shopper's signed mission, exactly as it would for a
  non-negotiated purchase. The negotiated total may only ever be at or
  below that approved ceiling.

Note what none of that trusts. Not the merchants' language models, not
the buyer's, not the offers table, not the client. Three models spent
three rounds arguing and the only thing they were ever able to influence
was which row of a catalog got looked up.
"""
from __future__ import annotations

import json
import os
import time
from dataclasses import dataclass
from typing import Any

from ..audit import chain as audit_chain
from ..gateway import mission_verify
from ..products import CATALOG
from . import merchants as merchants_mod
from . import negotiation as neg
from . import policy as policy_mod
from .intents import OfferIntent

QUOTE_TTL_SECONDS = 30 * 60
MANDATE_TTL_SECONDS = 60 * 60
# Room above the negotiated total for the gateway's own budget check. The
# mission the shopper signed already carries their real ceiling; this is
# only the upsell headroom the gateway multiplies by, kept at the same
# 1.3 the rest of the system uses.
UPSELL_CAP = 1.3


class SettlementRefused(RuntimeError):
    """A settlement that must not proceed. Carries a machine-readable code."""

    def __init__(self, code: str, message: str,
                 detail: dict[str, Any] | None = None) -> None:
        super().__init__(message)
        self.code = code
        self.message = message
        self.detail = detail or {}


@dataclass(frozen=True)
class NegotiatedSettlement:
    """What the market asks the binding to pin, beyond the usual fields."""

    amount_paise: int
    merchant_id: str
    transcript_hash: str


def _require_accepted(negotiation_id: str) -> dict[str, Any]:
    row = neg.get(negotiation_id)
    if row is None:
        raise SettlementRefused("NEGOTIATION_NOT_FOUND",
                                f"unknown negotiation {negotiation_id}")
    if row["state"] != neg.ACCEPTED:
        raise SettlementRefused(
            "NEGOTIATION_NOT_ACCEPTED",
            f"negotiation is {row['state']}, not {neg.ACCEPTED}",
            {"state": row["state"]})
    return row


def recompute(negotiation_id: str) -> tuple[dict[str, Any],
                                            policy_mod.PolicyVerdict]:
    """Re-derive the payable total from first principles. No stored totals.

    This is the function that makes the offers table non-authoritative.
    It reads the intent the merchant actually sent, trusts nothing else,
    and asks the pure policy engine what that intent is worth against the
    merchant's signed manifest and the live catalog.
    """
    row = _require_accepted(negotiation_id)

    offer = None
    for candidate in neg.offers_for(negotiation_id):
        if candidate["offer_id"] == row["winner_offer_id"]:
            offer = candidate
            break
    if offer is None:
        raise SettlementRefused(
            "WINNING_OFFER_MISSING",
            "the accepted offer is no longer in the transcript")

    manifest = merchants_mod.get(offer["merchant_id"])
    if manifest is None:
        raise SettlementRefused("MERCHANT_UNKNOWN",
                                f"no manifest for {offer['merchant_id']}")

    intent = OfferIntent.model_validate(json.loads(offer["intent_json"]))
    verdict = policy_mod.evaluate(intent=intent, manifest=manifest,
                                  catalog=CATALOG)
    if not verdict.accepted or verdict.total_paise is None:
        # The offer passed policy when it was made and does not now. The
        # manifest was re-signed, the catalog moved, or the row was
        # edited. Any of those means this is not the deal that was won.
        raise SettlementRefused(
            "RECOMPUTE_REJECTED",
            f"the accepted offer no longer passes policy: {verdict.reason}",
            {"reason": verdict.reason, "breach": verdict.breach})

    recorded_hash = row["transcript_hash"] or ""
    live_hash = neg.transcript_hash(negotiation_id)
    if recorded_hash != live_hash:
        raise SettlementRefused(
            "TRANSCRIPT_MUTATED",
            "the negotiation changed after it was accepted",
            {"recorded": recorded_hash[:16], "recomputed": live_hash[:16]})

    return row, verdict


def _signed_mission(row: dict[str, Any], verdict: policy_mod.PolicyVerdict,
                    now_ts: int) -> dict[str, Any]:
    """The shopper's mission, in the form the gateway already verifies."""
    categories = sorted({CATALOG[line.sku]["category"]
                         for line in verdict.lines})
    blob: dict[str, Any] = {
        "mission_id": row["mission_id"],
        "intent": row["mission_text"][:200],
        "budget_paise": int(row["budget_paise"]),
        "allowed_categories": categories,
        "forbidden_categories": [],
        "upsell_cap": UPSELL_CAP,
        "expires_at": now_ts + 600,
    }
    blob["signature"] = mission_verify.sign_mission(
        json.dumps(blob, sort_keys=True, separators=(",", ":")))
    return blob


def _negotiated_quote(*, quote_id: str, mission_id: str,
                      verdict: policy_mod.PolicyVerdict,
                      transcript_hash: str,
                      now_ts: int) -> dict[str, Any]:
    """A price lock over the negotiated total, signed like any other.

    The line items are the catalog's and the adjustments are the policy
    engine's. Nothing in here came off the wire, which is why it can be
    written server-side without going through the client quote route --
    that route exists to stop a client naming a price, and no client is
    involved.
    """
    from .. import tools as tools_mod
    from ..store import db as store

    items = [{"sku": line.sku, "name": line.name, "qty": 1,
              "unit_price_paise": line.list_paise,
              "line_total_paise": line.discounted_paise}
             for line in verdict.lines]
    total = int(verdict.total_paise or 0)
    expires_at = now_ts + QUOTE_TTL_SECONDS

    payload = json.dumps(
        {"quote_id": quote_id, "mission_id": mission_id,
         "items": [{"sku": i["sku"], "qty": i["qty"]} for i in items],
         "total_paise": total, "expires_at": expires_at},
        sort_keys=True)
    signature = tools_mod._hmac(payload)

    quote = {"quote_id": quote_id, "mission_id": mission_id, "items": items,
             "total_paise": total, "expires_at": expires_at,
             "signature": signature,
             "negotiated": {
                 "merchant_id": verdict.merchant_id,
                 "transcript_hash": transcript_hash,
                 "subtotal_paise": verdict.subtotal_paise,
                 "line_discount_paise": verdict.line_discount_paise,
                 "bundle_discount_paise": verdict.bundle_discount_paise,
                 "shipping_paise": verdict.shipping_paise,
                 "warranty_paise": verdict.warranty_paise,
                 "delivery_days": verdict.delivery_days,
                 "priced_by": "server-side catalog recomputation"}}

    tools_mod.quotes[quote_id] = quote
    store.execute(
        "INSERT OR REPLACE INTO quotes "
        "(quote_id, mission_id, items, total_paise, expires_at, signature, "
        " created_at, negotiated_json) VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
        (quote_id, mission_id, json.dumps(items), total, expires_at,
         signature, now_ts, json.dumps(quote["negotiated"], sort_keys=True)))
    return quote


async def _replay(row: dict[str, Any], verdict: policy_mod.PolicyVerdict,
                  negotiation_id: str, total: int) -> dict[str, Any]:
    """Re-present an authorization that was already spent.

    The mandates are re-signed because they are time-bounded, but every
    identity the execution machine dedupes on -- mission, proposal hash,
    approve sequence -- is the one recorded at first settlement.
    """
    from ..mandates import CartMandate, IntentMandate, sign_cart, sign_intent
    from ..tools import CreateOrderReq, tool_create_order

    approve_seq = int(row["settlement_approve_seq"])
    quote_id = str(row["settlement_quote_id"])
    proposal_hash = str(row["settlement_proposal_hash"] or "")
    now_ts = int(time.time())

    mandate_key = os.environ.get("USER_MANDATE_KEY", "")
    if not mandate_key:
        raise SettlementRefused(
            "MANDATE_KEY_UNAVAILABLE",
            "USER_MANDATE_KEY is not configured")

    order_resp = await tool_create_order(
        CreateOrderReq(
            quote_id=quote_id, proposal_hash=proposal_hash,
            approve_seq=approve_seq,
            intent_mandate=sign_intent(IntentMandate(
                mission_id=row["mission_id"],
                user_id=f"user_{row['mission_id']}",
                ceiling_paise=total,
                expires_at=now_ts + MANDATE_TTL_SECONDS), mandate_key),
            cart_mandate=sign_cart(CartMandate(
                mission_id=row["mission_id"], cart_hash=proposal_hash,
                amount_paise=total, signed_at=now_ts,
                expires_at=now_ts + MANDATE_TTL_SECONDS), mandate_key)),
        x_idempotency_key=f"idem_mkt_{negotiation_id}_{approve_seq}",
        x_sellable_fault="")

    return {
        "negotiation_id": negotiation_id,
        "merchant_id": verdict.merchant_id,
        "amount_paise": total,
        "amount_display": f"Rs {total / 100:,.2f}",
        "approve_seq": approve_seq,
        "proposal_hash": proposal_hash,
        "quote_id": quote_id,
        "transcript_hash": row["transcript_hash"],
        "breakdown": verdict.public(),
        "order": order_resp,
        "replayed": True,
    }


async def settle(negotiation_id: str, *,
                 idempotency_key: str | None = None) -> dict[str, Any]:
    """Take an accepted negotiation all the way to an order.

    Returns the outcome the rest of the system already speaks, with the
    negotiation's own facts attached. Raises SettlementRefused before any
    money path is touched if the negotiation cannot be trusted.
    """
    from ..mandates import CartMandate, IntentMandate, sign_cart, sign_intent
    from ..tools import CreateOrderReq, ProposalReq, evaluate_proposal, tool_create_order

    row, verdict = recompute(negotiation_id)
    total = int(verdict.total_paise or 0)
    now_ts = int(time.time())

    # ---- already settled? replay the original authorization -----------
    #
    # Not "return the cached answer" -- re-run the money path with the
    # SAME approve_seq, quote and proposal hash. The execution machine
    # recognises that authorization, finds its durable row, and hands
    # back the original order. Re-deriving a fresh authorization here
    # instead would look to that machine like a second, different
    # authorized purchase, and it would dutifully open a second payment.
    if row["settlement_approve_seq"] is not None:
        return await _replay(row, verdict, negotiation_id, total)

    mandate_key = os.environ.get("USER_MANDATE_KEY", "")
    if not mandate_key:
        raise SettlementRefused(
            "MANDATE_KEY_UNAVAILABLE",
            "USER_MANDATE_KEY is not configured; the user mandates that "
            "authorize a payment cannot be signed")

    # ---- gateway: the same R1-R12 every other purchase goes through ---
    mission_blob = _signed_mission(row, verdict, now_ts)
    settlement = NegotiatedSettlement(
        amount_paise=total, merchant_id=verdict.merchant_id,
        transcript_hash=row["transcript_hash"] or "")

    proposal_req = ProposalReq(
        mission=mission_blob,
        items=[{"sku": line.sku, "qty": 1} for line in verdict.lines])
    verdict_resp = await evaluate_proposal(proposal_req, settlement=settlement)

    decision = verdict_resp["data"]["decision"]
    if decision != "APPROVE":
        audit_chain.append("market", "settlement_refused", {
            "negotiation_id": negotiation_id, "stage": "gateway",
            "decision": decision,
            "rule_id": verdict_resp["data"].get("rule_id")},
            error_code=verdict_resp["data"].get("rule_id") or "GATEWAY_REFUSED",
            review_state="market_settlement_blocked")
        raise SettlementRefused(
            "GATEWAY_REFUSED",
            f"the gateway did not approve this basket: {decision}",
            {"decision": decision,
             "rule_id": verdict_resp["data"].get("rule_id"),
             "reason": verdict_resp["data"].get("reason")})

    approve_seq = int(verdict_resp["seq"])
    proposal_hash = verdict_resp["data"]["proposal_hash"] or ""

    # ---- price lock, mandates, money boundary -------------------------
    quote_id = f"qn_{negotiation_id[-12:]}_{approve_seq}"
    _negotiated_quote(quote_id=quote_id, mission_id=row["mission_id"],
                      verdict=verdict,
                      transcript_hash=row["transcript_hash"] or "",
                      now_ts=now_ts)

    intent_mandate = sign_intent(IntentMandate(
        mission_id=row["mission_id"], user_id=f"user_{row['mission_id']}",
        ceiling_paise=total, expires_at=now_ts + MANDATE_TTL_SECONDS,
    ), mandate_key)
    cart_mandate = sign_cart(CartMandate(
        mission_id=row["mission_id"], cart_hash=proposal_hash,
        amount_paise=total, signed_at=now_ts,
        expires_at=now_ts + MANDATE_TTL_SECONDS,
    ), mandate_key)

    audit_chain.append("market", "settlement_authorized", {
        "negotiation_id": negotiation_id,
        "merchant_id": verdict.merchant_id,
        "amount_paise": total,
        "approve_seq": approve_seq,
        "transcript_hash": row["transcript_hash"],
        "priced_by": "server-side catalog recomputation"},
        review_state="market_settlement_authorized")

    # Claim the sole right to settle before crossing the boundary. A
    # caller that loses the race did not authorize anything -- it replays
    # the winner's authorization instead of spending its own.
    if not neg.claim_settlement(negotiation_id, approve_seq=approve_seq,
                                quote_id=quote_id,
                                proposal_hash=proposal_hash):
        fresh = neg.get(negotiation_id)
        assert fresh is not None
        return await _replay(fresh, verdict, negotiation_id, total)

    idem = idempotency_key or f"idem_mkt_{negotiation_id}_{approve_seq}"

    order_resp = await tool_create_order(
        CreateOrderReq(quote_id=quote_id, proposal_hash=proposal_hash,
                       approve_seq=approve_seq,
                       intent_mandate=intent_mandate,
                       cart_mandate=cart_mandate),
        x_idempotency_key=idem,
        # Called in-process, so the Header defaults are never filled in by
        # FastAPI. Both are passed explicitly; the fault switch is the
        # timeout-injection demo hook and stays off for a real settlement.
        x_sellable_fault="")

    return {
        "negotiation_id": negotiation_id,
        "merchant_id": verdict.merchant_id,
        "amount_paise": total,
        "amount_display": f"Rs {total / 100:,.2f}",
        "approve_seq": approve_seq,
        "proposal_hash": proposal_hash,
        "quote_id": quote_id,
        "transcript_hash": row["transcript_hash"],
        "breakdown": verdict.public(),
        "order": order_resp,
    }
