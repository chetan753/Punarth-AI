"""Download YOLOv8n and export it to ONNX for the offline AI Scanner.

    pip install ultralytics
    python tools/get_model.py

Creates models/yolov8n.onnx (~12 MB). ultralytics is only needed for this
one-time export; the app itself runs the model with onnxruntime.
"""
import shutil
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
MODELS = ROOT / "models"
MODELS.mkdir(exist_ok=True)

try:
    from ultralytics import YOLO
except ImportError:
    sys.exit("Please run:  pip install ultralytics   (then run this script again)")

model = YOLO("yolov8n.pt")
out = model.export(format="onnx", imgsz=640, opset=12, simplify=False)
dest = MODELS / "yolov8n.onnx"
shutil.move(str(out), dest)
print(f"Saved detector to {dest}")
