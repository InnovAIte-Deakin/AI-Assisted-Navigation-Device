import json
from pathlib import Path

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

    json_path = out_dir / "eval_report.json"
    md_path = out_dir / "eval_report.md"
    assert json_path.exists()
    assert md_path.exists()

    with open(json_path) as f:
        saved = json.load(f)
    assert saved == report
    assert saved["meta"]["model_name"] == "mock (dev fixture)"
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
    import pytest

    with pytest.raises(ValueError):
        run(ground_truth_path=GT_PATH, out_dir=tmp_path / "bad1")  # neither given

    with pytest.raises(ValueError):
        run(
            ground_truth_path=GT_PATH, out_dir=tmp_path / "bad2",
            predictions_path=PRED_PATH, model_path="ML_side/models/some_model.pt",
        )  # both given
