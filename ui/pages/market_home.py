"""Marketplace Home."""
from __future__ import annotations

from PySide6.QtCore import Qt
from PySide6.QtWidgets import QFrame, QGridLayout, QHBoxLayout, QLabel, QVBoxLayout, QWidget

from core import catalog, marketplace

from .. import theme
from ..widgets import ClickableFrame, HScroller, Section, add_shadow, button, card, clear_layout, label, rupees
from .common import ScrollPage, make_cards


class MarketHomePage(ScrollPage):
    def on_show(self, **_):
        clear_layout(self.body)
        self.scroll_top()

        # Hero
        hero = QFrame()
        hero.setStyleSheet("QFrame#hero { background: qlineargradient(x1:0,y1:0,x2:1,y2:1, stop:0 #ecfdf3, stop:0.55 #ffffff,"
                           " stop:1 #dcfce7); border:1px solid #d1fae5; border-radius:24px; }")
        hero.setObjectName("hero")
        hl = QHBoxLayout(hero)
        hl.setContentsMargins(36, 30, 36, 30)
        col = QVBoxLayout()
        col.setSpacing(10)
        kicker = label("♻  SECOND LIFE ELECTRONICS")
        kicker.setStyleSheet(f"color:{theme.GREEN_DARK}; font-weight:800; font-size:12px;")
        col.addWidget(kicker)
        h = label("Premium pre-owned tech.\nZero new e-waste.")
        h.setStyleSheet("font-size:34px; font-weight:800;")
        col.addWidget(h)
        col.addWidget(label("Every listing shows a standard condition grade, known defects and — when scanned — an AI "
                            "assessment. Pay securely; your money is confirmed by our server before the seller ships.",
                            "muted", wrap=True))
        btns = QHBoxLayout()
        btns.addWidget(button("Browse electronics", "primary", lambda: self.state.go("browse")))
        btns.addWidget(button("📷  Sell with AI Scanner", "dark", lambda: self.state.go("scanner")))
        btns.addStretch()
        col.addLayout(btns)
        hl.addLayout(col, 3)
        stats = marketplace.marketplace_stats()
        sc = QVBoxLayout()
        for v, t in [(str(stats["active_listings"]), "devices for sale"), (str(stats["sellers"]), "active sellers"),
                     (str(stats["devices_resold"]), "devices resold")]:
            box = QFrame()
            box.setStyleSheet("QFrame { background:white; border:1px solid #d1fae5; border-radius:16px; }")
            bl = QVBoxLayout(box)
            bl.setContentsMargins(18, 10, 18, 10)
            n = QLabel(v)
            n.setStyleSheet(f"font-size:26px; font-weight:800; color:{theme.GREEN_DARK}; border:0;")
            bl.addWidget(n)
            tt = QLabel(t)
            tt.setStyleSheet(f"color:{theme.MUTED}; border:0;")
            bl.addWidget(tt)
            sc.addWidget(box)
        hl.addLayout(sc, 1)
        self.body.addWidget(hero)

        # Categories
        sec = Section("Shop by category")
        grid = QGridLayout()
        grid.setSpacing(12)
        counts = marketplace.category_counts()
        for i, cat in enumerate(catalog.CATEGORIES):
            tile = ClickableFrame()
            tile.setProperty("card", "true")
            tile.setCursor(Qt.CursorShape.PointingHandCursor)
            tile.setStyleSheet(f"ClickableFrame:hover {{ border:1px solid {theme.GREEN}; background:{theme.GREEN_50}; }}")
            tl = QHBoxLayout(tile)
            tl.setContentsMargins(14, 12, 14, 12)
            ic = QLabel(catalog.CATEGORY_ICONS[cat])
            ic.setStyleSheet(f"font-size:22px; background:{theme.GREEN_50}; border-radius:12px; padding:6px;")
            tl.addWidget(ic)
            c2 = QVBoxLayout()
            c2.setSpacing(0)
            c2.addWidget(label(cat, "h3"))
            c2.addWidget(label(f"{counts.get(cat, 0)} listed", "small"))
            tl.addLayout(c2)
            tl.addStretch()
            tile.clicked.connect(lambda c=cat: self.state.go("browse", category=c))
            grid.addWidget(tile, i // 4, i % 4)
        gw = QWidget()
        gw.setLayout(grid)
        sec.add(gw)
        self.body.addWidget(sec)

        def carousel(title, items, subtitle="", action=None):
            if not items:
                return
            s = Section(title, "See all" if action else "", action, subtitle)
            hs = HScroller(470)
            hs.set_widgets(make_cards(self.state, items))
            s.add(hs)
            self.body.addWidget(s)

        featured = [x for x in marketplace.search_listings(sort="featured", limit=12, exclude_seller=self.state.uid)
                    if x["featured_active"]]
        carousel("★ Featured listings", featured, "Promoted by sellers")
        carousel("Recently listed", marketplace.search_listings(sort="newest", limit=12, exclude_seller=self.state.uid),
                 "", lambda: self.state.go("browse", sort="newest"))
        carousel("Refurbished by verified businesses",
                 marketplace.search_listings(seller_type="industry", verified_only=True, limit=12,
                                             exclude_seller=self.state.uid),
                 "Inspected and graded by industry sellers", lambda: self.state.go("browse", seller_type="industry"))
        repair = marketplace.search_listings(conditions=["For Parts / Repair"], limit=12, exclude_seller=self.state.uid)
        carousel("For repairers & hobbyists", repair, "Devices sold for parts or repair")

        # How it works
        how = Section("How Punarth Market works")
        row = QHBoxLayout()
        row.setSpacing(12)
        for icon, t, d in [("📷", "Scan", "AI identifies the device and checks visible defects."),
                           ("🧠", "Assess", "Answer a few questions; AI decides reuse, repair, refurbish or recycle."),
                           ("🏷️", "List", "AI writes the listing and suggests a fair price. You confirm everything."),
                           ("🔒", "Sell safely", "Buyer pays via Razorpay; our server verifies before you ship.")]:
            c, cl = card("soft", (16, 14, 16, 14), 4)
            ic = label(icon)
            ic.setStyleSheet("font-size:26px;")
            cl.addWidget(ic)
            cl.addWidget(label(t, "h3"))
            cl.addWidget(label(d, "small", wrap=True))
            row.addWidget(c)
        w = QWidget()
        w.setLayout(row)
        how.add(w)
        self.body.addWidget(how)

        # Condition guide
        guide = Section("Condition grades explained", subtitle="The same five labels on every listing")
        row = QHBoxLayout()
        row.setSpacing(10)
        for cond in catalog.CONDITIONS:
            fg, bg = theme.CONDITION_COLORS[cond]
            c, cl = card("true", (14, 12, 14, 12), 4)
            t = label(cond)
            t.setStyleSheet(f"color:{fg}; background:{bg}; border-radius:8px; padding:4px 8px; font-weight:800;")
            cl.addWidget(t)
            cl.addWidget(label(catalog.CONDITION_DESCRIPTIONS[cond], "small", wrap=True))
            cl.addStretch()
            row.addWidget(c)
        w2 = QWidget()
        w2.setLayout(row)
        guide.add(w2)
        self.body.addWidget(guide)

        cta, cl = card("true", (26, 20, 26, 20))
        cta.setStyleSheet("QFrame { background:#0f2e1d; border-radius:18px; border:0; } QLabel { color:white; }")
        add_shadow(cta)
        r = QHBoxLayout()
        cc = QVBoxLayout()
        cc.addWidget(label("Got a device lying around?", "h2"))
        cc.addWidget(label(f"Sellers keep up to 97% of the sale price. Featured listings from {rupees(catalog.FEATURED_LISTING_PRICE)}.",
                           wrap=True))
        r.addLayout(cc, 1)
        r.addWidget(button("Sell your device", "primary", lambda: self.state.go("sell")))
        cl.addLayout(r)
        self.body.addWidget(cta)
        self.body.addStretch()
