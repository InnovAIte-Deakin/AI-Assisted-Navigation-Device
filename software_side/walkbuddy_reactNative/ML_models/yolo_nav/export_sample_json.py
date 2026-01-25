"""
Generate a sample ML → Software JSON payload from a YOLO model
and save it as `sample_detections.json` in this directory.

This is intended as a concrete artifact you can share with the
Software stream to demonstrate and validate the JSON format.
"""

from __future__ import annotations

import json
from pathlib import Path

from ultralytics import YOLO

from ml_to_software_json import yolo_result_to_json


ROOT = Path(__file__).resolve().parent
PROJECT_ROOT = ROOT.parent.parent.parent.parent  # Go up to AI-Assisted-Navigation-Device-main

# Try trained model first, fallback to base model
TRAINED_MODEL = PROJECT_ROOT / "ML_side" / "models" / "object_detection" / "best.pt"
BASE_MODEL = ROOT / "weights" / "yolov8s.pt"

# Use a validation image from the dataset
VAL_IMAGE_DIR = PROJECT_ROOT / "ML_side" / "data" / "processed" / "val_dataset" / "val" / "images"
OUT_JSON = ROOT / "sample_detections.json"


def main() -> None:
    # Choose model: prefer trained, fallback to base
    if TRAINED_MODEL.exists():
        model_path = TRAINED_MODEL
        source_name = "yolov8s_indoor_v1_trained"
        print(f"✅ Using trained model: {model_path}")
    elif BASE_MODEL.exists():
        model_path = BASE_MODEL
        source_name = "yolov8s_base"
        print(f"⚠️  Using base model (trained model not found): {model_path}")
    else:
        raise SystemExit(
            f"❌ No model found!\n"
            f"  Looked for trained: {TRAINED_MODEL}\n"
            f"  Looked for base: {BASE_MODEL}"
        )

    # Find a test image
    test_image = None
    if VAL_IMAGE_DIR.exists():
        jpg_files = list(VAL_IMAGE_DIR.glob("*.jpg"))
        if jpg_files:
            test_image = jpg_files[0]
            print(f"✅ Using validation image: {test_image.name}")
    
    if test_image is None:
        raise SystemExit(
            f"❌ No test image found!\n"
            f"  Looked in: {VAL_IMAGE_DIR}\n"
            f"  Place at least one .jpg image there."
        )

    print(f"\nLoading model from: {model_path}")
    model = YOLO(str(model_path))

    print(f"Running inference on: {test_image.name}")
    result = model.predict(str(test_image), conf=0.3, verbose=False)[0]

    payload = yolo_result_to_json(result, source_name=source_name)

    with OUT_JSON.open("w", encoding="utf-8") as f:
        json.dump(payload, f, indent=2)

    num_detections = len(payload.get("detections", []))
    print(f"\n✅ Wrote {OUT_JSON}")
    print(f"   Found {num_detections} detection(s)")
    if num_detections > 0:
        labels = [d["label"] for d in payload["detections"]]
        print(f"   Classes: {', '.join(set(labels))}")


if __name__ == "__main__":
    main()


