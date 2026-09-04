"""Box matching: turns raw ground truth + predictions into TP/FP/FN.

This is the core of the whole pipeline. Everything else (per-class metrics,
missed-hazard lists, false-detection lists) is built on top of the matches
produced here, so this module is kept small and heavily tested.
"""

from typing import Sequence, Tuple, List


def iou(box_a: Sequence[float], box_b: Sequence[float]) -> float:
    """Intersection-over-union for two [x_min, y_min, x_max, y_max] boxes."""
    xa1, ya1, xa2, ya2 = box_a
    xb1, yb1, xb2, yb2 = box_b

    inter_x1 = max(xa1, xb1)
    inter_y1 = max(ya1, yb1)
    inter_x2 = min(xa2, xb2)
    inter_y2 = min(ya2, yb2)

    inter_w = max(0.0, inter_x2 - inter_x1)
    inter_h = max(0.0, inter_y2 - inter_y1)
    inter_area = inter_w * inter_h

    area_a = max(0.0, xa2 - xa1) * max(0.0, ya2 - ya1)
    area_b = max(0.0, xb2 - xb1) * max(0.0, yb2 - yb1)
    union = area_a + area_b - inter_area

    if union <= 0:
        return 0.0
    return inter_area / union


def match_class_detections(
    gt_boxes: List[dict],
    pred_boxes: List[dict],
    iou_threshold: float = 0.5,
) -> Tuple[List[Tuple[int, int, float]], List[int], List[int]]:
    """Greedy IoU matching for a single class within a single image.

    gt_boxes: list of {"bbox": [x_min,y_min,x_max,y_max], ...}
    pred_boxes: list of {"bbox": [...], "score": float, ...}

    Predictions are matched in descending confidence order, each to the
    highest-IoU unmatched ground truth box at or above iou_threshold.
    Ties are broken by prediction index, so results are deterministic.

    Returns (matches, fp_indices, fn_indices):
      matches: list of (gt_index, pred_index, iou)
      fp_indices: pred indices with no acceptable match (false detections)
      fn_indices: gt indices never matched (missed hazards)

    Raises ValueError, with the offending index, if a ground truth box is
    missing "bbox" or a prediction box is missing "bbox" or "score", rather
    than letting a malformed box raise a raw KeyError partway through
    matching.
    """
    for gi, gt in enumerate(gt_boxes):
        if "bbox" not in gt:
            raise ValueError(f"Ground truth box at index {gi} is missing a 'bbox' field.")
    for pi, pred in enumerate(pred_boxes):
        if "bbox" not in pred:
            raise ValueError(f"Prediction box at index {pi} is missing a 'bbox' field.")
        if "score" not in pred:
            raise ValueError(
                f"Prediction box at index {pi} is missing a 'score' field, "
                "required to rank predictions by confidence before matching."
            )

    pred_order = sorted(
        range(len(pred_boxes)),
        key=lambda i: (-pred_boxes[i]["score"], i),
    )

    matched_gt = set()
    matches: List[Tuple[int, int, float]] = []
    fp_indices: List[int] = []

    for pi in pred_order:
        best_iou = 0.0
        best_gi = -1
        for gi, gt in enumerate(gt_boxes):
            if gi in matched_gt:
                continue
            cur_iou = iou(gt["bbox"], pred_boxes[pi]["bbox"])
            if cur_iou > best_iou:
                best_iou = cur_iou
                best_gi = gi
        if best_gi != -1 and best_iou >= iou_threshold:
            matched_gt.add(best_gi)
            matches.append((best_gi, pi, best_iou))
        else:
            fp_indices.append(pi)

    fn_indices = [gi for gi in range(len(gt_boxes)) if gi not in matched_gt]
    return matches, fp_indices, fn_indices
