import hashlib
import json
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))  # ML_side, so `evaluation` is importable

from evaluation.run_eval import run

FIXTURE_DIR = Path(__file__).parent / "fixtures" / "eval"
GT_PATH = FIXTURE_DIR / "ground_truth_small.json"
PRED_PATH = FIXTURE_DIR / "predictions_small.json"


def test_run_end_to_end_with_mock_predictions_writes_both_reports(tmp_path):
    out_dir = tmp_path / "run1"
    report = run(
        ground_truth_path=GT_PATH,
        out_dir=out_dir,
        predictions_path=PRED_PATH,
        model_name="mock (dev fixture)",
        deterministic_timestamp=True,
    )

    json_path = out_dir / "error_analysis_report.json"
    md_path = out_dir / "error_analysis_report.md"
    assert json_path.exists()
    assert md_path.exists()

    with open(json_path) as f:
        saved = json.load(f)
    assert saved == report
    assert saved["meta"]["model_name"] == "mock (dev fixture)"
    assert saved["meta"]["artifact_type"] == "supplementary_error_analysis"
    assert saved["model"] is None  # no real model file in mock mode
    assert saved["overall"]["micro"]["tp"] == 4
    assert len(saved["missed_hazards"]) == 2
    assert len(saved["false_detections"]) == 2
    assert "latency" in saved  # measure_speed defaults to True


def test_run_is_deterministic_across_repeated_calls(tmp_path):
    report_a = run(
        ground_truth_path=GT_PATH, out_dir=tmp_path / "a",
        predictions_path=PRED_PATH, deterministic_timestamp=True, measure_speed=False,
    )
    report_b = run(
        ground_truth_path=GT_PATH, out_dir=tmp_path / "b",
        predictions_path=PRED_PATH, deterministic_timestamp=True, measure_speed=False,
    )
    assert report_a == report_b


def test_run_without_latency_omits_latency_section(tmp_path):
    report = run(
        ground_truth_path=GT_PATH, out_dir=tmp_path / "no_latency",
        predictions_path=PRED_PATH, measure_speed=False, deterministic_timestamp=True,
    )
    assert "latency" not in report


def test_run_requires_exactly_one_of_predictions_or_model_path(tmp_path):
    with pytest.raises(ValueError):
        run(ground_truth_path=GT_PATH, out_dir=tmp_path / "bad1")  # neither given

    with pytest.raises(ValueError):
        run(
            ground_truth_path=GT_PATH, out_dir=tmp_path / "bad2",
            predictions_path=PRED_PATH, model_path="ML_side/models/some_model.pt",
        )  # both given


def _fake_yolo_loader(monkeypatch, calls_log):
    def fake_load_yolo_predict_fn(model_path, conf=0.25, iou=0.45):
        def predict_fn(image):
            calls_log.append(image)
            return []
        predict_fn.class_names = {0: "person"}
        return predict_fn

    monkeypatch.setattr("evaluation.run_eval.load_yolo_predict_fn", fake_load_yolo_predict_fn)


def test_run_real_model_path_uses_image_path_not_image_id(tmp_path, monkeypatch):
    image_path = str(tmp_path / "abc.jpg")
    gt_path = tmp_path / "gt.json"
    gt_path.write_text(json.dumps([
        {"image_id": "abc", "image_path": image_path, "boxes": [{"class": "person", "bbox": [0, 0, 10, 10]}]},
    ]))
    model_path = tmp_path / "model.pt"
    model_path.write_bytes(b"fake-model-bytes")

    calls = []
    _fake_yolo_loader(monkeypatch, calls)

    report = run(
        ground_truth_path=gt_path,
        out_dir=tmp_path / "out",
        model_path=model_path,
        measure_speed=False,
        deterministic_timestamp=True,
    )

    assert calls == [image_path]  # got the real path, not "abc"
    assert report["model"]["filename"] == "model.pt"
    assert report["model"]["sha256"] == hashlib.sha256(b"fake-model-bytes").hexdigest()


def test_run_real_model_missing_image_path_raises(tmp_path, monkeypatch):
    gt_path = tmp_path / "gt.json"
    gt_path.write_text(json.dumps([{"image_id": "abc", "boxes": []}]))  # no image_path
    model_path = tmp_path / "model.pt"
    model_path.write_bytes(b"fake-model-bytes")

    _fake_yolo_loader(monkeypatch, [])

    with pytest.raises(ValueError, match="image_path"):
        run(
            ground_truth_path=gt_path, out_dir=tmp_path / "out",
            model_path=model_path, measure_speed=False,
        )


def test_run_real_model_with_latency_does_not_triple_inference(tmp_path, monkeypatch):
    """Regression test for the reviewed real-model latency path: it should
    run the model exactly twice per image (one warmup pass + one combined
    predictions-building/timing pass), not three times (build, warmup,
    timed), and the returned predictions must still be the ones actually
    used for scoring, not thrown away after timing.
    """
    image_paths = [str(tmp_path / "a.jpg"), str(tmp_path / "b.jpg")]
    gt_path = tmp_path / "gt.json"
    gt_path.write_text(json.dumps([
        {"image_id": "a", "image_path": image_paths[0], "boxes": [{"class": "person", "bbox": [0, 0, 10, 10]}]},
        {"image_id": "b", "image_path": image_paths[1], "boxes": [{"class": "person", "bbox": [0, 0, 10, 10]}]},
    ]))
    model_path = tmp_path / "model.pt"
    model_path.write_bytes(b"fake-model-bytes")

    calls = []

    def fake_load_yolo_predict_fn(model_path, conf=0.25, iou=0.45):
        def predict_fn(image):
            calls.append(image)
            return [{"class": "person", "bbox": [0, 0, 10, 10], "score": 0.9}]
        predict_fn.class_names = {0: "person"}
        return predict_fn

    monkeypatch.setattr("evaluation.run_eval.load_yolo_predict_fn", fake_load_yolo_predict_fn)

    report = run(
        ground_truth_path=gt_path,
        out_dir=tmp_path / "out",
        model_path=model_path,
        measure_speed=True,
        deterministic_timestamp=True,
    )

    num_images = len(image_paths)
    # Exactly 2x per image: one discarded warmup pass, one combined
    # build-and-time pass, not 3x (build, warmup, timed separately).
    assert len(calls) == 2 * num_images
    assert sorted(calls) == sorted(image_paths * 2)

    # Only the single combined pass is timed, the warmup pass is not.
    assert report["latency"]["num_samples"] == num_images

    # Predictions from that combined pass were genuinely used for scoring,
    # not discarded, both boxes should have matched as true positives.
    assert report["overall"]["micro"]["tp"] == 2
    assert report["overall"]["micro"]["fp"] == 0
    assert report["overall"]["micro"]["fn"] == 0
