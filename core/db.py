"""SQLite storage. One connection per thread; WAL mode so the desktop app and the
payment server can share the database file during a local demo."""
from __future__ import annotations

import json
import sqlite3
import threading
from contextlib import contextmanager
from datetime import datetime, timezone
from pathlib import Path

from . import config

_local = threading.local()
_db_path: Path = config.DB_PATH

SCHEMA = """
CREATE TABLE IF NOT EXISTS users (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    name TEXT NOT NULL,
    email TEXT NOT NULL UNIQUE,
    password_hash TEXT NOT NULL,
    salt TEXT NOT NULL,
    account_type TEXT NOT NULL CHECK (account_type IN ('common','industry')),
    business_name TEXT DEFAULT '',
    phone TEXT DEFAULT '',
    city TEXT DEFAULT '',
    verified INTEGER DEFAULT 0,
    seller_plan TEXT DEFAULT 'free',
    plan_until TEXT DEFAULT '',
    created_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS assessments (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id INTEGER NOT NULL REFERENCES users(id),
    category TEXT NOT NULL,
    brand TEXT DEFAULT '',
    model TEXT DEFAULT '',
    detection_json TEXT DEFAULT '{}',
    answers_json TEXT DEFAULT '{}',
    grade TEXT,
    functional_status TEXT,
    classification TEXT,
    confidence REAL,
    reasons_json TEXT DEFAULT '[]',
    defects_json TEXT DEFAULT '[]',
    est_low INTEGER, est_high INTEGER, suggested_price INTEGER,
    image_path TEXT DEFAULT '',
    created_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS listings (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    seller_id INTEGER NOT NULL REFERENCES users(id),
    title TEXT NOT NULL,
    category TEXT NOT NULL,
    brand TEXT DEFAULT '',
    model TEXT DEFAULT '',
    age_months INTEGER DEFAULT 0,
    condition TEXT NOT NULL,
    functionality_status TEXT NOT NULL,
    functionality_source TEXT NOT NULL DEFAULT 'user_reported',
    description TEXT DEFAULT '',
    price INTEGER NOT NULL,
    original_price INTEGER DEFAULT 0,
    est_low INTEGER DEFAULT 0, est_high INTEGER DEFAULT 0, suggested_price INTEGER DEFAULT 0,
    location TEXT DEFAULT '',
    delivery_options TEXT DEFAULT 'delivery,pickup',
    quantity INTEGER NOT NULL DEFAULT 1,
    status TEXT NOT NULL DEFAULT 'active' CHECK (status IN ('draft','active','sold','removed')),
    is_featured INTEGER DEFAULT 0,
    featured_until TEXT DEFAULT '',
    for_repair INTEGER DEFAULT 0,
    specs_json TEXT DEFAULT '{}',
    defects_json TEXT DEFAULT '[]',
    ai_assessment_json TEXT DEFAULT '',
    provenance_json TEXT DEFAULT '{}',
    assessment_id INTEGER REFERENCES assessments(id),
    views INTEGER DEFAULT 0,
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_listings_status ON listings(status, category);

CREATE TABLE IF NOT EXISTS listing_images (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    listing_id INTEGER NOT NULL REFERENCES listings(id) ON DELETE CASCADE,
    path TEXT NOT NULL,
    position INTEGER DEFAULT 0
);

CREATE TABLE IF NOT EXISTS wishlist (
    user_id INTEGER NOT NULL, listing_id INTEGER NOT NULL, created_at TEXT NOT NULL,
    PRIMARY KEY (user_id, listing_id)
);

CREATE TABLE IF NOT EXISTS cart_items (
    user_id INTEGER NOT NULL, listing_id INTEGER NOT NULL, qty INTEGER NOT NULL DEFAULT 1,
    added_at TEXT NOT NULL,
    PRIMARY KEY (user_id, listing_id)
);

CREATE TABLE IF NOT EXISTS payments (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id INTEGER NOT NULL,
    purpose TEXT NOT NULL CHECK (purpose IN ('order','featured','subscription')),
    amount_paise INTEGER NOT NULL,
    currency TEXT NOT NULL DEFAULT 'INR',
    status TEXT NOT NULL DEFAULT 'created' CHECK (status IN ('created','pending','paid','failed')),
    mode TEXT DEFAULT '',
    razorpay_order_id TEXT DEFAULT '',
    razorpay_payment_id TEXT DEFAULT '',
    meta_json TEXT DEFAULT '{}',
    failure_reason TEXT DEFAULT '',
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_payments_rzp ON payments(razorpay_order_id);

CREATE TABLE IF NOT EXISTS orders (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    buyer_id INTEGER NOT NULL,
    seller_id INTEGER NOT NULL,
    payment_id INTEGER REFERENCES payments(id),
    status TEXT NOT NULL,
    subtotal INTEGER NOT NULL,
    delivery_fee INTEGER NOT NULL DEFAULT 0,
    services_fee INTEGER NOT NULL DEFAULT 0,
    total INTEGER NOT NULL,
    commission INTEGER NOT NULL DEFAULT 0,
    delivery_method TEXT NOT NULL DEFAULT 'delivery',
    address_json TEXT DEFAULT '{}',
    services_json TEXT DEFAULT '[]',
    tracking_code TEXT DEFAULT '',
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS order_items (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    order_id INTEGER NOT NULL REFERENCES orders(id),
    listing_id INTEGER NOT NULL,
    title TEXT NOT NULL,
    price INTEGER NOT NULL,
    qty INTEGER NOT NULL
);

CREATE TABLE IF NOT EXISTS order_events (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    order_id INTEGER NOT NULL,
    status TEXT NOT NULL,
    note TEXT DEFAULT '',
    created_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS questions (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    listing_id INTEGER NOT NULL,
    asker_id INTEGER NOT NULL,
    question TEXT NOT NULL,
    answer TEXT DEFAULT '',
    created_at TEXT NOT NULL,
    answered_at TEXT DEFAULT ''
);

CREATE TABLE IF NOT EXISTS messages (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    listing_id INTEGER,
    sender_id INTEGER NOT NULL,
    recipient_id INTEGER NOT NULL,
    body TEXT NOT NULL,
    is_read INTEGER DEFAULT 0,
    created_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS partners (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    name TEXT NOT NULL,
    type TEXT NOT NULL CHECK (type IN ('repair','refurbish','recycler')),
    city TEXT NOT NULL,
    phone TEXT DEFAULT '',
    rating REAL DEFAULT 4.5,
    authorized INTEGER DEFAULT 0,
    description TEXT DEFAULT ''
);

CREATE TABLE IF NOT EXISTS recovery_requests (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id INTEGER NOT NULL,
    assessment_id INTEGER,
    type TEXT NOT NULL CHECK (type IN ('repair','refurbish','recycle_collection','donate','inspection')),
    partner_id INTEGER,
    status TEXT NOT NULL DEFAULT 'Requested',
    details_json TEXT DEFAULT '{}',
    created_at TEXT NOT NULL
);
"""


def now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


def set_db_path(path) -> None:
    """Point the module at a different DB file (used by tests)."""
    global _db_path
    _db_path = Path(path)
    if getattr(_local, "conn", None) is not None:
        _local.conn.close()
        _local.conn = None


def conn() -> sqlite3.Connection:
    c = getattr(_local, "conn", None)
    if c is None or getattr(_local, "path", None) != _db_path:
        c = sqlite3.connect(_db_path, timeout=15, check_same_thread=False,
                            isolation_level=None)  # autocommit; tx() opens explicit transactions
        c.row_factory = sqlite3.Row
        c.execute("PRAGMA foreign_keys = ON")
        c.execute("PRAGMA journal_mode = WAL")
        _local.conn = c
        _local.path = _db_path
    return c


@contextmanager
def tx():
    """Transaction: commits on success, rolls back on error."""
    c = conn()
    try:
        c.execute("BEGIN IMMEDIATE")
        yield c
        c.execute("COMMIT")
    except Exception:
        c.execute("ROLLBACK")
        raise


def init_db() -> None:
    c = conn()
    c.executescript(SCHEMA)
    c.commit()


def q(sql: str, params=()) -> list[sqlite3.Row]:
    return conn().execute(sql, params).fetchall()


def q1(sql: str, params=()):
    return conn().execute(sql, params).fetchone()


def execute(sql: str, params=()) -> int:
    c = conn()
    cur = c.execute(sql, params)
    c.commit()
    return cur.lastrowid


def row_to_dict(row) -> dict | None:
    if row is None:
        return None
    d = dict(row)
    for key in list(d):
        if key.endswith("_json") and isinstance(d[key], str):
            try:
                d[key[:-5]] = json.loads(d[key]) if d[key] else None
            except json.JSONDecodeError:
                d[key[:-5]] = None
    return d
