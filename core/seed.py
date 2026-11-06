"""Demo data: accounts, recovery partners and marketplace listings with
generated product images, so the app is presentable on first launch."""
from __future__ import annotations

import json
import random
from datetime import timedelta

from PIL import Image, ImageDraw, ImageFilter, ImageFont

from . import auth, catalog, config, db, marketplace

DEMO_PASSWORD = "demo123"

USERS = [
    ("Asha Rao", "asha@demo.in", "common", "", "Bengaluru", 1),
    ("Rohan Mehta", "rohan@demo.in", "common", "", "Mumbai", 0),
    ("Priya Nair", "priya@demo.in", "common", "", "Kochi", 1),
    ("Vikram Singh", "greencycle@demo.in", "industry", "GreenCycle Refurbishers Pvt Ltd", "Bengaluru", 1),
    ("Neha Gupta", "techreuse@demo.in", "industry", "TechReuse Solutions", "Delhi", 1),
]

PARTNERS = [
    ("FixIt Mobile Care", "repair", "Bengaluru", 4.7, 0, "Smartphone & tablet screen, battery and port repairs."),
    ("Laptop Doctor", "repair", "Mumbai", 4.6, 0, "Laptop board-level repair, keyboards, hinges."),
    ("QuickServe Electronics", "repair", "Delhi", 4.4, 0, "TVs, monitors and home electronics repair."),
    ("ReNew Tech Refurbishers", "refurbish", "Bengaluru", 4.8, 1, "Grade-A refurbishment with 6-month warranty."),
    ("SecondLife Devices", "refurbish", "Pune", 4.5, 1, "Bulk refurbishment for corporate IT assets."),
    ("GreenEarth E-Waste Recyclers", "recycler", "Bengaluru", 4.8, 1, "CPCB-authorised e-waste recycler."),
    ("MetalLoop Recycling", "recycler", "Delhi", 4.7, 1, "CPCB-authorised; metal recovery from e-waste."),
    ("CleanCircuit Recyclers", "recycler", "Mumbai", 4.6, 1, "CPCB-authorised collection and recycling."),
    ("Hyderabad E-Waste Hub", "recycler", "Hyderabad", 4.3, 1, "Authorised dismantler and recycler."),
]

LISTINGS = [
    # seller_idx, title, category, brand, model, age_m, condition, func, source, price, orig, loc, qty, color, days_ago, featured, defects, specs
    (0, "Apple iPhone 13 128GB – Excellent condition", "Smartphones", "Apple", "iPhone 13", 26, "Excellent",
     "Fully working (seller tested)", "seller_tested", 32999, 69900, "Bengaluru", 1, (40, 60, 90), 1, True,
     ["Light scratch on rear glass"], {"Storage": "128 GB", "Battery health": "86%", "Colour": "Midnight"}),
    (1, "Samsung Galaxy S21 FE 5G – Good condition", "Smartphones", "Samsung", "Galaxy S21 FE", 30, "Good",
     "Fully working (seller reported)", "user_reported", 17499, 39999, "Mumbai", 1, (110, 140, 120), 3, False,
     ["Minor scuffs on frame"], {"Storage": "128 GB", "RAM": "8 GB"}),
    (3, "Dell Latitude 7490 i5 8th Gen – Refurbished", "Laptops", "Dell", "Latitude 7490", 60, "Excellent",
     "Fully working (verified inspection)", "verified_inspection", 23999, 85000, "Bengaluru", 6, (30, 30, 35), 2, True,
     [], {"CPU": "Intel i5-8350U", "RAM": "16 GB", "SSD": "256 GB", "Display": "14\" FHD"}),
    (2, "Lenovo IdeaPad Slim 3 – Like New", "Laptops", "Lenovo", "IdeaPad Slim 3", 8, "Like New",
     "Fully working (seller tested)", "seller_tested", 38999, 52990, "Kochi", 1, (150, 150, 160), 0, False,
     [], {"CPU": "Ryzen 5 7520U", "RAM": "8 GB", "SSD": "512 GB"}),
    (0, "Apple iPad 9th Gen Wi-Fi 64GB", "Tablets", "Apple", "iPad (9th gen)", 28, "Good",
     "Fully working (seller reported)", "user_reported", 18999, 30900, "Bengaluru", 1, (190, 190, 200), 5, False,
     ["Small dent on corner"], {"Storage": "64 GB", "Connectivity": "Wi-Fi"}),
    (4, "HP EliteDesk 800 G4 Mini PC (Business lot)", "Desktop Computers", "HP", "EliteDesk 800 G4", 54, "Good",
     "Fully working (verified inspection)", "verified_inspection", 14499, 60000, "Delhi", 12, (60, 60, 70), 4, False,
     [], {"CPU": "Intel i5-8500T", "RAM": "8 GB", "SSD": "256 GB"}),
    (4, "Dell P2419H 24\" IPS Monitor", "Monitors", "Dell", "P2419H", 48, "Good",
     "Fully working (verified inspection)", "verified_inspection", 6999, 14500, "Delhi", 8, (20, 25, 30), 6, False,
     ["Light marks on stand"], {"Size": "24 inch", "Panel": "IPS 1080p", "Ports": "HDMI, DP, VGA"}),
    (1, "Sony Bravia 43\" 4K Smart TV", "Televisions", "Sony", "KD-43X74K", 22, "Excellent",
     "Fully working (seller reported)", "user_reported", 27999, 49990, "Mumbai", 1, (15, 15, 20), 2, True,
     [], {"Size": "43 inch", "Resolution": "4K UHD", "OS": "Google TV"}),
    (3, "Apple 20W USB-C Power Adapter (Original)", "Chargers and Adapters", "Apple", "MHJ83HN/A", 14, "Excellent",
     "Fully working (verified inspection)", "verified_inspection", 899, 1900, "Bengaluru", 25, (235, 235, 235), 7, False,
     [], {"Output": "20W USB-C PD"}),
    (2, "Sony WH-1000XM4 Noise Cancelling Headphones", "Audio Devices", "Sony", "WH-1000XM4", 34, "Good",
     "Fully working (seller tested)", "seller_tested", 11999, 29990, "Kochi", 1, (25, 25, 30), 1, False,
     ["Ear cushions slightly worn"], {"Type": "Over-ear, wireless", "Battery": "~25 hrs"}),
    (0, "Logitech MX Master 3 Wireless Mouse", "Computer Accessories", "Logitech", "MX Master 3", 20, "Excellent",
     "Fully working (seller reported)", "user_reported", 4499, 9995, "Bengaluru", 1, (60, 65, 75), 9, False,
     [], {"Connectivity": "Bluetooth / USB receiver"}),
    (4, "Raspberry Pi 4 Model B 4GB (tested)", "Electronic Components", "Raspberry Pi", "4 Model B", 30, "Good",
     "Fully working (seller tested)", "seller_tested", 3999, 5500, "Delhi", 5, (40, 140, 70), 3, False,
     [], {"RAM": "4 GB", "Includes": "Case + heatsinks"}),
    (1, "Sony PlayStation 5 Disc Edition + 2 Controllers", "Gaming Consoles", "Sony", "PS5 CFI-1108A", 36, "Good",
     "Fully working (seller reported)", "user_reported", 33999, 49990, "Mumbai", 1, (240, 240, 245), 0, True,
     ["Controller has light stick wear"], {"Storage": "825 GB", "Includes": "2 DualSense controllers"}),
    (2, "OnePlus Nord CE 2 – For Repair (screen cracked)", "Smartphones", "OnePlus", "Nord CE 2", 40,
     "For Parts / Repair", "Partially working", "user_reported", 2999, 23999, "Kochi", 1, (90, 120, 160), 2, False,
     ["Cracked screen", "Touch unresponsive in top area"], {"Storage": "128 GB"}),
    (3, "Lenovo ThinkPad T480 – Refurbished Grade A", "Laptops", "Lenovo", "ThinkPad T480", 66, "Excellent",
     "Fully working (verified inspection)", "verified_inspection", 21499, 90000, "Bengaluru", 10, (25, 25, 25), 8, False,
     [], {"CPU": "Intel i5-8250U", "RAM": "8 GB", "SSD": "256 GB"}),
    (0, "Canon EOS 1500D DSLR with 18-55mm lens", "Other Electronics", "Canon", "EOS 1500D", 44, "Good",
     "Fully working (seller reported)", "user_reported", 19999, 34995, "Bengaluru", 1, (30, 30, 30), 12, False,
     ["Minor wear on grip"], {"Sensor": "24.1 MP APS-C", "Shutter count": "~11,000"}),
]


def _font(size: int):
    for name in ("DejaVuSans-Bold.ttf", "Arial Bold.ttf", "arialbd.ttf", "Helvetica.ttc"):
        try:
            return ImageFont.truetype(name, size)
        except OSError:
            continue
    return ImageFont.load_default()


def _shade(c, f):
    return tuple(max(0, min(255, int(v * f))) for v in c)


def render_product_image(category: str, color, label: str, variant: int, path) -> None:
    """Draw a clean studio-style product illustration."""
    W, H = 900, 680
    bgs = [((236, 247, 240), (255, 255, 255)), ((240, 244, 248), (252, 253, 255)), ((246, 243, 236), (255, 255, 252))]
    top, bot = bgs[variant % 3]
    img = Image.new("RGB", (W, H))
    d = ImageDraw.Draw(img)
    for y in range(H):
        t = y / H
        d.line([(0, y), (W, y)], fill=tuple(int(top[i] * (1 - t) + bot[i] * t) for i in range(3)))
    # soft shadow layer
    shadow = Image.new("L", (W, H), 0)
    sd = ImageDraw.Draw(shadow)
    sd.ellipse([W * 0.2, H * 0.80, W * 0.8, H * 0.90], fill=90)
    shadow = shadow.filter(ImageFilter.GaussianBlur(18))
    img.paste((0, 0, 0), mask=shadow.point(lambda v: v // 2))
    d = ImageDraw.Draw(img)
    c, dark, light = color, _shade(color, 0.6), _shade(color, 1.35)
    screen = (18, 24, 32)
    glow = [(34, 197, 94), (14, 165, 233), (168, 85, 247)][variant % 3]
    cx, cy = W // 2, int(H * 0.47)

    def screen_grad(box):
        x0, y0, x1, y1 = [int(v) for v in box]
        for y in range(y0, y1):
            t = (y - y0) / max(1, y1 - y0)
            d.line([(x0, y), (x1, y)], fill=tuple(int(screen[i] * (1 - t) + glow[i] * 0.55 * t) for i in range(3)))

    cat = category
    if cat in ("Smartphones", "Tablets"):
        w, h = (190, 380) if cat == "Smartphones" else (330, 430)
        if variant == 1:
            d.rounded_rectangle([cx - w / 2, cy - h / 2, cx + w / 2, cy + h / 2], 34, fill=c, outline=dark, width=4)
            d.rounded_rectangle([cx - w / 2 + 22, cy - h / 2 + 22, cx - w / 2 + 92, cy - h / 2 + 112], 20, fill=dark)
            for i, (ox, oy) in enumerate([(40, 45), (40, 88), (72, 66)]):
                d.ellipse([cx - w / 2 + ox - 14, cy - h / 2 + oy - 14, cx - w / 2 + ox + 14, cy - h / 2 + oy + 14], fill=(20, 20, 25), outline=light, width=2)
        else:
            d.rounded_rectangle([cx - w / 2, cy - h / 2, cx + w / 2, cy + h / 2], 34, fill=dark)
            screen_grad([cx - w / 2 + 10, cy - h / 2 + 12, cx + w / 2 - 10, cy + h / 2 - 12])
            d.rounded_rectangle([cx - 30, cy - h / 2 + 18, cx + 30, cy - h / 2 + 32], 7, fill=(5, 5, 8))
            d.text((cx, cy), "12:30", fill=(240, 255, 245), font=_font(44), anchor="mm")
    elif cat in ("Laptops",):
        sw, sh = 520, 320
        d.rounded_rectangle([cx - sw / 2, cy - sh / 2 - 40, cx + sw / 2, cy + sh / 2 - 40], 16, fill=dark)
        screen_grad([cx - sw / 2 + 14, cy - sh / 2 - 26, cx + sw / 2 - 14, cy + sh / 2 - 54])
        d.polygon([(cx - sw / 2 - 40, cy + sh / 2 - 30), (cx + sw / 2 + 40, cy + sh / 2 - 30),
                   (cx + sw / 2 + 70, cy + sh / 2 + 10), (cx - sw / 2 - 70, cy + sh / 2 + 10)], fill=c)
        d.rectangle([cx - sw / 2 - 70, cy + sh / 2 + 10, cx + sw / 2 + 70, cy + sh / 2 + 22], fill=dark)
        d.rounded_rectangle([cx - 60, cy + sh / 2 - 22, cx + 60, cy + sh / 2 + 4], 4, fill=_shade(c, 0.85))
    elif cat in ("Monitors", "Televisions", "Desktop Computers"):
        sw, sh = (600, 340) if cat == "Televisions" else (500, 300)
        d.rounded_rectangle([cx - sw / 2, cy - sh / 2 - 30, cx + sw / 2, cy + sh / 2 - 30], 10, fill=(15, 15, 18))
        screen_grad([cx - sw / 2 + 10, cy - sh / 2 - 20, cx + sw / 2 - 10, cy + sh / 2 - 40])
        if cat == "Televisions":
            d.polygon([(cx - 200, cy + sh / 2 - 30), (cx - 230, cy + sh / 2 + 40), (cx - 210, cy + sh / 2 + 40)], fill=dark)
            d.polygon([(cx + 200, cy + sh / 2 - 30), (cx + 230, cy + sh / 2 + 40), (cx + 210, cy + sh / 2 + 40)], fill=dark)
        else:
            d.rectangle([cx - 18, cy + sh / 2 - 30, cx + 18, cy + sh / 2 + 30], fill=dark)
            d.rounded_rectangle([cx - 110, cy + sh / 2 + 30, cx + 110, cy + sh / 2 + 46], 8, fill=dark)
        if cat == "Desktop Computers":
            d.rounded_rectangle([cx + sw / 2 - 40, cy + 40, cx + sw / 2 + 120, cy + sh / 2 + 46], 10, fill=c, outline=dark, width=3)
            d.ellipse([cx + sw / 2 + 30, cy + 70, cx + sw / 2 + 50, cy + 90], fill=glow)
    elif cat == "Gaming Consoles":
        d.rounded_rectangle([cx - 90, cy - 220, cx + 90, cy + 200], 60, fill=c, outline=_shade(c, 0.8), width=4)
        d.rounded_rectangle([cx - 28, cy - 200, cx + 28, cy + 180], 22, fill=(20, 20, 25))
        d.ellipse([cx + 150, cy + 80, cx + 330, cy + 190], fill=_shade(c, 0.95), outline=dark, width=3)
        d.ellipse([cx + 180, cy + 115, cx + 210, cy + 145], fill=(30, 30, 30))
        d.ellipse([cx + 270, cy + 115, cx + 300, cy + 145], fill=(30, 30, 30))
    elif cat == "Audio Devices":
        d.arc([cx - 190, cy - 230, cx + 190, cy + 150], 190, 350, fill=c, width=34)
        for sx in (-1, 1):
            d.rounded_rectangle([cx + sx * 180 - 70, cy - 20, cx + sx * 180 + 70, cy + 170], 50, fill=c, outline=dark, width=4)
            d.rounded_rectangle([cx + sx * 180 - 45, cy + 10, cx + sx * 180 + 45, cy + 140], 36, fill=dark)
    elif cat == "Chargers and Adapters":
        d.rounded_rectangle([cx - 110, cy - 110, cx + 110, cy + 110], 30, fill=c, outline=_shade(c, 0.8), width=4)
        d.rounded_rectangle([cx - 40, cy - 10, cx + 40, cy + 10], 8, fill=(60, 60, 60))
        d.rectangle([cx - 60, cy - 190, cx - 40, cy - 110], fill=(180, 180, 185))
        d.rectangle([cx + 40, cy - 190, cx + 60, cy - 110], fill=(180, 180, 185))
        d.line([(cx, cy + 110), (cx + 60, cy + 200), (cx + 220, cy + 210)], fill=(230, 230, 230), width=14)
    elif cat == "Computer Accessories":
        d.rounded_rectangle([cx - 110, cy - 190, cx + 110, cy + 190], 110, fill=c, outline=dark, width=4)
        d.line([(cx, cy - 190), (cx, cy - 40)], fill=dark, width=5)
        d.rounded_rectangle([cx - 14, cy - 140, cx + 14, cy - 80], 10, fill=dark)
    elif cat == "Electronic Components":
        d.rounded_rectangle([cx - 260, cy - 170, cx + 260, cy + 170], 18, fill=c)
        for i in range(0, 520, 26):
            d.rectangle([cx - 250 + i, cy - 165, cx - 242 + i, cy - 150], fill=(212, 175, 55))
        d.rectangle([cx - 80, cy - 70, cx + 60, cy + 70], fill=(30, 30, 30))
        d.rectangle([cx + 120, cy - 120, cx + 240, cy - 40], fill=(190, 190, 195))
        d.rectangle([cx + 120, cy + 20, cx + 240, cy + 100], fill=(190, 190, 195))
        for i in range(8):
            d.line([(cx - 230, cy - 100 + i * 25), (cx - 100, cy - 100 + i * 25)], fill=_shade(c, 1.4), width=3)
    else:  # camera / other
        d.rounded_rectangle([cx - 230, cy - 130, cx + 230, cy + 150], 30, fill=c)
        d.rounded_rectangle([cx - 100, cy - 175, cx + 40, cy - 120], 12, fill=c)
        d.ellipse([cx - 120, cy - 100, cx + 120, cy + 140], fill=(25, 25, 28), outline=(90, 90, 95), width=10)
        d.ellipse([cx - 70, cy - 50, cx + 70, cy + 90], fill=_shade(glow, 0.5))
        d.ellipse([cx - 30, cy - 10, cx + 0, cy + 20], fill=(230, 240, 255))

    d.text((40, H - 50), label, fill=(70, 90, 80), font=_font(22))
    d.text((W - 40, 36), "Punarth AI", fill=(22, 163, 74), font=_font(20), anchor="ra")
    img.save(path, quality=92)


def seed_if_empty() -> bool:
    db.init_db()
    if db.q1("SELECT COUNT(*) c FROM users")["c"] > 0:
        return False
    rnd = random.Random(7)
    user_ids = []
    for name, email, atype, biz, city, verified in USERS:
        u = auth.register(name, email, DEMO_PASSWORD, atype, city=city, phone="98" + str(rnd.randint(10000000, 99999999)),
                          business_name=biz)
        db.execute("UPDATE users SET verified=? WHERE id=?", (verified, u["id"]))
        user_ids.append(u["id"])
    for name, ptype, city, rating, authorized, desc in PARTNERS:
        db.execute("INSERT INTO partners (name,type,city,phone,rating,authorized,description) VALUES (?,?,?,?,?,?,?)",
                   (name, ptype, city, "080-4" + str(rnd.randint(1000000, 9999999)), rating, authorized, desc))
    for (si, title, cat, brand, model, age, cond, func, src, price, orig, loc, qty, color, days, featured,
         defects, specs) in LISTINGS:
        lid = marketplace.create_listing(user_ids[si], {
            "title": title, "category": cat, "brand": brand, "model": model, "age_months": age,
            "condition": cond, "functionality_status": func, "functionality_source": src,
            "description": _description(cat, cond, func, defects, specs), "price": price,
            "original_price": orig, "location": loc, "quantity": qty, "defects": defects, "specs": specs,
            "delivery_options": "delivery,pickup" if cat != "Televisions" else "delivery,pickup",
            "provenance": {"title": "user", "description": "user", "condition": "user", "price": "user"},
        })
        paths = []
        for v in range(3):
            p = config.IMAGE_DIR / f"seed_{lid}_{v}.jpg"
            render_product_image(cat, color, f"{brand} {model}", v, p)
            paths.append(str(p))
        marketplace.add_images(lid, paths)
        created = (marketplace._utcnow() - timedelta(days=days, hours=rnd.randint(0, 20))).isoformat()
        views = rnd.randint(12, 340)
        featured_until = (marketplace._utcnow() + timedelta(days=5)).isoformat() if featured else ""
        db.execute("UPDATE listings SET created_at=?, updated_at=?, views=?, is_featured=?, featured_until=? WHERE id=?",
                   (created, created, views, 1 if featured else 0, featured_until, lid))
    # Sample Q&A
    db.execute("INSERT INTO questions (listing_id,asker_id,question,answer,created_at,answered_at) VALUES (?,?,?,?,?,?)",
               (1, user_ids[1], "Is the battery original? Any repairs done?",
                "Yes, original battery at 86% health. Never repaired.", db.now(), db.now()))
    db.execute("INSERT INTO questions (listing_id,asker_id,question,created_at) VALUES (?,?,?,?)",
               (3, user_ids[0], "Does it come with a charger and any warranty?", db.now()))
    return True


def _description(cat, cond, func, defects, specs) -> str:
    lines = [f"{cond} condition. {catalog.CONDITION_DESCRIPTIONS[cond]}",
             f"Functionality: {func}."]
    if defects:
        lines.append("Known defects: " + "; ".join(defects) + ".")
    if specs:
        lines.append("Specs: " + ", ".join(f"{k}: {v}" for k, v in specs.items()) + ".")
    return "\n".join(lines)


if __name__ == "__main__":
    print("Seeded" if seed_if_empty() else "Database already has data", "→", config.DB_PATH)
    print(json.dumps(marketplace.marketplace_stats(), indent=2))
