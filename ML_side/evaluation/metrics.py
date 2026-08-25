"""Turns ground truth + predictions into overall/per-class metrics,
a missed-hazards list, and a false-detections list.

Expected input format (same shape for both ground_truth and predictions):

    [
      {
        "image_id": "img001",
        "boxes": [
          {"class": "person", "bbox": [x_min, y_min, x_max, y_max]},
          ...
        ],
      },
      ...
    ]

Prediction boxes additionally carry a "score" (confidence) field.
Coordinates are plain floats/ints in a consistent unit (pixels or
normalised 0-1), the pipeline itself doesn't care which, as long as
ground truth and predictions use the same unit.

Class names are canonicalized through the navigation_semantics contract
(so recognized aliases like "office-chair" resolve to "chair"), and by
default a class that still doesn't resolve to an approved class is treated
as a hard error rather than silently dropped, since an unrecognized class
usually means a real model/taxonomy mismatch worth knowing about, not
noise to filter out. Pass strict=False to instead surface these in the
result as "unknown_classes" without failing.
"""

from collections import defaultdict
from typing import List, Optional, Sequence

from .matching import match_class_detections
from .taxonomy import (
    BaseSeverity,
    DEFAULT_SEVERITY,
    TAXONOMY_CLASSES,
    canonicalize_class_name,
    severity_rank,
)


class TaxonomyMismatchError(ValueError):
    """Raised when ground truth or predictions reference an unrecognized class."""


def _index_by_image_and_class(
    records: List[dict], classes: Sequence[str], all_classes: Sequence[str], source: str
):
    """Group boxes by image_id then class, registering every image_id even
    when it has zero (or zero in-taxonomy) boxes, and collecting any class
    name that doesn't canonicalize to an approved class instead of quietly
    dropping it.

    ``classes`` may be a subset of the full taxonomy (``all_classes``). A box
    whose class is a valid taxonomy class but simply isn't part of the
    requested subset is excluded from the index without being treated as
    unknown, only boxes that don't canonicalize to any approved class at all
    go into ``unknown``.
    """
    index: dict = defaultdict(lambda: defaultdict(list))
    unknown: List[dict] = []
    for rec in records:
        image_id = rec["image_id"]
        index[image_id]  # register the image even if it has no boxes at all
        for box in rec.get("boxes", []):
            raw_cls = box["class"]
            canonical = canonicalize_class_name(raw_cls)
            if canonical is None or canonical not in all_classes:
                unknown.append({"image_id": image_id, "source": source, "class": raw_cls})
                continue
            if canonical not in classes:
                continue  # valid taxonomy class, just outside the requested subset
            index[image_id][canonical].append(box)
    return index, unknown


def _precision_recall_f1(tp: int, fp: int, fn: int):
    precision = tp / (tp + fp) if (tp + fp) > 0 else None
    recall = tp / (tp + fn) if (tp + fn) > 0 else None
    if precision is None or recall is None or (precision + recall) == 0:
        f1 = None
    else:
        f1 = 2 * precision * recall / (precision + recall)
    return precision, recall, f1


def evaluate(
    ground_truth: List[dict],
    predictions: List[dict],
    classes: Optional[Sequence[str]] = None,
    iou_threshold: float = 0.5,
    severity_map: Optional[dict] = None,
    strict: bool = True,
) -> dict:
    """Run the full evaluation and return one deterministic result dict.

    Given the same ground_truth, predictions, classes and iou_threshold,
    this always returns the same result, there is no randomness and no
    dependence on dict/set iteration order (image ids and classes are
    always processed in a fixed, sorted order).

    strict=True (the default) raises TaxonomyMismatchError if any box in
    either input references a class that doesn't canonicalize to an
    approved class, this is meant to catch a real model/taxonomy mismatch
    rather than hide it. strict=False instead includes those occurrences
    in the result under "unknown_classes" and proceeds using only the
    recognized boxes.
    """
    classes = list(classes) if classes is not None else list(TAXONOMY_CLASSES)
    severity_map = severity_map if severity_map is not None else DEFAULT_SEVERITY

    gt_index, gt_unknown = _index_by_image_and_class(
        ground_truth, classes, TAXONOMY_CLASSES, "ground_truth"
    )
    pred_index, pred_unknown = _index_by_image_and_class(
        predictions, classes, TAXONOMY_CLASSES, "prediction"
    )
    unknown_classes = gt_unknown + pred_unknown
    unknown_classes.sort(key=lambda u: (u["image_id"], u["source"], str(u["class"])))

    if strict and unknown_classes:
        names = sorted({str(u["class"]) for u in unknown_classes})
        raise TaxonomyMismatchError(
            "Found box(es) with a class that isn't in the approved taxonomy: "
            f"{', '.join(names)}. Pass strict=False to surface these in the "
            "report instead of failing."
        )

    # Ground truth defines the evaluated set of images. A prediction given
    # for an image_id with no matching ground truth entry is almost always a
    # data problem (a typo'd or mismatched id), not a real result, including
    # it would fabricate false_detections against an image that was never
    # actually part of this evaluation. Those ids are excluded from scoring
    # and surfaced separately instead of silently treated as real data.
    gt_ids = set(gt_index)
    pred_ids = set(pred_index)
    predictions_without_ground_truth = sorted(pred_ids - gt_ids)
    image_ids = sorted(gt_ids)

    counts = {c: {"tp": 0, "fp": 0, "fn": 0, "support": 0} for c in classes}
    missed_hazards = []
    false_detections = []

    for image_id in image_ids:
        for cls in classes:
            gt_boxes = gt_index[image_id].get(cls, [])
            pred_boxes = pred_index[image_id].get(cls, [])
            counts[cls]["support"] += len(gt_boxes)

            matches, fp_idx, fn_idx = match_class_detections(gt_boxes, pred_boxes, iou_threshold)
            counts[cls]["tp"] += len(matches)
            counts[cls]["fp"] += len(fp_idx)
            counts[cls]["fn"] += len(fn_idx)

            for gi in fn_idx:
                gt = gt_boxes[gi]
                missed_hazards.append({
                    "image_id": image_id,
                    "class": cls,
                    "bbox": gt["bbox"],
                    "severity": severity_map.get(cls, "UNKNOWN"),
                })
            for pi in fp_idx:
                pred = pred_boxes[pi]
                false_detections.append({
                    "image_id": image_id,
                    "class": cls,
                    "bbox": pred["bbox"],
                    "score": pred["score"],
                })

    per_class = {}
    for c in classes:
        tp, fp, fn = counts[c]["tp"], counts[c]["fp"], counts[c]["fn"]
        precision, recall, f1 = _precision_recall_f1(tp, fp, fn)
        per_class[c] = {
            "tp": tp, "fp": fp, "fn": fn,
            "support": counts[c]["support"],
            "precision": precision, "recall": recall, "f1": f1,
        }

    micro_tp = sum(counts[c]["tp"] for c in classes)
    micro_fp = sum(counts[c]["fp"] for c in classes)
    micro_fn = sum(counts[c]["fn"] for c in classes)
    micro_p, micro_r, micro_f1 = _precision_recall_f1(micro_tp, micro_fp, micro_fn)

    classes_with_signal = [
        c for c in classes
        if counts[c]["support"] > 0 or (counts[c]["tp"] + counts[c]["fp"]) > 0
    ]
    if classes_with_signal:
        macro_p = sum(per_class[c]["precision"] or 0.0 for c in classes_with_signal) / len(classes_with_signal)
        macro_r = sum(per_class[c]["recall"] or 0.0 for c in classes_with_signal) / len(classes_with_signal)
        macro_f1 = sum(per_class[c]["f1"] or 0.0 for c in classes_with_signal) / len(classes_with_signal)
    else:
        macro_p = macro_r = macro_f1 = None

    def _severity_sort_key(severity_name: str) -> int:
        # severity_rank() returns higher numbers for more severe entries
        # (CRITICAL=4 ... LOW=1); negate so CRITICAL sorts first. Anything
        # that isn't a recognized BaseSeverity name (e.g. a caller-supplied
        # severity_map with a typo) sorts last instead of raising.
        try:
            return -severity_rank(BaseSeverity[severity_name])
        except KeyError:
            return 1

    missed_hazards.sort(key=lambda h: (_severity_sort_key(h["severity"]), h["image_id"], h["class"]))
    false_detections.sort(key=lambda d: (d["image_id"], d["class"]))

    return {
        "config": {"iou_threshold": iou_threshold, "classes": classes, "strict": strict},
        "num_images": len(image_ids),
        "per_class": per_class,
        "overall": {
            "micro": {"tp": micro_tp, "fp": micro_fp, "fn": micro_fn,
                      "precision": micro_p, "recall": micro_r, "f1": micro_f1},
            "macro": {"precision": macro_p, "recall": macro_r, "f1": macro_f1},
        },
        "missed_hazards": missed_hazards,
        "false_detections": false_detections,
        "unknown_classes": unknown_classes,
        "unmatched_image_ids": {
            "predictions_without_ground_truth": predictions_without_ground_truth,
        },
    }
