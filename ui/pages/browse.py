"""Browse Electronics: search + interactive filters + responsive results grid."""
from __future__ import annotations

from PySide6.QtCore import QTimer
from PySide6.QtWidgets import (QButtonGroup, QCheckBox, QComboBox, QFrame, QHBoxLayout, QLineEdit, QRadioButton,
                               QSpinBox, QVBoxLayout, QWidget)

from core import catalog, marketplace

from .. import theme
from ..widgets import ProductGrid, button, empty_state, label, scroll
from .common import make_cards


class BrowsePage(QWidget):
    def __init__(self, state):
        super().__init__()
        self.state = state
        root = QHBoxLayout(self)
        root.setContentsMargins(0, 0, 0, 0)
        root.setSpacing(0)
        self._debounce = QTimer(self)
        self._debounce.setSingleShot(True)
        self._debounce.setInterval(250)
        self._debounce.timeout.connect(self.refresh)
        self._loading = False

        # ---- filter panel
        panel = QWidget()
        pl = QVBoxLayout(panel)
        pl.setContentsMargins(22, 20, 14, 20)
        pl.setSpacing(10)
        head = QHBoxLayout()
        head.addWidget(label("Filters", "h2"))
        head.addStretch()
        head.addWidget(button("Reset", "link", self.reset))
        pl.addLayout(head)
        self.text = QLineEdit()
        self.text.setPlaceholderText("Name, brand, model or category")
        self.text.textChanged.connect(self._changed)
        pl.addWidget(self.text)

        pl.addWidget(self._title("Category"))
        self.cat_checks = {}
        for c in catalog.CATEGORIES:
            cb = QCheckBox(f"{catalog.CATEGORY_ICONS[c]}  {c}")
            cb.toggled.connect(self._changed)
            self.cat_checks[c] = cb
            pl.addWidget(cb)

        pl.addWidget(self._title("Brand"))
        self.brand = QComboBox()
        self.brand.currentTextChanged.connect(self._changed)
        pl.addWidget(self.brand)

        pl.addWidget(self._title("Price range (₹)"))
        pr = QHBoxLayout()
        self.min_price = QSpinBox()
        self.max_price = QSpinBox()
        for sp in (self.min_price, self.max_price):
            sp.setRange(0, 1_000_000)
            sp.setSingleStep(1000)
            sp.valueChanged.connect(self._changed)
        self.max_price.setValue(1_000_000)
        pr.addWidget(self.min_price)
        pr.addWidget(label("–"))
        pr.addWidget(self.max_price)
        pl.addLayout(pr)
        quick = QHBoxLayout()
        for txt, lo, hi in (("< 5k", 0, 5000), ("5–20k", 5000, 20000), ("20k+", 20000, 1_000_000)):
            b = button(txt, "chip", lambda _=False, lo=lo, hi=hi: self._price(lo, hi))
            quick.addWidget(b)
        pl.addLayout(quick)

        pl.addWidget(self._title("Condition"))
        self.cond_checks = {}
        for c in catalog.CONDITIONS:
            cb = QCheckBox(c)
            cb.toggled.connect(self._changed)
            self.cond_checks[c] = cb
            pl.addWidget(cb)

        pl.addWidget(self._title("Location"))
        self.location = QComboBox()
        self.location.setEditable(True)
        self.location.currentTextChanged.connect(self._changed)
        pl.addWidget(self.location)

        pl.addWidget(self._title("Seller type"))
        self.seller_group = QButtonGroup(self)
        self.seller_radios = {}
        for key, txt in (("", "Any"), ("common", "Individual sellers"), ("industry", "Business sellers")):
            rb = QRadioButton(txt)
            rb.toggled.connect(self._changed)
            self.seller_group.addButton(rb)
            self.seller_radios[key] = rb
            pl.addWidget(rb)
        self.verified = QCheckBox("✔ Verified sellers only")
        self.verified.toggled.connect(self._changed)
        pl.addWidget(self.verified)

        pl.addWidget(self._title("Recently listed"))
        self.recent = QComboBox()
        for txt, d in (("Any time", 0), ("Last 24 hours", 1), ("Last 7 days", 7), ("Last 30 days", 30)):
            self.recent.addItem(txt, d)
        self.recent.currentIndexChanged.connect(self._changed)
        pl.addWidget(self.recent)
        pl.addStretch()
        side = QFrame()
        side.setStyleSheet(f"QFrame#side {{ background:white; border-right:1px solid {theme.BORDER}; }}")
        side.setObjectName("side")
        side.setFixedWidth(300)
        sl = QVBoxLayout(side)
        sl.setContentsMargins(0, 0, 0, 0)
        sl.addWidget(scroll(panel))
        root.addWidget(side)

        # ---- results
        res = QWidget()
        rl = QVBoxLayout(res)
        rl.setContentsMargins(28, 22, 28, 22)
        rl.setSpacing(14)
        top = QHBoxLayout()
        self.title = label("Browse Electronics", "h1")
        top.addWidget(self.title)
        top.addStretch()
        top.addWidget(label("Sort", "muted"))
        self.sort = QComboBox()
        for txt, key in (("Featured", "featured"), ("Newest first", "newest"), ("Price: low to high", "price_asc"),
                         ("Price: high to low", "price_desc"), ("Most viewed", "popular")):
            self.sort.addItem(txt, key)
        self.sort.currentIndexChanged.connect(self._changed)
        top.addWidget(self.sort)
        rl.addLayout(top)
        self.count = label("", "muted")
        rl.addWidget(self.count)
        self.grid = ProductGrid()
        self.empty = empty_state("🔎", "No devices match these filters", "Try removing a filter or widening the price range.",
                                 "Reset filters", self.reset)
        rl.addWidget(self.empty)
        rl.addWidget(self.grid)
        rl.addStretch()
        root.addWidget(scroll(res), 1)

    def _title(self, t):
        lb = label(t)
        lb.setStyleSheet(f"font-weight:800; color:{theme.INK}; margin-top:8px;")
        return lb

    def _price(self, lo, hi):
        self._loading = True
        self.min_price.setValue(lo)
        self.max_price.setValue(hi)
        self._loading = False
        self._changed()

    def _changed(self, *_):
        if not self._loading:
            self._debounce.start()

    def _fill_dynamic(self):
        cur_b, cur_l = self.brand.currentText(), self.location.currentText()
        self.brand.clear()
        self.brand.addItems(["All brands"] + marketplace.brands_in_use())
        self.brand.setCurrentText(cur_b or "All brands")
        self.location.clear()
        self.location.addItems([""] + sorted(set(marketplace.locations_in_use())))
        self.location.setCurrentText(cur_l)

    def reset(self):
        self._loading = True
        self.text.clear()
        for cb in list(self.cat_checks.values()) + list(self.cond_checks.values()):
            cb.setChecked(False)
        self.brand.setCurrentText("All brands")
        self.min_price.setValue(0)
        self.max_price.setValue(1_000_000)
        self.location.setCurrentText("")
        self.seller_radios[""].setChecked(True)
        self.verified.setChecked(False)
        self.recent.setCurrentIndex(0)
        self.sort.setCurrentIndex(0)
        self._loading = False
        self.refresh()

    def on_show(self, text=None, category=None, sort=None, seller_type=None, **_):
        self._loading = True
        self._fill_dynamic()
        if text is not None or category or seller_type or sort:
            self.text.setText(text or "")
            for c, cb in self.cat_checks.items():
                cb.setChecked(c == category)
            if seller_type is not None:
                self.seller_radios.get(seller_type, self.seller_radios[""]).setChecked(True)
            if sort:
                i = self.sort.findData(sort)
                self.sort.setCurrentIndex(max(0, i))
        if not self.seller_group.checkedButton():
            self.seller_radios[""].setChecked(True)
        self._loading = False
        self.refresh()

    def refresh(self):
        cats = [c for c, cb in self.cat_checks.items() if cb.isChecked()]
        conds = [c for c, cb in self.cond_checks.items() if cb.isChecked()]
        brand = self.brand.currentText()
        seller_type = next((k for k, rb in self.seller_radios.items() if rb.isChecked()), "")
        items = marketplace.search_listings(
            text=self.text.text(), categories=cats, brands=[brand] if brand and brand != "All brands" else None,
            min_price=self.min_price.value() or None,
            max_price=self.max_price.value() if self.max_price.value() < 1_000_000 else None,
            conditions=conds, location=self.location.currentText(), seller_type=seller_type,
            verified_only=self.verified.isChecked(), recent_days=self.recent.currentData() or None,
            sort=self.sort.currentData(), exclude_seller=self.state.uid)
        self.title.setText(cats[0] if len(cats) == 1 else "Browse Electronics")
        q = f" for “{self.text.text()}”" if self.text.text().strip() else ""
        self.count.setText(f"{len(items)} device{'s' if len(items) != 1 else ''} found{q}")
        self.empty.setVisible(not items)
        self.grid.setVisible(bool(items))
        self.grid.set_cards(make_cards(self.state, items))
