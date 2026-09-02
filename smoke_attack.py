import sys, os, json
sys.path.insert(0, r'C:\Users\Lenovo\Downloads\SELLABLE')
os.environ['APP_API_KEY'] = 'test-key'
os.environ['MISSION_HMAC_KEY'] = 'test-hmac'
from apps.api import attack
res = attack.attack_run_all()
print('Scenarios total:', res['scenarios_total'])
print('Scenarios blocked:', res['scenarios_blocked'])
print('Block rate:', res['block_rate'])
print()
for r in res['results']:
    print(f"{r['id']:30s}  decision={r['decision']:6s}  rule={r['rule_id'] or '-':25s}  money_calls={r['money_calls']}  safe={r['safe']}")