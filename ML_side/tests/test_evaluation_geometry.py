import csv
import json
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))  # ML_side, so `evaluation` is importable

from evaluation.geometry import (
    DEFAULT_MEDIUM_AREA_MAX,
    DEFAULT_SMALL_AREA_MAX,
    AspectThresholds,
    HeldOutEvidenceError,
    SizeThresholds,
    aspect_bucket_for_hw,
    bbox_area,
    bbox_aspect_hw,
    box_aspect_bucket,
    box_size_bucket,
    canonical_split,
    evaluate_by_geometry,
    filter_records,
    path_is_held_out,
    refuse_held_out_inputs,
    refuse_held_out_path,
    size_bucket_for_area,
)
from evaluation.geometry_report import (
    build_csv_rows,
    build_json_report,
    build_markdown_report,
)
from evaluation.metrics import evaluate
from evaluation.run_geometry_eval import run
from evaluation.taxonomy import TAXONOMY_CLASSES

FIXTURE_DIR = Path(__file__).parent / "fixtures" / "eval" / "geometry"
GT_PATH = FIXTURE_DIR / "ground_truth.json"
PRED_PATH = FIXTURE_DIR / "predictions.json"
SMALL_GT_PATH = Path(__file__).parent / "fixtures" / "eval" / "ground_truth_small.json"
SMALL_PRED_PATH = Path(__file__).parent / "fixtures" / "eval" / "predictions_small.json"


def _load_geometry_fixtures():
    with open(GT_PATH) as f:
        gt = json.load(f)
    with open(PRED_PATH) as f:
        preds = json.load(f)
    return gt, preds


# ---- unit: area / aspect / buckets ----

def test_bbox_area_and_aspect_of_known_boxes():
    assert bbox_area([0, 0, 10, 10]) == pytest.approx(100)
    assert bbox_aspect_hw([0, 0, 10, 10]) == pytest.approx(1.0)
    assert bbox_area([10, 10, 30, 210]) == pytest.approx(4000)
    assert bbox_aspect_hw([10, 10, 30, 210]) == pytest.approx(10.0)
    assert bbox_area([0, 0, 200, 80]) == pytest.approx(16000)
    assert bbox_aspect_hw([0, 0, 200, 80]) == pytest.approx(0.4)
    assert bbox_area([0, 0, 0, 10]) == 0.0
    assert bbox_aspect_hw([0, 0, 0, 10]) is None


def test_coco_size_bucket_boundaries():
    thresholds = SizeThresholds()
    assert thresholds.small_max == DEFAULT_SMALL_AREA_MAX
    assert thresholds.medium_max == DEFAULT_MEDIUM_AREA_MAX
    assert size_bucket_for_area(0, thresholds) == "invalid"
    assert size_bucket_for_area(1023, thresholds) == "small"
    assert size_bucket_for_area(1024, thresholds) == "medium"
    assert size_bucket_for_area(9215, thresholds) == "medium"
    assert size_bucket_for_area(9216, thresholds) == "large"


def test_aspect_bucket_boundaries():
    thresholds = AspectThresholds()
    assert aspect_bucket_for_hw(None, thresholds) == "invalid"
    assert aspect_bucket_for_hw(3.0, thresholds) == "tall_thin"
    assert aspect_bucket_for_hw(2.999, thresholds) == "tall"
    assert aspect_bucket_for_hw(1.5, thresholds) == "tall"
    assert aspect_bucket_for_hw(1.499, thresholds) == "square_ish"
    assert aspect_bucket_for_hw(2.0 / 3.0, thresholds) == "square_ish"
    assert aspect_bucket_for_hw((2.0 / 3.0) - 1e-9, thresholds) == "wide"


def test_size_thresholds_are_configurable():
    tight = SizeThresholds(small_max=50, medium_max=200)
    assert size_bucket_for_area(49, tight) == "small"
    assert size_bucket_for_area(50, tight) == "medium"
    assert size_bucket_for_area(200, tight) == "large"


def test_filter_records_keeps_image_ids_and_extra_fields():
    records = [
        {
            "image_id": "imgA",
            "image_path": "/tmp/imgA.jpg",
            "boxes": [
                {"class": "pole", "bbox": [0, 0, 10, 10]},
                {"class": "pole", "bbox": [0, 0, 40, 400]},
            ],
        },
        {"image_id": "imgB", "boxes": []},
    ]
    thresholds = SizeThresholds()
    filtered = filter_records(
        records, lambda box: box_size_bucket(box, thresholds) == "small"
    )
    assert [rec["image_id"] for rec in filtered] == ["imgA", "imgB"]
    assert filtered[0]["image_path"] == "/tmp/imgA.jpg"
    assert len(filtered[0]["boxes"]) == 1
    assert filtered[0]["boxes"][0]["bbox"] == [0, 0, 10, 10]
    assert filtered[1]["boxes"] == []
    assert len(records[0]["boxes"]) == 2  # original not mutated


# ---- split / held-out guard ----

def test_canonical_split_aliases_and_required():
    assert canonical_split("train") == "train"
    assert canonical_split("val") == "val"
    assert canonical_split("validation") == "val"
    assert canonical_split("eval") == "val"
    assert canonical_split("VAL") == "val"
    with pytest.raises(HeldOutEvidenceError, match="required"):
        canonical_split("")
    with pytest.raises(HeldOutEvidenceError, match="required"):
        canonical_split(None)
    with pytest.raises(ValueError, match="Unknown dataset split"):
        canonical_split("holdout")


@pytest.mark.parametrize("split", ["test", "TEST", "heldout", "held-out", "held_out", "held-out-test"])
def test_canonical_split_refuses_held_out_names(split):
    with pytest.raises(HeldOutEvidenceError, match="held-out"):
        canonical_split(split)


def test_path_is_held_out_distinguishes_tests_from_test():
    assert path_is_held_out("dataset/test/labels.json") is True
    assert path_is_held_out("dataset/test.json") is True
    assert path_is_held_out("walkbuddy-heldout-dataset.json") is True
    assert path_is_held_out("candidates/foo-heldout-test-corrected/summary.json") is True
    assert path_is_held_out(GT_PATH) is False
    assert path_is_held_out("tests/fixtures/eval/geometry/ground_truth.json") is False


def test_refuse_held_out_path_and_inputs():
    with pytest.raises(HeldOutEvidenceError):
        refuse_held_out_path("data/held-out/gt.json")
    with pytest.raises(HeldOutEvidenceError):
        refuse_held_out_inputs("data/test/gt.json", "data/val/preds.json", "val")
    with pytest.raises(HeldOutEvidenceError):
        refuse_held_out_inputs(GT_PATH, PRED_PATH, "test")
    assert refuse_held_out_inputs(GT_PATH, PRED_PATH, "validation") == "val"


def test_evaluate_by_geometry_requires_split_and_records_held_out_false():
    gt, preds = _load_geometry_fixtures()
    with pytest.raises(TypeError):
        evaluate_by_geometry(gt, preds)
    result = evaluate_by_geometry(gt, preds, split="val")
    assert result["config"]["held_out_test_used"] is False
    assert result["config"]["dataset_split"] == "val"


def test_evaluate_by_geometry_refuses_test_split():
    gt, preds = _load_geometry_fixtures()
    with pytest.raises(HeldOutEvidenceError):
        evaluate_by_geometry(gt, preds, split="test")


def test_normalized_boxes_are_rejected():
    gt = [{"image_id": "n", "boxes": [{"class": "pole", "bbox": [0.1, 0.1, 0.2, 0.4]}]}]
    preds = [{"image_id": "n", "boxes": [{"class": "pole", "bbox": [0.1, 0.1, 0.2, 0.4], "score": 0.9}]}]
    with pytest.raises(ValueError, match="pixel xyxy"):
        evaluate_by_geometry(gt, preds, split="val")


# ---- fixture geometry assignments ----

def test_geometry_fixture_bucket_assignments():
    thresholds_s = SizeThresholds()
    thresholds_a = AspectThresholds()
    gt, preds = _load_geometry_fixtures()
    by_id = {rec["image_id"]: rec["boxes"][0] for rec in gt}

    assert box_size_bucket(by_id["img_small_square_pole"], thresholds_s) == "small"
    assert box_aspect_bucket(by_id["img_small_square_pole"], thresholds_a) == "square_ish"

    assert box_size_bucket(by_id["img_medium_tall_thin_pole"], thresholds_s) == "medium"
    assert box_aspect_bucket(by_id["img_medium_tall_thin_pole"], thresholds_a) == "tall_thin"

    assert box_size_bucket(by_id["img_large_wide_table"], thresholds_s) == "large"
    assert box_aspect_bucket(by_id["img_large_wide_table"], thresholds_a) == "wide"

    assert box_size_bucket(by_id["img_cross_size_pole"], thresholds_s) == "small"
    assert box_aspect_bucket(by_id["img_cross_size_pole"], thresholds_a) == "square_ish"
    cross_pred = [rec for rec in preds if rec["image_id"] == "img_cross_size_pole"][0]["boxes"][0]
    assert box_size_bucket(cross_pred, thresholds_s) == "medium"
    assert box_aspect_bucket(cross_pred, thresholds_a) == "square_ish"

    assert box_size_bucket(by_id["img_large_tall_thin_pole"], thresholds_s) == "large"
    assert box_aspect_bucket(by_id["img_large_tall_thin_pole"], thresholds_a) == "tall_thin"

    assert box_size_bucket(by_id["img_medium_wide_pole"], thresholds_s) == "medium"
    assert box_aspect_bucket(by_id["img_medium_wide_pole"], thresholds_a) == "wide"


# ---- evaluate_by_geometry scoring ----

def test_evaluate_by_geometry_is_deterministic():
    gt, preds = _load_geometry_fixtures()
    a = evaluate_by_geometry(gt, preds, split="val", classes=TAXONOMY_CLASSES, iou_threshold=0.5)
    b = evaluate_by_geometry(gt, preds, split="val", classes=TAXONOMY_CLASSES, iou_threshold=0.5)
    assert a == b


def test_unstratified_matches_plain_evaluate():
    gt, preds = _load_geometry_fixtures()
    plain = evaluate(gt, preds, classes=TAXONOMY_CLASSES, iou_threshold=0.5)
    geo = evaluate_by_geometry(gt, preds, split="train", classes=TAXONOMY_CLASSES, iou_threshold=0.5)
    assert geo["unstratified"]["per_class"] == plain["per_class"]
    assert geo["unstratified"]["overall"] == plain["overall"]
    assert geo["num_images"] == 6
    # Unstratified, the cross-size pair still matches (IoU 0.5625), so pole is 5 TPs.
    assert geo["unstratified"]["per_class"]["pole"]["tp"] == 5
    assert geo["unstratified"]["per_class"]["pole"]["fp"] == 0
    assert geo["unstratified"]["per_class"]["pole"]["fn"] == 0
    assert geo["unstratified"]["per_class"]["table"]["tp"] == 1


def test_size_breakdown_for_pole_and_table():
    gt, preds = _load_geometry_fixtures()
    result = evaluate_by_geometry(gt, preds, split="val", classes=TAXONOMY_CLASSES)

    pole_small = result["by_size"]["small"]["per_class"]["pole"]
    assert pole_small["support"] == 2  # 10x10 and 30x30
    assert pole_small["tp"] == 1
    assert pole_small["fn"] == 1  # 30x30 GT, prediction landed in medium
    assert pole_small["fp"] == 0
    assert pole_small["precision"] == pytest.approx(1.0)
    assert pole_small["recall"] == pytest.approx(0.5)

    pole_medium = result["by_size"]["medium"]["per_class"]["pole"]
    assert pole_medium["support"] == 2  # 20x200 and 200x40
    assert pole_medium["tp"] == 2
    assert pole_medium["fp"] == 1  # 40x40 prediction from the cross-size image
    assert pole_medium["fn"] == 0
    assert pole_medium["precision"] == pytest.approx(2 / 3)
    assert pole_medium["recall"] == pytest.approx(1.0)

    pole_large = result["by_size"]["large"]["per_class"]["pole"]
    assert pole_large["support"] == 1
    assert pole_large["tp"] == 1
    assert pole_large["fp"] == 0
    assert pole_large["fn"] == 0

    table_large = result["by_size"]["large"]["per_class"]["table"]
    assert table_large["support"] == 1
    assert table_large["tp"] == 1
    assert result["by_size"]["small"]["per_class"]["table"]["support"] == 0


def test_aspect_breakdown_including_empty_tall_bucket():
    gt, preds = _load_geometry_fixtures()
    result = evaluate_by_geometry(gt, preds, split="val", classes=TAXONOMY_CLASSES)

    pole_thin = result["by_aspect"]["tall_thin"]["per_class"]["pole"]
    assert pole_thin["support"] == 2
    assert pole_thin["tp"] == 2
    assert pole_thin["fp"] == 0
    assert pole_thin["fn"] == 0

    pole_square = result["by_aspect"]["square_ish"]["per_class"]["pole"]
    # Both the 10x10 pair and the 30x30 vs 40x40 pair are square_ish, and the
    # latter still matches on IoU when aspect (not size) is the slice.
    assert pole_square["support"] == 2
    assert pole_square["tp"] == 2
    assert pole_square["fp"] == 0
    assert pole_square["fn"] == 0

    pole_wide = result["by_aspect"]["wide"]["per_class"]["pole"]
    assert pole_wide["support"] == 1
    assert pole_wide["tp"] == 1

    pole_tall = result["by_aspect"]["tall"]["per_class"]["pole"]
    assert pole_tall["support"] == 0
    assert pole_tall["tp"] == 0
    assert pole_tall["fp"] == 0
    assert pole_tall["fn"] == 0
    assert pole_tall["precision"] is None
    assert pole_tall["recall"] is None
    assert pole_tall["f1"] is None

    table_wide = result["by_aspect"]["wide"]["per_class"]["table"]
    assert table_wide["support"] == 1
    assert table_wide["tp"] == 1


def test_cross_size_pair_is_fn_and_fp_under_independent_filtering():
    """The 30x30 GT / 40x40 pred pair is a TP unstratified (IoU 0.5625) but
    splits into FN(small) + FP(medium) when size-filtered independently."""
    gt = [{"image_id": "cross", "boxes": [{"class": "pole", "bbox": [0, 0, 30, 30]}]}]
    preds = [{"image_id": "cross", "boxes": [{"class": "pole", "bbox": [0, 0, 40, 40], "score": 0.8}]}]
    result = evaluate_by_geometry(gt, preds, split="val", classes=["pole"])
    assert result["unstratified"]["per_class"]["pole"]["tp"] == 1
    assert result["by_size"]["small"]["per_class"]["pole"]["fn"] == 1
    assert result["by_size"]["small"]["per_class"]["pole"]["tp"] == 0
    assert result["by_size"]["medium"]["per_class"]["pole"]["fp"] == 1
    assert result["by_size"]["medium"]["per_class"]["pole"]["tp"] == 0
    assert result["by_size"]["large"]["per_class"]["pole"]["support"] == 0


def test_classes_pole_excludes_other_taxonomy_classes():
    gt, preds = _load_geometry_fixtures()
    result = evaluate_by_geometry(gt, preds, split="val", classes=["pole"])
    assert list(result["unstratified"]["per_class"]) == ["pole"]
    assert "table" not in result["by_size"]["large"]["per_class"]
    assert "table" not in result["by_size_and_aspect"]
    assert result["unstratified"]["per_class"]["pole"]["tp"] == 5


def test_size_and_aspect_cross_tab_for_pole():
    gt, preds = _load_geometry_fixtures()
    result = evaluate_by_geometry(gt, preds, split="val", classes=["pole"])
    crossed = result["by_size_and_aspect"]["pole"]
    assert crossed["small|square_ish"]["support"] == 2
    assert crossed["small|square_ish"]["tp"] == 1
    assert crossed["small|square_ish"]["fn"] == 1
    assert crossed["medium|tall_thin"]["tp"] == 1
    assert crossed["medium|wide"]["tp"] == 1
    assert crossed["large|tall_thin"]["tp"] == 1
    assert crossed["small|tall_thin"]["support"] == 0
    assert crossed["small|tall_thin"]["precision"] is None


def test_bucket_support_counts_ground_truth_only():
    gt, preds = _load_geometry_fixtures()
    result = evaluate_by_geometry(gt, preds, split="val", classes=TAXONOMY_CLASSES)
    pole_size = result["bucket_support"]["size"]["pole"]
    assert pole_size["small"] == 2
    assert pole_size["medium"] == 2
    assert pole_size["large"] == 1
    assert pole_size["invalid"] == 0
    pole_aspect = result["bucket_support"]["aspect"]["pole"]
    assert pole_aspect["tall_thin"] == 2
    assert pole_aspect["tall"] == 0
    assert pole_aspect["square_ish"] == 2
    assert pole_aspect["wide"] == 1


def test_existing_eval_fixture_pole_is_medium_tall_thin():
    with open(SMALL_GT_PATH) as f:
        gt = json.load(f)
    with open(SMALL_PRED_PATH) as f:
        preds = json.load(f)
    result = evaluate_by_geometry(gt, preds, split="val", classes=TAXONOMY_CLASSES)
    pole_box = [b for rec in gt for b in rec["boxes"] if b["class"] == "pole"][0]
    assert box_size_bucket(pole_box, SizeThresholds()) == "medium"
    assert box_aspect_bucket(pole_box, AspectThresholds()) == "tall_thin"
    assert result["by_size"]["medium"]["per_class"]["pole"]["tp"] == 1
    assert result["by_aspect"]["tall_thin"]["per_class"]["pole"]["tp"] == 1


# ---- reports ----

def test_json_report_records_guard_metadata_and_is_deterministic():
    gt, preds = _load_geometry_fixtures()
    result = evaluate_by_geometry(gt, preds, split="eval", classes=TAXONOMY_CLASSES)
    report_a = build_json_report(result, extra_meta={"model_name": "mock"})
    report_b = build_json_report(result, extra_meta={"model_name": "mock"})
    assert report_a == report_b
    assert report_a["meta"]["artifact_type"] == "geometry_breakdown"
    assert report_a["meta"]["dataset_split"] == "val"
    assert report_a["meta"]["held_out_test_used"] is False
    assert report_a["meta"]["coordinate_space"] == "pixel_xyxy"
    assert report_a["meta"]["size_buckets"]["small"] == [0, 1024]
    assert report_a["meta"]["size_buckets"]["medium"] == [1024, 9216]
    assert report_a["meta"]["size_buckets"]["large"] == [9216, None]
    assert "generated_at" not in report_a["meta"]


def test_csv_rows_cover_each_dimension_bucket_class():
    gt, preds = _load_geometry_fixtures()
    result = evaluate_by_geometry(gt, preds, split="val", classes=["pole", "table"])
    report = build_json_report(result)
    rows = build_csv_rows(report)
    # 2 classes * (1 unstratified + 3 size + 4 aspect + 12 size_and_aspect) = 40
    assert len(rows) == 2 * (1 + 3 + 4 + 12)
    pole_small = [
        row for row in rows if row["dimension"] == "size" and row["bucket"] == "small" and row["class"] == "pole"
    ][0]
    assert pole_small["support"] == 2
    assert pole_small["tp"] == 1
    assert pole_small["fn"] == 1
    empty = [
        row
        for row in rows
        if row["dimension"] == "aspect" and row["bucket"] == "tall" and row["class"] == "pole"
    ][0]
    assert empty["precision"] == ""
    assert empty["recall"] == ""


def test_markdown_leads_with_pole_focus_and_notes_independent_filtering():
    gt, preds = _load_geometry_fixtures()
    result = evaluate_by_geometry(gt, preds, split="val", classes=TAXONOMY_CLASSES)
    report = build_json_report(result, extra_meta={"model_name": "mock"})
    md = build_markdown_report(report, model_name="mock")
    assert md.index("## Pole focus") < md.index("## By object size")
    assert "Pole — by object size" in md
    assert "Pole — by aspect ratio" in md
    assert "Pole — by size × aspect" in md
    assert "independently" in md
    assert "Held-out test used: False" in md
    assert "tall_thin" in md


def test_markdown_omits_pole_focus_when_pole_not_requested():
    gt, preds = _load_geometry_fixtures()
    result = evaluate_by_geometry(gt, preds, split="val", classes=["table"])
    report = build_json_report(result)
    md = build_markdown_report(report, model_name="table only")
    assert "## Pole focus" not in md
    assert "### table" in md or "| table |" in md


# ---- CLI ----

def test_run_writes_json_csv_and_markdown(tmp_path):
    out_dir = tmp_path / "geo"
    report = run(
        ground_truth_path=GT_PATH,
        predictions_path=PRED_PATH,
        out_dir=out_dir,
        split="val",
        model_name="mock (dev fixture)",
        deterministic_timestamp=True,
    )
    json_path = out_dir / "geometry_eval_report.json"
    csv_path = out_dir / "geometry_eval_report.csv"
    md_path = out_dir / "geometry_eval_report.md"
    assert json_path.exists()
    assert csv_path.exists()
    assert md_path.exists()
    with open(json_path) as f:
        saved = json.load(f)
    assert saved == report
    assert saved["meta"]["held_out_test_used"] is False
    with open(csv_path, newline="") as f:
        rows = list(csv.DictReader(f))
    assert rows[0]["dimension"] == "unstratified"
    md = md_path.read_text(encoding="utf-8")
    assert "## Pole focus" in md
    assert "≥" in md


def test_run_is_deterministic_across_repeated_calls(tmp_path):
    report_a = run(
        ground_truth_path=GT_PATH,
        predictions_path=PRED_PATH,
        out_dir=tmp_path / "a",
        split="val",
        deterministic_timestamp=True,
    )
    report_b = run(
        ground_truth_path=GT_PATH,
        predictions_path=PRED_PATH,
        out_dir=tmp_path / "b",
        split="val",
        deterministic_timestamp=True,
    )
    assert report_a == report_b


def test_run_classes_pole_only(tmp_path):
    report = run(
        ground_truth_path=GT_PATH,
        predictions_path=PRED_PATH,
        out_dir=tmp_path / "pole_only",
        split="train",
        classes=["pole"],
        deterministic_timestamp=True,
    )
    assert report["meta"]["classes"] == ["pole"]
    assert report["meta"]["dataset_split"] == "train"
    assert "table" not in report["unstratified"]["per_class"]


def test_run_rejects_test_split(tmp_path):
    with pytest.raises(HeldOutEvidenceError):
        run(
            ground_truth_path=GT_PATH,
            predictions_path=PRED_PATH,
            out_dir=tmp_path / "nope",
            split="test",
        )


def test_run_rejects_held_out_path_even_with_val_split(tmp_path):
    heldout_gt = tmp_path / "held-out" / "gt.json"
    heldout_gt.parent.mkdir()
    heldout_gt.write_text(GT_PATH.read_text())
    with pytest.raises(HeldOutEvidenceError):
        run(
            ground_truth_path=heldout_gt,
            predictions_path=PRED_PATH,
            out_dir=tmp_path / "out",
            split="val",
        )


def test_cli_requires_split(tmp_path):
    from evaluation.run_geometry_eval import main

    with pytest.raises(SystemExit):
        main(
            [
                "--ground-truth",
                str(GT_PATH),
                "--predictions",
                str(PRED_PATH),
                "--out-dir",
                str(tmp_path / "cli"),
            ]
        )


def test_cli_split_test_returns_nonzero(tmp_path, capsys):
    from evaluation.run_geometry_eval import main

    code = main(
        [
            "--ground-truth",
            str(GT_PATH),
            "--predictions",
            str(PRED_PATH),
            "--split",
            "test",
            "--out-dir",
            str(tmp_path / "cli_test"),
        ]
    )
    assert code == 1
    err = capsys.readouterr().err
    assert "held-out" in err.lower()
