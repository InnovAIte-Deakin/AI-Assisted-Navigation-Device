from pathlib import Path
from typing import Dict, Any
import cv2
from opentelemetry import trace

tracer = trace.get_tracer("ocr.adapter")

def _convert_4corners_to_bbox(bbox_corners):
    x = [p[0] for p in bbox_corners]
    y = [p[1] for p in bbox_corners]
    return {
        "x_min": int(min(x)),
        "y_min": int(min(y)),
        "x_max": int(max(x)),
        "y_max": int(max(y)),
    }

def ocr_adapter(reader, image_path: str) -> Dict[str, Any]:
    path = Path(image_path)
    if not path.exists():
        raise FileNotFoundError(image_path)

    check = cv2.imread(str(path))
    if check is None or check.size == 0:
        return {"image_id": path.stem, "detections": []}

    with tracer.start_as_current_span("ocr.read_text"):
        raw = reader.readtext(str(path), detail=1, paragraph=False)

    detections = []
    for bbox, text, conf in raw:
        if conf < 0.25:
            continue
        text_clean = text.strip()
        if not text_clean:
            continue
        try:
            detections.append({
                "category": text_clean,
                "confidence": round(float(conf), 4),
                "bbox": _convert_4corners_to_bbox(bbox),
            })
        except Exception:
            pass

    # Sort top-to-bottom by vertical position for reading order
    detections.sort(key=lambda x: x["bbox"]["y_min"])

    return {
        "image_id": path.stem,
        "detections": detections,
    }
