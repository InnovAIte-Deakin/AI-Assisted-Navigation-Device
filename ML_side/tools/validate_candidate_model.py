"""Offline validation for a candidate WalkBuddy navigation detection model.

This tool validates a supplied artifact and writes only reports. It never
renames, copies, promotes, exports, or replaces model weights.
"""

from __future__ import annotations

import argparse
import json
import math
import os
import sys
from collections.abc import Callable, Mapping, Sequence
from datetime import UTC, datetime
from numbers import Integral
from pathlib import Path
from typing import Any
from uuid import uuid4

import inspect_active_model as model_inspector
import validate_dataset_manifest as manifest_validator


SCHEMA_VERSION = "1.0.0"
TOOL_NAME = "validate_candidate_model"
TOOL_VERSION = "1.0.0"
ML_SIDE_DIR = Path(__file__).resolve().parents[1]
MODELS_DIR = (ML_SIDE_DIR / "models").resolve()
APPROVED_TAXONOMY = manifest_validator.APPROVED_TAXONOMY


class CandidateValidationError(Exception):
    """Raised for an unsafe report destination or invalid command invocation."""


def _timestamp_utc() -> str:
    return datetime.now(UTC).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def _check(name: str, status: str, message: str) -> dict[str, str]:
    return {"name": name, "status": status, "message": message}


def _is_within(path: Path, parent: Path) -> bool:
    try:
        path.relative_to(parent)
    except ValueError:
        return False
    return True


def prepare_output_directory(output_path: str | Path, overwrite: bool) -> Path:
    """Create a report directory while refusing model-weight locations."""
    path = Path(output_path).expanduser().resolve()
    if _is_within(path, MODELS_DIR):
        raise CandidateValidationError("Report output must not be written inside ML_side/models.")
    if path.exists() and not path.is_dir():
        raise CandidateValidationError("Report output path is not a directory.")
    if path.exists() and any(path.iterdir()) and not overwrite:
        raise CandidateValidationError(
            "Report output directory is not empty. Use --overwrite to replace report files."
        )
    try:
        path.mkdir(parents=True, exist_ok=True)
    except OSError as exc:
        raise CandidateValidationError("Report output directory could not be created.") from exc
    return path


def _safe_json(value: object) -> object:
    """Reject values that would make the report non-portable JSON."""
    if isinstance(value, float):
        if not math.isfinite(value):
            raise ValueError("Non-finite value")
        return value
    if value is None or isinstance(value, (str, int, bool)):
        return value
    if isinstance(value, Mapping):
        return {str(key): _safe_json(item) for key, item in value.items()}
    if isinstance(value, Sequence) and not isinstance(value, (str, bytes)):
        return [_safe_json(item) for item in value]
    raise ValueError("Non-serialisable value")


def _write_json(path: Path, payload: Mapping[str, object]) -> None:
    try:
        safe_payload = _safe_json(payload)
        _atomic_write_text(
            path,
            json.dumps(safe_payload, indent=2, sort_keys=True, allow_nan=False) + "\n",
        )
    except (OSError, TypeError, ValueError) as exc:
        raise CandidateValidationError("Candidate report JSON could not be written.") from exc


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
    """Render a path-safe human-readable report from the machine-readable data."""
    candidate = report["candidate"]
    assert isinstance(candidate, Mapping)
    lines = [
        "# Candidate Model Validation",
        "",
        f"- Verdict: **{report['verdict']}**",
        f"- File: `{candidate.get('filename')}`",
        f"- File size: {candidate.get('file_size_bytes')} bytes",
        f"- SHA-256: `{candidate.get('sha256')}`",
        f"- Class count: {candidate.get('class_count')}",
        "",
        "## Checks",
        "",
        "| Check | Status | Detail |",
        "| --- | --- | --- |",
    ]
    for check in report["checks"]:
        assert isinstance(check, Mapping)
        lines.append(f"| {check['name']} | {check['status']} | {check['message']} |")
    warnings = report["warnings"]
    if warnings:
        lines.extend(["", "## Warnings", ""])
        lines.extend(f"- {warning}" for warning in warnings)
    lines.extend(
        [
            "",
            "The smoke test confirms only that the supplied model executed on a local image. "
            "It does not establish detection quality or approve deployment.",
            "",
        ]
    )
    return "\n".join(lines)


def _candidate_stub(candidate_path: Path) -> dict[str, object]:
    return {
        "filename": candidate_path.name,
        "file_size_bytes": None,
        "sha256": None,
        "task": None,
        "class_count": None,
        "class_id_to_name": None,
        "ordered_class_names": None,
    }


def _has_strict_class_ids(names: object) -> bool:
    """Reject lossy IDs such as ``0.5`` before class metadata is normalised."""
    if isinstance(names, Mapping):
        raw_ids = names.keys()
    elif isinstance(names, Sequence) and not isinstance(names, (str, bytes)):
        raw_ids = range(len(names))
    else:
        return False
    for raw_id in raw_ids:
        if isinstance(raw_id, bool):
            return False
        if isinstance(raw_id, Integral):
            continue
        if (
            isinstance(raw_id, str)
            and raw_id.isascii()
            and raw_id.isdecimal()
            and raw_id == str(int(raw_id))
        ):
            continue
        return False
    return True


def validate_candidate(
    candidate_path: str | Path,
    *,
    smoke_image: str | Path | None = None,
    yolo_loader: Callable[[str], Any] | None = None,
) -> dict[str, object]:
    """Validate an artifact with injected loading and local-only optional smoke input."""
    path = Path(candidate_path).expanduser().resolve()
    candidate = _candidate_stub(path)
    checks: list[dict[str, str]] = []
    warnings: list[str] = []
    model: Any | None = None

    if not path.exists():
        checks.append(_check("artifact_exists", "fail", "Candidate artifact is missing."))
    elif not path.is_file():
        checks.append(_check("artifact_is_file", "fail", "Candidate path is not a regular file."))
    else:
        checks.append(_check("artifact_exists", "pass", "Candidate artifact exists."))
        try:
            size_bytes = path.stat().st_size
        except OSError:
            checks.append(_check("artifact_size", "fail", "Candidate artifact size could not be read."))
        else:
            candidate["file_size_bytes"] = size_bytes
            if size_bytes <= 0:
                checks.append(_check("artifact_size", "fail", "Candidate artifact is empty."))
            else:
                checks.append(_check("artifact_size", "pass", "Candidate artifact is non-empty."))
        try:
            candidate["sha256"] = model_inspector.calculate_sha256(path)
        except OSError:
            checks.append(_check("sha256", "fail", "Candidate checksum could not be computed."))
        else:
            checks.append(_check("sha256", "pass", "Candidate checksum was computed."))

        try:
            loader = yolo_loader or model_inspector._get_yolo_loader()
            model = loader(str(path))
        except Exception:
            checks.append(_check("model_load", "fail", "Candidate model could not be loaded."))
        else:
            checks.append(_check("model_load", "pass", "Candidate model loaded."))

    class_names: dict[int, str] | None = None
    if model is not None:
        try:
            task = getattr(model, "task")
        except Exception:
            warnings.append("Model task metadata was unavailable.")
            checks.append(_check("detection_task", "warning", "Model task metadata was unavailable."))
        else:
            candidate["task"] = task if isinstance(task, str) else None
            if task == "detect":
                checks.append(_check("detection_task", "pass", "Model task is detection."))
            elif task is None:
                warnings.append("Model task metadata was unavailable.")
                checks.append(_check("detection_task", "warning", "Model task metadata was unavailable."))
            else:
                checks.append(_check("detection_task", "fail", "Model task is not detection."))

        try:
            raw_class_names = model.names
            if not _has_strict_class_ids(raw_class_names):
                raise model_inspector.InspectionError("Model class IDs are malformed.")
            class_names = model_inspector.normalise_class_names(raw_class_names)
        except Exception:
            checks.append(
                _check("class_metadata", "fail", "Model class metadata is missing or malformed.")
            )
        else:
            candidate["class_count"] = len(class_names)
            candidate["class_id_to_name"] = {
                str(class_id): name for class_id, name in class_names.items()
            }
            candidate["ordered_class_names"] = [
                class_names[class_id] for class_id in sorted(class_names)
            ]
            if len(class_names) == len(APPROVED_TAXONOMY):
                checks.append(
                    _check("class_count", "pass", "Model class count is exactly eight.")
                )
            else:
                checks.append(
                    _check("class_count", "fail", "Model class count is not exactly eight.")
                )
            actual_taxonomy = list(class_names.items())
            if actual_taxonomy == list(APPROVED_TAXONOMY):
                checks.append(
                    _check("approved_taxonomy", "pass", "Class IDs and ordered names match the approved taxonomy.")
                )
            else:
                checks.append(
                    _check(
                        "approved_taxonomy",
                        "fail",
                        "Class IDs and ordered names do not match the approved taxonomy.",
                    )
                )

    try:
        _safe_json(candidate)
    except ValueError:
        checks.append(
            _check("report_metadata", "fail", "Model metadata is not safely serialisable.")
        )
    else:
        checks.append(
            _check("report_metadata", "pass", "Reported metadata is finite and serialisable.")
        )

    if model is None:
        checks.append(_check("smoke_inference", "fail", "Smoke inference could not run without a loaded model."))
    elif smoke_image is None:
        checks.append(_check("smoke_inference", "fail", "A local smoke image is required to confirm execution."))
    else:
        image_path = Path(smoke_image).expanduser().resolve()
        if not image_path.is_file():
            checks.append(_check("smoke_inference", "fail", "Smoke image is missing or not a file."))
        else:
            try:
                model.predict(source=str(image_path), save=False, verbose=False)
            except Exception:
                checks.append(_check("smoke_inference", "fail", "Candidate smoke inference failed."))
            else:
                checks.append(_check("smoke_inference", "pass", "Candidate smoke inference completed."))

    if any(check["status"] == "fail" for check in checks):
        verdict = "fail"
    elif warnings:
        verdict = "pass_with_warnings"
    else:
        verdict = "pass"
    return {
        "schema_version": SCHEMA_VERSION,
        "tool": {"name": TOOL_NAME, "version": TOOL_VERSION},
        "created_at_utc": _timestamp_utc(),
        "candidate": candidate,
        "approved_taxonomy": [
            {"id": class_id, "name": name} for class_id, name in APPROVED_TAXONOMY
        ],
        "checks": checks,
        "warnings": warnings,
        "verdict": verdict,
    }


def run_validation(
    *,
    candidate_path: str | Path,
    output_path: str | Path,
    smoke_image: str | Path | None = None,
    overwrite: bool = False,
    yolo_loader: Callable[[str], Any] | None = None,
) -> dict[str, object]:
    """Validate and write reports without making any change to model artifacts."""
    output = prepare_output_directory(output_path, overwrite)
    report = validate_candidate(
        candidate_path, smoke_image=smoke_image, yolo_loader=yolo_loader
    )
    _write_json(output / "candidate_model_report.json", report)
    try:
        _atomic_write_text(
            output / "candidate_model_report.md", render_markdown_report(report)
        )
    except (OSError, UnicodeError) as exc:
        raise CandidateValidationError("Candidate report Markdown could not be written.") from exc
    return report


def parse_args(argv: Sequence[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Offline validation for a candidate WalkBuddy detection model."
    )
    parser.add_argument("--model", required=True, help="Local candidate model file.")
    parser.add_argument("--output", required=True, help="Directory for validation reports.")
    parser.add_argument(
        "--smoke-image",
        required=True,
        help="Trusted local image used only to confirm model execution.",
    )
    parser.add_argument(
        "--overwrite",
        action="store_true",
        help="Allow report files to replace files in a non-empty output directory.",
    )
    return parser.parse_args(argv)


def main(argv: Sequence[str] | None = None) -> int:
    args = parse_args(argv)
    try:
        report = run_validation(
            candidate_path=args.model,
            output_path=args.output,
            smoke_image=args.smoke_image,
            overwrite=args.overwrite,
        )
    except CandidateValidationError as exc:
        print(f"Candidate validation failed: {exc}", file=sys.stderr)
        return 1
    print(f"Candidate validation verdict: {report['verdict']}")
    return 1 if report["verdict"] == "fail" else 0


if __name__ == "__main__":
    raise SystemExit(main())
