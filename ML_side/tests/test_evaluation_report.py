import json
from pathlib import Path

from evaluation.metrics import evaluate
from evaluation.report import (
    build_json_report,
    build_markdown_report,
    write_json_report,
    write_markdown_report,
)
from evaluation.taxonomy import TAXONOMY_CLASSES

FIXTURE_DIR = Path(__file__).parent / "fixtures" / "eval"


def _load_fixtures():
    with open(FIXTURE_DIR / "ground_truth_small.json") as f:
        gt = json.load(f)
    with open(FIXTURE_DIR / "predictions_small.json") as f:
        preds = json.load(f)
    return gt, preds


def _sample_result():
    gt, preds = _load_fixtures()
    return evaluate(gt, preds, classes=TAXONOMY_CLASSES, iou_threshold=0.5)


def test_build_json_report_is_deterministic_without_timestamp():
    result = _sample_result()
    report_a = build_json_report(result)
    report_b = build_json_report(result)
    assert report_a == report_b
    assert "generated_at" not in report_a["meta"]


def test_build_json_report_includes_optional_fields_when_given():
    result = _sample_result()
    latency = {"num_samples": 2, "mean_ms": 10.0, "median_ms": 10.0, "p95_ms": 10.0, "fps": 100.0}
    report = build_json_report(
        result, latency=latency, generated_at="2026-08-10T00:00:00Z",
        extra_meta={"model_name": "test model"},
    )
    assert report["latency"] == latency
    assert report["meta"]["generated_at"] == "2026-08-10T00:00:00Z"
    assert report["meta"]["model_name"] == "test model"


def test_json_report_round_trips_through_disk(tmp_path):
    result = _sample_result()
    report = build_json_report(result)
    out_path = tmp_path / "eval_report.json"
    write_json_report(report, out_path)

    with open(out_path) as f:
        reloaded = json.load(f)
    assert reloaded == report


def test_markdown_report_contains_expected_sections():
    result = _sample_result()
    report = build_json_report(result)
    md = build_markdown_report(report, model_name="inherited model")

    assert "# WalkBuddy Navigation Model Evaluation — inherited model" in md
    assert "## Overall" in md
    assert "## Per-class" in md
    assert "## Missed navigation hazards (2)" in md
    assert "## False detections (2)" in md
    assert "stairs" in md
    assert "vehicle" in md
    assert "chair" in md
    assert "bicycle" in md


def test_markdown_report_handles_no_hazards_or_false_detections():
    # a trivial perfect-match case: one image, one class, matched exactly
    gt = [{"image_id": "img1", "boxes": [{"class": "person", "bbox": [0, 0, 10, 10]}]}]
    preds = [{"image_id": "img1", "boxes": [{"class": "person", "bbox": [0, 0, 10, 10], "score": 0.99}]}]
    result = evaluate(gt, preds, classes=TAXONOMY_CLASSES, iou_threshold=0.5)
    report = build_json_report(result)
    md = build_markdown_report(report)

    assert "## Missed navigation hazards (0)" in md
    assert "## False detections (0)" in md


def test_markdown_report_writes_to_disk(tmp_path):
    result = _sample_result()
    report = build_json_report(result)
    md = build_markdown_report(report)
    out_path = tmp_path / "eval_report.md"
    write_markdown_report(md, out_path)
    assert out_path.read_text() == md
