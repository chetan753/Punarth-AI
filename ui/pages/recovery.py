"""Recovery Center: repair / refurbishment / recycling / donation requests and
partner directory."""
from __future__ import annotations

from PySide6.QtWidgets import QComboBox, QGridLayout, QHBoxLayout, QVBoxLayout, QWidget

from core import assessment, catalog, marketplace

from .. import theme
from ..widgets import badge, button, card, clear_layout, label, page_container
from .dialogs import RecoveryRequestDialog

TYPE_LABELS = {"repair": "🔧 Repair", "refurbish": "✨ Refurbishment", "recycle_collection": "♻️ Recycling collection",
               "donate": "🎁 Donation", "inspection": "🔍 Inspection"}


class RecoveryPage(QWidget):
    def __init__(self, state):
        super().__init__()
        self.state = state
        sa, self.body = page_container()
        outer = QVBoxLayout(self)
        outer.setContentsMargins(0, 0, 0, 0)
        outer.addWidget(sa)

    def on_show(self, **_):
        clear_layout(self.body)
        head = QHBoxLayout()
        col = QVBoxLayout()
        col.addWidget(label("Recovery Center", "h1"))
        col.addWidget(label("Every device gets the right second life: reuse, repair, refurbish or responsible recycling.",
                            "muted"))
        head.addLayout(col)
        head.addStretch()
        self.cat = QComboBox()
        self.cat.addItems(catalog.CATEGORIES)
        head.addWidget(self.cat)
        for rtype in ("repair", "refurbish", "recycle_collection"):
            head.addWidget(button(TYPE_LABELS[rtype], "soft", lambda _=False, t=rtype: self._new(t)))
        self.body.addLayout(head)

        guide = QGridLayout()
        guide.setSpacing(12)
        for i, cls in enumerate(assessment.CLASSIFICATIONS):
            c, cl = card("true", (14, 12, 14, 12), 4)
            cl.addWidget(badge(cls, "white", assessment.CLASSIFICATION_COLORS[cls]))
            recs = assessment.recommendations(cls)
            cl.addWidget(label(" · ".join(r["title"] for r in recs[:3]), "small", wrap=True))
            guide.addWidget(c, i // 3, i % 3)
        gw = QWidget()
        gw.setLayout(guide)
        self.body.addWidget(gw)

        self.body.addWidget(label("My requests", "h2"))
        reqs = marketplace.recovery_requests(self.state.uid)
        if not reqs:
            self.body.addWidget(label("No requests yet. Scan a device or create a request above.", "muted"))
        for r in reqs:
            c, cl = card("true", (16, 12, 16, 12))
            row = QHBoxLayout()
            row.addWidget(label(f"<b>{TYPE_LABELS.get(r['type'], r['type'])}</b>"))
            dev = " ".join(x for x in (r.get("brand"), r.get("model"), r.get("category")) if x)
            if dev:
                row.addWidget(label(dev, "muted"))
            if r.get("classification"):
                row.addWidget(badge(r["classification"], "white", assessment.CLASSIFICATION_COLORS.get(r["classification"], theme.MUTED)))
            row.addStretch()
            row.addWidget(label(f"{r.get('partner_name') or ''} {('· ' + r['partner_city']) if r.get('partner_city') else ''}", "muted"))
            row.addWidget(badge(r["status"], "#1e40af", "#dbeafe"))
            row.addWidget(label(r["created_at"][:10], "small"))
            cl.addLayout(row)
            det = r.get("details") or {}
            if det.get("when"):
                cl.addWidget(label(f"{det['when']} · {det.get('address', '')}", "small"))
            self.body.addWidget(c)

        self.body.addWidget(label("Partner network", "h2"))
        grid = QGridLayout()
        grid.setSpacing(12)
        allp = marketplace.partners("repair") + marketplace.partners("refurbish") + marketplace.partners("recycler")
        for i, p in enumerate(allp):
            c, cl = card("true", (14, 12, 14, 12), 4)
            top = QHBoxLayout()
            top.addWidget(label(f"<b>{p['name']}</b>"))
            top.addStretch()
            top.addWidget(badge(p["type"].title(), theme.GREEN_DARK, theme.GREEN_100))
            cl.addLayout(top)
            cl.addWidget(label(f"📍 {p['city']} · ★ {p['rating']}" + (" · CPCB authorised" if p["authorized"] else ""), "small"))
            cl.addWidget(label(p["description"], "small", wrap=True))
            grid.addWidget(c, i // 3, i % 3)
        pw = QWidget()
        pw.setLayout(grid)
        self.body.addWidget(pw)
        self.body.addStretch()

    def _new(self, rtype):
        if RecoveryRequestDialog(self.state, rtype, None, self.cat.currentText(), self).exec():
            self.state.toast("Request submitted.", "success")
            self.on_show()
