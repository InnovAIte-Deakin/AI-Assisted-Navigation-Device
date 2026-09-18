"""Depth proxy estimation.

Ported from ML_side/notebooks/cohort-2/04_training_and_depth_estimation.ipynb,
section 11 ("Depth estimation — work in progress"). The notebook only computed
these scores inline on label files inside a Colab session; this module makes
the same logic importable so the backend (or tests) can call it directly.

This is a PROXY, not real depth estimation — it infers "closeness" from a
bounding box's size and vertical position in the frame, not from any actual
depth sensor or monocular depth model. See ML_side/README.md, Known Gaps
("Proximity is a bbox area heuristic") and Future Directions Tier 1
("Integrate depth estimation into the backend") for context on why this
exists and what would replace it.

Note: this module's function signatures were written to match
ML_side/tests/test_depth_estimator.py (already in the repo, authored
separately) rather than invented from scratch — running `pytest
ML_side/tests/test_depth_estimator.py -v` against this file should pass.
"""

from pathlib import Path

import numpy as np

REQUIRED_BOX_KEYS = ("x_min", "y_min", "x_max", "y_max")
DEFAULT_ALPHA = 0.7
DEFAULT_BETA = 0.3


def baseline_depth_score(box_height_px, img_height_px):
    """Baseline depth proxy: taller boxes (more pixels) are assumed closer.

    Formula ported verbatim from the notebook's `baseline_depth_score`.
    """
    return float(box_height_px) / float(img_height_px)


def improved_depth_score(
    box_height_px,
    box_center_y_px,
    img_height_px,
    alpha=DEFAULT_ALPHA,
    beta=DEFAULT_BETA,
):
    """Improved depth proxy combining box size and vertical position.

    Objects that are both large and low in the frame (closer to the camera,
    typically) score as "closer". Formula ported verbatim from the
    notebook's `improved_depth_score`.
    """
    size_score = float(box_height_px) / float(img_height_px)
    position_score = float(box_center_y_px) / float(img_height_px)
    return alpha * size_score + beta * position_score


def read_yolo_labels(label_path):
    """Read a YOLO-format label file: `class x_center y_center width height`
    (all normalized 0-1). Returns a list of (cls, xc, yc, w, h) tuples.

    Ported from the notebook's `read_yolo_labels` — used there to recompute
    depth proxy scores from ground-truth label files rather than live
    detections.
    """
    rows = []
    with open(label_path, "r") as f:
        for line in f:
            parts = line.strip().split()
            if len(parts) != 5:
                continue
            cls = int(float(parts[0]))
            xc, yc, w, h = map(float, parts[1:])
            rows.append((cls, xc, yc, w, h))
    return rows


def _load_image_array(image):
    """Accept a numpy array or an image file path and return a numpy array."""
    if isinstance(image, (str, Path)):
        from PIL import Image as PILImage

        with PILImage.open(image) as im:
            return np.array(im)
    return image


def _normalize_box(box):
    """Accept either a dict with x_min/y_min/x_max/y_max keys, or a 4-item
    (x_min, y_min, x_max, y_max) sequence, and return a validated dict.
    """
    if isinstance(box, dict):
        missing = [k for k in REQUIRED_BOX_KEYS if k not in box]
        if missing:
            raise ValueError(
                f"Bounding box dict must contain {', '.join(REQUIRED_BOX_KEYS)}; "
                f"missing: {', '.join(missing)}"
            )
        x_min, y_min, x_max, y_max = (box[k] for k in REQUIRED_BOX_KEYS)
    else:
        try:
            x_min, y_min, x_max, y_max = box
        except (TypeError, ValueError) as exc:
            raise ValueError(
                "Bounding box sequence must have exactly 4 values: "
                "(x_min, y_min, x_max, y_max)"
            ) from exc

    width = x_max - x_min
    height = y_max - y_min
    if width <= 0 or height <= 0:
        raise ValueError(
            "Bounding box must have positive width and height, "
            f"got width={width}, height={height}"
        )

    return {"x_min": x_min, "y_min": y_min, "x_max": x_max, "y_max": y_max}


def estimate_depth(image, bounding_boxes=None, alpha=DEFAULT_ALPHA, beta=DEFAULT_BETA):
    """Compute relative depth proxy scores for a set of boxes on one frame.

    This does NOT produce a real depth map — `depth_map` is always None. It's
    a placeholder key reserved for when real monocular depth estimation
    replaces this proxy (see ML README Future Directions, Tier 1).

    Args:
        image: numpy array (H, W) or (H, W, C), or a path to an image file.
        bounding_boxes: optional list of boxes. Each box is either a dict
            with x_min/y_min/x_max/y_max keys, or a 4-item
            (x_min, y_min, x_max, y_max) sequence.
        alpha, beta: weights passed through to improved_depth_score.

    Returns:
        dict with keys: image_height, image_width, unit ("relative_depth_score"),
        depth_map (always None), and boxes — a list of per-box dicts each
        containing "bbox", "baseline_depth_score", and "improved_depth_score".
    """
    arr = np.asarray(_load_image_array(image))

    if arr.ndim < 2:
        raise ValueError("Image array must have at least 2 dimensions (H, W[, C])")

    img_height, img_width = arr.shape[0], arr.shape[1]

    boxes_out = []
    for raw_box in bounding_boxes or []:
        box = _normalize_box(raw_box)
        box_height_px = box["y_max"] - box["y_min"]
        box_center_y_px = (box["y_min"] + box["y_max"]) / 2.0

        boxes_out.append(
            {
                "bbox": box,
                "baseline_depth_score": baseline_depth_score(box_height_px, img_height),
                "improved_depth_score": improved_depth_score(
                    box_height_px, box_center_y_px, img_height, alpha=alpha, beta=beta
                ),
            }
        )

    return {
        "image_height": img_height,
        "image_width": img_width,
        "unit": "relative_depth_score",
        "depth_map": None,
        "boxes": boxes_out,
    }
