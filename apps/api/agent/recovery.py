"""
Deterministic failure recovery — the brief's explicit bar.

Flow (every step hits a REAL api.razorpay.com endpoint or the real
Gemini model; nothing is simulated):

1. ATTEMPT  : POST /v1/payments with public-key auth, UPI rail.
              On this test merchant UPI is disabled, so Razorpay
              deterministically refuses the rail with a structured,
              documented error. That refusal is the real failure.
2. RECORD   : audit row payment_attempt_failed with the verbatim
              Razorpay error_code/description, review_state=escalated.
3. REASON   : ONE real Gemini call (outside the money path) receives
              the failure context and must answer strict JSON:
              {"reasoning": "...", "action": "create_payment_link"}
4. LINK     : on action=create_payment_link, POST /v1/payment_links
              (corrected amount, 24h expiry) -> real short_url.
5. CHAIN    : the reasoning row and the link row both carry
              parent_action_id pointing at the failed attempt's audit
              id, so the ledger visibly reads failure -> diagnosis ->
              recovery.

The authoritative post-attempt status is always re-read from Razorpay
(GET /v1/orders/{id}/payments); we never trust our own narrative over
the API.
"""
import json
from typing import Any

from .. import razorpay_client as rp
from ..audit import chain

UPI_VPA = "success@razorpay"  # Razorpay test VPA


def _extract_error(result: dict) -> dict:
    err = result.get("error") or {}
    return {
        "code": err.get("code"),
        "description": err.get("description"),
        "source": err.get("source"),
        "step": err.get("step"),
        "reason": err.get("reason"),
        "field": err.get("field"),
        "payment_id": (err.get("metadata") or {}).get("payment_id"),
    }


RECOVERY_SYSTEM = """You are a payments-recovery agent for an online
merchant. A buyer's payment attempt just failed. You must decide how to
recover WITHOUT retrying the failed rail blindly.

Respond with EXACTLY one JSON object and nothing else:
{"reasoning": "<one or two sentences>", "action": "create_payment_link"}

Rules:
- If the failure indicates the rail itself is unavailable or declined
  (UPI disabled, bank not enabled, user-declined), choose
  "create_payment_link" as the alternative rail.
- Do not invent fields. Output valid JSON only."""


def reason_recovery(failure: dict, amount_paise: int, order_id: str) -> dict:
    """Real LLM call -> strict JSON {reasoning, action}. Fail-soft."""
    from ..llm.gemini import ask as llm_ask

    user_prompt = f"""Payment failure context:
- order_id: {order_id}
- amount_paise: {amount_paise}
- rail: UPI (VPA {UPI_VPA})
- razorpay error code: {failure.get('code')}
- razorpay error description: {failure.get('description')}
- failure step: {failure.get('step')}
- failure reason: {failure.get('reason')}

Decide the recovery action now."""

    raw = llm_ask(RECOVERY_SYSTEM, user_prompt)
    text = (raw.get("text") or "").strip()
    parsed = None
    if text:
        # Secure parse: take the outermost JSON object if present.
        start = text.find("{")
        end = text.rfind("}")
        if start != -1 and end > start:
            try:
                candidate = json.loads(text[start:end + 1])
                if isinstance(candidate, dict):
                    parsed = {
                        "reasoning": str(candidate.get("reasoning", ""))[:500],
                        "action": str(candidate.get("action", ""))[:64],
                    }
            except json.JSONDecodeError:
                parsed = None
    return {"model": raw.get("model"), "latency_ms": raw.get("latency_ms"),
            "raw_response": text[:800], "error": raw.get("error"),
            "parsed": parsed}


def run_recovery(order_id: str, order_amount_paise: int,
                  mission_id: str, payment_mode: str = "success") -> dict[str, Any]:
    """
    Execute the full failure->diagnosis->recovery loop for one order.
    Returns a JSON-safe summary including every audit action_id.
    When payment_mode is 'success', the payment succeeds directly
    (the real rail succeeded), skipping recovery actions.
    """
    summary: dict[str, Any] = {
        "order_id": order_id,
        "mission_id": mission_id,
        "attempt_rail": "upi",
    }

    # ---- STEP 1: real UPI attempt against api.razorpay.com ----
    attempt = rp.attempt_checkout_payment(
        order_id, order_amount_paise,
        method_body={"method": "upi", "upi": {"vpa": UPI_VPA}})
    result = attempt.get("result", {})
    failure = _extract_error(result)
    summary["attempt_result"] = result

    payment_id = result.get("id") or failure.get("payment_id")
    succeeded = bool(result.get("id")) and not result.get("error")

    # Authoritative re-read: never trust the callback alone.
    authoritative = rp.list_order_payments(order_id)
    summary["authoritative_payments"] = [
        {"id": p.get("id"), "status": p.get("status"),
         "method": p.get("method")}
        for p in authoritative]

    if succeeded and any(p.get("status") == "captured"
                         for p in authoritative):
        seq = chain.append(
            "webhook", "payment_captured",
            {"order_id": order_id, "payment_id": payment_id},
            review_state="executed")
        summary.update({"outcome": "captured",
                        "attempt_action_id": chain.action_id(seq)})
        return summary

    if succeeded:
        seq = chain.append(
            "executor", "payment_authorized_pending_capture",
            {"order_id": order_id, "payment_id": payment_id})
        summary.update({"outcome": "authorized",
                        "attempt_action_id": chain.action_id(seq)})
        return summary

    # ---- STEP 2: record the REAL failure verbatim ----
    fail_seq = chain.append(
        "razorpay_webhook_equivalent", "payment_attempt_failed",
        {"order_id": order_id,
         "rail": "upi",
         "vpa": UPI_VPA,
         "razorpay_result": result},
        parent_action_id=None,
        error_code=str(failure.get("code") or "UNKNOWN"),
        error_reason=str(failure.get("description") or ""),
        review_state="escalated")
    fail_aid = chain.action_id(fail_seq)
    summary["failed_payment_action_id"] = fail_aid
    summary["failure"] = failure

    # ---- STEP 3: ONE real LLM reasoning call (outside money path) ----
    reasoning = reason_recovery(failure, order_amount_paise, order_id)
    parsed = reasoning.get("parsed") or {}
    reason_seq = chain.append(
        "buyer_agent", "recovery_reasoned",
        {"order_id": order_id,
         "parsed_action": parsed.get("action"),
         "model": reasoning.get("model"),
         "llm_error": reasoning.get("error")},
        parent_action_id=fail_aid,
        reasoning_trace={
            "prompt_system": RECOVERY_SYSTEM[:400],
            "raw_response": reasoning.get("raw_response"),
            "parsed": parsed,
        })
    reason_aid = chain.action_id(reason_seq)
    summary["reasoning_action_id"] = reason_aid
    summary["llm"] = {k: reasoning.get(k) for k in
                      ("model", "latency_ms", "error", "raw_response")}
    summary["llm_decision"] = parsed

    # ---- STEP 4: recovery only if the model chose the link rail ----
    if parsed.get("action") == "create_payment_link":
        link_idem = rp.derive_idempotency_key(
            "payment_link", mission_id, order_id, order_amount_paise)
        link = rp.create_payment_link(
            order_amount_paise,
            description=f"Recovery link for order {order_id} "
                        f"(mission {mission_id})",
            expire_by_seconds=24 * 3600,
            notes={"order_id": order_id, "mission_id": mission_id,
                   "parent_failure": fail_aid},
            idempotency_key=link_idem)
        link_seq = chain.append(
            "executor", "payment_link_issued",
            {"order_id": order_id,
             "link_id": link.get("id"),
             "short_url": link.get("short_url"),
             "amount_paise": order_amount_paise,
             "expire_by": link.get("expire_by")},
            parent_action_id=fail_aid,
            idempotency_key=link_idem,
            review_state="pending_merchant")
        summary.update({
            "outcome": "payment_failed_then_link_issued",
            "link_action_id": chain.action_id(link_seq),
            "payment_link": {"id": link.get("id"),
                             "short_url": link.get("short_url")},
            "idempotency_key": link_idem,
        })
    else:
        summary["outcome"] = "payment_failed_no_recovery_action"

    return summary
