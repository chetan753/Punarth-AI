"""Sign in / create account with Common or Industry account type."""
from __future__ import annotations

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (QButtonGroup, QComboBox, QFrame, QHBoxLayout, QLabel, QLineEdit, QStackedWidget,
                               QVBoxLayout, QWidget)

from core import auth, catalog, seed

from .. import theme
from ..widgets import add_shadow, button, label


class AccountTypeCard(QFrame):
    def __init__(self, key, icon, title, text, on_pick):
        super().__init__()
        self.key = key
        self._on_pick = on_pick
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        lay = QVBoxLayout(self)
        lay.setContentsMargins(14, 12, 14, 12)
        ic = QLabel(icon)
        ic.setStyleSheet("font-size:24px;")
        lay.addWidget(ic)
        lay.addWidget(label(title, "h3"))
        lay.addWidget(label(text, "small", wrap=True))
        self.set_selected(False)

    def set_selected(self, sel: bool):
        border = theme.GREEN if sel else theme.BORDER
        bg = theme.GREEN_50 if sel else "white"
        self.setStyleSheet(f"AccountTypeCard {{ background:{bg}; border:2px solid {border}; border-radius:14px; }}")

    def mousePressEvent(self, e):
        self._on_pick(self.key)


class LoginPage(QWidget):
    def __init__(self, state):
        super().__init__()
        self.state = state
        root = QHBoxLayout(self)
        root.setContentsMargins(0, 0, 0, 0)
        root.setSpacing(0)

        hero = QFrame()
        hero.setStyleSheet("QFrame { background: qlineargradient(x1:0,y1:0,x2:1,y2:1, stop:0 #064e3b, stop:0.6 #15803d,"
                           " stop:1 #22c55e); } QLabel { color: white; background: transparent; }")
        hl = QVBoxLayout(hero)
        hl.setContentsMargins(64, 64, 64, 64)
        b = QLabel("♻  Punarth AI")
        b.setStyleSheet("font-size:30px; font-weight:800;")
        hl.addWidget(b)
        hl.addSpacing(30)
        h = QLabel("Give every device\na second life.")
        h.setStyleSheet("font-size:44px; font-weight:800;")
        hl.addWidget(h)
        sub = QLabel("Scan a device with AI, get a recovery decision, see its resale value and sell it on the "
                     "Punarth Marketplace — or repair, refurbish and recycle it responsibly.")
        sub.setWordWrap(True)
        sub.setStyleSheet("font-size:16px; color:#d1fae5;")
        hl.addWidget(sub)
        hl.addSpacing(28)
        for icon, t in [("📷", "Live AI camera scanner"), ("🧠", "AI segregation: reuse · repair · refurbish · recycle"),
                        ("💰", "Instant resale value & AI-written listings"), ("🛍️", "Buy & sell certified second-hand electronics"),
                        ("🔒", "Secure Razorpay payments, verified on the server")]:
            row = QLabel(f"{icon}   {t}")
            row.setStyleSheet("font-size:15px; font-weight:600; padding:6px 0;")
            hl.addWidget(row)
        hl.addStretch()
        foot = QLabel("Every reused phone saves ~55 kg CO₂ and keeps toxic e-waste out of landfill.")
        foot.setStyleSheet("color:#a7f3d0; font-size:13px;")
        hl.addWidget(foot)
        root.addWidget(hero, 5)

        right = QWidget()
        rl = QVBoxLayout(right)
        rl.setContentsMargins(60, 40, 60, 40)
        rl.addStretch()
        card = QFrame()
        card.setProperty("card", "true")
        card.setMaximumWidth(470)
        add_shadow(card, 40, 30, 10)
        cl = QVBoxLayout(card)
        cl.setContentsMargins(34, 30, 34, 30)
        cl.setSpacing(12)
        tabs = QHBoxLayout()
        self.tab_group = QButtonGroup(self)
        self.signin_tab = button("Sign in", "chip", lambda: self._tab(0))
        self.signup_tab = button("Create account", "chip", lambda: self._tab(1))
        for t in (self.signin_tab, self.signup_tab):
            t.setCheckable(True)
            self.tab_group.addButton(t)
            tabs.addWidget(t)
        tabs.addStretch()
        cl.addLayout(tabs)
        self.forms = QStackedWidget()
        self.forms.addWidget(self._signin_form())
        self.forms.addWidget(self._signup_form())
        cl.addWidget(self.forms)
        self.error = label("", wrap=True)
        self.error.setStyleSheet(f"color:{theme.RED}; font-weight:600;")
        cl.addWidget(self.error)
        wrap = QHBoxLayout()
        wrap.addStretch()
        wrap.addWidget(card)
        wrap.addStretch()
        rl.addLayout(wrap)
        rl.addStretch()
        root.addWidget(right, 6)
        self._tab(0)

    def _tab(self, i):
        self.forms.setCurrentIndex(i)
        (self.signin_tab if i == 0 else self.signup_tab).setChecked(True)
        self.error.setText("")

    def _signin_form(self):
        w = QWidget()
        lay = QVBoxLayout(w)
        lay.setContentsMargins(0, 8, 0, 0)
        lay.setSpacing(10)
        lay.addWidget(label("Welcome back", "h1"))
        lay.addWidget(label("Sign in to scan, sell and shop.", "muted"))
        self.si_email = QLineEdit()
        self.si_email.setPlaceholderText("Email")
        self.si_pass = QLineEdit()
        self.si_pass.setPlaceholderText("Password")
        self.si_pass.setEchoMode(QLineEdit.EchoMode.Password)
        self.si_pass.returnPressed.connect(self._signin)
        lay.addWidget(self.si_email)
        lay.addWidget(self.si_pass)
        lay.addWidget(button("Sign in", "primary", self._signin))
        lay.addSpacing(6)
        lay.addWidget(label(f"Demo accounts (password: {seed.DEMO_PASSWORD})", "small"))
        demo = QHBoxLayout()
        demo.addWidget(button("👤 Common user", "soft", lambda: self._demo("asha@demo.in")))
        demo.addWidget(button("🏭 Industry user", "soft", lambda: self._demo("greencycle@demo.in")))
        lay.addLayout(demo)
        return w

    def _signup_form(self):
        w = QWidget()
        lay = QVBoxLayout(w)
        lay.setContentsMargins(0, 8, 0, 0)
        lay.setSpacing(10)
        lay.addWidget(label("Create your account", "h2"))
        types = QHBoxLayout()
        self.type_cards = [
            AccountTypeCard("common", "👤", "Common User", "Sell or recycle your own devices, shop second-hand.", self._pick),
            AccountTypeCard("industry", "🏭", "Industry User", "Businesses, refurbishers, IT asset disposal, bulk selling.", self._pick),
        ]
        for c in self.type_cards:
            types.addWidget(c)
        lay.addLayout(types)
        self.su_name = QLineEdit()
        self.su_name.setPlaceholderText("Full name")
        self.su_biz = QLineEdit()
        self.su_biz.setPlaceholderText("Business / organisation name")
        self.su_email = QLineEdit()
        self.su_email.setPlaceholderText("Email")
        self.su_pass = QLineEdit()
        self.su_pass.setPlaceholderText("Password (min 6 characters)")
        self.su_pass.setEchoMode(QLineEdit.EchoMode.Password)
        row = QHBoxLayout()
        self.su_city = QComboBox()
        self.su_city.setEditable(True)
        self.su_city.addItems(catalog.CITIES)
        self.su_phone = QLineEdit()
        self.su_phone.setPlaceholderText("Mobile number")
        row.addWidget(self.su_city)
        row.addWidget(self.su_phone)
        for x in (self.su_name, self.su_biz, self.su_email, self.su_pass):
            lay.addWidget(x)
        lay.addLayout(row)
        lay.addWidget(button("Create account", "primary", self._signup))
        self._pick("common")
        return w

    def _pick(self, key):
        self.account_type = key
        for c in self.type_cards:
            c.set_selected(c.key == key)
        self.su_biz.setVisible(key == "industry")

    def _signin(self):
        try:
            self.state.user = auth.login(self.si_email.text(), self.si_pass.text())
            self.state.user_changed.emit()
        except auth.AuthError as e:
            self.error.setText(str(e))

    def _demo(self, email):
        self.si_email.setText(email)
        self.si_pass.setText(seed.DEMO_PASSWORD)
        self._signin()

    def _signup(self):
        try:
            self.state.user = auth.register(self.su_name.text(), self.su_email.text(), self.su_pass.text(),
                                            self.account_type, city=self.su_city.currentText(),
                                            phone=self.su_phone.text(), business_name=self.su_biz.text())
            self.state.user_changed.emit()
        except auth.AuthError as e:
            self.error.setText(str(e))

    def reset(self):
        self.si_pass.clear()
        self.error.setText("")
        self._tab(0)
