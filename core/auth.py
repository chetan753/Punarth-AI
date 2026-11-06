"""User accounts: registration, login (PBKDF2 password hashing), profile."""
from __future__ import annotations

import hashlib
import hmac
import re
import secrets

from . import db


class AuthError(Exception):
    pass


def _hash(password: str, salt: str) -> str:
    return hashlib.pbkdf2_hmac("sha256", password.encode(), bytes.fromhex(salt), 200_000).hex()


def register(name: str, email: str, password: str, account_type: str,
             city: str = "", phone: str = "", business_name: str = "") -> dict:
    name, email = name.strip(), email.strip().lower()
    if not name:
        raise AuthError("Please enter your name.")
    if not re.fullmatch(r"[^@\s]+@[^@\s]+\.[^@\s]+", email):
        raise AuthError("Please enter a valid email address.")
    if len(password) < 6:
        raise AuthError("Password must be at least 6 characters.")
    if account_type not in ("common", "industry"):
        raise AuthError("Choose Common User or Industry User.")
    if account_type == "industry" and not business_name.strip():
        raise AuthError("Industry users must enter a business / organisation name.")
    if db.q1("SELECT id FROM users WHERE email=?", (email,)):
        raise AuthError("An account with this email already exists.")
    salt = secrets.token_hex(16)
    plan = "business" if account_type == "industry" else "free"
    uid = db.execute(
        "INSERT INTO users (name,email,password_hash,salt,account_type,business_name,phone,city,"
        "seller_plan,created_at) VALUES (?,?,?,?,?,?,?,?,?,?)",
        (name, email, _hash(password, salt), salt, account_type, business_name.strip(),
         phone.strip(), city.strip(), plan, db.now()),
    )
    return get_user(uid)


def login(email: str, password: str) -> dict:
    row = db.q1("SELECT * FROM users WHERE email=?", (email.strip().lower(),))
    if not row or not hmac.compare_digest(row["password_hash"], _hash(password, row["salt"])):
        raise AuthError("Incorrect email or password.")
    return get_user(row["id"])


def get_user(user_id: int) -> dict | None:
    row = db.q1("SELECT id,name,email,account_type,business_name,phone,city,verified,seller_plan,"
                "plan_until,created_at FROM users WHERE id=?", (user_id,))
    return dict(row) if row else None


def update_profile(user_id: int, **fields) -> dict:
    allowed = {"name", "phone", "city", "business_name"}
    sets = {k: v for k, v in fields.items() if k in allowed}
    if sets:
        cols = ", ".join(f"{k}=?" for k in sets)
        db.execute(f"UPDATE users SET {cols} WHERE id=?", (*sets.values(), user_id))
    return get_user(user_id)


def display_name(user: dict) -> str:
    if user.get("account_type") == "industry" and user.get("business_name"):
        return user["business_name"]
    return user.get("name", "")
