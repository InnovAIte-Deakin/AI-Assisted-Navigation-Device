from pathlib import Path
from ultralytics import YOLO
from opentelemetry import trace

tracer = trace.get_tracer("vision.adapter")

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

    if result.boxes:
        for box in result.boxes:
            coords = box.xyxy[0].tolist()
            conf = float(box.conf[0])
            cls_id = int(box.cls[0])
            label = result.names[cls_id]

            detections.append({
                "category": label,
                "confidence": round(conf, 3),
                "bbox": {
                    "x_min": int(coords[0]),
                    "y_min": int(coords[1]),
                    "x_max": int(coords[2]),
                    "y_max": int(coords[3]),
                },
            })

    detections.sort(key=lambda x: x["confidence"], reverse=True)

    return {
        "image_id": Path(image_path).stem,
        "detections": detections,
    }
