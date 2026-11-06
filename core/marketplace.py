"""Marketplace domain logic: listings, search, wishlist, cart, checkout, orders,
payments (state changes only via the payment server), Q&A, messages, seller
dashboard, plans, featured listings and recovery requests."""
from __future__ import annotations

import json
import secrets
import shutil
from datetime import datetime, timedelta, timezone
from pathlib import Path

from . import assessment, catalog, config, db


class MarketError(Exception):
    pass


class ListingBlocked(MarketError):
    """Raised when a device must not be listed for consumer resale."""


ORDER_FLOW_DELIVERY = ["Paid", "Confirmed", "Shipped", "Out for Delivery", "Delivered"]
ORDER_FLOW_PICKUP = ["Paid", "Confirmed", "Ready for Pickup", "Picked Up"]
OPEN_ORDER_STATES = {"Paid", "Confirmed", "Shipped", "Out for Delivery", "Ready for Pickup"}
COMPLETED_STATES = {"Delivered", "Picked Up"}
PAID_STATES = OPEN_ORDER_STATES | COMPLETED_STATES


def _utcnow() -> datetime:
    return datetime.now(timezone.utc).replace(microsecond=0)


# ----------------------------------------------------------------------------
# Listings
# ----------------------------------------------------------------------------

SAFETY_KEYS = ("battery_swollen", "burn_smell_leak", "gets_hot")


def check_listing_safety(safety_answers: dict | None, assessment_id: int | None) -> None:
    if assessment_id:
        a = assessment.get_assessment(assessment_id)
        if a and a["classification"] == "Hazardous":
            raise ListingBlocked("This device was classified as Hazardous. Hazardous or unsafe "
                                 "devices cannot be listed for consumer resale — please use "
                                 "authorised e-waste collection instead.")
    for key in SAFETY_KEYS:
        if (safety_answers or {}).get(key) == "yes":
            raise ListingBlocked("Devices with a swollen battery, burn marks, leaks, exposed "
                                 "wiring or overheating cannot be listed for resale. Please "
                                 "book an authorised e-waste collection.")


def _validate_listing(data: dict) -> None:
    if not str(data.get("title", "")).strip():
        raise MarketError("Please enter a product title.")
    if data.get("category") not in catalog.CATEGORIES:
        raise MarketError("Please choose a category.")
    if data.get("condition") not in catalog.CONDITIONS:
        raise MarketError("Please choose a condition.")
    try:
        price = int(data.get("price", 0))
    except (TypeError, ValueError):
        raise MarketError("Price must be a whole number of rupees.")
    if price <= 0:
        raise MarketError("Price must be greater than ₹0.")
    if int(data.get("quantity", 1) or 1) < 1:
        raise MarketError("Quantity must be at least 1.")
    if not str(data.get("location", "")).strip():
        raise MarketError("Please enter the item's location (city).")
    fs = data.get("functionality_status")
    if fs and fs.startswith("Fully working (verified") and data.get("functionality_source") != "verified_inspection":
        raise MarketError("Only partner-inspected devices can be marked as verified.")


def active_listing_limit(user: dict) -> int:
    return catalog.SELLER_PLANS.get(user.get("seller_plan") or "free", catalog.SELLER_PLANS["free"])["listing_limit"]


def create_listing(seller_id: int, data: dict, image_paths: list[str] | None = None,
                   safety_answers: dict | None = None, status: str = "active") -> int:
    check_listing_safety(safety_answers, data.get("assessment_id"))
    _validate_listing(data)
    seller = db.q1("SELECT * FROM users WHERE id=?", (seller_id,))
    if not seller:
        raise MarketError("Seller not found.")
    if status == "active":
        active = db.q1("SELECT COUNT(*) c FROM listings WHERE seller_id=? AND status='active'",
                       (seller_id,))["c"]
        if active >= active_listing_limit(dict(seller)):
            raise MarketError("You have reached the active listing limit of your plan. "
                              "Upgrade in Seller Dashboard → Plans.")
    ts = db.now()
    lid = db.execute(
        "INSERT INTO listings (seller_id,title,category,brand,model,age_months,condition,"
        "functionality_status,functionality_source,description,price,original_price,est_low,est_high,"
        "suggested_price,location,delivery_options,quantity,status,for_repair,specs_json,defects_json,"
        "ai_assessment_json,provenance_json,assessment_id,created_at,updated_at) "
        "VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)",
        (seller_id, data["title"].strip(), data["category"], data.get("brand", ""), data.get("model", ""),
         int(data.get("age_months") or 0), data["condition"],
         data.get("functionality_status") or "Not tested",
         data.get("functionality_source") or "user_reported", data.get("description", ""),
         int(data["price"]), int(data.get("original_price") or 0), int(data.get("est_low") or 0),
         int(data.get("est_high") or 0), int(data.get("suggested_price") or 0), data["location"].strip(),
         data.get("delivery_options") or "delivery,pickup", int(data.get("quantity") or 1), status,
         1 if data.get("for_repair") or data["condition"] == "For Parts / Repair" else 0,
         json.dumps(data.get("specs") or {}), json.dumps(data.get("defects") or []),
         json.dumps(data.get("ai_summary")) if data.get("ai_summary") else "",
         json.dumps(data.get("provenance") or {}), data.get("assessment_id"), ts, ts),
    )
    if image_paths:
        add_images(lid, image_paths)
    return lid


def update_listing(seller_id: int, listing_id: int, data: dict, image_paths: list[str] | None = None) -> None:
    current = get_listing(listing_id)
    if not current or current["seller_id"] != seller_id:
        raise MarketError("You can only edit your own listings.")
    merged = {**current, **data}
    merged["specs"] = data.get("specs", current.get("specs") or {})
    merged["defects"] = data.get("defects", current.get("defects") or [])
    _validate_listing(merged)
    db.execute(
        "UPDATE listings SET title=?,category=?,brand=?,model=?,age_months=?,condition=?,"
        "functionality_status=?,description=?,price=?,location=?,delivery_options=?,quantity=?,"
        "for_repair=?,specs_json=?,defects_json=?,provenance_json=?,updated_at=? WHERE id=?",
        (merged["title"], merged["category"], merged["brand"], merged["model"],
         int(merged["age_months"] or 0), merged["condition"], merged["functionality_status"],
         merged["description"], int(merged["price"]), merged["location"], merged["delivery_options"],
         int(merged["quantity"]), 1 if merged.get("for_repair") or merged["condition"] == "For Parts / Repair" else 0,
         json.dumps(merged["specs"]), json.dumps(merged["defects"]),
         json.dumps(data.get("provenance", current.get("provenance") or {})), db.now(), listing_id),
    )
    if image_paths is not None:
        db.execute("DELETE FROM listing_images WHERE listing_id=?", (listing_id,))
        add_images(listing_id, image_paths)


def set_listing_status(seller_id: int, listing_id: int, status: str) -> None:
    if status not in ("active", "sold", "removed", "draft"):
        raise MarketError("Invalid status.")
    row = db.q1("SELECT seller_id, status FROM listings WHERE id=?", (listing_id,))
    if not row or row["seller_id"] != seller_id:
        raise MarketError("You can only change your own listings.")
    if status == "active" and row["status"] != "active":
        seller = dict(db.q1("SELECT * FROM users WHERE id=?", (seller_id,)))
        active = db.q1("SELECT COUNT(*) c FROM listings WHERE seller_id=? AND status='active'", (seller_id,))["c"]
        if active >= active_listing_limit(seller):
            raise MarketError("You have reached the active listing limit of your plan.")
    db.execute("UPDATE listings SET status=?, updated_at=? WHERE id=?", (status, db.now(), listing_id))
    if status != "active":
        db.execute("DELETE FROM cart_items WHERE listing_id=?", (listing_id,))


def delete_listing(seller_id: int, listing_id: int) -> None:
    """Soft delete so existing orders keep their history."""
    set_listing_status(seller_id, listing_id, "removed")


def add_images(listing_id: int, image_paths: list[str]) -> None:
    start = db.q1("SELECT COUNT(*) c FROM listing_images WHERE listing_id=?", (listing_id,))["c"]
    for i, src in enumerate(image_paths):
        src_path = Path(src)
        if not src_path.exists():
            continue
        if config.IMAGE_DIR in src_path.resolve().parents:
            dest = src_path
        else:
            dest = config.IMAGE_DIR / f"l{listing_id}_{secrets.token_hex(4)}{src_path.suffix.lower() or '.jpg'}"
            shutil.copyfile(src_path, dest)
        db.execute("INSERT INTO listing_images (listing_id,path,position) VALUES (?,?,?)",
                   (listing_id, str(dest), start + i))


def listing_images(listing_id: int) -> list[str]:
    return [r["path"] for r in db.q("SELECT path FROM listing_images WHERE listing_id=? ORDER BY position",
                                     (listing_id,))]


_LISTING_SELECT = """
SELECT l.*, u.name AS seller_name, u.business_name AS seller_business, u.account_type AS seller_type,
       u.verified AS seller_verified, u.city AS seller_city, u.created_at AS seller_since,
       u.seller_plan AS seller_plan,
       (SELECT path FROM listing_images i WHERE i.listing_id=l.id ORDER BY position LIMIT 1) AS cover
FROM listings l JOIN users u ON u.id = l.seller_id
"""


def _decorate(d: dict) -> dict:
    d["seller_display"] = d.get("seller_business") if d.get("seller_type") == "industry" and d.get("seller_business") else d.get("seller_name")
    d["featured_active"] = bool(d.get("is_featured")) and (d.get("featured_until") or "") > db.now()
    return d


def get_listing(listing_id: int) -> dict | None:
    row = db.q1(_LISTING_SELECT + " WHERE l.id=?", (listing_id,))
    if not row:
        return None
    d = _decorate(db.row_to_dict(row))
    d["images"] = listing_images(listing_id)
    return d


def record_view(listing_id: int, viewer_id: int | None) -> None:
    row = db.q1("SELECT seller_id FROM listings WHERE id=?", (listing_id,))
    if row and row["seller_id"] != viewer_id:
        db.execute("UPDATE listings SET views = views + 1 WHERE id=?", (listing_id,))


def search_listings(text: str = "", categories: list[str] | None = None, brands: list[str] | None = None,
                    min_price: int | None = None, max_price: int | None = None,
                    conditions: list[str] | None = None, location: str = "", seller_type: str = "",
                    verified_only: bool = False, recent_days: int | None = None,
                    sort: str = "featured", limit: int = 200, exclude_seller: int | None = None) -> list[dict]:
    where, params = ["l.status='active'", "l.quantity > 0"], []
    if text.strip():
        for word in text.strip().split():
            like = f"%{word}%"
            where.append("(l.title LIKE ? OR l.brand LIKE ? OR l.model LIKE ? OR l.category LIKE ?)")
            params += [like] * 4
    if categories:
        where.append(f"l.category IN ({','.join('?' * len(categories))})")
        params += categories
    if brands:
        where.append(f"l.brand IN ({','.join('?' * len(brands))})")
        params += brands
    if min_price is not None:
        where.append("l.price >= ?")
        params.append(int(min_price))
    if max_price is not None:
        where.append("l.price <= ?")
        params.append(int(max_price))
    if conditions:
        where.append(f"l.condition IN ({','.join('?' * len(conditions))})")
        params += conditions
    if location.strip():
        where.append("l.location LIKE ?")
        params.append(f"%{location.strip()}%")
    if seller_type in ("common", "industry"):
        where.append("u.account_type = ?")
        params.append(seller_type)
    if verified_only:
        where.append("u.verified = 1")
    if recent_days:
        cutoff = (_utcnow() - timedelta(days=int(recent_days))).isoformat()
        where.append("l.created_at >= ?")
        params.append(cutoff)
    if exclude_seller:
        where.append("l.seller_id != ?")
        params.append(exclude_seller)
    order = {
        "featured": "(l.is_featured=1 AND l.featured_until > ?) DESC, l.created_at DESC",
        "newest": "l.created_at DESC",
        "price_asc": "l.price ASC",
        "price_desc": "l.price DESC",
        "popular": "l.views DESC",
    }.get(sort, "l.created_at DESC")
    if sort == "featured":
        params.append(db.now())
    sql = _LISTING_SELECT + " WHERE " + " AND ".join(where) + f" ORDER BY {order} LIMIT {int(limit)}"
    return [_decorate(db.row_to_dict(r)) for r in db.q(sql, params)]


def brands_in_use() -> list[str]:
    return [r["brand"] for r in db.q("SELECT DISTINCT brand FROM listings WHERE status='active' AND brand!='' ORDER BY brand")]


def locations_in_use() -> list[str]:
    return [r["location"] for r in db.q("SELECT DISTINCT location FROM listings WHERE status='active' ORDER BY location")]


def category_counts() -> dict:
    return {r["category"]: r["c"] for r in db.q(
        "SELECT category, COUNT(*) c FROM listings WHERE status='active' AND quantity>0 GROUP BY category")}


def seller_listings(seller_id: int, include_removed: bool = False) -> list[dict]:
    sql = _LISTING_SELECT + " WHERE l.seller_id=?" + ("" if include_removed else " AND l.status!='removed'") + " ORDER BY l.updated_at DESC"
    return [_decorate(db.row_to_dict(r)) for r in db.q(sql, (seller_id,))]


def similar_listings(listing: dict, limit: int = 4) -> list[dict]:
    items = search_listings(categories=[listing["category"]], sort="popular", limit=limit + 1)
    return [i for i in items if i["id"] != listing["id"]][:limit]


# ----------------------------------------------------------------------------
# Wishlist
# ----------------------------------------------------------------------------

def toggle_wishlist(user_id: int, listing_id: int) -> bool:
    if db.q1("SELECT 1 FROM wishlist WHERE user_id=? AND listing_id=?", (user_id, listing_id)):
        db.execute("DELETE FROM wishlist WHERE user_id=? AND listing_id=?", (user_id, listing_id))
        return False
    db.execute("INSERT INTO wishlist (user_id,listing_id,created_at) VALUES (?,?,?)",
               (user_id, listing_id, db.now()))
    return True


def wishlist_ids(user_id: int) -> set[int]:
    return {r["listing_id"] for r in db.q("SELECT listing_id FROM wishlist WHERE user_id=?", (user_id,))}


def wishlist(user_id: int) -> list[dict]:
    rows = db.q(_LISTING_SELECT + " JOIN wishlist w ON w.listing_id=l.id WHERE w.user_id=? "
                "AND l.status!='removed' ORDER BY w.created_at DESC", (user_id,))
    return [_decorate(db.row_to_dict(r)) for r in rows]


# ----------------------------------------------------------------------------
# Cart
# ----------------------------------------------------------------------------

def add_to_cart(user_id: int, listing_id: int, qty: int = 1) -> None:
    listing = db.q1("SELECT * FROM listings WHERE id=?", (listing_id,))
    if not listing or listing["status"] != "active" or listing["quantity"] < 1:
        raise MarketError("This item is no longer available.")
    if listing["seller_id"] == user_id:
        raise MarketError("You cannot buy your own listing.")
    existing = db.q1("SELECT qty FROM cart_items WHERE user_id=? AND listing_id=?", (user_id, listing_id))
    new_qty = min(listing["quantity"], (existing["qty"] if existing else 0) + max(1, qty))
    db.execute("INSERT INTO cart_items (user_id,listing_id,qty,added_at) VALUES (?,?,?,?) "
               "ON CONFLICT(user_id,listing_id) DO UPDATE SET qty=excluded.qty",
               (user_id, listing_id, new_qty, db.now()))


def set_cart_qty(user_id: int, listing_id: int, qty: int) -> None:
    if qty <= 0:
        remove_from_cart(user_id, listing_id)
        return
    listing = db.q1("SELECT quantity FROM listings WHERE id=?", (listing_id,))
    if not listing:
        raise MarketError("Item not found.")
    db.execute("UPDATE cart_items SET qty=? WHERE user_id=? AND listing_id=?",
               (min(qty, listing["quantity"]), user_id, listing_id))


def remove_from_cart(user_id: int, listing_id: int) -> None:
    db.execute("DELETE FROM cart_items WHERE user_id=? AND listing_id=?", (user_id, listing_id))


def cart_count(user_id: int) -> int:
    return db.q1("SELECT COALESCE(SUM(qty),0) c FROM cart_items WHERE user_id=?", (user_id,))["c"]


def cart_items(user_id: int) -> list[dict]:
    rows = db.q(_LISTING_SELECT.replace("SELECT l.*", "SELECT c.qty AS cart_qty, l.*") +
                " JOIN cart_items c ON c.listing_id=l.id WHERE c.user_id=? ORDER BY c.added_at", (user_id,))
    items = []
    for r in rows:
        d = _decorate(db.row_to_dict(r))
        d["available"] = d["status"] == "active" and d["quantity"] >= d["cart_qty"]
        items.append(d)
    return items


def _delivery_fee(items: list[dict], method: str, subtotal: int) -> int:
    if method == "pickup":
        return 0
    if subtotal >= catalog.FREE_DELIVERY_ABOVE:
        return 0
    large = any(i["category"] in catalog.LARGE_ITEM_CATEGORIES for i in items)
    return catalog.DELIVERY_FEE_LARGE if large else catalog.DELIVERY_FEE_STANDARD


def cart_summary(user_id: int, delivery_method: str = "delivery", services: list[str] | None = None,
                 only_listing: int | None = None, buy_now_qty: int = 1) -> dict:
    """Price calculation grouped by seller (each seller ships separately).
    `only_listing` supports Buy Now without touching the cart."""
    services = [s for s in (services or []) if s in catalog.SERVICES]
    if only_listing:
        listing = get_listing(only_listing)
        if not listing:
            raise MarketError("Item not found.")
        listing["cart_qty"] = min(buy_now_qty, listing["quantity"])
        listing["available"] = listing["status"] == "active" and listing["quantity"] >= 1
        items = [listing]
    else:
        items = cart_items(user_id)
    groups: dict[int, dict] = {}
    problems = []
    for it in items:
        if not it["available"]:
            problems.append(f"'{it['title']}' is no longer available in that quantity.")
            continue
        if it["seller_id"] == user_id:
            problems.append(f"'{it['title']}' is your own listing.")
            continue
        if delivery_method == "delivery" and "delivery" not in (it["delivery_options"] or ""):
            problems.append(f"'{it['title']}' is pickup only.")
        g = groups.setdefault(it["seller_id"], {"seller_id": it["seller_id"], "seller": it["seller_display"],
                                                "items": [], "subtotal": 0})
        g["items"].append(it)
        g["subtotal"] += it["price"] * it["cart_qty"]
    total = subtotal_all = delivery_all = services_all = 0
    for g in groups.values():
        g["delivery_fee"] = _delivery_fee(g["items"], delivery_method, g["subtotal"])
        svc = 0
        for s in services:
            unit = catalog.SERVICES[s]["price"]
            svc += unit * (sum(i["cart_qty"] for i in g["items"]) if s == "extended_warranty" else 1)
        g["services_fee"] = svc
        g["total"] = g["subtotal"] + g["delivery_fee"] + svc
        subtotal_all += g["subtotal"]
        delivery_all += g["delivery_fee"]
        services_all += svc
        total += g["total"]
    return {"groups": list(groups.values()), "subtotal": subtotal_all, "delivery": delivery_all,
            "services": services_all, "total": total, "problems": problems,
            "item_count": sum(i["cart_qty"] for g in groups.values() for i in g["items"])}


# ----------------------------------------------------------------------------
# Checkout, payments and orders
# ----------------------------------------------------------------------------

def _commission_rate(seller_id: int) -> float:
    row = db.q1("SELECT seller_plan FROM users WHERE id=?", (seller_id,))
    return catalog.SELLER_PLANS.get(row["seller_plan"] if row else "free", catalog.SELLER_PLANS["free"])["commission"]


def create_checkout(user_id: int, delivery_method: str, address: dict, services: list[str] | None = None,
                    only_listing: int | None = None, buy_now_qty: int = 1) -> int:
    """Creates orders in 'Pending Payment' and a payment record. Returns payment id.
    Orders become 'Paid' only when the payment server verifies the payment."""
    if delivery_method not in ("delivery", "pickup"):
        raise MarketError("Choose delivery or pickup.")
    if delivery_method == "delivery":
        for k in ("name", "phone", "line1", "city", "pincode"):
            if not str(address.get(k, "")).strip():
                raise MarketError("Please complete the delivery address (name, phone, address, city, PIN code).")
        if not str(address["pincode"]).strip().isdigit() or len(str(address["pincode"]).strip()) != 6:
            raise MarketError("PIN code must be 6 digits.")
    summary = cart_summary(user_id, delivery_method, services, only_listing, buy_now_qty)
    if summary["problems"]:
        raise MarketError(" ".join(summary["problems"]))
    if not summary["groups"]:
        raise MarketError("Your cart is empty.")
    ts = db.now()
    with db.tx() as c:
        cur = c.execute(
            "INSERT INTO payments (user_id,purpose,amount_paise,currency,status,meta_json,created_at,updated_at) "
            "VALUES (?,?,?,?,?,?,?,?)",
            (user_id, "order", summary["total"] * 100, config.CURRENCY, "created",
             json.dumps({"from_cart": only_listing is None}), ts, ts))
        payment_id = cur.lastrowid
        for g in summary["groups"]:
            commission = round(g["subtotal"] * _commission_rate(g["seller_id"]))
            cur = c.execute(
                "INSERT INTO orders (buyer_id,seller_id,payment_id,status,subtotal,delivery_fee,services_fee,"
                "total,commission,delivery_method,address_json,services_json,created_at,updated_at) "
                "VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?)",
                (user_id, g["seller_id"], payment_id, "Pending Payment", g["subtotal"], g["delivery_fee"],
                 g["services_fee"], g["total"], commission, delivery_method, json.dumps(address),
                 json.dumps(services or []), ts, ts))
            order_id = cur.lastrowid
            for it in g["items"]:
                c.execute("INSERT INTO order_items (order_id,listing_id,title,price,qty) VALUES (?,?,?,?,?)",
                          (order_id, it["id"], it["title"], it["price"], it["cart_qty"]))
            c.execute("INSERT INTO order_events (order_id,status,note,created_at) VALUES (?,?,?,?)",
                      (order_id, "Pending Payment", "Order created, awaiting payment", ts))
    return payment_id


def create_featured_payment(user_id: int, listing_id: int) -> int:
    row = db.q1("SELECT seller_id,status FROM listings WHERE id=?", (listing_id,))
    if not row or row["seller_id"] != user_id:
        raise MarketError("You can only feature your own listings.")
    if row["status"] != "active":
        raise MarketError("Only active listings can be featured.")
    ts = db.now()
    return db.execute(
        "INSERT INTO payments (user_id,purpose,amount_paise,currency,status,meta_json,created_at,updated_at) "
        "VALUES (?,?,?,?,?,?,?,?)",
        (user_id, "featured", catalog.FEATURED_LISTING_PRICE * 100, config.CURRENCY, "created",
         json.dumps({"listing_id": listing_id}), ts, ts))


def create_subscription_payment(user_id: int, plan: str) -> int:
    if plan not in catalog.SELLER_PLANS or catalog.SELLER_PLANS[plan]["price"] <= 0:
        raise MarketError("Choose a paid plan.")
    ts = db.now()
    return db.execute(
        "INSERT INTO payments (user_id,purpose,amount_paise,currency,status,meta_json,created_at,updated_at) "
        "VALUES (?,?,?,?,?,?,?,?)",
        (user_id, "subscription", catalog.SELLER_PLANS[plan]["price"] * 100, config.CURRENCY, "created",
         json.dumps({"plan": plan}), ts, ts))


def get_payment(payment_id: int) -> dict | None:
    return db.row_to_dict(db.q1("SELECT * FROM payments WHERE id=?", (payment_id,)))


def mark_payment_paid(payment_id: int, razorpay_payment_id: str = "", mode: str = "") -> bool:
    """SERVER-SIDE ONLY. Called by the payment server after signature / API /
    webhook verification. Idempotent. Returns True if state changed."""
    ts = db.now()
    with db.tx() as c:
        p = c.execute("SELECT * FROM payments WHERE id=?", (payment_id,)).fetchone()
        if not p:
            raise MarketError("Payment not found.")
        if p["status"] == "paid":
            return False
        c.execute("UPDATE payments SET status='paid', razorpay_payment_id=COALESCE(NULLIF(?,''),razorpay_payment_id), "
                  "mode=COALESCE(NULLIF(?,''),mode), updated_at=? WHERE id=?",
                  (razorpay_payment_id, mode, ts, payment_id))
        meta = json.loads(p["meta_json"] or "{}")
        if p["purpose"] == "order":
            for o in c.execute("SELECT * FROM orders WHERE payment_id=?", (payment_id,)).fetchall():
                items = c.execute("SELECT * FROM order_items WHERE order_id=?", (o["id"],)).fetchall()
                ok = o["status"] != "Cancelled" and all(
                    (lst := c.execute("SELECT quantity,status FROM listings WHERE id=?", (it["listing_id"],)).fetchone())
                    and lst["status"] == "active" and lst["quantity"] >= it["qty"] for it in items)
                if not ok:
                    c.execute("UPDATE orders SET status='Refund Required', updated_at=? WHERE id=?", (ts, o["id"]))
                    c.execute("INSERT INTO order_events (order_id,status,note,created_at) VALUES (?,?,?,?)",
                              (o["id"], "Refund Required", "Order cancelled or item sold out before payment completed; refund will be issued", ts))
                    continue
                for it in items:
                    c.execute("UPDATE listings SET quantity = quantity - ?, updated_at=?, "
                              "status = CASE WHEN quantity - ? <= 0 THEN 'sold' ELSE status END WHERE id=?",
                              (it["qty"], ts, it["qty"], it["listing_id"]))
                    c.execute("DELETE FROM cart_items WHERE user_id=? AND listing_id=?", (o["buyer_id"], it["listing_id"]))
                tracking = "PNR" + secrets.token_hex(4).upper()
                c.execute("UPDATE orders SET status='Paid', tracking_code=?, updated_at=? WHERE id=?",
                          (tracking, ts, o["id"]))
                c.execute("INSERT INTO order_events (order_id,status,note,created_at) VALUES (?,?,?,?)",
                          (o["id"], "Paid", "Payment verified by server", ts))
            # remove now-unavailable items from every cart
            c.execute("DELETE FROM cart_items WHERE listing_id IN (SELECT id FROM listings WHERE status!='active')")
        elif p["purpose"] == "featured":
            until = (_utcnow() + timedelta(days=catalog.FEATURED_DAYS)).isoformat()
            c.execute("UPDATE listings SET is_featured=1, featured_until=? WHERE id=?", (until, meta.get("listing_id")))
        elif p["purpose"] == "subscription":
            until = (_utcnow() + timedelta(days=30)).isoformat()
            c.execute("UPDATE users SET seller_plan=?, plan_until=? WHERE id=?", (meta.get("plan"), until, p["user_id"]))
    return True


def mark_payment_failed(payment_id: int, reason: str = "") -> None:
    """SERVER-SIDE ONLY."""
    ts = db.now()
    with db.tx() as c:
        p = c.execute("SELECT status,purpose FROM payments WHERE id=?", (payment_id,)).fetchone()
        if not p or p["status"] == "paid":
            return
        c.execute("UPDATE payments SET status='failed', failure_reason=?, updated_at=? WHERE id=?",
                  (reason[:300], ts, payment_id))
        if p["purpose"] == "order":
            for o in c.execute("SELECT id FROM orders WHERE payment_id=? AND status='Pending Payment'", (payment_id,)).fetchall():
                c.execute("UPDATE orders SET status='Payment Failed', updated_at=? WHERE id=?", (ts, o["id"]))
                c.execute("INSERT INTO order_events (order_id,status,note,created_at) VALUES (?,?,?,?)",
                          (o["id"], "Payment Failed", reason[:200], ts))


def _orders(where: str, params) -> list[dict]:
    rows = db.q(f"""SELECT o.*, b.name AS buyer_name, s.name AS seller_name, s.business_name AS seller_business,
                    s.account_type AS seller_type, p.status AS payment_status
                    FROM orders o JOIN users b ON b.id=o.buyer_id JOIN users s ON s.id=o.seller_id
                    LEFT JOIN payments p ON p.id=o.payment_id WHERE {where} ORDER BY o.id DESC""", params)
    out = []
    for r in rows:
        d = db.row_to_dict(r)
        d["seller_display"] = d["seller_business"] if d["seller_type"] == "industry" and d["seller_business"] else d["seller_name"]
        d["items"] = [dict(i) for i in db.q(
            "SELECT oi.*, (SELECT path FROM listing_images li WHERE li.listing_id=oi.listing_id ORDER BY position LIMIT 1) AS cover "
            "FROM order_items oi WHERE order_id=?", (d["id"],))]
        d["events"] = [dict(e) for e in db.q("SELECT * FROM order_events WHERE order_id=? ORDER BY id", (d["id"],))]
        out.append(d)
    return out


def buyer_orders(user_id: int) -> list[dict]:
    return _orders("o.buyer_id=?", (user_id,))


def buyer_purchases(user_id: int) -> list[dict]:
    """Paid orders only (what the user actually bought)."""
    states = tuple(PAID_STATES)
    return _orders(f"o.buyer_id=? AND o.status IN ({','.join('?' * len(states))})", (user_id, *states))


def seller_orders(seller_id: int) -> list[dict]:
    return _orders("o.seller_id=? AND o.status != 'Pending Payment'", (seller_id,))


def orders_for_payment(payment_id: int) -> list[dict]:
    return _orders("o.payment_id=?", (payment_id,))


def next_order_status(order: dict) -> str | None:
    flow = ORDER_FLOW_PICKUP if order["delivery_method"] == "pickup" else ORDER_FLOW_DELIVERY
    if order["status"] in flow and flow.index(order["status"]) < len(flow) - 1:
        return flow[flow.index(order["status"]) + 1]
    return None


def advance_order(seller_id: int, order_id: int, note: str = "") -> str:
    o = db.q1("SELECT * FROM orders WHERE id=?", (order_id,))
    if not o or o["seller_id"] != seller_id:
        raise MarketError("Order not found.")
    nxt = next_order_status(dict(o))
    if not nxt:
        raise MarketError(f"Order is '{o['status']}' and cannot be advanced.")
    ts = db.now()
    with db.tx() as c:
        c.execute("UPDATE orders SET status=?, updated_at=? WHERE id=?", (nxt, ts, order_id))
        c.execute("INSERT INTO order_events (order_id,status,note,created_at) VALUES (?,?,?,?)",
                  (order_id, nxt, note, ts))
    return nxt


def cancel_unpaid_payment(buyer_id: int, payment_id: int) -> None:
    """Buyer cancels an unpaid checkout (all orders of that payment)."""
    p = get_payment(payment_id)
    if not p or p["user_id"] != buyer_id:
        raise MarketError("Order not found.")
    if p["status"] == "paid":
        raise MarketError("Paid orders must be cancelled through support.")
    ts = db.now()
    with db.tx() as c:
        c.execute("UPDATE payments SET status='failed', failure_reason='Cancelled by buyer', updated_at=? WHERE id=?",
                  (ts, payment_id))
        for o in c.execute("SELECT id FROM orders WHERE payment_id=? AND status IN ('Pending Payment','Payment Failed')",
                           (payment_id,)).fetchall():
            c.execute("UPDATE orders SET status='Cancelled', updated_at=? WHERE id=?", (ts, o["id"]))
            c.execute("INSERT INTO order_events (order_id,status,note,created_at) VALUES (?,?,?,?)",
                      (o["id"], "Cancelled", "Cancelled by buyer", ts))


def reset_payment_for_retry(payment_id: int) -> bool:
    """SERVER-SIDE: allow another attempt after a failed payment (not after cancellation)."""
    p = get_payment(payment_id)
    if not p or p["status"] == "paid" or p["failure_reason"] == "Cancelled by buyer":
        return False
    ts = db.now()
    with db.tx() as c:
        c.execute("UPDATE payments SET status='pending', failure_reason='', updated_at=? WHERE id=?", (ts, payment_id))
        for o in c.execute("SELECT id FROM orders WHERE payment_id=? AND status='Payment Failed'", (payment_id,)).fetchall():
            c.execute("UPDATE orders SET status='Pending Payment', updated_at=? WHERE id=?", (ts, o["id"]))
            c.execute("INSERT INTO order_events (order_id,status,note,created_at) VALUES (?,?,?,?)",
                      (o["id"], "Pending Payment", "Payment retried", ts))
    return True


# ----------------------------------------------------------------------------
# Questions and messages
# ----------------------------------------------------------------------------

def ask_question(listing_id: int, asker_id: int, text: str) -> int:
    if len(text.strip()) < 3:
        raise MarketError("Please type your question.")
    return db.execute("INSERT INTO questions (listing_id,asker_id,question,created_at) VALUES (?,?,?,?)",
                      (listing_id, asker_id, text.strip()[:500], db.now()))


def answer_question(seller_id: int, question_id: int, answer: str) -> None:
    row = db.q1("SELECT l.seller_id FROM questions q JOIN listings l ON l.id=q.listing_id WHERE q.id=?", (question_id,))
    if not row or row["seller_id"] != seller_id:
        raise MarketError("Only the seller can answer this question.")
    db.execute("UPDATE questions SET answer=?, answered_at=? WHERE id=?", (answer.strip()[:1000], db.now(), question_id))


def listing_questions(listing_id: int) -> list[dict]:
    return [dict(r) for r in db.q("SELECT q.*, u.name AS asker_name FROM questions q JOIN users u ON u.id=q.asker_id "
                                  "WHERE listing_id=? ORDER BY q.id DESC", (listing_id,))]


def seller_questions(seller_id: int, unanswered_only: bool = False) -> list[dict]:
    sql = ("SELECT q.*, u.name AS asker_name, l.title AS listing_title FROM questions q "
           "JOIN listings l ON l.id=q.listing_id JOIN users u ON u.id=q.asker_id WHERE l.seller_id=?")
    if unanswered_only:
        sql += " AND q.answer=''"
    return [dict(r) for r in db.q(sql + " ORDER BY q.id DESC", (seller_id,))]


def send_message(sender_id: int, recipient_id: int, body: str, listing_id: int | None = None) -> int:
    if not body.strip():
        raise MarketError("Message is empty.")
    if sender_id == recipient_id:
        raise MarketError("You cannot message yourself.")
    return db.execute("INSERT INTO messages (listing_id,sender_id,recipient_id,body,created_at) VALUES (?,?,?,?,?)",
                      (listing_id, sender_id, recipient_id, body.strip()[:2000], db.now()))


def inbox(user_id: int) -> list[dict]:
    return [dict(r) for r in db.q(
        "SELECT m.*, s.name AS sender_name, r.name AS recipient_name, l.title AS listing_title FROM messages m "
        "JOIN users s ON s.id=m.sender_id JOIN users r ON r.id=m.recipient_id "
        "LEFT JOIN listings l ON l.id=m.listing_id WHERE m.sender_id=? OR m.recipient_id=? ORDER BY m.id DESC",
        (user_id, user_id))]


def mark_messages_read(user_id: int) -> None:
    db.execute("UPDATE messages SET is_read=1 WHERE recipient_id=?", (user_id,))


# ----------------------------------------------------------------------------
# Seller dashboard
# ----------------------------------------------------------------------------

def seller_stats(seller_id: int) -> dict:
    one = lambda sql, *p: db.q1(sql, p)[0] or 0  # noqa: E731
    paid = tuple(PAID_STATES)
    ph = ",".join("?" * len(paid))
    open_states = tuple(OPEN_ORDER_STATES)
    return {
        "total_listings": one("SELECT COUNT(*) FROM listings WHERE seller_id=? AND status!='removed'", seller_id),
        "active_listings": one("SELECT COUNT(*) FROM listings WHERE seller_id=? AND status='active'", seller_id),
        "sold_products": one(f"SELECT COALESCE(SUM(oi.qty),0) FROM order_items oi JOIN orders o ON o.id=oi.order_id "
                             f"WHERE o.seller_id=? AND o.status IN ({ph})", seller_id, *paid)
        + one("SELECT COUNT(*) FROM listings l WHERE seller_id=? AND status='sold' AND NOT EXISTS "
              "(SELECT 1 FROM order_items oi WHERE oi.listing_id=l.id)", seller_id),
        "pending_orders": one(f"SELECT COUNT(*) FROM orders WHERE seller_id=? AND status IN ({','.join('?' * len(open_states))})",
                              seller_id, *open_states),
        "total_sales": one(f"SELECT COALESCE(SUM(subtotal),0) FROM orders WHERE seller_id=? AND status IN ({ph})", seller_id, *paid),
        "estimated_revenue": one(f"SELECT COALESCE(SUM(subtotal-commission),0) FROM orders WHERE seller_id=? AND status IN ({ph})",
                                 seller_id, *paid),
        "commission_paid": one(f"SELECT COALESCE(SUM(commission),0) FROM orders WHERE seller_id=? AND status IN ({ph})", seller_id, *paid),
        "product_views": one("SELECT COALESCE(SUM(views),0) FROM listings WHERE seller_id=?", seller_id),
        "buyer_requests": one("SELECT COUNT(*) FROM questions q JOIN listings l ON l.id=q.listing_id "
                              "WHERE l.seller_id=? AND q.answer=''", seller_id)
        + one("SELECT COUNT(*) FROM messages WHERE recipient_id=? AND is_read=0", seller_id),
    }


def sales_history(seller_id: int) -> list[dict]:
    paid = tuple(PAID_STATES)
    return [dict(r) for r in db.q(
        f"SELECT o.id AS order_id, o.created_at, o.status, oi.title, oi.price, oi.qty, o.commission, "
        f"u.name AS buyer_name FROM orders o JOIN order_items oi ON oi.order_id=o.id JOIN users u ON u.id=o.buyer_id "
        f"WHERE o.seller_id=? AND o.status IN ({','.join('?' * len(paid))}) ORDER BY o.id DESC", (seller_id, *paid))]


def marketplace_stats() -> dict:
    paid = tuple(PAID_STATES)
    ph = ",".join("?" * len(paid))
    r = db.q1(f"SELECT COUNT(*) n, COALESCE(SUM(commission),0) c FROM orders WHERE status IN ({ph})", paid)
    return {
        "active_listings": db.q1("SELECT COUNT(*) FROM listings WHERE status='active'")[0],
        "devices_resold": r["n"],
        "platform_commission": r["c"],
        "sellers": db.q1("SELECT COUNT(DISTINCT seller_id) FROM listings")[0],
    }


# ----------------------------------------------------------------------------
# Recovery partners and requests (repair / refurbish / recycle / donate)
# ----------------------------------------------------------------------------

def partners(ptype: str, city: str = "") -> list[dict]:
    rows = db.q("SELECT * FROM partners WHERE type=? ORDER BY (city=?) DESC, rating DESC", (ptype, city))
    return [dict(r) for r in rows]


def create_recovery_request(user_id: int, rtype: str, assessment_id: int | None, partner_id: int | None,
                            details: dict | None = None) -> int:
    if rtype not in ("repair", "refurbish", "recycle_collection", "donate", "inspection"):
        raise MarketError("Unknown request type.")
    return db.execute("INSERT INTO recovery_requests (user_id,assessment_id,type,partner_id,details_json,created_at) "
                      "VALUES (?,?,?,?,?,?)", (user_id, assessment_id, rtype, partner_id,
                                               json.dumps(details or {}), db.now()))


def recovery_requests(user_id: int) -> list[dict]:
    return [db.row_to_dict(r) for r in db.q(
        "SELECT r.*, p.name AS partner_name, p.city AS partner_city, a.category, a.brand, a.model, a.classification "
        "FROM recovery_requests r LEFT JOIN partners p ON p.id=r.partner_id "
        "LEFT JOIN assessments a ON a.id=r.assessment_id WHERE r.user_id=? ORDER BY r.id DESC", (user_id,))]


def impact_summary(user_id: int) -> dict:
    """Recovery impact for dashboards (devices diverted from landfill)."""
    rows = db.q("SELECT category, classification FROM assessments WHERE user_id=?", (user_id,))
    sold = db.q("SELECT l.category FROM orders o JOIN order_items oi ON oi.order_id=o.id JOIN listings l "
                "ON l.id=oi.listing_id WHERE o.seller_id=? AND o.status IN ('Delivered','Picked Up')", (user_id,))
    ewaste = co2 = 0.0
    for r in sold:
        imp = assessment.environmental_impact(r["category"])
        ewaste += imp["ewaste_kg"]
        co2 += imp["co2_kg"]
    by_class: dict[str, int] = {}
    for r in rows:
        by_class[r["classification"]] = by_class.get(r["classification"], 0) + 1
    return {"assessments": len(rows), "by_class": by_class, "devices_resold": len(sold),
            "ewaste_kg": round(ewaste, 1), "co2_kg": round(co2)}
