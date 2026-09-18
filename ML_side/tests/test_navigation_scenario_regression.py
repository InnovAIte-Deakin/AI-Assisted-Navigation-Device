"""Regression coverage for the offline navigation scenario-evaluation harness."""

from __future__ import annotations

import inspect
import json
import math
import subprocess
import sys
from pathlib import Path

import pytest


ML_SIDE_DIR = Path(__file__).resolve().parents[1]
if str(ML_SIDE_DIR) not in sys.path:
    sys.path.insert(0, str(ML_SIDE_DIR))

from scenario_regression import evaluator


def case(
    scenario_id: str,
    expected: list[str],
    *,
    allowed: list[str] | None = None,
    image: str = "images/example.jpg",
) -> dict[str, object]:
    return {
        "scenario_id": scenario_id,
        "description": f"Controlled {scenario_id} scenario.",
        "image": image,
        "expected_classes": expected,
        **({"allowed_classes": allowed} if allowed is not None else {}),
    }


def suite(
    cases: list[dict[str, object]] | None = None,
    *,
    policy: str = "report_only",
) -> dict[str, object]:
    return {
        "schema_version": evaluator.SCHEMA_VERSION,
        "suite_id": "navigation-regression-v1",
        "unexpected_detection_policy": policy,
        "cases": cases or [case("stairs-ahead", ["stairs"])],
    }


def fixture(
    predictions: dict[str, list[dict[str, object]]] | None = None,
    *,
    model: dict[str, str] | None = None,
) -> dict[str, object]:
    return {
        "schema_version": evaluator.SCHEMA_VERSION,
        "suite_id": "navigation-regression-v1",
        "predictions": (
            predictions if predictions is not None else {"stairs-ahead": [{"class_name": "stairs", "confidence": 0.9}]}
        ),
        **({"model": model} if model is not None else {}),
    }


def evaluate(
    suite_payload: dict[str, object] | None = None,
    fixture_payload: dict[str, object] | None = None,
    *,
    threshold: float = 0.0,
) -> dict[str, object]:
    parsed_suite = evaluator.parse_case_suite(suite_payload or suite())
    parsed_fixture = evaluator.parse_prediction_fixture(fixture_payload or fixture(), parsed_suite)
    return evaluator.evaluate_suite(parsed_suite, parsed_fixture, confidence_threshold=threshold)


def test_taxonomy_is_exactly_the_approved_navigation_taxonomy() -> None:
    assert evaluator.APPROVED_TAXONOMY == (
        (0, "person"),
        (1, "stairs"),
        (2, "door"),
        (3, "chair"),
        (4, "table"),
        (5, "pole"),
        (6, "bicycle"),
        (7, "vehicle"),
    )


def test_valid_case_normalizes_a_relative_windows_path_to_git_safe_posix() -> None:
    parsed = evaluator.parse_case_suite(suite([case("stairs-ahead", ["stairs"], image="images\\stairs.jpg")]))
    assert parsed.cases[0].image == "images/stairs.jpg"


@pytest.mark.parametrize(
    "payload, message",
    [
        ({}, "missing required field"),
        (suite([{"scenario_id": "stairs-ahead"}]), "missing required field"),
        ({**suite(), "schema_version": "2.0.0"}, "schema_version"),
        ({**suite(), "extra": True}, "unsupported field"),
        ({**suite(), "cases": []}, "non-empty"),
        (suite([case("", ["stairs"])]), "scenario_id"),
        (suite([case("   ", ["stairs"])]), "scenario_id"),
        (suite([case(123, ["stairs"])]), "scenario_id"),  # type: ignore[arg-type]
        (suite([case("stairs-ahead", ["book"])]), "unknown class"),
        (suite([case("stairs-ahead", ["Stairs"])]), "unknown class"),
        (suite([case("stairs-ahead", [" stairs "])]), "unknown class"),
        (suite([case("stairs-ahead", [""])]), "unknown class"),
        (suite([case("stairs-ahead", ["stairs", "stairs"])]), "duplicate"),
        (suite([case("stairs-ahead", "stairs")]), "must be an array"),  # type: ignore[arg-type]
        (suite([case("stairs-ahead", ["stairs"], allowed="person")]), "must be an array"),  # type: ignore[arg-type]
        (suite([case("stairs-ahead", ["stairs"], allowed=["stairs"])]), "must not repeat"),
        (suite([case("stairs-ahead", ["stairs"]), case("stairs-ahead", ["person"])]), "duplicate scenario_id"),
        ({**suite(), "unexpected_detection_policy": []}, "unexpected_detection_policy"),
    ],
)
def test_malformed_cases_fail_with_readable_context(payload: dict[str, object], message: str) -> None:
    with pytest.raises(evaluator.ScenarioRegressionError, match=message):
        evaluator.parse_case_suite(payload)


@pytest.mark.parametrize(
    "image",
    [
        "/absolute/image.jpg",
        "C:\\images\\stairs.jpg",
        "C:images\\stairs.jpg",
        "\\\\server\\share\\stairs.jpg",
        "../stairs.jpg",
        "images/../stairs.jpg",
        "./../stairs.jpg",
        "images\\..\\stairs.jpg",
        "images/%2e%2e/stairs.jpg",
        "https://example.invalid/stairs.jpg",
    ],
)
def test_unsafe_image_paths_are_rejected(image: str) -> None:
    with pytest.raises(evaluator.ScenarioRegressionError):
        evaluator.parse_case_suite(suite([case("stairs-ahead", ["stairs"], image=image)]))


def test_perfect_true_positive_case_passes_with_unit_metrics() -> None:
    report = evaluate()
    result = report["scenarios"][0]  # type: ignore[index]
    assert result["passed"] is True
    assert result["true_positives"] == 1
    assert result["metrics"] == {"precision": 1.0, "recall": 1.0, "f1": 1.0}


def test_false_positive_is_reported_without_silently_failing_default_policy() -> None:
    report = evaluate(fixture_payload=fixture({"stairs-ahead": [{"class_name": "person", "confidence": 0.9}]}))
    result = report["scenarios"][0]  # type: ignore[index]
    assert result["passed"] is False
    assert result["unexpected_classes"] == ["person"]
    assert result["missed_classes"] == ["stairs"]


def test_unexpected_detection_policy_can_fail_an_otherwise_complete_case() -> None:
    fixture_payload = fixture(
        {
            "stairs-ahead": [
                {"class_name": "stairs", "confidence": 0.9},
                {"class_name": "person", "confidence": 0.9},
            ]
        }
    )
    report_only_result = evaluate(fixture_payload=fixture_payload)["scenarios"][0]  # type: ignore[index]
    assert report_only_result["passed"] is True
    assert report_only_result["false_positives"] == 1
    assert report_only_result["unexpected_classes"] == ["person"]
    report = evaluate(
        suite([case("stairs-ahead", ["stairs"])], policy="fail"),
        fixture_payload,
    )
    assert report["scenarios"][0]["passed"] is False  # type: ignore[index]


def test_false_negative_and_zero_predictions_are_explicit() -> None:
    report = evaluate(fixture_payload=fixture({"stairs-ahead": []}))
    result = report["scenarios"][0]  # type: ignore[index]
    assert result["detected_classes"] == []
    assert result["missed_classes"] == ["stairs"]
    assert result["metrics"] == {"precision": None, "recall": 0.0, "f1": 0.0}


def test_mixed_tp_fp_fn_and_deterministic_f1() -> None:
    report = evaluate(
        suite([case("mixed", ["stairs", "door"])]),
        fixture({"mixed": [{"class_name": "stairs", "confidence": 0.9}, {"class_name": "person", "confidence": 0.9}]}),
    )
    result = report["scenarios"][0]  # type: ignore[index]
    assert (result["true_positives"], result["false_positives"], result["false_negatives"]) == (1, 1, 1)
    assert result["metrics"] == {"precision": 0.5, "recall": 0.5, "f1": 0.5}


def test_allowed_classes_are_reported_but_not_false_positives() -> None:
    report = evaluate(
        suite([case("stairs-person", ["stairs"], allowed=["person"])]),
        fixture({"stairs-person": [{"class_name": "stairs", "confidence": 0.9}, {"class_name": "person", "confidence": 0.9}]}),
    )
    result = report["scenarios"][0]  # type: ignore[index]
    assert result["allowed_detected_classes"] == ["person"]
    assert result["unexpected_classes"] == []
    assert result["passed"] is True


def test_allowed_detection_never_satisfies_a_missing_required_class() -> None:
    report = evaluate(
        suite([case("stairs-person", ["stairs"], allowed=["person"])]),
        fixture({"stairs-person": [{"class_name": "person", "confidence": 0.9}]}),
    )
    result = report["scenarios"][0]  # type: ignore[index]
    assert result["allowed_detected_classes"] == ["person"]
    assert (result["true_positives"], result["false_positives"], result["false_negatives"]) == (0, 0, 1)
    assert result["passed"] is False


def test_negative_scenario_has_undefined_metrics_when_nothing_is_detected() -> None:
    report = evaluate(suite([case("empty-hallway", [])]), fixture({"empty-hallway": []}))
    result = report["scenarios"][0]  # type: ignore[index]
    assert result["passed"] is True
    assert result["metrics"] == {"precision": None, "recall": None, "f1": None}


def test_negative_scenario_reports_false_positives_without_fabricating_recall() -> None:
    report = evaluate(
        suite([case("empty-hallway", [])]),
        fixture({"empty-hallway": [{"class_name": "vehicle", "confidence": 0.9}]}),
    )
    result = report["scenarios"][0]  # type: ignore[index]
    assert result["passed"] is True
    assert result["unexpected_classes"] == ["vehicle"]
    assert result["metrics"] == {"precision": 0.0, "recall": None, "f1": 0.0}


def test_negative_scenario_with_fail_policy_fails_but_preserves_counts() -> None:
    report = evaluate(
        suite([case("empty-hallway", [])], policy="fail"),
        fixture({"empty-hallway": [{"class_name": "vehicle", "confidence": 0.9}]}),
    )
    result = report["scenarios"][0]  # type: ignore[index]
    assert result["passed"] is False
    assert (result["true_positives"], result["false_positives"], result["false_negatives"]) == (0, 1, 0)


def test_aggregate_and_per_class_metrics_cover_multiple_scenarios() -> None:
    report = evaluate(
        suite([case("stairs", ["stairs"]), case("door", ["door"])]),
        fixture({"stairs": [{"class_name": "stairs", "confidence": 0.9}], "door": [{"class_name": "person", "confidence": 0.9}]}),
    )
    assert report["aggregate"] == {  # type: ignore[index]
        "scenario_count": 2,
        "scenarios_passed": 1,
        "scenarios_failed": 1,
        "true_positives": 1,
        "false_positives": 1,
        "false_negatives": 1,
        "precision": 0.5,
        "recall": 0.5,
        "f1": 0.5,
    }
    assert report["per_class"]["stairs"]["true_positives"] == 1  # type: ignore[index]
    assert report["per_class"]["door"]["false_negatives"] == 1  # type: ignore[index]
    assert report["per_class"]["person"]["false_positives"] == 1  # type: ignore[index]


def test_aggregate_uses_micro_counts_not_an_average_of_case_metrics() -> None:
    report = evaluate(
        suite([case("stairs", ["stairs"]), case("door-chair", ["door", "chair"])]),
        fixture(
            {
                "stairs": [{"class_name": "stairs", "confidence": 0.9}],
                "door-chair": [{"class_name": "person", "confidence": 0.9}],
            }
        ),
    )
    aggregate = report["aggregate"]  # type: ignore[index]
    assert aggregate["precision"] == 0.5
    assert aggregate["recall"] == pytest.approx(1 / 3)
    assert aggregate["f1"] == 0.4
    assert aggregate["f1"] != pytest.approx(0.5)


def test_unobserved_per_class_metrics_are_explicitly_not_applicable() -> None:
    report = evaluate()
    vehicle = report["per_class"]["vehicle"]  # type: ignore[index]
    assert vehicle == {
        "true_positives": 0,
        "false_positives": 0,
        "false_negatives": 0,
        "precision": None,
        "recall": None,
        "f1": None,
    }


def test_detection_lists_are_deduplicated_and_canonically_ordered() -> None:
    report = evaluate(
        suite([case("ordered", ["stairs", "vehicle"])]),
        fixture({"ordered": [{"class_name": "vehicle", "confidence": 0.9}, {"class_name": "stairs", "confidence": 0.9}, {"class_name": "stairs", "confidence": 0.8}]}),
    )
    result = report["scenarios"][0]  # type: ignore[index]
    assert result["detected_classes"] == ["stairs", "vehicle"]
    assert result["true_positives"] == 2
    assert list(report["per_class"]) == list(evaluator.CANONICAL_CLASS_NAMES)  # type: ignore[arg-type]


@pytest.mark.parametrize(
    "detection, message",
    [
        ({"class_name": "book", "confidence": 0.9}, "exact approved"),
        ({"class_name": "Stairs", "confidence": 0.9}, "exact approved"),
        ({"class_name": " stairs ", "confidence": 0.9}, "exact approved"),
        ({"class_name": "", "confidence": 0.9}, "exact approved"),
        ({"class_name": "stairs"}, "missing required field"),
        ({"class_name": "stairs", "confidence": "0.9"}, "finite"),
        ({"class_name": "stairs", "confidence": True}, "finite"),
        ({"class_name": "stairs", "confidence": math.nan}, "finite"),
        ({"class_name": "stairs", "confidence": math.inf}, "finite"),
        ({"class_name": "stairs", "confidence": -0.1}, "between 0 and 1"),
        ({"class_name": "stairs", "confidence": 1.1}, "between 0 and 1"),
        ({"class_name": "stairs", "confidence": 0.9, "extra": "field"}, "unsupported field"),
    ],
)
def test_fixture_rejects_unknown_or_invalid_confidence(detection: dict[str, object], message: str) -> None:
    parsed_suite = evaluator.parse_case_suite(suite())
    with pytest.raises(evaluator.ScenarioRegressionError, match=message):
        evaluator.parse_prediction_fixture(fixture({"stairs-ahead": [detection]}), parsed_suite)


def test_fixture_requires_exact_scenario_coverage_and_optional_safe_model_identity() -> None:
    parsed_suite = evaluator.parse_case_suite(
        suite([case("stairs-ahead", ["stairs"]), case("door-ahead", ["door"]), case("chair-ahead", ["chair"])])
    )
    with pytest.raises(evaluator.ScenarioRegressionError, match="missing scenario IDs"):
        evaluator.parse_prediction_fixture(fixture({"stairs-ahead": []}), parsed_suite)
    with pytest.raises(evaluator.ScenarioRegressionError, match="unknown scenario IDs"):
        evaluator.parse_prediction_fixture(
            fixture(
                {
                    "stairs-ahead": [],
                    "door-ahead": [],
                    "chair-ahead": [],
                    "vehicle-ahead": [],
                }
            ),
            parsed_suite,
        )
    with pytest.raises(evaluator.ScenarioRegressionError, match="suite_id"):
        evaluator.parse_prediction_fixture(
            {**fixture({"stairs-ahead": [], "door-ahead": [], "chair-ahead": []}), "suite_id": "different-suite"},
            parsed_suite,
        )
    with pytest.raises(evaluator.ScenarioRegressionError, match="must be an object"):
        evaluator.parse_prediction_fixture([], parsed_suite)
    parsed = evaluator.parse_prediction_fixture(
        fixture(
            {"stairs-ahead": [], "door-ahead": [], "chair-ahead": []},
            model={"filename": "candidate.pt", "sha256": "a" * 64},
        ),
        parsed_suite,
    )
    assert parsed.model == {"filename": "candidate.pt", "sha256": "a" * 64}


def test_confidence_filtering_is_explicit_and_not_a_risk_policy() -> None:
    report = evaluate(
        fixture_payload=fixture({"stairs-ahead": [{"class_name": "stairs", "confidence": 0.49}]}),
        threshold=0.5,
    )
    result = report["scenarios"][0]  # type: ignore[index]
    assert result["filtered_out_detection_count"] == 1
    assert result["missed_classes"] == ["stairs"]
    assert "risk" in report["inference_settings"]["threshold_semantics"]  # type: ignore[index]


def test_confidence_comparison_includes_equal_values_and_excludes_only_lower_values() -> None:
    report = evaluate(
        fixture_payload=fixture(
            {
                "stairs-ahead": [
                    {"class_name": "stairs", "confidence": 0.5},
                    {"class_name": "person", "confidence": 0.499999},
                    {"class_name": "door", "confidence": 0.500001},
                ]
            }
        ),
        threshold=0.5,
    )
    result = report["scenarios"][0]  # type: ignore[index]
    assert result["detected_classes"] == ["stairs", "door"]
    assert result["filtered_out_detection_count"] == 1


@pytest.mark.parametrize(
    "threshold",
    [None, -0.01, 1.01, math.nan, math.inf, -math.inf, "0.5", True],
)
def test_invalid_confidence_thresholds_are_rejected_cleanly(threshold: object) -> None:
    parsed_suite = evaluator.parse_case_suite(suite())
    parsed_fixture = evaluator.parse_prediction_fixture(fixture(), parsed_suite)
    with pytest.raises(evaluator.ScenarioRegressionError, match="confidence_threshold"):
        evaluator.evaluate_suite(parsed_suite, parsed_fixture, confidence_threshold=threshold)  # type: ignore[arg-type]


@pytest.mark.parametrize("threshold", [0, 0.0, 1, 1.0])
def test_confidence_threshold_bounds_and_equality_are_deterministic(threshold: float) -> None:
    report = evaluate(
        fixture_payload=fixture({"stairs-ahead": [{"class_name": "stairs", "confidence": threshold}]}),
        threshold=threshold,
    )
    assert report["scenarios"][0]["detected_classes"] == ["stairs"]  # type: ignore[index]


def test_fixture_replay_writes_json_and_markdown_without_absolute_paths(tmp_path: Path) -> None:
    cases = tmp_path / "cases.json"
    predictions = tmp_path / "predictions.json"
    output = tmp_path / "reports"
    cases.write_text(json.dumps(suite()), encoding="utf-8")
    predictions.write_text(json.dumps(fixture()), encoding="utf-8")

    report = evaluator.run_fixture_evaluation(
        case_suite_path=cases,
        prediction_fixture_path=predictions,
        output_path=output,
    )

    json_report = (output / "scenario_evaluation.json").read_text(encoding="utf-8")
    markdown_report = (output / "scenario_evaluation.md").read_text(encoding="utf-8")
    assert (output / "scenario_evaluation.json").is_file()
    assert (output / "scenario_evaluation.md").is_file()
    assert str(tmp_path) not in json_report
    assert list(json.loads(json_report)["per_class"]) == list(evaluator.CANONICAL_CLASS_NAMES)
    assert report["sources"]["case_suite"]["filename"] == "cases.json"  # type: ignore[index]
    assert "Missed: (none)" in markdown_report
    assert "Unexpected: (none)" in markdown_report


def test_loader_rejects_duplicate_json_prediction_keys_and_malformed_json(tmp_path: Path) -> None:
    cases = tmp_path / "cases.json"
    duplicate_fixture = tmp_path / "duplicate-fixture.json"
    malformed_fixture = tmp_path / "malformed-fixture.json"
    cases.write_text(json.dumps(suite()), encoding="utf-8")
    duplicate_fixture.write_text(
        '{"schema_version":"1.0.0","suite_id":"navigation-regression-v1",'
        '"predictions":{"stairs-ahead":[],"stairs-ahead":[]}}',
        encoding="utf-8",
    )
    malformed_fixture.write_text("{not-json", encoding="utf-8")
    _, parsed_suite = evaluator.load_case_suite(cases)
    with pytest.raises(evaluator.ScenarioRegressionError, match="duplicate JSON field"):
        evaluator.load_prediction_fixture(duplicate_fixture, parsed_suite)
    with pytest.raises(evaluator.ScenarioRegressionError, match="could not be read"):
        evaluator.load_prediction_fixture(malformed_fixture, parsed_suite)


def test_source_checksums_change_with_input_bytes_and_reports_are_reproducible(tmp_path: Path) -> None:
    cases = tmp_path / "cases.json"
    predictions = tmp_path / "predictions.json"
    first_output = tmp_path / "first"
    second_output = tmp_path / "second"
    cases.write_text(json.dumps(suite(), indent=2), encoding="utf-8")
    predictions.write_text(json.dumps(fixture(), indent=2), encoding="utf-8")
    first = evaluator.run_fixture_evaluation(
        case_suite_path=cases,
        prediction_fixture_path=predictions,
        output_path=first_output,
    )
    second = evaluator.run_fixture_evaluation(
        case_suite_path=cases,
        prediction_fixture_path=predictions,
        output_path=second_output,
    )
    assert first["sources"] == second["sources"]
    assert (first_output / "scenario_evaluation.json").read_bytes() == (
        second_output / "scenario_evaluation.json"
    ).read_bytes()
    assert (first_output / "scenario_evaluation.md").read_bytes() == (
        second_output / "scenario_evaluation.md"
    ).read_bytes()
    cases.write_text(json.dumps({**suite(), "suite_id": "navigation-regression-v2"}), encoding="utf-8")
    changed_source, _ = evaluator.load_case_suite(cases)
    assert evaluator._sha256(changed_source) != first["sources"]["case_suite"]["sha256"]  # type: ignore[index]


def test_reports_include_exact_missed_and_unexpected_names() -> None:
    report = evaluate(
        suite([case("stairs-ahead", ["stairs"], allowed=["chair"])]),
        fixture({"stairs-ahead": [{"class_name": "person", "confidence": 0.9}]}),
    )
    markdown = evaluator.render_markdown_report(report)
    assert "Allowed: chair" in markdown
    assert "Missed: stairs" in markdown
    assert "Unexpected: person" in markdown
    assert "Counts: TP 0, FP 1, FN 1" in markdown


def test_report_output_refuses_the_repository_and_json_is_finite(tmp_path: Path) -> None:
    report = evaluate()
    with pytest.raises(evaluator.ScenarioRegressionError, match="outside the repository"):
        evaluator.write_reports(report, evaluator._REPOSITORY_ROOT / "scenario-results", overwrite=False)
    assert "NaN" not in json.dumps(report, allow_nan=False)


def test_output_directory_refuses_files_and_nonempty_directories_without_overwrite(tmp_path: Path) -> None:
    report = evaluate()
    output_file = tmp_path / "output-file"
    output_file.write_text("not a directory", encoding="utf-8")
    with pytest.raises(evaluator.ScenarioRegressionError, match="not a directory"):
        evaluator.write_reports(report, output_file, overwrite=False)
    nonempty_output = tmp_path / "nonempty-output"
    nonempty_output.mkdir()
    (nonempty_output / "unrelated.txt").write_text("preserve", encoding="utf-8")
    with pytest.raises(evaluator.ScenarioRegressionError, match="not empty"):
        evaluator.write_reports(report, nonempty_output, overwrite=False)
    evaluator.write_reports(report, nonempty_output, overwrite=True)
    assert (nonempty_output / "unrelated.txt").read_text(encoding="utf-8") == "preserve"


def test_core_module_has_no_network_client_dependency() -> None:
    source = inspect.getsource(evaluator)
    assert "import requests" not in source
    assert "urllib.request" not in source
    assert "localhost" not in source
    assert ":8001" not in source


def test_cli_help_runs_without_a_server_or_model() -> None:
    command = [
        sys.executable,
        str(ML_SIDE_DIR / "tools" / "evaluate_navigation_scenarios.py"),
        "--help",
    ]
    result = subprocess.run(command, capture_output=True, text=True, check=False)
    assert result.returncode == 0
    assert "normalized local detections" in result.stdout


def test_cli_replays_a_valid_local_fixture(tmp_path: Path) -> None:
    cases = tmp_path / "cases.json"
    predictions = tmp_path / "predictions.json"
    output = tmp_path / "reports"
    cases.write_text(json.dumps(suite()), encoding="utf-8")
    predictions.write_text(json.dumps(fixture()), encoding="utf-8")
    command = [
        sys.executable,
        str(ML_SIDE_DIR / "tools" / "evaluate_navigation_scenarios.py"),
        "--cases",
        str(cases),
        "--predictions",
        str(predictions),
        "--output",
        str(output),
    ]
    result = subprocess.run(command, capture_output=True, text=True, check=False)
    assert result.returncode == 0
    assert "1/1 scenarios passed" in result.stdout
    assert (output / "scenario_evaluation.json").is_file()


def test_cli_reports_expected_input_errors_without_a_traceback(tmp_path: Path) -> None:
    command = [
        sys.executable,
        str(ML_SIDE_DIR / "tools" / "evaluate_navigation_scenarios.py"),
        "--cases",
        str(tmp_path / "missing-cases.json"),
        "--predictions",
        str(tmp_path / "missing-predictions.json"),
        "--output",
        str(tmp_path / "reports"),
    ]
    result = subprocess.run(command, capture_output=True, text=True, check=False)
    assert result.returncode == 1
    assert "Scenario evaluation failed: Case suite file is missing" in result.stderr
    assert "Traceback" not in result.stderr
