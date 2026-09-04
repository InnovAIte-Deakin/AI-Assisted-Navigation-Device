"""Validate Git-safe WalkBuddy navigation dataset manifests without network access.

The structural validator implements a project-specific subset of the bundled
Draft 2020-12 JSON Schema document: ``$defs``, ``$ref``, ``type``, ``required``,
``properties``, ``additionalProperties``, ``items``, ``minItems``,
``minLength``, ``minimum``, ``pattern``, ``enum``, and ``const``. It is not a
general-purpose JSON Schema implementation.
"""

from __future__ import annotations

import argparse
import json
import math
import re
import sys
from collections import Counter, defaultdict
from collections.abc import Iterable, Mapping, Sequence
from dataclasses import dataclass
from datetime import date
from functools import lru_cache
from pathlib import Path, PurePosixPath, PureWindowsPath
from typing import Any
from urllib.parse import unquote


ML_SIDE_DIR = Path(__file__).resolve().parents[1]
DEFAULT_SCHEMA_PATH = ML_SIDE_DIR / "datasets" / "manifest.schema.json"
APPROVED_TAXONOMY: tuple[tuple[int, str], ...] = (
    (0, "person"),
    (1, "stairs"),
    (2, "door"),
    (3, "chair"),
    (4, "table"),
    (5, "pole"),
    (6, "bicycle"),
    (7, "vehicle"),
)
APPROVED_TARGETS = dict(APPROVED_TAXONOMY)
IMAGE_EXTENSIONS = frozenset({".jpg", ".jpeg", ".png", ".bmp", ".webp", ".tif", ".tiff"})
LABEL_EXTENSIONS = frozenset({".txt"})
SUPPORTED_SCHEMA_KEYWORDS = frozenset(
    {
        "$defs",
        "$ref",
        "type",
        "required",
        "properties",
        "additionalProperties",
        "items",
        "minItems",
        "minLength",
        "minimum",
        "pattern",
        "enum",
        "const",
    }
)
SCHEMA_ANNOTATION_KEYWORDS = frozenset({"$schema", "$id", "title", "description"})


@dataclass(frozen=True)
class ValidationIssue:
    """One readable structural or semantic validation problem."""

    location: str
    message: str


class ManifestValidationError(Exception):
    """Raised when a manifest or the local validation schema cannot be read."""


def _issue(location: str, message: str) -> ValidationIssue:
    return ValidationIssue(location=location, message=message)


@lru_cache(maxsize=1)
def load_schema(schema_path: Path = DEFAULT_SCHEMA_PATH) -> dict[str, object]:
    """Read the bundled JSON Schema without accessing datasets or the network."""
    try:
        with schema_path.open("r", encoding="utf-8-sig") as schema_file:
            schema = json.load(schema_file)
    except FileNotFoundError as exc:
        raise ManifestValidationError(f"Schema file is missing: {schema_path}") from exc
    except OSError as exc:
        raise ManifestValidationError(f"Schema file could not be read: {schema_path}") from exc
    except json.JSONDecodeError as exc:
        raise ManifestValidationError(f"Schema file is not valid JSON: {schema_path}") from exc

    if not isinstance(schema, dict):
        raise ManifestValidationError(f"Schema root must be an object: {schema_path}")
    _ensure_supported_schema_keywords(schema)
    return schema


def _ensure_supported_schema_keywords(schema: Mapping[str, object], location: str = "$") -> None:
    """Reject a future schema keyword that this project-specific validator cannot enforce."""
    for keyword, value in schema.items():
        if keyword not in SUPPORTED_SCHEMA_KEYWORDS | SCHEMA_ANNOTATION_KEYWORDS:
            raise ManifestValidationError(f"Unsupported schema keyword {keyword!r} at {location}.")

        if keyword == "properties" and isinstance(value, Mapping):
            for property_name, property_schema in value.items():
                if isinstance(property_schema, Mapping):
                    _ensure_supported_schema_keywords(property_schema, f"{location}.properties.{property_name}")
        elif keyword in {"items", "additionalProperties"} and isinstance(value, Mapping):
            _ensure_supported_schema_keywords(value, f"{location}.{keyword}")
        elif keyword == "$defs" and isinstance(value, Mapping):
            for definition_name, definition_schema in value.items():
                if isinstance(definition_schema, Mapping):
                    _ensure_supported_schema_keywords(definition_schema, f"{location}.$defs.{definition_name}")


def _is_integer(value: object) -> bool:
    return isinstance(value, int) and not isinstance(value, bool)


def _is_number(value: object) -> bool:
    return isinstance(value, (int, float)) and not isinstance(value, bool)


def _matches_type(value: object, expected_type: str) -> bool:
    type_checks = {
        "object": lambda: isinstance(value, dict),
        "array": lambda: isinstance(value, list),
        "string": lambda: isinstance(value, str),
        "integer": lambda: _is_integer(value),
        "number": lambda: _is_number(value),
        "boolean": lambda: isinstance(value, bool),
        "null": lambda: value is None,
    }
    check = type_checks.get(expected_type)
    return check() if check is not None else True


def _resolve_reference(reference: str, root_schema: Mapping[str, object]) -> Mapping[str, object]:
    if not reference.startswith("#/"):
        raise ManifestValidationError(f"Unsupported schema reference: {reference}")

    target: object = root_schema
    for raw_part in reference[2:].split("/"):
        part = raw_part.replace("~1", "/").replace("~0", "~")
        if not isinstance(target, Mapping) or part not in target:
            raise ManifestValidationError(f"Schema reference cannot be resolved: {reference}")
        target = target[part]

    if not isinstance(target, Mapping):
        raise ManifestValidationError(f"Schema reference is not an object: {reference}")
    return target


def _schema_issues(
    value: object,
    schema: Mapping[str, object],
    root_schema: Mapping[str, object],
    location: str,
) -> list[ValidationIssue]:
    """Validate the JSON-Schema subset used by the bundled manifest schema."""
    reference = schema.get("$ref")
    if isinstance(reference, str):
        return _schema_issues(value, _resolve_reference(reference, root_schema), root_schema, location)

    issues: list[ValidationIssue] = []
    expected_type = schema.get("type")
    if isinstance(expected_type, str) and not _matches_type(value, expected_type):
        return [_issue(location, f"must be a {expected_type}.")]

    if "const" in schema and value != schema["const"]:
        issues.append(_issue(location, f"must equal {schema['const']!r}."))

    allowed_values = schema.get("enum")
    if isinstance(allowed_values, list) and value not in allowed_values:
        issues.append(_issue(location, f"must be one of {allowed_values!r}."))

    if isinstance(value, str):
        min_length = schema.get("minLength")
        if _is_integer(min_length) and len(value) < min_length:
            issues.append(_issue(location, f"must contain at least {min_length} character(s)."))
        pattern = schema.get("pattern")
        if isinstance(pattern, str) and re.search(pattern, value) is None:
            issues.append(_issue(location, "does not match the required format."))

    if _is_number(value):
        minimum = schema.get("minimum")
        if _is_number(minimum) and value < minimum:
            issues.append(_issue(location, f"must be at least {minimum}."))

    if isinstance(value, list):
        min_items = schema.get("minItems")
        if _is_integer(min_items) and len(value) < min_items:
            issues.append(_issue(location, f"must contain at least {min_items} item(s)."))
        item_schema = schema.get("items")
        if isinstance(item_schema, Mapping):
            for index, item in enumerate(value):
                issues.extend(_schema_issues(item, item_schema, root_schema, f"{location}[{index}]"))

    if isinstance(value, dict):
        required = schema.get("required")
        if isinstance(required, list):
            for property_name in required:
                if isinstance(property_name, str) and property_name not in value:
                    issues.append(_issue(location, f"is missing required field {property_name!r}."))

        properties = schema.get("properties")
        property_schemas = properties if isinstance(properties, Mapping) else {}
        for property_name, property_value in value.items():
            property_location = f"{location}.{property_name}"
            property_schema = property_schemas.get(property_name)
            if isinstance(property_schema, Mapping):
                issues.extend(
                    _schema_issues(property_value, property_schema, root_schema, property_location)
                )
                continue

            additional_properties = schema.get("additionalProperties", True)
            if additional_properties is False:
                issues.append(_issue(property_location, "is not an allowed field."))
            elif isinstance(additional_properties, Mapping):
                issues.extend(
                    _schema_issues(property_value, additional_properties, root_schema, property_location)
                )

    return issues


def _as_mapping(value: object) -> Mapping[str, object] | None:
    return value if isinstance(value, Mapping) else None


def _as_list(value: object) -> list[object] | None:
    return value if isinstance(value, list) else None


def _normalise_identifier(value: object) -> str | None:
    if not isinstance(value, str) or not value.strip():
        return None
    return value.strip().casefold()


def _unsafe_path_reason(path: str) -> str | None:
    if path.casefold().startswith("file:"):
        return "must not be a file URI."

    windows_path = PureWindowsPath(path)
    posix_path = PurePosixPath(path.replace("\\", "/"))
    if (
        windows_path.is_absolute()
        or posix_path.is_absolute()
        or path.startswith("\\")
        or re.match(r"^[A-Za-z]:", path) is not None
    ):
        return "must not be an absolute Windows or POSIX path."

    parts = [part for part in re.split(r"[\\/]", path) if part]
    if ".." in parts:
        return "must not contain path traversal ('..')."
    return None


def _is_safe_relative_path(value: object) -> tuple[bool, str | None]:
    if not isinstance(value, str) or not value.strip():
        return False, "must be a non-empty relative path."

    path = value.strip()
    path_reason = _unsafe_path_reason(path)
    if path_reason is not None:
        return False, path_reason

    decoded_path = path
    for _ in range(2):
        next_path = unquote(decoded_path)
        if next_path == decoded_path:
            break
        decoded_path = next_path
    decoded_reason = _unsafe_path_reason(decoded_path)
    if decoded_reason is not None:
        return False, f"must not use percent-encoded syntax that {decoded_reason.removeprefix('must not ')}"
    return True, None


def _resolve_dataset_reference(dataset_root: Path, relative_path: str) -> Path | None:
    """Resolve a checked file path and reject a symlink that leaves the dataset root."""
    candidate = dataset_root.joinpath(*relative_path.replace("\\", "/").split("/")).resolve()
    try:
        candidate.relative_to(dataset_root)
    except ValueError:
        return None
    return candidate


def _validate_date(value: object, location: str, issues: list[ValidationIssue]) -> None:
    if not isinstance(value, str):
        return
    try:
        date.fromisoformat(value)
    except ValueError:
        issues.append(_issue(location, "must be an ISO 8601 calendar date (YYYY-MM-DD)."))


def _iter_samples(manifest: Mapping[str, object]) -> Iterable[tuple[str, int, Mapping[str, object]]]:
    splits = _as_mapping(manifest.get("splits"))
    if splits is None:
        return
    for split_name in ("train", "validation", "test"):
        split = _as_mapping(splits.get(split_name))
        samples = _as_list(split.get("samples")) if split is not None else None
        if samples is None:
            continue
        for index, sample in enumerate(samples):
            mapping = _as_mapping(sample)
            if mapping is not None:
                yield split_name, index, mapping


def _validate_taxonomy(manifest: Mapping[str, object], issues: list[ValidationIssue]) -> None:
    taxonomy = _as_mapping(manifest.get("taxonomy"))
    if taxonomy is None:
        return

    target_classes = _as_list(taxonomy.get("target_classes"))
    actual_taxonomy: list[tuple[object, object]] = []
    target_ids: list[int] = []
    if target_classes is not None:
        for index, target in enumerate(target_classes):
            target_mapping = _as_mapping(target)
            if target_mapping is None:
                continue
            target_id = target_mapping.get("id")
            target_name = target_mapping.get("name")
            actual_taxonomy.append((target_id, target_name))
            if _is_integer(target_id):
                target_ids.append(target_id)
            if _is_integer(target_id) and target_name not in {name for _, name in APPROVED_TAXONOMY}:
                issues.append(
                    _issue(
                        f"$.taxonomy.target_classes[{index}].name",
                        "is not an approved WalkBuddy target class.",
                    )
                )

    if actual_taxonomy != list(APPROVED_TAXONOMY):
        issues.append(
            _issue(
                "$.taxonomy.target_classes",
                "must exactly match the approved IDs and order: "
                + ", ".join(f"{class_id}:{name}" for class_id, name in APPROVED_TAXONOMY)
                + ".",
            )
        )
    for target_id, count in Counter(target_ids).items():
        if count > 1:
            issues.append(
                _issue("$.taxonomy.target_classes", f"contains duplicate target class ID {target_id}.")
            )
    target_names = [target_name for _, target_name in actual_taxonomy if isinstance(target_name, str)]
    for target_name, count in Counter(target_names).items():
        if count > 1:
            issues.append(
                _issue("$.taxonomy.target_classes", f"contains duplicate target class name {target_name!r}.")
            )

    class_mappings = _as_list(taxonomy.get("class_mappings"))
    mapped_sources: dict[str, tuple[object, object]] = {}
    if class_mappings is not None:
        for index, mapping in enumerate(class_mappings):
            mapping_data = _as_mapping(mapping)
            if mapping_data is None:
                continue
            location = f"$.taxonomy.class_mappings[{index}]"
            source_class = _normalise_identifier(mapping_data.get("source_class"))
            target_id = mapping_data.get("target_class_id")
            target_name = mapping_data.get("target_class_name")
            rationale = mapping_data.get("mapping_rationale")

            if source_class is not None:
                prior_target = mapped_sources.get(source_class)
                target = (target_id, target_name)
                if prior_target is not None:
                    if prior_target == target:
                        issues.append(_issue(location, "duplicates an existing source-class mapping."))
                    else:
                        issues.append(_issue(location, "conflicts with an existing source-class mapping."))
                else:
                    mapped_sources[source_class] = target

            if not _is_integer(target_id) or APPROVED_TARGETS.get(target_id) != target_name:
                issues.append(
                    _issue(
                        location,
                        "must map to a matching ID/name pair in the approved WalkBuddy taxonomy.",
                    )
                )
            if isinstance(rationale, str) and rationale and not rationale.strip():
                issues.append(
                    _issue(location, "must include a non-empty mapping_rationale for an explicit mapping.")
                )

    source_decision_sets: dict[str, set[str]] = defaultdict(set)
    for category in ("excluded_source_classes", "unmapped_source_classes"):
        decisions = _as_list(taxonomy.get(category))
        if decisions is None:
            continue
        for index, decision in enumerate(decisions):
            decision_data = _as_mapping(decision)
            if decision_data is None:
                continue
            source_class = _normalise_identifier(decision_data.get("source_class"))
            if source_class is not None:
                source_decision_sets[source_class].add(category)
            reason = decision_data.get("reason")
            if isinstance(reason, str) and reason and not reason.strip():
                issues.append(_issue(f"$.taxonomy.{category}[{index}]", "must include a non-empty reason."))

    for source_class in mapped_sources:
        if source_class in source_decision_sets:
            issues.append(
                _issue(
                    "$.taxonomy",
                    f"source class {source_class!r} cannot be both mapped and excluded or unmapped.",
                )
            )
    for source_class, categories in source_decision_sets.items():
        if len(categories) > 1:
            issues.append(
                _issue(
                    "$.taxonomy",
                    f"source class {source_class!r} cannot be both excluded and unmapped.",
                )
            )


def _validate_bounding_boxes(
    sample: Mapping[str, object], coordinate_format: object, location: str, issues: list[ValidationIssue]
) -> None:
    boxes = _as_list(sample.get("bounding_boxes"))
    if boxes is None:
        return

    image_width = sample.get("width")
    image_height = sample.get("height")
    for index, box in enumerate(boxes):
        box_data = _as_mapping(box)
        if box_data is None:
            continue
        box_location = f"{location}.bounding_boxes[{index}]"
        class_id = box_data.get("class_id")
        if not _is_integer(class_id) or class_id not in APPROVED_TARGETS:
            issues.append(_issue(f"{box_location}.class_id", "must be an approved target class ID."))

        values: dict[str, float] = {}
        for field_name in ("x", "y", "width", "height"):
            value = box_data.get(field_name)
            if not _is_number(value) or not math.isfinite(float(value)):
                issues.append(_issue(f"{box_location}.{field_name}", "must be a finite number."))
                continue
            values[field_name] = float(value)
        if len(values) != 4:
            continue

        x, y, width, height = (values[name] for name in ("x", "y", "width", "height"))
        if width <= 0 or height <= 0:
            issues.append(_issue(box_location, "must have positive width and height."))
            continue

        if coordinate_format == "normalized_xywh":
            if x < 0 or y < 0 or x + width > 1 or y + height > 1:
                issues.append(
                    _issue(box_location, "must fit within normalized image bounds from 0 to 1.")
                )
        elif coordinate_format == "pixel_xywh":
            if not _is_integer(image_width) or not _is_integer(image_height):
                issues.append(
                    _issue(location, "requires positive width and height for pixel_xywh bounding boxes.")
                )
            elif x < 0 or y < 0 or x + width > image_width or y + height > image_height:
                issues.append(_issue(box_location, "must fit within the declared image bounds."))


def _validate_samples(
    manifest: Mapping[str, object], dataset_root: Path | None, check_files: bool, issues: list[ValidationIssue]
) -> None:
    taxonomy = _as_mapping(manifest.get("taxonomy"))
    coordinate_format = taxonomy.get("bounding_box_coordinate_format") if taxonomy else None
    sample_ids: dict[str, str] = {}
    image_splits: dict[str, set[str]] = defaultdict(set)
    group_splits: dict[str, set[str]] = defaultdict(set)
    image_locations: dict[str, str] = {}
    image_occurrences: dict[str, list[str]] = defaultdict(list)

    root_is_available = True
    resolved_root: Path | None = None
    if check_files and dataset_root is not None:
        resolved_root = dataset_root.expanduser().resolve()
        if not resolved_root.is_dir():
            issues.append(_issue("--dataset-root", f"is not an existing directory: {resolved_root}"))
            root_is_available = False

    for split_name, index, sample in _iter_samples(manifest):
        location = f"$.splits.{split_name}.samples[{index}]"
        sample_id = _normalise_identifier(sample.get("sample_id"))
        if sample_id is not None:
            prior_location = sample_ids.get(sample_id)
            if prior_location is not None:
                issues.append(_issue(location, f"duplicates sample_id from {prior_location}."))
            else:
                sample_ids[sample_id] = location

        image_path = sample.get("image_path")
        image_is_safe = False
        if isinstance(image_path, str) and image_path.strip():
            image_is_safe, image_path_error = _is_safe_relative_path(image_path)
            if not image_is_safe:
                issues.append(_issue(f"{location}.image_path", image_path_error or "is invalid."))
        if image_is_safe and isinstance(image_path, str):
            image_suffix = Path(image_path).suffix.lower()
            if image_suffix not in IMAGE_EXTENSIONS:
                issues.append(_issue(f"{location}.image_path", "has an unsupported image extension."))
            normalized_image = image_path.replace("\\", "/").casefold()
            image_splits[normalized_image].add(split_name)
            image_locations.setdefault(normalized_image, location)
            image_occurrences[normalized_image].append(location)

        label_path = sample.get("label_path")
        if sample.get("labelled") is True and not isinstance(label_path, str):
            issues.append(_issue(location, "requires label_path when labelled is true."))
        label_is_safe = False
        if isinstance(label_path, str) and label_path.strip():
            label_is_safe, label_path_error = _is_safe_relative_path(label_path)
            if not label_is_safe:
                issues.append(_issue(f"{location}.label_path", label_path_error or "is invalid."))
            elif Path(label_path).suffix.lower() not in LABEL_EXTENSIONS:
                issues.append(_issue(f"{location}.label_path", "has an unsupported label extension."))

        group_id = _normalise_identifier(sample.get("group_id"))
        if group_id is not None:
            group_splits[group_id].add(split_name)

        annotation_summary = _as_mapping(sample.get("annotation_summary"))
        if annotation_summary is not None:
            class_ids = _as_list(annotation_summary.get("class_ids"))
            if class_ids is not None:
                for class_index, class_id in enumerate(class_ids):
                    if not _is_integer(class_id) or class_id not in APPROVED_TARGETS:
                        issues.append(
                            _issue(
                                f"{location}.annotation_summary.class_ids[{class_index}]",
                                "must be an approved target class ID.",
                            )
                        )

        _validate_bounding_boxes(sample, coordinate_format, location, issues)

        if check_files and root_is_available and resolved_root is not None:
            for path_name, path_value in (("image_path", image_path), ("label_path", label_path)):
                if path_value is None or not isinstance(path_value, str):
                    continue
                path_is_safe = (path_name == "image_path" and image_is_safe) or (
                    path_name == "label_path" and label_is_safe
                )
                if not path_is_safe:
                    continue
                candidate = _resolve_dataset_reference(resolved_root, path_value)
                if candidate is None:
                    issues.append(
                        _issue(
                            f"{location}.{path_name}",
                            "resolves outside the supplied dataset root.",
                        )
                    )
                elif not candidate.is_file():
                    issues.append(_issue(f"{location}.{path_name}", f"referenced file is missing: {candidate}"))

    for image_path, splits in image_splits.items():
        if len(splits) > 1:
            issues.append(
                _issue(
                    image_locations[image_path],
                    f"image is reused across splits: {', '.join(sorted(splits))}.",
                )
            )
        elif len(image_occurrences[image_path]) > 1:
            issues.append(
                _issue(
                    image_locations[image_path],
                    "image appears more than once in the same split.",
                )
            )
    for group_id, splits in group_splits.items():
        if len(splits) > 1:
            issues.append(
                _issue(
                    "$.splits",
                    f"group or sequence {group_id!r} is reused across splits: {', '.join(sorted(splits))}.",
                )
            )


def _validate_quality_and_release(manifest: Mapping[str, object], issues: list[ValidationIssue]) -> None:
    dataset = _as_mapping(manifest.get("dataset"))
    provenance = _as_mapping(manifest.get("source_provenance"))
    licence = _as_mapping(manifest.get("licence"))
    storage_release = _as_mapping(manifest.get("storage_release"))

    if dataset is not None:
        _validate_date(dataset.get("release_date"), "$.dataset.release_date", issues)
    if provenance is not None:
        _validate_date(provenance.get("accessed_on"), "$.source_provenance.accessed_on", issues)
        source_reference = provenance.get("source_reference")
        source_is_safe, source_path_error = _is_safe_relative_path(source_reference)
        if (
            not source_is_safe
            and source_path_error is not None
            and ("absolute" in source_path_error or "file URI" in source_path_error)
        ):
            issues.append(
                _issue(
                    "$.source_provenance.source_reference",
                    "must not be a personal absolute filesystem path.",
                )
            )
    if licence is not None:
        _validate_date(licence.get("review_date"), "$.licence.review_date", issues)
        if licence.get("attribution_required") is True:
            requirements = licence.get("attribution_requirements")
            if not isinstance(requirements, str) or not requirements.strip():
                issues.append(
                    _issue(
                        "$.licence.attribution_requirements",
                        "must be non-empty when attribution_required is true.",
                    )
                )

    if storage_release is not None:
        storage_reference = storage_release.get("authoritative_storage_reference")
        storage_is_safe, storage_path_error = _is_safe_relative_path(storage_reference)
        if (
            not storage_is_safe
            and storage_path_error is not None
            and ("absolute" in storage_path_error or "file URI" in storage_path_error)
        ):
            issues.append(
                _issue(
                    "$.storage_release.authoritative_storage_reference",
                    "must not be a personal absolute filesystem path.",
                )
            )


def validate_manifest(
    manifest: Mapping[str, object],
    *,
    dataset_root: str | Path | None = None,
    check_files: bool = False,
) -> list[ValidationIssue]:
    """Return all practical structural and semantic issues for one manifest."""
    if check_files and dataset_root is None:
        return [_issue("--check-files", "requires --dataset-root.")]

    schema = load_schema()
    issues = _schema_issues(manifest, schema, schema, "$")
    _validate_taxonomy(manifest, issues)
    _validate_quality_and_release(manifest, issues)
    root = Path(dataset_root) if dataset_root is not None else None
    _validate_samples(manifest, root, check_files, issues)
    return issues


def load_manifest(manifest_path: str | Path) -> tuple[Path, dict[str, object]]:
    """Load one local JSON manifest and turn ordinary read errors into messages."""
    path = Path(manifest_path).expanduser().resolve()
    if not path.exists():
        raise ManifestValidationError(f"Manifest file is missing: {path}")
    if not path.is_file():
        raise ManifestValidationError(f"Manifest path is not a file: {path}")

    try:
        with path.open("r", encoding="utf-8-sig") as manifest_file:
            manifest = json.load(manifest_file)
    except OSError as exc:
        raise ManifestValidationError(f"Manifest file could not be read: {path}") from exc
    except json.JSONDecodeError as exc:
        raise ManifestValidationError(
            f"Manifest file is not valid JSON: {path} (line {exc.lineno}, column {exc.colno})"
        ) from exc

    if not isinstance(manifest, dict):
        raise ManifestValidationError(f"Manifest root must be an object: {path}")
    return path, manifest


def format_issues(issues: Sequence[ValidationIssue]) -> str:
    """Format all findings without a traceback or a premature first-error exit."""
    lines = [f"Dataset manifest validation failed ({len(issues)} issue(s)):" ]
    lines.extend(f"- {issue.location}: {issue.message}" for issue in issues)
    return "\n".join(lines)


def parse_args(argv: Sequence[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Validate a Git-safe WalkBuddy navigation dataset manifest without network access."
    )
    parser.add_argument("manifest", help="Path to a JSON dataset manifest.")
    parser.add_argument(
        "--dataset-root",
        help="Local controlled dataset root used only with --check-files.",
    )
    parser.add_argument(
        "--check-files",
        action="store_true",
        help="Check that manifest image and label paths exist beneath --dataset-root.",
    )
    return parser.parse_args(argv)


def main(argv: Sequence[str] | None = None) -> int:
    """Run the validator and return zero only when no validation issue is found."""
    args = parse_args(argv)
    try:
        manifest_path, manifest = load_manifest(args.manifest)
        issues = validate_manifest(
            manifest,
            dataset_root=args.dataset_root,
            check_files=args.check_files,
        )
    except ManifestValidationError as exc:
        print(f"Dataset manifest validation failed: {exc}", file=sys.stderr)
        return 1

    if issues:
        print(format_issues(issues), file=sys.stderr)
        return 1

    print(f"Dataset manifest validation passed: {manifest_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
