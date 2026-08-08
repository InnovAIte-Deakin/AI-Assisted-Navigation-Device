"""Read-only quality inspection for local YOLO-format candidate datasets.

The tool deliberately reuses the WalkBuddy manifest validator's approved
taxonomy and path-safety helpers.  It never downloads, modifies, or copies
dataset files.  Reports are deterministic apart from ``execution.time_utc``.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import math
import re
import sys
from collections import Counter, defaultdict
from collections.abc import Mapping, Sequence
from datetime import UTC, datetime
from pathlib import Path

import validate_dataset_manifest as manifest_validator


TOOL_NAME = "inspect_candidate_dataset"
TOOL_VERSION = "1.0.0"
SPLIT_KEYS: tuple[tuple[str, tuple[str, ...]], ...] = (
    ("train", ("train",)),
    ("validation", ("validation", "val")),
    ("test", ("test",)),
)
APPROVED_TAXONOMY = manifest_validator.APPROVED_TAXONOMY
APPROVED_TARGETS = manifest_validator.APPROVED_TARGETS
IMAGE_EXTENSIONS = manifest_validator.IMAGE_EXTENSIONS


class CandidateInspectionError(Exception):
    """Raised for an input that cannot be inspected safely."""


def _issue(location: str, message: str) -> dict[str, str]:
    return {"location": location, "message": message}


def _normalise_relative_path(value: str) -> str:
    return "/".join(part for part in value.replace("\\", "/").split("/") if part not in {"", "."})


def _relative_path(root: Path, path: Path) -> str:
    return path.relative_to(root).as_posix()


def _resolves_beneath(root: Path, path: Path) -> bool:
    try:
        path.resolve().relative_to(root.resolve())
    except (OSError, RuntimeError, ValueError):
        return False
    return True


def _sort_issues(issues: list[dict[str, str]]) -> list[dict[str, str]]:
    return sorted(issues, key=lambda item: (item["location"], item["message"]))


def _safe_resolve(root: Path, raw_path: object, location: str, errors: list[dict[str, str]]) -> Path | None:
    is_safe, reason = manifest_validator._is_safe_relative_path(raw_path)
    if not is_safe:
        errors.append(_issue(location, reason or "must be a safe relative path."))
        return None
    assert isinstance(raw_path, str)
    resolved = manifest_validator._resolve_dataset_reference(root, raw_path.strip())
    if resolved is None:
        errors.append(_issue(location, "resolves outside the supplied dataset root."))
    return resolved


def _load_structured_file(path: Path, description: str) -> dict[str, object]:
    try:
        text = path.read_text(encoding="utf-8-sig")
    except FileNotFoundError as exc:
        raise CandidateInspectionError(f"{description} is missing: {path}") from exc
    except OSError as exc:
        raise CandidateInspectionError(f"{description} could not be read: {path}") from exc

    if path.suffix.casefold() == ".json":
        try:
            loaded = json.loads(text)
        except json.JSONDecodeError as exc:
            raise CandidateInspectionError(f"{description} is not valid JSON: {path}") from exc
    else:
        try:
            import yaml
        except ImportError as exc:
            raise CandidateInspectionError(
                f"{description} requires PyYAML for this YAML file; no dependency was installed."
            ) from exc
        try:
            loaded = yaml.safe_load(text)
        except yaml.YAMLError as exc:
            raise CandidateInspectionError(f"{description} is not valid YAML: {path}") from exc

    if not isinstance(loaded, dict):
        raise CandidateInspectionError(f"{description} root must be an object: {path}")
    return loaded


def _source_taxonomy(dataset_yaml: Mapping[str, object], errors: list[dict[str, str]]) -> dict[int, str]:
    names = dataset_yaml.get("names")
    taxonomy: dict[int, str] = {}
    if isinstance(names, list):
        for class_id, class_name in enumerate(names):
            if not isinstance(class_name, str) or not class_name.strip():
                errors.append(_issue(f"$.names[{class_id}]", "must be a non-empty class name."))
            else:
                taxonomy[class_id] = class_name.strip()
    elif isinstance(names, Mapping):
        for raw_id, class_name in names.items():
            if isinstance(raw_id, bool):
                errors.append(_issue("$.names", "contains a boolean rather than an integer class ID."))
                continue
            try:
                class_id = int(raw_id)
            except (TypeError, ValueError):
                errors.append(_issue("$.names", f"contains non-integer class ID {raw_id!r}."))
                continue
            if isinstance(raw_id, str) and raw_id.strip() != str(class_id):
                errors.append(_issue("$.names", f"contains malformed class ID {raw_id!r}."))
                continue
            if class_id < 0:
                errors.append(_issue("$.names", f"contains negative class ID {class_id}."))
            elif not isinstance(class_name, str) or not class_name.strip():
                errors.append(_issue(f"$.names[{class_id}]", "must be a non-empty class name."))
            elif class_id in taxonomy:
                errors.append(_issue("$.names", f"contains duplicate class ID {class_id}."))
            else:
                taxonomy[class_id] = class_name.strip()
    else:
        errors.append(_issue("$.names", "is required and must be a list or an ID-to-name object."))

    if not taxonomy:
        errors.append(_issue("$.names", "must define at least one source class."))
    for name, count in Counter(value.casefold() for value in taxonomy.values()).items():
        if count > 1:
            errors.append(_issue("$.names", f"contains duplicate source class name {name!r}."))
    return dict(sorted(taxonomy.items()))


def _resolve_layout(
    dataset_root: Path, dataset_yaml: Mapping[str, object], errors: list[dict[str, str]]
) -> dict[str, dict[str, Path | str | None]]:
    yaml_root_value = dataset_yaml.get("path", ".")
    yaml_root = _safe_resolve(dataset_root, yaml_root_value, "$.path", errors)
    if yaml_root is None:
        return {}
    if not yaml_root.is_dir():
        errors.append(_issue("$.path", "does not resolve to an existing directory beneath the dataset root."))
        return {}

    layout: dict[str, dict[str, Path | str | None]] = {}
    seen_image_directories: dict[Path, str] = {}
    for canonical_name, yaml_names in SPLIT_KEYS:
        raw_split_path: object | None = next(
            (dataset_yaml[key] for key in yaml_names if key in dataset_yaml), None
        )
        if raw_split_path is None:
            if canonical_name == "test":
                continue
            errors.append(_issue(f"$.{yaml_names[0]}", "is required for candidate dataset inspection."))
            continue
        image_directory = _safe_resolve(
            yaml_root, raw_split_path, f"$.{yaml_names[0]}", errors
        )
        if image_directory is None:
            continue
        if not image_directory.is_dir():
            errors.append(
                _issue(f"$.{yaml_names[0]}", "does not resolve to an existing split directory.")
            )
            continue
        prior_split = seen_image_directories.get(image_directory)
        if prior_split is not None:
            errors.append(
                _issue(
                    f"$.{yaml_names[0]}",
                    f"normalizes to the same image directory as the {prior_split!r} split.",
                )
            )
        seen_image_directories[image_directory] = canonical_name
        label_directory = _derive_label_directory(image_directory)
        layout[canonical_name] = {
            "declared_path": _normalise_relative_path(str(raw_split_path)),
            "image_directory": image_directory,
            "label_directory": label_directory,
        }
    return layout


def _derive_label_directory(image_directory: Path) -> Path:
    """Derive the paired labels directory for common YOLO directory layouts."""
    parts = list(image_directory.parts)
    image_indices = [index for index, part in enumerate(parts) if part.casefold() == "images"]
    if image_indices:
        parts[image_indices[-1]] = "labels"
        return Path(*parts)
    return image_directory.parent / "labels"


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as source:
        for chunk in iter(lambda: source.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _image_dimensions(path: Path) -> tuple[int, int]:
    try:
        from PIL import Image, UnidentifiedImageError
    except ImportError as exc:
        raise CandidateInspectionError("Pillow is unavailable for requested image decoding.") from exc
    try:
        with Image.open(path) as image:
            image.verify()
        with Image.open(path) as image:
            width, height = image.size
    except (OSError, SyntaxError, UnidentifiedImageError, ValueError) as exc:
        raise CandidateInspectionError(str(exc)) from exc
    if width < 1 or height < 1:
        raise CandidateInspectionError("image dimensions must be positive.")
    return int(width), int(height)


def _pillow_available() -> bool:
    """Return whether the already-installed optional decoder can be imported."""
    try:
        import PIL  # noqa: F401
    except ImportError:
        return False
    return True


def _read_group_map(path: Path | None, dataset_root: Path, errors: list[dict[str, str]]) -> dict[str, str] | None:
    if path is None:
        return None
    loaded = _load_structured_file(path, "Group mapping file")
    raw_groups = loaded.get("groups", loaded)
    if not isinstance(raw_groups, Mapping):
        errors.append(_issue("$.groups", "must be an object mapping relative image paths to group IDs."))
        return {}
    groups: dict[str, str] = {}
    for raw_path, raw_group_id in raw_groups.items():
        location = f"$.groups[{raw_path!r}]"
        is_safe, reason = manifest_validator._is_safe_relative_path(raw_path)
        if not is_safe:
            errors.append(_issue(location, reason or "must be a safe relative image path."))
            continue
        if not isinstance(raw_path, str) or not isinstance(raw_group_id, str) or not raw_group_id.strip():
            errors.append(_issue(location, "must map a relative image path to a non-empty group ID."))
            continue
        resolved = manifest_validator._resolve_dataset_reference(dataset_root, raw_path)
        if resolved is None:
            errors.append(_issue(location, "resolves outside the supplied dataset root."))
            continue
        normalised = _normalise_relative_path(raw_path).casefold()
        if normalised in groups:
            errors.append(_issue(location, "duplicates a normalized group-map image path."))
        else:
            groups[normalised] = raw_group_id.strip()
    return groups


def _mapping_summary(
    metadata: Mapping[str, object] | None,
    source_taxonomy: Mapping[int, str],
    errors: list[dict[str, str]],
    warnings: list[dict[str, str]],
) -> tuple[dict[int, dict[str, object]], dict[int, str], dict[int, str]]:
    mapping_entries = metadata.get("class_mapping", []) if metadata is not None else []
    excluded_entries = metadata.get("excluded_source_classes", []) if metadata is not None else []
    unmapped_entries = metadata.get("unmapped_source_classes", []) if metadata is not None else []
    if not isinstance(mapping_entries, list):
        errors.append(_issue("$.class_mapping", "must be a list of explicit source-to-target mappings."))
        mapping_entries = []
    if not isinstance(excluded_entries, list):
        errors.append(_issue("$.excluded_source_classes", "must be a list."))
        excluded_entries = []
    if not isinstance(unmapped_entries, list):
        errors.append(_issue("$.unmapped_source_classes", "must be a list."))
        unmapped_entries = []

    mappings: dict[int, dict[str, object]] = {}
    for index, entry in enumerate(mapping_entries):
        location = f"$.class_mapping[{index}]"
        if not isinstance(entry, Mapping):
            errors.append(_issue(location, "must be an object."))
            continue
        source_id = entry.get("source_class_id")
        target_id = entry.get("target_class_id")
        target_name = entry.get("target_class_name")
        rationale = entry.get("mapping_rationale")
        if not isinstance(source_id, int) or isinstance(source_id, bool) or source_id not in source_taxonomy:
            errors.append(_issue(f"{location}.source_class_id", "must identify a source class defined by the dataset YAML."))
            continue
        if not isinstance(target_id, int) or isinstance(target_id, bool) or APPROVED_TARGETS.get(target_id) != target_name:
            errors.append(_issue(location, "must map to a matching approved WalkBuddy target ID/name pair."))
            continue
        if not isinstance(rationale, str) or not rationale.strip():
            errors.append(_issue(f"{location}.mapping_rationale", "must be a non-empty explicit rationale."))
            continue
        if source_id in mappings:
            errors.append(_issue(location, f"duplicates a mapping for source class ID {source_id}."))
            continue
        mappings[source_id] = {
            "target_class_id": target_id,
            "target_class_name": target_name,
            "mapping_rationale": rationale.strip(),
        }

    def decision_entries(raw_entries: object, category: str) -> dict[int, str]:
        decisions: dict[int, str] = {}
        assert isinstance(raw_entries, list)
        for index, entry in enumerate(raw_entries):
            location = f"$.{category}[{index}]"
            if not isinstance(entry, Mapping):
                errors.append(_issue(location, "must be an object."))
                continue
            source_id = entry.get("source_class_id")
            reason = entry.get("reason")
            if not isinstance(source_id, int) or isinstance(source_id, bool) or source_id not in source_taxonomy:
                errors.append(_issue(f"{location}.source_class_id", "must identify a source class defined by the dataset YAML."))
                continue
            if not isinstance(reason, str) or not reason.strip():
                errors.append(_issue(f"{location}.reason", "must be a non-empty reason."))
                continue
            if source_id in decisions:
                errors.append(_issue(location, f"duplicates a decision for source class ID {source_id}."))
                continue
            decisions[source_id] = reason.strip()
        return decisions

    excluded = decision_entries(excluded_entries, "excluded_source_classes")
    unmapped = decision_entries(unmapped_entries, "unmapped_source_classes")
    for source_id in sorted(set(mappings) & (set(excluded) | set(unmapped))):
        errors.append(_issue("$.class_mapping", f"source class ID {source_id} cannot be both mapped and excluded or unmapped."))
    for source_id in sorted(set(excluded) & set(unmapped)):
        errors.append(_issue("$.excluded_source_classes", f"source class ID {source_id} cannot be both excluded and unmapped."))
    for source_id, source_name in source_taxonomy.items():
        if source_id not in mappings and source_id not in excluded and source_id not in unmapped:
            warnings.append(
                _issue(
                    "$.class_mapping",
                    f"source class {source_id}:{source_name} has no explicit mapping, exclusion, or unmapped decision.",
                )
            )
    return mappings, excluded, unmapped


def _parse_label_file(
    label_path: Path,
    display_path: str,
    source_taxonomy: Mapping[int, str],
    mappings: Mapping[int, Mapping[str, object]],
    excluded: Mapping[int, str],
    errors: list[dict[str, str]],
) -> tuple[list[dict[str, object]], int, bool]:
    try:
        lines = label_path.read_text(encoding="utf-8-sig").splitlines()
    except (OSError, UnicodeDecodeError) as exc:
        errors.append(_issue(display_path, f"label file could not be read as UTF-8: {exc}"))
        return [], 1, False
    annotations: list[dict[str, object]] = []
    invalid_rows = 0
    contains_annotation_text = False
    for line_number, line in enumerate(lines, start=1):
        if not line.strip():
            continue
        contains_annotation_text = True
        location = f"{display_path}:{line_number}"
        fields = line.split()
        if len(fields) != 5:
            errors.append(_issue(location, "YOLO label rows must contain exactly 5 fields."))
            invalid_rows += 1
            continue
        raw_class_id, *raw_values = fields
        if re.fullmatch(r"[0-9]+", raw_class_id) is None:
            errors.append(_issue(location, "class ID must be a non-negative integer."))
            invalid_rows += 1
            continue
        class_id = int(raw_class_id)
        if class_id not in source_taxonomy:
            errors.append(_issue(location, f"class ID {class_id} is outside the source YAML taxonomy."))
            invalid_rows += 1
            continue
        try:
            x_center, y_center, width, height = (float(value) for value in raw_values)
        except ValueError:
            errors.append(_issue(location, "bounding-box coordinates must be numeric."))
            invalid_rows += 1
            continue
        values = (x_center, y_center, width, height)
        if not all(math.isfinite(value) for value in values):
            errors.append(_issue(location, "bounding-box coordinates must be finite."))
            invalid_rows += 1
            continue
        if width <= 0 or height <= 0:
            errors.append(_issue(location, "bounding-box width and height must be positive."))
            invalid_rows += 1
            continue
        if (
            x_center < 0
            or y_center < 0
            or x_center > 1
            or y_center > 1
            or x_center - width / 2 < 0
            or x_center + width / 2 > 1
            or y_center - height / 2 < 0
            or y_center + height / 2 > 1
        ):
            errors.append(_issue(location, "bounding box extends outside normalized YOLO bounds."))
            invalid_rows += 1
            continue
        mapping = mappings.get(class_id)
        annotations.append(
            {
                "source_class_id": class_id,
                "source_class_name": source_taxonomy[class_id],
                "target_class_id": mapping.get("target_class_id") if mapping else None,
                "target_class_name": mapping.get("target_class_name") if mapping else None,
                "excluded": class_id in excluded,
                "x_center": x_center,
                "y_center": y_center,
                "width": width,
                "height": height,
            }
        )
    return annotations, invalid_rows, not contains_annotation_text


def _scan_split(
    split_name: str,
    layout: Mapping[str, Path | str | None],
    dataset_root: Path,
    source_taxonomy: Mapping[int, str],
    mappings: Mapping[int, Mapping[str, object]],
    excluded: Mapping[int, str],
    *,
    decode_images: bool,
    checksums: bool,
    errors: list[dict[str, str]],
    warnings: list[dict[str, str]],
) -> tuple[dict[str, object], list[dict[str, object]]]:
    image_directory = layout["image_directory"]
    label_directory = layout["label_directory"]
    assert isinstance(image_directory, Path) and isinstance(label_directory, Path)
    images: list[Path] = []
    for path in image_directory.rglob("*"):
        if not path.is_file() or path.suffix.casefold() not in IMAGE_EXTENSIONS:
            continue
        if not _resolves_beneath(dataset_root, path):
            errors.append(
                _issue(_relative_path(dataset_root, path), "image symlink resolves outside the supplied dataset root.")
            )
            continue
        images.append(path)
    images.sort(key=lambda path: _relative_path(dataset_root, path).casefold())
    unsupported = sorted(
        _relative_path(dataset_root, path)
        for path in image_directory.rglob("*")
        if path.is_file() and path.suffix.casefold() not in IMAGE_EXTENSIONS
    )
    if unsupported:
        warnings.append(
            _issue(
                f"splits.{split_name}",
                f"contains {len(unsupported)} file(s) with unsupported image extensions.",
            )
        )

    label_paths: dict[str, Path] = {}
    if label_directory.is_dir():
        for path in sorted(label_directory.rglob("*.txt"), key=lambda item: item.as_posix().casefold()):
            if not _resolves_beneath(dataset_root, path):
                errors.append(
                    _issue(_relative_path(dataset_root, path), "label symlink resolves outside the supplied dataset root.")
                )
                continue
            key = path.relative_to(label_directory).with_suffix("").as_posix().casefold()
            label_paths[key] = path
    else:
        warnings.append(_issue(f"splits.{split_name}", "paired labels directory is missing."))

    records: list[dict[str, object]] = []
    image_keys: set[str] = set()
    invalid_annotation_count = 0
    for image_path in images:
        relative_image = _relative_path(dataset_root, image_path)
        image_key = image_path.relative_to(image_directory).with_suffix("").as_posix().casefold()
        image_keys.add(image_key)
        label_path = label_paths.get(image_key)
        annotations: list[dict[str, object]] = []
        label_is_empty = False
        if label_path is None:
            warnings.append(_issue(relative_image, "image has no paired YOLO label file."))
        else:
            annotations, invalid_rows, label_is_empty = _parse_label_file(
                label_path,
                _relative_path(dataset_root, label_path),
                source_taxonomy,
                mappings,
                excluded,
                errors,
            )
            invalid_annotation_count += invalid_rows
        dimensions: tuple[int, int] | None = None
        if decode_images:
            try:
                dimensions = _image_dimensions(image_path)
            except CandidateInspectionError as exc:
                errors.append(_issue(relative_image, f"image is unreadable or corrupt: {exc}"))
        checksum: str | None = None
        if checksums:
            try:
                checksum = _sha256(image_path)
            except OSError as exc:
                errors.append(_issue(relative_image, f"image checksum could not be read: {exc}"))
        records.append(
            {
                "split": split_name,
                "image_path": relative_image,
                "label_path": _relative_path(dataset_root, label_path) if label_path is not None else None,
                "source_sample_identifier": image_path.stem.casefold(),
                "annotations": annotations,
                "label_is_empty": label_is_empty,
                "checksum": checksum,
                "width": dimensions[0] if dimensions else None,
                "height": dimensions[1] if dimensions else None,
            }
        )
    orphan_labels = sorted(
        _relative_path(dataset_root, label_path)
        for key, label_path in label_paths.items()
        if key not in image_keys
    )
    for orphan in orphan_labels:
        warnings.append(_issue(orphan, "label has no paired supported image file."))
    empty_labels = sorted(
        record["label_path"]
        for record in records
        if record["label_path"] is not None and record["label_is_empty"]
    )
    return (
        {
            "declared_path": layout["declared_path"],
            "image_directory": _relative_path(dataset_root, image_directory),
            "label_directory": _relative_path(dataset_root, label_directory),
            "image_count": len(images),
            "label_file_count": len(label_paths),
            "images_without_labels": sorted(
                record["image_path"] for record in records if record["label_path"] is None
            ),
            "labels_without_images": orphan_labels,
            "empty_label_files": empty_labels,
            "unsupported_image_files": unsupported,
            "invalid_annotation_count": invalid_annotation_count,
        },
        records,
    )


def _analysis_findings(
    records: Sequence[Mapping[str, object]],
    group_map: Mapping[str, str] | None,
    errors: list[dict[str, str]],
    warnings: list[dict[str, str]],
) -> dict[str, object]:
    sample_ids: dict[str, list[Mapping[str, object]]] = defaultdict(list)
    checksums: dict[str, list[Mapping[str, object]]] = defaultdict(list)
    groups: dict[str, list[Mapping[str, object]]] = defaultdict(list)
    normalised_paths: dict[str, list[Mapping[str, object]]] = defaultdict(list)
    unused_groups = set(group_map or {})
    for record in records:
        image_path = str(record["image_path"])
        sample_ids[str(record["source_sample_identifier"])].append(record)
        normalised_paths[_normalise_relative_path(image_path).casefold()].append(record)
        checksum = record.get("checksum")
        if isinstance(checksum, str):
            checksums[checksum].append(record)
        if group_map is not None:
            group_id = group_map.get(_normalise_relative_path(image_path).casefold())
            if group_id is not None:
                groups[group_id].append(record)
                unused_groups.discard(_normalise_relative_path(image_path).casefold())
            else:
                warnings.append(_issue(image_path, "has no supplied group identifier."))

    def duplicate_entries(values: Mapping[str, Sequence[Mapping[str, object]]], field: str) -> list[dict[str, object]]:
        return [
            {
                field: key,
                "images": sorted(str(record["image_path"]) for record in entries),
                "splits": sorted({str(record["split"]) for record in entries}),
            }
            for key, entries in sorted(values.items())
            if len(entries) > 1
        ]

    duplicate_sample_identifiers = duplicate_entries(sample_ids, "sample_identifier")
    duplicate_normalised_paths = duplicate_entries(normalised_paths, "normalized_path")
    duplicate_checksums = duplicate_entries(checksums, "sha256")
    cross_split_duplicates = [entry for entry in duplicate_checksums if len(entry["splits"]) > 1]
    group_leakage = [entry for entry in duplicate_entries(groups, "group_id") if len(entry["splits"]) > 1]
    if duplicate_sample_identifiers:
        warnings.append(_issue("duplicates.sample_identifiers", "duplicate filename-stem sample identifiers were found."))
    if duplicate_normalised_paths:
        errors.append(_issue("duplicates.normalized_paths", "the same normalized image path was listed more than once."))
    if duplicate_checksums:
        warnings.append(_issue("duplicates.checksums", "identical image checksums were found."))
    for entry in cross_split_duplicates:
        errors.append(
            _issue("leakage.image_checksums", f"identical image checksum is present across {entry['splits']!r}.")
        )
    for entry in group_leakage:
        errors.append(_issue("leakage.groups", f"group {entry['group_id']!r} is present across {entry['splits']!r}."))
    if group_map is None:
        warnings.append(
            _issue(
                "leakage.groups",
                "no group mapping was supplied; filename similarity was not used to infer group leakage.",
            )
        )
    for unused_path in sorted(unused_groups):
        warnings.append(_issue(f"groups[{unused_path}]", "does not match an inspected image path."))
    return {
        "duplicate_sample_identifiers": duplicate_sample_identifiers,
        "duplicate_normalized_paths": duplicate_normalised_paths,
        "duplicate_checksums": duplicate_checksums,
        "cross_split_duplicate_images": cross_split_duplicates,
        "cross_split_group_leakage": group_leakage,
        "grouping_configured": group_map is not None,
    }


def _manifest_metadata_missing(
    metadata: Mapping[str, object] | None,
    source_taxonomy: Mapping[int, str],
    mappings: Mapping[int, Mapping[str, object]],
    excluded: Mapping[int, str],
    unmapped: Mapping[int, str],
    records: Sequence[Mapping[str, object]],
    group_map: Mapping[str, str] | None,
) -> list[str]:
    if metadata is None:
        return ["metadata file"]
    missing = [
        field
        for field in (
            "dataset",
            "source_provenance",
            "licence",
            "storage_release",
            "quality_review_status",
            "known_limitations",
        )
        if field not in metadata
    ]
    for source_id in source_taxonomy:
        if source_id not in mappings and source_id not in excluded and source_id not in unmapped:
            missing.append(f"taxonomy decision for source class {source_id}:{source_taxonomy[source_id]}")
    if group_map is None:
        missing.append("explicit group identifiers for every image")
    else:
        for record in records:
            if _normalise_relative_path(str(record["image_path"])).casefold() not in group_map:
                missing.append("explicit group identifiers for every image")
                break
    return missing


def _candidate_manifest(
    report: Mapping[str, object],
    metadata: Mapping[str, object],
    source_taxonomy: Mapping[int, str],
    mappings: Mapping[int, Mapping[str, object]],
    excluded: Mapping[int, str],
    unmapped: Mapping[int, str],
    records: Sequence[Mapping[str, object]],
    group_map: Mapping[str, str],
) -> dict[str, object]:
    split_samples: dict[str, list[dict[str, object]]] = {"train": [], "validation": [], "test": []}
    for record in sorted(records, key=lambda item: (str(item["split"]), str(item["image_path"]))):
        image_path = str(record["image_path"])
        sample_id = "candidate-" + hashlib.sha256(image_path.encode("utf-8")).hexdigest()[:20]
        annotation_ids = sorted(
            {
                int(annotation["target_class_id"])
                for annotation in record["annotations"]  # type: ignore[index]
                if annotation.get("target_class_id") is not None and not annotation.get("excluded")
            }
        )
        sample: dict[str, object] = {
            "sample_id": sample_id,
            "image_path": image_path,
            "group_id": group_map[_normalise_relative_path(image_path).casefold()],
            "labelled": record["label_path"] is not None,
            "annotation_summary": {
                "bounding_box_count": len(record["annotations"]),
                "class_ids": annotation_ids,
            },
        }
        if record["label_path"] is not None:
            sample["label_path"] = record["label_path"]
        if isinstance(record.get("checksum"), str):
            sample["checksum"] = f"sha256:{record['checksum']}"
        if isinstance(record.get("width"), int) and isinstance(record.get("height"), int):
            sample["width"] = record["width"]
            sample["height"] = record["height"]
        split_samples[str(record["split"])].append(sample)

    all_annotations = [annotation for record in records for annotation in record["annotations"]]  # type: ignore[index]
    duplicate_count = len(report["duplicates"]["duplicate_checksums"])  # type: ignore[index]
    unreadable_count = len(report["image_issues"]["unreadable_images"])  # type: ignore[index]
    invalid_annotation_count = int(report["totals"]["invalid_annotation_count"])  # type: ignore[index]
    excluded_sample_count = sum(
        1
        for record in records
        if any(annotation.get("excluded") for annotation in record["annotations"])  # type: ignore[index]
    )
    quality: dict[str, object] = {
        "image_count": int(report["totals"]["image_count"]),  # type: ignore[index]
        "annotation_count": len(all_annotations),
        "duplicate_count": duplicate_count,
        "corrupt_file_count": unreadable_count,
        "invalid_annotation_count": invalid_annotation_count,
        "excluded_sample_count": excluded_sample_count,
        "quality_review_status": metadata["quality_review_status"],
        "known_limitations": metadata["known_limitations"],
    }
    checksum_values = {
        str(record["image_path"]): f"sha256:{record['checksum']}"
        for record in records
        if isinstance(record.get("checksum"), str)
    }
    if checksum_values:
        quality["checksums"] = dict(sorted(checksum_values.items()))
    return {
        "schema_version": "1.0.0",
        "dataset": metadata["dataset"],
        "source_provenance": metadata["source_provenance"],
        "licence": metadata["licence"],
        "taxonomy": {
            "target_classes": [{"id": class_id, "name": name} for class_id, name in APPROVED_TAXONOMY],
            "class_mappings": [
                {
                    "source_class": source_taxonomy[source_id],
                    "target_class_id": mapping["target_class_id"],
                    "target_class_name": mapping["target_class_name"],
                    "mapping_rationale": mapping["mapping_rationale"],
                    "review_decision": "mapped",
                }
                for source_id, mapping in sorted(mappings.items())
            ],
            "excluded_source_classes": [
                {"source_class": source_taxonomy[source_id], "reason": reason}
                for source_id, reason in sorted(excluded.items())
            ],
            "unmapped_source_classes": [
                {"source_class": source_taxonomy[source_id], "reason": reason}
                for source_id, reason in sorted(unmapped.items())
            ],
            "bounding_box_coordinate_format": "normalized_xywh",
        },
        "splits": {split_name: {"samples": split_samples[split_name]} for split_name in split_samples},
        "quality": quality,
        "storage_release": metadata["storage_release"],
    }


def inspect_dataset(
    dataset_root: Path,
    dataset_yaml_path: Path,
    *,
    metadata_path: Path | None = None,
    group_map_path: Path | None = None,
    decode_images: bool = True,
    checksums: bool = True,
    generate_manifest: bool = False,
    execution_time_utc: str | None = None,
) -> tuple[dict[str, object], dict[str, object] | None]:
    """Inspect a local YOLO dataset and return a report plus optional candidate manifest.

    Inputs are read-only.  The caller is responsible for choosing an output
    directory outside the dataset root when writing the returned data.
    """
    root = dataset_root.resolve()
    if not root.is_dir():
        raise CandidateInspectionError(f"Dataset root is not an existing directory: {dataset_root}")
    dataset_yaml = _load_structured_file(dataset_yaml_path, "Dataset YAML")
    metadata = _load_structured_file(metadata_path, "Metadata file") if metadata_path else None
    errors: list[dict[str, str]] = []
    warnings: list[dict[str, str]] = []
    source_taxonomy = _source_taxonomy(dataset_yaml, errors)
    mappings, excluded, unmapped = _mapping_summary(metadata, source_taxonomy, errors, warnings)
    layout = _resolve_layout(root, dataset_yaml, errors)
    group_map = _read_group_map(group_map_path, root, errors)
    if decode_images:
        if not _pillow_available():
            decode_images = False
            warnings.append(_issue("image_decoding", "Pillow is unavailable; full image decoding was skipped."))
    else:
        warnings.append(_issue("image_decoding", "image decoding was explicitly skipped."))
    if not checksums:
        warnings.append(_issue("checksums", "SHA-256 checksum calculation was explicitly skipped."))

    split_reports: dict[str, object] = {}
    records: list[dict[str, object]] = []
    for split_name in ("train", "validation", "test"):
        if split_name not in layout:
            split_reports[split_name] = {
                "declared_path": None,
                "image_directory": None,
                "label_directory": None,
                "image_count": 0,
                "label_file_count": 0,
                "images_without_labels": [],
                "labels_without_images": [],
                "empty_label_files": [],
                "unsupported_image_files": [],
                "invalid_annotation_count": 0,
            }
            continue
        split_report, split_records = _scan_split(
            split_name,
            layout[split_name],
            root,
            source_taxonomy,
            mappings,
            excluded,
            decode_images=decode_images,
            checksums=checksums,
            errors=errors,
            warnings=warnings,
        )
        split_reports[split_name] = split_report
        records.extend(split_records)

    findings = _analysis_findings(records, group_map, errors, warnings)
    source_counts = Counter(
        int(annotation["source_class_id"])
        for record in records
        for annotation in record["annotations"]  # type: ignore[index]
    )
    target_counts = Counter(
        int(annotation["target_class_id"])
        for record in records
        for annotation in record["annotations"]  # type: ignore[index]
        if annotation.get("target_class_id") is not None and not annotation.get("excluded")
    )
    unreadable_images = sorted(
        error["location"]
        for error in errors
        if error["message"].startswith("image is unreadable or corrupt")
    )
    samples_without_annotations = sorted(
        str(record["image_path"]) for record in records if not record["annotations"]
    )
    image_count = len(records)
    annotation_count = sum(len(record["annotations"]) for record in records)
    invalid_annotation_count = sum(
        int(split_report["invalid_annotation_count"])
        for split_report in split_reports.values()  # type: ignore[union-attr]
    )
    totals = {
        "image_count": image_count,
        "label_file_count": sum(int(split_report["label_file_count"]) for split_report in split_reports.values()),  # type: ignore[union-attr]
        "annotation_count": annotation_count,
        "invalid_annotation_count": invalid_annotation_count,
        "images_without_labels": sum(len(split_report["images_without_labels"]) for split_report in split_reports.values()),  # type: ignore[union-attr]
        "labels_without_images": sum(len(split_report["labels_without_images"]) for split_report in split_reports.values()),  # type: ignore[union-attr]
        "empty_label_files": sum(len(split_report["empty_label_files"]) for split_report in split_reports.values()),  # type: ignore[union-attr]
        "samples_without_annotations": len(samples_without_annotations),
    }
    if errors:
        verdict = "fail"
    elif warnings:
        verdict = "pass_with_warnings"
    else:
        verdict = "pass"
    report: dict[str, object] = {
        "tool": {"name": TOOL_NAME, "version": TOOL_VERSION},
        "execution": {
            "time_utc": execution_time_utc
            or datetime.now(UTC).replace(microsecond=0).isoformat().replace("+00:00", "Z"),
            "network_access": False,
            "read_only_dataset_inspection": True,
        },
        "dataset_identity": metadata.get("dataset", {}).get("id")
        if isinstance(metadata, Mapping) and isinstance(metadata.get("dataset"), Mapping)
        else None,
        "dataset_source_version": metadata.get("dataset", {}).get("source_version")
        if isinstance(metadata, Mapping) and isinstance(metadata.get("dataset"), Mapping)
        else None,
        "settings": {"image_decoding": decode_images, "checksums": checksums},
        "splits": split_reports,
        "source_taxonomy": [{"id": class_id, "name": name} for class_id, name in source_taxonomy.items()],
        "walkbuddy_target_taxonomy": [
            {"id": class_id, "name": name} for class_id, name in APPROVED_TAXONOMY
        ],
        "mapping_summary": {
            "mapped_source_classes": [
                {
                    "source_class_id": source_id,
                    "source_class_name": source_taxonomy[source_id],
                    **mapping,
                }
                for source_id, mapping in sorted(mappings.items())
            ],
            "excluded_source_classes": [
                {"source_class_id": source_id, "source_class_name": source_taxonomy[source_id], "reason": reason}
                for source_id, reason in sorted(excluded.items())
            ],
            "unmapped_source_classes": [
                {
                    "source_class_id": source_id,
                    "source_class_name": source_taxonomy[source_id],
                    "reason": unmapped.get(source_id, "No explicit source-taxonomy decision was supplied."),
                }
                for source_id in source_taxonomy
                if source_id not in mappings and source_id not in excluded
            ],
        },
        "totals": totals,
        "annotation_counts_by_source_class": [
            {"id": source_id, "name": source_taxonomy[source_id], "count": source_counts[source_id]}
            for source_id in source_taxonomy
        ],
        "annotation_counts_by_walkbuddy_target_class": [
            {"id": target_id, "name": target_name, "count": target_counts[target_id]}
            for target_id, target_name in APPROVED_TAXONOMY
        ],
        "image_issues": {
            "unreadable_images": unreadable_images,
            "samples_without_valid_annotations": samples_without_annotations,
        },
        "duplicates": findings,
        "validation_errors": _sort_issues(errors),
        "warnings": _sort_issues(warnings),
        "quality_verdict": verdict,
        "limitations": [
            "A passing inspection does not establish legal, privacy, ethical, or dataset-fitness approval.",
            "This inspection does not measure model quality or production readiness.",
            "Group leakage is checked only when explicit group identifiers are supplied.",
        ],
    }
    candidate: dict[str, object] | None = None
    if generate_manifest:
        missing = _manifest_metadata_missing(
            metadata, source_taxonomy, mappings, excluded, unmapped, records, group_map
        )
        if report["quality_verdict"] == "fail":
            missing.append("a passing dataset-quality inspection")
        if missing:
            report["candidate_manifest"] = {
                "requested": True,
                "generated": False,
                "missing_requirements": sorted(set(missing)),
            }
        else:
            assert metadata is not None and group_map is not None
            candidate = _candidate_manifest(
                report, metadata, source_taxonomy, mappings, excluded, unmapped, records, group_map
            )
            manifest_issues = manifest_validator.validate_manifest(candidate)
            if manifest_issues:
                report["candidate_manifest"] = {
                    "requested": True,
                    "generated": False,
                    "missing_requirements": [
                        f"generated manifest validation: {issue.location}: {issue.message}"
                        for issue in manifest_issues
                    ],
                }
                candidate = None
            else:
                report["candidate_manifest"] = {"requested": True, "generated": True}
    else:
        report["candidate_manifest"] = {"requested": False, "generated": False}
    return report, candidate


def _markdown_table(rows: Sequence[Sequence[object]], headers: Sequence[str]) -> list[str]:
    lines = ["| " + " | ".join(headers) + " |", "| " + " | ".join("---" for _ in headers) + " |"]
    lines.extend("| " + " | ".join(str(value) for value in row) + " |" for row in rows)
    return lines


def render_markdown_report(report: Mapping[str, object]) -> str:
    totals = report["totals"]
    assert isinstance(totals, Mapping)
    lines = [
        "# Candidate dataset quality report",
        "",
        f"Tool: `{report['tool']['name']}` {report['tool']['version']}.",  # type: ignore[index]
        f"Execution time (runtime metadata): {report['execution']['time_utc']}."  # type: ignore[index]
        "",
        "## Source identity",
        "",
        f"- Dataset identity: `{report.get('dataset_identity') or 'not recorded'}`.",
        f"- Source version: `{report.get('dataset_source_version') or 'not recorded'}`.",
        "",
        "## Quality verdict",
        "",
        f"`{report['quality_verdict']}`. The verdict is `fail` when validation errors exist, "
        "`pass_with_warnings` when there are no errors but warnings exist, and `pass` otherwise.",
        "",
        "## Totals",
        "",
    ]
    lines.extend(
        _markdown_table(
            [(key.replace("_", " "), value) for key, value in totals.items()], ["Measure", "Value"]
        )
    )
    lines.extend(["", "## Split inspection", ""])
    split_rows = []
    for name, split in report["splits"].items():  # type: ignore[index]
        split_rows.append((name, split["image_count"], split["label_file_count"], split["invalid_annotation_count"]))
    lines.extend(_markdown_table(split_rows, ["Split", "Images", "Label files", "Invalid label rows"]))
    lines.extend(["", "## Source class distribution", ""])
    lines.extend(
        _markdown_table(
            [(item["id"], item["name"], item["count"]) for item in report["annotation_counts_by_source_class"]],  # type: ignore[index]
            ["Source ID", "Class", "Annotations"],
        )
    )
    lines.extend(["", "## WalkBuddy target distribution", ""])
    lines.extend(
        _markdown_table(
            [(item["id"], item["name"], item["count"]) for item in report["annotation_counts_by_walkbuddy_target_class"]],  # type: ignore[index]
            ["Target ID", "Class", "Mapped annotations"],
        )
    )
    for heading, values in (("Validation errors", report["validation_errors"]), ("Warnings", report["warnings"])):
        lines.extend(["", f"## {heading}", ""])
        if values:
            lines.extend(f"- `{value['location']}`: {value['message']}" for value in values)  # type: ignore[index]
        else:
            lines.append("- None.")
    lines.extend(["", "## Limitations", ""])
    lines.extend(f"- {limitation}" for limitation in report["limitations"])  # type: ignore[index]
    lines.append("")
    return "\n".join(lines)


def write_outputs(
    report: Mapping[str, object],
    candidate_manifest: Mapping[str, object] | None,
    output_directory: Path,
    dataset_root: Path,
) -> list[Path]:
    resolved_output = output_directory.resolve()
    try:
        resolved_output.relative_to(dataset_root.resolve())
    except ValueError:
        pass
    else:
        raise CandidateInspectionError("Output directory must be outside the supplied dataset root.")
    resolved_output.mkdir(parents=True, exist_ok=True)
    json_path = resolved_output / "dataset_quality_report.json"
    markdown_path = resolved_output / "dataset_quality_report.md"
    json_path.write_text(json.dumps(report, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    markdown_path.write_text(render_markdown_report(report), encoding="utf-8")
    paths = [json_path, markdown_path]
    if candidate_manifest is not None:
        manifest_path = resolved_output / "candidate_manifest.json"
        manifest_path.write_text(json.dumps(candidate_manifest, indent=2, sort_keys=True) + "\n", encoding="utf-8")
        paths.append(manifest_path)
    return paths


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Read-only YOLO candidate-dataset quality inspection for the WalkBuddy taxonomy."
    )
    parser.add_argument("--dataset-root", required=True, type=Path, help="Controlled local root containing the dataset.")
    parser.add_argument("--dataset-yaml", required=True, type=Path, help="Local YOLO dataset YAML file.")
    parser.add_argument("--output-dir", required=True, type=Path, help="Directory outside the dataset root for generated reports.")
    parser.add_argument("--metadata", type=Path, help="Optional reviewed metadata JSON or YAML for mapping and manifest generation.")
    parser.add_argument("--group-map", type=Path, help="Optional JSON or YAML map of relative image paths to explicit group IDs.")
    parser.add_argument("--skip-image-decode", action="store_true", help="Do not decode images with Pillow.")
    parser.add_argument("--skip-checksums", action="store_true", help="Do not calculate SHA-256 image checksums.")
    parser.add_argument("--generate-manifest", action="store_true", help="Write candidate_manifest.json only when reviewed metadata is complete.")
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    try:
        report, candidate = inspect_dataset(
            args.dataset_root,
            args.dataset_yaml,
            metadata_path=args.metadata,
            group_map_path=args.group_map,
            decode_images=not args.skip_image_decode,
            checksums=not args.skip_checksums,
            generate_manifest=args.generate_manifest,
        )
        paths = write_outputs(report, candidate, args.output_dir, args.dataset_root)
    except CandidateInspectionError as exc:
        print(f"Candidate dataset inspection failed: {exc}", file=sys.stderr)
        return 1
    print(f"Candidate dataset inspection verdict: {report['quality_verdict']}")
    print("Generated: " + ", ".join(str(path) for path in paths))
    return 0 if report["quality_verdict"] != "fail" else 1


if __name__ == "__main__":
    raise SystemExit(main())
