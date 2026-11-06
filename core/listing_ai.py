"""AI-based listing assistance: builds an editable listing draft from a device
assessment. Every generated field is tagged so the UI can show which values
came from AI and which the seller confirmed or changed."""
from __future__ import annotations

from . import catalog

AI_FIELDS = ["title", "description", "category", "brand", "model", "condition",
             "functionality_status", "defects", "est_low", "est_high", "price", "for_repair"]


def generate_title(category: str, brand: str, model: str, grade: str, answers: dict) -> str:
    parts = [p for p in (brand if brand and brand != "Other" else "", model) if p]
    name = " ".join(parts) if parts else f"Used {category.rstrip('s').lower()}"
    if category == "Smartphones" and not model:
        name += " smartphone"
    suffix = {"For Parts / Repair": "– For Parts / Repair"}.get(grade, f"– {grade} condition")
    return f"{name} {suffix}".strip()


def generate_description(result: dict, answers: dict) -> str:
    cat, grade = result["category"], result["grade"]
    age = int(float(answers.get("age_months") or 0))
    age_txt = f"{age} months old" if age < 24 else f"about {age // 12} years old"
    lines = [f"{grade} condition {cat.lower().rstrip('s')} — {age_txt}."]
    lines.append(catalog.CONDITION_DESCRIPTIONS[grade])

    working, failing = [], []
    for q in catalog.questions_for(cat):
        if q["kind"] != "yesno" or q.get("hazard") or q["key"] in catalog.NEGATIVE_YES_KEYS:
            continue
        a = str(answers.get(q["key"], "unsure")).lower()
        label = q["text"].rstrip("?")
        if a == "yes":
            working.append(label)
        elif a == "no":
            failing.append(label)
    if working:
        lines.append("Seller reports: " + "; ".join(w[0].lower() + w[1:] for w in working[:6]) + ".")
    if failing:
        lines.append("Known issues: " + "; ".join(f[0].lower() + f[1:] for f in failing) + ".")
    bh = answers.get("battery_health")
    if bh and bh not in ("Unknown", "Not applicable / Unknown"):
        lines.append(f"Battery: {bh}.")
    acc = answers.get("accessories")
    if acc:
        lines.append(f"Included: {acc.lower()}.")
    lines.append("Functionality is as reported by the seller and has not been independently "
                 "verified unless marked 'verified inspection'.")
    return "\n".join(lines)


def draft_from_assessment(result: dict, answers: dict, location: str = "") -> dict:
    """Return listing form values + provenance map (field -> 'ai')."""
    v = result["value"]
    draft = {
        "title": generate_title(result["category"], result["brand"], result["model"],
                                result["grade"], answers),
        "description": generate_description(result, answers),
        "category": result["category"],
        "brand": result["brand"] or "",
        "model": result["model"] or "",
        "age_months": int(float(answers.get("age_months") or 0)),
        "condition": result["grade"],
        "functionality_status": result["functional_status"],
        "functionality_source": "user_reported",
        "defects": [d["label"] for d in result["defects"]],
        "price": v["suggested"],
        "original_price": int(float(answers.get("original_price") or 0)),
        "est_low": v["low"], "est_high": v["high"], "suggested_price": v["suggested"],
        "location": location,
        "for_repair": 1 if result["classification"] in ("Repairable", "Requires Manual Inspection")
        or result["grade"] == "For Parts / Repair" else 0,
        "recommended_category": result["category"],
        "ai_summary": {
            "classification": result["classification"],
            "grade": result["grade"],
            "functional_status": result["functional_status"],
            "confidence": result["confidence"],
            "reasons": result["reasons"],
            "defects": result["defects"],
            "value": v,
        },
    }
    provenance = {f: "ai" for f in AI_FIELDS}
    provenance["age_months"] = "user"          # came straight from the seller's answer
    provenance["original_price"] = "user"
    return {"values": draft, "provenance": provenance}


def resolve_provenance(ai_values: dict, final_values: dict, provenance: dict,
                       confirmed: bool) -> dict:
    """After editing: fields changed by the user become 'user'; untouched AI
    fields become 'ai_confirmed' if the seller ticked the review box."""
    out = {}
    for field, src in provenance.items():
        if src != "ai":
            out[field] = src
        elif str(ai_values.get(field)) != str(final_values.get(field)):
            out[field] = "user"
        else:
            out[field] = "ai_confirmed" if confirmed else "ai"
    return out
