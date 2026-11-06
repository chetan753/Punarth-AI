"""Sell Your Device (AI or manual) and Create / Edit Listing with AI-assisted
fields, provenance badges, safety checks and preview before publishing."""
from __future__ import annotations

from PySide6.QtCore import QSize, Qt
from PySide6.QtGui import QIcon
from PySide6.QtWidgets import (QCheckBox, QComboBox, QFileDialog, QFormLayout, QHBoxLayout, QLabel, QLineEdit,
                               QListView, QListWidget, QListWidgetItem, QMessageBox, QPlainTextEdit, QRadioButton,
                               QSpinBox, QWidget)

from core import auth, catalog, listing_ai, marketplace

from .. import theme
from ..widgets import badge, button, card, clear_layout, label, rounded_pixmap, rupees
from .common import ScrollPage
from .dialogs import ListingPreviewDialog


class SellPage(ScrollPage):
    def on_show(self, **_):
        clear_layout(self.body)
        self.body.addWidget(label("Sell Your Device", "h1"))
        self.body.addWidget(label("Give your device a second life and earn from it. Choose how you'd like to create "
                                  "your listing.", "muted"))
        row = QHBoxLayout()
        row.setSpacing(18)
        a, al = card("true", (26, 24, 26, 24), 10, shadow=True)
        a.setStyleSheet(f"QFrame[card='true'] {{ border:2px solid {theme.GREEN}; }}")
        al.addWidget(badge("RECOMMENDED · OPTION A", "white", theme.GREEN))
        al.addWidget(label("📷  Sell through AI Scanner", "h2"))
        for i, s in enumerate(["Place the device in front of your camera", "AI detects the device, category and brand",
                               "AI checks visible defects", "Answer a few functionality questions",
                               "Get estimated resale value + suggested price", "AI fills in your listing — you review & publish"], 1):
            al.addWidget(label(f"<b style='color:{theme.GREEN}'>{i}.</b>  {s}"))
        al.addStretch()
        al.addWidget(button("Start AI Scanner", "primary", lambda: self.state.go("scanner")))
        row.addWidget(a, 1)
        b, bl = card("true", (26, 24, 26, 24), 10, shadow=True)
        bl.addWidget(badge("OPTION B", theme.INK, "#eef2ef"))
        bl.addWidget(label("✍️  Create listing manually", "h2"))
        bl.addWidget(label("Already know your device's details? Enter product name, category, brand, model, age, "
                           "condition, functionality, description, price, location and photos yourself.", "muted", wrap=True))
        bl.addWidget(label("You'll preview the listing before it goes live.", "muted"))
        bl.addStretch()
        bl.addWidget(button("Create listing manually", "dark", lambda: self.state.go("create_listing", manual=True)))
        row.addWidget(b, 1)
        w = QWidget()
        w.setLayout(row)
        self.body.addWidget(w)

        info = QHBoxLayout()
        info.setSpacing(18)
        s, sl = card("danger", (20, 16, 20, 16), 6)
        sl.addWidget(label("⚠️  Not allowed for resale", "h3"))
        sl.addWidget(label("Devices with swollen batteries, burn marks, leaks, exposed wiring or that overheat are "
                           "hazardous and can't be listed. Book a free authorised e-waste collection instead.", wrap=True))
        sl.addWidget(button("Book e-waste collection", "danger", lambda: self.state.go("recovery")))
        info.addWidget(s, 1)
        plan = catalog.SELLER_PLANS.get(self.state.user.get("seller_plan") or "free")
        p, pl = card("soft", (20, 16, 20, 16), 6)
        pl.addWidget(label(f"Your plan: {plan['name']}", "h3"))
        for perk in plan["perks"]:
            pl.addWidget(label(f"✓ {perk}"))
        pl.addWidget(button("See plans & featured listings", "link", lambda: self.state.go("seller_dashboard", tab="plans")))
        info.addWidget(p, 1)
        iw = QWidget()
        iw.setLayout(info)
        self.body.addWidget(iw)
        self.body.addStretch()


class CreateListingPage(ScrollPage):
    def on_show(self, from_ai=False, manual=False, edit_id=None, **_):
        self.edit_id = edit_id
        self.draft = self.state.listing_draft if from_ai else None
        if from_ai and not self.draft:
            from_ai = False
        self.mode = "edit" if edit_id else ("ai" if from_ai else "manual")
        self.ai_values = (self.draft or {}).get("values", {})
        self.provenance = dict((self.draft or {}).get("provenance", {}))
        self.badges: dict[str, QLabel] = {}
        self.images: list[str] = []
        self._build()
        self.scroll_top()

    # ------------------------------------------------------------------ build
    def _build(self):
        clear_layout(self.body)
        b = self.body
        existing = marketplace.get_listing(self.edit_id) if self.edit_id else None
        if existing and existing["seller_id"] != self.state.uid:
            b.addWidget(label("You can only edit your own listings.", "h2"))
            return
        title = {"edit": "Edit listing", "ai": "Create listing — AI assisted", "manual": "Create listing"}[self.mode]
        b.addWidget(button("←  Back", "link", self.state.back), 0, Qt.AlignmentFlag.AlignLeft)
        b.addWidget(label(title, "h1"))

        if self.mode == "ai":
            s = self.ai_values.get("ai_summary", {})
            ai, al = card("ai", (20, 16, 20, 16), 6)
            al.addWidget(label("🤖  Filled in from your AI device assessment", "h3"))
            v = s.get("value", {})
            al.addWidget(label(f"Classification <b>{s.get('classification')}</b> · Grade <b>{s.get('grade')}</b> · "
                               f"Estimated value <b>{rupees(v.get('low', 0))} – {rupees(v.get('high', 0))}</b> · "
                               f"Suggested price <b>{rupees(v.get('suggested', 0))}</b> · Recommended category "
                               f"<b>{self.ai_values.get('recommended_category')}</b>", wrap=True))
            al.addWidget(label("Purple badges mark AI-generated values. Edit anything — edited fields become "
                               "“Seller provided”. Buyers see which information came from AI.", "small", wrap=True))
            b.addWidget(ai)

        form_card, fl = card("true", (24, 20, 24, 20), 12)
        form = QFormLayout()
        form.setLabelAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
        form.setHorizontalSpacing(18)
        form.setVerticalSpacing(12)

        self.title = QLineEdit()
        self.cat = QComboBox()
        self.cat.addItems(catalog.CATEGORIES)
        self.brand = QComboBox()
        self.brand.setEditable(True)
        self.model = QLineEdit()
        self.age = QSpinBox()
        self.age.setRange(0, 400)
        self.age.setSuffix(" months")
        self.cond = QComboBox()
        self.cond.addItems(catalog.CONDITIONS)
        self.cond_help = label("", "small", wrap=True)
        self.func = QComboBox()
        self.src_reported = QRadioButton("I've used it / reported")
        self.src_tested = QRadioButton("I tested it with the checklist")
        self.desc = QPlainTextEdit()
        self.desc.setMinimumHeight(140)
        self.defects = QPlainTextEdit()
        self.defects.setPlaceholderText("One defect per line, e.g. 'Light scratch on back'")
        self.defects.setMaximumHeight(90)
        self.specs = QPlainTextEdit()
        self.specs.setPlaceholderText("Key: value per line, e.g.\nStorage: 128 GB\nRAM: 8 GB")
        self.specs.setMaximumHeight(90)
        self.price = QSpinBox()
        self.price.setRange(0, 10_000_000)
        self.price.setPrefix("₹ ")
        self.price.setSingleStep(100)
        self.qty = QSpinBox()
        self.qty.setRange(1, 10_000)
        self.location = QComboBox()
        self.location.setEditable(True)
        self.location.addItems(catalog.CITIES)
        self.deliv = QCheckBox("Delivery")
        self.pickup = QCheckBox("Pickup")
        self.for_repair = QCheckBox("Mark as “For Repair” (sold for repair or parts)")

        def refresh_brands():
            cur = self.brand.currentText()
            self.brand.clear()
            self.brand.addItems(catalog.BRANDS.get(self.cat.currentText(), ["Other"]))
            self.brand.setCurrentText(cur)
        self.cat.currentTextChanged.connect(lambda _: refresh_brands())
        refresh_brands()
        self.cond.currentTextChanged.connect(lambda c: self.cond_help.setText(catalog.CONDITION_DESCRIPTIONS.get(c, "")))

        def frow(text, widget, key=None):
            box = QWidget()
            h = QHBoxLayout(box)
            h.setContentsMargins(0, 0, 0, 0)
            h.addWidget(widget, 1)
            if key and self.mode == "ai" and key in self.provenance:
                bd = QLabel()
                self.badges[key] = bd
                h.addWidget(bd)
            form.addRow(label(text, "muted"), box)

        frow("Product name", self.title, "title")
        frow("Category", self.cat, "category")
        frow("Brand", self.brand, "brand")
        frow("Model", self.model, "model")
        frow("Age", self.age)
        frow("Condition", self.cond, "condition")
        form.addRow(QLabel(""), self.cond_help)
        frow("Functionality", self.func, "functionality_status")
        src = QWidget()
        sh = QHBoxLayout(src)
        sh.setContentsMargins(0, 0, 0, 0)
        sh.addWidget(self.src_reported)
        sh.addWidget(self.src_tested)
        sh.addStretch()
        form.addRow(label("Functionality based on", "muted"), src)
        frow("Description", self.desc, "description")
        frow("Known defects", self.defects, "defects")
        frow("Specifications", self.specs)
        price_box = QWidget()
        ph = QHBoxLayout(price_box)
        ph.setContentsMargins(0, 0, 0, 0)
        ph.addWidget(self.price, 1)
        sugg = self.ai_values.get("suggested_price") or 0
        if sugg:
            ph.addWidget(label(f"Suggested {rupees(sugg)} (range {rupees(self.ai_values.get('est_low'))}–"
                               f"{rupees(self.ai_values.get('est_high'))})", "small"))
            ph.addWidget(button("Use", "link", lambda: self.price.setValue(int(sugg))))
        if self.mode == "ai":
            bd = QLabel()
            self.badges["price"] = bd
            ph.addWidget(bd)
        form.addRow(label("Price", "muted"), price_box)
        frow("Quantity", self.qty)
        frow("Location", self.location)
        dv = QWidget()
        dh = QHBoxLayout(dv)
        dh.setContentsMargins(0, 0, 0, 0)
        dh.addWidget(self.deliv)
        dh.addWidget(self.pickup)
        dh.addStretch()
        form.addRow(label("Delivery options", "muted"), dv)
        form.addRow(QLabel(""), self.for_repair)
        fl.addLayout(form)
        b.addWidget(form_card)

        # Images
        ic, il = card("true", (24, 18, 24, 18), 10)
        hr = QHBoxLayout()
        hr.addWidget(label("Product images", "h3"))
        hr.addWidget(label("First image is the cover. Add clear photos of all sides and any defects.", "small"))
        hr.addStretch()
        hr.addWidget(button("+ Add photos", "soft", self._add_images))
        hr.addWidget(button("Remove selected", None, self._remove_image))
        hr.addWidget(button("Make cover", None, self._make_cover))
        il.addLayout(hr)
        self.img_list = QListWidget()
        self.img_list.setViewMode(QListView.ViewMode.IconMode)
        self.img_list.setIconSize(QSize(150, 112))
        self.img_list.setFixedHeight(160)
        self.img_list.setMovement(QListView.Movement.Static)
        self.img_list.setSpacing(8)
        il.addWidget(self.img_list)
        b.addWidget(ic)

        # Safety (manual) / confirmation (AI)
        self.safety_checks = {}
        if self.mode == "manual":
            s, sl = card("warn", (22, 16, 22, 16), 6)
            sl.addWidget(label("Safety check (required)", "h3"))
            for key, text in (("battery_swollen", "The battery is swollen, bulging or the case is lifting"),
                              ("burn_smell_leak", "There are burn marks, a burning smell, leaks or exposed wires"),
                              ("gets_hot", "It overheats while charging or in use")):
                cb = QCheckBox(text)
                self.safety_checks[key] = cb
                sl.addWidget(cb)
            self.safety_ok = QCheckBox("I confirm the device has none of the hazards above (leave them unticked).")
            self.safety_ok.setStyleSheet("font-weight:700;")
            sl.addWidget(self.safety_ok)
            b.addWidget(s)
        self.confirm_ai = QCheckBox("I have reviewed the AI-generated information above and confirm it is accurate.")
        if self.mode == "ai":
            self.confirm_ai.setStyleSheet("font-weight:700;")
            b.addWidget(self.confirm_ai)
        b.addWidget(label("Functionality is shown to buyers as seller-reported or seller-tested. Only devices "
                          "checked at a partner inspection are shown as verified.", "small", wrap=True))

        act = QHBoxLayout()
        act.addStretch()
        if self.mode != "edit":
            act.addWidget(button("Save as draft", None, lambda: self._save("draft")))
        act.addWidget(button("👁  Preview", "soft", self._preview))
        act.addWidget(button("Save changes" if self.mode == "edit" else "Publish listing", "primary",
                             lambda: self._save("active")))
        b.addLayout(act)
        b.addStretch()

        self._populate(existing)
        self._orig = self._values()
        for w, sig in ((self.title, self.title.textChanged), (self.cat, self.cat.currentTextChanged),
                       (self.brand, self.brand.currentTextChanged), (self.model, self.model.textChanged),
                       (self.cond, self.cond.currentTextChanged), (self.func, self.func.currentTextChanged),
                       (self.desc, self.desc.textChanged), (self.defects, self.defects.textChanged),
                       (self.price, self.price.valueChanged)):
            sig.connect(self._update_badges)
        self._update_badges()

    def _populate(self, existing):
        u = self.state.user
        func_opts = [f for f in catalog.FUNCTIONALITY_STATUSES if "verified" not in f]
        if existing and existing["functionality_source"] == "verified_inspection":
            func_opts = catalog.FUNCTIONALITY_STATUSES
        self.func.addItems(func_opts)
        if existing:
            v = existing
            self.images = list(existing["images"])
            defects = existing.get("defects") or []
            specs = existing.get("specs") or {}
        elif self.mode == "ai":
            v = self.ai_values
            self.images = [self.draft["image_path"]] if self.draft.get("image_path") else []
            defects = v.get("defects") or []
            specs = {}
        else:
            v = {"location": u.get("city", ""), "condition": "Good", "functionality_status": "Fully working (seller reported)",
                 "delivery_options": "delivery,pickup"}
            defects, specs = [], {}
        self.title.setText(v.get("title", ""))
        self.cat.setCurrentText(v.get("category", catalog.CATEGORIES[0]))
        self.brand.setCurrentText(v.get("brand", ""))
        self.model.setText(v.get("model", ""))
        self.age.setValue(int(v.get("age_months") or 0))
        self.cond.setCurrentText(v.get("condition", "Good"))
        self.cond_help.setText(catalog.CONDITION_DESCRIPTIONS.get(self.cond.currentText(), ""))
        fs = v.get("functionality_status", "")
        if fs and self.func.findText(fs) < 0:
            self.func.addItem(fs)
        self.func.setCurrentText(fs)
        (self.src_tested if v.get("functionality_source") == "seller_tested" else self.src_reported).setChecked(True)
        self.desc.setPlainText(v.get("description", ""))
        self.defects.setPlainText("\n".join(defects))
        self.specs.setPlainText("\n".join(f"{k}: {val}" for k, val in specs.items()))
        self.price.setValue(int(v.get("price") or 0))
        self.qty.setValue(int(v.get("quantity") or 1))
        self.location.setCurrentText(v.get("location") or u.get("city", ""))
        opts = v.get("delivery_options") or "delivery,pickup"
        self.deliv.setChecked("delivery" in opts)
        self.pickup.setChecked("pickup" in opts)
        self.for_repair.setChecked(bool(v.get("for_repair")))
        self._refresh_images()

    # --------------------------------------------------------------- values
    def _values(self) -> dict:
        specs = {}
        for line in self.specs.toPlainText().splitlines():
            if ":" in line:
                k, _, val = line.partition(":")
                if k.strip():
                    specs[k.strip()] = val.strip()
        opts = ",".join(x for x, cb in (("delivery", self.deliv), ("pickup", self.pickup)) if cb.isChecked())
        return {
            "title": self.title.text().strip(), "category": self.cat.currentText(),
            "brand": self.brand.currentText().strip(), "model": self.model.text().strip(),
            "age_months": self.age.value(), "condition": self.cond.currentText(),
            "functionality_status": self.func.currentText(),
            "functionality_source": "seller_tested" if self.src_tested.isChecked() else "user_reported",
            "description": self.desc.toPlainText().strip(),
            "defects": [d.strip() for d in self.defects.toPlainText().splitlines() if d.strip()],
            "specs": specs, "price": self.price.value(), "quantity": self.qty.value(),
            "location": self.location.currentText().strip(), "delivery_options": opts or "pickup",
            "for_repair": 1 if self.for_repair.isChecked() else 0,
        }

    def _update_badges(self, *_):
        if self.mode != "ai":
            return
        cur = self._values()
        for key, bd in self.badges.items():
            ai_v = self.ai_values.get(key)
            same = str(ai_v) == str(cur.get(key))
            if same:
                bd.setText("AI")
                bd.setToolTip("AI-generated — please check")
                bd.setStyleSheet("background:#ede9fe; color:#5b21b6; border-radius:8px; padding:3px 8px; font-weight:800; font-size:11px;")
            else:
                bd.setText("Edited")
                bd.setToolTip("Changed by you")
                bd.setStyleSheet(f"background:{theme.GREEN_100}; color:{theme.GREEN_DARK}; border-radius:8px; padding:3px 8px; font-weight:800; font-size:11px;")

    # --------------------------------------------------------------- images
    def _refresh_images(self):
        self.img_list.clear()
        for i, p in enumerate(self.images):
            it = QListWidgetItem(QIcon(rounded_pixmap(p, 150, 112, 10)), "Cover" if i == 0 else "")
            it.setData(Qt.ItemDataRole.UserRole, p)
            self.img_list.addItem(it)

    def _add_images(self):
        paths, _ = QFileDialog.getOpenFileNames(self, "Choose product photos", "", "Images (*.jpg *.jpeg *.png *.webp)")
        self.images += [p for p in paths if p not in self.images]
        self._refresh_images()

    def _remove_image(self):
        for it in self.img_list.selectedItems():
            p = it.data(Qt.ItemDataRole.UserRole)
            if p in self.images:
                self.images.remove(p)
        self._refresh_images()

    def _make_cover(self):
        sel = self.img_list.selectedItems()
        if sel:
            p = sel[0].data(Qt.ItemDataRole.UserRole)
            self.images.remove(p)
            self.images.insert(0, p)
            self._refresh_images()

    # --------------------------------------------------------------- actions
    def _check(self, status: str) -> bool:
        if self.mode == "manual" and status == "active":
            if any(cb.isChecked() for cb in self.safety_checks.values()):
                QMessageBox.warning(self, "Can't list this device",
                                    "Devices with these hazards can't be sold to consumers. Please book an authorised "
                                    "e-waste collection from the Recovery Center.")
                return False
            if not self.safety_ok.isChecked():
                QMessageBox.information(self, "Safety confirmation", "Please confirm the safety check before publishing.")
                return False
        if self.mode == "ai" and status == "active" and not self.confirm_ai.isChecked():
            QMessageBox.information(self, "Review AI information",
                                    "Please review the AI-generated fields and tick the confirmation box.")
            return False
        if status == "active" and not self.images:
            if QMessageBox.question(self, "No photos", "Listings with photos sell much faster. Publish without photos?") \
                    != QMessageBox.StandardButton.Yes:
                return False
        return True

    def _provenance(self, values) -> dict:
        if self.mode == "ai":
            return listing_ai.resolve_provenance(self.ai_values, values, self.provenance, self.confirm_ai.isChecked())
        if self.mode == "edit":
            old = marketplace.get_listing(self.edit_id).get("provenance") or {}
            return {k: ("user" if k in values and str(values[k]) != str(self._orig.get(k)) else src)
                    for k, src in old.items()}
        return {k: "user" for k in ("title", "description", "category", "brand", "model", "condition",
                                    "functionality_status", "defects", "price")}

    def _preview(self):
        v = self._values()
        dlg = ListingPreviewDialog(v, self.images, self._provenance(v), auth.display_name(self.state.user), self)
        if dlg.exec():
            self._save("active")

    def _save(self, status: str):
        if not self._check(status):
            return
        v = self._values()
        v["provenance"] = self._provenance(v)
        try:
            if self.mode == "edit":
                marketplace.update_listing(self.state.uid, self.edit_id, v, self.images)
                lid = self.edit_id
                self.state.toast("Listing updated.", "success")
            else:
                if self.mode == "ai":
                    v.update({k: self.ai_values.get(k) for k in ("est_low", "est_high", "suggested_price", "original_price")})
                    v["ai_summary"] = self.ai_values.get("ai_summary")
                    v["assessment_id"] = self.draft.get("assessment_id")
                safety = {k: "yes" if cb.isChecked() else "no" for k, cb in self.safety_checks.items()}
                lid = marketplace.create_listing(self.state.uid, v, self.images, safety, status=status)
                self.state.listing_draft = None
                self.state.toast("Saved as draft." if status == "draft" else "🎉 Your listing is live!", "success")
        except marketplace.ListingBlocked as e:
            QMessageBox.warning(self, "Listing blocked for safety", str(e))
            return
        except marketplace.MarketError as e:
            QMessageBox.warning(self, "Please check the listing", str(e))
            return
        self.state.data_changed.emit()
        if status == "active":
            self.state.go("product", id=lid)
        else:
            self.state.go("my_listings")
