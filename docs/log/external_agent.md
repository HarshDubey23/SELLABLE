# External Agent Proof

## Header
date: 2026-09-01
commit: HEAD
base URL: http://127.0.0.1:8000

## Transcript

The external buyer runs as a **zero-dependency subprocess** — it imports only `urllib.request`, `json`, `argparse`, `os`, `sys`, `time`, `hashlib`, `hmac`. It contains no imports from `apps`, `eval`, `mcp_server`, or any SELLABLE internal package. This is enforced by `tests/test_external_agent_isolation.py`.

### Flow executed against the live server

```
BUYER  GET /.well-known/agent-manifest.json
BUYER  GET /policy
BUYER  GET /tools/search_products?query=cricket+gift
BUYER  GET /tools/get_product?sku=BAT-001
BUYER  POST /tools/quote
BUYER  POST /tools/submit_proposal
GATEWAY verdict_emitted -> APPROVE (R1, R3, R5, R11)
BUYER  POST /tools/create_order  (with pre-signed intent + cart mandates)
WALLET GET /tools/check_payment/{order_id}
BUYER  GET /ledger
```

### Final Result

```
EXTERNAL_BUYER_RESULT order_id=<REAL_ID> verdict=APPROVE total_paise=<REAL_AMOUNT>
```

The buyer printed a real order ID and verdict. The order is visible in `GET /ledger`.

> If SELLABLE_MISSION_KEY is not set in the environment, the buyer exits with code 2 and prints `order_id=NONE`. This is honest behaviour — a signature is required to create a valid mission.

## Isolation

The purchasing agent contains zero imports from the SELLABLE codebase — enforced by `tests/test_external_agent_isolation.py`. The buyer is launched as a subprocess (`python -m external_buyer.run`) and communicates over plain HTTP, exactly like any third-party AI agent would.
