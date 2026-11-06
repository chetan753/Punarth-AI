"""My Orders (with tracking) and My Purchases."""
from __future__ import annotations

from PySide6.QtCore import Qt
from PySide6.QtWidgets import QHBoxLayout, QLabel, QMessageBox, QVBoxLayout, QWidget

from core import marketplace

from .. import theme
from ..widgets import (badge, button, card, clear_layout, empty_state, label, rounded_pixmap, rupees, status_badge)
from .common import ScrollPage
from .dialogs import pay


def tracking_bar(order: dict) -> QWidget:
    flow = marketplace.ORDER_FLOW_PICKUP if order["delivery_method"] == "pickup" else marketplace.ORDER_FLOW_DELIVERY
    w = QWidget()
    row = QHBoxLayout(w)
    row.setContentsMargins(0, 6, 0, 6)
    row.setSpacing(0)
    cur = flow.index(order["status"]) if order["status"] in flow else -1
    for i, step in enumerate(flow):
        done = i <= cur
        dot = QLabel("✓" if done else str(i + 1))
        dot.setFixedSize(26, 26)
        dot.setAlignment(Qt.AlignmentFlag.AlignCenter)
        dot.setStyleSheet(f"background:{theme.GREEN if done else '#e5ede8'}; color:{'white' if done else theme.MUTED};"
                          " border-radius:13px; font-weight:800; font-size:12px;")
        col = QVBoxLayout()
        col.setSpacing(4)
        col.addWidget(dot, 0, Qt.AlignmentFlag.AlignHCenter)
        t = label(step, "small")
        t.setAlignment(Qt.AlignmentFlag.AlignCenter)
        if i == cur:
            t.setStyleSheet(f"color:{theme.GREEN_DARK}; font-weight:800; font-size:12px;")
        col.addWidget(t)
        row.addLayout(col)
        if i < len(flow) - 1:
            line = QLabel()
            line.setFixedHeight(3)
            line.setStyleSheet(f"background:{theme.GREEN if i < cur else '#e5ede8'}; border-radius:1px;")
            row.addWidget(line, 1, Qt.AlignmentFlag.AlignTop)
    return w


def order_card(state, o: dict, parent, buyer_view: bool = True, on_change=None) -> QWidget:
    c, cl = card("true", (20, 16, 20, 16), 10)
    head = QHBoxLayout()
    head.addWidget(label(f"<b>Order #{o['id']}</b>"))
    head.addWidget(label(f"{o['created_at'][:10]} · {'from ' + o['seller_display'] if buyer_view else 'to ' + o['buyer_name']}", "muted"))
    head.addStretch()
    if o.get("tracking_code"):
        head.addWidget(label(f"Tracking {o['tracking_code']}", "small"))
    head.addWidget(status_badge(o["status"]))
    cl.addLayout(head)
    for it in o["items"]:
        r = QHBoxLayout()
        pic = QLabel()
        pic.setPixmap(rounded_pixmap(it.get("cover"), 64, 50, 8))
        r.addWidget(pic)
        t = button(it["title"], "link", lambda _=False, lid=it["listing_id"]: state.go("product", id=lid))
        r.addWidget(t)
        r.addStretch()
        r.addWidget(label(f"{it['qty']} × {rupees(it['price'])}", "muted"))
        cl.addLayout(r)
    tot = QHBoxLayout()
    tot.addWidget(label(f"{'🚚 Delivery' if o['delivery_method'] == 'delivery' else '🏬 Pickup'} · "
                        f"items {rupees(o['subtotal'])} + delivery {rupees(o['delivery_fee'])}"
                        + (f" + services {rupees(o['services_fee'])}" if o["services_fee"] else ""), "small"))
    tot.addStretch()
    tot.addWidget(label(f"<b>Total {rupees(o['total'])}</b>"))
    cl.addLayout(tot)
    if o["status"] in marketplace.PAID_STATES:
        cl.addWidget(tracking_bar(o))
    if o["events"]:
        last = o["events"][-1]
        cl.addWidget(label(f"Latest: {last['status']} — {last['note'] or ''} ({last['created_at'][:16].replace('T', ' ')})",
                           "small", wrap=True))
    if buyer_view and o["status"] in ("Pending Payment", "Payment Failed"):
        r = QHBoxLayout()
        r.addWidget(label("Payment not completed. The order is reserved only after the server verifies payment.",
                          "small", wrap=True), 1)

        def retry():
            if pay(state, o["payment_id"], parent):
                state.toast("Payment verified. Order confirmed!", "success")
                state.cart_changed.emit()
                state.data_changed.emit()
            if on_change:
                on_change()

        def cancel():
            if QMessageBox.question(parent, "Cancel order", "Cancel this unpaid order?") == QMessageBox.StandardButton.Yes:
                marketplace.cancel_unpaid_payment(state.uid, o["payment_id"])
                if on_change:
                    on_change()
        r.addWidget(button("Cancel", "danger", cancel))
        r.addWidget(button("Pay now", "primary", retry))
        cl.addLayout(r)
    if o["status"] == "Refund Required":
        cl.addWidget(label("This item sold out before your payment completed. A full refund will be issued to your "
                           "original payment method.", "small", wrap=True))
    return c


class MyOrdersPage(ScrollPage):
    def on_show(self, **_):
        clear_layout(self.body)
        self.body.addWidget(label("My Orders", "h1"))
        self.body.addWidget(label("Track every order you've placed. Each seller ships separately.", "muted"))
        orders = marketplace.buyer_orders(self.state.uid)
        if not orders:
            self.body.addWidget(empty_state("📦", "No orders yet", "When you buy something it will appear here with live tracking.",
                                            "Browse electronics", lambda: self.state.go("browse")))
        for o in orders:
            self.body.addWidget(order_card(self.state, o, self, True, self.on_show))
        self.body.addStretch()


class MyPurchasesPage(ScrollPage):
    def on_show(self, **_):
        clear_layout(self.body)
        self.body.addWidget(label("My Purchases", "h1"))
        self.body.addWidget(label("Devices you've bought on Punarth Market.", "muted"))
        orders = marketplace.buyer_purchases(self.state.uid)
        items = [(o, it) for o in orders for it in o["items"]]
        if not items:
            self.body.addWidget(empty_state("🛍️", "No purchases yet", "Your paid orders will show up here.",
                                            "Browse electronics", lambda: self.state.go("browse")))
        spent = sum(o["total"] for o in orders)
        if items:
            self.body.addWidget(badge(f"{len(items)} device(s) · {rupees(spent)} spent · second-life tech 🌱",
                                      theme.GREEN_DARK, theme.GREEN_100))
        for o, it in items:
            c, cl = card("true", (16, 14, 16, 14))
            r = QHBoxLayout()
            pic = QLabel()
            pic.setPixmap(rounded_pixmap(it.get("cover"), 120, 90, 10))
            r.addWidget(pic)
            col = QVBoxLayout()
            col.addWidget(label(f"<b>{it['title']}</b>", wrap=True))
            col.addWidget(label(f"Bought {o['created_at'][:10]} from {o['seller_display']} · {rupees(it['price'])} × {it['qty']}", "muted"))
            sr = QHBoxLayout()
            sr.addWidget(status_badge(o["status"]))
            sr.addStretch()
            col.addLayout(sr)
            r.addLayout(col, 1)
            bc = QVBoxLayout()
            bc.addWidget(button("View item", "soft", lambda _=False, lid=it["listing_id"]: self.state.go("product", id=lid)))
            bc.addWidget(button("Track order", None, lambda: self.state.go("my_orders")))
            bc.addWidget(button("Resell later", None, lambda: self.state.go("scanner"),
                                "When you're done with it, scan it again to resell"))
            r.addLayout(bc)
            cl.addLayout(r)
            self.body.addWidget(c)
        self.body.addStretch()
