"""Optional relative-depth enrichment for vision detections.

The existing depth estimator provides a relative proxy based on bounding-box
size and vertical position. It is not a physical distance measurement.

Depth estimation is optional: if the ML-side module is unavailable or raises
an error, detections are preserved with ``relative_depth`` set to ``None``.
"""

from __future__ import annotations

import importlib.util
import logging
from pathlib import Path
from typing import Callable

logger = logging.getLogger(__name__)


def _load_depth_estimator() -> Callable | None:
    """Load the existing ML-side depth estimator when available."""

    try:
        from depth.depth_estimator import estimate_depth

        return estimate_depth
    except ImportError:
        pass

    # Local repository fallback:
    # repo/
    #   ML_side/depth/depth_estimator.py
    #   software_side/.../backend/adapters/depth_adapter.py
    repo_root = Path(__file__).resolve().parents[4]
    estimator_path = repo_root / "ML_side" / "depth" / "depth_estimator.py"

    if not estimator_path.is_file():
        logger.warning(
            "Depth estimator is unavailable; relative depth enrichment disabled."
        )
        return None

    try:
        spec = importlib.util.spec_from_file_location(
            "walkbuddy_depth_estimator",
            estimator_path,
        )
        if spec is None or spec.loader is None:
            return None

        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)

        return module.estimate_depth
    except Exception:
        logger.exception(
            "Unable to load depth estimator; relative depth enrichment disabled."
        )
        return None


estimate_depth = _load_depth_estimator()


def enrich_detections_with_depth(
    image_path: str,
    detections: list[dict],
) -> list[dict]:
    """Add an optional relative-depth score to each detection.

    The value comes from the estimator's ``improved_depth_score`` and must not
    be interpreted as metres or any other physical distance.

    If depth estimation is unavailable or fails, the existing detections are
    returned normally with ``relative_depth`` set to ``None``.
    """

    for detection in detections:
        detection["relative_depth"] = None

    if not detections or estimate_depth is None:
        return detections

    try:
        depth_result = estimate_depth(
            image_path,
            bounding_boxes=[detection["bbox"] for detection in detections],
        )

        depth_boxes = depth_result.get("boxes", [])

        for detection, depth_box in zip(detections, depth_boxes):
            score = depth_box.get("improved_depth_score")
            if score is not None:
                detection["relative_depth"] = float(score)

    except Exception:
        logger.exception(
            "Depth estimation failed; continuing without relative depth."
        )

    return detections