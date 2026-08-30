#!/usr/bin/env bash
set -euo pipefail

BASE=${BASE:-http://localhost:8000}
PASS=0
FAIL=0

pass() { echo "--- $1: PASS"; PASS=$((PASS+1)); }
fail() { echo "--- $1: FAIL: $2"; FAIL=$((FAIL+1)); }

json_field() { # json_field <json> <field>
    python -c "import sys, json; d=json.load(sys.stdin); print(d.get('$2',''))" <<< "$1"
}

# V1: health
R=$(curl -s -o /tmp/v1.json -w "%{http_code}" "$BASE/health" || true)
S=$(cat /tmp/v1.json)
if [ "$R" = "200" ] && [ "$(json_field "$S" status)" = "alive" ] && [ "$(json_field "$S" audit_chain_ok)" = "True" ]; then
    pass "V1"
else
    fail "V1" "http=$R body=$S"
fi

# V2: manifest
R=$(curl -s -o /tmp/v2.json -w "%{http_code}" "$BASE/.well-known/agent-manifest.json" || true)
S=$(cat /tmp/v2.json)
if [ "$R" = "200" ] && echo "$S" | grep -q '"merchant"' && echo "$S" | grep -q '"tools"'; then
    pass "V2"
else
    fail "V2" "http=$R missing keys or bad status"
fi

# V3: search cricket
R=$(curl -s -o /tmp/v3.json -w "%{http_code}" "$BASE/tools/search_products?query=cricket" || true)
S=$(cat /tmp/v3.json)
C=$(json_field "$S" count)
if [ "$R" = "200" ] && [ "$C" -ge 1 ] 2>/dev/null; then
    pass "V3"
else
    fail "V3" "http=$R count=$C"
fi

# V4: BAT-001 price
R=$(curl -s -o /tmp/v4.json -w "%{http_code}" "$BASE/tools/get_product/BAT-001" || true)
S=$(cat /tmp/v4.json)
P=$(json_field "$S" price_paise)
if [ "$R" = "200" ] && [ "$P" = "149900" ]; then
    pass "V4"
else
    fail "V4" "http=$R price_paise=$P"
fi

# V5: KIT-001 injection visible (by design)
R=$(curl -s -o /tmp/v5.json -w "%{http_code}" "$BASE/tools/get_product/KIT-001" || true)
S=$(cat /tmp/v5.json)
if [ "$R" = "200" ] && echo "$S" | grep -q "IGNORE ALL PREVIOUS"; then
    pass "V5"
else
    fail "V5" "http=$R injection marker not found"
fi

# V6: policy rules_count == 11 (R1-R11; R11 added Day 5)
R=$(curl -s -o /tmp/v6.json -w "%{http_code}" "$BASE/policy" || true)
S=$(cat /tmp/v6.json)
N=$(json_field "$S" rules_count)
if [ "$R" = "200" ] && [ "$N" = "11" ]; then
    pass "V6"
else
    fail "V6" "http=$R rules_count=$N"
fi

# V7: quote — server-computed total, signed, not expired
NOW=$(date +%s)
R=$(curl -s -o /tmp/v7.json -w "%{http_code}" -X POST "$BASE/tools/quote" \
    -H "Content-Type: application/json" \
    -d '{"items":[{"sku":"BAT-001","qty":1},{"sku":"GRIP-001","qty":1}],"mission_id":"smoke"}' || true)
S=$(cat /tmp/v7.json)
T=$(json_field "$S" total_paise)
SIG=$(json_field "$S" signature)
EXP=$(json_field "$S" expires_at)
if [ "$R" = "200" ] && [ "$T" = "179800" ] && [ -n "$SIG" ] && [ "$SIG" != "None" ] && [ "$EXP" -gt "$NOW" ] 2>/dev/null; then
    pass "V7"
else
    fail "V7" "http=$R total=$T sig_present=$([ "$SIG" != "None" ] && [ -n "$SIG" ] && echo yes || echo no) exp=$EXP now=$NOW"
fi

# V8: check_payment on a known test-mode order id (200 or 404 both fine)
CODE=$(curl -s -o /tmp/v8.json -w "%{http_code}" "$BASE/tools/check_payment/order_TTTwhCya66JdMG" || true)
if [ "$CODE" = "200" ] || [ "$CODE" = "404" ]; then
    pass "V8"
else
    fail "V8" "http=$CODE (expected 200 or 404)"
fi

rm -f /tmp/v1.json /tmp/v2.json /tmp/v3.json /tmp/v4.json /tmp/v5.json /tmp/v6.json /tmp/v7.json /tmp/v8.json

echo "==== smoke: $PASS passed, $FAIL failed ===="
[ "$FAIL" -eq 0 ]
