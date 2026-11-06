"""Shared application state and signals (signed-in user, navigation, refresh)."""
from __future__ import annotations

from PySide6.QtCore import QObject, Signal


class AppState(QObject):
    user_changed = Signal()
    cart_changed = Signal()
    wishlist_changed = Signal()
    data_changed = Signal()
    navigate_requested = Signal(str, object)
    back_requested = Signal()
    toast_requested = Signal(str, str)

    def __init__(self):
        super().__init__()
        self.user: dict | None = None
        # Listing draft handed from the AI Scanner to Create Listing
        self.listing_draft: dict | None = None
        # Buy Now (single item checkout without the cart)
        self.buy_now: dict | None = None
        self.detector = None  # lazily created vision.Detector

    @property
    def uid(self) -> int:
        return self.user["id"] if self.user else 0

    @property
    def is_industry(self) -> bool:
        return bool(self.user and self.user["account_type"] == "industry")

    def go(self, page: str, **params):
        self.navigate_requested.emit(page, params)

    def back(self):
        self.back_requested.emit()

    def toast(self, text: str, kind: str = "info"):
        self.toast_requested.emit(text, kind)

    def get_detector(self):
        if self.detector is None:
            from core import vision
            self.detector = vision.Detector()
        return self.detector
