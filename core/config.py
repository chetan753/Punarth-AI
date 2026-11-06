"""Central configuration. Values come from environment variables or a .env file
in the project root (KEY=VALUE per line). Nothing secret is hard-coded."""
from __future__ import annotations

import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
# When packaged as an .exe (PyInstaller), keep data, models and .env next to the executable.
FROZEN = bool(getattr(sys, "frozen", False))
APP_DIR = Path(sys.executable).resolve().parent if FROZEN else ROOT


def _load_dotenv() -> None:
    env_file = APP_DIR / ".env"
    if not env_file.exists():
        return
    for raw in env_file.read_text(encoding="utf-8").splitlines():
        line = raw.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, _, value = line.partition("=")
        os.environ.setdefault(key.strip(), value.strip().strip('"').strip("'"))


_load_dotenv()

DATA_DIR = Path(os.environ.get("PUNARTH_DATA_DIR", APP_DIR / "data"))
DATA_DIR.mkdir(parents=True, exist_ok=True)
IMAGE_DIR = DATA_DIR / "images"
IMAGE_DIR.mkdir(parents=True, exist_ok=True)
DB_PATH = Path(os.environ.get("PUNARTH_DB", DATA_DIR / "punarth.db"))
MODELS_DIR = APP_DIR / "models"
ASSETS_DIR = ROOT / "assets"

# Payment server (runs separately; handles all Razorpay secrets + verification)
PAYMENT_SERVER_HOST = os.environ.get("PAYMENT_SERVER_HOST", "127.0.0.1")
PAYMENT_SERVER_PORT = int(os.environ.get("PAYMENT_SERVER_PORT", "5055"))
PAYMENT_SERVER_URL = os.environ.get(
    "PAYMENT_SERVER_URL", f"http://{PAYMENT_SERVER_HOST}:{PAYMENT_SERVER_PORT}"
)

# Razorpay — read ONLY by the payment server process.
RAZORPAY_KEY_ID = os.environ.get("RAZORPAY_KEY_ID", "")
RAZORPAY_KEY_SECRET = os.environ.get("RAZORPAY_KEY_SECRET", "")
RAZORPAY_WEBHOOK_SECRET = os.environ.get("RAZORPAY_WEBHOOK_SECRET", "")
# Demo mode lets you run the full flow at a hackathon without Razorpay keys.
# The payment is still confirmed by the server, never by the desktop app.
PAYMENT_DEMO_MODE = os.environ.get("PAYMENT_DEMO_MODE", "auto").lower()


def payments_in_demo_mode() -> bool:
    if PAYMENT_DEMO_MODE in ("1", "true", "yes", "on"):
        return True
    if PAYMENT_DEMO_MODE in ("0", "false", "no", "off"):
        return False
    return not (RAZORPAY_KEY_ID and RAZORPAY_KEY_SECRET)


# Optional cloud vision for brand/model recognition and defect description.
ANTHROPIC_API_KEY = os.environ.get("ANTHROPIC_API_KEY", "")
VISION_MODEL = os.environ.get("PUNARTH_VISION_MODEL", "claude-sonnet-5-5")

# Local object detector (YOLOv8/YOLO11 exported to ONNX, COCO classes)
YOLO_MODEL_PATH = Path(os.environ.get("PUNARTH_YOLO_MODEL", MODELS_DIR / "yolov8n.onnx"))
CAMERA_INDEX = int(os.environ.get("PUNARTH_CAMERA_INDEX", "0"))

CURRENCY = "INR"
