"""AI Scanner vision.

1. Local, offline detection with a YOLO model exported to ONNX (COCO classes
   such as cell phone, laptop, tv, keyboard, mouse, remote).
2. Image-quality checks and a visible-defect heuristic (possible cracks /
   deep scratches) inside the detected device box.
3. Optional cloud vision (Anthropic API) for category, brand / model and a
   description of visible defects, when ANTHROPIC_API_KEY is set.

Everything returned here is an *AI estimate*. Functionality is never
inferred from an image; it always comes from the seller's answers.
"""
from __future__ import annotations

import base64
import json
import math
import re

import cv2
import numpy as np

from . import catalog, config

COCO_NAMES = [
    "person", "bicycle", "car", "motorcycle", "airplane", "bus", "train", "truck", "boat", "traffic light",
    "fire hydrant", "stop sign", "parking meter", "bench", "bird", "cat", "dog", "horse", "sheep", "cow",
    "elephant", "bear", "zebra", "giraffe", "backpack", "umbrella", "handbag", "tie", "suitcase", "frisbee",
    "skis", "snowboard", "sports ball", "kite", "baseball bat", "baseball glove", "skateboard", "surfboard",
    "tennis racket", "bottle", "wine glass", "cup", "fork", "knife", "spoon", "bowl", "banana", "apple",
    "sandwich", "orange", "broccoli", "carrot", "hot dog", "pizza", "donut", "cake", "chair", "couch",
    "potted plant", "bed", "dining table", "toilet", "tv", "laptop", "mouse", "remote", "keyboard",
    "cell phone", "microwave", "oven", "toaster", "sink", "refrigerator", "book", "clock", "vase",
    "scissors", "teddy bear", "hair drier", "toothbrush",
]

# COCO class -> (marketplace category, friendly name)
ELECTRONICS = {
    "cell phone": ("Smartphones", "Smartphone / tablet"),
    "laptop": ("Laptops", "Laptop"),
    "tv": ("Televisions", "TV / monitor"),
    "keyboard": ("Computer Accessories", "Keyboard"),
    "mouse": ("Computer Accessories", "Mouse"),
    "remote": ("Other Electronics", "Remote / small device"),
    "microwave": ("Other Electronics", "Microwave"),
    "clock": ("Other Electronics", "Clock / small device"),
    "hair drier": ("Other Electronics", "Hair dryer"),
}


class Detector:
    """YOLOv5/v8/11 ONNX detector with onnxruntime (falls back to OpenCV DNN)."""

    def __init__(self, model_path=None, conf_threshold: float = 0.35):
        self.model_path = str(model_path or config.YOLO_MODEL_PATH)
        self.conf = conf_threshold
        self.session = None
        self.net = None
        self.input_size = 640
        self.error = ""
        self._load()

    @property
    def available(self) -> bool:
        return self.session is not None or self.net is not None

    def _load(self):
        import os
        if not os.path.exists(self.model_path):
            self.error = (f"Detector model not found at {self.model_path}. Run "
                          "`python tools/get_model.py` to download it, or choose the category manually.")
            return
        try:
            import onnxruntime as ort
            self.session = ort.InferenceSession(self.model_path, providers=["CPUExecutionProvider"])
            shape = self.session.get_inputs()[0].shape
            if isinstance(shape[2], int):
                self.input_size = shape[2]
        except Exception as e:  # pragma: no cover - depends on local install
            try:
                self.net = cv2.dnn.readNetFromONNX(self.model_path)
            except Exception as e2:
                self.error = f"Could not load detector: {e} / {e2}"

    def _infer(self, blob: np.ndarray) -> np.ndarray:
        if self.session is not None:
            name = self.session.get_inputs()[0].name
            return self.session.run(None, {name: blob})[0]
        self.net.setInput(blob)
        return self.net.forward()

    def detect(self, frame: np.ndarray, electronics_only: bool = True) -> list[dict]:
        if not self.available or frame is None:
            return []
        h, w = frame.shape[:2]
        s = self.input_size
        scale = min(s / w, s / h)
        nw, nh = int(round(w * scale)), int(round(h * scale))
        canvas = np.full((s, s, 3), 114, dtype=np.uint8)
        dx, dy = (s - nw) // 2, (s - nh) // 2
        canvas[dy:dy + nh, dx:dx + nw] = cv2.resize(frame, (nw, nh))
        blob = cv2.cvtColor(canvas, cv2.COLOR_BGR2RGB).astype(np.float32).transpose(2, 0, 1)[None] / 255.0
        out = self._infer(blob)
        return postprocess(out, scale, dx, dy, w, h, self.conf, electronics_only)


def postprocess(out: np.ndarray, scale: float, dx: int, dy: int, w: int, h: int,
                conf_thr: float = 0.35, electronics_only: bool = True) -> list[dict]:
    """Decode YOLO output. Supports v8/11 (1, 84, N) and v5 (1, N, 85)."""
    pred = np.squeeze(out, 0)
    if pred.shape[0] in (84, 85) and pred.shape[1] not in (84, 85):
        pred = pred.T                                   # -> (N, 84|85)
    if pred.shape[1] == 85:                             # YOLOv5: objectness at col 4
        scores_all = pred[:, 5:] * pred[:, 4:5]
    else:
        scores_all = pred[:, 4:]
    cls = scores_all.argmax(1)
    scores = scores_all[np.arange(len(cls)), cls]
    keep = scores >= conf_thr
    boxes, confs, classes = [], [], []
    for (cx, cy, bw, bh), sc, c in zip(pred[keep, :4], scores[keep], cls[keep]):
        name = COCO_NAMES[int(c)] if int(c) < len(COCO_NAMES) else str(c)
        if electronics_only and name not in ELECTRONICS:
            continue
        x = (cx - bw / 2 - dx) / scale
        y = (cy - bh / 2 - dy) / scale
        boxes.append([int(max(0, x)), int(max(0, y)), int(min(w, bw / scale)), int(min(h, bh / scale))])
        confs.append(float(sc))
        classes.append(name)
    if not boxes:
        return []
    idx = cv2.dnn.NMSBoxes(boxes, confs, conf_thr, 0.45)
    idx = np.array(idx).flatten().tolist() if len(idx) else []
    results = []
    for i in idx:
        name = classes[i]
        cat, friendly = ELECTRONICS.get(name, ("Other Electronics", name))
        results.append({"label": friendly, "coco_class": name, "category": cat,
                        "confidence": round(confs[i], 3), "box": boxes[i]})
    results.sort(key=lambda r: r["confidence"] * r["box"][2] * r["box"][3], reverse=True)
    return results


# ---------------------------------------------------------------------------
# Image quality and visible-defect heuristics
# ---------------------------------------------------------------------------

def image_quality(frame: np.ndarray) -> dict:
    gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
    sharp = float(cv2.Laplacian(gray, cv2.CV_64F).var())
    bright = float(gray.mean())
    tips = []
    if sharp < 60:
        tips.append("Image looks blurry — hold the device steady and closer to the camera.")
    if bright < 55:
        tips.append("Image is dark — add more light.")
    if bright > 215:
        tips.append("Image is over-exposed — reduce glare or direct light.")
    return {"sharpness": round(sharp, 1), "brightness": round(bright, 1), "ok": not tips, "tips": tips}


def analyze_defects(frame: np.ndarray, box: list[int] | None = None) -> list[dict]:
    """Flags *possible* cracks / deep scratches as long diagonal straight
    edges inside the device region. Returns [{label, confidence, source}]."""
    if frame is None:
        return []
    H, W = frame.shape[:2]
    x, y, bw, bh = box if box else (0, 0, W, H)
    roi = frame[y:y + bh, x:x + bw]
    if roi.size == 0 or min(roi.shape[:2]) < 40:
        return []
    gray = cv2.cvtColor(roi, cv2.COLOR_BGR2GRAY)
    gray = cv2.GaussianBlur(gray, (3, 3), 0)
    edges = cv2.Canny(gray, 50, 150)
    rh, rw = gray.shape
    min_len = 0.22 * min(rh, rw)
    lines = cv2.HoughLinesP(edges, 1, np.pi / 180, threshold=50, minLineLength=min_len, maxLineGap=6)
    defects = []
    diag = 0
    if lines is not None:
        mx, my = 0.07 * rw, 0.07 * rh
        for x1, y1, x2, y2 in np.asarray(lines).reshape(-1, 4):
            if min(x1, x2) < mx or max(x1, x2) > rw - mx or min(y1, y2) < my or max(y1, y2) > rh - my:
                continue  # device outline, not a defect
            ang = abs(math.degrees(math.atan2(y2 - y1, x2 - x1))) % 180
            if 12 < ang < 78 or 102 < ang < 168:
                diag += 1
    if diag >= 2:
        defects.append({"label": "Possible crack or deep scratch", "confidence": round(min(0.85, 0.45 + 0.08 * diag), 2),
                        "source": "ai_image"})
    return defects


# ---------------------------------------------------------------------------
# Optional cloud vision
# ---------------------------------------------------------------------------

VISION_PROMPT = (
    "You are the vision module of an e-waste recovery app. Look at the electronic device in the photo. "
    "Reply with ONLY a JSON object with keys: category (one of: " + ", ".join(catalog.CATEGORIES) + "), "
    "brand (string or empty if not recognisable), model (string or empty — do not guess wildly), "
    "visible_defects (list of objects with label and confidence 0-1, only what is visible e.g. cracked screen, "
    "dents, deep scratches, missing keys, swollen back panel), hazard_signs (list of strings; e.g. swollen battery, "
    "burn marks, exposed wiring), confidence (0-1 for the category). Never state whether the device works."
)


def cloud_identify(frame: np.ndarray, timeout: float = 30) -> dict:
    if not config.ANTHROPIC_API_KEY:
        raise RuntimeError("Cloud vision is off (set ANTHROPIC_API_KEY in .env to enable brand/model recognition).")
    import requests
    h, w = frame.shape[:2]
    scale = min(1.0, 1280 / max(h, w))
    img = cv2.resize(frame, (int(w * scale), int(h * scale))) if scale < 1 else frame
    ok, buf = cv2.imencode(".jpg", img, [cv2.IMWRITE_JPEG_QUALITY, 85])
    if not ok:
        raise RuntimeError("Could not encode image.")
    body = {
        "model": config.VISION_MODEL, "max_tokens": 600,
        "messages": [{"role": "user", "content": [
            {"type": "image", "source": {"type": "base64", "media_type": "image/jpeg",
                                         "data": base64.b64encode(buf.tobytes()).decode()}},
            {"type": "text", "text": VISION_PROMPT}]}],
    }
    r = requests.post("https://api.anthropic.com/v1/messages", json=body, timeout=timeout,
                      headers={"x-api-key": config.ANTHROPIC_API_KEY, "anthropic-version": "2023-06-01",
                               "content-type": "application/json"})
    r.raise_for_status()
    text = "".join(part.get("text", "") for part in r.json().get("content", []))
    return parse_vision_json(text)


def parse_vision_json(text: str) -> dict:
    m = re.search(r"\{.*\}", text, re.S)
    if not m:
        raise RuntimeError("Vision model did not return JSON.")
    data = json.loads(m.group(0))
    cat = data.get("category") if data.get("category") in catalog.CATEGORIES else "Other Electronics"
    defects = []
    for d in data.get("visible_defects") or []:
        if isinstance(d, str):
            d = {"label": d, "confidence": 0.6}
        defects.append({"label": str(d.get("label", ""))[:80], "confidence": float(d.get("confidence", 0.6)),
                        "source": "ai_image"})
    return {"category": cat, "brand": str(data.get("brand") or "")[:40], "model": str(data.get("model") or "")[:60],
            "defects": defects, "hazard_signs": [str(h)[:80] for h in data.get("hazard_signs") or []],
            "confidence": float(data.get("confidence") or 0.5)}


def analyze_capture(frame: np.ndarray, detector: Detector | None, use_cloud: bool = True) -> dict:
    """Full analysis of a captured frame. Returns findings for the assessment."""
    findings = {"detections": [], "category": "", "brand": "", "model": "", "defects": [],
                "hazard_signs": [], "quality": image_quality(frame), "sources": [], "notes": []}
    box = None
    if detector and detector.available:
        dets = detector.detect(frame)
        findings["detections"] = dets
        if dets:
            top = dets[0]
            box = top["box"]
            findings["category"] = top["category"]
            findings["detector_label"] = top["label"]
            findings["detector_confidence"] = top["confidence"]
            findings["sources"].append("local detector")
        else:
            findings["notes"].append("No electronic device detected — centre the device and try again, "
                                     "or pick the category manually.")
    elif detector is not None and detector.error:
        findings["notes"].append(detector.error)
    findings["defects"] = analyze_defects(frame, box)
    findings["box"] = box
    if use_cloud and config.ANTHROPIC_API_KEY:
        try:
            cloud = cloud_identify(frame)
            findings["sources"].append("cloud vision")
            if cloud["category"] and (not findings["category"] or cloud["confidence"] >= 0.6):
                findings["category"] = cloud["category"]
            findings["brand"], findings["model"] = cloud["brand"], cloud["model"]
            findings["defects"] += cloud["defects"]
            findings["hazard_signs"] = cloud["hazard_signs"]
        except Exception as e:  # network problems must not break the scanner
            findings["notes"].append(f"Cloud vision unavailable: {e}")
    return findings
