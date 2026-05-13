from pathlib import Path
import cv2
from ultralytics import YOLO
from opentelemetry import trace
from tts_service.message_reasoning import calculate_spatial_position # reuse existing direction logic

tracer = trace.get_tracer("vision.adapter")

# ============================================================================
# PRIORITY MAPPING - Priority Assignment to Detected Objects
# ============================================================================
# Priority tiers for navigation safety (per task requirements):
# 🔴 HIGH — moving vehicles, stairs, open doors, wet floors, people in path
# 🟡 MEDIUM — furniture, poles, bins, parked bikes
# 🟢 LOW — walls, background objects, decorations
#
# Note: Our YOLO model only detects indoor objects:
# book, books, monitor, office-chair, whiteboard, table, tv
# We map these to the closest priority tier based on physical danger.

PRIORITY_MAP = {
    # HIGH - Potential fall hazards / high risk for visually impaired
    "chair": "HIGH",
    "office-chair": "HIGH",
    "table": "HIGH",
    "monitor": "HIGH",
    "tv": "HIGH",
    
    # MEDIUM - Notable but less immediately dangerous
    "whiteboard": "MEDIUM",
    
    # LOW - Minimal hazard
    "book": "LOW",
    "books": "LOW",
}

# Default priority for unknown classes
DEFAULT_PRIORITY = "LOW"


def get_priority(category: str) -> str:
    """Get priority level for a detected category."""
    return PRIORITY_MAP.get(category.lower(), DEFAULT_PRIORITY)


def vision_adapter(model: YOLO, image_path: str) -> dict:
    with tracer.start_as_current_span("vision.inference") as span:
        span.set_attribute("model", "yolo")
        results = model.predict(
            source=image_path,
            conf=0.25,
            iou=0.45,
            verbose=False
        )

    result = results[0]
    detections = []
    
    # get image width for direction calculation
    image_height, image_width = result.orig_shape[:2]

    # Get image dimensions for spatial direction calculation
    img = cv2.imread(image_path)
    if img is not None:
        image_height, image_width = img.shape[:2]
    else:
        image_height, image_width = 480, 640

    if result.boxes:
        for box in result.boxes:
            coords = box.xyxy[0].tolist()
            conf = float(box.conf[0])
            cls_id = int(box.cls[0])
            label = result.names[cls_id]
            bbox = {
                "x_min": int(coords[0]),
                "y_min": int(coords[1]),
                "x_max": int(coords[2]),
                "y_max": int(coords[3]),
            }

            # compute left/right/ahead
            direction = calculate_spatial_position(bbox, image_width) 

            # Get priority for this category
            priority = get_priority(label)

            detections.append({
                "category": label,
                "confidence": round(conf, 3),
                "bbox": bbox,
                "direction": direction, # store computed direction instead of hardcoded value
                "priority": priority,  # NEW: Priority field
            })

    # Sort by priority first (HIGH > MEDIUM > LOW), then by confidence
    priority_order = {"HIGH": 0, "MEDIUM": 1, "LOW": 2}
    detections.sort(key=lambda x: (priority_order.get(x["priority"], 3), -x["confidence"]))

    return {
        "image_id": Path(image_path).stem,
        "detections": detections,
        "metadata": {
            "image_shape": [image_height, image_width],
        },
    }
