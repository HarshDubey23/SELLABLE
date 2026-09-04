# Sample Signed Missions for SELLABLE

This document lists 5 sample signed missions ready for testing with the SELLABLE Policy Gateway.

## Regenerating Signatures

If `MISSION_HMAC_KEY` changes, regenerate signatures using this snippet:

```python
import json, os, time
from apps.api.gateway import mission_verify

def sign(mission_dict):
    blob = {k: v for k, v in mission_dict.items() if k != "signature"}
    return mission_verify.sign_mission(mission_verify.dumps(blob))
```

---

## 1. Cricket Gift — Under Budget (APPROVE)

**Intent:** Buy a Kashmir willow cricket bat within Rs 2,000 budget.

### Signed Mission JSON
```json
{
  "mission_id": "MSN-SMPL-001",
  "intent": "Cricket gift",
  "budget_paise": 200000,
  "allowed_categories": [
    "cricket"
  ],
  "forbidden_categories": [],
  "upsell_cap": 1.3,
  "expires_at": 1787540000,
  "signature": "69b6613892ad969ccf15ce92420132756b44ee133d7c1de180b949c22383656d"
}
```

### Curl Command
```bash
curl -X POST http://localhost:8000/tools/submit_proposal \
  -H "Content-Type: application/json" \
  -d '{
    "mission": {
      "mission_id": "MSN-SMPL-001",
      "intent": "Cricket gift",
      "budget_paise": 200000,
      "allowed_categories": ["cricket"],
      "forbidden_categories": [],
      "upsell_cap": 1.3,
      "expires_at": 1787540000,
      "signature": "69b6613892ad969ccf15ce92420132756b44ee133d7c1de180b949c22383656d"
    },
    "items": [{"sku": "BAT-001", "qty": 1}]
  }'
```

- **Expected Verdict:** `APPROVE`
- **Explanation:** `BAT-001` (149900 paise / Rs 1,499) is in category `cricket` and under the 200000 paise (Rs 2,000) budget.

---

## 2. Office Stationery — Over Budget (REJECT R1_BUDGET)

**Intent:** Buy notebooks and pens under Rs 500 budget.

### Signed Mission JSON
```json
{
  "mission_id": "MSN-SMPL-002",
  "intent": "Office stationery",
  "budget_paise": 50000,
  "allowed_categories": [
    "stationery"
  ],
  "forbidden_categories": [],
  "upsell_cap": 1.3,
  "expires_at": 1787540000,
  "signature": "7b9cc946744ea467c9d84b97a34df4a5f55c864e435e4efe9137af1ee4a50d60"
}
```

### Curl Command
```bash
curl -X POST http://localhost:8000/tools/submit_proposal \
  -H "Content-Type: application/json" \
  -d '{
    "mission": {
      "mission_id": "MSN-SMPL-002",
      "intent": "Office stationery",
      "budget_paise": 50000,
      "allowed_categories": ["stationery"],
      "forbidden_categories": [],
      "upsell_cap": 1.3,
      "expires_at": 1787540000,
      "signature": "7b9cc946744ea467c9d84b97a34df4a5f55c864e435e4efe9137af1ee4a50d60"
    },
    "items": [{"sku": "BAGP-001", "qty": 1}]
  }'
```

- **Expected Verdict:** `REJECT` (`R1_BUDGET`)
- **Explanation:** `BAGP-001` (99900 paise / Rs 999) exceeds the Rs 500 budget (50000 paise).

---

## 3. Grocery Essentials — Category Scope Check (APPROVE)

**Intent:** Buy grocery essentials under Rs 1,500 budget.

### Signed Mission JSON
```json
{
  "mission_id": "MSN-SMPL-003",
  "intent": "Grocery essentials",
  "budget_paise": 150000,
  "allowed_categories": [
    "groceries"
  ],
  "forbidden_categories": [],
  "upsell_cap": 1.3,
  "expires_at": 1787540000,
  "signature": "870663dcf6fbad20a7b71ae17652c8fef4a062ec6049df60e1997f8cd20875b6"
}
```

### Curl Command
```bash
curl -X POST http://localhost:8000/tools/submit_proposal \
  -H "Content-Type: application/json" \
  -d '{
    "mission": {
      "mission_id": "MSN-SMPL-003",
      "intent": "Grocery essentials",
      "budget_paise": 150000,
      "allowed_categories": ["groceries"],
      "forbidden_categories": [],
      "upsell_cap": 1.3,
      "expires_at": 1787540000,
      "signature": "870663dcf6fbad20a7b71ae17652c8fef4a062ec6049df60e1997f8cd20875b6"
    },
    "items": [{"sku": "RICE-001", "qty": 1}, {"sku": "OIL-001", "qty": 1}]
  }'
```

- **Expected Verdict:** `APPROVE`
- **Explanation:** Total 89800 paise (Rs 898) is within `groceries` category scope and under Rs 1,500 budget.

---

## 4. Electronics Splurge — Out of Scope Item (REJECT R5_SCOPE)

**Intent:** Buy electronics under Rs 5,000 budget.

### Signed Mission JSON
```json
{
  "mission_id": "MSN-SMPL-004",
  "intent": "Electronics splurge",
  "budget_paise": 500000,
  "allowed_categories": [
    "electronics"
  ],
  "forbidden_categories": [],
  "upsell_cap": 1.3,
  "expires_at": 1787540000,
  "signature": "16ea273e304d86154750477022fdfca7edcb1e7bd658951ee228afbf0aa29e4e"
}
```

### Curl Command
```bash
curl -X POST http://localhost:8000/tools/submit_proposal \
  -H "Content-Type: application/json" \
  -d '{
    "mission": {
      "mission_id": "MSN-SMPL-004",
      "intent": "Electronics splurge",
      "budget_paise": 500000,
      "allowed_categories": ["electronics"],
      "forbidden_categories": [],
      "upsell_cap": 1.3,
      "expires_at": 1787540000,
      "signature": "16ea273e304d86154750477022fdfca7edcb1e7bd658951ee228afbf0aa29e4e"
    },
    "items": [{"sku": "TSH-001", "qty": 1}]
  }'
```

- **Expected Verdict:** `REJECT` (`R5_SCOPE`)
- **Explanation:** `TSH-001` is category `apparel` which is outside allowed category scope `electronics`.

---

## 5. Cricket Gear Upsell — Upsell Cap Check (APPROVE)

**Intent:** Buy cricket gear under Rs 3,000 budget with 1.5x upsell cap (max cap Rs 4,500).

### Signed Mission JSON
```json
{
  "mission_id": "MSN-SMPL-005",
  "intent": "Cricket gear upsell",
  "budget_paise": 300000,
  "allowed_categories": [
    "cricket"
  ],
  "forbidden_categories": [],
  "upsell_cap": 1.5,
  "expires_at": 1787540000,
  "signature": "d0b2a14458b9449eeb3d7b8ce0482889baf35b0c7424fbd7686001f96141361a"
}
```

### Curl Command
```bash
curl -X POST http://localhost:8000/tools/submit_proposal \
  -H "Content-Type: application/json" \
  -d '{
    "mission": {
      "mission_id": "MSN-SMPL-005",
      "intent": "Cricket gear upsell",
      "budget_paise": 300000,
      "allowed_categories": ["cricket"],
      "forbidden_categories": [],
      "upsell_cap": 1.5,
      "expires_at": 1787540000,
      "signature": "d0b2a14458b9449eeb3d7b8ce0482889baf35b0c7424fbd7686001f96141361a"
    },
    "items": [{"sku": "BAT-002", "qty": 1}, {"sku": "PAD-001", "qty": 1}]
  }'
```

- **Expected Verdict:** `APPROVE`
- **Explanation:** Total 349800 paise (Rs 3,498) exceeds base budget Rs 3,000 but stays under the 1.5x upsell cap of Rs 4,500 (450000 paise).
