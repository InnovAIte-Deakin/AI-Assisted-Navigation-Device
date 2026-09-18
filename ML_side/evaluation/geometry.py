"""Size and aspect-ratio bucketing on top of evaluate().

This module does not reimplement IoU matching, precision, or recall.
It slices the same ground-truth / prediction JSON that evaluate() already
consumes, then calls evaluate() once per bucket.

Ground-truth and predictions are filtered independently (COCO-style). A
medium ground-truth box whose matching prediction is large is therefore a
false negative in the medium bucket and a false positive in the large
bucket.

Coordinates are pixel xyxy, the same unit load_yolo_predict_fn() writes
and the existing eval fixtures use. COCO area thresholds are in px².
"""

from typing import Callable, List, Optional, Sequence

from .metrics import evaluate
from .taxonomy import TAXONOMY_CLASSES, canonicalize_class_name


DEFAULT_SMALL_AREA_MAX = float(32 ** 2)  # 1024, exclusive upper bound
DEFAULT_MEDIUM_AREA_MAX = float(96 ** 2)  # 9216, exclusive upper bound
DEFAULT_TALL_THIN_MIN = 3.0
DEFAULT_TALL_MIN = 1.5
DEFAULT_SQUARE_MIN = 2.0 / 3.0

SIZE_BUCKET_ORDER = ("small", "medium", "large")
ASPECT_BUCKET_ORDER = ("tall_thin", "tall", "square_ish", "wide")

ALLOWED_SPLITS = ("train", "val")
SPLIT_ALIASES = {
    "train": "train",
    "val": "val",
    "validation": "val",
    "eval": "val",
}
FORBIDDEN_SPLIT_TOKENS = ("test", "heldout", "held-out", "held_out")

COORDINATE_SPACE = "pixel_xyxy"


class HeldOutEvidenceError(ValueError):
    """Raised when a held-out test split or path is supplied. No override exists."""


class SizeThresholds:
    """COCO-style area cuts. small_max and medium_max are exclusive upper bounds."""

    def __init__(
        self,
        small_max: float = DEFAULT_SMALL_AREA_MAX,
        medium_max: float = DEFAULT_MEDIUM_AREA_MAX,
    ):
        if not (0 < small_max < medium_max):
            raise ValueError(
                f"Size thresholds must satisfy 0 < small_max < medium_max; "
                f"got small_max={small_max}, medium_max={medium_max}."
            )
        self.small_max = float(small_max)
        self.medium_max = float(medium_max)

    def as_edges(self) -> dict:
        return {
            "small": [0, self.small_max],
            "medium": [self.small_max, self.medium_max],
            "large": [self.medium_max, None],
        }


class AspectThresholds:
    """Height/width cuts. Lower bounds are inclusive, upper bounds exclusive."""

    def __init__(
        self,
        tall_thin_min: float = DEFAULT_TALL_THIN_MIN,
        tall_min: float = DEFAULT_TALL_MIN,
        square_min: float = DEFAULT_SQUARE_MIN,
    ):
        if not (0 < square_min < tall_min < tall_thin_min):
            raise ValueError(
                "Aspect thresholds must satisfy 0 < square_min < tall_min < "
                f"tall_thin_min; got square_min={square_min}, tall_min={tall_min}, "
                f"tall_thin_min={tall_thin_min}."
            )
        self.tall_thin_min = float(tall_thin_min)
        self.tall_min = float(tall_min)
        self.square_min = float(square_min)

    def as_edges(self) -> dict:
        return {
            "tall_thin": {"min_hw": self.tall_thin_min, "max_hw": None},
            "tall": {"min_hw": self.tall_min, "max_hw": self.tall_thin_min},
            "square_ish": {"min_hw": self.square_min, "max_hw": self.tall_min},
            "wide": {"min_hw": None, "max_hw": self.square_min},
        }


def bbox_area(bbox: Sequence[float]) -> float:
    """Pixel area of an [x_min, y_min, x_max, y_max] box; 0 if inverted or empty."""
    x1, y1, x2, y2 = bbox
    width = x2 - x1
    height = y2 - y1
    if width <= 0 or height <= 0:
        return 0.0
    return width * height


def bbox_aspect_hw(bbox: Sequence[float]) -> Optional[float]:
    """Height / width, or None when the box has no positive width/height."""
    x1, y1, x2, y2 = bbox
    width = x2 - x1
    height = y2 - y1
    if width <= 0 or height <= 0:
        return None
    return height / width


def _box_bbox(box: dict) -> Optional[list]:
    bbox = box.get("bbox")
    if not isinstance(bbox, (list, tuple)) or len(bbox) != 4:
        return None
    return list(bbox)


def size_bucket_for_area(area: float, thresholds: SizeThresholds) -> str:
    if area is None or area <= 0:
        return "invalid"
    if area < thresholds.small_max:
        return "small"
    if area < thresholds.medium_max:
        return "medium"
    return "large"


def aspect_bucket_for_hw(hw: Optional[float], thresholds: AspectThresholds) -> str:
    if hw is None:
        return "invalid"
    if hw >= thresholds.tall_thin_min:
        return "tall_thin"
    if hw >= thresholds.tall_min:
        return "tall"
    if hw >= thresholds.square_min:
        return "square_ish"
    return "wide"


def box_size_bucket(box: dict, thresholds: SizeThresholds) -> str:
    bbox = _box_bbox(box)
    if bbox is None:
        return "invalid"
    return size_bucket_for_area(bbox_area(bbox), thresholds)


def box_aspect_bucket(box: dict, thresholds: AspectThresholds) -> str:
    bbox = _box_bbox(box)
    if bbox is None:
        return "invalid"
    return aspect_bucket_for_hw(bbox_aspect_hw(bbox), thresholds)


def filter_records(records: List[dict], predicate: Callable[[dict], bool]) -> List[dict]:
    """Keep every image_id; keep only boxes for which predicate(box) is True.

    Extra per-record fields (for example image_path) are preserved. The
    original records are not mutated.
    """
    filtered = []
    for rec in records:
        new_rec = dict(rec)
        new_rec["boxes"] = [box for box in rec.get("boxes", []) if predicate(box)]
        filtered.append(new_rec)
    return filtered


def _normalize_held_out_token(value: str) -> str:
    return value.strip().lower().replace("_", "-")


def _component_is_test(part: str) -> bool:
    name = part.lower()
    if name == "test":
        return True
    if "." in name:
        stem = name.rsplit(".", 1)[0]
        if stem == "test":
            return True
    return False


def _component_is_held_out(part: str) -> bool:
    compact = part.lower().replace("_", "").replace("-", "")
    if "heldout" in compact:
        return True
    return _normalize_held_out_token(part) in {"held-out", "heldout"}


def path_is_held_out(path) -> bool:
    """True when a filesystem path names the held-out test split.

    A path component exactly named ``test`` (or a file stem ``test``) is
    refused. ``tests`` is not, so this package's own pytest fixtures remain
    usable. Any component containing held-out / heldout / held_out is refused.
    """
    from pathlib import Path

    for part in Path(path).parts:
        if _component_is_test(part) or _component_is_held_out(part):
            return True
    return False


def refuse_held_out_path(path) -> None:
    if path_is_held_out(path):
        raise HeldOutEvidenceError(
            f"Held-out test evidence is not allowed: {path}. "
            "Use train or val (aliases: validation, eval) only."
        )


def canonical_split(split: str) -> str:
    """Map an allowed split name to train/val. Held-out names always fail."""
    if split is None or str(split).strip() == "":
        raise HeldOutEvidenceError(
            "dataset split is required; allowed values are train, val "
            "(aliases: validation, eval). The held-out test split is not allowed."
        )
    key = str(split).strip().lower()
    compact = key.replace("_", "").replace("-", "")
    if key in {"test"} or compact in {"test", "heldout", "heldouttest"} or "heldout" in compact:
        raise HeldOutEvidenceError(
            "The held-out test split cannot be used. "
            "Use train or val (aliases: validation, eval)."
        )
    if key in SPLIT_ALIASES:
        return SPLIT_ALIASES[key]
    allowed = ", ".join(ALLOWED_SPLITS) + " (aliases: validation, eval)"
    raise ValueError(f"Unknown dataset split {split!r}. Allowed: {allowed}.")


def refuse_held_out_inputs(ground_truth_path, predictions_path, split: str) -> str:
    """Validate split and input paths. Returns the canonical split name."""
    canonical = canonical_split(split)
    refuse_held_out_path(ground_truth_path)
    refuse_held_out_path(predictions_path)
    return canonical


def assert_pixel_xyxy(ground_truth: List[dict], predictions: List[dict]) -> None:
    """Refuse inputs that look like normalized YOLO boxes, not pixel xyxy."""
    areas = []
    for records in (ground_truth, predictions):
        for rec in records:
            for box in rec.get("boxes", []):
                bbox = _box_bbox(box)
                if bbox is None:
                    continue
                area = bbox_area(bbox)
                if area > 0:
                    areas.append(area)
    if areas and max(areas) <= 1.0:
        raise ValueError(
            "All bounding-box areas are <= 1.0; geometry evaluation expects "
            "pixel xyxy coordinates because COCO size buckets are in pixel^2. "
            "Normalized YOLO boxes would all fall into the small bucket."
        )


def _canonical_box_class(box: dict, classes: Sequence[str]) -> Optional[str]:
    raw = box.get("class")
    if raw is None:
        return None
    canonical = canonicalize_class_name(raw)
    if canonical is None or canonical not in classes:
        return None
    return canonical


def _bucket_support(
    ground_truth: List[dict],
    classes: Sequence[str],
    size_thresholds: SizeThresholds,
    aspect_thresholds: AspectThresholds,
) -> dict:
    size_counts = {
        c: {bucket: 0 for bucket in SIZE_BUCKET_ORDER + ("invalid",)} for c in classes
    }
    aspect_counts = {
        c: {bucket: 0 for bucket in ASPECT_BUCKET_ORDER + ("invalid",)} for c in classes
    }
    for rec in ground_truth:
        for box in rec.get("boxes", []):
            cls = _canonical_box_class(box, classes)
            if cls is None:
                continue
            size_counts[cls][box_size_bucket(box, size_thresholds)] += 1
            aspect_counts[cls][box_aspect_bucket(box, aspect_thresholds)] += 1
    return {"size": size_counts, "aspect": aspect_counts}


def _metrics_view(result: dict) -> dict:
    return {
        "num_images": result["num_images"],
        "per_class": result["per_class"],
        "overall": result["overall"],
        "missed_hazards": result["missed_hazards"],
        "false_detections": result["false_detections"],
    }


def _class_metrics(result: dict, cls: str) -> dict:
    return dict(result["per_class"][cls])


def evaluate_by_geometry(
    ground_truth: List[dict],
    predictions: List[dict],
    *,
    split: str,
    classes: Optional[Sequence[str]] = None,
    iou_threshold: float = 0.5,
    size_thresholds: Optional[SizeThresholds] = None,
    aspect_thresholds: Optional[AspectThresholds] = None,
    strict: bool = True,
) -> dict:
    """Score detections overall and inside each size / aspect bucket.

    ``split`` is required. Held-out names (test, held-out, …) always raise
    HeldOutEvidenceError; there is no override flag.
    """
    canonical = canonical_split(split)
    classes = list(classes) if classes is not None else list(TAXONOMY_CLASSES)
    size_thresholds = size_thresholds if size_thresholds is not None else SizeThresholds()
    aspect_thresholds = (
        aspect_thresholds if aspect_thresholds is not None else AspectThresholds()
    )

    assert_pixel_xyxy(ground_truth, predictions)

    unstratified = evaluate(
        ground_truth,
        predictions,
        classes=classes,
        iou_threshold=iou_threshold,
        strict=strict,
    )

    by_size = {}
    for bucket in SIZE_BUCKET_ORDER:
        gt_b = filter_records(
            ground_truth, lambda box, b=bucket: box_size_bucket(box, size_thresholds) == b
        )
        pred_b = filter_records(
            predictions, lambda box, b=bucket: box_size_bucket(box, size_thresholds) == b
        )
        by_size[bucket] = _metrics_view(
            evaluate(
                gt_b,
                pred_b,
                classes=classes,
                iou_threshold=iou_threshold,
                strict=strict,
            )
        )

    by_aspect = {}
    for bucket in ASPECT_BUCKET_ORDER:
        gt_b = filter_records(
            ground_truth, lambda box, b=bucket: box_aspect_bucket(box, aspect_thresholds) == b
        )
        pred_b = filter_records(
            predictions, lambda box, b=bucket: box_aspect_bucket(box, aspect_thresholds) == b
        )
        by_aspect[bucket] = _metrics_view(
            evaluate(
                gt_b,
                pred_b,
                classes=classes,
                iou_threshold=iou_threshold,
                strict=strict,
            )
        )

    by_size_and_aspect = {cls: {} for cls in classes}
    for size_bucket in SIZE_BUCKET_ORDER:
        for aspect_bucket in ASPECT_BUCKET_ORDER:
            key = f"{size_bucket}|{aspect_bucket}"

            def _both(box, s=size_bucket, a=aspect_bucket):
                return (
                    box_size_bucket(box, size_thresholds) == s
                    and box_aspect_bucket(box, aspect_thresholds) == a
                )

            crossed = evaluate(
                filter_records(ground_truth, _both),
                filter_records(predictions, _both),
                classes=classes,
                iou_threshold=iou_threshold,
                strict=strict,
            )
            for cls in classes:
                by_size_and_aspect[cls][key] = _class_metrics(crossed, cls)

    return {
        "config": {
            "iou_threshold": iou_threshold,
            "classes": classes,
            "strict": strict,
            "dataset_split": canonical,
            "held_out_test_used": False,
            "coordinate_space": COORDINATE_SPACE,
            "size_buckets": size_thresholds.as_edges(),
            "aspect_buckets": aspect_thresholds.as_edges(),
        },
        "num_images": unstratified["num_images"],
        "unstratified": _metrics_view(unstratified),
        "by_size": by_size,
        "by_aspect": by_aspect,
        "by_size_and_aspect": by_size_and_aspect,
        "bucket_support": _bucket_support(
            ground_truth, classes, size_thresholds, aspect_thresholds
        ),
        "unknown_classes": unstratified["unknown_classes"],
        "unmatched_image_ids": unstratified["unmatched_image_ids"],
    }
