"""Live end-to-end demo against the running server."""
import httpx, sys, time, json
sys.path.insert(0, r'C:\Users\Lenovo\Downloads\SELLABLE')
from apps.api.gateway import mission_verify
from apps.api.mandates.mandates import IntentMandate, CartMandate, sign_intent, sign_cart

base = 'http://127.0.0.1:8000'
H = {'X-API-Key': 'sellable_demo_key_4f7e9c2a8b1d3e6f'}
USER_KEY = '13f81275b54466008321a7527678ba36f86e00445307ef3501480e7683cffcc0'

print('=' * 60)
print('SELLABLE LIVE GOLDEN PATH')
print('=' * 60)

# Step 1: search
r = httpx.get(base + '/tools/search_products',
              params={'query': 'cricket bat', 'limit': 5})
results = r.json()['results']
print()
print('1. SEARCH')
print(f"   status={r.status_code}  results={len(results)}")
for p in results[:3]:
    print(f"   - {p['sku']:10s} Rs {p['price_paise']/100:>7,.0f}  {p['name']}")

# Step 2: submit_proposal
now = int(time.time())
blob = {'mission_id': 'MSN-LIVE-DEMO', 'intent': 'buy cricket bat',
        'budget_paise': 200000, 'allowed_categories': ['cricket'],
        'forbidden_categories': [], 'upsell_cap': 1.3,
        'expires_at': now + 600}
sig = mission_verify.sign_mission(mission_verify.dumps(blob))
blob['signature'] = sig

r = httpx.post(base + '/tools/submit_proposal',
               json={'mission': blob, 'items': [{'sku': 'BAT-001', 'qty': 1}]},
               headers=H)
d = r.json()['data']
print()
print('2. GATEWAY VERDICT')
print(f"   decision: {d['decision']}")
print(f"   reason:   {d['reason']}")
print(f"   rules:    {len(d['rule_matrix'])} checked")
for rule in d['rule_matrix']:
    mark = 'PASS' if rule['status'] == 'PASS' else 'FAIL'
    print(f"     {rule['rule_id']:30s} {mark}")

# Step 3: quote
r = httpx.post(base + '/tools/quote',
               json={'items': [{'sku': 'BAT-001', 'qty': 1}],
                     'mission_id': 'MSN-LIVE-DEMO'}, headers=H)
q = r.json()
print()
print('3. QUOTE')
print(f"   quote_id: {q['quote_id']}")
print(f"   total:    Rs {q['total_paise']/100:,.0f}")

# Step 4: mandates
intent = sign_intent(IntentMandate(
    mission_id='MSN-LIVE-DEMO', user_id='demo_user',
    ceiling_paise=q['total_paise'], expires_at=int(time.time()) + 3600),
    USER_KEY)
cart = sign_cart(CartMandate(
    mission_id='MSN-LIVE-DEMO', cart_hash=d['proposal_hash'],
    amount_paise=q['total_paise'], signed_at=int(time.time())),
    USER_KEY)
print()
print('4. MANDATES')
print(f"   intent: signature={intent['sig'][:16]}...")
print(f"   cart:   signature={cart['sig'][:16]}...")

# Step 5: create_order (real Razorpay)
seq_resp = httpx.get(base + '/audit').json()['entries'][-1]['seq']
r = httpx.post(base + '/tools/create_order',
               json={'quote_id': q['quote_id'], 'proposal_hash': d['proposal_hash'],
                     'approve_seq': seq_resp,
                     'intent_mandate': intent, 'cart_mandate': cart},
               headers={**H, 'X-Idempotency-Key': 'live-demo-1'})
print()
print('5. RAZORPAY ORDER')
print(f"   status: {r.status_code}")
if r.status_code == 200:
    o = r.json()
    print(f"   order_id: {o['order_id']}")
    print(f"   amount:   {o.get('amount_display', '')}")
    print(f"   state:    {o['status']}")
else:
    print(f"   body: {r.text[:200]}")

# Attack lab
print()
print('=' * 60)
print('ATTACK LAB')
print('=' * 60)
r = httpx.post(base + '/attack/run_all', timeout=30)
data = r.json()
print()
print(f"  Scenarios: {data['scenarios_total']}, blocked: {data['scenarios_blocked']}")
print(f"  Block rate: {data['block_rate']}")
for atk in data['results']:
    mark = 'BLOCKED' if atk['safe'] else 'NOT BLOCKED'
    print(f"   {atk['id']:30s} {atk['decision']:6s}  rule={atk['rule_id'] or '-':25s} money={atk['money_calls']}  {mark}")

# Money-call invariant
print()
print('=' * 60)
print('MONEY-CALL INVARIANT')
print('=' * 60)
r = httpx.get(base + '/invariant/money-calls')
inv = r.json()
print()
print(f"  invariant: {inv['invariant']}")
print(f"  boundary_calls: {inv['money_calls']['boundary_calls']}")
print(f"  total events: {inv['money_calls']['total']}")
print(f"  by_operation: {json.dumps(inv['money_calls']['by_operation'])}")

# Status snapshot
print()
print('=' * 60)
print('STATUS')
print('=' * 60)
r = httpx.get(base + '/status')
s = r.json()
print()
print(f"  system_risk: {s['system_risk']}")
print(f"  policy_gateway: {s['policy_gateway']['rules_count']} rules, "
      f"{s['policy_gateway']['approvals_total']} approve, "
      f"{s['policy_gateway']['rejections_total']} reject")
print(f"  audit_chain: {s['audit_chain']['entries']} entries, "
      f"healthy={s['audit_chain']['healthy']}")
print(f"  razorpay: mode={s['razorpay']['mode']}")
print(f"  llm: configured={s['llm']['configured']}, model={s['llm']['model']}")
print(f"  catalog: {s['catalog']['sku_count']} SKUs")