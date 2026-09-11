from pathlib import Path
from adapters.depth_adapter import enrich_detections_with_depth
import cv2
from ultralytics import YOLO
from opentelemetry import trace
from tts_service.message_reasoning import calculate_spatial_position # reuse existing direction logic
from ml_contract.navigation_semantics import BaseSeverity, get_base_severity, severity_rank

tracer = trace.get_tracer("vision.adapter")

# Canonical MVP labels use their centralized base severities. Unknown legacy
# labels retain the existing LOW fallback without acquiring MVP semantics.

DEFAULT_PRIORITY = BaseSeverity.LOW.name


def get_priority(category: str) -> str:
    """Get the contract base severity, preserving ``LOW`` for unknown labels."""
    severity = get_base_severity(category)
    return severity.name if severity is not None else DEFAULT_PRIORITY


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
    detections = enrich_detections_with_depth(image_path, detections)
    # Sort by deliberate base-severity ranking, then by confidence.
    priority_order = {
        severity.name: -severity_rank(severity) for severity in BaseSeverity
    }
    detections.sort(key=lambda x: (priority_order.get(x["priority"], 0), -x["confidence"]))

    return {
        "image_id": Path(image_path).stem,
        "detections": detections,
        "metadata": {
            "image_shape": [image_height, image_width],
        },
    }
