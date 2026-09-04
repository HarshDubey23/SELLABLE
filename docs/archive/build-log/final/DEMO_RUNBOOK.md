# SELLABLE — Live Demo Runbook

### Quick Start Commands
```bash
# 1. Start the server
python -m uvicorn apps.api.main:app --port 8000

# 2. Run the strict verification suite
python scripts/final_verify.py --strict

# 3. Open UI in browser
http://localhost:8000/
```

### Scenario Execution Matrix
| Scenario | CLI Demo Command | Expected Outcome |
|---|---|---|
| **Happy Path** | `python scripts/final_demo.py --scenario happy-path` | Autonomous purchase -> Approval -> Razorpay Order Created |
| **Prompt Injection** | `python scripts/final_demo.py --scenario prompt-injection` | Attack detected -> Gateway REJECT -> 0 Money Calls |
| **Budget Attack** | `python scripts/final_demo.py --scenario budget-attack` | Overbudget SKU proposed -> R1 FAIL -> 0 Money Calls |
| **Cart Mutation** | `python scripts/final_demo.py --scenario cart-mutation` | Price altered post-approval -> Binding Mismatch -> Blocked |
| **Replay Attack** | `python scripts/final_demo.py --scenario replay` | Duplicate order execution -> Binding Already Consumed |
| **Payment Failure** | `python scripts/final_demo.py --scenario payment-failure` | Simulated payment fail -> Bounded recovery -> Audited |
| **Audit Tamper** | `python scripts/final_demo.py --scenario audit-tamper` | DB row altered -> Genesis hash check detects corruption |
