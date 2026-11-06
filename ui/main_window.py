"""Main window: login, role-based sidebar (Common / Industry), app pages and
the Marketplace with its own header navigation. Pages cross-fade."""
from __future__ import annotations

from PySide6.QtCore import QEasingCurve, QPropertyAnimation, Qt
from PySide6.QtWidgets import (QButtonGroup, QFrame, QGraphicsOpacityEffect, QHBoxLayout, QLabel, QLineEdit,
                               QMainWindow, QMessageBox, QStackedWidget, QVBoxLayout, QWidget)

from core import auth, marketplace

from .state import AppState
from .widgets import CountBadgeButton, Toast, button

APP_PAGES = {"dashboard", "scanner", "recovery"}
MARKET_PAGES = ["market_home", "browse", "product", "sell", "create_listing", "my_listings", "my_orders",
                "my_purchases", "cart", "wishlist", "checkout", "seller_dashboard"]

MARKET_NAV = [("market_home", "Home"), ("browse", "Browse Electronics"), ("sell", "Sell Your Device"),
              ("my_listings", "My Listings"), ("my_orders", "My Orders"), ("my_purchases", "My Purchases"),
              ("seller_dashboard", "Seller Dashboard")]


def fade_switch(stack: QStackedWidget, widget: QWidget):
    if stack.currentWidget() is widget:
        return
    stack.setCurrentWidget(widget)
    eff = QGraphicsOpacityEffect(widget)
    widget.setGraphicsEffect(eff)
    anim = QPropertyAnimation(eff, b"opacity", widget)
    anim.setDuration(240)
    anim.setStartValue(0.0)
    anim.setEndValue(1.0)
    anim.setEasingCurve(QEasingCurve.Type.OutCubic)
    anim.finished.connect(lambda: widget.setGraphicsEffect(None))
    anim.start()
    widget._switch_anim = anim


class Sidebar(QFrame):
    def __init__(self, state: AppState):
        super().__init__()
        self.state = state
        self.setObjectName("Sidebar")
        self.setFixedWidth(236)
        self.lay = QVBoxLayout(self)
        self.lay.setContentsMargins(16, 22, 16, 18)
        self.lay.setSpacing(4)
        self.group = QButtonGroup(self)
        self.group.setExclusive(True)
        self.buttons: dict[str, object] = {}

    def build(self):
        while self.lay.count():
            it = self.lay.takeAt(0)
            if it.widget():
                it.widget().deleteLater()
        for b in list(self.group.buttons()):
            self.group.removeButton(b)
        self.buttons.clear()
        u = self.state.user
        brand = QLabel("♻  Punarth AI")
        brand.setObjectName("SidebarBrand")
        self.lay.addWidget(brand)
        role = QLabel("INDUSTRY ACCOUNT" if self.state.is_industry else "PERSONAL ACCOUNT")
        role.setObjectName("SidebarRole")
        self.lay.addWidget(role)
        self.lay.addSpacing(18)
        if self.state.is_industry:
            items = [("dashboard", "🏭   Business Dashboard"), ("scanner", "📷   AI Scanner & Intake"),
                     ("recovery", "♻️   Recovery Center"), ("market_home", "🛍️   Marketplace"),
                     ("seller_dashboard", "📊   Seller Dashboard")]
        else:
            items = [("dashboard", "🏠   Dashboard"), ("scanner", "📷   AI Scanner"),
                     ("recovery", "♻️   Recovery Center"), ("market_home", "🛍️   Marketplace"),
                     ("sell", "💸   Sell a Device")]
        for key, text in items:
            b = button(text)
            b.setProperty("nav", "true")
            b.setCheckable(True)
            b.clicked.connect(lambda _=False, k=key: self.state.go(k))
            self.group.addButton(b)
            self.buttons[key] = b
            self.lay.addWidget(b)
        self.lay.addStretch()
        who = QLabel(f"<b style='color:white'>{auth.display_name(u)}</b><br><span style='font-size:12px'>{u['email']}</span>")
        who.setWordWrap(True)
        self.lay.addWidget(who)
        out = button("Sign out", None, self._logout)
        out.setStyleSheet("QPushButton { background: rgba(255,255,255,0.1); color: white; border: 0; }"
                          "QPushButton:hover { background: rgba(255,255,255,0.2); }")
        self.lay.addWidget(out)

    def _logout(self):
        self.state.user = None
        self.state.user_changed.emit()

    def highlight(self, page: str):
        key = page if page in self.buttons else ("market_home" if page in MARKET_PAGES else None)
        if page == "sell" and "sell" in self.buttons:
            key = "sell"
        if page == "seller_dashboard" and "seller_dashboard" in self.buttons:
            key = "seller_dashboard"
        if key and key in self.buttons:
            self.buttons[key].setChecked(True)


class MarketplaceShell(QWidget):
    """Marketplace area: own header (brand, search, wishlist, cart, account) + nav + pages."""

    def __init__(self, state: AppState):
        super().__init__()
        self.state = state
        lay = QVBoxLayout(self)
        lay.setContentsMargins(0, 0, 0, 0)
        lay.setSpacing(0)
        header = QFrame()
        header.setObjectName("MarketHeader")
        hl = QVBoxLayout(header)
        hl.setContentsMargins(28, 14, 28, 0)
        hl.setSpacing(8)
        top = QHBoxLayout()
        brand = QLabel("Punarth <span style='color:#16a34a'>Market</span>")
        brand.setObjectName("MarketBrand")
        brand.setTextFormat(Qt.TextFormat.RichText)
        top.addWidget(brand)
        tag = QLabel("Certified second-life electronics")
        tag.setProperty("role", "small")
        top.addWidget(tag)
        top.addSpacing(18)
        self.search = QLineEdit()
        self.search.setObjectName("MarketSearch")
        self.search.setPlaceholderText("🔍  Search phones, laptops, brands, models…")
        self.search.returnPressed.connect(self._search)
        top.addWidget(self.search, 1)
        top.addSpacing(10)
        self.wish_btn = CountBadgeButton("♡  Wishlist")
        self.wish_btn.clicked.connect(lambda: state.go("wishlist"))
        self.cart_btn = CountBadgeButton("🛒  Cart")
        self.cart_btn.clicked.connect(lambda: state.go("cart"))
        self.msg_btn = CountBadgeButton("💬")
        self.msg_btn.setToolTip("Messages")
        self.msg_btn.clicked.connect(self._messages)
        sell = button("+ Sell", "primary", lambda: state.go("sell"))
        for w in (self.wish_btn, self.cart_btn, self.msg_btn, sell):
            top.addWidget(w)
        hl.addLayout(top)
        nav = QHBoxLayout()
        nav.setSpacing(2)
        self.nav_group = QButtonGroup(self)
        self.nav_buttons = {}
        for key, text in MARKET_NAV:
            b = button(text, "mnav")
            b.setCheckable(True)
            b.clicked.connect(lambda _=False, k=key: state.go(k))
            self.nav_group.addButton(b)
            self.nav_buttons[key] = b
            nav.addWidget(b)
        nav.addStretch()
        hl.addLayout(nav)
        lay.addWidget(header)
        self.stack = QStackedWidget()
        lay.addWidget(self.stack, 1)
        state.cart_changed.connect(self.refresh_counts)
        state.wishlist_changed.connect(self.refresh_counts)
        state.data_changed.connect(self.refresh_counts)

    def _search(self):
        self.state.go("browse", text=self.search.text().strip())

    def _messages(self):
        from .pages.dialogs import MessagesDialog
        MessagesDialog(self.state, self).exec()
        self.refresh_counts()

    def refresh_counts(self):
        if not self.state.user:
            return
        self.cart_btn.set_count(marketplace.cart_count(self.state.uid))
        self.wish_btn.set_count(len(marketplace.wishlist_ids(self.state.uid)))
        unread = sum(1 for m in marketplace.inbox(self.state.uid) if m["recipient_id"] == self.state.uid and not m["is_read"])
        self.msg_btn.set_count(unread)

    def highlight(self, page: str):
        alias = {"product": "browse", "create_listing": "sell", "checkout": None, "cart": None, "wishlist": None}
        key = alias.get(page, page)
        if key in self.nav_buttons:
            self.nav_buttons[key].setChecked(True)
        else:
            self.nav_group.setExclusive(False)
            for b in self.nav_buttons.values():
                b.setChecked(False)
            self.nav_group.setExclusive(True)


class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("Punarth AI — E-waste Recovery & Second-Hand Electronics Marketplace")
        self.resize(1440, 900)
        self.setMinimumSize(1100, 700)
        self.state = AppState()
        self.root = QStackedWidget()
        self.root.setObjectName("AppRoot")
        self.setCentralWidget(self.root)

        from .pages.login import LoginPage
        self.login = LoginPage(self.state)
        self.root.addWidget(self.login)

        self.shell = QWidget()
        sh = QHBoxLayout(self.shell)
        sh.setContentsMargins(0, 0, 0, 0)
        sh.setSpacing(0)
        self.sidebar = Sidebar(self.state)
        sh.addWidget(self.sidebar)
        self.content = QStackedWidget()
        sh.addWidget(self.content, 1)
        self.root.addWidget(self.shell)
        self.market = MarketplaceShell(self.state)
        self.content.addWidget(self.market)

        self.pages: dict[str, QWidget] = {}
        self.history: list[tuple[str, dict]] = []
        self.current: tuple[str, dict] | None = None
        self.state.user_changed.connect(self._on_user)
        # Queued so a page is never rebuilt while one of its own widgets is still handling a click.
        self.state.navigate_requested.connect(self.navigate, Qt.ConnectionType.QueuedConnection)
        self.state.back_requested.connect(self.go_back)
        self.state.toast_requested.connect(lambda t, k: Toast(self, t, k))

    # Pages are created lazily on first use.
    def _page(self, name: str) -> QWidget:
        if name in self.pages:
            return self.pages[name]
        from .pages import cart, dashboard, market_home, orders, product, recovery, scanner, sell, seller
        from .pages import browse as browse_mod
        factories = {
            "dashboard": dashboard.DashboardPage, "scanner": scanner.ScannerPage, "recovery": recovery.RecoveryPage,
            "market_home": market_home.MarketHomePage, "browse": browse_mod.BrowsePage,
            "product": product.ProductPage, "sell": sell.SellPage, "create_listing": sell.CreateListingPage,
            "my_listings": seller.MyListingsPage, "my_orders": orders.MyOrdersPage,
            "my_purchases": orders.MyPurchasesPage, "cart": cart.CartPage, "wishlist": cart.WishlistPage,
            "checkout": cart.CheckoutPage, "seller_dashboard": seller.SellerDashboardPage,
        }
        page = factories[name](self.state)
        self.pages[name] = page
        (self.market.stack if name in MARKET_PAGES else self.content).addWidget(page)
        return page

    def _on_user(self):
        if self.state.user is None:
            if "scanner" in self.pages:
                self.pages["scanner"].on_hide()
            for p in self.pages.values():
                p.setParent(None)
                p.deleteLater()
            self.pages.clear()
            self.history.clear()
            self.current = None
            self.login.reset()
            fade_switch(self.root, self.login)
            return
        self.sidebar.build()
        fade_switch(self.root, self.shell)
        self.market.refresh_counts()
        self.navigate("dashboard", {})

    def navigate(self, name: str, params: dict, push: bool = True):
        if not self.state.user:
            return
        page = self._page(name)
        if push and self.current and self.current[0] != name:
            self.history.append(self.current)
            self.history = self.history[-30:]
        self.current = (name, params)
        # leave scanner -> stop camera
        scanner = self.pages.get("scanner")
        if scanner is not None and name != "scanner":
            scanner.on_hide()
        try:
            page.on_show(**params)
        except Exception as e:  # keep the app usable, show what went wrong
            QMessageBox.warning(self, "Something went wrong", str(e))
        if name in MARKET_PAGES:
            fade_switch(self.content, self.market)
            fade_switch(self.market.stack, page)
            self.market.highlight(name)
            if name != "browse":
                self.market.search.clear()
        else:
            fade_switch(self.content, page)
        self.sidebar.highlight(name)

    def go_back(self):
        if self.history:
            name, params = self.history.pop()
            self.navigate(name, params, push=False)
        else:
            self.navigate("dashboard", {}, push=False)

    def closeEvent(self, e):
        sc = self.pages.get("scanner")
        if sc is not None:
            sc.on_hide()
        super().closeEvent(e)
