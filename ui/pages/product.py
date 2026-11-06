"""Product Details page."""
from __future__ import annotations

from PySide6.QtCore import Qt
from PySide6.QtWidgets import QGridLayout, QHBoxLayout, QLineEdit, QSpinBox, QVBoxLayout, QWidget

from core import catalog, marketplace

from .. import theme
from ..widgets import (HeartButton, HScroller, ImageGallery, Section, badge, button, card, clear_layout,
                       condition_badge, label, provenance_badge, rupees, verified_badge)
from .common import ScrollPage, add_to_cart, make_cards, toggle_wish
from .dialogs import ContactSellerDialog

FIELD_NAMES = {"title": "Title", "description": "Description", "category": "Category", "brand": "Brand",
               "model": "Model", "condition": "Condition", "functionality_status": "Functionality",
               "defects": "Defects", "price": "Price"}


class ProductPage(ScrollPage):
    def on_show(self, id=None, **_):
        if id is None:
            return
        self.listing_id = id
        marketplace.record_view(id, self.state.uid)
        self.render()
        self.scroll_top()

    def render(self):
        clear_layout(self.body)
        l = marketplace.get_listing(self.listing_id)
        if not l:
            self.body.addWidget(label("This listing no longer exists.", "h2"))
            return
        self.l = l
        own = l["seller_id"] == self.state.uid
        self.body.addWidget(button("←  Back", "link", self.state.back), 0, Qt.AlignmentFlag.AlignLeft)

        top = QHBoxLayout()
        top.setSpacing(32)
        g = ImageGallery(540, 410)
        g.set_images(l["images"])
        top.addWidget(g, 0, Qt.AlignmentFlag.AlignTop)

        info = QVBoxLayout()
        info.setSpacing(10)
        tags = QHBoxLayout()
        tags.addWidget(badge(f"{catalog.CATEGORY_ICONS.get(l['category'], '')} {l['category']}", theme.INK, "#eef2ef"))
        if l["featured_active"]:
            tags.addWidget(badge("★ Featured", "#92400e", "#fef3c7"))
        if l["for_repair"]:
            tags.addWidget(badge("For Repair / Parts", "#991b1b", "#fee2e2"))
        if l["status"] != "active":
            tags.addWidget(badge(l["status"].upper(), "white", theme.MUTED))
        tags.addStretch()
        info.addLayout(tags)
        t = label(l["title"], wrap=True)
        t.setStyleSheet("font-size:26px; font-weight:800;")
        info.addWidget(t)
        info.addWidget(label(f"Brand: <b>{l['brand'] or '—'}</b>   ·   Model: <b>{l['model'] or '—'}</b>   ·   "
                             f"Age: <b>{l['age_months']} months</b>", "muted"))
        cr = QHBoxLayout()
        cr.addWidget(condition_badge(l["condition"]))
        func_fg = theme.GREEN_DARK if l["functionality_status"].startswith("Fully") else "#92400e"
        cr.addWidget(badge(l["functionality_status"], func_fg, "#f1f5f2"))
        cr.addStretch()
        info.addLayout(cr)
        info.addWidget(label(catalog.FUNCTIONALITY_SOURCES.get(l["functionality_source"], ""), "small"))

        pr = QHBoxLayout()
        pr.addWidget(label(rupees(l["price"]), "bigprice"))
        if l["original_price"] and l["original_price"] > l["price"]:
            o = label(f"<s>{rupees(l['original_price'])}</s> new · save {round(100 * (1 - l['price'] / l['original_price']))}%")
            o.setStyleSheet(f"color:{theme.GREEN_DARK}; font-weight:700;")
            pr.addWidget(o)
        pr.addStretch()
        info.addLayout(pr)
        if l["est_low"] and l["est_high"]:
            info.addWidget(label(f"AI estimated resale range: {rupees(l['est_low'])} – {rupees(l['est_high'])}", "small"))

        if own:
            box, bl = card("soft", (16, 12, 16, 12))
            bl.addWidget(label("This is your listing.", "h3"))
            bl.addWidget(label(f"{l['views']} views · {l['quantity']} in stock · status {l['status']}", "muted"))
            r = QHBoxLayout()
            r.addWidget(button("Edit listing", "primary", lambda: self.state.go("create_listing", edit_id=l["id"])))
            r.addWidget(button("Seller dashboard", None, lambda: self.state.go("seller_dashboard")))
            r.addStretch()
            bl.addLayout(r)
            info.addWidget(box)
        elif l["status"] == "active" and l["quantity"] > 0:
            r = QHBoxLayout()
            self.qty = QSpinBox()
            self.qty.setRange(1, max(1, l["quantity"]))
            self.qty.setPrefix("Qty ")
            if l["quantity"] > 1:
                r.addWidget(self.qty)
            add = button("🛒  Add to Cart", "soft", lambda: add_to_cart(self.state, l["id"], self.qty.value()))
            buy = button("Buy Now", "primary", self._buy_now)
            for b in (add, buy):
                b.setMinimumHeight(46)
            r.addWidget(add, 1)
            r.addWidget(buy, 1)
            heart = HeartButton(l["id"] in marketplace.wishlist_ids(self.state.uid), 22)
            heart.setFixedSize(46, 46)
            heart.clicked.connect(lambda: toggle_wish(self.state, l["id"], heart))
            r.addWidget(heart)
            info.addLayout(r)
            info.addWidget(button("💬  Contact Seller", None, lambda: self._contact()))
            if l["quantity"] > 1:
                info.addWidget(label(f"{l['quantity']} available", "small"))
        else:
            info.addWidget(label("This item has been sold.", "h3"))

        # Delivery / pickup
        dbox, dl = card("true", (16, 12, 16, 12), 4)
        dl.addWidget(label("🚚  Delivery & pickup", "h3"))
        opts = l["delivery_options"] or ""
        if "delivery" in opts:
            fee = catalog.DELIVERY_FEE_LARGE if l["category"] in catalog.LARGE_ITEM_CATEGORIES else catalog.DELIVERY_FEE_STANDARD
            fee_txt = "Free delivery" if l["price"] >= catalog.FREE_DELIVERY_ABOVE else f"Delivery {rupees(fee)}"
            dl.addWidget(label(f"• {fee_txt} · ships from {l['location']} · usually 2–5 days", "muted"))
        if "pickup" in opts:
            dl.addWidget(label(f"• Free pickup from seller in {l['location']}", "muted"))
        dl.addWidget(label("• Payment is held until the server verifies it; seller ships only after verification.", "small"))
        info.addWidget(dbox)

        # Seller
        sbox, sl = card("true", (16, 12, 16, 12), 4)
        r = QHBoxLayout()
        av = label((l["seller_display"] or "?")[0].upper())
        av.setFixedSize(44, 44)
        av.setAlignment(Qt.AlignmentFlag.AlignCenter)
        av.setStyleSheet(f"background:{theme.GREEN}; color:white; border-radius:22px; font-size:18px; font-weight:800;")
        r.addWidget(av)
        c = QVBoxLayout()
        c.setSpacing(2)
        c.addWidget(label(f"<b>{l['seller_display']}</b>"))
        c.addWidget(label(f"{'Business seller' if l['seller_type'] == 'industry' else 'Individual seller'} · "
                          f"📍 {l['seller_city'] or l['location']} · since {l['seller_since'][:7]}", "small"))
        r.addLayout(c, 1)
        r.addWidget(verified_badge(bool(l["seller_verified"]), l["seller_type"]))
        sl.addLayout(r)
        info.addWidget(sbox)
        info.addStretch()
        iw = QWidget()
        iw.setLayout(info)
        top.addWidget(iw, 1)
        tw = QWidget()
        tw.setLayout(top)
        self.body.addWidget(tw)

        # Details row
        row = QHBoxLayout()
        row.setSpacing(18)
        left = QVBoxLayout()
        left.setSpacing(14)
        prov = l.get("provenance") or {}
        d, dl2 = card("true", (20, 16, 20, 16), 8)
        hr = QHBoxLayout()
        hr.addWidget(label("Product description", "h3"))
        hr.addStretch()
        if prov.get("description"):
            hr.addWidget(provenance_badge(prov["description"]))
        dl2.addLayout(hr)
        dl2.addWidget(label(l["description"] or "No description provided.", wrap=True, selectable=True))
        left.addWidget(d)

        dk, dkl = card("warn" if l.get("defects") else "true", (20, 16, 20, 16), 6)
        dkl.addWidget(label("Known defects", "h3"))
        if l.get("defects"):
            for x in l["defects"]:
                dkl.addWidget(label(f"• {x}", wrap=True))
        else:
            dkl.addWidget(label("No defects reported by the seller.", "muted"))
        left.addWidget(dk)

        sp, spl = card("true", (20, 16, 20, 16), 6)
        spl.addWidget(label("Specifications", "h3"))
        specs = {"Category": l["category"], "Brand": l["brand"] or "—", "Model": l["model"] or "—",
                 "Age": f"{l['age_months']} months", "Condition": l["condition"],
                 "Functionality": l["functionality_status"], **(l.get("specs") or {})}
        grid = QGridLayout()
        grid.setHorizontalSpacing(24)
        for i, (k, v) in enumerate(specs.items()):
            grid.addWidget(label(k, "muted"), i, 0)
            grid.addWidget(label(f"<b>{v}</b>"), i, 1)
        spl.addLayout(grid)
        left.addWidget(sp)

        # Q&A
        qa, qal = card("true", (20, 16, 20, 16), 8)
        qal.addWidget(label("Buyer questions", "h3"))
        if not own and l["status"] == "active":
            ask = QHBoxLayout()
            self.q_edit = QLineEdit()
            self.q_edit.setPlaceholderText("Ask the seller a question about this item…")
            self.q_edit.returnPressed.connect(self._ask)
            ask.addWidget(self.q_edit, 1)
            ask.addWidget(button("Ask", "primary", self._ask))
            qal.addLayout(ask)
        qs = marketplace.listing_questions(l["id"])
        if not qs:
            qal.addWidget(label("No questions yet.", "muted"))
        for q in qs:
            qal.addWidget(label(f"<b>Q:</b> {q['question']} <span style='color:#5b7466'>— {q['asker_name']}</span>", wrap=True))
            qal.addWidget(label(f"<b>A:</b> {q['answer']}" if q["answer"] else "<i>Awaiting seller's answer</i>",
                                "muted", wrap=True))
        left.addWidget(qa)
        lw = QWidget()
        lw.setLayout(left)
        row.addWidget(lw, 3)

        right = QVBoxLayout()
        right.setSpacing(14)
        ai = l.get("ai_assessment")
        a, al = card("ai", (18, 16, 18, 16), 6)
        al.addWidget(label("🤖  AI assessment summary", "h3"))
        if ai:
            al.addWidget(label(f"Recovery classification: <b>{ai.get('classification')}</b>"))
            al.addWidget(label(f"AI condition grade: <b>{ai.get('grade')}</b>"))
            al.addWidget(label(f"Functionality (seller-answered): <b>{ai.get('functional_status')}</b>", wrap=True))
            v = ai.get("value") or {}
            if v.get("low"):
                al.addWidget(label(f"Estimated value: {rupees(v['low'])} – {rupees(v['high'])}"))
            for d_ in (ai.get("defects") or [])[:5]:
                src = "image" if d_.get("source") == "ai_image" else "seller"
                al.addWidget(label(f"• {d_['label']} ({src})", "small", wrap=True))
            al.addWidget(label(f"Confidence {int(float(ai.get('confidence', 0)) * 100)}%", "small"))
        else:
            al.addWidget(label("This listing was created manually, without an AI scan.", "muted", wrap=True))
        al.addWidget(label("The AI assessment is supporting information only and is not a guarantee of the "
                           "product's condition or functionality.", "small", wrap=True))
        right.addWidget(a)
        if prov:
            p, pl = card("true", (18, 16, 18, 16), 6)
            pl.addWidget(label("Where this information came from", "h3"))
            for k, src in prov.items():
                if k in FIELD_NAMES:
                    rr = QHBoxLayout()
                    rr.addWidget(label(FIELD_NAMES[k], "muted"))
                    rr.addStretch()
                    rr.addWidget(provenance_badge(src))
                    pl.addLayout(rr)
            right.addWidget(p)
        cg, cgl = card("soft", (18, 16, 18, 16), 6)
        cgl.addWidget(label(f"What “{l['condition']}” means", "h3"))
        cgl.addWidget(label(catalog.CONDITION_DESCRIPTIONS[l["condition"]], wrap=True))
        right.addWidget(cg)
        right.addStretch()
        rw = QWidget()
        rw.setLayout(right)
        row.addWidget(rw, 2)
        roww = QWidget()
        roww.setLayout(row)
        self.body.addWidget(roww)

        similar = marketplace.similar_listings(l)
        if similar:
            s = Section("Similar devices")
            hs = HScroller(470)
            hs.set_widgets(make_cards(self.state, similar))
            s.add(hs)
            self.body.addWidget(s)
        self.body.addStretch()

    def _buy_now(self):
        self.state.buy_now = {"listing_id": self.l["id"], "qty": self.qty.value()}
        self.state.go("checkout", buy_now=True)

    def _contact(self):
        if ContactSellerDialog(self.state, self.l, self).exec():
            self.state.toast("Message sent to the seller.", "success")
            self.state.data_changed.emit()

    def _ask(self):
        try:
            marketplace.ask_question(self.l["id"], self.state.uid, self.q_edit.text())
        except marketplace.MarketError as e:
            self.state.toast(str(e), "error")
            return
        self.state.toast("Question posted. The seller will be notified.", "success")
        self.render()
