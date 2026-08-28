# SELLABLE — 5-Minute Pitch Video Script

Record as unlisted YouTube or Loom at 1920x1080. Storyboard hits all four
scoring axes: Problem Taste, Build Quality, AI Judgment, Failure Recovery.

| Time | Section | Axis | Key Action |
|------|---------|------|------------|
| 0:00-0:30 | The problem | Problem Taste | Show README tagline; explain injection surface |
| 0:30-1:30 | Architecture | Build Quality | Show /gateway/proof JSON with 0 LLM imports |
| 1:30-2:30 | Negotiation engine | AI Judgment | Run live /negotiation/start + /run |
| 2:30-3:30 | Failure recovery | Failure Recovery | Show 3 failure demos + /audit/timeline |
| 3:30-4:20 | Eval harness | Build Quality | Run eval; show gated 100% injection resistance |
| 4:20-4:50 | What broke + next | Honesty | Show day05.md What broke section |
| 4:50-5:00 | CTA | — | Repo URL, MIT, 60+ tests green |

## 0:00-0:30 — Opening Hook

Visual: README top section with tagline highlighted.

> "When an AI agent buys something, every string it reads becomes a
> prompt-injection attack surface. If the LLM is in the money-deciding
> code, a single malicious product description can make the merchant sell
> at a loss. SELLABLE keeps the LLM out of the money path. The LLM
> proposes. Deterministic policy disposes. The audit log remembers."

## 0:30-1:30 — Architecture

Visual: docs/ARCHITECTURE.md data flow, then /gateway/proof in browser.

Walk through three layers: pure-stdlib gateway, SHA-256 audit chain,
single Razorpay money boundary.

```bash
curl /gateway/proof | jq
# show llm_imports_detected: 0, io_calls_detected: 0, source_sha256
```

## 1:30-2:30 — Negotiation Engine (Day 5 headline)

Visual: negotiation/engine.py with clamp_offer highlighted. Run a live
negotiation.

```bash
NID=$(curl -sX POST http://localhost:8000/negotiation/start \
  -H 'Content-Type: application/json' \
  -d '{"mission_id":"MSN-DEMO","sku":"BAT-001","qty":1,
       "floor_paise":119900,"ceiling_paise":149900,
       "buyer_budget_paise":150000,"max_turns":5}' | jq -r .negotiation_id)

curl -X POST http://localhost:8000/negotiation/$NID/run \
  -H 'Content-Type: application/json' -d '{"llm_enabled":false}' | jq .
```

Voiceover: Day 5 headline — multi-turn bounded negotiation. LLM writes
rationales; deterministic strategy sets prices. Floor and ceiling are
server-side. If LLM proposes below floor, it is clamped. Raw price is
preserved for audit. Walk-away if gap persists.

## 2:30-3:30 — Failure Recovery (the bar)

Visual: /audit/timeline. Run three failure demos.

1. Injection I1 — neutralized by server-side prices (R3).
2. Payment failure — real UPI refusal -> Gemini reasoning -> Payment Link.
3. Negotiation walk-away — bounded termination, no order.

Show `aud_67 -> aud_68 -> aud_69` linked by `parent_action_id`.

## 3:30-4:20 — Eval Harness

```bash
python -m eval.run --missions 100 --reps 3 --seed 42
cat eval/report.md
```

Three arms: static (baseline), ungated (naive, fraud loss), gated
(SELLABLE, 100% injection resistance). Headline: gated > ungated > static
after fraud loss.

## 4:20-4:50 — What Broke (honesty)

Visual: docs/log/day05.md What broke section.

Five things broke, each taught a lesson. Judges read "what broke" first.

## 4:50-5:00 — CTA

On-screen: `github.com/HarshDubey23/SELLABLE` — MIT — 60+ tests green.

> "The code is at github.com/HarshDubey23/SELLABLE. Thank you."
