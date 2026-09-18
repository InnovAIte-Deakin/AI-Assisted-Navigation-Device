"""Read-only inspector for locally supplied WalkBuddy YOLO model metadata."""

from __future__ import annotations

import argparse
import hashlib
import sys
from collections.abc import Callable, Mapping, Sequence
from dataclasses import dataclass
from pathlib import Path
from typing import Any


DEFAULT_MODEL_PATH = Path(__file__).resolve().parents[1] / "models" / "best.pt"
CHECKSUM_CHUNK_SIZE = 1024 * 1024


class InspectionError(Exception):
    """Raised when local model metadata cannot be safely inspected."""


@dataclass(frozen=True)
class ModelMetadata:
    """The limited metadata reported by this read-only utility."""

    path: Path
    size_bytes: int
    sha256: str
    class_names: dict[int, str]


def calculate_sha256(path: Path) -> str:
    """Return the SHA-256 checksum of a local file without modifying it."""
    digest = hashlib.sha256()
    with path.open("rb") as model_file:
        for chunk in iter(lambda: model_file.read(CHECKSUM_CHUNK_SIZE), b""):
            digest.update(chunk)
    return digest.hexdigest()


def normalise_class_names(names: object) -> dict[int, str]:
    """Validate and normalise the Ultralytics model.names ID/name mapping."""
    if isinstance(names, Mapping):
        raw_items = names.items()
    elif isinstance(names, Sequence) and not isinstance(names, (str, bytes)):
        raw_items = enumerate(names)
    else:
        raise InspectionError("Model metadata is missing or has malformed model.names.")

    class_names: dict[int, str] = {}
    for raw_id, raw_name in raw_items:
        if isinstance(raw_id, bool):
            raise InspectionError("Model metadata is missing or has malformed model.names.")
        try:
            class_id = int(raw_id)
        except (TypeError, ValueError) as exc:
            raise InspectionError(
                "Model metadata is missing or has malformed model.names."
            ) from exc

        if class_id < 0 or class_id in class_names:
            raise InspectionError("Model metadata is missing or has malformed model.names.")
        if not isinstance(raw_name, str) or not raw_name.strip():
            raise InspectionError("Model metadata is missing or has malformed model.names.")

        class_names[class_id] = raw_name.strip()

    if not class_names:
        raise InspectionError("Model metadata is missing or has malformed model.names.")

    return dict(sorted(class_names.items()))


def format_class_map(class_names: Mapping[int, str]) -> str:
    """Format a validated class map without exposing unrelated model internals."""
    return "\n".join(
        f"  {class_id}: {name}" for class_id, name in sorted(class_names.items())
    )


def _get_yolo_loader() -> Callable[[str], Any]:
    try:
        from ultralytics import YOLO
    except ImportError as exc:
        raise InspectionError(
            "Ultralytics dependency is unavailable. Use a backend environment "
            "with ultralytics installed."
        ) from exc
    return YOLO


def load_class_names(
    model_path: Path, yolo_loader: Callable[[str], Any] | None = None
) -> dict[int, str]:
    """Load and validate only the class metadata from a local model file."""
    loader = yolo_loader or _get_yolo_loader()
    try:
        model = loader(str(model_path))
    except Exception as exc:
        raise InspectionError("Model loading failed.") from exc

    try:
        names = model.names
    except Exception as exc:
        raise InspectionError("Model metadata is missing or has malformed model.names.") from exc

    return normalise_class_names(names)


def inspect_model(
    model_path: str | Path, yolo_loader: Callable[[str], Any] | None = None
) -> ModelMetadata:
    """Inspect a local model path without downloading, changing, or exporting it."""
    path = Path(model_path).expanduser().resolve()
    if not path.exists():
        raise InspectionError(f"Model file is missing: {path}")
    if not path.is_file():
        raise InspectionError(f"Model path is not a file: {path}")

    return ModelMetadata(
        path=path,
        size_bytes=path.stat().st_size,
        sha256=calculate_sha256(path),
        class_names=load_class_names(path, yolo_loader),
    )


def format_metadata(metadata: ModelMetadata) -> str:
    """Return the complete, intentionally limited inspection report."""
    return "\n".join(
        (
            f"Resolved model path: {metadata.path}",
            f"File size in bytes: {metadata.size_bytes}",
            f"SHA-256 checksum: {metadata.sha256}",
            f"Number of classes: {len(metadata.class_names)}",
            "Class ID-to-name mapping:",
            format_class_map(metadata.class_names),
        )
    )


def parse_args(argv: Sequence[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Read-only inspection of a local WalkBuddy YOLO model."
    )
    parser.add_argument(
        "model_path",
        nargs="?",
        default=DEFAULT_MODEL_PATH,
        help=f"Local model to inspect (default: {DEFAULT_MODEL_PATH})",
    )
    return parser.parse_args(argv)


def main(argv: Sequence[str] | None = None) -> int:
    """Run the inspector and return a non-zero code when inspection fails."""
    args = parse_args(argv)
    try:
        metadata = inspect_model(args.model_path)
    except InspectionError as exc:
        print(f"Inspection failed: {exc}", file=sys.stderr)
        return 1

    print(format_metadata(metadata))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
