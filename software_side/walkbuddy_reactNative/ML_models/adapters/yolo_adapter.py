import json
import numpy as np
from pathlib import Path
from ultralytics import YOLO

# Load model once globally
BASE_DIR = Path(__file__).resolve().parent.parent.parent.parent.parent # Adjust based on your structure
print(BASE_DIR)
MODEL_PATH = BASE_DIR / "ML_side" / "models" / "object_detection" / "best.pt"
model_instance = YOLO(str(MODEL_PATH))

def vision_adapter(image_path: str) -> dict:
    """
    Pure function: Image Path -> Standardized Dict
    No file saving, no debug dumps.
    """
    # Run Inference
    results = model_instance.predict(
        source=image_path,
        conf=0.25,
        iou=0.45,
        verbose=False
    )
    result = results[0]

    # Standardize Output
    clean_detections = []
    if result.boxes:
        for box in result.boxes:
            # Extract basic data
            coords = box.xyxy[0].tolist() # [x1, y1, x2, y2]
            conf = float(box.conf[0])
            cls_id = int(box.cls[0])
            label = result.names[cls_id]

            clean_detections.append({
                "category": label,
                "confidence": round(conf, 3),
                "bbox": {
                    "x_min": int(coords[0]),
                    "y_min": int(coords[1]),
                    "x_max": int(coords[2]),
                    "y_max": int(coords[3])
                }
            })

    # Sort by confidence
    clean_detections.sort(key=lambda x: x['confidence'], reverse=True)

    return {
        "image_id": Path(image_path).stem,
        "detections": clean_detections
    }