"""Payment server + vision tests."""
import hashlib
import hmac
import json
import os
import tempfile

import cv2
import numpy as np
import pytest

os.environ.setdefault("PUNARTH_DATA_DIR", tempfile.mkdtemp())

from core import auth, config, db, marketplace, seed, vision  # noqa: E402
from payment_server import server  # noqa: E402


@pytest.fixture()
def setup(tmp_path, monkeypatch):
    db.set_db_path(tmp_path / "s.db")
    seed.seed_if_empty()
    asha = auth.login("asha@demo.in", "demo123")
    item = marketplace.search_listings("Bravia")[0]
    marketplace.add_to_cart(asha["id"], item["id"])
    pid = marketplace.create_checkout(asha["id"], "pickup", {})
    return server.app.test_client(), pid, item


def test_demo_flow(setup, monkeypatch):
    client, pid, item = setup
    monkeypatch.setattr(config, "payments_in_demo_mode", lambda: True)
    r = client.post(f"/api/payments/{pid}/start")
    assert r.status_code == 200 and r.json["status"] == "pending"
    assert "DEMO MODE" in client.get(f"/pay/{pid}").get_data(as_text=True)
    assert client.get(f"/api/payments/{pid}").json["status"] == "pending"
    assert client.post(f"/demo/{pid}/success").json["status"] == "paid"
    assert marketplace.orders_for_payment(pid)[0]["status"] == "Paid"


def test_demo_endpoint_disabled_in_live_mode(setup, monkeypatch):
    client, pid, _ = setup
    monkeypatch.setattr(config, "payments_in_demo_mode", lambda: False)
    assert client.post(f"/demo/{pid}/success").status_code == 403


def test_razorpay_verify_and_webhook(setup, monkeypatch):
    client, pid, item = setup
    monkeypatch.setattr(config, "payments_in_demo_mode", lambda: False)
    monkeypatch.setattr(config, "RAZORPAY_KEY_ID", "rzp_test_x")
    monkeypatch.setattr(config, "RAZORPAY_KEY_SECRET", "sekret")
    monkeypatch.setattr(config, "RAZORPAY_WEBHOOK_SECRET", "whsec")
    amount = marketplace.get_payment(pid)["amount_paise"]
    monkeypatch.setattr(server, "rzp_create_order", lambda a, r, n: {"id": "order_ABC", "amount": a})
    assert client.post(f"/api/payments/{pid}/start").json["status"] == "pending"
    page = client.get(f"/pay/{pid}").get_data(as_text=True)
    assert "checkout.razorpay.com" in page and "order_ABC" in page and "sekret" not in page

    # forged signature is rejected and does NOT mark paid
    r = client.post(f"/api/payments/{pid}/verify", json={"razorpay_order_id": "order_ABC",
                    "razorpay_payment_id": "pay_1", "razorpay_signature": "bad"})
    assert r.status_code == 400
    assert marketplace.get_payment(pid)["status"] == "pending"

    # new checkout for a valid flow
    asha = auth.login("asha@demo.in", "demo123")
    marketplace.add_to_cart(asha["id"], item["id"])
    pid2 = marketplace.create_checkout(asha["id"], "pickup", {})
    monkeypatch.setattr(server, "rzp_create_order", lambda a, r, n: {"id": "order_XYZ", "amount": a})
    client.post(f"/api/payments/{pid2}/start")
    sig = hmac.new(b"sekret", b"order_XYZ|pay_2", hashlib.sha256).hexdigest()
    monkeypatch.setattr(server, "rzp_fetch_payment",
                        lambda p: {"order_id": "order_XYZ", "amount": amount, "status": "captured"})
    r = client.post(f"/api/payments/{pid2}/verify", json={"razorpay_order_id": "order_XYZ",
                    "razorpay_payment_id": "pay_2", "razorpay_signature": sig})
    assert r.json == {"ok": True, "status": "paid"}
    assert marketplace.orders_for_payment(pid2)[0]["status"] == "Paid"

    # webhook: bad signature rejected, good one accepted (idempotent)
    body = json.dumps({"event": "payment.captured", "payload": {"payment": {"entity": {
        "id": "pay_2", "order_id": "order_XYZ", "amount": amount}}}}).encode()
    assert client.post("/webhooks/razorpay", data=body, headers={"X-Razorpay-Signature": "nope"}).status_code == 400
    good = hmac.new(b"whsec", body, hashlib.sha256).hexdigest()
    assert client.post("/webhooks/razorpay", data=body, headers={"X-Razorpay-Signature": good}).json["ok"]


def test_webhook_marks_paid_when_browser_closed(setup, monkeypatch):
    client, pid, _ = setup
    monkeypatch.setattr(config, "payments_in_demo_mode", lambda: False)
    monkeypatch.setattr(config, "RAZORPAY_KEY_ID", "k")
    monkeypatch.setattr(config, "RAZORPAY_KEY_SECRET", "s")
    monkeypatch.setattr(config, "RAZORPAY_WEBHOOK_SECRET", "w")
    monkeypatch.setattr(server, "rzp_create_order", lambda a, r, n: {"id": "order_W", "amount": a})
    client.post(f"/api/payments/{pid}/start")
    amount = marketplace.get_payment(pid)["amount_paise"]
    body = json.dumps({"event": "order.paid", "payload": {"order": {"entity": {"id": "order_W", "amount_paid": amount}},
                                                          "payment": {"entity": {"id": "pay_9", "order_id": "order_W",
                                                                                 "amount": amount}}}}).encode()
    sig = hmac.new(b"w", body, hashlib.sha256).hexdigest()
    client.post("/webhooks/razorpay", data=body, headers={"X-Razorpay-Signature": sig})
    assert marketplace.get_payment(pid)["status"] == "paid"


# ---------------- vision ----------------

def test_yolo_postprocess_v8_layout():
    out = np.zeros((1, 84, 3), dtype=np.float32)
    out[0, :4, 0] = [320, 320, 100, 200]
    out[0, 4 + 67, 0] = 0.9         # cell phone
    out[0, :4, 1] = [100, 100, 50, 50]
    out[0, 4 + 0, 1] = 0.95         # person -> ignored
    res = vision.postprocess(out, 1.0, 0, 0, 640, 640)
    assert len(res) == 1 and res[0]["category"] == "Smartphones"
    assert res[0]["box"] == [270, 220, 100, 200]


def test_defect_heuristic():
    img = np.full((400, 300, 3), 30, np.uint8)
    clean = vision.analyze_defects(img)
    assert clean == []
    for off in (0, 40, 80):
        cv2.line(img, (60 + off, 60), (200 + off, 330), (230, 230, 230), 2)
    assert vision.analyze_defects(img)[0]["label"].startswith("Possible crack")


def test_quality_and_parse():
    q = vision.image_quality(np.zeros((100, 100, 3), np.uint8))
    assert not q["ok"]
    parsed = vision.parse_vision_json('Sure: {"category":"Laptops","brand":"Dell","model":"XPS 13",'
                                      '"visible_defects":["dent on lid"],"confidence":0.8}')
    assert parsed["brand"] == "Dell" and parsed["defects"][0]["label"] == "dent on lid"


def test_detector_missing_model_is_graceful(tmp_path):
    d = vision.Detector(tmp_path / "none.onnx")
    assert not d.available and "not found" in d.error
    f = vision.analyze_capture(np.full((200, 200, 3), 120, np.uint8), d, use_cloud=False)
    assert f["notes"]
