"""Reusable widgets: cards, badges, product cards with hover animation,
animated wishlist heart, image gallery, responsive grid, toast, workers."""
from __future__ import annotations

from pathlib import Path

from PySide6.QtCore import (QEasingCurve, QPoint, QPropertyAnimation, QRectF, QSize, Qt, QThread, QTimer,
                            QVariantAnimation, Signal)
from PySide6.QtGui import QColor, QCursor, QFont, QIcon, QPainter, QPainterPath, QPixmap
from PySide6.QtWidgets import (QFrame, QGraphicsDropShadowEffect, QGraphicsOpacityEffect, QGridLayout,
                               QHBoxLayout, QLabel, QPushButton, QScrollArea, QSizePolicy, QVBoxLayout, QWidget)

from . import theme

# ---------------------------------------------------------------------------
# helpers
# ---------------------------------------------------------------------------

_pix_cache: dict[tuple, QPixmap] = {}


def rupees(v) -> str:
    try:
        v = int(round(float(v)))
    except (TypeError, ValueError):
        return "₹0"
    s = str(abs(v))
    if len(s) > 3:  # Indian digit grouping 12,34,567
        head, tail = s[:-3], s[-3:]
        parts = []
        while len(head) > 2:
            parts.insert(0, head[-2:])
            head = head[:-2]
        if head:
            parts.insert(0, head)
        s = ",".join(parts) + "," + tail
    return ("-₹" if v < 0 else "₹") + s


def rounded_pixmap(path: str | None, w: int, h: int, radius: int = 14) -> QPixmap:
    key = (path, w, h, radius)
    if key in _pix_cache:
        return _pix_cache[key]
    out = QPixmap(w, h)
    out.fill(Qt.GlobalColor.transparent)
    p = QPainter(out)
    p.setRenderHint(QPainter.RenderHint.Antialiasing)
    p.setRenderHint(QPainter.RenderHint.SmoothPixmapTransform)
    clip = QPainterPath()
    clip.addRoundedRect(QRectF(0, 0, w, h), radius, radius)
    p.setClipPath(clip)
    src = QPixmap(path) if path and Path(path).exists() else QPixmap()
    if src.isNull():
        p.fillRect(0, 0, w, h, QColor(theme.GREEN_50))
        p.setPen(QColor(theme.MUTED))
        f = QFont()
        f.setPointSize(28)
        p.setFont(f)
        p.drawText(QRectF(0, 0, w, h), Qt.AlignmentFlag.AlignCenter, "♻")
    else:
        scaled = src.scaled(w, h, Qt.AspectRatioMode.KeepAspectRatioByExpanding,
                            Qt.TransformationMode.SmoothTransformation)
        p.drawPixmap(int((w - scaled.width()) / 2), int((h - scaled.height()) / 2), scaled)
    p.end()
    _pix_cache[key] = out
    return out


def clear_layout(layout) -> None:
    while layout.count():
        item = layout.takeAt(0)
        w = item.widget()
        if w is not None:
            w.setParent(None)
            w.deleteLater()
        elif item.layout() is not None:
            clear_layout(item.layout())


def label(text: str = "", role: str | None = None, wrap: bool = False, selectable: bool = False) -> QLabel:
    lb = QLabel(text)
    if role:
        lb.setProperty("role", role)
    lb.setWordWrap(wrap)
    if selectable:
        lb.setTextInteractionFlags(Qt.TextInteractionFlag.TextSelectableByMouse)
    return lb


def button(text: str, kind: str | None = None, slot=None, tooltip: str = "") -> QPushButton:
    b = QPushButton(text)
    if kind:
        b.setProperty("kind", kind)
    b.setCursor(QCursor(Qt.CursorShape.PointingHandCursor))
    if slot:
        b.clicked.connect(slot)
    if tooltip:
        b.setToolTip(tooltip)
    return b


def card(kind: str = "true", margins=(18, 16, 18, 16), spacing: int = 10, shadow: bool = False):
    f = QFrame()
    f.setProperty("card", kind)
    lay = QVBoxLayout(f)
    lay.setContentsMargins(*margins)
    lay.setSpacing(spacing)
    if shadow:
        add_shadow(f)
    return f, lay


def add_shadow(widget, blur: int = 24, alpha: int = 28, dy: int = 6):
    eff = QGraphicsDropShadowEffect(widget)
    eff.setBlurRadius(blur)
    eff.setOffset(0, dy)
    eff.setColor(QColor(15, 81, 50, alpha))
    widget.setGraphicsEffect(eff)
    return eff


def badge(text: str, fg: str = theme.GREEN_DARK, bg: str = theme.GREEN_100) -> QLabel:
    lb = QLabel(text)
    lb.setStyleSheet(f"background:{bg}; color:{fg}; border-radius:9px; padding:3px 9px; font-size:12px; font-weight:700;")
    lb.setSizePolicy(QSizePolicy.Policy.Maximum, QSizePolicy.Policy.Fixed)
    return lb


def condition_badge(cond: str) -> QLabel:
    fg, bg = theme.CONDITION_COLORS.get(cond, (theme.INK, "#eef2ef"))
    return badge(cond, fg, bg)


def status_badge(status: str) -> QLabel:
    fg, bg = theme.ORDER_STATUS_COLORS.get(status, (theme.INK, "#eef2ef"))
    return badge(status, fg, bg)


def provenance_badge(src: str) -> QLabel:
    if src == "ai":
        return badge("AI-generated · not yet confirmed", "#5b21b6", "#ede9fe")
    if src == "ai_confirmed":
        return badge("AI-generated · seller confirmed", "#5b21b6", "#f5f3ff")
    return badge("Seller provided", theme.GREEN_DARK, theme.GREEN_100)


def verified_badge(verified: bool, seller_type: str = "") -> QLabel:
    if verified:
        txt = "✔ Verified business" if seller_type == "industry" else "✔ Verified seller"
        return badge(txt, "#065f46", "#d1fae5")
    return badge("Unverified seller", "#64748b", "#f1f5f9")


def hline() -> QFrame:
    f = QFrame()
    f.setFrameShape(QFrame.Shape.HLine)
    f.setStyleSheet(f"color:{theme.BORDER}; background:{theme.BORDER}; max-height:1px;")
    return f


def scroll(widget: QWidget, horizontal: bool = False) -> QScrollArea:
    sa = QScrollArea()
    sa.setWidgetResizable(True)
    sa.setFrameShape(QFrame.Shape.NoFrame)
    if not horizontal:
        sa.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
    sa.setWidget(widget)
    return sa


def page_container(max_width: int | None = None):
    """Scrollable page body. Returns (scroll_area, inner_layout)."""
    inner = QWidget()
    lay = QVBoxLayout(inner)
    lay.setContentsMargins(32, 24, 32, 32)
    lay.setSpacing(18)
    if max_width:
        inner.setMaximumWidth(max_width)
    return scroll(inner), lay


def empty_state(icon: str, title: str, text: str, action_text: str = "", action=None) -> QWidget:
    w, lay = card("soft", (30, 36, 30, 36), 8)
    ic = label(icon)
    ic.setStyleSheet("font-size:44px;")
    ic.setAlignment(Qt.AlignmentFlag.AlignCenter)
    t = label(title, "h3")
    t.setAlignment(Qt.AlignmentFlag.AlignCenter)
    s = label(text, "muted", wrap=True)
    s.setAlignment(Qt.AlignmentFlag.AlignCenter)
    lay.addWidget(ic)
    lay.addWidget(t)
    lay.addWidget(s)
    if action_text and action:
        b = button(action_text, "primary", action)
        row = QHBoxLayout()
        row.addStretch()
        row.addWidget(b)
        row.addStretch()
        lay.addLayout(row)
    return w


class StatTile(QFrame):
    def __init__(self, title: str, value: str, icon: str = "", accent: str = theme.GREEN, sub: str = ""):
        super().__init__()
        self.setProperty("card", "true")
        lay = QVBoxLayout(self)
        lay.setContentsMargins(18, 14, 18, 14)
        lay.setSpacing(4)
        top = QHBoxLayout()
        t = label(title, "muted")
        top.addWidget(t)
        top.addStretch()
        if icon:
            ic = QLabel(icon)
            c = QColor(accent)
            ic.setStyleSheet(f"font-size:18px; background:rgba({c.red()},{c.green()},{c.blue()},0.12); "
                             "border-radius:10px; padding:4px 7px;")
            top.addWidget(ic)
        lay.addLayout(top)
        self.value_label = QLabel(value)
        self.value_label.setStyleSheet(f"font-size:26px; font-weight:800; color:{theme.INK};")
        lay.addWidget(self.value_label)
        if sub:
            lay.addWidget(label(sub, "small"))
        self.setMinimumWidth(170)

    def set_value(self, v: str):
        self.value_label.setText(v)


# ---------------------------------------------------------------------------
# Animated controls
# ---------------------------------------------------------------------------

class HeartButton(QPushButton):
    """Wishlist toggle with a 'pop' animation."""
    toggled_on = Signal(bool)

    def __init__(self, active: bool = False, size: int = 20):
        super().__init__()
        self._active = active
        self._size = size
        self.setCursor(QCursor(Qt.CursorShape.PointingHandCursor))
        self.setFixedSize(40, 40)
        self.setToolTip("Add to wishlist")
        self._anim = QVariantAnimation(self)
        self._anim.setDuration(380)
        self._anim.setKeyValueAt(0, size)
        self._anim.setKeyValueAt(0.45, size + 10)
        self._anim.setKeyValueAt(1, size)
        self._anim.setEasingCurve(QEasingCurve.Type.OutBack)
        self._anim.valueChanged.connect(lambda v: self._paint(int(v)))
        self._paint(size)

    def _paint(self, px: int):
        color = theme.RED if self._active else "#94a3b8"
        self.setText("♥" if self._active else "♡")
        self.setStyleSheet(f"QPushButton {{ background: rgba(255,255,255,0.95); border: 1px solid {theme.BORDER};"
                           f" border-radius: 20px; color: {color}; font-size: {px}px; padding: 0; }}")

    def set_active(self, active: bool, animate: bool = False):
        self._active = active
        if animate:
            self._anim.stop()
            self._anim.start()
        else:
            self._paint(self._size)


class CountBadgeButton(QPushButton):
    """Header button with a bouncing counter (cart)."""

    def __init__(self, text: str):
        super().__init__(text)
        self.setProperty("kind", "icon")
        self.setCursor(QCursor(Qt.CursorShape.PointingHandCursor))
        self._base = text
        self._count = 0
        self.bubble = QLabel(self)
        self.bubble.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.bubble.setStyleSheet(f"background:{theme.RED}; color:white; border-radius:9px; font-size:11px; font-weight:800;")
        self.bubble.hide()
        self._anim = QPropertyAnimation(self.bubble, b"pos", self)
        self._anim.setDuration(450)
        self._anim.setEasingCurve(QEasingCurve.Type.OutBounce)

    def set_count(self, n: int, animate: bool = True):
        changed = n != self._count
        self._count = n
        if n <= 0:
            self.bubble.hide()
            return
        self.bubble.setText(str(n) if n < 100 else "99+")
        self.bubble.resize(max(18, 9 + 7 * len(self.bubble.text())), 18)
        end = QPoint(self.width() - self.bubble.width() - 2, 0)
        self.bubble.show()
        self.bubble.raise_()
        if animate and changed:
            self._anim.stop()
            self._anim.setStartValue(QPoint(end.x(), end.y() - 12))
            self._anim.setEndValue(end)
            self._anim.start()
        else:
            self.bubble.move(end)

    def resizeEvent(self, e):
        super().resizeEvent(e)
        if self._count:
            self.bubble.move(self.width() - self.bubble.width() - 2, 0)


class ClickableFrame(QFrame):
    clicked = Signal()

    def mouseReleaseEvent(self, e):
        if e.button() == Qt.MouseButton.LeftButton and self.rect().contains(e.position().toPoint()):
            self.clicked.emit()
        super().mouseReleaseEvent(e)


class ProductCard(ClickableFrame):
    """Marketplace product card with animated hover elevation."""
    wishlist_toggled = Signal(int)
    open_requested = Signal(int)

    WIDTH = 252

    def __init__(self, listing: dict, wished: bool = False, compact: bool = False):
        super().__init__()
        self.listing = listing
        self.setProperty("card", "true")
        self.setCursor(QCursor(Qt.CursorShape.PointingHandCursor))
        self.setFixedWidth(self.WIDTH)
        self._shadow = add_shadow(self, blur=14, alpha=18, dy=3)
        self._hover = QVariantAnimation(self)
        self._hover.setDuration(180)
        self._hover.valueChanged.connect(self._apply_hover)

        lay = QVBoxLayout(self)
        lay.setContentsMargins(10, 10, 10, 12)
        lay.setSpacing(6)

        img_h = 150 if compact else 176
        self.img = QLabel()
        self.img.setFixedSize(self.WIDTH - 22, img_h)
        self.img.setPixmap(rounded_pixmap(listing.get("cover"), self.WIDTH - 22, img_h, 12))
        lay.addWidget(self.img)

        # overlay badges on image
        self.heart = HeartButton(wished)
        self.heart.setParent(self.img)
        self.heart.move(self.WIDTH - 22 - 46, 6)
        self.heart.show()
        self.heart.clicked.connect(lambda: self.wishlist_toggled.emit(listing["id"]))
        if listing.get("featured_active"):
            fb = badge("★ Featured", "#92400e", "#fef3c7")
            fb.setParent(self.img)
            fb.move(8, 8)
            fb.show()
        if listing.get("for_repair"):
            rb = badge("For Repair", "#991b1b", "#fee2e2")
            rb.setParent(self.img)
            rb.move(8, img_h - 30)
            rb.show()

        title = label(listing["title"], wrap=True)
        title.setStyleSheet("font-weight:700; font-size:14px;")
        title.setMaximumHeight(40)
        lay.addWidget(title)
        bm = " · ".join(x for x in (listing.get("brand"), listing.get("model")) if x)
        lay.addWidget(label(bm or listing["category"], "small"))

        row = QHBoxLayout()
        row.setSpacing(6)
        row.addWidget(condition_badge(listing["condition"]))
        row.addStretch()
        lay.addLayout(row)

        price_row = QHBoxLayout()
        p = label(rupees(listing["price"]), "price")
        price_row.addWidget(p)
        if listing.get("original_price") and listing["original_price"] > listing["price"]:
            off = round(100 * (1 - listing["price"] / listing["original_price"]))
            o = label(f"{off}% below new")
            o.setStyleSheet(f"color:{theme.GREEN_DARK}; font-size:12px; font-weight:700;")
            price_row.addWidget(o)
        price_row.addStretch()
        lay.addLayout(price_row)

        seller = label(f"🏪 {listing.get('seller_display', '')}", "small")
        lay.addWidget(seller)
        meta = QHBoxLayout()
        meta.addWidget(label(f"📍 {listing.get('location', '')}", "small"))
        meta.addStretch()
        v = "✔ Verified" if listing.get("seller_verified") else "Unverified"
        vb = label(v)
        vb.setStyleSheet(f"font-size:11px; font-weight:700; color:{'#047857' if listing.get('seller_verified') else '#94a3b8'};")
        meta.addWidget(vb)
        lay.addLayout(meta)

        view = button("View Product", "soft", lambda: self.open_requested.emit(listing["id"]))
        lay.addWidget(view)
        self.clicked.connect(lambda: self.open_requested.emit(listing["id"]))

    def _apply_hover(self, t):
        if self.graphicsEffect() is not self._shadow:
            return  # card is still fading in
        t = float(t)
        self._shadow.setBlurRadius(14 + 22 * t)
        self._shadow.setOffset(0, 3 + 7 * t)
        self._shadow.setColor(QColor(15, 81, 50, int(18 + 30 * t)))

    def enterEvent(self, e):
        self._hover.stop()
        self._hover.setStartValue(0.0)
        self._hover.setEndValue(1.0)
        self._hover.start()
        self.setStyleSheet(f"QFrame[card='true'] {{ border: 1px solid {theme.GREEN_200}; }}")
        super().enterEvent(e)

    def leaveEvent(self, e):
        self._hover.stop()
        self._hover.setStartValue(1.0)
        self._hover.setEndValue(0.0)
        self._hover.start()
        self.setStyleSheet("")
        super().leaveEvent(e)

    def set_wished(self, wished: bool, animate: bool = True):
        self.heart.set_active(wished, animate)


class ProductGrid(QWidget):
    """Responsive grid that reflows product cards on resize."""

    def __init__(self, spacing: int = 18):
        super().__init__()
        self.grid = QGridLayout(self)
        self.grid.setContentsMargins(0, 0, 0, 0)
        self.grid.setHorizontalSpacing(spacing)
        self.grid.setVerticalSpacing(spacing)
        self.cards: list[QWidget] = []
        self._cols = 0

    def set_cards(self, cards: list[QWidget]):
        for c in self.cards:
            c.setParent(None)
            c.deleteLater()
        self.cards = cards
        self._cols = 0
        self._reflow(force=True)
        for i, c in enumerate(cards):
            fade_in(c, delay=min(i, 12) * 35)

    def _reflow(self, force: bool = False):
        w = max(self.width(), 300)
        cols = max(1, (w + 18) // (ProductCard.WIDTH + 18))
        if cols == self._cols and not force:
            return
        self._cols = cols
        while self.grid.count():
            self.grid.takeAt(0)
        for i, c in enumerate(self.cards):
            self.grid.addWidget(c, i // cols, i % cols, Qt.AlignmentFlag.AlignTop | Qt.AlignmentFlag.AlignLeft)
        for col in range(cols + 1):
            self.grid.setColumnStretch(col, 0)
        self.grid.setColumnStretch(cols, 1)

    def resizeEvent(self, e):
        super().resizeEvent(e)
        self._reflow()


def fade_in(widget: QWidget, duration: int = 260, delay: int = 0):
    eff = QGraphicsOpacityEffect(widget)
    eff.setOpacity(0.0)
    widget.setGraphicsEffect(eff)
    anim = QPropertyAnimation(eff, b"opacity", widget)
    anim.setDuration(duration)
    anim.setStartValue(0.0)
    anim.setEndValue(1.0)
    anim.setEasingCurve(QEasingCurve.Type.OutCubic)

    def done():
        # restore hover shadow for product cards (an effect slot holds one effect)
        if isinstance(widget, ProductCard):
            widget._shadow = add_shadow(widget, blur=14, alpha=18, dy=3)
        else:
            widget.setGraphicsEffect(None)

    anim.finished.connect(done)
    QTimer.singleShot(delay, anim.start)
    widget._fade_anim = anim  # keep reference


class HScroller(QScrollArea):
    """Horizontal carousel of cards."""

    def __init__(self, height: int = 400):
        super().__init__()
        self.setWidgetResizable(True)
        self.setFrameShape(QFrame.Shape.NoFrame)
        self.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self.setFixedHeight(height)
        self.inner = QWidget()
        self.row = QHBoxLayout(self.inner)
        self.row.setContentsMargins(4, 4, 4, 12)
        self.row.setSpacing(18)
        self.setWidget(self.inner)

    def set_widgets(self, widgets: list[QWidget]):
        clear_layout(self.row)
        for w in widgets:
            self.row.addWidget(w)
        self.row.addStretch()

    def wheelEvent(self, e):
        bar = self.horizontalScrollBar()
        bar.setValue(bar.value() - e.angleDelta().y())


class ImageGallery(QWidget):
    """Main image with thumbnail strip and cross-fade."""

    def __init__(self, width: int = 520, height: int = 400):
        super().__init__()
        self.w, self.h = width, height
        self.paths: list[str] = []
        lay = QVBoxLayout(self)
        lay.setContentsMargins(0, 0, 0, 0)
        lay.setSpacing(10)
        self.main = QLabel()
        self.main.setFixedSize(width, height)
        self.main.setStyleSheet(f"background:{theme.GREEN_50}; border-radius:18px;")
        lay.addWidget(self.main)
        nav = QHBoxLayout()
        self.prev = button("‹", None, lambda: self.step(-1))
        self.next = button("›", None, lambda: self.step(1))
        for b in (self.prev, self.next):
            b.setFixedSize(36, 36)
        self.thumbs = QHBoxLayout()
        self.thumbs.setSpacing(8)
        nav.addWidget(self.prev)
        nav.addLayout(self.thumbs)
        nav.addStretch()
        nav.addWidget(self.next)
        lay.addLayout(nav)
        self.index = 0
        self._effect = QGraphicsOpacityEffect(self.main)
        self.main.setGraphicsEffect(self._effect)
        self._anim = QPropertyAnimation(self._effect, b"opacity", self)
        self._anim.setDuration(220)
        self._anim.setStartValue(0.25)
        self._anim.setEndValue(1.0)

    def set_images(self, paths: list[str]):
        self.paths = paths or [None]
        clear_layout(self.thumbs)
        self._thumb_btns = []
        for i, p in enumerate(self.paths):
            b = QPushButton()
            b.setFixedSize(72, 56)
            b.setIcon(QIcon(rounded_pixmap(p, 72, 56, 8)))
            b.setIconSize(QSize(72, 56))
            b.setCursor(QCursor(Qt.CursorShape.PointingHandCursor))
            b.clicked.connect(lambda _=False, i=i: self.show_index(i))
            self.thumbs.addWidget(b)
            self._thumb_btns.append(b)
        self.show_index(0, animate=False)

    def show_index(self, i: int, animate: bool = True):
        if not self.paths:
            return
        self.index = i % len(self.paths)
        self.main.setPixmap(rounded_pixmap(self.paths[self.index], self.w, self.h, 18))
        for j, b in enumerate(self._thumb_btns):
            b.setStyleSheet(f"border: 2px solid {theme.GREEN if j == self.index else 'transparent'}; border-radius:10px; padding:0;")
        if animate:
            self._anim.stop()
            self._anim.start()

    def step(self, d: int):
        self.show_index(self.index + d)


# ---------------------------------------------------------------------------
# Toast notifications
# ---------------------------------------------------------------------------

class Toast(QLabel):
    def __init__(self, parent: QWidget, text: str, kind: str = "info"):
        super().__init__(text, parent)
        self.setObjectName("Toast")
        colors = {"info": theme.INK, "success": theme.GREEN_DARK, "error": theme.RED}
        self.setStyleSheet(f"#Toast {{ background:{colors.get(kind, theme.INK)}; color:white; border-radius:12px;"
                           f" padding:12px 18px; font-weight:600; }}")
        self.setWordWrap(True)
        self.setMaximumWidth(420)
        self.setMinimumWidth(260)
        self.adjustSize()
        eff = QGraphicsOpacityEffect(self)
        self.setGraphicsEffect(eff)
        pr = parent.rect()
        end = QPoint(pr.width() - self.width() - 24, pr.height() - self.height() - 24)
        self.move(end.x(), end.y() + 30)
        self.show()
        self.raise_()
        self._a1 = QPropertyAnimation(self, b"pos", self)
        self._a1.setDuration(260)
        self._a1.setStartValue(QPoint(end.x(), end.y() + 30))
        self._a1.setEndValue(end)
        self._a1.setEasingCurve(QEasingCurve.Type.OutCubic)
        self._o = QPropertyAnimation(eff, b"opacity", self)
        self._o.setDuration(260)
        self._o.setStartValue(0.0)
        self._o.setEndValue(1.0)
        self._a1.start()
        self._o.start()
        QTimer.singleShot(2800, self._fade_out)

    def _fade_out(self):
        self._o.stop()
        self._o.setStartValue(1.0)
        self._o.setEndValue(0.0)
        self._o.finished.connect(self.deleteLater)
        self._o.start()


# ---------------------------------------------------------------------------
# Background work
# ---------------------------------------------------------------------------

class Worker(QThread):
    done = Signal(object)
    failed = Signal(str)

    def __init__(self, fn, *args, **kwargs):
        super().__init__()
        self.fn, self.args, self.kwargs = fn, args, kwargs

    def run(self):
        try:
            self.done.emit(self.fn(*self.args, **self.kwargs))
        except Exception as e:  # surfaced to the UI
            self.failed.emit(str(e))


_workers: set = set()


def run_async(fn, on_done=None, on_fail=None, *args, **kwargs) -> Worker:
    w = Worker(fn, *args, **kwargs)
    if on_done:
        w.done.connect(on_done)
    if on_fail:
        w.failed.connect(on_fail)
    _workers.add(w)
    w.finished.connect(lambda: _workers.discard(w))
    w.start()
    return w


class Section(QWidget):
    """Title + optional action link + content."""

    def __init__(self, title: str, action_text: str = "", action=None, subtitle: str = ""):
        super().__init__()
        self.lay = QVBoxLayout(self)
        self.lay.setContentsMargins(0, 0, 0, 0)
        self.lay.setSpacing(12)
        head = QHBoxLayout()
        col = QVBoxLayout()
        col.setSpacing(2)
        col.addWidget(label(title, "h2"))
        if subtitle:
            col.addWidget(label(subtitle, "muted"))
        head.addLayout(col)
        head.addStretch()
        if action_text and action:
            head.addWidget(button(action_text + "  →", "link", action))
        self.lay.addLayout(head)

    def add(self, w):
        self.lay.addWidget(w)
        return w
