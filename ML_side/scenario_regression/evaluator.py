"""Pure, offline scenario-regression scoring for navigation detections.

This module evaluates canonical class presence per scenario. It does not load
models, inspect images, make network requests, or implement navigation-risk,
proximity, temporal-stabilization, or promotion policy.
"""

from __future__ import annotations

import hashlib
import json
import math
import os
import re
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from pathlib import Path, PurePosixPath, PureWindowsPath
from typing import Any
from urllib.parse import unquote
from uuid import uuid4

from tools.validate_dataset_manifest import APPROVED_TAXONOMY


SCHEMA_VERSION = "1.0.0"
TOOL_NAME = "evaluate_navigation_scenarios"
TOOL_VERSION = "1.0.0"
CANONICAL_CLASS_NAMES = tuple(name for _, name in APPROVED_TAXONOMY)
_CLASS_ORDER = {name: class_id for class_id, name in APPROVED_TAXONOMY}
_IDENTIFIER_PATTERN = re.compile(r"^[a-z0-9][a-z0-9-]*$")
_SHA256_PATTERN = re.compile(r"^[0-9a-f]{64}$")
_UNEXPECTED_POLICIES = frozenset({"report_only", "fail"})
_REPOSITORY_ROOT = Path(__file__).resolve().parents[2]


class ScenarioRegressionError(ValueError):
    """Raised for an invalid suite, fixture, or report invocation."""


class _DuplicateJsonKeyError(ValueError):
    """Raised internally when an input JSON object repeats a field name."""


@dataclass(frozen=True)
class ScenarioCase:
    """One controlled class-presence regression scenario."""

    scenario_id: str
    description: str
    image: str
    expected_classes: tuple[str, ...]
    allowed_classes: tuple[str, ...]
    notes: str | None


@dataclass(frozen=True)
class ScenarioSuite:
    """A versioned collection of controlled scenario cases."""

    suite_id: str
    unexpected_detection_policy: str
    cases: tuple[ScenarioCase, ...]


@dataclass(frozen=True)
class NormalizedDetection:
    """The minimal detector output used for deterministic class-level scoring."""

    class_name: str
    confidence: float


@dataclass(frozen=True)
class PredictionFixture:
    """Saved normalized detections aligned to a scenario suite."""

    suite_id: str
    predictions: Mapping[str, tuple[NormalizedDetection, ...]]
    model: Mapping[str, str] | None


def _error(location: str, message: str) -> ScenarioRegressionError:
    return ScenarioRegressionError(f"{location}: {message}")


def _require_mapping(value: object, location: str) -> Mapping[str, object]:
    if not isinstance(value, Mapping):
        raise _error(location, "must be an object.")
    if not all(isinstance(key, str) for key in value):
        raise _error(location, "must use string field names.")
    return value


def _require_identifier(value: object, location: str) -> str:
    if not isinstance(value, str) or not _IDENTIFIER_PATTERN.fullmatch(value):
        raise _error(location, "must use lowercase letters, numbers, and single hyphens.")
    return value


def _require_text(value: object, location: str) -> str:
    if not isinstance(value, str) or not value.strip():
        raise _error(location, "must be a non-empty string.")
    return value


def _decode_until_stable(value: str) -> str:
    decoded = value
    for _ in range(3):
        next_value = unquote(decoded)
        if next_value == decoded:
            return decoded
        decoded = next_value
    return decoded


def normalise_relative_image_path(value: object, location: str = "image") -> str:
    """Validate a portable relative image path without reading the image file."""

    if not isinstance(value, str) or not value or value != value.strip() or "\x00" in value:
        raise _error(location, "must be a non-empty, whitespace-trimmed relative path.")

    decoded = _decode_until_stable(value)
    if "\x00" in decoded:
        raise _error(location, "must not contain null bytes.")
    windows_path = PureWindowsPath(decoded)
    if (
        decoded.startswith(("/", "\\"))
        or windows_path.is_absolute()
        or windows_path.drive
        or re.match(r"^[a-zA-Z][a-zA-Z0-9+.-]*:", decoded)
    ):
        raise _error(location, "must be a controlled local relative path, not an absolute path or URI.")

    normalized = decoded.replace("\\", "/")
    posix_path = PurePosixPath(normalized)
    if posix_path.is_absolute() or not posix_path.parts or any(part in {".", ".."} for part in posix_path.parts):
        raise _error(location, "must not contain path traversal.")
    return posix_path.as_posix()


def _canonical_classes(value: object, location: str) -> tuple[str, ...]:
    if not isinstance(value, list):
        raise _error(location, "must be an array of exact canonical class names.")
    if not all(isinstance(name, str) for name in value):
        raise _error(location, "must contain only string class names.")
    names = tuple(value)
    unknown = sorted(set(names) - set(CANONICAL_CLASS_NAMES))
    if unknown:
        raise _error(location, f"contains unknown class names: {', '.join(unknown)}.")
    if len(set(names)) != len(names):
        raise _error(location, "must not contain duplicate class names.")
    return tuple(sorted(names, key=_CLASS_ORDER.__getitem__))


def _check_fields(data: Mapping[str, object], allowed: set[str], location: str) -> None:
    unexpected = sorted(set(data) - allowed)
    if unexpected:
        raise _error(location, f"contains unsupported field(s): {', '.join(unexpected)}.")


def _parse_case(value: object, index: int) -> ScenarioCase:
    location = f"cases[{index}]"
    case = _require_mapping(value, location)
    _check_fields(
        case,
        {"scenario_id", "description", "image", "expected_classes", "allowed_classes", "notes"},
        location,
    )
    required = ("scenario_id", "description", "image", "expected_classes")
    for field in required:
        if field not in case:
            raise _error(location, f"is missing required field {field!r}.")
    expected = _canonical_classes(case["expected_classes"], f"{location}.expected_classes")
    allowed = _canonical_classes(case.get("allowed_classes", []), f"{location}.allowed_classes")
    overlap = sorted(set(expected) & set(allowed), key=_CLASS_ORDER.__getitem__)
    if overlap:
        raise _error(location, f"must not repeat expected classes as allowed classes: {', '.join(overlap)}.")
    notes = case.get("notes")
    if notes is not None:
        notes = _require_text(notes, f"{location}.notes")
    return ScenarioCase(
        scenario_id=_require_identifier(case["scenario_id"], f"{location}.scenario_id"),
        description=_require_text(case["description"], f"{location}.description"),
        image=normalise_relative_image_path(case["image"], f"{location}.image"),
        expected_classes=expected,
        allowed_classes=allowed,
        notes=notes,
    )


def parse_case_suite(value: object) -> ScenarioSuite:
    """Validate a versioned, Git-safe suite of controlled scenarios."""

    suite = _require_mapping(value, "suite")
    _check_fields(suite, {"schema_version", "suite_id", "unexpected_detection_policy", "cases"}, "suite")
    for field in ("schema_version", "suite_id", "cases"):
        if field not in suite:
            raise _error("suite", f"is missing required field {field!r}.")
    if suite["schema_version"] != SCHEMA_VERSION:
        raise _error("suite.schema_version", f"must equal {SCHEMA_VERSION!r}.")
    policy = suite.get("unexpected_detection_policy", "report_only")
    if not isinstance(policy, str) or policy not in _UNEXPECTED_POLICIES:
        raise _error("suite.unexpected_detection_policy", "must be 'report_only' or 'fail'.")
    cases_value = suite["cases"]
    if not isinstance(cases_value, list) or not cases_value:
        raise _error("suite.cases", "must be a non-empty array.")
    cases = tuple(_parse_case(case, index) for index, case in enumerate(cases_value))
    scenario_ids = [case.scenario_id for case in cases]
    if len(set(scenario_ids)) != len(scenario_ids):
        raise _error("suite.cases", "must not contain duplicate scenario_id values.")
    return ScenarioSuite(
        suite_id=_require_identifier(suite["suite_id"], "suite.suite_id"),
        unexpected_detection_policy=policy,
        cases=cases,
    )


def _parse_detection(value: object, location: str) -> NormalizedDetection:
    detection = _require_mapping(value, location)
    _check_fields(detection, {"class_name", "confidence"}, location)
    for field in ("class_name", "confidence"):
        if field not in detection:
            raise _error(location, f"is missing required field {field!r}.")
    class_name = detection["class_name"]
    if not isinstance(class_name, str) or class_name not in CANONICAL_CLASS_NAMES:
        raise _error(f"{location}.class_name", "must be an exact approved canonical class name.")
    confidence = detection["confidence"]
    if isinstance(confidence, bool) or not isinstance(confidence, (int, float)) or not math.isfinite(float(confidence)):
        raise _error(f"{location}.confidence", "must be a finite number between 0 and 1.")
    if not 0 <= float(confidence) <= 1:
        raise _error(f"{location}.confidence", "must be between 0 and 1.")
    return NormalizedDetection(class_name=class_name, confidence=float(confidence))


def _parse_model_identity(value: object) -> Mapping[str, str]:
    model = _require_mapping(value, "prediction_fixture.model")
    _check_fields(model, {"filename", "sha256"}, "prediction_fixture.model")
    for field in ("filename", "sha256"):
        if field not in model:
            raise _error("prediction_fixture.model", f"is missing required field {field!r}.")
    filename = model["filename"]
    sha256 = model["sha256"]
    if (
        not isinstance(filename, str)
        or not filename
        or PurePosixPath(filename).name != filename
        or PureWindowsPath(filename).name != filename
    ):
        raise _error("prediction_fixture.model.filename", "must be a filename without path components.")
    if not isinstance(sha256, str) or not _SHA256_PATTERN.fullmatch(sha256):
        raise _error("prediction_fixture.model.sha256", "must be a lowercase 64-character SHA-256 checksum.")
    return {"filename": filename, "sha256": sha256}


def parse_prediction_fixture(value: object, suite: ScenarioSuite) -> PredictionFixture:
    """Validate normalized, replayable predictions for every suite scenario."""

    fixture = _require_mapping(value, "prediction_fixture")
    _check_fields(fixture, {"schema_version", "suite_id", "predictions", "model"}, "prediction_fixture")
    for field in ("schema_version", "suite_id", "predictions"):
        if field not in fixture:
            raise _error("prediction_fixture", f"is missing required field {field!r}.")
    if fixture["schema_version"] != SCHEMA_VERSION:
        raise _error("prediction_fixture.schema_version", f"must equal {SCHEMA_VERSION!r}.")
    if fixture["suite_id"] != suite.suite_id:
        raise _error("prediction_fixture.suite_id", "must exactly match suite.suite_id.")
    predictions_value = _require_mapping(fixture["predictions"], "prediction_fixture.predictions")
    expected_ids = {case.scenario_id for case in suite.cases}
    actual_ids = set(predictions_value)
    if actual_ids != expected_ids:
        missing = sorted(expected_ids - actual_ids)
        unexpected = sorted(actual_ids - expected_ids)
        details = []
        if missing:
            details.append(f"missing scenario IDs: {', '.join(missing)}")
        if unexpected:
            details.append(f"unknown scenario IDs: {', '.join(unexpected)}")
        raise _error("prediction_fixture.predictions", "; ".join(details) + ".")
    predictions: dict[str, tuple[NormalizedDetection, ...]] = {}
    for case in suite.cases:
        entries = predictions_value[case.scenario_id]
        if not isinstance(entries, list):
            raise _error(f"prediction_fixture.predictions.{case.scenario_id}", "must be an array.")
        predictions[case.scenario_id] = tuple(
            _parse_detection(entry, f"prediction_fixture.predictions.{case.scenario_id}[{index}]")
            for index, entry in enumerate(entries)
        )
    model = fixture.get("model")
    return PredictionFixture(
        suite_id=suite.suite_id,
        predictions=predictions,
        model=_parse_model_identity(model) if model is not None else None,
    )


def _metric_summary(true_positives: int, false_positives: int, false_negatives: int) -> dict[str, float | None]:
    precision_denominator = true_positives + false_positives
    recall_denominator = true_positives + false_negatives
    f1_denominator = (2 * true_positives) + false_positives + false_negatives
    return {
        "precision": (true_positives / precision_denominator) if precision_denominator else None,
        "recall": (true_positives / recall_denominator) if recall_denominator else None,
        "f1": (2 * true_positives / f1_denominator) if f1_denominator else None,
    }


def _ordered_classes(classes: set[str]) -> list[str]:
    return sorted(classes, key=_CLASS_ORDER.__getitem__)


def _validate_confidence_threshold(value: object) -> float:
    if isinstance(value, bool) or not isinstance(value, (int, float)) or not math.isfinite(float(value)):
        raise ScenarioRegressionError("confidence_threshold must be a finite number between 0 and 1.")
    threshold = float(value)
    if not 0 <= threshold <= 1:
        raise ScenarioRegressionError("confidence_threshold must be between 0 and 1.")
    return threshold


def evaluate_suite(
    suite: ScenarioSuite,
    fixture: PredictionFixture,
    *,
    confidence_threshold: float = 0.0,
) -> dict[str, object]:
    """Score fixture detections with deterministic class-presence semantics."""

    if fixture.suite_id != suite.suite_id:
        raise ScenarioRegressionError("prediction fixture suite_id does not match the supplied suite.")
    threshold = _validate_confidence_threshold(confidence_threshold)
    scenario_results: list[dict[str, object]] = []
    totals = {"true_positives": 0, "false_positives": 0, "false_negatives": 0}
    per_class_counts = {
        class_name: {"true_positives": 0, "false_positives": 0, "false_negatives": 0}
        for class_name in CANONICAL_CLASS_NAMES
    }

    for case in suite.cases:
        detections = fixture.predictions[case.scenario_id]
        detected = {item.class_name for item in detections if item.confidence >= threshold}
        expected = set(case.expected_classes)
        allowed = set(case.allowed_classes)
        true_positive_classes = expected & detected
        missed_classes = expected - detected
        unexpected_classes = detected - expected - allowed
        allowed_detected_classes = detected & allowed
        passed = not missed_classes and (
            suite.unexpected_detection_policy == "report_only" or not unexpected_classes
        )
        counts = {
            "true_positives": len(true_positive_classes),
            "false_positives": len(unexpected_classes),
            "false_negatives": len(missed_classes),
        }
        for key, count in counts.items():
            totals[key] += count
        for class_name in true_positive_classes:
            per_class_counts[class_name]["true_positives"] += 1
        for class_name in unexpected_classes:
            per_class_counts[class_name]["false_positives"] += 1
        for class_name in missed_classes:
            per_class_counts[class_name]["false_negatives"] += 1
        scenario_results.append(
            {
                "scenario_id": case.scenario_id,
                "description": case.description,
                "image": case.image,
                "notes": case.notes,
                "expected_classes": list(case.expected_classes),
                "allowed_classes": list(case.allowed_classes),
                "detected_classes": _ordered_classes(detected),
                "allowed_detected_classes": _ordered_classes(allowed_detected_classes),
                "true_positive_classes": _ordered_classes(true_positive_classes),
                "missed_classes": _ordered_classes(missed_classes),
                "unexpected_classes": _ordered_classes(unexpected_classes),
                "filtered_out_detection_count": len(detections) - sum(
                    item.confidence >= threshold for item in detections
                ),
                **counts,
                "metrics": _metric_summary(**counts),
                "passed": passed,
            }
        )

    scenarios_passed = sum(result["passed"] is True for result in scenario_results)
    aggregate = {
        "scenario_count": len(scenario_results),
        "scenarios_passed": scenarios_passed,
        "scenarios_failed": len(scenario_results) - scenarios_passed,
        **totals,
        **_metric_summary(**totals),
    }
    per_class = {
        class_name: {**counts, **_metric_summary(**counts)}
        for class_name, counts in per_class_counts.items()
    }
    return {
        "schema_version": SCHEMA_VERSION,
        "tool": {"name": TOOL_NAME, "version": TOOL_VERSION},
        "case_suite": {
            "suite_id": suite.suite_id,
            "unexpected_detection_policy": suite.unexpected_detection_policy,
        },
        "model": dict(fixture.model) if fixture.model is not None else None,
        "inference_settings": {
            "confidence_threshold": threshold,
            "threshold_semantics": "Detector operating threshold only; not a navigation-risk, proximity, or safety-policy threshold.",
        },
        "taxonomy": [{"id": class_id, "name": name} for class_id, name in APPROVED_TAXONOMY],
        "scenarios": scenario_results,
        "aggregate": aggregate,
        "per_class": per_class,
    }


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    try:
        with path.open("rb") as source:
            for chunk in iter(lambda: source.read(1024 * 1024), b""):
                digest.update(chunk)
    except OSError as exc:
        raise ScenarioRegressionError("Input checksum could not be computed.") from exc
    return digest.hexdigest()


def _unique_json_object(pairs: list[tuple[str, object]]) -> dict[str, object]:
    """Reject JSON duplicate keys before a parser can silently overwrite one."""

    result: dict[str, object] = {}
    for key, value in pairs:
        if key in result:
            raise _DuplicateJsonKeyError(key)
        result[key] = value
    return result


def _load_json(path: str | Path, label: str) -> tuple[Path, object]:
    source = Path(path).expanduser().resolve()
    if not source.exists() or not source.is_file():
        raise ScenarioRegressionError(f"{label} file is missing or is not a file.")
    try:
        return source, json.loads(
            source.read_text(encoding="utf-8"), object_pairs_hook=_unique_json_object
        )
    except _DuplicateJsonKeyError as exc:
        raise ScenarioRegressionError(f"{label} file contains duplicate JSON field {exc.args[0]!r}.") from exc
    except (OSError, UnicodeError, json.JSONDecodeError) as exc:
        raise ScenarioRegressionError(f"{label} file could not be read as UTF-8 JSON.") from exc


def load_case_suite(path: str | Path) -> tuple[Path, ScenarioSuite]:
    """Load a case suite from local JSON without reading image data."""

    source, payload = _load_json(path, "Case suite")
    return source, parse_case_suite(payload)


def load_prediction_fixture(path: str | Path, suite: ScenarioSuite) -> tuple[Path, PredictionFixture]:
    """Load saved normalized detections from local JSON."""

    source, payload = _load_json(path, "Prediction fixture")
    return source, parse_prediction_fixture(payload, suite)


def _is_within(path: Path, parent: Path) -> bool:
    try:
        path.relative_to(parent)
    except ValueError:
        return False
    return True


def prepare_output_directory(output_path: str | Path, *, overwrite: bool) -> Path:
    """Create an external report directory so generated output cannot enter Git."""

    output = Path(output_path).expanduser().resolve()
    if _is_within(output, _REPOSITORY_ROOT):
        raise ScenarioRegressionError("Report output must be outside the repository.")
    if output.exists() and not output.is_dir():
        raise ScenarioRegressionError("Report output path is not a directory.")
    if output.exists() and any(output.iterdir()) and not overwrite:
        raise ScenarioRegressionError("Report output directory is not empty. Use --overwrite to replace reports.")
    try:
        output.mkdir(parents=True, exist_ok=True)
    except OSError as exc:
        raise ScenarioRegressionError("Report output directory could not be created.") from exc
    return output


def _atomic_write_text(path: Path, content: str) -> None:
    temporary = path.with_name(f".{path.name}.{uuid4().hex}.tmp")
    try:
        temporary.write_text(content, encoding="utf-8")
        os.replace(temporary, path)
    except (OSError, UnicodeError) as exc:
        try:
            temporary.unlink(missing_ok=True)
        except OSError:
            pass
        raise ScenarioRegressionError("Scenario report could not be written.") from exc


def _display_metric(value: object) -> str:
    return "n/a" if value is None else f"{float(value):.6f}"


def render_markdown_report(report: Mapping[str, object]) -> str:
    """Render a deterministic human-readable companion to the JSON report."""

    aggregate = report["aggregate"]
    per_class = report["per_class"]
    scenarios = report["scenarios"]
    assert isinstance(aggregate, Mapping) and isinstance(per_class, Mapping) and isinstance(scenarios, list)
    lines = [
        "# Navigation Scenario Regression Evaluation",
        "",
        f"- Suite: `{report['case_suite']['suite_id']}`",  # type: ignore[index]
        f"- Unexpected detection policy: `{report['case_suite']['unexpected_detection_policy']}`",  # type: ignore[index]
        f"- Detector confidence threshold: `{report['inference_settings']['confidence_threshold']}`",  # type: ignore[index]
        "- Threshold scope: detector operating point only; not navigation risk or proximity policy.",
        "",
        "## Aggregate Metrics",
        "",
        "| Scenarios | Passed | Failed | TP | FP | FN | Precision | Recall | F1 |",
        "|---:|---:|---:|---:|---:|---:|---:|---:|---:|",
        "| {scenario_count} | {scenarios_passed} | {scenarios_failed} | {true_positives} | {false_positives} | {false_negatives} | {precision} | {recall} | {f1} |".format(
            **{
                **aggregate,
                "precision": _display_metric(aggregate["precision"]),
                "recall": _display_metric(aggregate["recall"]),
                "f1": _display_metric(aggregate["f1"]),
            }
        ),
        "",
        "## Scenario Results",
        "",
    ]
    for result in scenarios:
        assert isinstance(result, Mapping)
        lines.extend(
            [
                f"### {result['scenario_id']}",
                "",
                f"- Result: **{'PASS' if result['passed'] else 'FAIL'}**",
                f"- Expected: {', '.join(result['expected_classes']) or '(none)'}",  # type: ignore[arg-type]
                f"- Allowed: {', '.join(result['allowed_classes']) or '(none)'}",  # type: ignore[arg-type]
                f"- Detected: {', '.join(result['detected_classes']) or '(none)'}",  # type: ignore[arg-type]
                f"- Missed: {', '.join(result['missed_classes']) or '(none)'}",  # type: ignore[arg-type]
                f"- Unexpected: {', '.join(result['unexpected_classes']) or '(none)'}",  # type: ignore[arg-type]
                "- Counts: TP {true_positives}, FP {false_positives}, FN {false_negatives}".format(
                    **result
                ),
                "",
            ]
        )
    lines.extend(
        [
            "## Per-Class Metrics",
            "",
            "| Class | TP | FP | FN | Precision | Recall | F1 |",
            "|---|---:|---:|---:|---:|---:|---:|",
        ]
    )
    for class_name in CANONICAL_CLASS_NAMES:
        metrics = per_class[class_name]
        assert isinstance(metrics, Mapping)
        lines.append(
            "| {class_name} | {true_positives} | {false_positives} | {false_negatives} | {precision} | {recall} | {f1} |".format(
                **{
                    **metrics,
                    "class_name": class_name,
                    "precision": _display_metric(metrics["precision"]),
                    "recall": _display_metric(metrics["recall"]),
                    "f1": _display_metric(metrics["f1"]),
                }
            )
        )
    return "\n".join(lines) + "\n"


def write_reports(report: Mapping[str, object], output_path: str | Path, *, overwrite: bool) -> Path:
    """Write the two versioned reports without exposing absolute input paths."""

    output = prepare_output_directory(output_path, overwrite=overwrite)
    try:
        serialized = json.dumps(report, indent=2, allow_nan=False) + "\n"
    except (TypeError, ValueError) as exc:
        raise ScenarioRegressionError("Scenario report is not JSON-safe.") from exc
    _atomic_write_text(output / "scenario_evaluation.json", serialized)
    _atomic_write_text(output / "scenario_evaluation.md", render_markdown_report(report))
    return output


def run_fixture_evaluation(
    *,
    case_suite_path: str | Path,
    prediction_fixture_path: str | Path,
    output_path: str | Path,
    confidence_threshold: float = 0.0,
    overwrite: bool = False,
) -> dict[str, object]:
    """Load local JSON inputs, replay predictions, and write external reports."""

    case_source, suite = load_case_suite(case_suite_path)
    fixture_source, fixture = load_prediction_fixture(prediction_fixture_path, suite)
    report = evaluate_suite(suite, fixture, confidence_threshold=confidence_threshold)
    report["sources"] = {
        "case_suite": {"filename": case_source.name, "sha256": _sha256(case_source)},
        "prediction_fixture": {"filename": fixture_source.name, "sha256": _sha256(fixture_source)},
    }
    write_reports(report, output_path, overwrite=overwrite)
    return report
