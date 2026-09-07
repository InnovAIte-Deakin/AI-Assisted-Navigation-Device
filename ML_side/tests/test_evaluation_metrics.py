import json
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))  # ML_side, so `evaluation` is importable

from evaluation.matching import iou, match_class_detections
from evaluation.metrics import TaxonomyMismatchError, evaluate
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


def test_match_class_detections_missing_bbox_raises_value_error():
    with pytest.raises(ValueError, match="bbox"):
        match_class_detections([{"not_bbox": []}], [], iou_threshold=0.5)
    with pytest.raises(ValueError, match="bbox"):
        match_class_detections([], [{"not_bbox": [], "score": 0.9}], iou_threshold=0.5)


def test_match_class_detections_missing_score_raises_value_error():
    # a bbox with no score can't be ranked by confidence, this should raise
    # a clear ValueError rather than a raw KeyError partway through matching
    with pytest.raises(ValueError, match="score"):
        match_class_detections([], [{"bbox": [0, 0, 1, 1]}], iou_threshold=0.5)


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


def test_evaluate_num_images_counts_images_with_zero_boxes():
    # An image with zero ground-truth boxes and zero predictions must
    # still be counted, not silently dropped, since it is a legitimate
    # "nothing to detect here" case, not a missing image. Uses its own
    # small input rather than the shared fixture, since that fixture does
    # not include a zero-box image.
    gt = [
        {"image_id": "img001", "boxes": [{"class": "person", "bbox": [0, 0, 10, 10]}]},
        {"image_id": "img002", "boxes": []},
    ]
    preds = [
        {"image_id": "img001", "boxes": [{"class": "person", "bbox": [1, 1, 11, 11], "score": 0.9}]},
    ]
    result = evaluate(gt, preds, classes=TAXONOMY_CLASSES, iou_threshold=0.5)
    assert result["num_images"] == 2


def test_evaluate_raises_on_unknown_class_by_default():
    gt = [{"image_id": "imgX", "boxes": [{"class": "unknown_thing", "bbox": [0, 0, 5, 5]}]}]
    preds = [{"image_id": "imgX", "boxes": [{"class": "unknown_thing", "bbox": [0, 0, 5, 5], "score": 0.9}]}]
    with pytest.raises(TaxonomyMismatchError, match="unknown_thing"):
        evaluate(gt, preds, classes=TAXONOMY_CLASSES, iou_threshold=0.5)


def test_evaluate_strict_false_surfaces_unknown_classes_instead_of_raising():
    gt = [{"image_id": "imgX", "boxes": [{"class": "unknown_thing", "bbox": [0, 0, 5, 5]}]}]
    preds = [{"image_id": "imgX", "boxes": [{"class": "unknown_thing", "bbox": [0, 0, 5, 5], "score": 0.9}]}]
    result = evaluate(gt, preds, classes=TAXONOMY_CLASSES, iou_threshold=0.5, strict=False)
    assert "unknown_thing" not in result["per_class"]
    assert result["missed_hazards"] == []
    assert result["false_detections"] == []
    assert len(result["unknown_classes"]) == 2  # one from ground truth, one from predictions
    sources = {u["source"] for u in result["unknown_classes"]}
    assert sources == {"ground_truth", "prediction"}


def test_evaluate_canonicalizes_known_alias():
    # "office-chair" is a documented alias for "chair" in the navigation
    # semantics contract, it should match against a plain "chair" box
    # rather than being treated as a separate/unknown class.
    gt = [{"image_id": "imgX", "boxes": [{"class": "chair", "bbox": [0, 0, 10, 10]}]}]
    preds = [{"image_id": "imgX", "boxes": [{"class": "office-chair", "bbox": [1, 1, 11, 11], "score": 0.9}]}]
    result = evaluate(gt, preds, classes=TAXONOMY_CLASSES, iou_threshold=0.5)
    assert result["unknown_classes"] == []
    assert result["per_class"]["chair"]["tp"] == 1


def test_evaluate_classes_subset_excludes_other_taxonomy_classes_without_erroring():
    # "door" is a valid taxonomy class but isn't part of the requested
    # subset here. It must be excluded from scoring, not treated as
    # unknown, previously this raised TaxonomyMismatchError under
    # strict=True even though "door" is a perfectly valid class overall.
    gt = [{"image_id": "imgX", "boxes": [
        {"class": "person", "bbox": [0, 0, 10, 10]},
        {"class": "door", "bbox": [20, 20, 30, 30]},
    ]}]
    preds = [{"image_id": "imgX", "boxes": [
        {"class": "person", "bbox": [1, 1, 11, 11], "score": 0.9},
    ]}]
    result = evaluate(gt, preds, classes=["person"], iou_threshold=0.5, strict=True)
    assert result["unknown_classes"] == []
    assert "door" not in result["per_class"]
    assert result["per_class"]["person"]["tp"] == 1


def test_evaluate_prediction_only_image_id_is_surfaced_not_fabricated():
    # A prediction for an image_id absent from ground truth (typo'd or
    # mismatched id) must not be scored as a false detection against an
    # image that was never actually part of this evaluation, it should be
    # excluded and surfaced separately instead.
    gt = [{"image_id": "img001", "boxes": [{"class": "person", "bbox": [0, 0, 10, 10]}]}]
    preds = [
        {"image_id": "img001", "boxes": [{"class": "person", "bbox": [1, 1, 11, 11], "score": 0.9}]},
        {"image_id": "img999", "boxes": [{"class": "person", "bbox": [0, 0, 10, 10], "score": 0.9}]},
    ]
    result = evaluate(gt, preds, classes=TAXONOMY_CLASSES, iou_threshold=0.5)
    assert result["num_images"] == 1  # only the ground-truth image is scored
    assert result["unmatched_image_ids"]["predictions_without_ground_truth"] == ["img999"]
    assert result["false_detections"] == []  # img999's prediction isn't fabricated as an FP
    assert result["overall"]["micro"]["fp"] == 0
