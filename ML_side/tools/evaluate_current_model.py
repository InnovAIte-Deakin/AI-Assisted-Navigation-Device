"""Read-only baseline evaluation for a locally supplied WalkBuddy YOLO model."""

from __future__ import annotations

import argparse
import json
import re
import sys
from collections import Counter
from collections.abc import Callable, Mapping, Sequence
from dataclasses import dataclass
from pathlib import Path
from time import perf_counter
from typing import Any

import inspect_active_model as model_inspector


DEFAULT_MODEL_PATH = Path(__file__).resolve().parents[1] / "models" / "best.pt"
SUPPORTED_IMAGE_EXTENSIONS = frozenset({".jpg", ".jpeg", ".png"})
UNLABELLED_AUDIT_LABEL = (
    "Unlabelled inference audit — these results are not precision, recall, or "
    "mAP accuracy metrics."
)


class EvaluationError(Exception):
    """Raised when a baseline evaluation cannot be completed safely."""


@dataclass(frozen=True)
class ImageDiscovery:
    """Supported images and ignored files discovered in a supplied folder."""

    images: list[Path]
    skipped_files: list[Path]


def validate_model_path(model_path: str | Path) -> Path:
    """Resolve a local model path without downloading or changing it."""
    path = Path(model_path).expanduser().resolve()
    if not path.exists():
        raise EvaluationError(f"Model file is missing: {path}")
    if not path.is_file():
        raise EvaluationError(f"Model path is not a file: {path}")
    return path


def discover_images(images_path: str | Path) -> ImageDiscovery:
    """Return supported image files without reading, copying, or changing them."""
    path = Path(images_path).expanduser().resolve()
    if not path.exists():
        raise EvaluationError(f"Image folder is missing: {path}")
    if not path.is_dir():
        raise EvaluationError(f"Image path is not a directory: {path}")

    files = sorted(candidate for candidate in path.rglob("*") if candidate.is_file())
    images = [file for file in files if file.suffix.lower() in SUPPORTED_IMAGE_EXTENSIONS]
    skipped_files = [file for file in files if file not in images]
    if not images:
        raise EvaluationError(
            "No supported images found. Supported extensions are: .jpg, .jpeg, .png."
        )
    return ImageDiscovery(images=images, skipped_files=skipped_files)


def validate_dataset_yaml_path(dataset_yaml: str | Path) -> Path:
    """Validate a local dataset YAML and reject automatic-download directives."""
    path = Path(dataset_yaml).expanduser().resolve()
    if not path.exists():
        raise EvaluationError(f"Dataset YAML file is missing: {path}")
    if not path.is_file():
        raise EvaluationError(f"Dataset YAML path is not a file: {path}")
    if path.suffix.lower() not in {".yaml", ".yml"}:
        raise EvaluationError(f"Dataset YAML path must end in .yaml or .yml: {path}")

    try:
        contents = path.read_text(encoding="utf-8")
    except OSError as exc:
        raise EvaluationError(f"Dataset YAML could not be read: {path}") from exc

    if re.search(r"^\s*download\s*:", contents, flags=re.MULTILINE):
        raise EvaluationError(
            "Dataset YAML declares a download directive. Automatic dataset downloads are refused."
        )
    return path


def prepare_output_directory(output_path: str | Path, overwrite: bool) -> Path:
    """Create an output directory, refusing non-empty directories by default."""
    path = Path(output_path).expanduser().resolve()
    if path.exists() and not path.is_dir():
        raise EvaluationError(f"Output path is not a directory: {path}")
    if path.exists() and any(path.iterdir()) and not overwrite:
        raise EvaluationError(
            f"Output directory is not empty: {path}. Use --overwrite to replace result files."
        )
    try:
        path.mkdir(parents=True, exist_ok=True)
    except OSError as exc:
        raise EvaluationError(f"Output directory could not be created: {path}") from exc
    return path


def load_model_and_metadata(
    model_path: str | Path, yolo_loader: Callable[[str], Any] | None = None
) -> tuple[model_inspector.ModelMetadata, Any]:
    """Load only a supplied local model and extract its limited class metadata."""
    path = validate_model_path(model_path)
    try:
        loader = yolo_loader or model_inspector._get_yolo_loader()
    except model_inspector.InspectionError as exc:
        raise EvaluationError(str(exc)) from exc

    try:
        model = loader(str(path))
    except Exception as exc:
        raise EvaluationError("Model loading failed.") from exc

    try:
        class_names = model_inspector.normalise_class_names(model.names)
    except (AttributeError, model_inspector.InspectionError) as exc:
        raise EvaluationError("Model metadata is missing or has malformed model.names.") from exc

    metadata = model_inspector.ModelMetadata(
        path=path,
        size_bytes=path.stat().st_size,
        sha256=model_inspector.calculate_sha256(path),
        class_names=class_names,
    )
    return metadata, model


def _as_list(value: object) -> list[object]:
    """Convert common tensor-like values to a flat Python list."""
    if hasattr(value, "tolist"):
        value = value.tolist()  # type: ignore[union-attr]
    if isinstance(value, (list, tuple)):
        flattened: list[object] = []
        for item in value:
            flattened.extend(_as_list(item))
        return flattened
    return [value]


def _as_float(value: object) -> float:
    if hasattr(value, "item"):
        value = value.item()  # type: ignore[union-attr]
    values = _as_list(value)
    if len(values) != 1:
        raise ValueError("Expected a scalar value.")
    return float(values[0])


def _as_int(value: object) -> int:
    return int(_as_float(value))


def serialise_prediction_result(
    result: Any, image_path: Path, class_names: Mapping[int, str], inference_ms: float
) -> dict[str, object]:
    """Serialise only detection fields needed for a reproducible inference audit."""
    detections: list[dict[str, object]] = []
    boxes = getattr(result, "boxes", None)
    if boxes is not None:
        for box in boxes:
            coordinates = _as_list(getattr(box, "xyxy"))
            if len(coordinates) < 4:
                raise ValueError("Detection box is missing xyxy coordinates.")
            class_id = _as_int(getattr(box, "cls"))
            detections.append(
                {
                    "class_id": class_id,
                    "class_name": class_names.get(class_id, f"unknown_{class_id}"),
                    "confidence": _as_float(getattr(box, "conf")),
                    "bbox_xyxy": [float(value) for value in coordinates[:4]],
                }
            )

    return {
        "image_filename": image_path.name,
        "inference_time_ms": round(inference_ms, 3),
        "detection_count": len(detections),
        "detections": detections,
    }


def run_unlabelled_inference_audit(
    model: Any, discovery: ImageDiscovery, class_names: Mapping[int, str]
) -> tuple[list[dict[str, object]], list[dict[str, str]], dict[str, object]]:
    """Run local inference one image at a time without saving or copying images."""
    predictions: list[dict[str, object]] = []
    failed_images: list[dict[str, str]] = []
    inference_times: list[float] = []
    detection_counts: Counter[str] = Counter()

    for image_path in discovery.images:
        try:
            started = perf_counter()
            results = model.predict(source=str(image_path), save=False, verbose=False)
            inference_ms = (perf_counter() - started) * 1000
            if not results:
                raise ValueError("Model returned no result.")
            prediction = serialise_prediction_result(
                results[0], image_path, class_names, inference_ms
            )
        except Exception as exc:
            failed_images.append({"image_filename": image_path.name, "error": str(exc)})
            continue

        predictions.append(prediction)
        inference_times.append(float(prediction["inference_time_ms"]))
        for detection in prediction["detections"]:  # type: ignore[union-attr]
            detection_counts[str(detection["class_name"])] += 1

    summary = {
        "mode": "unlabelled_inference_audit",
        "result_label": UNLABELLED_AUDIT_LABEL,
        "total_discovered_images": len(discovery.images),
        "total_processed_images": len(predictions),
        "skipped_file_count": len(discovery.skipped_files),
        "failed_image_count": len(failed_images),
        "failed_images": failed_images,
        "average_inference_time_ms": (
            round(sum(inference_times) / len(inference_times), 3)
            if inference_times
            else None
        ),
        "detection_counts_by_class": dict(sorted(detection_counts.items())),
    }
    return predictions, failed_images, summary


def _metric_value(metrics: Any, mapping_keys: Sequence[str], attribute_names: Sequence[str]) -> float | None:
    results_dict = getattr(metrics, "results_dict", None)
    if isinstance(results_dict, Mapping):
        for key in mapping_keys:
            if key in results_dict:
                try:
                    return _as_float(results_dict[key])
                except (TypeError, ValueError):
                    return None

    box = getattr(metrics, "box", None)
    for attribute_name in attribute_names:
        value = getattr(box, attribute_name, None) if box is not None else None
        if value is None:
            value = getattr(metrics, attribute_name, None)
        if value is not None:
            try:
                return _as_float(value)
            except (TypeError, ValueError):
                return None
    return None


def _sequence_value(value: object, index: int) -> float | None:
    if value is None:
        return None
    try:
        return float(_as_list(value)[index])
    except (IndexError, TypeError, ValueError):
        return None


def extract_validation_metrics(
    metrics: Any, class_names: Mapping[int, str]
) -> dict[str, object]:
    """Extract available Ultralytics validation metrics without inventing values."""
    metric_specs = {
        "precision": (["metrics/precision(B)", "precision"], ["mp", "precision"]),
        "recall": (["metrics/recall(B)", "recall"], ["mr", "recall"]),
        "mAP50": (["metrics/mAP50(B)", "mAP50"], ["map50"]),
        "mAP50_95": (["metrics/mAP50-95(B)", "mAP50-95"], ["map"]),
    }
    extracted = {
        name: _metric_value(metrics, mapping_keys, attributes)
        for name, (mapping_keys, attributes) in metric_specs.items()
    }
    notes = [
        f"{name} was unavailable from the Ultralytics validation result."
        for name, value in extracted.items()
        if value is None
    ]

    image_counts = getattr(metrics, "nt_per_image", None)
    validation_image_count = len(_as_list(image_counts)) if image_counts is not None else None
    if validation_image_count is None:
        notes.append("Validation image count was unavailable from the Ultralytics result.")

    speed = getattr(metrics, "speed", None)
    inference_timing_ms = (
        {str(key): float(value) for key, value in speed.items()}
        if isinstance(speed, Mapping)
        else None
    )
    if inference_timing_ms is None:
        notes.append("Inference timing was unavailable from the Ultralytics result.")

    per_class_results: dict[str, dict[str, object]] = {}
    box = getattr(metrics, "box", None)
    class_indices = getattr(box, "ap_class_index", None) if box is not None else None
    if class_indices is not None:
        for index, raw_class_id in enumerate(_as_list(class_indices)):
            class_id = int(raw_class_id)
            per_class_results[str(class_id)] = {
                "class_name": class_names.get(class_id, f"unknown_{class_id}"),
                "precision": _sequence_value(getattr(box, "p", None), index),
                "recall": _sequence_value(getattr(box, "r", None), index),
                "mAP50": _sequence_value(getattr(box, "ap50", None), index),
                "mAP50_95": _sequence_value(getattr(box, "ap", None), index),
            }
    else:
        notes.append("Per-class validation results were unavailable from the Ultralytics result.")

    return {
        **extracted,
        "validation_image_count": validation_image_count,
        "inference_timing_ms": inference_timing_ms,
        "per_class_results": per_class_results or None,
        "metric_notes": notes,
    }


def _metadata_payload(metadata: model_inspector.ModelMetadata) -> dict[str, object]:
    return {
        "filename": metadata.path.name,
        "resolved_path": str(metadata.path),
        "file_size_bytes": metadata.size_bytes,
        "sha256": metadata.sha256,
        "class_count": len(metadata.class_names),
        "class_id_to_name": {str(key): value for key, value in metadata.class_names.items()},
    }


def _write_json(path: Path, payload: Mapping[str, object]) -> None:
    try:
        path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    except (OSError, TypeError) as exc:
        raise EvaluationError(f"Output write failed: {path}") from exc


def _write_report(path: Path, content: str) -> None:
    try:
        path.write_text(content, encoding="utf-8")
    except OSError as exc:
        raise EvaluationError(f"Output write failed: {path}") from exc


def _format_report(
    metadata: model_inspector.ModelMetadata, summary: Mapping[str, object]
) -> str:
    lines = [
        "# Current WalkBuddy Model Baseline",
        "",
        "## Model metadata",
        "",
        f"- Filename: `{metadata.path.name}`",
        f"- Resolved path: `{metadata.path}`",
        f"- File size: {metadata.size_bytes} bytes",
        f"- SHA-256: `{metadata.sha256}`",
        f"- Class count: {len(metadata.class_names)}",
        "- Class mapping:",
    ]
    lines.extend(f"  - {class_id}: `{name}`" for class_id, name in metadata.class_names.items())
    lines.extend(["", "## Evaluation result", ""])

    if summary["mode"] == "unlabelled_inference_audit":
        lines.extend(
            [
                f"> {UNLABELLED_AUDIT_LABEL}",
                "",
                f"- Processed images: {summary['total_processed_images']}",
                f"- Failed images: {summary['failed_image_count']}",
                f"- Unsupported files skipped: {summary['skipped_file_count']}",
                f"- Average inference time: {summary['average_inference_time_ms']} ms",
                "",
                "See `predictions.json` for per-image detections and failures.",
            ]
        )
    else:
        metrics = summary["validation_metrics"]
        lines.extend(
            [
                "Labelled validation uses Ultralytics validation metrics from the supplied local dataset YAML.",
                "",
                f"- Precision: {metrics['precision']}",
                f"- Recall: {metrics['recall']}",
                f"- mAP50: {metrics['mAP50']}",
                f"- mAP50-95: {metrics['mAP50_95']}",
                f"- Validation image count: {metrics['validation_image_count']}",
                "",
                "See `validation_metrics.json` for available per-class values and metric notes.",
            ]
        )
    return "\n".join(lines) + "\n"


def evaluate(
    *,
    model_path: str | Path,
    output_path: str | Path,
    images_path: str | Path | None = None,
    dataset_yaml: str | Path | None = None,
    overwrite: bool = False,
    yolo_loader: Callable[[str], Any] | None = None,
) -> dict[str, object]:
    """Evaluate a local model in exactly one safe, explicit mode."""
    if (images_path is None) == (dataset_yaml is None):
        raise EvaluationError("Provide exactly one of an image folder or a dataset YAML file.")

    model = validate_model_path(model_path)
    discovery = discover_images(images_path) if images_path is not None else None
    dataset = validate_dataset_yaml_path(dataset_yaml) if dataset_yaml is not None else None
    output = prepare_output_directory(output_path, overwrite)
    metadata, yolo_model = load_model_and_metadata(model, yolo_loader)
    metadata_payload = _metadata_payload(metadata)

    if discovery is not None:
        predictions, failed_images, summary = run_unlabelled_inference_audit(
            yolo_model, discovery, metadata.class_names
        )
        _write_json(output / "model_metadata.json", metadata_payload)
        _write_json(
            output / "predictions.json",
            {
                "mode": "unlabelled_inference_audit",
                "result_label": UNLABELLED_AUDIT_LABEL,
                "images": predictions,
                "failed_images": failed_images,
            },
        )
        _write_json(output / "summary.json", summary)
    else:
        try:
            validation_result = yolo_model.val(
                data=str(dataset),
                project=str(output),
                name="ultralytics_validation",
                exist_ok=True,
                plots=False,
                save_json=False,
                verbose=False,
            )
        except Exception as exc:
            raise EvaluationError("Labelled validation failed.") from exc

        validation_metrics = extract_validation_metrics(validation_result, metadata.class_names)
        summary = {
            "mode": "labelled_validation",
            "dataset_yaml": str(dataset),
            "validation_metrics": validation_metrics,
        }
        _write_json(output / "model_metadata.json", metadata_payload)
        _write_json(output / "validation_metrics.json", validation_metrics)
        _write_json(output / "summary.json", summary)

    _write_report(output / "baseline_report.md", _format_report(metadata, summary))
    return summary


def parse_args(argv: Sequence[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Read-only WalkBuddy model baseline evaluation."
    )
    parser.add_argument(
        "--model",
        default=DEFAULT_MODEL_PATH,
        help=f"Local YOLO model file (default: {DEFAULT_MODEL_PATH})",
    )
    mode = parser.add_mutually_exclusive_group(required=True)
    mode.add_argument("--images", help="Folder of local .jpg, .jpeg, or .png images.")
    mode.add_argument("--dataset-yaml", help="Local labelled YOLO dataset YAML for validation.")
    parser.add_argument("--output", required=True, help="Directory for generated result files.")
    parser.add_argument(
        "--overwrite",
        action="store_true",
        help="Allow writing result files into a non-empty output directory.",
    )
    return parser.parse_args(argv)


def main(argv: Sequence[str] | None = None) -> int:
    """Run the evaluator and return a non-zero exit code on a safe failure."""
    args = parse_args(argv)
    try:
        summary = evaluate(
            model_path=args.model,
            output_path=args.output,
            images_path=args.images,
            dataset_yaml=args.dataset_yaml,
            overwrite=args.overwrite,
        )
    except EvaluationError as exc:
        print(f"Evaluation failed: {exc}", file=sys.stderr)
        return 1

    print(f"Baseline evaluation complete: {args.output}")
    print(f"Mode: {summary['mode']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
