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
"""

from collections import defaultdict
from typing import List, Optional, Sequence

from .matching import match_class_detections
from .taxonomy import DEFAULT_SEVERITY, TAXONOMY_CLASSES

_SEVERITY_ORDER = {"CRITICAL": 0, "HIGH": 1, "MEDIUM": 2, "LOW": 3, "UNKNOWN": 4}


def _index_by_image_and_class(records: List[dict], classes: Sequence[str]) -> dict:
    index: dict = defaultdict(lambda: defaultdict(list))
    for rec in records:
        image_id = rec["image_id"]
        for box in rec.get("boxes", []):
            cls = box["class"]
            if cls not in classes:
                continue
            index[image_id][cls].append(box)
    return index


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
) -> dict:
    """Run the full evaluation and return one deterministic result dict.

    Given the same ground_truth, predictions, classes and iou_threshold,
    this always returns the same result, there is no randomness and no
    dependence on dict/set iteration order (image ids and classes are
    always processed in a fixed, sorted order).
    """
    classes = list(classes) if classes is not None else list(TAXONOMY_CLASSES)
    severity_map = severity_map if severity_map is not None else DEFAULT_SEVERITY

    gt_index = _index_by_image_and_class(ground_truth, classes)
    pred_index = _index_by_image_and_class(predictions, classes)
    image_ids = sorted(set(gt_index) | set(pred_index))

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

    missed_hazards.sort(key=lambda h: (_SEVERITY_ORDER.get(h["severity"], 9), h["image_id"], h["class"]))
    false_detections.sort(key=lambda d: (d["image_id"], d["class"]))

    return {
        "config": {"iou_threshold": iou_threshold, "classes": classes},
        "num_images": len(image_ids),
        "per_class": per_class,
        "overall": {
            "micro": {"tp": micro_tp, "fp": micro_fp, "fn": micro_fn,
                      "precision": micro_p, "recall": micro_r, "f1": micro_f1},
            "macro": {"precision": macro_p, "recall": macro_r, "f1": macro_f1},
        },
        "missed_hazards": missed_hazards,
        "false_detections": false_detections,
    }
