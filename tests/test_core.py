"""Core engine tests: run with  python -m pytest -q"""
import os
import tempfile

import pytest

_tmp = tempfile.mkdtemp()
os.environ["PUNARTH_DATA_DIR"] = _tmp

from core import assessment, auth, catalog, db, listing_ai, marketplace, seed  # noqa: E402


@pytest.fixture(autouse=True)
def fresh_db(tmp_path):
    db.set_db_path(tmp_path / "t.db")
    seed.seed_if_empty()
    yield


def good_phone_answers(**over):
    a = {"age_months": 12, "original_price": 30000, "powers_on": "yes", "body_damage": "Light scratches",
         "battery_swollen": "no", "burn_smell_leak": "no", "liquid_damage": "no",
         "accessories": "Charger / key accessories only", "screen_ok": "yes", "touch_ok": "yes",
         "battery_health": "Above 85% / full day", "cameras_ok": "yes", "charging_ok": "yes",
         "calls_ok": "yes", "biometrics_ok": "yes", "account_removed": "yes"}
    a.update(over)
    return a


# ---------------- assessment / segregation ----------------

def test_reusable_phone():
    r = assessment.assess("Smartphones", good_phone_answers(), "Samsung", "Galaxy A54")
    assert r["classification"] == "Reusable"
    assert r["grade"] == "Excellent"
    assert r["functional_status"] == "Fully working (seller reported)"
    assert 0 < r["value"]["low"] < r["value"]["suggested"] < r["value"]["high"] < 30000
    assert r["can_list"]
    assert any(x["action"] == "create_listing" for x in r["recommendations"])


def test_hazard_blocks_everything():
    r = assessment.assess("Smartphones", good_phone_answers(battery_swollen="yes"))
    assert r["classification"] == "Hazardous"
    assert not r["can_list"]
    assert r["value"]["suggested"] == 0


def test_repairable_screen():
    r = assessment.assess("Smartphones", good_phone_answers(screen_ok="no"), "Apple", "iPhone 12")
    assert r["classification"] == "Repairable"
    assert r["grade"] == "For Parts / Repair"
    assert r["functional_status"] == "Partially working"
    est = assessment.repair_estimate("Smartphones", good_phone_answers(screen_ok="no"))
    assert est["low"] > 0


def test_recyclable_dead_old():
    r = assessment.assess("Smartphones", good_phone_answers(powers_on="no", age_months=110))
    assert r["classification"] == "Recyclable"
    assert not r["can_list"]


def test_refurbishable_and_manual():
    r = assessment.assess("Laptops", {"age_months": 50, "powers_on": "yes", "body_damage": "Dents or cracks on body",
                                      "screen_ok": "yes", "keyboard_ok": "yes", "ports_ok": "yes", "boots_os": "yes",
                                      "battery_swollen": "no", "burn_smell_leak": "no"})
    assert r["classification"] == "Refurbishable"
    assert r["grade"] == "Fair"
    r2 = assessment.assess("Laptops", {"powers_on": "unsure"})
    assert r2["classification"] == "Requires Manual Inspection"
    assert r2["functional_status"] == "Not tested"


def test_image_defect_never_claims_working_and_caps_grade():
    findings = {"defects": [{"label": "Possible screen crack", "confidence": 0.8}]}
    r = assessment.assess("Smartphones", good_phone_answers(body_damage="No marks"), image_findings=findings)
    assert r["grade"] == "Good"
    assert r["warnings"]
    # Image alone (no answers) must never yield "fully working"
    r2 = assessment.assess("Smartphones", {}, image_findings={"defects": []})
    assert not r2["functional_status"].startswith("Fully working")


def test_listing_draft_and_provenance():
    ans = good_phone_answers()
    r = assessment.assess("Smartphones", ans, "Google", "Pixel 7")
    draft = listing_ai.draft_from_assessment(r, ans, "Pune")
    v = draft["values"]
    assert "Google Pixel 7" in v["title"]
    assert "not been independently verified" in v["description"]
    final = dict(v, price=v["price"] + 500)
    prov = listing_ai.resolve_provenance(v, final, draft["provenance"], confirmed=True)
    assert prov["price"] == "user" and prov["title"] == "ai_confirmed"


# ---------------- marketplace ----------------

def _users():
    asha = auth.login("asha@demo.in", "demo123")
    rohan = auth.login("rohan@demo.in", "demo123")
    return asha, rohan


def test_auth():
    with pytest.raises(auth.AuthError):
        auth.login("asha@demo.in", "wrong")
    u = auth.register("Test Co", "t@x.in", "secret1", "industry", business_name="Test Co Pvt")
    assert u["seller_plan"] == "business"


def test_hazardous_listing_blocked():
    asha, _ = _users()
    r = assessment.assess("Smartphones", good_phone_answers(burn_smell_leak="yes"))
    aid = assessment.save_assessment(asha["id"], r, {}, None)
    with pytest.raises(marketplace.ListingBlocked):
        marketplace.create_listing(asha["id"], {"title": "x", "category": "Smartphones", "condition": "Good",
                                                "price": 100, "location": "X", "assessment_id": aid})
    with pytest.raises(marketplace.ListingBlocked):
        marketplace.create_listing(asha["id"], {"title": "x", "category": "Smartphones", "condition": "Good",
                                                "price": 100, "location": "X"}, safety_answers={"battery_swollen": "yes"})


def test_search_filters():
    res = marketplace.search_listings("thinkpad")
    assert res and all("ThinkPad" in r["title"] for r in res)
    lap = marketplace.search_listings(categories=["Laptops"], max_price=25000)
    assert lap and all(r["price"] <= 25000 and r["category"] == "Laptops" for r in lap)
    ind = marketplace.search_listings(seller_type="industry", verified_only=True)
    assert ind and all(r["seller_type"] == "industry" for r in ind)
    assert marketplace.search_listings(conditions=["For Parts / Repair"])
    assert marketplace.search_listings(sort="featured")[0]["featured_active"]


def test_cart_checkout_payment_flow():
    asha, rohan = _users()
    tv = marketplace.search_listings("Bravia")[0]
    mon = marketplace.search_listings("P2419H")[0]
    marketplace.add_to_cart(asha["id"], tv["id"])
    marketplace.add_to_cart(asha["id"], mon["id"], 2)
    assert marketplace.cart_count(asha["id"]) == 3
    s = marketplace.cart_summary(asha["id"], "delivery")
    assert len(s["groups"]) == 2
    assert s["total"] == s["subtotal"] + s["delivery"] + s["services"]
    with pytest.raises(marketplace.MarketError):
        marketplace.create_checkout(asha["id"], "delivery", {"name": "A"})
    addr = {"name": "Asha", "phone": "9800000000", "line1": "12 MG Road", "city": "Bengaluru", "pincode": "560001"}
    pid = marketplace.create_checkout(asha["id"], "delivery", addr, ["inspection"])
    orders = marketplace.orders_for_payment(pid)
    assert all(o["status"] == "Pending Payment" for o in orders)
    assert marketplace.get_payment(pid)["amount_paise"] == s["total"] * 100 + 2 * 199 * 100
    # Not paid until server marks it
    assert marketplace.cart_count(asha["id"]) == 3
    assert marketplace.mark_payment_paid(pid, "pay_test", "demo") is True
    assert marketplace.mark_payment_paid(pid, "pay_test", "demo") is False  # idempotent
    orders = marketplace.orders_for_payment(pid)
    assert all(o["status"] == "Paid" for o in orders)
    assert marketplace.cart_count(asha["id"]) == 0
    assert marketplace.get_listing(tv["id"])["status"] == "sold"
    assert marketplace.get_listing(mon["id"])["quantity"] == mon["quantity"] - 2
    # seller flow
    tv_order = [o for o in orders if o["seller_id"] == rohan["id"]][0]
    assert marketplace.advance_order(rohan["id"], tv_order["id"]) == "Confirmed"
    for _ in range(3):
        marketplace.advance_order(rohan["id"], tv_order["id"])
    assert marketplace.buyer_orders(asha["id"])[0]["status"] in ("Delivered", "Paid")
    st = marketplace.seller_stats(rohan["id"])
    assert st["total_sales"] == tv["price"] and st["estimated_revenue"] < tv["price"]
    assert marketplace.buyer_purchases(asha["id"])


def test_failed_payment_and_sold_out():
    asha, rohan = _users()
    ps5 = marketplace.search_listings("PlayStation")[0]
    addr = {"name": "A", "phone": "9", "line1": "x", "city": "y", "pincode": "560001"}
    marketplace.add_to_cart(asha["id"], ps5["id"])
    pid = marketplace.create_checkout(asha["id"], "delivery", addr)
    marketplace.mark_payment_failed(pid, "card declined")
    assert marketplace.orders_for_payment(pid)[0]["status"] == "Payment Failed"
    # two buyers race for the same single item
    priya = auth.login("priya@demo.in", "demo123")
    marketplace.add_to_cart(priya["id"], ps5["id"])
    p1 = marketplace.create_checkout(asha["id"], "pickup", {})
    p2 = marketplace.create_checkout(priya["id"], "pickup", {})
    marketplace.mark_payment_paid(p1)
    marketplace.mark_payment_paid(p2)
    assert marketplace.orders_for_payment(p2)[0]["status"] == "Refund Required"


def test_buy_now_own_listing_and_qna():
    asha, rohan = _users()
    own = marketplace.seller_listings(asha["id"])[0]
    with pytest.raises(marketplace.MarketError):
        marketplace.add_to_cart(asha["id"], own["id"])
    s = marketplace.cart_summary(rohan["id"], "pickup", only_listing=own["id"])
    assert s["total"] == own["price"]
    qid = marketplace.ask_question(own["id"], rohan["id"], "Still available?")
    with pytest.raises(marketplace.MarketError):
        marketplace.answer_question(rohan["id"], qid, "hack")
    marketplace.answer_question(asha["id"], qid, "Yes")
    assert marketplace.listing_questions(own["id"])[0]["answer"] == "Yes"


def test_featured_and_subscription():
    asha, _ = _users()
    lst = marketplace.seller_listings(asha["id"])[-1]
    pid = marketplace.create_featured_payment(asha["id"], lst["id"])
    marketplace.mark_payment_paid(pid)
    assert marketplace.get_listing(lst["id"])["featured_active"]
    pid = marketplace.create_subscription_payment(asha["id"], "pro")
    marketplace.mark_payment_paid(pid)
    assert auth.get_user(asha["id"])["seller_plan"] == "pro"


def test_listing_limit_and_recovery():
    rohan = auth.login("rohan@demo.in", "demo123")
    base = {"title": "Cable", "category": "Chargers and Adapters", "condition": "Good", "price": 99, "location": "Mumbai"}
    marketplace.create_listing(rohan["id"], base)
    marketplace.create_listing(rohan["id"], base)
    with pytest.raises(marketplace.MarketError):
        marketplace.create_listing(rohan["id"], base)  # free plan = 5 active
    p = marketplace.partners("recycler", "Mumbai")
    assert p[0]["city"] == "Mumbai"
    rid = marketplace.create_recovery_request(rohan["id"], "recycle_collection", None, p[0]["id"], {"pickup": "Sat"})
    assert marketplace.recovery_requests(rohan["id"])[0]["id"] == rid


def test_all_categories_have_questions():
    for c in catalog.CATEGORIES:
        qs = catalog.questions_for(c)
        assert any(q.get("critical") for q in qs)
        assert len({q["key"] for q in qs}) == len(qs)
