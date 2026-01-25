"""
Utilities to convert Ultralytics YOLO results into a standard
ML → Software JSON payload for the AI-Assisted Navigation Device.

Intended usage:
    from ultralytics import YOLO
    from ml_to_software_json import yolo_result_to_json

    model = YOLO("weights/yolov8s.pt")
    result = model.predict("some_image.jpg", conf=0.3, verbose=False)[0]
    payload = yolo_result_to_json(result, source_name="yolov8s_indoor_v1")
"""

from __future__ import annotations

import time
import uuid
from typing import Any, Dict


def _severity_from_area_frac(area_frac: float, base: float = 0.14) -> str:
    """
    Map relative bounding-box area → coarse severity bucket.

    This mirrors the heuristic used on the Android side:
    - "near":   object fills at least `base` of the frame
    - "mid":    object fills ~0.55×..1× of that threshold
    - "far":    object fills ~0.32×..0.55× of that threshold
    - "none":   otherwise (too small / far away)
    """
    if area_frac >= base:
        return "near"
    if area_frac >= base * 0.55:
        return "mid"
    if area_frac >= base * 0.32:
        return "far"
    return "none"


def _side_from_cx(cx_norm: float) -> str:
    """
    Turn normalized horizontal center position into a coarse side label.
    """
    if cx_norm < 0.4:
        return "left"
    if cx_norm > 0.6:
        return "right"
    return "center"


def _iso_timestamp_now() -> str:
    """
    Return an ISO-8601 timestamp with nanosecond-ish precision in UTC.
    Example: 2025-11-29T12:34:56.123456789Z
    """
    t = time.gmtime()
    base = time.strftime("%Y-%m-%dT%H:%M:%S", t)
    ns = int(time.time_ns() % 1_000_000_000)
    return f"{base}.{ns:09d}Z"


def yolo_result_to_json(result, source_name: str = "yolov8s_indoor_v1") -> Dict[str, Any]:
    """
    Convert a single Ultralytics YOLO result object into the agreed
    JSON structure the Software team will consume.

    The output schema (one frame) is:
    {
      "timestamp": "...",
      "frame_id": "...",
      "source": "model_or_pipeline_name",
      "detections": [
        {
          "id": 0,
          "label": "office-chair",
          "confidence": 0.82,
          "bbox_norm": { "cx": 0.5, "cy": 0.6, "w": 0.2, "h": 0.3 },
          "severity": "near" | "mid" | "far" | "none",
          "side": "left" | "center" | "right",
          "distance_m": null
        },
        ...
      ]
    }
    """
    # Original image size (H, W, C)
    H, W = result.orig_shape[:2]
    frame_area = float(H * W) if H > 0 and W > 0 else 0.0

    boxes = getattr(result, "boxes", None)
    detections = []

    if boxes is not None and len(boxes) > 0:
        xyxy = boxes.xyxy.cpu().numpy()
        conf = boxes.conf.cpu().numpy()
        cls_ids = boxes.cls.cpu().numpy().astype(int)
        names = getattr(result, "names", {}) or {}

        for i, (box, c, cls_id) in enumerate(zip(xyxy, conf, cls_ids)):
            x1, y1, x2, y2 = box
            w = max(0.0, x2 - x1)
            h = max(0.0, y2 - y1)
            cx = x1 + w / 2.0
            cy = y1 + h / 2.0

            if W <= 0 or H <= 0:
                cx_norm = cy_norm = w_norm = h_norm = 0.0
            else:
                cx_norm = float(cx / W)
                cy_norm = float(cy / H)
                w_norm = float(w / W)
                h_norm = float(h / H)

            area_frac = (w * h) / frame_area if frame_area > 0 else 0.0
            severity = _severity_from_area_frac(area_frac)
            side = _side_from_cx(cx_norm)

            detections.append(
                {
                    "id": i,
                    "label": names.get(int(cls_id), str(int(cls_id))),
                    "confidence": float(c),
                    "bbox_norm": {
                        "cx": cx_norm,
                        "cy": cy_norm,
                        "w": w_norm,
                        "h": h_norm,
                    },
                    "severity": severity,
                    "side": side,
                    "distance_m": None,  # reserved for future depth estimation
                }
            )

    payload: Dict[str, Any] = {
        "timestamp": _iso_timestamp_now(),
        "frame_id": str(uuid.uuid4()),
        "source": source_name,
        "detections": detections,
    }
    return payload


