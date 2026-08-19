import json
from pathlib import Path

import pytest

from evaluation.matching import iou, match_class_detections
from evaluation.metrics import evaluate
from evaluation.taxonomy import TAXONOMY_CLASSES

FIXTURE_DIR = Path(__file__).parent / "fixtures" / "eval"


def _load_fixtures():
    with open(FIXTURE_DIR / "ground_truth_small.json") as f:
        gt = json.load(f)
    with open(FIXTURE_DIR / "predictions_small.json") as f:
        preds = json.load(f)
    return gt, preds


# ---- iou() ----

def test_iou_identical_boxes_is_one():
    box = [10, 10, 50, 50]
    assert iou(box, box) == pytest.approx(1.0)


def test_iou_disjoint_boxes_is_zero():
    assert iou([0, 0, 10, 10], [20, 20, 30, 30]) == 0.0


def test_iou_known_overlap():
    # two 10x10 boxes overlapping in a 5x10 strip -> intersection 50,
    # union = 100 + 100 - 50 = 150, iou = 50/150
    a = [0, 0, 10, 10]
    b = [5, 0, 15, 10]
    assert iou(a, b) == pytest.approx(50 / 150)


# ---- match_class_detections() ----

def test_match_class_detections_simple_tp():
    gt = [{"bbox": [0, 0, 10, 10]}]
    preds = [{"bbox": [1, 1, 11, 11], "score": 0.9}]
    matches, fp, fn = match_class_detections(gt, preds, iou_threshold=0.5)
    assert len(matches) == 1
    assert fp == []
    assert fn == []


def test_match_class_detections_below_threshold_is_fp_and_fn():
    gt = [{"bbox": [0, 0, 10, 10]}]
    preds = [{"bbox": [8, 8, 18, 18], "score": 0.9}]  # low overlap
    matches, fp, fn = match_class_detections(gt, preds, iou_threshold=0.5)
    assert matches == []
    assert fp == [0]
    assert fn == [0]


def test_match_class_detections_prefers_higher_confidence_on_conflict():
    gt = [{"bbox": [0, 0, 10, 10]}]
    preds = [
        {"bbox": [0, 0, 10, 10], "score": 0.4},
        {"bbox": [0, 0, 10, 10], "score": 0.9},
    ]
    matches, fp, fn = match_class_detections(gt, preds, iou_threshold=0.5)
    assert len(matches) == 1
    matched_gi, matched_pi, _ = matches[0]
    assert matched_pi == 1  # the higher-confidence prediction wins the match
    assert fp == [0]
    assert fn == []


def test_match_class_detections_empty_inputs():
    matches, fp, fn = match_class_detections([], [], iou_threshold=0.5)
    assert (matches, fp, fn) == ([], [], [])


# ---- evaluate() on the small fixture ----

def test_evaluate_is_deterministic_across_runs():
    gt, preds = _load_fixtures()
    result_a = evaluate(gt, preds, classes=TAXONOMY_CLASSES, iou_threshold=0.5)
    result_b = evaluate(gt, preds, classes=TAXONOMY_CLASSES, iou_threshold=0.5)
    assert result_a == result_b


def test_evaluate_per_class_counts_match_expected_design():
    gt, preds = _load_fixtures()
    result = evaluate(gt, preds, classes=TAXONOMY_CLASSES, iou_threshold=0.5)
    per_class = result["per_class"]

    # TP classes: person, door, table, pole
    for cls in ("person", "door", "table", "pole"):
        assert per_class[cls]["tp"] == 1
        assert per_class[cls]["fp"] == 0
        assert per_class[cls]["fn"] == 0
        assert per_class[cls]["precision"] == pytest.approx(1.0)
        assert per_class[cls]["recall"] == pytest.approx(1.0)
        assert per_class[cls]["f1"] == pytest.approx(1.0)

    # FN classes (missed hazards): stairs, vehicle
    for cls in ("stairs", "vehicle"):
        assert per_class[cls]["tp"] == 0
        assert per_class[cls]["fn"] == 1
        assert per_class[cls]["precision"] is None
        assert per_class[cls]["recall"] == pytest.approx(0.0)

    # FP-only classes with zero ground-truth support: chair, bicycle
    for cls in ("chair", "bicycle"):
        assert per_class[cls]["support"] == 0
        assert per_class[cls]["fp"] == 1
        assert per_class[cls]["precision"] == pytest.approx(0.0)
        assert per_class[cls]["recall"] is None


def test_evaluate_overall_micro_and_macro():
    gt, preds = _load_fixtures()
    result = evaluate(gt, preds, classes=TAXONOMY_CLASSES, iou_threshold=0.5)
    micro = result["overall"]["micro"]
    macro = result["overall"]["macro"]

    assert micro["tp"] == 4
    assert micro["fp"] == 2
    assert micro["fn"] == 2
    assert micro["precision"] == pytest.approx(4 / 6)
    assert micro["recall"] == pytest.approx(4 / 6)

    assert macro["precision"] == pytest.approx(0.5)
    assert macro["recall"] == pytest.approx(0.5)
    assert macro["f1"] == pytest.approx(0.5)


def test_evaluate_missed_hazards_flags_correct_boxes_and_severity():
    gt, preds = _load_fixtures()
    result = evaluate(gt, preds, classes=TAXONOMY_CLASSES, iou_threshold=0.5)
    missed = result["missed_hazards"]

    assert len(missed) == 2
    classes_missed = {h["class"] for h in missed}
    assert classes_missed == {"stairs", "vehicle"}
    # both are CRITICAL under the proposed severity map, and CRITICAL should sort first
    assert all(h["severity"] == "CRITICAL" for h in missed)
    assert missed[0]["image_id"] == "img001"  # stairs, sorted before vehicle by image_id
    assert missed[1]["image_id"] == "img002"


def test_evaluate_false_detections_flags_correct_boxes():
    gt, preds = _load_fixtures()
    result = evaluate(gt, preds, classes=TAXONOMY_CLASSES, iou_threshold=0.5)
    false_dets = result["false_detections"]

    assert len(false_dets) == 2
    classes_flagged = {d["class"] for d in false_dets}
    assert classes_flagged == {"chair", "bicycle"}
    for d in false_dets:
        assert "score" in d and 0.0 <= d["score"] <= 1.0


def test_evaluate_handles_no_ground_truth_or_predictions():
    result = evaluate([], [], classes=TAXONOMY_CLASSES, iou_threshold=0.5)
    assert result["num_images"] == 0
    assert result["missed_hazards"] == []
    assert result["false_detections"] == []
    for cls in TAXONOMY_CLASSES:
        assert result["per_class"][cls]["support"] == 0


def test_evaluate_ignores_out_of_taxonomy_classes():
    gt = [{"image_id": "imgX", "boxes": [{"class": "unknown_thing", "bbox": [0, 0, 5, 5]}]}]
    preds = [{"image_id": "imgX", "boxes": [{"class": "unknown_thing", "bbox": [0, 0, 5, 5], "score": 0.9}]}]
    result = evaluate(gt, preds, classes=TAXONOMY_CLASSES, iou_threshold=0.5)
    assert "unknown_thing" not in result["per_class"]
    assert result["missed_hazards"] == []
    assert result["false_detections"] == []
