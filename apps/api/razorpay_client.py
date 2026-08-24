import razorpay  # THE ONLY PLACE THIS IMPORT LIVES IN THE CODEBASE
from functools import lru_cache
import os


@lru_cache(maxsize=1)
def _client():
    # env read at CALL time, not import time (day-2 lesson: import order bit us)
    return razorpay.Client(
        auth=(os.environ["RAZORPAY_KEY_ID"], os.environ["RAZORPAY_KEY_SECRET"])
    )


def create_order(amount_paise: int, receipt: str, notes: dict) -> dict:
    if not isinstance(amount_paise, int) or isinstance(amount_paise, bool):
        raise ValueError("G4: money is int paise")
    return _client().order.create({
        "amount": amount_paise,
        "currency": "INR",
        "receipt": receipt,
        "notes": notes,
    })


def fetch_order(order_id: str) -> dict:
    return _client().order.fetch(order_id)
