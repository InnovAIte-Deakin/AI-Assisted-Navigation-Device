"""Capture safe, startup-only lineage metadata for the active YOLO artifact."""

from __future__ import annotations

import hashlib
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from datetime import datetime, timezone
from importlib.metadata import version
from pathlib import Path
from typing import Any

from ml_contract import NAVIGATION_CLASSES


CHECKSUM_CHUNK_SIZE = 1024 * 1024
# Derived from the single canonical contract so this module never becomes a
# second, independently maintained taxonomy.
APPROVED_TAXONOMY: tuple[str, ...] = tuple(
    navigation_class.name for navigation_class in NAVIGATION_CLASSES
)


class ModelMetadataError(ValueError):
    """Raised when an otherwise loaded model has unusable public metadata."""


@dataclass(frozen=True)
class ModelLineage:
    """The intentionally limited model details safe to expose operationally."""

    loaded: bool
    filename: str
    sha256: str | None
    size_bytes: int | None
    num_classes: int | None
    classes: list[str]
    load_duration_ms: float
    loaded_at: str
    runtime: dict[str, Any]
    failure_category: str | None = None
    taxonomy_compatible: bool | None = None

    def as_dict(self) -> dict[str, Any]:
        """Return a copy suitable for the operational model-info endpoint."""
        return {
            "loaded": self.loaded,
            "filename": self.filename,
            "sha256": self.sha256,
            "size_bytes": self.size_bytes,
            "num_classes": self.num_classes,
            "classes": list(self.classes),
            "taxonomy_compatible": self.taxonomy_compatible,
            "load_duration_ms": self.load_duration_ms,
            "loaded_at": self.loaded_at,
            "runtime": dict(self.runtime),
            "failure_category": self.failure_category,
        }


def calculate_sha256(path: Path) -> str:
    """Return the SHA-256 of a local artifact without modifying it."""
    digest = hashlib.sha256()
    with path.open("rb") as model_file:
        for chunk in iter(lambda: model_file.read(CHECKSUM_CHUNK_SIZE), b""):
            digest.update(chunk)
    return digest.hexdigest()


def normalise_class_names(names: object) -> list[str]:
    """Validate Ultralytics ``model.names`` and return its ID-ordered labels."""
    if isinstance(names, Mapping):
        raw_items = names.items()
    elif isinstance(names, Sequence) and not isinstance(names, (str, bytes)):
        raw_items = enumerate(names)
    else:
        raise ModelMetadataError("model.names is missing or malformed")

    class_names: dict[int, str] = {}
    for raw_id, raw_name in raw_items:
        if isinstance(raw_id, bool):
            raise ModelMetadataError("model.names is missing or malformed")
        try:
            class_id = int(raw_id)
        except (TypeError, ValueError) as exc:
            raise ModelMetadataError("model.names is missing or malformed") from exc

        if class_id < 0 or class_id in class_names:
            raise ModelMetadataError("model.names is missing or malformed")
        if not isinstance(raw_name, str) or not raw_name.strip():
            raise ModelMetadataError("model.names is missing or malformed")
        class_names[class_id] = raw_name.strip()

    if not class_names:
        raise ModelMetadataError("model.names is missing or malformed")
    return [class_names[class_id] for class_id in sorted(class_names)]


def is_taxonomy_compatible(class_names: Sequence[str]) -> bool:
    """Report whether ordered class names exactly match the approved taxonomy.

    Matching is deliberately exact in count, identifier order, and canonical
    spelling. Legacy aliases such as ``office-chair`` remain valid when
    interpreting individual detections, but must never allow a differently
    trained artifact to satisfy the production model contract.
    """
    return tuple(class_names) == APPROVED_TAXONOMY


def runtime_details() -> dict[str, Any]:
    """Return runtime-version and compute-device information without failing startup."""
    try:
        ultralytics_version = version("ultralytics")
    except Exception:
        # Package metadata is optional; a malformed installation must not make
        # model readiness depend on reporting its version.
        ultralytics_version = None

    runtime: dict[str, Any] = {
        "ultralytics": ultralytics_version,
        "torch": None,
        "cuda_available": False,
        "device": "unknown",
    }
    try:
        import torch
        runtime["torch"] = getattr(torch, "__version__", None)
        cuda_available = bool(torch.cuda.is_available())
    except Exception:
        # This is optional operational introspection. A damaged or partial
        # PyTorch installation must not prevent an otherwise loaded model from
        # making the backend ready.
        return runtime

    runtime["cuda_available"] = cuda_available
    if not cuda_available:
        runtime["device"] = "cpu"
        return runtime

    try:
        runtime["device"] = f"cuda:0 ({torch.cuda.get_device_name(0)})"
    except Exception:
        runtime["device"] = "cuda"
    return runtime


def capture_model_lineage(
    model_path: Path, model: object, load_duration_ms: float
) -> ModelLineage:
    """Capture safe lineage once after an already-loaded local model succeeds."""
    path = model_path.resolve()
    if not path.is_file():
        raise ModelMetadataError("model artifact is not a file")
    try:
        class_names = normalise_class_names(model.names)
    except ModelMetadataError:
        raise
    except Exception as exc:
        raise ModelMetadataError("model.names is missing or malformed") from exc

    return ModelLineage(
        loaded=True,
        filename=path.name,
        sha256=calculate_sha256(path),
        size_bytes=path.stat().st_size,
        num_classes=len(class_names),
        classes=class_names,
        load_duration_ms=round(float(load_duration_ms), 3),
        loaded_at=datetime.now(timezone.utc).isoformat(),
        runtime=runtime_details(),
        taxonomy_compatible=is_taxonomy_compatible(class_names),
    )


def unavailable_model_lineage(
    model_path: Path, load_duration_ms: float, failure_category: str
) -> ModelLineage:
    """Create a public-safe record for a failed model load without error text."""
    return ModelLineage(
        loaded=False,
        filename=model_path.name,
        sha256=None,
        size_bytes=None,
        num_classes=None,
        classes=[],
        load_duration_ms=round(float(load_duration_ms), 3),
        loaded_at=datetime.now(timezone.utc).isoformat(),
        runtime=runtime_details(),
        failure_category=failure_category,
    )


def metadata_unavailable_model_lineage(
    model_path: Path, load_duration_ms: float
) -> ModelLineage:
    """Preserve readiness when a loaded model's optional lineage capture fails."""
    return ModelLineage(
        loaded=True,
        filename=model_path.name,
        sha256=None,
        size_bytes=None,
        num_classes=None,
        classes=[],
        load_duration_ms=round(float(load_duration_ms), 3),
        loaded_at=datetime.now(timezone.utc).isoformat(),
        runtime=runtime_details(),
        failure_category="model_metadata_unavailable",
    )
