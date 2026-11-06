"""Dialogs: payment (server-verified), recovery requests, messages,
contact seller, listing preview."""
from __future__ import annotations

from PySide6.QtCore import Qt, QTimer, QUrl
from PySide6.QtGui import QDesktopServices
from PySide6.QtWidgets import (QComboBox, QDialog, QHBoxLayout, QLineEdit, QListWidget, QListWidgetItem,
                               QMessageBox, QPlainTextEdit, QVBoxLayout, QWidget)

from core import catalog, marketplace, payments_client

from .. import theme
from ..widgets import (ImageGallery, badge, button, condition_badge, label, provenance_badge, run_async,
                       rupees, scroll)


class PaymentDialog(QDialog):
    """Starts a payment on the server, opens the checkout page in the browser,
    then polls the SERVER for the verified status. The app never decides that a
    payment succeeded on its own."""

    def __init__(self, state, payment_id: int, parent=None):
        super().__init__(parent)
        self.state = state
        self.payment_id = payment_id
        self.url = ""
        self.final_status = ""
        self.setWindowTitle("Secure payment")
        self.setMinimumWidth(480)
        lay = QVBoxLayout(self)
        lay.setContentsMargins(26, 24, 26, 22)
        lay.setSpacing(12)
        lay.addWidget(label("🔒  Secure payment", "h2"))
        p = marketplace.get_payment(payment_id)
        lay.addWidget(label(f"Amount: <b>{rupees(p['amount_paise'] / 100)}</b>"))
        self.status = label("Connecting to the payment server…", "muted", wrap=True)
        lay.addWidget(self.status)
        self.note = label("", "small", wrap=True)
        lay.addWidget(self.note)
        row = QHBoxLayout()
        self.open_btn = button("Open payment page", "primary", self._open)
        self.open_btn.setEnabled(False)
        row.addWidget(self.open_btn)
        row.addStretch()
        row.addWidget(button("Close", None, self.reject))
        lay.addLayout(row)
        self.timer = QTimer(self)
        self.timer.setInterval(2000)
        self.timer.timeout.connect(self._poll)
        self._polling = False
        run_async(self._start, self._started, self._failed)

    def _start(self):
        if not payments_client.ensure_server_running():
            raise RuntimeError("The payment server is not reachable. Start it with:\n"
                               "python -m payment_server.server")
        return payments_client.start(self.payment_id)

    def _started(self, data):
        self.url = data["checkout_url"]
        demo = data.get("mode") == "demo"
        self.note.setText("Demo mode: Razorpay keys are not set, so a test page simulates the payment. "
                          "The payment server still records the result." if demo else
                          "Pay with UPI, card, netbanking or wallet on Razorpay. This window updates automatically "
                          "once the server verifies the payment.")
        self.open_btn.setEnabled(True)
        if data.get("status") == "paid":
            self._finish("paid")
            return
        self.status.setText("⏳ Waiting for payment… complete it in your browser.")
        self._open()
        self.timer.start()

    def _failed(self, msg):
        self.status.setText(f"❌ {msg}")
        self.status.setStyleSheet(f"color:{theme.RED};")

    def _open(self):
        if self.url:
            QDesktopServices.openUrl(QUrl(self.url))

    def _poll(self):
        if self._polling:
            return
        self._polling = True

        def done(d):
            self._polling = False
            if d["status"] in ("paid", "failed"):
                self._finish(d["status"], d.get("failure_reason", ""))

        def fail(_):
            self._polling = False
        run_async(payments_client.status, done, fail, self.payment_id)

    def _finish(self, status, reason=""):
        self.timer.stop()
        self.final_status = status
        if status == "paid":
            self.status.setText("✅ Payment verified by the server.")
            self.status.setStyleSheet(f"color:{theme.GREEN_DARK}; font-weight:700;")
            QTimer.singleShot(700, self.accept)
        else:
            self.status.setText(f"❌ Payment failed. {reason}")
            self.status.setStyleSheet(f"color:{theme.RED}; font-weight:700;")

    def done(self, r):  # noqa: D401 - Qt override
        self.timer.stop()
        super().done(r)


def pay(state, payment_id: int, parent) -> bool:
    dlg = PaymentDialog(state, payment_id, parent)
    dlg.exec()
    return dlg.final_status == "paid"


class RecoveryRequestDialog(QDialog):
    TITLES = {"repair": ("🔧", "Book a repair partner", "repair"),
              "refurbish": ("✨", "Create refurbishment request", "refurbish"),
              "recycle_collection": ("♻️", "Book authorised e-waste collection", "recycler"),
              "donate": ("🎁", "Donate this device", "refurbish"),
              "inspection": ("🔍", "Book a partner inspection", "repair")}

    def __init__(self, state, rtype: str, assessment_id, category: str, parent=None):
        super().__init__(parent)
        self.state, self.rtype, self.assessment_id = state, rtype, assessment_id
        icon, title, ptype = self.TITLES[rtype]
        self.setWindowTitle(title)
        self.setMinimumWidth(520)
        lay = QVBoxLayout(self)
        lay.setContentsMargins(24, 22, 24, 20)
        lay.setSpacing(10)
        lay.addWidget(label(f"{icon}  {title}", "h2"))
        lay.addWidget(label(f"Device category: {category}", "muted"))
        self.partners = marketplace.partners(ptype, state.user.get("city", ""))
        self.combo = QComboBox()
        for p in self.partners:
            tag = " · CPCB authorised" if p["authorized"] else ""
            self.combo.addItem(f"{p['name']} — {p['city']} · ★{p['rating']}{tag}", p["id"])
        lay.addWidget(label("Partner", "muted"))
        lay.addWidget(self.combo)
        self.desc = label("", "small", wrap=True)
        lay.addWidget(self.desc)
        self.combo.currentIndexChanged.connect(self._desc)
        self._desc()
        lay.addWidget(label("Pickup / visit preference", "muted"))
        self.when = QComboBox()
        self.when.addItems(["Doorstep pickup — next available slot", "Doorstep pickup — weekend",
                            "I will drop it at the partner"])
        lay.addWidget(self.when)
        self.addr = QLineEdit(state.user.get("city", ""))
        self.addr.setPlaceholderText("Pickup address")
        lay.addWidget(self.addr)
        self.notes = QPlainTextEdit()
        self.notes.setPlaceholderText("Notes for the partner (optional)")
        self.notes.setMaximumHeight(80)
        lay.addWidget(self.notes)
        if rtype == "recycle_collection":
            lay.addWidget(label("Collection by authorised recyclers is free. You'll receive a recycling certificate.",
                                "small", wrap=True))
        row = QHBoxLayout()
        row.addStretch()
        row.addWidget(button("Cancel", None, self.reject))
        row.addWidget(button("Submit request", "primary", self._submit))
        lay.addLayout(row)

    def _desc(self):
        i = self.combo.currentIndex()
        if 0 <= i < len(self.partners):
            self.desc.setText(self.partners[i]["description"])

    def _submit(self):
        if not self.partners:
            QMessageBox.warning(self, "No partners", "No partners are available yet.")
            return
        marketplace.create_recovery_request(self.state.uid, self.rtype, self.assessment_id, self.combo.currentData(),
                                            {"when": self.when.currentText(), "address": self.addr.text(),
                                             "notes": self.notes.toPlainText()})
        self.state.data_changed.emit()
        self.accept()


class ContactSellerDialog(QDialog):
    def __init__(self, state, listing: dict, parent=None):
        super().__init__(parent)
        self.state, self.listing = state, listing
        self.setWindowTitle("Contact seller")
        self.setMinimumWidth(460)
        lay = QVBoxLayout(self)
        lay.setContentsMargins(24, 22, 24, 20)
        lay.addWidget(label(f"Message {listing['seller_display']}", "h2"))
        lay.addWidget(label(f"About: {listing['title']}", "muted", wrap=True))
        self.body = QPlainTextEdit()
        self.body.setPlainText("Hi, is this still available? ")
        lay.addWidget(self.body)
        lay.addWidget(label("For your safety, pay only through Punarth AI checkout.", "small"))
        row = QHBoxLayout()
        row.addStretch()
        row.addWidget(button("Cancel", None, self.reject))
        row.addWidget(button("Send", "primary", self._send))
        lay.addLayout(row)

    def _send(self):
        try:
            marketplace.send_message(self.state.uid, self.listing["seller_id"], self.body.toPlainText(), self.listing["id"])
        except marketplace.MarketError as e:
            QMessageBox.warning(self, "Can't send", str(e))
            return
        self.accept()


class MessagesDialog(QDialog):
    def __init__(self, state, parent=None):
        super().__init__(parent)
        self.state = state
        self.setWindowTitle("Messages")
        self.resize(640, 520)
        lay = QVBoxLayout(self)
        lay.setContentsMargins(20, 18, 20, 18)
        lay.addWidget(label("💬  Messages", "h2"))
        self.list = QListWidget()
        self.list.setStyleSheet("QListWidget { border:1px solid #e2eee6; border-radius:12px; } "
                                "QListWidget::item { padding:10px; border-bottom:1px solid #eef5f0; }")
        lay.addWidget(self.list, 1)
        self.reply_to = None
        self.reply = QLineEdit()
        self.reply.setPlaceholderText("Select a message, type a reply and press Enter")
        self.reply.returnPressed.connect(self._send)
        lay.addWidget(self.reply)
        self.list.currentItemChanged.connect(self._select)
        self._load()
        marketplace.mark_messages_read(state.uid)

    def _load(self):
        self.list.clear()
        for m in marketplace.inbox(self.state.uid):
            incoming = m["recipient_id"] == self.state.uid
            who = f"From {m['sender_name']}" if incoming else f"To {m['recipient_name']}"
            about = f" · re: {m['listing_title']}" if m.get("listing_title") else ""
            it = QListWidgetItem(f"{'🔵 ' if incoming and not m['is_read'] else ''}{who}{about}\n{m['body']}\n{m['created_at'][:16].replace('T', ' ')}")
            it.setData(Qt.ItemDataRole.UserRole, m)
            self.list.addItem(it)
        if self.list.count() == 0:
            self.list.addItem("No messages yet.")

    def _select(self, item, _prev=None):
        m = item.data(Qt.ItemDataRole.UserRole) if item else None
        if not m:
            return
        other = m["sender_id"] if m["recipient_id"] == self.state.uid else m["recipient_id"]
        self.reply_to = (other, m.get("listing_id"))

    def _send(self):
        if not self.reply_to or not self.reply.text().strip():
            return
        marketplace.send_message(self.state.uid, self.reply_to[0], self.reply.text(), self.reply_to[1])
        self.reply.clear()
        self._load()


class ListingPreviewDialog(QDialog):
    """Shows the listing exactly as buyers will see it before publishing."""

    def __init__(self, values: dict, images: list[str], provenance: dict, seller_name: str, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Listing preview")
        self.resize(980, 680)
        outer = QVBoxLayout(self)
        inner = QWidget()
        lay = QHBoxLayout(inner)
        lay.setContentsMargins(20, 20, 20, 20)
        lay.setSpacing(24)
        g = ImageGallery(440, 330)
        g.set_images(images)
        lay.addWidget(g, 0, Qt.AlignmentFlag.AlignTop)
        col = QVBoxLayout()
        col.setSpacing(8)
        col.addWidget(badge("PREVIEW — not yet published", "#92400e", "#fef3c7"))
        t = label(values.get("title", ""), "h1", wrap=True)
        t.setStyleSheet("font-size:24px; font-weight:800;")
        col.addWidget(t)
        if provenance.get("title"):
            col.addWidget(provenance_badge(provenance["title"]))
        col.addWidget(label(" · ".join(x for x in (values.get("brand"), values.get("model"), values.get("category")) if x), "muted"))
        row = QHBoxLayout()
        row.addWidget(condition_badge(values.get("condition", "Good")))
        row.addWidget(badge(values.get("functionality_status", ""), theme.INK, "#eef2ef"))
        row.addStretch()
        col.addLayout(row)
        col.addWidget(label(rupees(values.get("price", 0)), "bigprice"))
        col.addWidget(label(f"📍 {values.get('location', '')} · Sold by {seller_name}", "muted"))
        d = label(values.get("description", ""), wrap=True)
        col.addWidget(d)
        if values.get("defects"):
            col.addWidget(label("Known defects: " + "; ".join(values["defects"]), wrap=True))
        col.addWidget(label("Condition guide: " + catalog.CONDITION_DESCRIPTIONS.get(values.get("condition", "Good"), ""),
                            "small", wrap=True))
        col.addStretch()
        lay.addLayout(col, 1)
        outer.addWidget(scroll(inner), 1)
        row = QHBoxLayout()
        row.addStretch()
        row.addWidget(button("Keep editing", None, self.reject))
        row.addWidget(button("Publish listing", "primary", self.accept))
        outer.addLayout(row)


class AnswerQuestionDialog(QDialog):
    def __init__(self, question: dict, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Answer buyer question")
        self.setMinimumWidth(460)
        lay = QVBoxLayout(self)
        lay.setContentsMargins(22, 20, 22, 18)
        lay.addWidget(label(question.get("listing_title", ""), "muted", wrap=True))
        lay.addWidget(label(f"❓ {question['question']}", "h3", wrap=True))
        self.edit = QPlainTextEdit(question.get("answer") or "")
        lay.addWidget(self.edit)
        row = QHBoxLayout()
        row.addStretch()
        row.addWidget(button("Cancel", None, self.reject))
        row.addWidget(button("Post answer", "primary", self.accept))
        lay.addLayout(row)

    def text(self) -> str:
        return self.edit.toPlainText().strip()
