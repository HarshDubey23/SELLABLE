"""Zero-dependency SELLABLE buyer client. Python stdlib only.

    python -m external_buyer.run --base http://127.0.0.1:8000 \
        --mission missions/happy_path.json \
        --out docs/submission/evidence/external_buyer_transcript.json
"""
from __future__ import annotations

import argparse
import hashlib
import hmac
import json
import os
import sys
import time
import urllib.error
import urllib.request

T: list[dict] = []


def log(actor: str, event: str, detail: str = "") -> None:
    T.append({"n": len(T) + 1, "actor": actor, "event": event, "detail": detail})
    line = f"{len(T):>3}  {actor:<10} {event}"
    if detail:
        line += f"  -- {detail}"
    print(line.encode("ascii", "replace").decode()[:160])


def _canonicalize(mission: dict) -> str:
    payload = {k: v for k, v in mission.items() if k != "signature"}
    return json.dumps(payload, sort_keys=True, separators=(",", ":"))


def _sign(mission: dict, key: bytes) -> dict:
    canon = _canonicalize(mission)
    out = dict(mission)
    if "signature" in out:
        del out["signature"]
    out["signature"] = hmac.new(key, canon.encode(), hashlib.sha256).hexdigest()
    return out


class ApiResponse:
    def __init__(self, status: int, body: object, text: str) -> None:
        self.status, self.body, self.text = status, body, text


class BuyerClient:
    def __init__(self, base: str, api_key: str | None = None,
                 timeout: float = 10.0) -> None:
        self.base = base.rstrip("/")
        self.headers = {"Content-Type": "application/json"}
        if api_key:
            self.headers["X-API-Key"] = api_key
        self.timeout = timeout

    def get(self, path: str) -> ApiResponse:
        req = urllib.request.Request(self.base + path, headers=self.headers)
        return self._send(req)

    def post(self, path: str, payload: object) -> ApiResponse:
        data = payload if isinstance(payload, str) else json.dumps(payload or {})
        req = urllib.request.Request(
            self.base + path, data=data.encode("utf-8"),
            headers=self.headers, method="POST")
        return self._send(req)

    def _send(self, req: urllib.request.Request) -> ApiResponse:
        try:
            with urllib.request.urlopen(req, timeout=self.timeout) as resp:
                text = resp.read().decode("utf-8", errors="replace")
                return ApiResponse(resp.status, _safe_json(text), text)
        except urllib.error.HTTPError as e:
            text = e.read().decode("utf-8", errors="replace")
            return ApiResponse(e.code, _safe_json(text), text)
        except Exception as e:
            return ApiResponse(0, {"error": str(e)}, str(e))


def _safe_json(text: str) -> object:
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        return text


def _find_mission_file(mission_arg: str) -> str:
    if os.path.exists(mission_arg):
        return mission_arg
    root = os.path.abspath(os.path.join(
        os.path.dirname(__file__), "..", ".."))
    for candidate in [mission_arg,
                       os.path.join(root, mission_arg),
                       os.path.join(root, "missions", mission_arg)]:
        if os.path.exists(candidate):
            return candidate
    raise SystemExit(f"mission file not found: {mission_arg}")


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--base", required=True)
    ap.add_argument("--mission", required=True)
    ap.add_argument("--api-key", default=os.environ.get("APP_API_KEY"))
    ap.add_argument("--out", default="")
    args = ap.parse_args()
    c = BuyerClient(args.base, api_key=args.api_key)

    # 1. discovery
    log("buyer", "manifest_fetched", "GET /.well-known/agent-manifest.json")
    man = c.get("/.well-known/agent-manifest.json")
    log("merchant", "manifest",
        str(man.body)[:120] if man.body else f"HTTP {man.status}")

    pol = c.get("/policy")
    rules = pol.body.get("rules", []) if isinstance(pol.body, dict) else []
    log("buyer", "policy_read", f"{len(rules)} deterministic rules discovered")

    # 2. mission (never fake a signature)
    mission_path = _find_mission_file(args.mission)
    with open(mission_path, "r", encoding="utf-8") as f:
        mission = json.load(f)
    key = os.environ.get("MISSION_HMAC_KEY", "").encode()
    if not key:
        log("buyer", "abort", "MISSION_HMAC_KEY not set — cannot sign mission")
        return 2
    mission = _sign(mission, key)
    log("buyer", "mission_loaded", f"budget {mission.get('budget_paise')}p")

    # 3. server-truth prices via search + get_product
    items = mission.get("items") or mission.get("cart") or []
    truth: dict[str, int] = {}

    if not items:
        intent = mission.get("intent", "")
        log("buyer", "tool_call:search_products", f"query={intent}")
        r = c.get("/tools/search_products?query=" + urllib.request.quote(intent))
        results = (r.body or {}).get("results", []) if isinstance(r.body, dict) else []
        for it in results[:3]:
            sku = it.get("sku", "")
            prod = it
            if not prod.get("price_paise"):
                gr = c.get("/tools/get_product/" + urllib.request.quote(sku))
                prod = (gr.body or {}).get("product", gr.body) or {}
            truth[sku] = int(prod.get("price_paise", 0))
            log("merchant", "tool_result:get_product",
                f"{sku} truth {truth[sku]}p")
        items = [{"sku": s, "qty": 1} for s in truth]
    else:
        for it in items:
            gr = c.get("/tools/get_product/" + urllib.request.quote(str(it.get("sku", ""))))
            prod = (gr.body or {}).get("product", gr.body) or {}
            truth[it["sku"]] = int(prod.get("price_paise", it.get("price_paise", 0)))
            log("merchant", "tool_result:get_product",
                f"{it['sku']} truth {truth[it['sku']]}p")

    total = sum(truth.get(s.get("sku", ""), 0) * int(s.get("qty", 1))
                for s in items)
    log("buyer", "truth_total", f"{total} paise")

    # 4. quote
    log("buyer", "tool_call:quote", f"mission {mission.get('mission_id')}")
    qr = c.post("/tools/quote", {"items": items,
                                 "mission_id": mission.get("mission_id")})
    quote = qr.body or {}
    quote_id = quote.get("quote_id", "")
    total_paise = quote.get("total_paise", total)
    log("merchant", "quote", f"{quote_id} total {total_paise}p")

    # 5. propose -> verdict
    proposal = {"mission": mission, "items": items}
    log("buyer", "tool_call:submit_proposal", f"total {total_paise}p")
    r = c.post("/tools/submit_proposal", proposal)
    verdict = r.body or {}
    decision = str((verdict.get("data") or {}).get("decision",
                         verdict.get("decision", ""))).upper()
    rule_id = (verdict.get("data") or {}).get("rule_id", "")
    seq = verdict.get("seq", "")
    proposal_hash = (verdict.get("data") or {}).get("proposal_hash", "")
    log("gateway", "verdict", f"{decision} {rule_id} seq={seq}")

    if decision != "APPROVE":
        log("buyer", "abort", f"gateway {decision}: {rule_id}")
        print(f"EXTERNAL_BUYER_RESULT order_id=NONE verdict={decision} "
              f"total_paise={total_paise} rule={rule_id}")
        if args.out:
            os.makedirs(os.path.dirname(args.out) or ".", exist_ok=True)
            with open(args.out, "w", encoding="utf-8") as f:
                json.dump({"base": args.base,
                           "generated_at_utc": time.strftime(
                               "%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
                           "transcript": T}, f, indent=2)
        return 3

    # 6. create order (requires pre-signed intent + cart mandates)
    log("buyer", "tool_call:create_order", f"approve_seq {seq}")
    intent_mandate = None
    cart_mandate = None
    root = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
    missions_dir = os.path.join(root, "missions")
    mid = mission.get("mission_id", "")
    intent_path = os.path.join(missions_dir, f"{mid}_intent_mandate.json")
    cart_path = os.path.join(missions_dir, f"{mid}_cart_mandate.json")
    if os.path.exists(intent_path):
        intent_mandate = json.load(open(intent_path, encoding="utf-8"))
    if os.path.exists(cart_path):
        cart_mandate = json.load(open(cart_path, encoding="utf-8"))

    order_body = {"quote_id": quote_id, "proposal_hash": proposal_hash,
                  "approve_seq": seq}
    if intent_mandate:
        order_body["intent_mandate"] = intent_mandate
    if cart_mandate:
        order_body["cart_mandate"] = cart_mandate

    order = c.post("/tools/create_order", order_body)
    order_body_resp = order.body or {}
    order_id = (order_body_resp.get("order_id")
                or (order_body_resp.get("order") or {}).get("id") or "")
    amount_paise = order_body_resp.get("amount_paise", total_paise)
    log("merchant", "order", json.dumps(order_body_resp)[:140])

    # 7. bounded payment poll
    if order_id:
        for _ in range(10):
            pay = c.get(f"/tools/check_payment/{order_id}")
            st = json.dumps(pay.body or {})
            log("wallet", "check_payment", st[:120])
            if "completed" in st or "payment_link" in st or "captured" in st:
                break
            time.sleep(0.5)

    led = c.get("/ledger")
    n = len((led.body or {}).get("entries", [])) if isinstance(led.body, dict) else 0
    log("buyer", "ledger_check", f"HTTP {led.status}, {n} entries visible")

    print(f"EXTERNAL_BUYER_RESULT order_id={order_id} verdict={decision} "
          f"total_paise={total_paise}")

    if args.out:
        os.makedirs(os.path.dirname(args.out) or ".", exist_ok=True)
        with open(args.out, "w", encoding="utf-8") as f:
            json.dump({"base": args.base,
                       "generated_at_utc": time.strftime(
                           "%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
                       "transcript": T}, f, indent=2)
        log("buyer", "transcript_written", args.out)
    return 0


if __name__ == "__main__":
    sys.exit(main())