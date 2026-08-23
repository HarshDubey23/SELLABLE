from fastapi import FastAPI, Request, HTTPException, Header
import hmac, hashlib, json, os, datetime
from pathlib import Path
from dotenv import load_dotenv

# .env project root se load karo
load_dotenv(Path(__file__).resolve().parents[2] / ".env")

app = FastAPI()
WEBHOOK_SECRET = os.environ["RAZORPAY_WEBHOOK_SECRET"]

@app.post("/webhook")
async def webhook(request: Request,
                  x_razorpay_signature: str = Header(default="")):
    body = await request.body()  # RAW body - parse mat karna pehle
    expected = hmac.new(
        WEBHOOK_SECRET.encode(), body, hashlib.sha256
    ).hexdigest()
    if not hmac.compare_digest(expected, x_razorpay_signature):
        print("SIGNATURE MISMATCH - REJECTED")
        raise HTTPException(status_code=400, detail="invalid signature")
    event = json.loads(body)
    line = f"[{datetime.datetime.now():%H:%M:%S}] {event['event']} | {event.get('id')}"
    print("EVENT RECEIVED:", line)
    with open("events.log", "a", encoding="utf-8") as f:
        f.write(line + "\n")
    return {"status": "ok"}

@app.get("/health")
def health():
    return {"status": "alive"}