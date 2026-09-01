# SELLABLE — Deploy Runbook

## Render

1. Go to https://render.com → New → Web Service.
2. Connect GitHub repo `HarshDubey23/SELLABLE`.
3. Build command: `pip install -r apps/api/requirements.txt`
4. Start command: `uvicorn apps.api.main:app --host 0.0.0.0 --port $PORT`
5. Set environment variables from the `.env.example` (all `from_secure: true`):
   - `RAZORPAY_KEY_ID`, `RAZORPAY_KEY_SECRET`, `RAZORPAY_WEBHOOK_SECRET`
   - `MISSION_HMAC_KEY`, `USER_MANDATE_KEY`
   - `GEMINI_API_KEY`, `GEMINI_MODEL=gemini-3.6-flash`, `APP_API_KEY`
6. Auto-deploy on push to `main`.

## Fly.io

1. `fly launch` → select `sellable` app, region `iad`.
2. `fly secrets set` for all env vars from `.env.example`.
3. `fly deploy` builds from `Dockerfile`.
4. `fly status` and `fly logs` for monitoring.

## Verification (post-deploy)

```bash
$ curl https://<app>.onrender.com/health
{"status":"alive","audit_chain_ok":true}

$ curl https://<app>.onrender.com/gateway/proof
{"llm_imports_detected":0,"io_calls_detected":0,...}

$ bash scripts/smoke_test.sh https://<app>.onrender.com
==== smoke_test: 8 passed, 0 failed ====
```

## Notes

- Render free tier: 15 GB disk, 512 MB RAM — sufficient for SQLite + uvicorn.
- Razorpay test keys rotate — update `RAZORPAY_KEY_ID`/`RAZORPAY_KEY_SECRET` on secret change.
- `GEMINI_API_KEY` billed separately via Google AI Studio; set spending cap.
- Never commit `.env`. All secrets via `from_secure` on Render or `fly secrets`.