import json
import numpy as np
from pathlib import Path
from ultralytics import YOLO
from opentelemetry import trace

# Initialize Tracer
tracer = trace.get_tracer("vision.adapter")

# Load model once globally
BASE_DIR = Path(__file__).resolve().parents[4] 
MODEL_PATH = BASE_DIR / "ML_side" / "models" / "best.pt"
model_instance = YOLO(str(MODEL_PATH))

def vision_adapter(image_path: str) -> dict:
    """
    Pure function: Image Path -> Standardized Dict
    No file saving, no debug dumps.
    """
    # 1. INFERENCE (Wrapped in Span)
    with tracer.start_as_current_span("vision.inference") as span:
        # Add attributes for context without overloading logs
        span.set_attribute("model", "yolo")
        
        results = model_instance.predict(
            source=image_path,
            conf=0.25,
            iou=0.45,
            verbose=False
        )
    
    # 2. POST-PROCESSING (Wrapped in Span)
    with tracer.start_as_current_span("vision.formatting") as span:
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
        
        # Record detection count (high signal metric)
        span.set_attribute("detection_count", len(clean_detections))

    return {
        "image_id": Path(image_path).stem,
        "detections": clean_detections
    }