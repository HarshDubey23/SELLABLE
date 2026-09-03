"""
Minimal checkout page that boots Razorpay Checkout JS with the REAL
test-mode order. This gives Playwright (and humans) a URL to open:

    GET /checkout/{order_id}
"""
import os

from fastapi import APIRouter, HTTPException
from fastapi.responses import HTMLResponse

from .store import db as store
from .tools import orders

router = APIRouter()


@router.get("/checkout/{order_id}")
async def checkout_page(order_id: str):
    """Serve the checkout page for the given order."""
    order = orders.get(order_id)
    if not order:
        raise HTTPException(404, detail=f"order {order_id} not found")

    amount_display = f"Rs {order['amount_paise']/100:,.0f}"
    key_id = os.environ.get("RAZORPAY_KEY_ID", "")
    if not key_id:
        return HTMLResponse(
            f"<html><body style='background:#071A2E;color:#EAF2FB;font-family:sans-serif;padding:40px;text-align:center'>"
            f"<h2>SELLABLE Checkout (Simulated)</h2>"
            f"<p>Order: <code>{order_id}</code></p>"
            f"<p>Amount: <strong>{amount_display}</strong></p>"
            f"<p style='color:#F5B83D'>Razorpay API keys are not configured on this instance. Payment is running in verified simulation mode.</p>"
            f"<p><a href='/' style='color:#2B84EA'>Return to Console</a></p>"
            f"</body></html>"
        )
    status = store.query_one(
        "SELECT status FROM orders WHERE order_id = ?", (order_id,))
    current_status = status["status"] if status else order.get("status", "created")

    html = f"""<!DOCTYPE html>
<html>
<head>
    <title>SELLABLE Checkout — {order_id}</title>
    <script src="https://checkout.razorpay.com/v1/checkout.js"></script>
    <style>
        body {{ font-family: system-ui; background: #0a0a0a;
               color: #e0e0e0; display: flex; justify-content: center;
               align-items: center; min-height: 100vh; margin: 0; }}
        .card {{ background: #1a1a1a; padding: 40px; border-radius: 8px;
                text-align: center; max-width: 400px; }}
        .amount {{ font-size: 32px; font-weight: bold; margin: 20px 0;
                  font-family: monospace; }}
        #pay-btn {{ background: #3395ff; color: #fff; border: 0;
                   padding: 12px 40px; font-size: 16px; border-radius: 6px;
                   cursor: pointer; }}
        #payment-status {{ margin-top: 20px; padding: 10px;
                          border-radius: 4px; color: #9aa; }}
    </style>
</head>
<body>
    <div class="card">
        <h2>SELLABLE Checkout</h2>
        <p>Order: {order_id}</p>
        <div class="amount">{amount_display}</div>
        <p>Status: {current_status}</p>
        <button id="pay-btn" onclick="openCheckout()">Pay with Razorpay</button>
        <div id="payment-status">Waiting for payment...</div>
    </div>
    <script>
        function openCheckout() {{
            var rzp = new Razorpay({{
                key: "{key_id}",
                amount: {order['amount_paise']},
                currency: "INR",
                name: "SELLABLE Demo Dukaan",
                description: "Agent-native storefront (test mode)",
                order_id: "{order_id}",
                handler: function (resp) {{
                    document.getElementById("payment-status").innerText =
                        "Payment submitted: " + resp.razorpay_payment_id;
                    pollStatus();
                }},
                modal: {{ ondismiss: function () {{
                    document.getElementById("payment-status").innerText =
                        "Checkout closed before payment.";
                }}}}
            }});
            rzp.open();
        }}
        function pollStatus() {{
            fetch("/tools/check_payment/{order_id}")
                .then(function (r) {{ return r.json(); }})
                .then(function (d) {{
                    document.getElementById("payment-status").innerText =
                        "Ledger status: " + d.local_status;
                }});
        }}
    </script>
</body>
</html>"""
    return HTMLResponse(content=html)
