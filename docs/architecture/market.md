# The market: three merchants who cannot name a price

Three language models compete for one shopper's order. They have real
strategies, they behave differently because of them, and none of them can
tell you what anything costs.

That last part is not a rule someone remembered to enforce. It is a
property of the schema they write in.

---

## The load-bearing invariant

A merchant answers with an `OfferIntent`:

```python
merchant_id          basket_sku_set       line_discount_pct
bundle_discount_pct  shipping             delivery_days
addon_skus           warranty_years       round
in_reply_to          offer_id             rationale
```

There is no amount field. There is no price field, no total, no paise,
no rupees. The model is choosing *terms*, and the server decides what
those terms cost.

This is enforced three ways, and the third is the one that matters:

1. **Pydantic** with `extra="forbid"` — an offer carrying an extra field
   is rejected at parse time, before anything reads it.
2. **A source-parsing test** walks the AST of `intents.py` and fails if
   any field name contains `amount`, `price`, `paise`, `total`, `rupee`,
   `inr`, `cost`, `fee`, `charge`, `payable` or `sum`.
3. **`docs/generated/truth.json`** records the live field list and, in
   `offer_intent_money_shaped_fields`, anything money-shaped it found.
   It is currently `[]`. If somebody adds a price field, that array fills
   in and the published claim contradicts itself in public.

A prompt-injected model that decides to grant a 90% discount has nowhere
to write it down.

---

## The layers, and what each one is allowed to decide

```
  the shopper's sentence
          │
          ▼
   buyer planner (LLM)      may choose:  which SKUs, what the priorities are
          │                 may NOT:     what anything costs
          │                 the ceiling comes from a regex, not the model
          ▼
   signed mission            budget bound the gateway later enforces
          │
          ▼
   3 merchant agents (LLM)  may choose:  discounts, delivery, warranty, addons
   concurrently             may NOT:     an amount — no field exists
          │                 may NOT see: any rival's terms, quotes or identity
          ▼
   MerchantPolicyEngine     pure. no LLM, no network, no clock, no DB.
          │                 signed manifest + catalog + intent -> total | refusal
          │                 NEVER clamps. an illegal offer is refused.
          ▼
   scorer                   pure integer arithmetic over the offers on the table
          │                 the LLM never picks the winner
          ▼
   accept                   conditional UPDATE. exactly once under any concurrency.
          │
          ▼
   settlement               recompute · re-hash · re-approve
          │
          ▼
   R1–R12 gateway ─ approval binding ─ execution machine ─ Razorpay
          (all pre-existing, unmodified, shared with every other purchase)
```

Three models argued for three rounds and the only thing they were ever
able to influence was which row of a catalog got looked up.

---

## Why nothing is clamped

A system that silently corrects an illegal offer behaves identically
whether its merchants are honest or not — which means nobody ever
discovers that one is not.

So `line_discount_pct: 15` against an 8% cap does not become 8. It
becomes `MERCHANT_POLICY_LINE_DISCOUNT_EXCEEDED`, an audit row, and a
verdict whose `total_paise` is `None`, because a refused offer has no
price. You can see this yourself: **Try an illegal offer** in the market
scene sends one through the real engine against the real signed manifest.

Every refusal names its own limit:

| reason | what it means |
| --- | --- |
| `MANIFEST_SIGNATURE_INVALID` | the manifest was edited underneath the engine |
| `LINE_DISCOUNT_EXCEEDED` | above this merchant's own line cap |
| `BUNDLE_DISCOUNT_EXCEEDED` | above this merchant's own bundle cap |
| `BUNDLE_NOT_EARNED` | fewer items than the bundle requires |
| `FREE_SHIPPING_NOT_EARNED` | basket below the free-shipping threshold |
| `DELIVERY_TOO_FAST` / `TOO_SLOW` | outside declared delivery capacity |
| `WARRANTY_NOT_OFFERED` | a term this merchant does not sell |
| `MARGIN_VIOLATION` | the deal falls below cost + minimum margin |
| `UNKNOWN_SKU` / `SKU_NOT_ELIGIBLE` | not in the catalog, or not for this merchant |

The caps and the margin floor are independent and neither is redundant.
Each merchant can reach its own headline discount — a cap nobody can use
is marketing, not a limit — and stacking both levers at their caps
breaches every merchant's margin floor. Caps bound each lever; the floor
bounds the deal.

---

## Isolation

No merchant sees another's terms, quotes, margins or identity. The buyer
brokers every disclosure and logs it.

This is not a promise about prompt-writing discipline. A test builds the
prompt each merchant would actually receive and fails if it contains any
other merchant's id or display name anywhere. A counter is checked the
same way: it reaches its addressee and nobody else.

---

## Durability

The negotiation is a state machine on SQLite, modelled on the execution
machine already sitting in front of Razorpay, for the same reason that
one exists.

```
OPEN → AWAITING_OFFERS → ROUND_COMPLETE → COUNTER_ISSUED → ...
                              │
                              └→ ACCEPTED | EXPIRED | FAILED
```

- **`offer_id` is a PRIMARY KEY**, derived from
  `sha256(negotiation, merchant, round)`. Replaying a round produces the
  same id and the insert is refused, so a merchant cannot bid twice and a
  replayed request cannot manufacture a second offer.
- **Accept is a conditional UPDATE** carrying `WHERE state =
  'ROUND_COMPLETE'`. Twenty racing accepts produce one winner and
  nineteen refusals.
- **A crash mid-round recovers to FAILED**, not to a phantom round. We
  do not know which merchants replied, so we do not pretend to. A
  negotiation left at `ROUND_COMPLETE` is genuinely resumable and is left
  alone.
- **Rounds expire.** An unfinished negotiation is swept to `EXPIRED`.

---

## The transcript hash

The transcript is ordered by `(round, kind, merchant_id, offer_id)`,
serialised with sorted keys and SHA-256'd. Merchants answer concurrently,
so arrival order differs on every run; ordering this way makes the hash a
property of what happened rather than of the race.

That hash goes into the approval binding. Alter the negotiation after it
was settled — edit an offer, add one, change a verdict — and the hash
moves, the binding stops matching, and no order is created.

---

## Settlement

`settle()` is the seam between the market and the money, and it trusts
none of what came before it.

**Recompute.** The policy engine re-prices the stored intent against the
signed manifest at settlement time. What gets charged is that
recomputation, never the `total_paise` column. Editing that column
changes a number that is displayed and nothing that is charged.

**Re-hash.** The transcript is hashed again and compared to the hash
recorded at acceptance.

**Re-approve.** The gateway evaluates the basket at catalog list price
against the shopper's signed mission, exactly as for any other purchase —
and the negotiated total may only ever be at or below that approved
ceiling. The bargaining layer can move a price down and has no way to
move one up. A settlement above the ceiling is
`SETTLEMENT_ABOVE_APPROVED_CEILING`, not a trim to fit.

Then: signed mission → R1–R12 → approval binding → user mandates →
execution machine → Razorpay. All of it pre-existing and unmodified. The
market added no payment path, because a second way to move money is a
second thing to get wrong.

**Settling twice does not pay twice.** The right to settle is claimed
with a conditional UPDATE; later callers replay the original
authorization rather than minting a new one. (This was a real bug: each
settle used to re-run the gateway, mint a fresh approve sequence, and the
execution machine — correctly — treated the two as different authorized
purchases and honoured both.)

---

## The approval binding, extended

Two fields were added, additively:

- `merchant_id` — which merchant won
- `negotiation_transcript_hash` — SHA-256 over the canonical transcript

Both are NULL for any purchase that never negotiated, and the executor
skips a check it has no subject for. The proof that this is genuinely
additive: 514 existing tests passed unmodified when it landed.

The executor reads both from the server's own quote record, never from
the request. A client cannot mint a quote, so it cannot assert a merchant
either.

---

## Two modes, both first-class

| | keys configured | no keys |
| --- | --- | --- |
| merchants | live LLM merchants | scripted fallback merchants |
| planner | LLM planner | keyword fallback planner |
| payments | Razorpay TEST MODE | simulated (`order_sim_` ids) |
| every feature | works | works |

Every API response and every badge carries the mode, read from the
provider machinery that already knows, so a label cannot drift from what
happened. A provider timeout, a malformed response or a rate limit drops
that one merchant to its deterministic strategy for that round, labelled
`fallback (llm unavailable)` in the transcript. The negotiation always
completes; nothing hangs on a third party.

The keyless market is reproducible: two runs of the same mission produce
the same offers, which is what makes a reviewer's clone useful — they see
the market this file describes, and can check it.

---

## What the catalog will not do

Ask for a camera and you get a refusal, not a substitute.

This was a bug worth recording. "Camera and lens for travel" used to
return `CHG-001`, a 65W charger, because its description says "compact
travel size" — a real catalog row, honestly labelled, and completely
wrong, with three merchants then bidding on a charger as though the
request had been served.

Only the name and the category can qualify an item now. A word in a
description says something about a product; the name and the category say
what it *is*, and only that can make it an answer. Descriptions still
order the items that already qualified.

SELLABLE sells what it stocks. Asked for anything else, it says so.
