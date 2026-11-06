"""Static marketplace knowledge: categories, condition grades, brands,
price baselines and device-specific assessment questions."""
from __future__ import annotations

CATEGORIES = [
    "Smartphones",
    "Laptops",
    "Tablets",
    "Desktop Computers",
    "Monitors",
    "Televisions",
    "Chargers and Adapters",
    "Audio Devices",
    "Computer Accessories",
    "Electronic Components",
    "Gaming Consoles",
    "Other Electronics",
]

CATEGORY_ICONS = {
    "Smartphones": "📱", "Laptops": "💻", "Tablets": "📲", "Desktop Computers": "🖥️",
    "Monitors": "🖵", "Televisions": "📺", "Chargers and Adapters": "🔌",
    "Audio Devices": "🎧", "Computer Accessories": "⌨️", "Electronic Components": "🔧",
    "Gaming Consoles": "🎮", "Other Electronics": "📦",
}

# Standardised condition labels, best to worst.
CONDITIONS = ["Like New", "Excellent", "Good", "Fair", "For Parts / Repair"]

CONDITION_DESCRIPTIONS = {
    "Like New": "No visible signs of use. No scratches, dents or marks. Usually "
                "with original accessories. Functions as reported by the seller.",
    "Excellent": "Very light signs of use that are hard to see at arm's length. "
                 "No cracks or dents. Functions as reported by the seller.",
    "Good": "Normal signs of use such as light scratches or scuffs. No cracks "
            "on the screen or body. Functions as reported by the seller.",
    "Fair": "Clearly used: noticeable scratches, dents or worn parts. May have "
            "minor non-critical issues that are listed in the defects.",
    "For Parts / Repair": "Does not fully work or has major damage. Sold for "
                          "repair, spare parts or refurbishment only.",
}

CONDITION_MULTIPLIER = {
    "Like New": 1.00, "Excellent": 0.90, "Good": 0.78, "Fair": 0.60, "For Parts / Repair": 0.22,
}

FUNCTIONALITY_STATUSES = [
    "Fully working (seller reported)",
    "Fully working (seller tested)",
    "Fully working (verified inspection)",
    "Partially working",
    "Not working",
    "Not tested",
]

FUNCTIONALITY_SOURCES = {
    "user_reported": "Reported by the seller, not independently tested",
    "seller_tested": "Tested by the seller with a checklist",
    "verified_inspection": "Checked at a Punarth AI partner inspection",
    "unknown": "Not tested",
}

BRANDS = {
    "Smartphones": ["Apple", "Samsung", "OnePlus", "Xiaomi", "Redmi", "Realme", "Vivo", "Oppo",
                    "Google", "Motorola", "Nothing", "iQOO", "Poco", "Other"],
    "Laptops": ["Apple", "Dell", "HP", "Lenovo", "Asus", "Acer", "MSI", "Microsoft", "Samsung", "Other"],
    "Tablets": ["Apple", "Samsung", "Lenovo", "Xiaomi", "Realme", "OnePlus", "Other"],
    "Desktop Computers": ["Dell", "HP", "Lenovo", "Apple", "Acer", "Asus", "Custom Build", "Other"],
    "Monitors": ["Dell", "LG", "Samsung", "BenQ", "Acer", "Asus", "ViewSonic", "HP", "Other"],
    "Televisions": ["Samsung", "LG", "Sony", "Mi", "TCL", "OnePlus", "Panasonic", "Vu", "Other"],
    "Chargers and Adapters": ["Apple", "Samsung", "Anker", "Mi", "Belkin", "Portronics", "Ambrane", "Other"],
    "Audio Devices": ["Sony", "JBL", "boAt", "Bose", "Apple", "Sennheiser", "Marshall", "Noise", "Other"],
    "Computer Accessories": ["Logitech", "HP", "Dell", "Zebronics", "Razer", "TP-Link", "SanDisk", "Other"],
    "Electronic Components": ["Raspberry Pi", "Arduino", "Intel", "AMD", "NVIDIA", "Corsair", "Kingston", "Other"],
    "Gaming Consoles": ["Sony", "Microsoft", "Nintendo", "Valve", "Other"],
    "Other Electronics": ["Philips", "Canon", "Nikon", "GoPro", "Fitbit", "Other"],
}

# Typical new price (INR) for a mid-range product in each category. Used when
# the seller does not know the original price. Premium brands get a multiplier.
CATEGORY_BASE_PRICE = {
    "Smartphones": 22000, "Laptops": 55000, "Tablets": 25000, "Desktop Computers": 45000,
    "Monitors": 12000, "Televisions": 35000, "Chargers and Adapters": 1200,
    "Audio Devices": 3500, "Computer Accessories": 1500, "Electronic Components": 4000,
    "Gaming Consoles": 40000, "Other Electronics": 5000,
}

PREMIUM_BRANDS = {"Apple": 2.4, "Google": 1.7, "Sony": 1.4, "Bose": 2.0, "Microsoft": 1.6,
                  "Samsung": 1.25, "OnePlus": 1.3, "Marshall": 1.8, "Sennheiser": 1.6,
                  "Razer": 1.5, "MSI": 1.3, "Dell": 1.1, "LG": 1.1, "Nintendo": 0.8}

# Fraction of value retained per year (exponential depreciation).
YEARLY_RETENTION = {
    "Smartphones": 0.68, "Laptops": 0.74, "Tablets": 0.72, "Desktop Computers": 0.72,
    "Monitors": 0.80, "Televisions": 0.78, "Chargers and Adapters": 0.80,
    "Audio Devices": 0.72, "Computer Accessories": 0.78, "Electronic Components": 0.75,
    "Gaming Consoles": 0.82, "Other Electronics": 0.75,
}

# Delivery
DELIVERY_FEE_STANDARD = 99
DELIVERY_FEE_LARGE = 349           # TVs, desktops, monitors
LARGE_ITEM_CATEGORIES = {"Televisions", "Desktop Computers", "Monitors"}
FREE_DELIVERY_ABOVE = 5000

CITIES = ["Bengaluru", "Mumbai", "Delhi", "Chennai", "Hyderabad", "Pune", "Kolkata",
          "Ahmedabad", "Jaipur", "Kochi", "Mysuru", "Lucknow", "Chandigarh", "Indore"]

# ---------------------------------------------------------------------------
# Assessment questions. Each question:
#   key, text, kind ("yesno" | "choice" | "number"), options (choice), weight,
#   critical (failure means the device is not fully working),
#   hazard (a "yes" answer is a safety hazard)
# Answers for yesno are "yes" / "no" / "unsure".
# ---------------------------------------------------------------------------

COMMON_QUESTIONS = [
    {"key": "age_months", "text": "How old is the device (in months)?", "kind": "number"},
    {"key": "original_price", "text": "Approximate original purchase price in ₹ (0 if unknown)",
     "kind": "number"},
    {"key": "powers_on", "text": "Does the device power on?", "kind": "yesno", "critical": True},
    {"key": "body_damage", "text": "Physical condition of the body",
     "kind": "choice",
     "options": ["No marks", "Light scratches", "Noticeable scratches / scuffs",
                 "Dents or cracks on body", "Broken parts"]},
    {"key": "battery_swollen", "text": "Is the battery swollen, bulging, or is the case lifting?",
     "kind": "yesno", "hazard": True, "applies_battery": True},
    {"key": "burn_smell_leak", "text": "Any burn marks, burning smell, leaking fluid or exposed wires?",
     "kind": "yesno", "hazard": True},
    {"key": "liquid_damage", "text": "Has the device had liquid / water damage?", "kind": "yesno"},
    {"key": "accessories", "text": "Accessories included",
     "kind": "choice", "options": ["Original box + all accessories", "Charger / key accessories only",
                                   "Device only"]},
]

CATEGORY_QUESTIONS = {
    "Smartphones": [
        {"key": "screen_ok", "text": "Is the screen free of cracks, lines and dead spots?", "kind": "yesno", "critical": True},
        {"key": "touch_ok", "text": "Does touch work across the whole screen?", "kind": "yesno", "critical": True},
        {"key": "battery_health", "text": "Battery health / backup",
         "kind": "choice", "options": ["Above 85% / full day", "70–85% / most of a day", "Below 70% / drains fast", "Unknown"]},
        {"key": "cameras_ok", "text": "Do front and rear cameras work?", "kind": "yesno", "critical": True},
        {"key": "charging_ok", "text": "Does it charge normally through the port?", "kind": "yesno", "critical": True},
        {"key": "calls_ok", "text": "Do calls, mic and speaker work?", "kind": "yesno", "critical": True},
        {"key": "biometrics_ok", "text": "Does fingerprint / face unlock work?", "kind": "yesno"},
        {"key": "account_removed", "text": "Is it factory reset with all accounts (iCloud / Google) removed?", "kind": "yesno"},
    ],
    "Laptops": [
        {"key": "screen_ok", "text": "Is the display free of cracks, lines and dead pixels?", "kind": "yesno", "critical": True},
        {"key": "keyboard_ok", "text": "Do all keys and the touchpad work?", "kind": "yesno", "critical": True},
        {"key": "battery_health", "text": "Battery backup",
         "kind": "choice", "options": ["Above 85% / full day", "70–85% / most of a day", "Below 70% / drains fast", "Unknown"]},
        {"key": "ports_ok", "text": "Do the USB / charging / display ports work?", "kind": "yesno", "critical": True},
        {"key": "hinge_ok", "text": "Are the hinges firm and undamaged?", "kind": "yesno"},
        {"key": "boots_os", "text": "Does it boot into the operating system?", "kind": "yesno", "critical": True},
        {"key": "storage_wiped", "text": "Has personal data been wiped?", "kind": "yesno"},
    ],
    "Tablets": [
        {"key": "screen_ok", "text": "Is the screen free of cracks, lines and dead spots?", "kind": "yesno", "critical": True},
        {"key": "touch_ok", "text": "Does touch work across the whole screen?", "kind": "yesno", "critical": True},
        {"key": "battery_health", "text": "Battery backup",
         "kind": "choice", "options": ["Above 85% / full day", "70–85% / most of a day", "Below 70% / drains fast", "Unknown"]},
        {"key": "charging_ok", "text": "Does it charge normally?", "kind": "yesno", "critical": True},
        {"key": "account_removed", "text": "Is it factory reset with accounts removed?", "kind": "yesno"},
    ],
    "Desktop Computers": [
        {"key": "boots_os", "text": "Does it boot into the operating system?", "kind": "yesno", "critical": True},
        {"key": "ports_ok", "text": "Do USB, display and network ports work?", "kind": "yesno", "critical": True},
        {"key": "fans_ok", "text": "Do the fans run without loud noise or overheating?", "kind": "yesno"},
        {"key": "storage_wiped", "text": "Has personal data been wiped?", "kind": "yesno"},
    ],
    "Monitors": [
        {"key": "screen_ok", "text": "Is the panel free of cracks, lines and dead pixels?", "kind": "yesno", "critical": True},
        {"key": "backlight_ok", "text": "Is brightness even, without flicker or dark patches?", "kind": "yesno", "critical": True},
        {"key": "ports_ok", "text": "Do the HDMI / DP / VGA inputs work?", "kind": "yesno", "critical": True},
        {"key": "stand_ok", "text": "Is the stand included and undamaged?", "kind": "yesno"},
    ],
    "Televisions": [
        {"key": "screen_ok", "text": "Is the panel free of cracks, lines and dead pixels?", "kind": "yesno", "critical": True},
        {"key": "backlight_ok", "text": "Is brightness even, without flicker or dark patches?", "kind": "yesno", "critical": True},
        {"key": "sound_ok", "text": "Do the built-in speakers work?", "kind": "yesno", "critical": True},
        {"key": "remote_ok", "text": "Is a working remote included?", "kind": "yesno"},
        {"key": "smart_ok", "text": "Do smart TV apps / Wi-Fi work (if a smart TV)?", "kind": "yesno"},
    ],
    "Chargers and Adapters": [
        {"key": "output_ok", "text": "Does it charge a device at normal speed?", "kind": "yesno", "critical": True},
        {"key": "cable_ok", "text": "Is the cable free of fraying, cuts or exposed wire?", "kind": "yesno", "critical": True},
        {"key": "gets_hot", "text": "Does it get unusually hot while charging?", "kind": "yesno", "hazard": True},
    ],
    "Audio Devices": [
        {"key": "both_channels", "text": "Does sound come from both left and right sides?", "kind": "yesno", "critical": True},
        {"key": "mic_ok", "text": "Does the microphone work (if it has one)?", "kind": "yesno"},
        {"key": "battery_health", "text": "Battery backup (wireless devices)",
         "kind": "choice", "options": ["Above 85% / full day", "70–85% / most of a day", "Below 70% / drains fast", "Not applicable / Unknown"]},
        {"key": "pairing_ok", "text": "Does Bluetooth pairing / the wired connector work?", "kind": "yesno", "critical": True},
    ],
    "Computer Accessories": [
        {"key": "works_ok", "text": "Does it work when connected to a computer?", "kind": "yesno", "critical": True},
        {"key": "all_buttons", "text": "Do all keys / buttons / functions work?", "kind": "yesno", "critical": True},
    ],
    "Electronic Components": [
        {"key": "tested", "text": "Has the component been tested in a working system?", "kind": "yesno", "critical": True},
        {"key": "pins_ok", "text": "Are pins / connectors straight and undamaged?", "kind": "yesno", "critical": True},
    ],
    "Gaming Consoles": [
        {"key": "boots_os", "text": "Does it boot to the home screen?", "kind": "yesno", "critical": True},
        {"key": "controllers_ok", "text": "Do the included controllers work without drift?", "kind": "yesno", "critical": True},
        {"key": "disc_ok", "text": "Does the disc drive read discs (if it has one)?", "kind": "yesno"},
        {"key": "overheats", "text": "Does it overheat or shut down during play?", "kind": "yesno"},
        {"key": "account_removed", "text": "Has your account been removed?", "kind": "yesno"},
    ],
    "Other Electronics": [
        {"key": "main_function_ok", "text": "Does the main function of the device work?", "kind": "yesno", "critical": True},
        {"key": "controls_ok", "text": "Do all buttons and controls work?", "kind": "yesno"},
    ],
}

BATTERY_CATEGORIES = {"Smartphones", "Laptops", "Tablets", "Audio Devices", "Gaming Consoles",
                      "Other Electronics"}

# Questions where a "yes" is BAD (inverted polarity)
NEGATIVE_YES_KEYS = {"battery_swollen", "burn_smell_leak", "liquid_damage", "gets_hot", "overheats"}


def questions_for(category: str) -> list[dict]:
    """Full ordered questionnaire for a device category."""
    qs = []
    for q in COMMON_QUESTIONS:
        if q.get("applies_battery") and category not in BATTERY_CATEGORIES:
            continue
        qs.append(dict(q))
    qs.extend(dict(q) for q in CATEGORY_QUESTIONS.get(category, CATEGORY_QUESTIONS["Other Electronics"]))
    return qs


# Seller plans (revenue model)
SELLER_PLANS = {
    "free": {"name": "Free", "price": 0, "listing_limit": 5, "commission": 0.08,
             "perks": ["Up to 5 active listings", "8% commission on completed sales"]},
    "pro": {"name": "Pro Seller", "price": 299, "listing_limit": 50, "commission": 0.05,
            "perks": ["Up to 50 active listings", "5% commission", "1 free featured listing / month"]},
    "business": {"name": "Business", "price": 999, "listing_limit": 100000, "commission": 0.03,
                 "perks": ["Unlimited listings", "3% commission", "Business seller badge",
                           "Bulk listing tools", "Priority refurbishment partners"]},
}
FEATURED_LISTING_PRICE = 49      # INR for 7 days
FEATURED_DAYS = 7

# Optional buyer / seller services
SERVICES = {
    "inspection": {"name": "Partner inspection before dispatch", "price": 199},
    "doorstep_pickup": {"name": "Doorstep pickup for sellers", "price": 79},
    "extended_warranty": {"name": "30-day Punarth care (buyer)", "price": 149},
}
