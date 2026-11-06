"""My Listings and Seller Dashboard (stats, listings, orders, buyer requests,
sales history, plans & featured listings)."""
from __future__ import annotations

from PySide6.QtWidgets import (QAbstractItemView, QButtonGroup, QGridLayout, QHBoxLayout, QHeaderView, QLabel,
                               QMessageBox, QTableWidget, QTableWidgetItem, QTabWidget, QVBoxLayout, QWidget)

from core import catalog, marketplace

from .. import theme
from ..widgets import (StatTile, badge, button, card, clear_layout, condition_badge, empty_state, label,
                       rounded_pixmap, rupees, scroll)
from .common import ScrollPage
from .dialogs import AnswerQuestionDialog, MessagesDialog, pay
from .orders import order_card

STATUS_STYLE = {"active": ("#166534", "#dcfce7"), "draft": ("#92400e", "#fef3c7"), "sold": ("#1e40af", "#dbeafe"),
                "removed": ("#475569", "#f1f5f9")}


def listing_row(state, l: dict, parent, on_change) -> QWidget:
    c, cl = card("true", (14, 12, 14, 12))
    r = QHBoxLayout()
    r.setSpacing(14)
    pic = QLabel()
    pic.setPixmap(rounded_pixmap(l.get("cover"), 110, 82, 10))
    r.addWidget(pic)
    col = QVBoxLayout()
    col.setSpacing(4)
    col.addWidget(button(l["title"], "link", lambda: state.go("product", id=l["id"])), 0)
    meta = QHBoxLayout()
    fg, bg = STATUS_STYLE.get(l["status"], (theme.INK, "#eee"))
    meta.addWidget(badge(l["status"].title(), fg, bg))
    meta.addWidget(condition_badge(l["condition"]))
    if l["featured_active"]:
        meta.addWidget(badge(f"★ Featured until {l['featured_until'][:10]}", "#92400e", "#fef3c7"))
    if l.get("ai_assessment"):
        meta.addWidget(badge("AI assessed", "#5b21b6", "#ede9fe"))
    meta.addStretch()
    col.addLayout(meta)
    col.addWidget(label(f"{rupees(l['price'])} · {l['quantity']} in stock · 👁 {l['views']} views · {l['category']} · "
                        f"updated {l['updated_at'][:10]}", "muted"))
    r.addLayout(col, 1)

    def act(fn, msg):
        try:
            fn()
        except marketplace.MarketError as e:
            QMessageBox.warning(parent, "Not possible", str(e))
            return
        state.toast(msg, "success")
        state.data_changed.emit()
        on_change()

    acts = QGridLayout()
    acts.setSpacing(6)
    btns = [button("Edit", None, lambda: state.go("create_listing", edit_id=l["id"]))]
    if l["status"] == "draft":
        btns.append(button("Publish", "primary", lambda: act(lambda: marketplace.set_listing_status(state.uid, l["id"], "active"), "Listing published")))
    if l["status"] == "active":
        btns.append(button("Mark as Sold", "soft", lambda: act(lambda: marketplace.set_listing_status(state.uid, l["id"], "sold"), "Marked as sold")))
        if not l["featured_active"]:
            def feature():
                try:
                    pid = marketplace.create_featured_payment(state.uid, l["id"])
                except marketplace.MarketError as e:
                    QMessageBox.warning(parent, "Feature listing", str(e))
                    return
                if pay(state, pid, parent):
                    state.toast(f"Featured for {catalog.FEATURED_DAYS} days ★", "success")
                    on_change()
            btns.append(button(f"★ Feature {rupees(catalog.FEATURED_LISTING_PRICE)}", None, feature))
    if l["status"] == "sold" and l["quantity"] > 0:
        btns.append(button("Relist", None, lambda: act(lambda: marketplace.set_listing_status(state.uid, l["id"], "active"), "Relisted")))

    def delete():
        if QMessageBox.question(parent, "Delete listing", f"Delete “{l['title']}”? Buyers will no longer see it.") \
                == QMessageBox.StandardButton.Yes:
            act(lambda: marketplace.delete_listing(state.uid, l["id"]), "Listing deleted")
    btns.append(button("Delete", "danger", delete))
    for i, b in enumerate(btns):
        acts.addWidget(b, i // 2, i % 2)
    r.addLayout(acts)
    cl.addLayout(r)
    return c


class MyListingsPage(ScrollPage):
    def __init__(self, state):
        super().__init__(state)
        self.filter = "all"

    def on_show(self, **_):
        clear_layout(self.body)
        head = QHBoxLayout()
        head.addWidget(label("My Listings", "h1"))
        head.addStretch()
        head.addWidget(button("+ Create Listing", "primary", lambda: self.state.go("sell")))
        self.body.addLayout(head)
        items = marketplace.seller_listings(self.state.uid)
        chips = QHBoxLayout()
        grp = QButtonGroup(self)
        for key, txt in (("all", "All"), ("active", "Active"), ("draft", "Drafts"), ("sold", "Sold")):
            n = len(items) if key == "all" else sum(1 for i in items if i["status"] == key)
            b = button(f"{txt} ({n})", "chip", lambda _=False, k=key: self._set(k))
            b.setCheckable(True)
            b.setChecked(key == self.filter)
            grp.addButton(b)
            chips.addWidget(b)
        chips.addStretch()
        self.body.addLayout(chips)
        shown = [i for i in items if self.filter == "all" or i["status"] == self.filter]
        if not shown:
            self.body.addWidget(empty_state("🏷️", "No listings here", "Sell a device with the AI Scanner or create a listing manually.",
                                            "Sell your device", lambda: self.state.go("sell")))
        for l in shown:
            self.body.addWidget(listing_row(self.state, l, self, self.on_show))
        self.body.addStretch()

    def _set(self, k):
        self.filter = k
        self.on_show()


class SellerDashboardPage(QWidget):
    def __init__(self, state):
        super().__init__()
        self.state = state
        root = QVBoxLayout(self)
        root.setContentsMargins(32, 22, 32, 16)
        root.setSpacing(14)
        head = QHBoxLayout()
        self.title = label("Seller Dashboard", "h1")
        head.addWidget(self.title)
        self.plan_badge = QLabel()
        head.addWidget(self.plan_badge)
        head.addStretch()
        head.addWidget(button("📷 List via AI Scanner", "soft", lambda: state.go("scanner")))
        head.addWidget(button("+ Create Listing", "primary", lambda: state.go("sell")))
        root.addLayout(head)
        self.tiles_w = QWidget()
        self.tiles = QGridLayout(self.tiles_w)
        self.tiles.setContentsMargins(0, 0, 0, 0)
        self.tiles.setSpacing(12)
        root.addWidget(self.tiles_w)
        self.tabs = QTabWidget()
        root.addWidget(self.tabs, 1)
        self.tab_pages = {}
        for key, txt in (("listings", "Listings"), ("orders", "Manage Orders"), ("requests", "Buyer Requests"),
                         ("history", "Sales History"), ("plans", "Plans & Promotions")):
            w = QWidget()
            lay = QVBoxLayout(w)
            lay.setContentsMargins(0, 12, 0, 0)
            inner = QWidget()
            il = QVBoxLayout(inner)
            il.setContentsMargins(0, 0, 8, 0)
            il.setSpacing(12)
            lay.addWidget(scroll(inner))
            self.tab_pages[key] = il
            self.tabs.addTab(w, txt)
        self.keys = list(self.tab_pages)

    def on_show(self, tab=None, **_):
        u = self.state.user
        plan = catalog.SELLER_PLANS.get(u.get("seller_plan") or "free")
        self.plan_badge.setText(f"  {plan['name']} plan  ")
        self.plan_badge.setStyleSheet(f"background:{theme.GREEN_100}; color:{theme.GREEN_DARK}; border-radius:10px; "
                                      "padding:4px 8px; font-weight:800;")
        clear_layout(self.tiles)
        st = marketplace.seller_stats(self.state.uid)
        tiles = [("Total Listings", st["total_listings"], "🏷️", ""), ("Active Listings", st["active_listings"], "✅", ""),
                 ("Sold Products", st["sold_products"], "📦", ""), ("Pending Orders", st["pending_orders"], "⏳", "to fulfil"),
                 ("Total Sales", rupees(st["total_sales"]), "💰", "paid orders"),
                 ("Estimated Revenue", rupees(st["estimated_revenue"]), "📈", f"after {rupees(st['commission_paid'])} commission"),
                 ("Product Views", st["product_views"], "👁", ""), ("Buyer Requests", st["buyer_requests"], "💬", "unanswered / unread")]
        for i, (t, v, ic, sub) in enumerate(tiles):
            self.tiles.addWidget(StatTile(t, str(v), ic, sub=sub), i // 4, i % 4)
        self._listings()
        self._orders()
        self._requests()
        self._history()
        self._plans()
        if tab in self.keys:
            self.tabs.setCurrentIndex(self.keys.index(tab))

    def _refresh(self):
        self.on_show()

    def _listings(self):
        lay = self.tab_pages["listings"]
        clear_layout(lay)
        items = marketplace.seller_listings(self.state.uid)
        if not items:
            lay.addWidget(empty_state("🏷️", "No listings yet", "Create your first listing.", "Sell a device",
                                      lambda: self.state.go("sell")))
        for l in items:
            lay.addWidget(listing_row(self.state, l, self, self._refresh))
        lay.addStretch()

    def _orders(self):
        lay = self.tab_pages["orders"]
        clear_layout(lay)
        orders = marketplace.seller_orders(self.state.uid)
        if not orders:
            lay.addWidget(label("No orders yet. Paid orders appear here for you to confirm and ship.", "muted"))
        for o in orders:
            c = order_card(self.state, o, self, buyer_view=False)
            nxt = marketplace.next_order_status(o)
            addr = o.get("address") or {}
            if o["delivery_method"] == "delivery" and addr:
                c.layout().addWidget(label(f"Ship to: {addr.get('name')}, {addr.get('line1')}, {addr.get('city')} "
                                           f"{addr.get('pincode')} · 📞 {addr.get('phone')}", "small", wrap=True))
            svc = o.get("services") or []
            if svc:
                c.layout().addWidget(label("Services: " + ", ".join(catalog.SERVICES[s]["name"] for s in svc if s in catalog.SERVICES),
                                           "small", wrap=True))
            if nxt:
                r = QHBoxLayout()
                r.addStretch()
                r.addWidget(label(f"Your payout: {rupees(o['subtotal'] - o['commission'])} (commission {rupees(o['commission'])})", "small"))
                r.addWidget(button(f"Mark as {nxt}", "primary", lambda _=False, oid=o["id"]: self._advance(oid)))
                c.layout().addLayout(r)
            lay.addWidget(c)
        lay.addStretch()

    def _advance(self, oid):
        try:
            s = marketplace.advance_order(self.state.uid, oid)
        except marketplace.MarketError as e:
            QMessageBox.warning(self, "Order", str(e))
            return
        self.state.toast(f"Order #{oid} → {s}", "success")
        self.state.data_changed.emit()
        self._refresh()
        self.tabs.setCurrentIndex(1)

    def _requests(self):
        lay = self.tab_pages["requests"]
        clear_layout(lay)
        top = QHBoxLayout()
        top.addWidget(label("Questions on your listings", "h3"))
        top.addStretch()
        top.addWidget(button("💬 Open messages", "soft", self._messages))
        lay.addLayout(top)
        qs = marketplace.seller_questions(self.state.uid)
        if not qs:
            lay.addWidget(label("No buyer questions yet.", "muted"))
        for q in qs:
            c, cl = card("warn" if not q["answer"] else "true", (16, 12, 16, 12), 4)
            cl.addWidget(label(f"<b>{q['listing_title']}</b>", "muted"))
            cl.addWidget(label(f"❓ {q['question']} — {q['asker_name']}", wrap=True))
            r = QHBoxLayout()
            r.addWidget(label(f"💬 {q['answer']}" if q["answer"] else "Not answered yet", "small", wrap=True), 1)
            r.addWidget(button("Edit answer" if q["answer"] else "Answer", "primary" if not q["answer"] else None,
                               lambda _=False, q=q: self._answer(q)))
            cl.addLayout(r)
            lay.addWidget(c)
        lay.addStretch()

    def _answer(self, q):
        dlg = AnswerQuestionDialog(q, self)
        if dlg.exec() and dlg.text():
            marketplace.answer_question(self.state.uid, q["id"], dlg.text())
            self.state.toast("Answer posted.", "success")
            self._refresh()
            self.tabs.setCurrentIndex(2)

    def _messages(self):
        MessagesDialog(self.state, self).exec()
        self.state.data_changed.emit()
        self._refresh()
        self.tabs.setCurrentIndex(2)

    def _history(self):
        lay = self.tab_pages["history"]
        clear_layout(lay)
        rows = marketplace.sales_history(self.state.uid)
        if not rows:
            lay.addWidget(label("No completed sales yet.", "muted"))
            lay.addStretch()
            return
        t = QTableWidget(len(rows), 7)
        t.setHorizontalHeaderLabels(["Order", "Date", "Item", "Qty", "Price", "Commission", "Status"])
        for i, r in enumerate(rows):
            vals = [f"#{r['order_id']}", r["created_at"][:10], r["title"], str(r["qty"]), rupees(r["price"] * r["qty"]),
                    rupees(r["commission"]), r["status"]]
            for j, v in enumerate(vals):
                t.setItem(i, j, QTableWidgetItem(v))
        t.horizontalHeader().setSectionResizeMode(2, QHeaderView.ResizeMode.Stretch)
        t.verticalHeader().setVisible(False)
        t.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        t.setMinimumHeight(min(600, 60 + 36 * len(rows)))
        lay.addWidget(t)
        total = sum(r["price"] * r["qty"] for r in rows)
        lay.addWidget(label(f"<b>{len(rows)} items sold · {rupees(total)} gross</b>"))
        lay.addStretch()

    def _plans(self):
        lay = self.tab_pages["plans"]
        clear_layout(lay)
        lay.addWidget(label("Seller plans", "h2"))
        lay.addWidget(label("Punarth AI earns a small commission on completed sales. Plans lower your commission and "
                            "raise your listing limit.", "muted", wrap=True))
        row = QHBoxLayout()
        row.setSpacing(14)
        cur = self.state.user.get("seller_plan") or "free"
        for key, p in catalog.SELLER_PLANS.items():
            c, cl = card("soft" if key == cur else "true", (20, 18, 20, 18), 6)
            cl.addWidget(label(p["name"], "h3"))
            cl.addWidget(label("Free" if not p["price"] else f"{rupees(p['price'])}/month", "price"))
            for perk in p["perks"]:
                cl.addWidget(label(f"✓ {perk}"))
            cl.addStretch()
            if key == cur:
                until = self.state.user.get("plan_until") or ""
                cl.addWidget(badge("Current plan" + (f" · until {until[:10]}" if until else ""), "white", theme.GREEN))
            elif p["price"]:
                if key == "business" and not self.state.is_industry:
                    cl.addWidget(label("Business plan is for Industry accounts.", "small", wrap=True))
                else:
                    cl.addWidget(button(f"Subscribe {rupees(p['price'])}", "primary", lambda _=False, k=key: self._subscribe(k)))
            row.addWidget(c, 1)
        w = QWidget()
        w.setLayout(row)
        lay.addWidget(w)

        lay.addWidget(label("Promotions & services", "h2"))
        row2 = QHBoxLayout()
        row2.setSpacing(14)
        f, fl = card("true", (20, 16, 20, 16), 6)
        fl.addWidget(label("★ Featured listings", "h3"))
        fl.addWidget(label(f"Appear first in search and on Marketplace Home for {catalog.FEATURED_DAYS} days — "
                           f"{rupees(catalog.FEATURED_LISTING_PRICE)} per listing. Use the ★ Feature button on any "
                           "active listing.", wrap=True))
        row2.addWidget(f, 1)
        r, rl = card("true", (20, 16, 20, 16), 6)
        rl.addWidget(label("🔁 Refurbishment partnerships", "h3"))
        rl.addWidget(label("Send devices to partner refurbishers and sell them back as Grade-A stock. Find partners in "
                           "the Recovery Center.", wrap=True))
        rl.addWidget(button("Open Recovery Center", "link", lambda: self.state.go("recovery")))
        row2.addWidget(r, 1)
        s, sl = card("true", (20, 16, 20, 16), 6)
        sl.addWidget(label("🧰 Buyer & seller services", "h3"))
        for svc in catalog.SERVICES.values():
            sl.addWidget(label(f"• {svc['name']} — {rupees(svc['price'])}"))
        row2.addWidget(s, 1)
        w2 = QWidget()
        w2.setLayout(row2)
        lay.addWidget(w2)
        lay.addStretch()

    def _subscribe(self, key):
        try:
            pid = marketplace.create_subscription_payment(self.state.uid, key)
        except marketplace.MarketError as e:
            QMessageBox.warning(self, "Subscribe", str(e))
            return
        if pay(self.state, pid, self):
            from core import auth
            self.state.user = auth.get_user(self.state.uid)
            self.state.toast(f"You're on the {catalog.SELLER_PLANS[key]['name']} plan now!", "success")
        self._refresh()
        self.tabs.setCurrentIndex(4)
