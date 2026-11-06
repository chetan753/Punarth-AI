"""Shared helpers for marketplace pages."""
from __future__ import annotations

from PySide6.QtWidgets import QVBoxLayout, QWidget

from core import marketplace

from ..widgets import ProductCard, page_container


def make_cards(state, listings: list[dict], compact: bool = False) -> list[ProductCard]:
    wished = marketplace.wishlist_ids(state.uid)
    cards = []
    for l in listings:
        c = ProductCard(l, l["id"] in wished, compact)
        c.open_requested.connect(lambda lid: state.go("product", id=lid))
        c.wishlist_toggled.connect(lambda lid, c=c: toggle_wish(state, lid, c))
        cards.append(c)
    return cards


def toggle_wish(state, listing_id: int, card_widget=None):
    added = marketplace.toggle_wishlist(state.uid, listing_id)
    if card_widget is not None:
        card_widget.set_wished(added, animate=True)
    state.wishlist_changed.emit()
    state.toast("Added to wishlist ♥" if added else "Removed from wishlist", "success" if added else "info")
    return added


def add_to_cart(state, listing_id: int, qty: int = 1) -> bool:
    try:
        marketplace.add_to_cart(state.uid, listing_id, qty)
    except marketplace.MarketError as e:
        state.toast(str(e), "error")
        return False
    state.cart_changed.emit()
    state.toast("Added to cart 🛒", "success")
    return True


class ScrollPage(QWidget):
    """Base for pages that rebuild a scrollable body on every visit."""

    def __init__(self, state):
        super().__init__()
        self.state = state
        sa, self.body = page_container()
        outer = QVBoxLayout(self)
        outer.setContentsMargins(0, 0, 0, 0)
        outer.addWidget(sa)
        self.scroll_area = sa

    def scroll_top(self):
        self.scroll_area.verticalScrollBar().setValue(0)
