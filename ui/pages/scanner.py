"""AI Scanner: live camera → device identification → device-specific
questions → AI Segregation result with recovery pathways, resale value and a
one-click marketplace listing."""
from __future__ import annotations

import time

import cv2
from PySide6.QtCore import QRectF, Qt, QThread, Signal
from PySide6.QtGui import QColor, QFont, QImage, QPainter, QPen, QPixmap
from PySide6.QtWidgets import (QButtonGroup, QComboBox, QFileDialog, QFrame, QGridLayout, QHBoxLayout, QLabel,
                               QLineEdit, QMessageBox, QSizePolicy, QSpinBox, QStackedWidget, QVBoxLayout, QWidget)

from core import assessment, catalog, config, listing_ai, vision

from .. import theme
from ..widgets import badge, button, card, clear_layout, label, rounded_pixmap, run_async, rupees, scroll
from .dialogs import RecoveryRequestDialog


class CameraThread(QThread):
    frame_ready = Signal(object, object)
    failed = Signal(str)

    def __init__(self, index: int, detector):
        super().__init__()
        self.index = index
        self.detector = detector
        self._running = True

    def run(self):
        cap = cv2.VideoCapture(self.index)
        if not cap.isOpened():
            self.failed.emit(f"Could not open camera #{self.index}. Check that a webcam is connected and not "
                             "used by another app, or upload a photo instead.")
            return
        n, dets = 0, []
        while self._running:
            ok, frame = cap.read()
            if not ok:
                self.msleep(30)
                continue
            if self.detector is not None and self.detector.available and n % 5 == 0:
                try:
                    dets = self.detector.detect(frame)
                except Exception:
                    dets = []
            n += 1
            self.frame_ready.emit(frame, dets)
            self.msleep(15)
        cap.release()

    def stop(self):
        self._running = False
        self.wait(2000)


def frame_to_pixmap(frame, dets, w: int, h: int) -> QPixmap:
    rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
    fh, fw = rgb.shape[:2]
    img = QImage(rgb.data, fw, fh, 3 * fw, QImage.Format.Format_RGB888).copy()
    pm = QPixmap.fromImage(img)
    if dets:
        p = QPainter(pm)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)
        for i, d in enumerate(dets[:4]):
            x, y, bw, bh = d["box"]
            color = QColor(theme.SCAN_ACCENT if i == 0 else "#a7f3d0")
            p.setPen(QPen(color, 4 if i == 0 else 2))
            p.drawRoundedRect(QRectF(x, y, bw, bh), 12, 12)
            txt = f"{d['label']}  {int(d['confidence'] * 100)}%"
            f = QFont()
            f.setPointSize(max(12, fw // 60))
            f.setBold(True)
            p.setFont(f)
            tw = p.fontMetrics().horizontalAdvance(txt) + 16
            th = p.fontMetrics().height() + 8
            p.fillRect(QRectF(x, max(0, y - th), tw, th), color)
            p.setPen(QColor("#04120c"))
            p.drawText(QRectF(x + 8, max(0, y - th), tw, th), Qt.AlignmentFlag.AlignVCenter, txt)
        p.end()
    return pm.scaled(w, h, Qt.AspectRatioMode.KeepAspectRatio, Qt.TransformationMode.SmoothTransformation)


class AnswerRow(QWidget):
    """One assessment question with the right input control."""

    def __init__(self, q: dict, default=None):
        super().__init__()
        self.q = q
        lay = QVBoxLayout(self)
        lay.setContentsMargins(0, 6, 0, 6)
        lay.setSpacing(6)
        text = q["text"]
        if q.get("hazard"):
            text = "⚠️  " + text
        t = label(text, wrap=True)
        t.setStyleSheet("font-weight:600; font-size:14px;" + ("color:#fca5a5;" if q.get("hazard") else ""))
        lay.addWidget(t)
        row = QHBoxLayout()
        row.setSpacing(8)
        if q["kind"] == "yesno":
            self.group = QButtonGroup(self)
            self.btns = {}
            for key, txt in (("yes", "Yes"), ("no", "No"), ("unsure", "Not sure")):
                b = button(txt, "chip")
                b.setCheckable(True)
                self.group.addButton(b)
                self.btns[key] = b
                row.addWidget(b)
            self.btns[default if default in self.btns else "unsure"].setChecked(True)
        elif q["kind"] == "choice":
            self.combo = QComboBox()
            self.combo.addItems(q["options"])
            if default in q["options"]:
                self.combo.setCurrentText(default)
            row.addWidget(self.combo, 1)
        else:
            self.spin = QSpinBox()
            self.spin.setRange(0, 10_000_000 if "price" in q["key"] else 400)
            self.spin.setSingleStep(1000 if "price" in q["key"] else 1)
            if "price" in q["key"]:
                self.spin.setPrefix("₹ ")
            else:
                self.spin.setSuffix(" months")
            self.spin.setValue(int(default or (12 if q["key"] == "age_months" else 0)))
            self.spin.setMinimumWidth(180)
            row.addWidget(self.spin)
        row.addStretch()
        lay.addLayout(row)

    def value(self):
        if self.q["kind"] == "yesno":
            for k, b in self.btns.items():
                if b.isChecked():
                    return k
            return "unsure"
        if self.q["kind"] == "choice":
            return self.combo.currentText()
        return self.spin.value()


class ScannerPage(QWidget):
    def __init__(self, state):
        super().__init__()
        self.state = state
        self.setObjectName("ScannerRoot")
        self.setAttribute(Qt.WidgetAttribute.WA_StyledBackground, True)
        self.cam: CameraThread | None = None
        self.last_frame = None
        self.last_dets = []
        self.captured = None
        self.findings: dict = {}
        self.result: dict | None = None
        self.answers: dict = {}
        self.assessment_id: int | None = None
        self.image_path = ""

        root = QVBoxLayout(self)
        root.setContentsMargins(28, 20, 28, 20)
        root.setSpacing(14)
        head = QHBoxLayout()
        title = label("AI Scanner", "h1")
        title.setStyleSheet("font-size:28px; font-weight:800; color:white;")
        head.addWidget(title)
        head.addWidget(badge("LIVE AI", "#04120c", theme.SCAN_ACCENT))
        head.addStretch()
        self.steps = []
        for i, s in enumerate(["1 Capture", "2 Identify", "3 Questions", "4 Recovery decision"]):
            lb = QLabel(s)
            self.steps.append(lb)
            head.addWidget(lb)
        root.addLayout(head)
        self.stack = QStackedWidget()
        root.addWidget(self.stack, 1)
        self.stack.addWidget(self._build_capture())
        self.identify_page = QWidget()
        self.stack.addWidget(self.identify_page)
        self.questions_page = QWidget()
        self.stack.addWidget(self.questions_page)
        self.result_page = QWidget()
        self.stack.addWidget(self.result_page)
        self._set_step(0)

    # ------------------------------------------------------------------ steps
    def _set_step(self, i: int):
        self.stack.setCurrentIndex(i)
        for j, lb in enumerate(self.steps):
            on = j == i
            done = j < i
            lb.setStyleSheet(f"padding:6px 12px; border-radius:14px; font-weight:700; font-size:12px;"
                             f"background:{theme.SCAN_ACCENT if on else ('#1f3a31' if done else 'transparent')};"
                             f"color:{'#04120c' if on else ('#a7f3d0' if done else '#5f8577')};")

    def on_show(self, **params):
        if self.stack.currentIndex() == 0:
            self.start_camera()

    def on_hide(self):
        self.stop_camera()

    # ------------------------------------------------------------- capture UI
    def _build_capture(self):
        w = QWidget()
        lay = QHBoxLayout(w)
        lay.setContentsMargins(0, 0, 0, 0)
        lay.setSpacing(18)
        left, ll = card("true", (14, 14, 14, 14))
        self.view = QLabel("Starting camera…")
        self.view.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.view.setMinimumSize(640, 440)
        self.view.setSizePolicy(QSizePolicy.Policy.Ignored, QSizePolicy.Policy.Ignored)
        self.view.setStyleSheet("background:#050b09; border-radius:14px; color:#5f8577; font-size:16px;")
        ll.addWidget(self.view, 1)
        tips = label("Place the device in the centre, well lit, against a plain background. Show the screen or the "
                     "side with visible damage.", "muted", wrap=True)
        ll.addWidget(tips)
        lay.addWidget(left, 3)

        right, rl = card("true", (18, 18, 18, 18), 12)
        right.setMinimumWidth(330)
        rl.addWidget(label("Live detection", "h3"))
        self.det_label = label("Waiting for frames…", "muted", wrap=True)
        rl.addWidget(self.det_label)
        det = self.state.get_detector()
        mode = ("Offline detector: ready" if det.available else "Offline detector: not installed")
        cloud = "Cloud vision: on (brand/model)" if config.ANTHROPIC_API_KEY else "Cloud vision: off"
        self.mode_label = label(f"• {mode}\n• {cloud}", "small", wrap=True)
        rl.addWidget(self.mode_label)
        if not det.available:
            rl.addWidget(label("Tip: run  python tools/get_model.py  once to enable offline device detection. "
                               "You can still capture and pick the category yourself.", "small", wrap=True))
        cam_row = QHBoxLayout()
        cam_row.addWidget(label("Camera", "muted"))
        self.cam_index = QSpinBox()
        self.cam_index.setRange(0, 8)
        self.cam_index.setValue(config.CAMERA_INDEX)
        cam_row.addWidget(self.cam_index)
        cam_row.addWidget(button("Restart", None, lambda: (self.stop_camera(), self.start_camera())))
        rl.addLayout(cam_row)
        rl.addStretch()
        self.capture_btn = button("📸  Capture & analyse", "primary", self.capture)
        self.capture_btn.setMinimumHeight(48)
        rl.addWidget(self.capture_btn)
        rl.addWidget(button("🖼️  Upload a photo instead", None, self.upload))
        rl.addWidget(button("✍️  Skip — enter device details manually", None, self.skip_manual))
        self.busy = label("", "small")
        rl.addWidget(self.busy)
        lay.addWidget(right, 2)
        return w

    def start_camera(self):
        if self.cam is not None:
            return
        self.cam = CameraThread(self.cam_index.value(), self.state.get_detector())
        self.cam.frame_ready.connect(self._on_frame)
        self.cam.failed.connect(self._on_cam_fail)
        self.cam.start()

    def stop_camera(self):
        if self.cam is not None:
            self.cam.stop()
            self.cam = None

    def _on_cam_fail(self, msg):
        self.view.setText(f"📷\n\n{msg}")
        self.cam = None

    def _on_frame(self, frame, dets):
        self.last_frame, self.last_dets = frame, dets
        self.view.setPixmap(frame_to_pixmap(frame, dets, self.view.width(), self.view.height()))
        if dets:
            d = dets[0]
            self.det_label.setText(f"<b style='color:#34d399;font-size:16px'>{d['label']}</b><br>"
                                   f"Category: {d['category']} · {int(d['confidence'] * 100)}% confidence")
        elif self.state.get_detector().available:
            self.det_label.setText("No electronic device detected yet — move it into view.")
        else:
            self.det_label.setText("Camera live. Capture when the device is in view.")

    def capture(self):
        if self.last_frame is None:
            QMessageBox.information(self, "No image", "The camera has no frame yet. Upload a photo instead.")
            return
        self._analyse(self.last_frame.copy())

    def upload(self):
        path, _ = QFileDialog.getOpenFileName(self, "Choose a photo of the device", "", "Images (*.jpg *.jpeg *.png *.webp *.bmp)")
        if not path:
            return
        frame = cv2.imread(path)
        if frame is None:
            QMessageBox.warning(self, "Unreadable image", "Could not read that image file.")
            return
        self._analyse(frame)

    def skip_manual(self):
        self.stop_camera()
        self.captured = None
        self.image_path = ""
        self.findings = {"notes": ["No image analysed — details entered manually."], "defects": [], "sources": []}
        self._build_identify()
        self._set_step(1)

    def _analyse(self, frame):
        self.stop_camera()
        self.captured = frame
        self.image_path = str(config.IMAGE_DIR / f"scan_{self.state.uid}_{int(time.time())}.jpg")
        cv2.imwrite(self.image_path, frame)
        self.capture_btn.setEnabled(False)
        self.busy.setText("Analysing image… (detector + defect check" + (" + cloud vision" if config.ANTHROPIC_API_KEY else "") + ")")
        run_async(vision.analyze_capture, self._analysed, self._analyse_failed, frame, self.state.get_detector())

    def _analyse_failed(self, msg):
        self.capture_btn.setEnabled(True)
        self.busy.setText("")
        QMessageBox.warning(self, "Analysis failed", msg)
        self.start_camera()

    def _analysed(self, findings):
        self.capture_btn.setEnabled(True)
        self.busy.setText("")
        self.findings = findings
        self._build_identify()
        self._set_step(1)

    # ------------------------------------------------------------- identify
    def _build_identify(self):
        clear_layout(self.identify_page.layout() or QVBoxLayout(self.identify_page))
        lay = self.identify_page.layout()
        lay.setContentsMargins(0, 0, 0, 0)
        row = QHBoxLayout()
        row.setSpacing(18)
        f = self.findings
        # left: image + AI findings
        left, ll = card("true", (16, 16, 16, 16))
        if self.captured is not None:
            img = QLabel()
            img.setPixmap(frame_to_pixmap(self.captured, f.get("detections", [])[:1], 520, 360))
            img.setAlignment(Qt.AlignmentFlag.AlignCenter)
            ll.addWidget(img)
        ai, al = card("ai", (14, 12, 14, 12), 6)
        al.addWidget(label("🤖  AI findings (estimates — please confirm)", "h3"))
        if f.get("detector_label"):
            al.addWidget(label(f"Detected: <b>{f['detector_label']}</b> ({int(f.get('detector_confidence', 0) * 100)}%)"))
        if f.get("brand") or f.get("model"):
            al.addWidget(label(f"Recognised: <b>{f.get('brand', '')} {f.get('model', '')}</b> (cloud vision)"))
        for d in f.get("defects", []):
            al.addWidget(label(f"• {d['label']} — {int(d.get('confidence', 0) * 100)}% (visible in image)"))
        if not f.get("defects") and self.captured is not None:
            al.addWidget(label("• No obvious visible defects found in this photo."))
        for h in f.get("hazard_signs", []):
            al.addWidget(label(f"⚠️ Possible hazard sign: {h}"))
        q = f.get("quality") or {}
        for t in q.get("tips", []):
            al.addWidget(label(f"📷 {t}", "small", wrap=True))
        for n in f.get("notes", []):
            al.addWidget(label(f"ℹ️ {n}", "small", wrap=True))
        al.addWidget(label("Images cannot show whether a device works. Functionality comes from your answers next.",
                           "small", wrap=True))
        ll.addWidget(ai)
        ll.addStretch()
        row.addWidget(left, 3)

        right, rl = card("true", (20, 18, 20, 18), 10)
        rl.addWidget(label("Confirm the device", "h2"))
        rl.addWidget(label("Fields marked AI were suggested by the scanner. Correct anything that's wrong.", "muted", wrap=True))
        self.cat_combo = QComboBox()
        self.cat_combo.addItems(catalog.CATEGORIES)
        if f.get("category"):
            self.cat_combo.setCurrentText(f["category"])
        self.brand_combo = QComboBox()
        self.brand_combo.setEditable(True)
        self.model_edit = QLineEdit()
        self.model_edit.setPlaceholderText("Model (e.g. Galaxy S21, ThinkPad T480)")
        self.model_edit.setText(f.get("model", ""))

        def refresh_brands():
            cur = self.brand_combo.currentText()
            self.brand_combo.clear()
            self.brand_combo.addItems([""] + catalog.BRANDS.get(self.cat_combo.currentText(), ["Other"]))
            self.brand_combo.setCurrentText(cur or f.get("brand", ""))
        self.cat_combo.currentTextChanged.connect(lambda _: refresh_brands())
        refresh_brands()
        self.brand_combo.setCurrentText(f.get("brand", ""))

        def field(name, widget, ai_flag):
            h = QHBoxLayout()
            h.addWidget(label(name, "muted"))
            if ai_flag:
                h.addWidget(badge("AI", "#ddd6fe", "#3b3570"))
            h.addStretch()
            rl.addLayout(h)
            rl.addWidget(widget)
        field("Category", self.cat_combo, bool(f.get("category")))
        field("Brand", self.brand_combo, bool(f.get("brand")))
        field("Model", self.model_edit, bool(f.get("model")))
        rl.addStretch()
        nav = QHBoxLayout()
        nav.addWidget(button("← Rescan", None, self.rescan))
        nav.addStretch()
        nav.addWidget(button("Next: questions →", "primary", self._to_questions))
        rl.addLayout(nav)
        row.addWidget(right, 2)
        lay.addLayout(row)

    # ------------------------------------------------------------- questions
    def _to_questions(self):
        cat = self.cat_combo.currentText()
        self.device = {"category": cat, "brand": self.brand_combo.currentText().strip(),
                       "model": self.model_edit.text().strip()}
        inner = QWidget()
        lay = QVBoxLayout(inner)
        lay.setContentsMargins(4, 4, 4, 4)
        lay.setSpacing(6)
        lay.addWidget(label(f"A few questions about your {cat.lower().rstrip('s')}", "h2"))
        lay.addWidget(label("Honest answers give an accurate recovery decision and price. Buyers see that "
                            "functionality is seller-reported.", "muted", wrap=True))
        if self.findings.get("hazard_signs"):
            w, wl = card("danger", (14, 10, 14, 10))
            wl.addWidget(label("⚠️ The image check noticed possible hazard signs: " +
                               ", ".join(self.findings["hazard_signs"]) + ". Please answer the safety questions carefully.",
                               wrap=True))
            lay.addWidget(w)
        self.rows = []
        grid = QGridLayout()
        grid.setHorizontalSpacing(30)
        for i, q in enumerate(catalog.questions_for(cat)):
            default = self.answers.get(q["key"]) if self.answers.get("_category") == cat else None
            r = AnswerRow(q, default)
            self.rows.append(r)
            box, bl = card("true", (14, 8, 14, 8))
            bl.addWidget(r)
            grid.addWidget(box, i // 2, i % 2)
        lay.addLayout(grid)
        lay.addStretch()
        clear_layout(self.questions_page.layout() or QVBoxLayout(self.questions_page))
        pl = self.questions_page.layout()
        pl.setContentsMargins(0, 0, 0, 0)
        pl.addWidget(scroll(inner), 1)
        nav = QHBoxLayout()
        nav.addWidget(button("← Back", None, lambda: self._set_step(1)))
        nav.addStretch()
        nav.addWidget(button("🧠  Run AI assessment", "primary", self._assess))
        pl.addLayout(nav)
        self._set_step(2)

    # ------------------------------------------------------------- result
    def _assess(self):
        self.answers = {r.q["key"]: r.value() for r in self.rows}
        self.answers["_category"] = self.device["category"]
        ans = {k: v for k, v in self.answers.items() if not k.startswith("_")}
        self.result = assessment.assess(self.device["category"], ans, self.device["brand"], self.device["model"],
                                        self.findings)
        det_info = {k: self.findings.get(k) for k in ("detector_label", "detector_confidence", "brand", "model",
                                                     "defects", "hazard_signs", "sources")}
        self.assessment_id = assessment.save_assessment(self.state.uid, self.result, ans, det_info, self.image_path)
        self._build_result()
        self._set_step(3)
        self.state.data_changed.emit()

    def _build_result(self):
        r = self.result
        inner = QWidget()
        lay = QVBoxLayout(inner)
        lay.setContentsMargins(4, 4, 4, 4)
        lay.setSpacing(14)
        color = assessment.CLASSIFICATION_COLORS[r["classification"]]
        banner = QFrame()
        banner.setStyleSheet(f"QFrame {{ background: qlineargradient(x1:0,y1:0,x2:1,y2:0, stop:0 {color}, stop:1 #0b1512);"
                             f" border-radius:18px; }} QLabel {{ color:white; background:transparent; }}")
        bl = QHBoxLayout(banner)
        bl.setContentsMargins(24, 20, 24, 20)
        col = QVBoxLayout()
        col.addWidget(label("AI SEGREGATION RESULT", "small"))
        big = label(r["classification"])
        big.setStyleSheet("font-size:34px; font-weight:800; color:white;")
        col.addWidget(big)
        dev = " ".join(x for x in (r["brand"], r["model"]) if x) or r["category"]
        col.addWidget(label(f"{dev} · {r['category']} · confidence {int(r['confidence'] * 100)}%"))
        bl.addLayout(col, 1)
        if self.image_path:
            pic = QLabel()
            pic.setPixmap(rounded_pixmap(self.image_path, 180, 130, 14))
            bl.addWidget(pic)
        lay.addWidget(banner)

        row = QHBoxLayout()
        row.setSpacing(14)
        # Why
        why, wl = card("true", (18, 16, 18, 16), 6)
        wl.addWidget(label("Why this decision", "h3"))
        for x in r["reasons"]:
            wl.addWidget(label(f"• {x}", wrap=True))
        for x in r["warnings"]:
            wl.addWidget(label(f"⚠️ {x}", wrap=True))
        wl.addStretch()
        row.addWidget(why, 3)
        # Condition
        cond, cl = card("true", (18, 16, 18, 16), 6)
        cl.addWidget(label("Condition grade", "h3"))
        g = label(r["grade"])
        g.setStyleSheet("font-size:22px; font-weight:800; color:#34d399;")
        cl.addWidget(g)
        cl.addWidget(label(catalog.CONDITION_DESCRIPTIONS[r["grade"]], "small", wrap=True))
        cl.addWidget(label(f"Functionality: <b>{r['functional_status']}</b>", wrap=True))
        cl.addWidget(label("Based on your answers — not verified from the image.", "small", wrap=True))
        cl.addStretch()
        row.addWidget(cond, 2)
        # Value
        val, vl = card("true", (18, 16, 18, 16), 6)
        v = r["value"]
        if r["classification"] in ("Hazardous",):
            vl.addWidget(label("Resale value", "h3"))
            vl.addWidget(label("Not resellable", "h2"))
            vl.addWidget(label(v["note"], "small", wrap=True))
        elif r["classification"] == "Recyclable":
            vl.addWidget(label("Material recovery value", "h3"))
            vl.addWidget(label(f"{rupees(v['low'])} – {rupees(v['high'])}", "h2"))
            vl.addWidget(label(v["note"], "small", wrap=True))
        else:
            vl.addWidget(label("Estimated resale value", "h3"))
            rng = label(f"{rupees(v['low'])} – {rupees(v['high'])}")
            rng.setStyleSheet("font-size:22px; font-weight:800; color:white;")
            vl.addWidget(rng)
            sp = label(f"Suggested listing price: <b style='color:#34d399'>{rupees(v['suggested'])}</b>")
            vl.addWidget(sp)
            vl.addWidget(label(f"Based on {v['basis']}, age and condition.", "small", wrap=True))
        imp = assessment.environmental_impact(r["category"])
        vl.addWidget(label(f"🌱 Reuse avoids ~{imp['co2_kg']} kg CO₂ and {imp['ewaste_kg']} kg e-waste.", "small", wrap=True))
        vl.addStretch()
        row.addWidget(val, 2)
        lay.addLayout(row)

        lay.addWidget(label("Recommended recovery pathways", "h2"))
        grid = QGridLayout()
        grid.setSpacing(12)
        for i, rec in enumerate(r["recommendations"]):
            c, rl = card("true", (16, 14, 16, 14), 6)
            rl.addWidget(label(rec["title"], "h3"))
            rl.addWidget(label(rec["text"], "small", wrap=True))
            rl.addStretch()
            if rec["action"] != "info":
                txt = {"create_listing": "Create listing", "repair": "Find repair partner",
                       "repair_estimate": "Estimate cost", "rescan": "Scan again", "refurbish": "Request refurbishment",
                       "refurb_value": "Show value", "recycle": "Book collection", "recovery_report": "View report",
                       "donate": "Donate", "inspection": "Book inspection"}[rec["action"]]
                if rec["action"] == "create_listing" and not r["can_list"]:
                    continue
                rl.addWidget(button(txt, "primary" if rec["action"] == "create_listing" else None,
                                    lambda _=False, a=rec["action"]: self._action(a)))
            grid.addWidget(c, i // 3, i % 3)
        lay.addLayout(grid)
        if not r["can_list"]:
            blk, bkl = card("danger" if r["classification"] == "Hazardous" else "warn", (16, 12, 16, 12))
            msg = ("This device is classified as Hazardous and cannot be listed for consumer resale. "
                   "Please book an authorised e-waste collection." if r["classification"] == "Hazardous" else
                   "Recyclable devices are routed to authorised recyclers rather than the marketplace.")
            bkl.addWidget(label(msg, wrap=True))
            lay.addWidget(blk)
        lay.addStretch()

        clear_layout(self.result_page.layout() or QVBoxLayout(self.result_page))
        pl = self.result_page.layout()
        pl.setContentsMargins(0, 0, 0, 0)
        pl.addWidget(scroll(inner), 1)
        nav = QHBoxLayout()
        nav.addWidget(button("← Edit answers", None, lambda: self._set_step(2)))
        nav.addWidget(button("📷 Scan another device", None, self.rescan))
        nav.addStretch()
        if r["can_list"]:
            nav.addWidget(button("🛍️  Create marketplace listing", "primary", lambda: self._action("create_listing")))
        pl.addLayout(nav)

    def _action(self, action: str):
        r = self.result
        ans = {k: v for k, v in self.answers.items() if not k.startswith("_")}
        if action == "create_listing":
            draft = listing_ai.draft_from_assessment(r, ans, self.state.user.get("city", ""))
            draft["assessment_id"] = self.assessment_id
            draft["image_path"] = self.image_path
            self.state.listing_draft = draft
            self.state.go("create_listing", from_ai=True)
        elif action == "rescan":
            self.rescan()
        elif action == "repair_estimate":
            est = assessment.repair_estimate(r["category"], ans)
            lines = "\n".join(f"• {t}: {rupees(a)} – {rupees(b)}" for t, a, b in est["items"]) or "• General diagnosis: ₹300 – ₹800"
            after = assessment.refurbished_value(r["category"], r["brand"], ans)
            QMessageBox.information(self, "Typical repair cost",
                                    f"{lines}\n\nTotal: {rupees(est['low'])} – {rupees(est['high'])}\n"
                                    f"Value after repair (Excellent condition): about {rupees(after)}\n\n"
                                    "Indicative ranges only; the repair partner gives the final quote.")
        elif action == "refurb_value":
            after = assessment.refurbished_value(r["category"], r["brand"], ans)
            QMessageBox.information(self, "Estimated refurbished value",
                                    f"As-is suggested price: {rupees(r['value']['suggested'])}\n"
                                    f"After professional refurbishment: about {rupees(after)}")
        elif action == "recovery_report":
            imp = assessment.environmental_impact(r["category"])
            QMessageBox.information(self, "Recovery report",
                                    f"Device: {r['category']}\nE-waste diverted from landfill: {imp['ewaste_kg']} kg\n"
                                    "Recovered via authorised recycling: metals (copper, aluminium, gold traces), "
                                    "plastics and glass. Batteries and hazardous parts are processed separately.\n\n"
                                    "A detailed certificate is issued by the recycler after collection.")
        else:
            rtype = {"repair": "repair", "refurbish": "refurbish", "recycle": "recycle_collection",
                     "donate": "donate", "inspection": "inspection"}[action]
            if RecoveryRequestDialog(self.state, rtype, self.assessment_id, r["category"], self).exec():
                self.state.toast("Request submitted. Track it in the Recovery Center.", "success")

    def rescan(self):
        self.result = None
        self.captured = None
        self.findings = {}
        self._set_step(0)
        self.start_camera()
