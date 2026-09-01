#!/usr/bin/env bash
set -euo pipefail

# SELLABLE smoke test — Phase 9.
# Usage: bash scripts/smoke_test.sh [base_url]
# Requires APP_API_KEY in environment.

BASE="${1:-${SELLABLE_BASE_URL:-http://localhost:8000}}"
PASS=0
FAIL=0

pass() { echo "  PASS: $1"; PASS=$((PASS+1)); }
fail() { echo "  FAIL: $1 ($2)"; FAIL=$((FAIL+1)); }

# 1. Health
R=$(curl -s -o /dev/null -w "%{http_code}" "$BASE/health")
if [ "$R" = "200" ]; then pass "Health 200"; else fail "Health" "http=$R"; fi

# 2. Audit chain verified
C=$(curl -s "$BASE/health")
if echo "$C" | grep -q '"audit_chain_ok":true'; then pass "Audit chain verified"; else fail "Audit chain" "body=$C"; fi

# 3. Gateway proof (0 LLM, 0 I/O)
P=$(curl -s "$BASE/gateway/proof")
if echo "$P" | grep -q '"llm_imports_detected":0' && echo "$P" | grep -q '"io_calls_detected":0'; then
  pass "Gateway proof (0 LLM, 0 I/O)"
else
  fail "Gateway proof" "body=$P"
fi

# 4. Policy rules_count == 12
N=$(curl -s "$BASE/policy" | python -c "import sys,json; print(json.load(sys.stdin).get('rules_count',0))" 2>/dev/null)
if [ "$N" = "12" ]; then pass "12 gateway rules (R1-R12)"; else fail "Rules count" "count=$N"; fi

# 5. Catalog 40 SKUs
SK=$(curl -s "$BASE/tools/search_products?query=cricket" | python -c "import sys,json; print(json.load(sys.stdin).get('count',0))" 2>/dev/null)
if [ "$SK" -ge "1" ]; then pass "Catalog search works"; else fail "Catalog search" "count=$SK"; fi

# 6. Injection I1 visible (by design)
I=$(curl -s "$BASE/tools/get_product/KIT-001")
if echo "$I" | grep -q "IGNORE ALL PREVIOUS"; then pass "I1 injection visible (by design)"; else fail "I1 injection" "not found"; fi

# 7. Quote — server-computed, signed
Q=$(curl -s -X POST "$BASE/tools/quote" \
  -H "Content-Type: application/json" \
  -H "X-API-Key: ${APP_API_KEY:?APP_API_KEY not set}" \
  -d '{"items":[{"sku":"BAT-001","qty":1}],"mission_id":"smoke"}')
if echo "$Q" | grep -q '"total_paise"'; then pass "Quote server-computed"; else fail "Quote" "body=$Q"; fi

# 8. Demo injection endpoint
D=$(curl -s "$BASE/demo/injection/I1")
if echo "$D" | grep -q '"mission_id"'; then pass "Demo injection endpoint"; else fail "Demo injection" "body=$D"; fi

echo "==== smoke_test: $PASS passed, $FAIL failed ===="
[ "$FAIL" -eq 0 ]