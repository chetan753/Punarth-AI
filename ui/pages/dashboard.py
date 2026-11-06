"""Home dashboard for Common and Industry users."""
from __future__ import annotations

from PySide6.QtCore import Qt
from PySide6.QtWidgets import QGridLayout, QHBoxLayout, QVBoxLayout, QWidget

from core import assessment, auth, marketplace

from .. import theme
from ..widgets import (ClickableFrame, StatTile, add_shadow, badge, button, card, clear_layout, label,
                       page_container, rupees)


class DashboardPage(QWidget):
    def __init__(self, state):
        super().__init__()
        self.state = state
        sa, self.body = page_container()
        outer = QVBoxLayout(self)
        outer.setContentsMargins(0, 0, 0, 0)
        outer.addWidget(sa)

    def on_show(self, **_):
        clear_layout(self.body)
        u = self.state.user
        ind = self.state.is_industry
        hello = label(f"{'Welcome' if ind else 'Hi'}, {auth.display_name(u).split(' ')[0] if not ind else auth.display_name(u)} 👋", "h1")
        self.body.addWidget(hello)
        self.body.addWidget(label("Scan a device to get its recovery pathway and resale value, then sell, repair, "
                                  "refurbish or recycle it — all in one place.", "muted", wrap=True))

        # Hero action
        hero, hl = card("true", (26, 22, 26, 22))
        hero.setStyleSheet("QFrame { background: qlineargradient(x1:0,y1:0,x2:1,y2:0, stop:0 #064e3b, stop:1 #16a34a);"
                           " border-radius:18px; border:0; } QLabel { color:white; background:transparent; }")
        row = QHBoxLayout()
        col = QWidget()
        cl = QVBoxLayout(col)
        cl.setContentsMargins(0, 0, 0, 0)
        t = label("Place a device in front of the camera", "h2")
        cl.addWidget(t)
        cl.addWidget(label("AI identifies it, asks a few questions, decides Reuse / Repair / Refurbish / Recycle and "
                           "estimates its resale value.", wrap=True))
        row.addWidget(col, 1)
        go = button("📷  Start AI Scanner", None, lambda: self.state.go("scanner"))
        go.setStyleSheet("QPushButton { background:white; color:#065f46; border:0; padding:12px 20px; font-weight:800; }")
        row.addWidget(go)
        hl.addLayout(row)
        self.body.addWidget(hero)

        # Stats
        imp = marketplace.impact_summary(self.state.uid)
        grid = QGridLayout()
        grid.setSpacing(14)
        tiles = [StatTile("Devices assessed", str(imp["assessments"]), "🔍"),
                 StatTile("Devices resold", str(imp["devices_resold"]), "🔁"),
                 StatTile("E-waste diverted", f"{imp['ewaste_kg']} kg", "🌱", sub="from completed sales"),
                 StatTile("CO₂ avoided", f"{imp['co2_kg']} kg", "🌍", sub="estimated, vs. buying new")]
        if ind:
            st = marketplace.seller_stats(self.state.uid)
            tiles += [StatTile("Active listings", str(st["active_listings"]), "🏷️"),
                      StatTile("Pending orders", str(st["pending_orders"]), "📦"),
                      StatTile("Total sales", rupees(st["total_sales"]), "💰"),
                      StatTile("Buyer requests", str(st["buyer_requests"]), "💬")]
        for i, t in enumerate(tiles):
            grid.addWidget(t, i // 4, i % 4)
        gw = QWidget()
        gw.setLayout(grid)
        self.body.addWidget(gw)

        # Quick actions
        qa = QHBoxLayout()
        qa.setSpacing(14)
        actions = [("🛍️", "Browse marketplace", "Certified second-hand phones, laptops & more", "market_home"),
                   ("💸", "Sell a device", "AI-assisted or manual listing", "sell"),
                   ("♻️", "Recovery center", "Repair, refurbish, recycle requests", "recovery"),
                   ("📊", "Seller dashboard", "Listings, orders, revenue", "seller_dashboard")]
        for icon, title, text, page in actions:
            f = ClickableFrame()
            f.setProperty("card", "true")
            f.setCursor(Qt.CursorShape.PointingHandCursor)
            add_shadow(f, 16, 14, 3)
            fl = QVBoxLayout(f)
            fl.setContentsMargins(18, 16, 18, 16)
            ic = label(icon)
            ic.setStyleSheet("font-size:26px;")
            fl.addWidget(ic)
            fl.addWidget(label(title, "h3"))
            fl.addWidget(label(text, "small", wrap=True))
            f.clicked.connect(lambda p=page: self.state.go(p))
            qa.addWidget(f)
        self.body.addLayout(qa)

        # Recent assessments
        self.body.addWidget(label("Recent device assessments", "h2"))
        items = assessment.user_assessments(self.state.uid)[:8]
        if not items:
            self.body.addWidget(label("No scans yet. Start the AI Scanner to assess your first device.", "muted"))
        for a in items:
            c, cl = card("true", (16, 12, 16, 12))
            r = QHBoxLayout()
            r.addWidget(label(f"<b>{a['brand'] or ''} {a['model'] or ''}</b>  {a['category']}"))
            col = assessment.CLASSIFICATION_COLORS.get(a["classification"], theme.MUTED)
            r.addWidget(badge(a["classification"], "white", col))
            r.addWidget(badge(a["grade"] or "", theme.INK, "#eef2ef"))
            if a["suggested_price"]:
                r.addWidget(label(f"Suggested {rupees(a['suggested_price'])}", "muted"))
            r.addStretch()
            r.addWidget(label(a["created_at"][:10], "small"))
            if assessment.can_list(a["classification"]):
                r.addWidget(button("Create listing", "soft", lambda _=False, a=a: self._list_from(a)))
            cl.addLayout(r)
            self.body.addWidget(c)
        self.body.addStretch()

    def _list_from(self, a):
        from core import listing_ai
        result = assessment.assess(a["category"], a["answers"] or {}, a["brand"], a["model"],
                                   {"defects": [d for d in (a["defects"] or []) if d.get("source") == "ai_image"]})
        draft = listing_ai.draft_from_assessment(result, a["answers"] or {}, self.state.user.get("city", ""))
        draft["assessment_id"] = a["id"]
        draft["image_path"] = a.get("image_path") or ""
        self.state.listing_draft = draft
        self.state.go("create_listing", from_ai=True)
