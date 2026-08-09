"""Tests for versioned candidate-evaluation comparison and gating."""

from __future__ import annotations

import json
import sys
from pathlib import Path

import pytest


TOOLS_DIR = Path(__file__).resolve().parents[1] / "tools"
sys.path.insert(0, str(TOOLS_DIR))

import compare_model_evaluations as comparison


CLASS_NAMES = comparison.APPROVED_CLASS_NAMES
HISTORICAL_REFERENCE = (
    Path(__file__).resolve().parents[1]
    / "evaluation"
    / "baselines"
    / "historical_7class_baseline.json"
)


def metrics(
    *,
    value: float = 0.5,
    latency: float = 10.0,
    missing: str | None = None,
) -> dict[str, object]:
    values: dict[str, object] = {
        "precision": value,
        "recall": value,
        "mAP50": value,
        "mAP50_95": value,
        "inference_timing_ms": {"inference": latency},
        "per_class_results": {
            str(index): {
                "class_name": name,
                "precision": value,
                "recall": value,
                "mAP50": value,
                "mAP50_95": value,
            }
            for index, name in enumerate(CLASS_NAMES)
        },
    }
    if missing is not None:
        values[missing] = None
    return values


def artifact(
    *,
    sha256: str,
    baseline_type: str = "canonical_8class_baseline",
    mode: str = "labelled_validation",
    settings: dict[str, object] | None = None,
    metric_values: dict[str, object] | None = None,
) -> dict[str, object]:
    classes = list(CLASS_NAMES)
    return {
        "schema_version": comparison.SCHEMA_VERSION,
        "tool": {"name": "evaluate_current_model", "version": "2.0.0"},
        "created_at_utc": "2026-08-09T00:00:00Z",
        "baseline_type": baseline_type,
        "model": {
            "filename": "candidate.pt",
            "file_size_bytes": 42,
            "sha256": sha256,
            "class_count": len(classes),
            "class_id_to_name": {str(index): name for index, name in enumerate(classes)},
            "ordered_class_names": classes,
        },
        "mode": mode,
        "metric_semantics": comparison.model_evaluator.LABELLED_VALIDATION_METRIC_SEMANTICS
        if mode == "labelled_validation"
        else None,
        "evaluation_settings": settings
        or {
            "operating_point_inference": None,
            "validation_ap": {
                "engine": "ultralytics_model_val",
                "confidence": "ultralytics_default_sweep",
                "iou": "ultralytics_default",
            },
        },
        "results": {"validation_metrics": metric_values or metrics()},
    }


def write_artifact(tmp_path: Path, name: str, payload: dict[str, object]) -> Path:
    path = tmp_path / name
    path.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")
    return path


def approved_gates(**gates: object) -> dict[str, object]:
    return {
        "schema_version": comparison.SCHEMA_VERSION,
        "policy_status": "APPROVED_POLICY",
        "gates": gates
        or {
            "aggregate_minimum_deltas": {"mAP50": -0.01},
            "required_classes": ["person", "stairs"],
            "maximum_latency_increase_ms": 2.0,
        },
    }


def validation_report(candidate: dict[str, object], *, verdict: str = "pass") -> dict[str, object]:
    passed_checks = [
        "artifact_exists",
        "artifact_size",
        "sha256",
        "model_load",
        "class_count",
        "approved_taxonomy",
        "report_metadata",
        "smoke_inference",
    ]
    return {
        "schema_version": comparison.SCHEMA_VERSION,
        "tool": {"name": comparison.CANDIDATE_VALIDATION_TOOL_NAME, "version": "1.0.0"},
        "candidate": dict(candidate["model"]),  # type: ignore[arg-type]
        "verdict": verdict,
        "checks": [
            *({"name": name, "status": "pass"} for name in passed_checks),
            {"name": "detection_task", "status": "pass"},
        ],
    }


def compare(
    tmp_path: Path,
    baseline: dict[str, object],
    candidate: dict[str, object],
    gates: dict[str, object] | None = None,
    *,
    include_validation: bool = True,
    validation_verdict: str = "pass",
) -> dict[str, object]:
    gate_path = write_artifact(tmp_path, "gates.json", gates) if gates else None
    validation_path = (
        write_artifact(
            tmp_path,
            "candidate-validation.json",
            validation_report(candidate, verdict=validation_verdict),
        )
        if include_validation
        else None
    )
    return comparison.compare_evaluations(
        write_artifact(tmp_path, "baseline.json", baseline),
        write_artifact(tmp_path, "candidate.json", candidate),
        gate_config_path=gate_path,
        candidate_validation_path=validation_path,
    )


def test_compatible_candidate_without_gates_requires_review(tmp_path: Path) -> None:
    report = compare(tmp_path, artifact(sha256="a" * 64), artifact(sha256="b" * 64))

    assert report["verdict"] == "REVIEW"
    assert report["technical_compatibility"]["status"] == "compatible"  # type: ignore[index]
    assert report["policy_gate"]["configuration_supplied"] is False  # type: ignore[index]


def test_approved_gates_without_matching_candidate_validation_require_review(
    tmp_path: Path,
) -> None:
    report = compare(
        tmp_path,
        artifact(sha256="a" * 64),
        artifact(sha256="b" * 64),
        approved_gates(),
        include_validation=False,
    )

    assert report["verdict"] == "REVIEW"
    assert report["technical_compatibility"]["status"] == "candidate_validation_missing"  # type: ignore[index]


@pytest.mark.parametrize(
    ("validation_verdict", "expected_status"),
    [("fail", "candidate_validation_failed"), ("pass", "candidate_validation_mismatch")],
)
def test_failed_or_mismatched_candidate_validation_cannot_pass(
    tmp_path: Path, validation_verdict: str, expected_status: str
) -> None:
    baseline = artifact(sha256="a" * 64)
    candidate = artifact(sha256="b" * 64)
    if expected_status == "candidate_validation_mismatch":
        report_path = write_artifact(
            tmp_path,
            "candidate-validation.json",
            validation_report(artifact(sha256="c" * 64)),
        )
        report = comparison.compare_evaluations(
            write_artifact(tmp_path, "baseline.json", baseline),
            write_artifact(tmp_path, "candidate.json", candidate),
            gate_config_path=write_artifact(tmp_path, "gates.json", approved_gates()),
            candidate_validation_path=report_path,
        )
    else:
        report = compare(
            tmp_path,
            baseline,
            candidate,
            approved_gates(),
            validation_verdict=validation_verdict,
        )

    assert report["verdict"] == "FAIL"
    assert report["technical_compatibility"]["status"] == expected_status  # type: ignore[index]


def test_incomplete_successful_candidate_validation_report_is_rejected(tmp_path: Path) -> None:
    candidate = artifact(sha256="b" * 64)
    incomplete = validation_report(candidate)
    incomplete["checks"] = []
    report_path = write_artifact(tmp_path, "candidate-validation.json", incomplete)

    with pytest.raises(comparison.ComparisonError, match="required successful check"):
        comparison.load_candidate_validation_report(report_path)


def test_approved_gates_can_pass_a_compatible_improvement(tmp_path: Path) -> None:
    baseline = artifact(sha256="a" * 64, metric_values=metrics(value=0.5, latency=10.0))
    candidate = artifact(sha256="b" * 64, metric_values=metrics(value=0.55, latency=11.0))
    report = compare(tmp_path, baseline, candidate, approved_gates())

    assert report["verdict"] == "PASS"
    assert report["deltas"]["aggregate"]["mAP50"] == pytest.approx(0.05)  # type: ignore[index]
    assert report["deltas"]["per_class"]["stairs"]["recall"] == pytest.approx(0.05)  # type: ignore[index]
    assert report["deltas"]["latency_ms"] == pytest.approx(1.0)  # type: ignore[index]
    assert report["candidate_validation"]["verdict"] == "pass"  # type: ignore[index]
    assert report["policy_gate"]["source_filename"] == "gates.json"  # type: ignore[index]
    assert report["policy_gate"]["gates"] == approved_gates()["gates"]  # type: ignore[index]


@pytest.mark.parametrize(
    ("candidate_metrics", "gates"),
    [
        (
            metrics(value=0.45),
            approved_gates(aggregate_minimum_deltas={"mAP50": -0.01}),
        ),
        (
            metrics(value=0.5, latency=14.0),
            approved_gates(maximum_latency_increase_ms=2.0),
        ),
    ],
)
def test_aggregate_and_latency_gate_breaches_fail(
    tmp_path: Path, candidate_metrics: dict[str, object], gates: dict[str, object]
) -> None:
    report = compare(
        tmp_path,
        artifact(sha256="a" * 64, metric_values=metrics()),
        artifact(sha256="b" * 64, metric_values=candidate_metrics),
        gates,
    )

    assert report["verdict"] == "FAIL"


def test_per_class_gate_breach_fails_by_canonical_name(tmp_path: Path) -> None:
    candidate_metrics = metrics()
    candidate_metrics["per_class_results"]["1"]["recall"] = 0.1  # type: ignore[index]
    gates = approved_gates(per_class_minimum_deltas={"recall": {"stairs": -0.01}})

    report = compare(
        tmp_path,
        artifact(sha256="a" * 64, metric_values=metrics()),
        artifact(sha256="b" * 64, metric_values=candidate_metrics),
        gates,
    )

    assert report["verdict"] == "FAIL"
    assert report["deltas"]["per_class"]["stairs"]["recall"] == pytest.approx(-0.4)  # type: ignore[index]


@pytest.mark.parametrize(
    ("candidate_value", "expected_verdict"),
    [(0.48, "PASS"), (0.480001, "PASS"), (0.479999, "FAIL")],
)
def test_metric_gate_boundaries_are_deterministic(
    tmp_path: Path, candidate_value: float, expected_verdict: str
) -> None:
    report = compare(
        tmp_path,
        artifact(sha256="a" * 64, metric_values=metrics(value=0.5)),
        artifact(sha256="b" * 64, metric_values=metrics(value=candidate_value)),
        approved_gates(aggregate_minimum_deltas={"mAP50": -0.02}),
    )

    assert report["verdict"] == expected_verdict


@pytest.mark.parametrize("missing", ["precision", "mAP50"])
def test_missing_or_nonfinite_metrics_require_review(tmp_path: Path, missing: str) -> None:
    report = compare(
        tmp_path,
        artifact(sha256="a" * 64),
        artifact(sha256="b" * 64, metric_values=metrics(missing=missing)),
        approved_gates(),
    )

    assert report["verdict"] == "REVIEW"
    assert report["technical_compatibility"]["status"] == "missing_metrics"  # type: ignore[index]


def test_nonfinite_metric_requires_review(tmp_path: Path) -> None:
    baseline_path = write_artifact(tmp_path, "baseline.json", artifact(sha256="a" * 64))
    candidate = artifact(sha256="b" * 64)
    candidate["results"]["validation_metrics"]["mAP50"] = float("nan")  # type: ignore[index]
    candidate_path = tmp_path / "candidate.json"
    candidate_path.write_text(json.dumps(candidate).replace("NaN", "NaN"), encoding="utf-8")
    gates_path = write_artifact(tmp_path, "gates.json", approved_gates())

    report = comparison.compare_evaluations(
        baseline_path,
        candidate_path,
        gate_config_path=gates_path,
        candidate_validation_path=write_artifact(
            tmp_path, "candidate-validation.json", validation_report(candidate)
        ),
    )

    assert report["verdict"] == "REVIEW"
    assert report["deltas"]["aggregate"]["mAP50"] is None  # type: ignore[index]


def test_nonfinite_evaluation_settings_are_rejected_before_comparison(tmp_path: Path) -> None:
    invalid = artifact(sha256="a" * 64)
    invalid["evaluation_settings"] = {"operating_point_inference": {"confidence": float("inf")}}

    with pytest.raises(comparison.ComparisonError, match="settings contain"):
        comparison.load_evaluation_artifact(write_artifact(tmp_path, "invalid.json", invalid))


@pytest.mark.parametrize("invalid_value", [float("inf"), 80.0])
def test_nonfinite_or_wrong_unit_metrics_require_review(
    tmp_path: Path, invalid_value: float
) -> None:
    candidate_metrics = metrics()
    candidate_metrics["precision"] = invalid_value

    report = compare(
        tmp_path,
        artifact(sha256="a" * 64),
        artifact(sha256="b" * 64, metric_values=candidate_metrics),
        approved_gates(),
    )

    assert report["verdict"] == "REVIEW"
    assert report["technical_compatibility"]["status"] == "missing_metrics"  # type: ignore[index]


@pytest.mark.parametrize("mutation", ["missing", "unknown", "duplicate", "null"])
def test_incomplete_or_unknown_per_class_metrics_require_review(
    tmp_path: Path, mutation: str
) -> None:
    candidate_metrics = metrics()
    per_class = candidate_metrics["per_class_results"]  # type: ignore[index]
    if mutation == "missing":
        del per_class["1"]
    elif mutation == "unknown":
        per_class["8"] = {
            "class_name": "book",
            "precision": 0.5,
            "recall": 0.5,
            "mAP50": 0.5,
            "mAP50_95": 0.5,
        }
    elif mutation == "duplicate":
        per_class["1"]["class_name"] = "person"
    else:
        per_class["1"]["mAP50"] = None

    report = compare(
        tmp_path,
        artifact(sha256="a" * 64),
        artifact(sha256="b" * 64, metric_values=candidate_metrics),
        approved_gates(),
    )

    assert report["verdict"] == "REVIEW"
    assert report["technical_compatibility"]["status"] == "missing_metrics"  # type: ignore[index]


def test_wrong_taxonomy_and_class_order_fail_not_review(tmp_path: Path) -> None:
    candidate = artifact(sha256="b" * 64)
    candidate["model"]["ordered_class_names"] = list(reversed(CLASS_NAMES))  # type: ignore[index]

    report = compare(tmp_path, artifact(sha256="a" * 64), candidate, approved_gates())

    assert report["verdict"] == "FAIL"
    assert report["technical_compatibility"]["status"] == "incompatible_taxonomy"  # type: ignore[index]


def test_historical_and_noncanonical_baselines_require_review(tmp_path: Path) -> None:
    historical = artifact(sha256="a" * 64, baseline_type="historical_reference")
    historical["model"].update(  # type: ignore[index]
        {"filename": "best.pt", "class_count": 7, "class_id_to_name": {"0": "book"}, "ordered_class_names": ["book"]}
    )
    historical_report = compare(tmp_path, historical, artifact(sha256="b" * 64), approved_gates())
    noncanonical_report = compare(
        tmp_path,
        artifact(sha256="c" * 64, baseline_type="evaluation"),
        artifact(sha256="d" * 64),
        approved_gates(),
    )

    assert historical_report["verdict"] == "REVIEW"
    assert historical_report["technical_compatibility"]["status"] == "historical_reference_only"  # type: ignore[index]
    assert noncanonical_report["verdict"] == "REVIEW"
    assert noncanonical_report["technical_compatibility"]["status"] == "baseline_not_canonical"  # type: ignore[index]


def test_committed_historical_reference_is_grounded_and_never_auto_promotes(
    tmp_path: Path,
) -> None:
    source, historical = comparison.load_evaluation_artifact(HISTORICAL_REFERENCE)
    candidate = artifact(sha256="b" * 64)

    report = comparison.compare_evaluations(
        source,
        write_artifact(tmp_path, "candidate.json", candidate),
        gate_config_path=write_artifact(tmp_path, "gates.json", approved_gates()),
        candidate_validation_path=write_artifact(
            tmp_path, "candidate-validation.json", validation_report(candidate)
        ),
    )

    assert historical["baseline_type"] == "historical_reference"
    assert historical["model"]["class_count"] == 7  # type: ignore[index]
    assert historical["results"]["images_processed"] == 33  # type: ignore[index]
    assert historical["results"]["average_inference_time_ms"] == 85.43  # type: ignore[index]
    assert historical["results"].get("validation_metrics") is None  # type: ignore[index]
    assert report["verdict"] == "REVIEW"
    assert report["technical_compatibility"]["status"] == "historical_reference_only"  # type: ignore[index]


def test_wrong_taxonomy_candidate_fails_even_against_historical_reference(tmp_path: Path) -> None:
    historical = artifact(sha256="a" * 64, baseline_type="historical_reference")
    historical["model"].update(  # type: ignore[index]
        {"filename": "best.pt", "class_count": 7, "class_id_to_name": {"0": "book"}, "ordered_class_names": ["book"]}
    )
    candidate = artifact(sha256="b" * 64)
    candidate["model"]["class_count"] = 7  # type: ignore[index]

    report = compare(tmp_path, historical, candidate, approved_gates())

    assert report["verdict"] == "FAIL"
    assert report["technical_compatibility"]["status"] == "incompatible_taxonomy"  # type: ignore[index]


@pytest.mark.parametrize("field", ["mode", "evaluation_settings"])
def test_incompatible_mode_or_settings_requires_review(tmp_path: Path, field: str) -> None:
    candidate = artifact(sha256="b" * 64)
    if field == "mode":
        candidate["mode"] = "unlabelled_inference_audit"
    else:
        candidate["evaluation_settings"] = {"operating_point_inference": {"confidence": 0.3}}

    report = compare(tmp_path, artifact(sha256="a" * 64), candidate, approved_gates())

    assert report["verdict"] == "REVIEW"
    expected_status = {
        "mode": "incompatible_evaluation_mode",
        "evaluation_settings": "incompatible_evaluation_settings",
    }[field]
    assert report["technical_compatibility"]["status"] == expected_status  # type: ignore[index]


def test_missing_metric_semantics_or_matching_unlabelled_audits_require_review(
    tmp_path: Path,
) -> None:
    missing_semantics = artifact(sha256="b" * 64)
    missing_semantics["metric_semantics"] = None
    semantics_report = compare(
        tmp_path, artifact(sha256="a" * 64), missing_semantics, approved_gates()
    )

    unlabelled_baseline = artifact(
        sha256="c" * 64, mode="unlabelled_inference_audit"
    )
    unlabelled_candidate = artifact(
        sha256="d" * 64, mode="unlabelled_inference_audit"
    )
    unlabelled_report = compare(
        tmp_path, unlabelled_baseline, unlabelled_candidate, approved_gates()
    )

    assert semantics_report["verdict"] == "REVIEW"
    assert semantics_report["technical_compatibility"]["status"] == "incompatible_metric_semantics"  # type: ignore[index]
    assert unlabelled_report["verdict"] == "REVIEW"
    assert unlabelled_report["technical_compatibility"]["status"] == "ineligible_evaluation_mode"  # type: ignore[index]


def test_example_policy_and_invalid_gate_targets_do_not_auto_pass(tmp_path: Path) -> None:
    example_policy = approved_gates()
    example_policy["policy_status"] = "EXAMPLE_NOT_APPROVED_POLICY"
    report = compare(
        tmp_path, artifact(sha256="a" * 64), artifact(sha256="b" * 64), example_policy
    )
    invalid = approved_gates(per_class_minimum_deltas={"recall": {"book": -0.1}})
    invalid_path = write_artifact(tmp_path, "invalid-gates.json", invalid)

    assert report["verdict"] == "REVIEW"
    with pytest.raises(comparison.ComparisonError, match="approved classes"):
        comparison._load_gate_config(invalid_path)


@pytest.mark.parametrize(
    "invalid_policy",
    [
        {"schema_version": comparison.SCHEMA_VERSION, "policy_status": "UNKNOWN", "gates": {"required_classes": ["person"]}},
        approved_gates(aggregate_minimum_deltas={"mAP50": -2.0}),
    ],
)
def test_malformed_or_unknown_gate_policy_fails_safely(
    tmp_path: Path, invalid_policy: dict[str, object]
) -> None:
    with pytest.raises(comparison.ComparisonError):
        comparison._load_gate_config(write_artifact(tmp_path, "invalid-gates.json", invalid_policy))


def test_unknown_schema_output_files_and_cli_exit_codes(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    baseline = artifact(sha256="a" * 64)
    baseline["schema_version"] = "9.9.9"
    baseline_path = write_artifact(tmp_path, "unknown.json", baseline)
    candidate_path = write_artifact(tmp_path, "candidate.json", artifact(sha256="b" * 64))
    with pytest.raises(comparison.ComparisonError, match="unsupported schema_version"):
        comparison.compare_evaluations(baseline_path, candidate_path)

    output = tmp_path / "comparison-output"
    report = comparison.run_comparison(
        baseline_path=candidate_path,
        candidate_path=candidate_path,
        output_path=output,
        gate_config_path=write_artifact(tmp_path, "gates.json", approved_gates()),
        candidate_validation_path=write_artifact(
            tmp_path,
            "candidate-validation.json",
            validation_report(artifact(sha256="b" * 64)),
        ),
    )
    assert report["verdict"] == "PASS"
    assert json.loads((output / "model_comparison.json").read_text(encoding="utf-8"))["verdict"] == "PASS"
    assert "## Deltas" in (output / "model_comparison.md").read_text(encoding="utf-8")

    review_exit = comparison.main(
        [
            "--baseline",
            str(candidate_path),
            "--candidate",
            str(candidate_path),
            "--output",
            str(tmp_path / "cli-output"),
        ]
    )
    assert review_exit == 2
    assert "Model comparison verdict: REVIEW" in capsys.readouterr().out


def test_empty_directory_and_models_output_are_rejected(tmp_path: Path) -> None:
    empty_directory = tmp_path / "empty"
    empty_directory.mkdir()
    candidate = artifact(sha256="b" * 64)

    with pytest.raises(comparison.ComparisonError, match="missing"):
        comparison.compare_evaluations(empty_directory, write_artifact(tmp_path, "candidate.json", candidate))
    with pytest.raises(comparison.ComparisonError, match="ML_side/models"):
        comparison._prepare_output_directory(comparison.MODELS_DIR, overwrite=False)


def test_corrupt_evaluation_json_is_rejected_without_fallback(tmp_path: Path) -> None:
    corrupt = tmp_path / "corrupt.json"
    corrupt.write_text("{not-json", encoding="utf-8")

    with pytest.raises(comparison.ComparisonError, match="read as JSON"):
        comparison.load_evaluation_artifact(corrupt)


def test_comparison_atomic_write_cleans_up_after_failure(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    target = tmp_path / "model_comparison.json"
    monkeypatch.setattr(
        Path,
        "write_text",
        lambda *_args, **_kwargs: (_ for _ in ()).throw(OSError("write failed")),
    )

    with pytest.raises(OSError, match="write failed"):
        comparison._atomic_write_text(target, "{}\n")

    assert not target.exists()
    assert not list(tmp_path.glob(".model_comparison.json.*.tmp"))


def test_cli_returns_one_for_a_configured_gate_failure(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    baseline_path = write_artifact(tmp_path, "baseline.json", artifact(sha256="a" * 64))
    candidate_path = write_artifact(
        tmp_path,
        "candidate.json",
        artifact(sha256="b" * 64, metric_values=metrics(value=0.1)),
    )
    gates_path = write_artifact(
        tmp_path,
        "gates.json",
        approved_gates(aggregate_minimum_deltas={"mAP50": -0.01}),
    )

    result = comparison.main(
        [
            "--baseline",
            str(baseline_path),
            "--candidate",
            str(candidate_path),
            "--gates",
            str(gates_path),
            "--candidate-validation",
            str(
                write_artifact(
                    tmp_path,
                    "candidate-validation.json",
                    validation_report(artifact(sha256="b" * 64, metric_values=metrics(value=0.1))),
                )
            ),
            "--output",
            str(tmp_path / "cli-output"),
        ]
    )

    assert result == 1
    assert "Model comparison verdict: FAIL" in capsys.readouterr().out
