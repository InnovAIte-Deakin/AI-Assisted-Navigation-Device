import logging
from pathlib import Path
from typing import Dict, Any
import cv2
from opentelemetry import trace

tracer = trace.get_tracer("ocr.adapter")
logger = logging.getLogger(__name__)

# EasyOCR crashes with cv2.error when a detected text region produces a
# zero-dimension crop (reproducible on tall portrait images).  Capping the
# longer side at 1024 px before detection prevents the bad crop, and the
# try/except is a second-line safety net.
_MAX_OCR_DIM = 1024


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

    img = cv2.imread(str(path))
    if img is None or img.size == 0:
        return {"image_id": path.stem, "detections": []}

    # Downscale large images so EasyOCR's crop-resize never produces a
    # zero-size region.  Pass the numpy array directly instead of the path
    # to avoid a second disk read.
    h, w = img.shape[:2]
    if max(h, w) > _MAX_OCR_DIM:
        scale = _MAX_OCR_DIM / max(h, w)
        img = cv2.resize(img, (int(w * scale), int(h * scale)), interpolation=cv2.INTER_AREA)

    with tracer.start_as_current_span("ocr.read_text"):
        try:
            raw = reader.readtext(img)
        except cv2.error as exc:
            logger.warning(f"[OCR] EasyOCR internal resize error (returning empty): {exc}")
            raw = []

    detections = []
    for bbox, text, conf in raw:
        if conf < 0.3:
            continue
        try:
            detections.append({
                "category": text.strip(),
                "confidence": round(float(conf), 4),
                "bbox": _convert_4corners_to_bbox(bbox),
            })
        except Exception:
            pass

    detections.sort(key=lambda x: x["confidence"], reverse=True)

    return {
        "image_id": path.stem,
        "detections": detections,
    }
