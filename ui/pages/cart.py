"""Shopping Cart, Wishlist and Checkout."""
from __future__ import annotations

from PySide6.QtWidgets import (QButtonGroup, QCheckBox, QGridLayout, QHBoxLayout, QLabel, QLineEdit, QMessageBox,
                               QRadioButton, QSpinBox, QVBoxLayout, QWidget)

from core import catalog, marketplace

from .. import theme
from ..widgets import (ProductGrid, badge, button, card, clear_layout, condition_badge, empty_state, hline, label,
                       rounded_pixmap, rupees)
from .common import ScrollPage, make_cards
from .dialogs import pay


def summary_card(summary: dict, title: str = "Order summary"):
    c, cl = card("true", (20, 18, 20, 18), 8)
    cl.addWidget(label(title, "h3"))

    def line(a, b, bold=False):
        r = QHBoxLayout()
        r.addWidget(label(f"<b>{a}</b>" if bold else a, None if bold else "muted"))
        r.addStretch()
        r.addWidget(label(f"<b>{b}</b>" if bold else b))
        cl.addLayout(r)
    line(f"Items ({summary['item_count']})", rupees(summary["subtotal"]))
    line("Delivery", "Free" if summary["delivery"] == 0 else rupees(summary["delivery"]))
    if summary["services"]:
        line("Services", rupees(summary["services"]))
    cl.addWidget(hline())
    line("Total", rupees(summary["total"]), True)
    if len(summary["groups"]) > 1:
        cl.addWidget(label(f"Ships from {len(summary['groups'])} sellers — delivery is charged per seller "
                           f"(free above {rupees(catalog.FREE_DELIVERY_ABOVE)}).", "small", wrap=True))
    return c, cl


class CartPage(ScrollPage):
    def on_show(self, **_):
        clear_layout(self.body)
        self.body.addWidget(label("Shopping Cart", "h1"))
        items = marketplace.cart_items(self.state.uid)
        if not items:
            self.body.addWidget(empty_state("🛒", "Your cart is empty", "Find great second-hand devices and give them a new home.",
                                            "Browse electronics", lambda: self.state.go("browse")))
            self.body.addStretch()
            return
        row = QHBoxLayout()
        row.setSpacing(20)
        col = QVBoxLayout()
        col.setSpacing(12)
        for it in items:
            c, cl = card("true", (16, 14, 16, 14))
            r = QHBoxLayout()
            r.setSpacing(14)
            pic = QLabel()
            pic.setPixmap(rounded_pixmap(it.get("cover"), 130, 98, 10))
            r.addWidget(pic)
            info = QVBoxLayout()
            info.addWidget(button(it["title"], "link", lambda _=False, lid=it["id"]: self.state.go("product", id=lid)), 0)
            info.addWidget(label(f"Sold by {it['seller_display']} · 📍 {it['location']}", "muted"))
            br = QHBoxLayout()
            br.addWidget(condition_badge(it["condition"]))
            if not it["available"]:
                br.addWidget(badge("No longer available", "#991b1b", "#fee2e2"))
            br.addStretch()
            info.addLayout(br)
            r.addLayout(info, 1)
            right = QVBoxLayout()
            right.addWidget(label(rupees(it["price"] * it["cart_qty"]), "price"))
            if it["quantity"] > 1:
                q = QSpinBox()
                q.setRange(1, it["quantity"])
                q.setValue(it["cart_qty"])
                q.setPrefix("Qty ")
                q.valueChanged.connect(lambda v, lid=it["id"]: self._qty(lid, v))
                right.addWidget(q)
            else:
                right.addWidget(label("Qty 1 (single item)", "small"))
            right.addWidget(button("Remove", "danger", lambda _=False, lid=it["id"]: self._remove(lid)))
            r.addLayout(right)
            cl.addLayout(r)
            col.addWidget(c)
        col.addStretch()
        cw = QWidget()
        cw.setLayout(col)
        row.addWidget(cw, 3)
        summary = marketplace.cart_summary(self.state.uid, "delivery")
        sc, scl = summary_card(summary)
        for p in summary["problems"]:
            scl.addWidget(label(f"⚠️ {p}", "small", wrap=True))
        go = button("Proceed to checkout", "primary", lambda: self.state.go("checkout"))
        go.setMinimumHeight(46)
        go.setEnabled(not summary["problems"] and bool(summary["groups"]))
        scl.addWidget(go)
        scl.addWidget(label("🔒 Payments via Razorpay, verified on our server.", "small"))
        side = QVBoxLayout()
        side.addWidget(sc)
        side.addStretch()
        sw = QWidget()
        sw.setLayout(side)
        sw.setFixedWidth(360)
        row.addWidget(sw)
        rw = QWidget()
        rw.setLayout(row)
        self.body.addWidget(rw)
        self.body.addStretch()

    def _qty(self, lid, v):
        marketplace.set_cart_qty(self.state.uid, lid, v)
        self.state.cart_changed.emit()
        self.on_show()

    def _remove(self, lid):
        marketplace.remove_from_cart(self.state.uid, lid)
        self.state.cart_changed.emit()
        self.state.toast("Removed from cart")
        self.on_show()


class WishlistPage(ScrollPage):
    def on_show(self, **_):
        clear_layout(self.body)
        self.body.addWidget(label("Wishlist", "h1"))
        items = marketplace.wishlist(self.state.uid)
        if not items:
            self.body.addWidget(empty_state("♡", "No saved devices yet", "Tap the heart on any product to save it here.",
                                            "Browse electronics", lambda: self.state.go("browse")))
            self.body.addStretch()
            return
        self.body.addWidget(label(f"{len(items)} saved device(s). Sold items stay here so you can find similar ones.", "muted"))
        g = ProductGrid()
        cards = make_cards(self.state, items)
        for c in cards:
            c.wishlist_toggled.connect(lambda _lid: self.on_show())
        g.set_cards(cards)
        self.body.addWidget(g)
        self.body.addStretch()


class CheckoutPage(ScrollPage):
    def on_show(self, buy_now=False, **_):
        self.buy_now = self.state.buy_now if buy_now else None
        self._building = True
        clear_layout(self.body)
        self.body.addWidget(button("←  Back", "link", self.state.back))
        self.body.addWidget(label("Checkout", "h1"))
        row = QHBoxLayout()
        row.setSpacing(20)
        left = QVBoxLayout()
        left.setSpacing(14)

        d, dl = card("true", (20, 18, 20, 18), 8)
        dl.addWidget(label("1. Delivery method", "h3"))
        self.method_group = QButtonGroup(self)
        self.m_delivery = QRadioButton(f"🚚  Home delivery (₹{catalog.DELIVERY_FEE_STANDARD}; large items ₹{catalog.DELIVERY_FEE_LARGE}; "
                                       f"free above {rupees(catalog.FREE_DELIVERY_ABOVE)} per seller)")
        self.m_pickup = QRadioButton("🏬  Pick up from seller (free)")
        for rb in (self.m_delivery, self.m_pickup):
            self.method_group.addButton(rb)
            rb.toggled.connect(self._recalc)
            dl.addWidget(rb)
        self.m_delivery.setChecked(True)
        left.addWidget(d)

        a, al = card("true", (20, 18, 20, 18), 8)
        al.addWidget(label("2. Delivery address", "h3"))
        u = self.state.user
        self.f_name = QLineEdit(u.get("name", ""))
        self.f_phone = QLineEdit(u.get("phone", ""))
        self.f_line1 = QLineEdit()
        self.f_line1.setPlaceholderText("House / flat, street, area")
        self.f_city = QLineEdit(u.get("city", ""))
        self.f_pin = QLineEdit()
        self.f_pin.setPlaceholderText("6-digit PIN code")
        self.f_pin.setMaxLength(6)
        g = QGridLayout()
        g.setSpacing(10)
        for i, (t, w) in enumerate((("Full name", self.f_name), ("Mobile", self.f_phone), ("Address", self.f_line1),
                                    ("City", self.f_city), ("PIN code", self.f_pin))):
            g.addWidget(label(t, "muted"), i, 0)
            g.addWidget(w, i, 1)
        al.addLayout(g)
        self.addr_card = a
        left.addWidget(a)

        s, sl = card("true", (20, 18, 20, 18), 8)
        sl.addWidget(label("3. Add-on services (optional)", "h3"))
        self.svc = {}
        for key in ("inspection", "extended_warranty"):
            svc = catalog.SERVICES[key]
            cb = QCheckBox(f"{svc['name']} — {rupees(svc['price'])}" + (" per item" if key == "extended_warranty" else " per seller"))
            cb.toggled.connect(self._recalc)
            self.svc[key] = cb
            sl.addWidget(cb)
        left.addWidget(s)

        self.items_card, self.items_l = card("true", (20, 18, 20, 18), 8)
        left.addWidget(self.items_card)
        left.addStretch()
        lw = QWidget()
        lw.setLayout(left)
        row.addWidget(lw, 3)

        self.side = QVBoxLayout()
        sw = QWidget()
        sw.setLayout(self.side)
        sw.setFixedWidth(370)
        row.addWidget(sw)
        rw = QWidget()
        rw.setLayout(row)
        self.body.addWidget(rw)
        self.body.addStretch()
        self._building = False
        self._recalc()

    def _summary(self):
        method = "pickup" if self.m_pickup.isChecked() else "delivery"
        services = [k for k, cb in self.svc.items() if cb.isChecked()]
        if self.buy_now:
            return marketplace.cart_summary(self.state.uid, method, services, self.buy_now["listing_id"],
                                            self.buy_now["qty"]), method, services
        return marketplace.cart_summary(self.state.uid, method, services), method, services

    def _recalc(self, *_):
        if getattr(self, "_building", True):
            return
        self.addr_card.setVisible(self.m_delivery.isChecked())
        try:
            summary, _, _ = self._summary()
        except marketplace.MarketError as e:
            clear_layout(self.side)
            self.side.addWidget(label(str(e), "h3"))
            return
        clear_layout(self.items_l)
        self.items_l.addWidget(label("4. Review items", "h3"))
        for g in summary["groups"]:
            self.items_l.addWidget(label(f"<b>Seller: {g['seller']}</b> · delivery "
                                         f"{'free' if g['delivery_fee'] == 0 else rupees(g['delivery_fee'])}", "muted"))
            for it in g["items"]:
                r = QHBoxLayout()
                pic = QLabel()
                pic.setPixmap(rounded_pixmap(it.get("cover"), 56, 44, 8))
                r.addWidget(pic)
                r.addWidget(label(it["title"]), 1)
                r.addWidget(label(f"{it['cart_qty']} × {rupees(it['price'])}"))
                self.items_l.addLayout(r)
        clear_layout(self.side)
        sc, scl = summary_card(summary)
        for p in summary["problems"]:
            scl.addWidget(label(f"⚠️ {p}", "small", wrap=True))
        self.pay_btn = button(f"🔒  Pay {rupees(summary['total'])}", "primary", self._place)
        self.pay_btn.setMinimumHeight(48)
        self.pay_btn.setEnabled(not summary["problems"] and bool(summary["groups"]))
        scl.addWidget(self.pay_btn)
        scl.addWidget(label("You'll complete payment on Razorpay (UPI, cards, netbanking, wallets). Your order is "
                            "confirmed only after our server verifies the payment.", "small", wrap=True))
        badges = QHBoxLayout()
        for t in ("UPI", "Cards", "NetBanking", "Wallets"):
            badges.addWidget(badge(t, theme.INK, "#eef2ef"))
        badges.addStretch()
        scl.addLayout(badges)
        self.side.addWidget(sc)
        self.side.addStretch()

    def _place(self):
        summary, method, services = self._summary()
        addr = {"name": self.f_name.text(), "phone": self.f_phone.text(), "line1": self.f_line1.text(),
                "city": self.f_city.text(), "pincode": self.f_pin.text()} if method == "delivery" else {}
        try:
            pid = marketplace.create_checkout(self.state.uid, method, addr, services,
                                              self.buy_now["listing_id"] if self.buy_now else None,
                                              self.buy_now["qty"] if self.buy_now else 1)
        except marketplace.MarketError as e:
            QMessageBox.warning(self, "Checkout", str(e))
            return
        paid = pay(self.state, pid, self)
        self.state.cart_changed.emit()
        self.state.data_changed.emit()
        if paid:
            self.state.buy_now = None
            orders = marketplace.orders_for_payment(pid)
            QMessageBox.information(self, "Order confirmed 🎉",
                                    "Payment verified by the server.\n\n" +
                                    "\n".join(f"Order #{o['id']} from {o['seller_display']} — {o['status']}" for o in orders) +
                                    "\n\nTrack it in My Orders.")
            self.state.go("my_orders")
        else:
            QMessageBox.information(self, "Payment not completed",
                                    "Your order is saved as 'Pending Payment'. You can pay or cancel it from My Orders.")
            self.state.go("my_orders")
