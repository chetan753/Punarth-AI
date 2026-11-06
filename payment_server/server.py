"""Punarth AI payment server (Flask).

All payment secrets and payment-state changes live here, never in the
desktop app. Flow:

  desktop  ── POST /api/payments/<id>/start ──►  server creates Razorpay order
  desktop  ── opens browser at /pay/<id>     ──►  Razorpay Checkout
  browser  ── POST /api/payments/<id>/verify ──►  HMAC signature check +
                                                   payment fetched from Razorpay API
  Razorpay ── POST /webhooks/razorpay        ──►  webhook signature check
  desktop  ── GET  /api/payments/<id>        ◄──  polls status ("paid" only after server verification)

Demo mode (no Razorpay keys): /pay/<id> shows a test page whose buttons call
the server, which then marks the payment. The desktop still cannot mark
anything as paid itself.

Run:  python -m payment_server.server
"""
from __future__ import annotations

import hashlib
import hmac
import html
import json
import logging

import requests
from flask import Flask, abort, jsonify, request

from core import config, db, marketplace

log = logging.getLogger("punarth.payments")
app = Flask(__name__)
RZP_API = "https://api.razorpay.com/v1"


# ---------------------------------------------------------------------------
# Razorpay helpers
# ---------------------------------------------------------------------------

def verify_checkout_signature(order_id: str, payment_id: str, signature: str, secret: str) -> bool:
    expected = hmac.new(secret.encode(), f"{order_id}|{payment_id}".encode(), hashlib.sha256).hexdigest()
    return hmac.compare_digest(expected, signature or "")


def verify_webhook_signature(raw_body: bytes, signature: str, secret: str) -> bool:
    expected = hmac.new(secret.encode(), raw_body, hashlib.sha256).hexdigest()
    return hmac.compare_digest(expected, signature or "")


def rzp_create_order(amount_paise: int, receipt: str, notes: dict) -> dict:
    r = requests.post(f"{RZP_API}/orders", auth=(config.RAZORPAY_KEY_ID, config.RAZORPAY_KEY_SECRET),
                      json={"amount": amount_paise, "currency": config.CURRENCY, "receipt": receipt,
                            "notes": notes}, timeout=20)
    r.raise_for_status()
    return r.json()


def rzp_fetch_payment(payment_id: str) -> dict:
    r = requests.get(f"{RZP_API}/payments/{payment_id}",
                     auth=(config.RAZORPAY_KEY_ID, config.RAZORPAY_KEY_SECRET), timeout=20)
    r.raise_for_status()
    return r.json()


def _payment_or_404(pid: int) -> dict:
    p = marketplace.get_payment(pid)
    if not p:
        abort(404)
    return p


def _public(p: dict) -> dict:
    return {"id": p["id"], "status": p["status"], "purpose": p["purpose"], "amount": p["amount_paise"] / 100,
            "mode": p["mode"], "failure_reason": p["failure_reason"]}


# ---------------------------------------------------------------------------
# API
# ---------------------------------------------------------------------------

@app.get("/health")
def health():
    return {"ok": True, "demo_mode": config.payments_in_demo_mode()}


@app.post("/api/payments/<int:pid>/start")
def start_payment(pid: int):
    p = _payment_or_404(pid)
    if p["status"] == "paid":
        return jsonify({**_public(p), "checkout_url": f"{config.PAYMENT_SERVER_URL}/pay/{pid}"})
    if p["status"] == "failed" and not marketplace.reset_payment_for_retry(pid):
        return jsonify({"error": "This checkout was cancelled. Please place a new order."}), 409
    if config.payments_in_demo_mode():
        db.execute("UPDATE payments SET mode='demo', status='pending', updated_at=? WHERE id=?", (db.now(), pid))
    elif p["razorpay_order_id"]:
        db.execute("UPDATE payments SET status='pending', updated_at=? WHERE id=?", (db.now(), pid))
    else:
        try:
            order = rzp_create_order(p["amount_paise"], f"punarth_{pid}", {"payment_id": str(pid), "purpose": p["purpose"]})
        except requests.RequestException as e:
            log.exception("Razorpay order creation failed")
            return jsonify({"error": f"Could not create Razorpay order: {e}"}), 502
        if int(order.get("amount", -1)) != p["amount_paise"]:
            return jsonify({"error": "Amount mismatch from Razorpay"}), 502
        db.execute("UPDATE payments SET mode='razorpay', status='pending', razorpay_order_id=?, updated_at=? WHERE id=?",
                   (order["id"], db.now(), pid))
    return jsonify({**_public(marketplace.get_payment(pid)), "checkout_url": f"{config.PAYMENT_SERVER_URL}/pay/{pid}"})


@app.get("/api/payments/<int:pid>")
def payment_status(pid: int):
    return jsonify(_public(_payment_or_404(pid)))


@app.post("/api/payments/<int:pid>/verify")
def verify_payment(pid: int):
    """Called by the checkout page after Razorpay's success handler."""
    p = _payment_or_404(pid)
    data = request.get_json(silent=True) or request.form
    rzp_order = data.get("razorpay_order_id", "")
    rzp_payment = data.get("razorpay_payment_id", "")
    signature = data.get("razorpay_signature", "")
    if p["mode"] != "razorpay" or rzp_order != p["razorpay_order_id"]:
        return jsonify({"ok": False, "error": "Order mismatch"}), 400
    if not verify_checkout_signature(rzp_order, rzp_payment, signature, config.RAZORPAY_KEY_SECRET):
        log.warning("Rejected payment %s: invalid checkout signature", pid)
        return jsonify({"ok": False, "error": "Invalid signature"}), 400
    # Defence in depth: confirm with Razorpay's API that money was actually captured/authorized
    try:
        info = rzp_fetch_payment(rzp_payment)
    except requests.RequestException:
        # Signature is valid; the webhook will confirm capture. Leave as pending.
        return jsonify({"ok": True, "status": "pending"})
    if info.get("order_id") != rzp_order or int(info.get("amount", -1)) != p["amount_paise"]:
        marketplace.mark_payment_failed(pid, "Payment details do not match order")
        return jsonify({"ok": False, "error": "Payment mismatch"}), 400
    if info.get("status") in ("captured", "authorized"):
        marketplace.mark_payment_paid(pid, rzp_payment, "razorpay")
        return jsonify({"ok": True, "status": "paid"})
    return jsonify({"ok": True, "status": "pending"})


@app.post("/webhooks/razorpay")
def razorpay_webhook():
    raw = request.get_data()
    if not config.RAZORPAY_WEBHOOK_SECRET or not verify_webhook_signature(
            raw, request.headers.get("X-Razorpay-Signature", ""), config.RAZORPAY_WEBHOOK_SECRET):
        abort(400)
    event = json.loads(raw or b"{}")
    etype = event.get("event", "")
    payload = event.get("payload", {})
    pay = (payload.get("payment") or {}).get("entity") or {}
    order = (payload.get("order") or {}).get("entity") or {}
    rzp_order_id = pay.get("order_id") or order.get("id")
    row = db.q1("SELECT id, amount_paise FROM payments WHERE razorpay_order_id=?", (rzp_order_id,)) if rzp_order_id else None
    if not row:
        return {"ok": True, "ignored": True}
    if etype in ("payment.captured", "order.paid"):
        amount = int(pay.get("amount") or order.get("amount_paid") or -1)
        if amount == row["amount_paise"]:
            marketplace.mark_payment_paid(row["id"], pay.get("id", ""), "razorpay")
    elif etype == "payment.failed":
        marketplace.mark_payment_failed(row["id"], (pay.get("error_description") or "Payment failed"))
    return {"ok": True}


# ---------------------------------------------------------------------------
# Checkout pages (opened in the user's browser by the desktop app)
# ---------------------------------------------------------------------------

PAGE = """<!doctype html><html><head><meta charset="utf-8"><title>Punarth AI · Secure Checkout</title>
<meta name="viewport" content="width=device-width,initial-scale=1">
<style>
body{{margin:0;font-family:Segoe UI,Inter,Arial,sans-serif;background:linear-gradient(160deg,#ecfdf3,#fff);color:#0f2e1d}}
.card{{max-width:460px;margin:8vh auto;background:#fff;border-radius:20px;padding:36px;box-shadow:0 20px 60px rgba(22,101,52,.15)}}
h1{{margin:0 0 4px;font-size:22px}} .logo{{color:#16a34a;font-weight:800;letter-spacing:.5px}}
.amt{{font-size:40px;font-weight:800;margin:18px 0}} .muted{{color:#5b7466;font-size:14px}}
button{{width:100%;padding:14px;border:0;border-radius:12px;font-size:16px;font-weight:700;cursor:pointer;margin-top:12px}}
.pay{{background:#16a34a;color:#fff}} .fail{{background:#fee2e2;color:#991b1b}}
.badge{{display:inline-block;background:#fef3c7;color:#92400e;padding:4px 10px;border-radius:99px;font-size:12px;font-weight:700}}
#msg{{margin-top:16px;font-weight:600}}
</style></head><body><div class="card">
<div class="logo">♻ PUNARTH AI</div><h1>{title}</h1><div class="muted">Payment #{pid}</div>
<div class="amt">₹{amount}</div>{body}<div id="msg"></div></div></body></html>"""


@app.get("/pay/<int:pid>")
def checkout_page(pid: int):
    p = _payment_or_404(pid)
    title = {"order": "Complete your purchase", "featured": "Feature your listing",
             "subscription": "Seller plan subscription"}[p["purpose"]]
    amount = f"{p['amount_paise'] / 100:,.2f}"
    if p["status"] == "paid":
        body = "<p><b>✅ Payment received.</b> You can return to the Punarth AI app.</p>"
    elif p["mode"] == "demo":
        body = (f"""<span class="badge">DEMO MODE · no real money</span>
<p class="muted">Razorpay keys are not configured, so this test page stands in for Razorpay Checkout.
The server — not the app — records the result.</p>
<button class="pay" onclick="go('success')">Simulate successful payment</button>
<button class="fail" onclick="go('fail')">Simulate failed payment</button>
<script>
async function go(r){{const res=await fetch('/demo/{pid}/'+r,{{method:'POST'}});const j=await res.json();
document.getElementById('msg').innerText=j.status==='paid'?'✅ Payment successful. Return to the app.':'❌ Payment failed. Return to the app to retry.';
document.querySelectorAll('button').forEach(b=>b.disabled=true);}}
</script>""")
    else:
        user = db.q1("SELECT name,email,phone FROM users WHERE id=?", (p["user_id"],))
        opts = {"key": config.RAZORPAY_KEY_ID, "amount": p["amount_paise"], "currency": config.CURRENCY,
                "name": "Punarth AI", "description": title, "order_id": p["razorpay_order_id"],
                "prefill": {"name": user["name"], "email": user["email"], "contact": user["phone"]},
                "theme": {"color": "#16a34a"}}
        body = (f"""<p class="muted">Secured by Razorpay · UPI, cards, netbanking & wallets</p>
<button class="pay" id="payBtn">Pay ₹{amount}</button>
<script src="https://checkout.razorpay.com/v1/checkout.js"></script>
<script>
const opts={json.dumps(opts)};
opts.handler=async function(resp){{
  const r=await fetch('/api/payments/{pid}/verify',{{method:'POST',headers:{{'Content-Type':'application/json'}},body:JSON.stringify(resp)}});
  const j=await r.json();
  document.getElementById('msg').innerText=j.ok?(j.status==='paid'?'✅ Payment verified. Return to the app.':'⏳ Payment received, awaiting confirmation…'):'❌ '+(j.error||'Verification failed');
}};
opts.modal={{ondismiss:function(){{document.getElementById('msg').innerText='Payment window closed.';}}}};
const rzp=new Razorpay(opts);
rzp.on('payment.failed',function(e){{document.getElementById('msg').innerText='❌ '+e.error.description;}});
document.getElementById('payBtn').onclick=function(e){{rzp.open();e.preventDefault();}};
</script>""")
    return PAGE.format(title=html.escape(title), pid=pid, amount=amount, body=body)


@app.post("/demo/<int:pid>/<result>")
def demo_complete(pid: int, result: str):
    if not config.payments_in_demo_mode():
        abort(403)
    p = _payment_or_404(pid)
    if p["mode"] != "demo":
        abort(400)
    if result == "success":
        marketplace.mark_payment_paid(pid, f"demo_{pid}", "demo")
    else:
        marketplace.mark_payment_failed(pid, "Simulated failure (demo mode)")
    return jsonify(_public(marketplace.get_payment(pid)))


def main():
    logging.basicConfig(level=logging.INFO)
    db.init_db()
    mode = "DEMO (no Razorpay keys)" if config.payments_in_demo_mode() else "RAZORPAY"
    print(f"Punarth AI payment server on {config.PAYMENT_SERVER_URL}  ·  mode: {mode}")
    app.run(host=config.PAYMENT_SERVER_HOST, port=config.PAYMENT_SERVER_PORT, debug=False, use_reloader=False)


if __name__ == "__main__":
    main()
