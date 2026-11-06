"""Device Assessment + AI Segregation + Recovery Intelligence.

Turns (category, questionnaire answers, optional image findings) into:
  * a standard condition grade
  * a functionality status (never "fully working" from an image alone)
  * a recovery classification (Reusable / Repairable / Refurbishable /
    Recyclable / Hazardous / Requires Manual Inspection) with reasons
  * an estimated resale value range and a suggested listing price
  * recovery recommendations connected to the marketplace
"""
from __future__ import annotations

import json

from . import catalog, db

CLASSIFICATIONS = ["Reusable", "Repairable", "Refurbishable", "Recyclable", "Hazardous",
                   "Requires Manual Inspection"]

CLASSIFICATION_COLORS = {
    "Reusable": "#16a34a", "Repairable": "#d97706", "Refurbishable": "#0891b2",
    "Recyclable": "#7c3aed", "Hazardous": "#dc2626", "Requires Manual Inspection": "#64748b",
}

BODY_LEVELS = catalog.COMMON_QUESTIONS[3]["options"]  # body_damage options, best→worst


def _yn(answers: dict, key: str) -> str:
    v = str(answers.get(key, "unsure")).strip().lower()
    return v if v in ("yes", "no", "unsure") else "unsure"


def _num(answers: dict, key: str, default: float = 0) -> float:
    try:
        return max(0.0, float(answers.get(key, default) or 0))
    except (TypeError, ValueError):
        return default


def nice_price(value: float) -> int:
    """Round to a marketplace-friendly price (…49 / …99 style)."""
    if value <= 0:
        return 0
    if value < 200:
        return int(max(9, round(value / 10) * 10 - 1))
    if value < 2000:
        return int(round(value / 50) * 50 - 1)
    return int(round(value / 100) * 100 - 1)


def estimate_value(category: str, brand: str, answers: dict, grade: str,
                   classification: str) -> dict:
    """Return dict(base_new, working_value, low, high, suggested, basis)."""
    original = _num(answers, "original_price")
    if original > 0:
        base = original
        basis = "your original purchase price"
    else:
        base = catalog.CATEGORY_BASE_PRICE.get(category, 5000) * catalog.PREMIUM_BRANDS.get(brand, 1.0)
        basis = f"typical new price for {brand + ' ' if brand and brand != 'Other' else ''}{category.lower()}"

    age_years = _num(answers, "age_months") / 12.0
    retention = catalog.YEARLY_RETENTION.get(category, 0.75)
    age_factor = max(0.08, retention ** age_years)
    working_value = base * age_factor

    if classification == "Hazardous":
        return {"base_new": round(base), "working_value": round(working_value), "low": 0, "high": 0,
                "suggested": 0, "basis": basis,
                "note": "Hazardous devices cannot be resold. Use authorised recycling."}
    if classification == "Recyclable":
        scrap = base * 0.03
        return {"base_new": round(base), "working_value": round(working_value),
                "low": int(scrap * 0.7), "high": int(scrap * 1.2), "suggested": 0, "basis": basis,
                "note": "Estimated material recovery value through an authorised recycler."}

    value = working_value * catalog.CONDITION_MULTIPLIER.get(grade, 0.6)
    adj = 1.0
    battery = str(answers.get("battery_health", ""))
    if battery.startswith("70"):
        adj -= 0.05
    elif battery.startswith("Below"):
        adj -= 0.12
    acc = str(answers.get("accessories", ""))
    if acc.startswith("Original box"):
        adj += 0.04
    elif acc.startswith("Device only"):
        adj -= 0.05
    if _yn(answers, "liquid_damage") == "yes":
        adj -= 0.15
    for q in catalog.questions_for(category):
        if q["kind"] == "yesno" and not q.get("critical") and not q.get("hazard") \
                and q["key"] not in catalog.NEGATIVE_YES_KEYS and _yn(answers, q["key"]) == "no":
            adj -= 0.04
    if _yn(answers, "overheats") == "yes":
        adj -= 0.10
    value *= max(0.3, adj)

    low, high = value * 0.88, value * 1.08
    return {"base_new": round(base), "working_value": round(working_value),
            "low": int(low), "high": int(high), "suggested": nice_price(value * 0.97),
            "basis": basis, "note": ""}


def assess(category: str, answers: dict, brand: str = "", model: str = "",
           image_findings: dict | None = None) -> dict:
    """Run assessment + segregation. Pure function (no DB writes)."""
    image_findings = image_findings or {}
    questions = catalog.questions_for(category)
    reasons: list[str] = []
    warnings: list[str] = []

    hazards = [q for q in questions if q.get("hazard") and _yn(answers, q["key"]) == "yes"]
    critical = [q for q in questions if q.get("critical") and q["key"] != "powers_on"]
    critical_fail = [q for q in critical if _yn(answers, q["key"]) == "no"]
    critical_unsure = [q for q in critical if _yn(answers, q["key"]) == "unsure"]
    powers = _yn(answers, "powers_on")
    body_opt = str(answers.get("body_damage", BODY_LEVELS[1]))
    body = BODY_LEVELS.index(body_opt) if body_opt in BODY_LEVELS else 1
    age_years = _num(answers, "age_months") / 12.0
    liquid = _yn(answers, "liquid_damage") == "yes"
    battery = str(answers.get("battery_health", ""))

    ai_defects = [d for d in image_findings.get("defects", []) if d.get("confidence", 0) >= 0.55]

    # Rough value of the item if it were working (decides repair-vs-recycle)
    base_guess = estimate_value(category, brand, answers, "Good", "Reusable")["working_value"]

    # ---------------- AI Segregation ----------------
    if hazards:
        classification = "Hazardous"
        for q in hazards:
            reasons.append(f"Safety risk reported: {q['text'].rstrip('?')}.")
        reasons.append("Damaged lithium batteries and exposed wiring can catch fire; "
                       "only authorised e-waste handlers should take this device.")
    elif powers == "unsure" or len(critical_unsure) >= 2:
        classification = "Requires Manual Inspection"
        reasons.append("Key functions could not be confirmed. A partner inspection is "
                       "needed before deciding resale, repair or recycling.")
    elif powers == "no":
        if body >= 4 or liquid or age_years > 8 or base_guess < 800:
            classification = "Recyclable"
            reasons.append("Device does not power on and repair is unlikely to be worthwhile "
                           f"(age {age_years:.1f} yrs, condition '{body_opt}'"
                           f"{', liquid damage' if liquid else ''}).")
        else:
            classification = "Repairable"
            reasons.append("Device does not power on, but its age and body condition make "
                           "repair worthwhile.")
    elif len(critical_fail) >= 3 or (body >= 4 and critical_fail):
        if age_years > 6 or base_guess < 1500:
            classification = "Recyclable"
            reasons.append("Multiple core functions fail and the repaired value would be low.")
        else:
            classification = "Repairable"
            reasons.append("Multiple core functions fail, but the device is worth repairing.")
    elif critical_fail:
        if base_guess < 500:
            classification = "Recyclable"
            reasons.append("A core function fails and the item's value is too low to repair.")
        else:
            classification = "Repairable"
            reasons.append("Repair needed: " + ", ".join(
                q["text"].rstrip("?").lower() for q in critical_fail) + " — answered 'no'.")
    elif body >= 3 or battery.startswith("Below") or liquid or (body == 2 and age_years > 4):
        classification = "Refurbishable"
        if body >= 3:
            reasons.append(f"Works, but body shows '{body_opt.lower()}'. Refurbishment restores value.")
        if battery.startswith("Below"):
            reasons.append("Battery health is low — a battery replacement adds resale value.")
        if liquid:
            reasons.append("Past liquid damage: a refurbishment check is recommended.")
        if body == 2 and age_years > 4:
            reasons.append("Older device with visible wear — good candidate for refurbishment.")
    else:
        classification = "Reusable"
        reasons.append("Powers on and all core functions were reported working.")

    if ai_defects and classification == "Reusable":
        warnings.append("The image check flagged possible visible defects: " +
                        ", ".join(d["label"] for d in ai_defects) +
                        ". Please inspect the device and describe them in the listing.")
    if _yn(answers, "account_removed") == "no" or _yn(answers, "storage_wiped") == "no":
        warnings.append("Remove your accounts and wipe personal data before selling.")

    # ---------------- Condition grade ----------------
    if classification in ("Hazardous", "Recyclable") or powers == "no" or critical_fail:
        grade = "For Parts / Repair"
    else:
        acc = str(answers.get("accessories", ""))
        grade = {0: "Like New" if (age_years <= 0.75 and acc.startswith("Original box")) else "Excellent",
                 1: "Excellent", 2: "Good", 3: "Fair", 4: "For Parts / Repair"}[body]
        caps = []
        if battery.startswith("70"):
            caps.append("Good")
        if battery.startswith("Below") or liquid:
            caps.append("Fair")
        if ai_defects:
            caps.append("Good")
        for cap in caps:
            if catalog.CONDITIONS.index(grade) < catalog.CONDITIONS.index(cap):
                grade = cap

    # ---------------- Functionality (never from image alone) ----------------
    if powers == "no":
        functional = "Not working"
    elif critical_fail:
        functional = "Partially working"
    elif powers == "unsure" or critical_unsure:
        functional = "Not tested"
    else:
        functional = "Fully working (seller reported)"

    answered = sum(1 for q in questions if str(answers.get(q["key"], "")).strip() not in ("", "unsure"))
    confidence = round(min(0.95, 0.45 + 0.5 * answered / max(1, len(questions))) -
                       (0.1 if ai_defects and classification == "Reusable" else 0), 2)

    value = estimate_value(category, brand, answers, grade, classification)
    defects = [{"label": q["text"].rstrip("?"), "source": "user"} for q in critical_fail]
    if body >= 2:
        defects.append({"label": body_opt, "source": "user"})
    if battery.startswith("Below"):
        defects.append({"label": "Battery health below 70%", "source": "user"})
    defects += [{"label": d["label"], "source": "ai_image", "confidence": d.get("confidence")}
                for d in ai_defects]

    return {
        "category": category, "brand": brand, "model": model,
        "grade": grade, "functional_status": functional,
        "classification": classification, "confidence": confidence,
        "reasons": reasons, "warnings": warnings, "defects": defects,
        "value": value, "recommendations": recommendations(classification),
        "can_list": can_list(classification),
        "list_as_for_repair": classification in ("Repairable", "Refurbishable"),
    }


def can_list(classification: str) -> bool:
    """Hazardous devices must never reach ordinary consumer resale. Recyclable
    devices are routed to recyclers instead of the marketplace."""
    return classification in ("Reusable", "Repairable", "Refurbishable", "Requires Manual Inspection")


def recommendations(classification: str) -> list[dict]:
    """Recovery pathways. `action` maps to a button in the UI."""
    R = {
        "Reusable": [
            {"title": "Sell on Punarth AI Marketplace", "action": "create_listing",
             "text": "List it in minutes with an AI-filled listing and suggested price."},
            {"title": "Reuse", "action": "info",
             "text": "Hand it down within your family or organisation to extend its life."},
            {"title": "Donate", "action": "donate",
             "text": "Donate to schools or NGOs through a Punarth AI collection partner."},
            {"title": "Transfer to a buyer", "action": "create_listing",
             "text": "Already have a buyer? Create a listing and share it with them."},
        ],
        "Repairable": [
            {"title": "Repair", "action": "repair",
             "text": "Most faults found are commonly repaired by service centres."},
            {"title": "Find a Repair Partner", "action": "repair",
             "text": "Book a nearby verified repair partner."},
            {"title": "Estimate Repair Cost", "action": "repair_estimate",
             "text": "See a typical repair cost range for this fault."},
            {"title": "Reassess After Repair", "action": "rescan",
             "text": "Scan again after repair to unlock a higher resale price."},
            {"title": "List as 'For Repair'", "action": "create_listing",
             "text": "Sell as-is to repairers and hobbyists, clearly marked For Repair."},
        ],
        "Refurbishable": [
            {"title": "Refurbishment", "action": "refurbish",
             "text": "Professional cleaning, part and battery replacement and testing."},
            {"title": "Refurbishment Partner", "action": "refurbish",
             "text": "Send to a partner who can refurbish and resell it."},
            {"title": "Estimated Refurbished Value", "action": "refurb_value",
             "text": "See what it could sell for after refurbishment."},
            {"title": "Create Refurbishment Request", "action": "refurbish",
             "text": "Request a pickup for refurbishment."},
        ],
        "Recyclable": [
            {"title": "Authorised Recycling", "action": "recycle",
             "text": "CPCB-authorised recyclers recover metals and handle toxic parts safely."},
            {"title": "Collection Request", "action": "recycle",
             "text": "Book a free doorstep e-waste collection."},
            {"title": "Recycling Partner", "action": "recycle",
             "text": "Choose an authorised recycler near you."},
            {"title": "Recovery Report", "action": "recovery_report",
             "text": "Get a report of materials recovered and CO₂ avoided."},
        ],
        "Hazardous": [
            {"title": "Stop using and isolate the device", "action": "info",
             "text": "Keep it away from heat and flammable items. Do not charge or puncture it."},
            {"title": "Authorised Hazardous E-waste Collection", "action": "recycle",
             "text": "Only authorised handlers should collect it. It cannot be listed for resale."},
        ],
        "Requires Manual Inspection": [
            {"title": "Book a Partner Inspection", "action": "inspection",
             "text": "A technician will test the device and confirm the right pathway."},
            {"title": "Answer again after testing", "action": "rescan",
             "text": "Test the device yourself and redo the assessment."},
            {"title": "List as 'Not tested'", "action": "create_listing",
             "text": "You may list it, clearly marked as untested, with condition For Parts / Repair."},
        ],
    }
    return R[classification]


REPAIR_COSTS = {  # typical INR ranges for common faults
    "screen_ok": (1500, 9000), "touch_ok": (1200, 6000), "cameras_ok": (800, 4000),
    "charging_ok": (400, 1500), "calls_ok": (500, 2000), "keyboard_ok": (1500, 5000),
    "ports_ok": (600, 3000), "boots_os": (800, 6000), "backlight_ok": (1500, 7000),
    "sound_ok": (800, 3000), "output_ok": (200, 600), "cable_ok": (150, 400),
    "both_channels": (400, 2000), "pairing_ok": (500, 1500), "works_ok": (300, 1500),
    "all_buttons": (300, 1200), "controllers_ok": (1000, 3500), "main_function_ok": (500, 3000),
    "powers_on": (800, 5000), "tested": (0, 0), "pins_ok": (300, 2000),
}


def repair_estimate(category: str, answers: dict) -> dict:
    low = high = 0
    items = []
    for q in catalog.questions_for(category):
        if q.get("critical") and _yn(answers, q["key"]) == "no":
            lo, hi = REPAIR_COSTS.get(q["key"], (500, 3000))
            items.append((q["text"].rstrip("?"), lo, hi))
            low += lo
            high += hi
    if str(answers.get("battery_health", "")).startswith("Below"):
        items.append(("Battery replacement", 900, 3500))
        low += 900
        high += 3500
    return {"items": items, "low": low, "high": high}


def refurbished_value(category: str, brand: str, answers: dict) -> int:
    return estimate_value(category, brand, answers, "Excellent", "Reusable")["suggested"]


def environmental_impact(category: str) -> dict:
    """Approximate e-waste and CO₂ avoided by reuse (kg). Indicative figures."""
    weights = {"Smartphones": (0.2, 55), "Laptops": (2.0, 300), "Tablets": (0.5, 100),
               "Desktop Computers": (8.0, 550), "Monitors": (5.0, 380), "Televisions": (12.0, 600),
               "Chargers and Adapters": (0.15, 4), "Audio Devices": (0.3, 15),
               "Computer Accessories": (0.4, 10), "Electronic Components": (0.3, 30),
               "Gaming Consoles": (3.5, 120), "Other Electronics": (1.0, 40)}
    kg, co2 = weights.get(category, (1.0, 40))
    return {"ewaste_kg": kg, "co2_kg": co2}


def save_assessment(user_id: int, result: dict, answers: dict, detection: dict | None,
                    image_path: str = "") -> int:
    v = result["value"]
    return db.execute(
        "INSERT INTO assessments (user_id,category,brand,model,detection_json,answers_json,grade,"
        "functional_status,classification,confidence,reasons_json,defects_json,est_low,est_high,"
        "suggested_price,image_path,created_at) VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)",
        (user_id, result["category"], result["brand"], result["model"], json.dumps(detection or {}),
         json.dumps(answers), result["grade"], result["functional_status"], result["classification"],
         result["confidence"], json.dumps(result["reasons"] + result["warnings"]),
         json.dumps(result["defects"]), v["low"], v["high"], v["suggested"], image_path, db.now()),
    )


def get_assessment(assessment_id: int) -> dict | None:
    return db.row_to_dict(db.q1("SELECT * FROM assessments WHERE id=?", (assessment_id,)))


def user_assessments(user_id: int) -> list[dict]:
    return [db.row_to_dict(r) for r in
            db.q("SELECT * FROM assessments WHERE user_id=? ORDER BY id DESC", (user_id,))]
