"""Compare versioned, offline WalkBuddy model-evaluation artifacts.

This tool reports a promotion recommendation only. It cannot promote, copy,
rename, deploy, or otherwise alter model weights.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import math
import os
import sys
from collections.abc import Mapping, Sequence
from datetime import UTC, datetime
from pathlib import Path
from typing import Any
from uuid import uuid4

import evaluate_current_model as model_evaluator
import validate_dataset_manifest as manifest_validator


SCHEMA_VERSION = "1.0.0"
TOOL_NAME = "compare_model_evaluations"
TOOL_VERSION = "1.0.0"
APPROVED_CLASS_NAMES = [name for _, name in manifest_validator.APPROVED_TAXONOMY]
AGGREGATE_METRICS = ("precision", "recall", "mAP50", "mAP50_95")
APPROVED_POLICY_STATUS = "APPROVED_POLICY"
EXAMPLE_POLICY_STATUS = "EXAMPLE_NOT_APPROVED_POLICY"
CANDIDATE_VALIDATION_TOOL_NAME = "validate_candidate_model"
METRIC_COMPARISON_TOLERANCE = 1e-12
ML_SIDE_DIR = Path(__file__).resolve().parents[1]
MODELS_DIR = (ML_SIDE_DIR / "models").resolve()


class ComparisonError(Exception):
    """Raised when input artifacts or a supplied gate configuration are invalid."""


def _timestamp_utc() -> str:
    return datetime.now(UTC).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def _is_finite_number(value: object) -> bool:
    return isinstance(value, (int, float)) and not isinstance(value, bool) and math.isfinite(float(value))


def _safe_float(value: object) -> float | None:
    return float(value) if _is_finite_number(value) else None


def _probability(value: object) -> float | None:
    numeric = _safe_float(value)
    return numeric if numeric is not None and 0 <= numeric <= 1 else None


def _is_json_safe(value: object) -> bool:
    """Reject non-finite values in compatibility-critical configuration fields."""
    if value is None or isinstance(value, (str, int, bool)):
        return True
    if isinstance(value, float):
        return math.isfinite(value)
    if isinstance(value, Mapping):
        return all(isinstance(key, str) and _is_json_safe(item) for key, item in value.items())
    if isinstance(value, Sequence) and not isinstance(value, (str, bytes)):
        return all(_is_json_safe(item) for item in value)
    return False


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    try:
        with path.open("rb") as source:
            for chunk in iter(lambda: source.read(1024 * 1024), b""):
                digest.update(chunk)
    except OSError as exc:
        raise ComparisonError("Artifact checksum could not be computed.") from exc
    return digest.hexdigest()


def _read_json(path: Path) -> dict[str, object]:
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except FileNotFoundError as exc:
        raise ComparisonError("Evaluation artifact is missing.") from exc
    except (OSError, json.JSONDecodeError) as exc:
        raise ComparisonError("Evaluation artifact could not be read as JSON.") from exc
    if not isinstance(payload, dict):
        raise ComparisonError("Evaluation artifact root must be a JSON object.")
    return payload


def load_evaluation_artifact(path_value: str | Path) -> tuple[Path, dict[str, object]]:
    """Load a versioned summary file or a directory containing ``summary.json``."""
    path = Path(path_value).expanduser().resolve()
    source = path / "summary.json" if path.is_dir() else path
    payload = _read_json(source)
    if payload.get("schema_version") != SCHEMA_VERSION:
        raise ComparisonError("Evaluation artifact has an unsupported schema_version.")
    tool = payload.get("tool")
    model = payload.get("model")
    settings = payload.get("evaluation_settings")
    if not isinstance(tool, Mapping) or not isinstance(model, Mapping) or not isinstance(settings, Mapping):
        raise ComparisonError("Evaluation artifact is missing the versioned tool, model, or settings fields.")
    if not _is_json_safe(settings):
        raise ComparisonError("Evaluation artifact settings contain non-finite or malformed values.")
    if not isinstance(tool.get("name"), str) or not isinstance(tool.get("version"), str):
        raise ComparisonError("Evaluation artifact tool metadata is malformed.")
    if not isinstance(model.get("filename"), str) or not isinstance(model.get("sha256"), str):
        raise ComparisonError("Evaluation artifact model lineage is malformed.")
    if len(model["sha256"]) != 64 or any(character not in "0123456789abcdef" for character in model["sha256"]):
        raise ComparisonError("Evaluation artifact model checksum must be a lowercase SHA-256 value.")
    if (
        not isinstance(model.get("file_size_bytes"), int)
        or isinstance(model["file_size_bytes"], bool)
        or model["file_size_bytes"] <= 0
    ):
        raise ComparisonError("Evaluation artifact model size is malformed.")
    if not isinstance(payload.get("mode"), str):
        raise ComparisonError("Evaluation artifact is missing its evaluation mode.")
    return source, payload


def _ordered_classes(artifact: Mapping[str, object]) -> list[str] | None:
    model = artifact.get("model")
    if not isinstance(model, Mapping):
        return None
    names = model.get("ordered_class_names")
    if not isinstance(names, Sequence) or isinstance(names, (str, bytes)):
        return None
    if not all(isinstance(name, str) and name for name in names):
        return None
    return list(names)


def _uses_approved_taxonomy(artifact: Mapping[str, object]) -> bool:
    """Require both the class ID map and ordered names to match the target taxonomy."""
    model = artifact.get("model")
    if not isinstance(model, Mapping):
        return False
    expected_map = {str(index): name for index, name in enumerate(APPROVED_CLASS_NAMES)}
    return (
        isinstance(model.get("class_count"), int)
        and not isinstance(model.get("class_count"), bool)
        and model.get("class_count") == len(APPROVED_CLASS_NAMES)
        and model.get("class_id_to_name") == expected_map
        and _ordered_classes(artifact) == APPROVED_CLASS_NAMES
    )


def _validation_metrics(artifact: Mapping[str, object]) -> Mapping[str, object] | None:
    results = artifact.get("results")
    if isinstance(results, Mapping) and isinstance(results.get("validation_metrics"), Mapping):
        return results["validation_metrics"]  # type: ignore[return-value]
    direct = artifact.get("validation_metrics")
    return direct if isinstance(direct, Mapping) else None


def _per_class_metrics(metrics: Mapping[str, object]) -> tuple[dict[str, Mapping[str, object]], list[str]]:
    raw = metrics.get("per_class_results")
    if raw is None:
        return {}, ["Per-class metrics are missing."]
    if not isinstance(raw, Mapping):
        return {}, ["Per-class metrics have an invalid structure."]
    by_name: dict[str, Mapping[str, object]] = {}
    issues: list[str] = []
    for value in raw.values():
        if not isinstance(value, Mapping) or not isinstance(value.get("class_name"), str):
            issues.append("A per-class metric entry is malformed.")
            continue
        class_name = value["class_name"]
        if class_name in by_name:
            issues.append(f"Per-class metric name is duplicated: {class_name}.")
            continue
        by_name[class_name] = value
    return by_name, issues


def _latency_ms(metrics: Mapping[str, object]) -> float | None:
    timing = metrics.get("inference_timing_ms")
    if not isinstance(timing, Mapping):
        return None
    for key in ("inference", "inference_ms"):
        if key in timing:
            latency = _safe_float(timing[key])
            return latency if latency is not None and latency >= 0 else None
    return None


def _public_model_reference(artifact: Mapping[str, object], source: Path) -> dict[str, object]:
    model = artifact.get("model")
    assert isinstance(model, Mapping)
    return {
        "artifact": source.name,
        "baseline_type": artifact.get("baseline_type", "evaluation"),
        "filename": model.get("filename"),
        "sha256": model.get("sha256"),
        "class_count": model.get("class_count"),
        "ordered_class_names": _ordered_classes(artifact),
        "mode": artifact.get("mode"),
    }


def _settings_match(baseline: Mapping[str, object], candidate: Mapping[str, object]) -> bool:
    return baseline.get("evaluation_settings") == candidate.get("evaluation_settings")


def _has_compatible_metric_semantics(artifact: Mapping[str, object]) -> bool:
    """Accept only the evaluator's documented labelled-validation metric meaning."""
    tool = artifact.get("tool")
    return (
        artifact.get("mode") == "labelled_validation"
        and isinstance(tool, Mapping)
        and tool.get("name") == model_evaluator.TOOL_NAME
        and artifact.get("metric_semantics")
        == model_evaluator.LABELLED_VALIDATION_METRIC_SEMANTICS
    )


def load_candidate_validation_report(path_value: str | Path) -> tuple[Path, dict[str, object]]:
    """Load a matching, versioned candidate-validation report without loading weights."""
    path = Path(path_value).expanduser().resolve()
    source = path / "candidate_model_report.json" if path.is_dir() else path
    payload = _read_json(source)
    if payload.get("schema_version") != SCHEMA_VERSION:
        raise ComparisonError("Candidate validation report has an unsupported schema_version.")
    tool = payload.get("tool")
    candidate = payload.get("candidate")
    if (
        not isinstance(tool, Mapping)
        or tool.get("name") != CANDIDATE_VALIDATION_TOOL_NAME
        or not isinstance(tool.get("version"), str)
        or not isinstance(candidate, Mapping)
    ):
        raise ComparisonError("Candidate validation report is malformed.")
    if payload.get("verdict") not in {"pass", "pass_with_warnings", "fail"}:
        raise ComparisonError("Candidate validation report has an invalid verdict.")
    checks = payload.get("checks")
    if not isinstance(checks, Sequence) or isinstance(checks, (str, bytes)):
        raise ComparisonError("Candidate validation report checks are malformed.")
    checks_by_name: dict[str, str] = {}
    for check in checks:
        if not isinstance(check, Mapping):
            raise ComparisonError("Candidate validation report checks are malformed.")
        name = check.get("name")
        status = check.get("status")
        if not isinstance(name, str) or not isinstance(status, str) or name in checks_by_name:
            raise ComparisonError("Candidate validation report checks are malformed.")
        checks_by_name[name] = status
    if payload["verdict"] in {"pass", "pass_with_warnings"}:
        required_passes = {
            "artifact_exists",
            "artifact_size",
            "sha256",
            "model_load",
            "class_count",
            "approved_taxonomy",
            "report_metadata",
            "smoke_inference",
        }
        if any(checks_by_name.get(name) != "pass" for name in required_passes):
            raise ComparisonError("Candidate validation report is missing a required successful check.")
        if checks_by_name.get("detection_task") not in {"pass", "warning"}:
            raise ComparisonError("Candidate validation report has an invalid detection-task check.")
        if any(status == "fail" for status in checks_by_name.values()):
            raise ComparisonError("Candidate validation report verdict conflicts with failed checks.")
    return source, payload


def _candidate_validation_reference(
    source: Path | None, report: Mapping[str, object] | None
) -> dict[str, object]:
    if source is None or report is None:
        return {
            "supplied": False,
            "source_filename": None,
            "sha256": None,
            "verdict": None,
        }
    return {
        "supplied": True,
        "source_filename": source.name,
        "sha256": _sha256(source),
        "verdict": report.get("verdict"),
    }


def _candidate_validation_status(
    candidate_evaluation: Mapping[str, object], validation_report: Mapping[str, object] | None
) -> tuple[str, str]:
    """Ensure a PASS is tied to validation of the same candidate artifact lineage."""
    if validation_report is None:
        return "missing", "No candidate-validation report was supplied."
    if validation_report.get("verdict") == "fail":
        return "failed", "The candidate-validation report recorded a failed artifact."
    candidate = validation_report.get("candidate")
    evaluation_model = candidate_evaluation.get("model")
    if not isinstance(candidate, Mapping) or not isinstance(evaluation_model, Mapping):
        return "mismatch", "Candidate validation lineage is malformed."
    required_fields = (
        "file_size_bytes",
        "sha256",
        "class_count",
        "class_id_to_name",
        "ordered_class_names",
    )
    if any(candidate.get(field) != evaluation_model.get(field) for field in required_fields):
        return "mismatch", "Candidate-validation lineage does not match the candidate evaluation."
    return "valid", "Candidate validation matches the candidate evaluation lineage."


def _load_gate_config(path_value: str | Path) -> dict[str, object]:
    payload = _read_json(Path(path_value).expanduser().resolve())
    if payload.get("schema_version") != SCHEMA_VERSION:
        raise ComparisonError("Gate configuration has an unsupported schema_version.")
    policy_status = payload.get("policy_status")
    if policy_status not in {APPROVED_POLICY_STATUS, EXAMPLE_POLICY_STATUS}:
        raise ComparisonError("Gate configuration policy_status is unknown or malformed.")
    gates = payload.get("gates")
    if not isinstance(gates, Mapping):
        raise ComparisonError("Gate configuration is missing a gates object.")
    aggregate = gates.get("aggregate_minimum_deltas", {})
    per_class = gates.get("per_class_minimum_deltas", {})
    required_classes = gates.get("required_classes", [])
    latency = gates.get("maximum_latency_increase_ms")
    if not isinstance(aggregate, Mapping) or not isinstance(per_class, Mapping):
        raise ComparisonError("Gate configuration metrics must be objects.")
    if not isinstance(required_classes, Sequence) or isinstance(required_classes, (str, bytes)):
        raise ComparisonError("Gate configuration required_classes must be an array.")
    if latency is not None and not _is_finite_number(latency):
        raise ComparisonError("Gate configuration latency tolerance must be finite.")
    for metric, tolerance in aggregate.items():
        if not isinstance(metric, str) or metric not in AGGREGATE_METRICS:
            raise ComparisonError("Aggregate gate metrics must be supported metric names.")
        if not _is_finite_number(tolerance) or not -1 <= float(tolerance) <= 1:
            raise ComparisonError("Aggregate gate tolerances must be finite numeric values.")
    for metric, class_thresholds in per_class.items():
        if not isinstance(metric, str) or metric not in AGGREGATE_METRICS:
            raise ComparisonError("Per-class gate metrics must be supported metric names.")
        if not isinstance(class_thresholds, Mapping):
            raise ComparisonError("Per-class gate tolerances must be objects keyed by class name.")
        for class_name, tolerance in class_thresholds.items():
            if (
                class_name not in APPROVED_CLASS_NAMES
                or not _is_finite_number(tolerance)
                or not -1 <= float(tolerance) <= 1
            ):
                raise ComparisonError(
                    "Per-class gate targets must be approved classes with finite numeric tolerances."
                )
    if not all(isinstance(name, str) and name in APPROVED_CLASS_NAMES for name in required_classes):
        raise ComparisonError("Gate configuration required_classes must use approved class names.")
    if len(set(required_classes)) != len(required_classes):
        raise ComparisonError("Gate configuration required_classes must not contain duplicates.")
    if not any((aggregate, per_class, required_classes, latency is not None)):
        raise ComparisonError("Gate configuration must declare at least one gate.")
    return payload


def _gate_policy_reference(
    source: Path | None, gate_config: Mapping[str, object] | None
) -> dict[str, object]:
    if source is None or gate_config is None:
        return {
            "configuration_supplied": False,
            "source_filename": None,
            "sha256": None,
            "schema_version": None,
            "policy_status": "not_supplied",
            "gates": None,
        }
    return {
        "configuration_supplied": True,
        "source_filename": source.name,
        "sha256": _sha256(source),
        "schema_version": gate_config["schema_version"],
        "policy_status": gate_config["policy_status"],
        "gates": gate_config["gates"],
    }


def _empty_deltas() -> dict[str, object]:
    return {"aggregate": {}, "per_class": {}, "latency_ms": None}


def _per_class_coverage_issues(
    metrics_by_name: Mapping[str, Mapping[str, object]], *, artifact_role: str
) -> list[str]:
    expected = set(APPROVED_CLASS_NAMES)
    actual = set(metrics_by_name)
    issues: list[str] = []
    if actual != expected:
        missing = sorted(expected - actual)
        unexpected = sorted(actual - expected)
        if missing:
            issues.append(f"{artifact_role} per-class metrics are missing: {', '.join(missing)}.")
        if unexpected:
            issues.append(f"{artifact_role} per-class metrics include unknown classes: {', '.join(unexpected)}.")
    for class_name in sorted(expected & actual):
        for metric in AGGREGATE_METRICS:
            if _probability(metrics_by_name[class_name].get(metric)) is None:
                issues.append(
                    f"{artifact_role} per-class metric {metric} for {class_name} is missing, non-finite, or outside 0..1."
                )
    return issues


def _metric_deltas(
    baseline_metrics: Mapping[str, object], candidate_metrics: Mapping[str, object]
) -> tuple[dict[str, object], list[str]]:
    deltas = _empty_deltas()
    missing: list[str] = []
    aggregate: dict[str, float | None] = {}
    for name in AGGREGATE_METRICS:
        baseline_value = _probability(baseline_metrics.get(name))
        candidate_value = _probability(candidate_metrics.get(name))
        if baseline_value is None or candidate_value is None:
            aggregate[name] = None
            missing.append(
                f"Aggregate metric {name} is missing, non-finite, or outside 0..1."
            )
        else:
            aggregate[name] = candidate_value - baseline_value
    deltas["aggregate"] = aggregate

    baseline_per_class, baseline_issues = _per_class_metrics(baseline_metrics)
    candidate_per_class, candidate_issues = _per_class_metrics(candidate_metrics)
    missing.extend(baseline_issues)
    missing.extend(candidate_issues)
    missing.extend(_per_class_coverage_issues(baseline_per_class, artifact_role="Baseline"))
    missing.extend(_per_class_coverage_issues(candidate_per_class, artifact_role="Candidate"))
    per_class: dict[str, dict[str, float | None]] = {}
    for class_name in sorted(set(baseline_per_class) | set(candidate_per_class)):
        per_class[class_name] = {}
        for metric in AGGREGATE_METRICS:
            baseline_value = _probability(baseline_per_class.get(class_name, {}).get(metric))
            candidate_value = _probability(candidate_per_class.get(class_name, {}).get(metric))
            per_class[class_name][metric] = (
                candidate_value - baseline_value
                if baseline_value is not None and candidate_value is not None
                else None
            )
    deltas["per_class"] = per_class

    baseline_latency = _latency_ms(baseline_metrics)
    candidate_latency = _latency_ms(candidate_metrics)
    deltas["latency_ms"] = (
        candidate_latency - baseline_latency
        if baseline_latency is not None and candidate_latency is not None
        else None
    )
    return deltas, missing


def _below_minimum(actual: float, minimum: float) -> bool:
    """Treat a value within a tiny floating-point representation error as equal."""
    return actual < minimum and not math.isclose(
        actual, minimum, rel_tol=0.0, abs_tol=METRIC_COMPARISON_TOLERANCE
    )


def _above_maximum(actual: float, maximum: float) -> bool:
    """Treat a value within a tiny floating-point representation error as equal."""
    return actual > maximum and not math.isclose(
        actual, maximum, rel_tol=0.0, abs_tol=METRIC_COMPARISON_TOLERANCE
    )


def _evaluate_gates(
    deltas: Mapping[str, object],
    baseline_metrics: Mapping[str, object],
    candidate_metrics: Mapping[str, object],
    gate_config: Mapping[str, object] | None,
) -> tuple[str, list[str]]:
    if gate_config is None:
        return "REVIEW", ["No explicitly supplied promotion-gate configuration is available."]

    if gate_config.get("policy_status") != APPROVED_POLICY_STATUS:
        return "REVIEW", [
            "The supplied configuration is not marked APPROVED_POLICY; automatic promotion requires ML-team/project approval."
        ]

    gates = gate_config["gates"]
    assert isinstance(gates, Mapping)
    reasons: list[str] = []
    aggregate_deltas = deltas["aggregate"]
    assert isinstance(aggregate_deltas, Mapping)
    for metric, minimum_delta in gates.get("aggregate_minimum_deltas", {}).items():
        actual_delta = aggregate_deltas.get(metric)
        if not _is_finite_number(actual_delta):
            return "REVIEW", [f"Required aggregate metric {metric} is missing or non-finite."]
        if _below_minimum(float(actual_delta), float(minimum_delta)):
            reasons.append(f"Aggregate {metric} delta {actual_delta} is below configured minimum {minimum_delta}.")

    per_class_deltas = deltas["per_class"]
    assert isinstance(per_class_deltas, Mapping)
    baseline_per_class, _ = _per_class_metrics(baseline_metrics)
    candidate_per_class, _ = _per_class_metrics(candidate_metrics)
    for metric, class_thresholds in gates.get("per_class_minimum_deltas", {}).items():
        assert isinstance(class_thresholds, Mapping)
        for class_name, minimum_delta in class_thresholds.items():
            actual = per_class_deltas.get(class_name)
            actual_delta = actual.get(metric) if isinstance(actual, Mapping) else None
            if class_name not in baseline_per_class or class_name not in candidate_per_class or not _is_finite_number(actual_delta):
                return "REVIEW", [f"Required per-class metric {metric} for {class_name} is missing or non-finite."]
            if _below_minimum(float(actual_delta), float(minimum_delta)):
                reasons.append(
                    f"Per-class {metric} delta for {class_name} is below configured minimum {minimum_delta}."
                )

    for class_name in gates.get("required_classes", []):
        if class_name not in baseline_per_class or class_name not in candidate_per_class:
            return "REVIEW", [f"Required class {class_name} is missing from per-class metrics."]

    maximum_latency = gates.get("maximum_latency_increase_ms")
    if maximum_latency is not None:
        latency_delta = deltas["latency_ms"]
        if not _is_finite_number(latency_delta):
            return "REVIEW", ["Required inference latency is missing or non-finite."]
        if _above_maximum(float(latency_delta), float(maximum_latency)):
            reasons.append(
                f"Inference latency increase {latency_delta} ms exceeds configured maximum {maximum_latency} ms."
            )
    return ("FAIL", reasons) if reasons else ("PASS", ["All explicitly supplied gates passed."])


def compare_evaluations(
    baseline_path: str | Path,
    candidate_path: str | Path,
    *,
    gate_config_path: str | Path | None = None,
    candidate_validation_path: str | Path | None = None,
) -> dict[str, object]:
    """Compare compatible versioned evaluation artifacts without changing models."""
    baseline_source, baseline = load_evaluation_artifact(baseline_path)
    candidate_source, candidate = load_evaluation_artifact(candidate_path)
    gate_source = Path(gate_config_path).expanduser().resolve() if gate_config_path is not None else None
    gate_config = _load_gate_config(gate_source) if gate_source is not None else None
    validation_source: Path | None = None
    validation_report: dict[str, object] | None = None
    if candidate_validation_path is not None:
        validation_source, validation_report = load_candidate_validation_report(
            candidate_validation_path
        )
    validation_status, validation_reason = _candidate_validation_status(
        candidate, validation_report
    )
    reasons: list[str] = []
    compatibility = "compatible"

    if not _uses_approved_taxonomy(candidate):
        compatibility = "incompatible_taxonomy"
        reasons.append("The candidate must use the approved ordered eight-class taxonomy.")
    elif validation_status == "failed":
        compatibility = "candidate_validation_failed"
        reasons.append(validation_reason)
    elif validation_status == "mismatch":
        compatibility = "candidate_validation_mismatch"
        reasons.append(validation_reason)
    elif baseline.get("baseline_type") == "historical_reference":
        compatibility = "historical_reference_only"
        reasons.append("Historical references cannot be used for automatic promotion.")
    elif not _uses_approved_taxonomy(baseline):
        compatibility = "incompatible_taxonomy"
        reasons.append("The non-historical baseline must use the approved ordered eight-class taxonomy.")
    elif baseline.get("baseline_type") != "canonical_8class_baseline":
        compatibility = "baseline_not_canonical"
        reasons.append("The baseline is not designated as a human-approved canonical 8-class baseline.")
    elif baseline.get("mode") != candidate.get("mode"):
        compatibility = "incompatible_evaluation_mode"
        reasons.append("Evaluation modes differ.")
    elif baseline.get("mode") != "labelled_validation":
        compatibility = "ineligible_evaluation_mode"
        reasons.append("Automatic promotion requires labelled validation, not an inference audit.")
    elif not _settings_match(baseline, candidate):
        compatibility = "incompatible_evaluation_settings"
        reasons.append("Evaluation settings differ.")
    elif not _has_compatible_metric_semantics(baseline) or not _has_compatible_metric_semantics(candidate):
        compatibility = "incompatible_metric_semantics"
        reasons.append("Artifacts do not declare the supported labelled-validation metric semantics.")
    elif validation_status == "missing":
        compatibility = "candidate_validation_missing"
        reasons.append(validation_reason)

    baseline_metrics = _validation_metrics(baseline)
    candidate_metrics = _validation_metrics(candidate)
    if baseline_metrics is None or candidate_metrics is None:
        deltas = _empty_deltas()
        reasons.append("Labelled validation metrics are missing.")
        if compatibility == "compatible":
            compatibility = "missing_metrics"
    else:
        deltas, metric_issues = _metric_deltas(baseline_metrics, candidate_metrics)
        if metric_issues:
            reasons.extend(metric_issues)
            if compatibility == "compatible":
                compatibility = "missing_metrics"

    if compatibility != "compatible":
        verdict = (
            "FAIL"
            if compatibility
            in {
                "incompatible_taxonomy",
                "candidate_validation_failed",
                "candidate_validation_mismatch",
            }
            else "REVIEW"
        )
        policy_reasons = ["Automatic promotion is not eligible for this comparison."]
    else:
        assert baseline_metrics is not None and candidate_metrics is not None
        verdict, policy_reasons = _evaluate_gates(
            deltas, baseline_metrics, candidate_metrics, gate_config
        )

    return {
        "schema_version": SCHEMA_VERSION,
        "tool": {"name": TOOL_NAME, "version": TOOL_VERSION},
        "created_at_utc": _timestamp_utc(),
        "baseline": _public_model_reference(baseline, baseline_source),
        "candidate": _public_model_reference(candidate, candidate_source),
        "candidate_validation": _candidate_validation_reference(
            validation_source, validation_report
        ),
        "technical_compatibility": {"status": compatibility, "reasons": reasons},
        "policy_gate": {
            **_gate_policy_reference(gate_source, gate_config),
            "result": verdict,
            "reasons": policy_reasons,
        },
        "deltas": deltas,
        "verdict": verdict,
    }


def _is_within(path: Path, parent: Path) -> bool:
    try:
        path.relative_to(parent)
    except ValueError:
        return False
    return True


def _prepare_output_directory(output_path: str | Path, overwrite: bool) -> Path:
    path = Path(output_path).expanduser().resolve()
    if _is_within(path, MODELS_DIR):
        raise ComparisonError("Comparison output must not be written inside ML_side/models.")
    if path.exists() and not path.is_dir():
        raise ComparisonError("Comparison output path is not a directory.")
    if path.exists() and any(path.iterdir()) and not overwrite:
        raise ComparisonError("Comparison output directory is not empty. Use --overwrite to replace reports.")
    try:
        path.mkdir(parents=True, exist_ok=True)
    except OSError as exc:
        raise ComparisonError("Comparison output directory could not be created.") from exc
    return path


def _atomic_write_text(path: Path, content: str) -> None:
    """Replace one report atomically without leaving a partial destination file."""
    temporary_path = path.with_name(f".{path.name}.{uuid4().hex}.tmp")
    try:
        temporary_path.write_text(content, encoding="utf-8")
        os.replace(temporary_path, path)
    except (OSError, UnicodeError):
        try:
            temporary_path.unlink(missing_ok=True)
        except OSError:
            pass
        raise


def render_markdown_report(report: Mapping[str, object]) -> str:
    compatibility = report["technical_compatibility"]
    policy = report["policy_gate"]
    validation = report["candidate_validation"]
    assert (
        isinstance(compatibility, Mapping)
        and isinstance(policy, Mapping)
        and isinstance(validation, Mapping)
    )
    lines = [
        "# Model Evaluation Comparison",
        "",
        f"- Verdict: **{report['verdict']}**",
        f"- Technical compatibility: `{compatibility['status']}`",
        f"- Policy configuration supplied: `{policy['configuration_supplied']}`",
        f"- Policy configuration file: `{policy['source_filename']}`",
        f"- Policy configuration SHA-256: `{policy['sha256']}`",
        f"- Policy status: `{policy['policy_status']}`",
        f"- Candidate validation supplied: `{validation['supplied']}`",
        f"- Candidate validation file: `{validation['source_filename']}`",
        f"- Candidate validation verdict: `{validation['verdict']}`",
        "",
        "## Reasons",
        "",
    ]
    reasons = list(compatibility["reasons"]) + list(policy["reasons"])
    lines.extend(f"- {reason}" for reason in reasons)
    lines.extend(["", "## Deltas", "", "```json", json.dumps(report["deltas"], indent=2, sort_keys=True, allow_nan=False), "```", ""])
    return "\n".join(lines)


def run_comparison(
    *,
    baseline_path: str | Path,
    candidate_path: str | Path,
    output_path: str | Path,
    gate_config_path: str | Path | None = None,
    candidate_validation_path: str | Path | None = None,
    overwrite: bool = False,
) -> dict[str, object]:
    output = _prepare_output_directory(output_path, overwrite)
    report = compare_evaluations(
        baseline_path,
        candidate_path,
        gate_config_path=gate_config_path,
        candidate_validation_path=candidate_validation_path,
    )
    try:
        _atomic_write_text(
            output / "model_comparison.json",
            json.dumps(report, indent=2, sort_keys=True, allow_nan=False) + "\n",
        )
        _atomic_write_text(
            output / "model_comparison.md", render_markdown_report(report)
        )
    except (OSError, TypeError, UnicodeError, ValueError) as exc:
        raise ComparisonError("Comparison report could not be written.") from exc
    return report


def parse_args(argv: Sequence[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Compare versioned WalkBuddy model evaluations without promoting models."
    )
    parser.add_argument("--baseline", required=True, help="Baseline summary JSON or result directory.")
    parser.add_argument("--candidate", required=True, help="Candidate summary JSON or result directory.")
    parser.add_argument("--output", required=True, help="Directory for comparison reports.")
    parser.add_argument(
        "--candidate-validation",
        help="Candidate validation JSON or directory; required for an automatic PASS.",
    )
    parser.add_argument("--gates", help="Explicitly supplied promotion-gate JSON; no default is used.")
    parser.add_argument("--overwrite", action="store_true", help="Allow report replacement in a non-empty output directory.")
    return parser.parse_args(argv)


def main(argv: Sequence[str] | None = None) -> int:
    args = parse_args(argv)
    try:
        report = run_comparison(
            baseline_path=args.baseline,
            candidate_path=args.candidate,
            output_path=args.output,
            gate_config_path=args.gates,
            candidate_validation_path=args.candidate_validation,
            overwrite=args.overwrite,
        )
    except ComparisonError as exc:
        print(f"Model comparison failed: {exc}", file=sys.stderr)
        return 1
    print(f"Model comparison verdict: {report['verdict']}")
    return {"PASS": 0, "FAIL": 1, "REVIEW": 2}[str(report["verdict"])]


if __name__ == "__main__":
    raise SystemExit(main())
