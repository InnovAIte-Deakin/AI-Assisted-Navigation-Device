"""Optional, display-only metric depth estimates for vision detections.

The estimator intentionally uses a separate model from the deployed YOLOv8
detector.  It is disabled unless WALKBUDDY_DEPTH_MODEL_DIR points to a local
Depth Anything V2 Metric Indoor Small Hugging Face model directory.  Do not
use its output in safety decisions: it has not been calibrated for a device.
"""
from __future__ import annotations

import logging
import time
from pathlib import Path
from typing import Any

import cv2
import numpy as np

logger = logging.getLogger(__name__)


class MetricDepthEstimator:
    """Lazy local-model estimator, limited to one complete frame per interval."""

    def __init__(self, model_dir: str | Path | None, interval_s: float = 0.5):
        self.model_dir = Path(model_dir) if model_dir else None
        self.interval_s = interval_s
        self._processor: Any = None
        self._model: Any = None
        self._torch: Any = None
        self._last_run_at = 0.0
        self.available = False

    def load(self) -> bool:
        if not self.model_dir or not self.model_dir.is_dir():
            logger.info("Depth estimates disabled: no local depth-model directory configured.")
            return False
        try:
            import torch
            from transformers import AutoImageProcessor, AutoModelForDepthEstimation

            self._processor = AutoImageProcessor.from_pretrained(self.model_dir, local_files_only=True)
            self._model = AutoModelForDepthEstimation.from_pretrained(self.model_dir, local_files_only=True)
            self._model.eval()
            self._torch = torch
            self.available = True
            logger.info("Optional metric depth model loaded from %s", self.model_dir)
        except Exception as exc:
            logger.warning("Depth estimates disabled: unable to load local model (%s)", exc)
        return self.available

    def annotate(self, image_path: str, detections: list[dict]) -> list[dict]:
        """Add distance_m only on scheduled frames; otherwise leave detections untouched."""
        now = time.monotonic()
        if not self.available or now - self._last_run_at < self.interval_s:
            return detections
        self._last_run_at = now
        image = cv2.imread(image_path)
        if image is None:
            return detections
        try:
            rgb = cv2.cvtColor(image, cv2.COLOR_BGR2RGB)
            inputs = self._processor(images=rgb, return_tensors="pt")
            with self._torch.no_grad():
                predicted = self._model(**inputs).predicted_depth
            depth = self._torch.nn.functional.interpolate(
                predicted.unsqueeze(1), size=rgb.shape[:2], mode="bicubic", align_corners=False
            ).squeeze().cpu().numpy()
        except Exception:
            logger.exception("Depth inference failed; retaining normal YOLO response.")
            return detections

        for detection in detections:
            estimate = self._box_median(depth, detection.get("bbox", {}))
            if estimate is not None:
                detection["distance_m"] = round(estimate, 1)
        return detections

    @staticmethod
    def _box_median(depth: np.ndarray, box: dict) -> float | None:
        h, w = depth.shape[:2]
        x1, x2 = sorted((int(box.get("x_min", 0)), int(box.get("x_max", 0))))
        y1, y2 = sorted((int(box.get("y_min", 0)), int(box.get("y_max", 0))))
        # Ignore the outer 20% of a box to reduce background/border contamination.
        dx, dy = max(1, (x2 - x1) // 5), max(1, (y2 - y1) // 5)
        crop = depth[max(0, y1 + dy):min(h, y2 - dy), max(0, x1 + dx):min(w, x2 - dx)]
        values = crop[np.isfinite(crop) & (crop > 0)]
        return float(np.median(values)) if values.size else None
