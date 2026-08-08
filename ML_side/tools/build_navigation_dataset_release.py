"""Build a controlled, local-only canonical WalkBuddy YOLO dataset release.

The builder deliberately consumes only previously reviewed local inputs.  It
does not infer class mappings, download data, or make a release eligible for
training.  Its generated manifest defaults to ``under_review`` unless reviewed
release metadata explicitly records another valid decision.
"""

from __future__ import annotations

import argparse
import copy
import hashlib
import json
import math
import shutil
import subprocess
import sys
import uuid
from collections import Counter
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from pathlib import Path, PureWindowsPath

try:
    import yaml
except ImportError:  # pragma: no cover - exercised through an ordinary CLI error
    yaml = None  # type: ignore[assignment]

YAML_ERROR = yaml.YAMLError if yaml is not None else ()

import inspect_candidate_dataset as inspector
import validate_dataset_manifest as manifest_validator


TOOL_NAME = "build_navigation_dataset_release"
TOOL_VERSION = "1.0.0"
REPOSITORY_ROOT = Path(__file__).resolve().parents[2]
CANONICAL_TAXONOMY = manifest_validator.APPROVED_TAXONOMY
CANONICAL_TARGETS = manifest_validator.APPROVED_TARGETS
SPLITS = ("train", "validation", "test")
EMPTY_POLICIES = frozenset({"retain_negative", "exclude_image"})


class DatasetReleaseError(Exception):
    """Raised for a controlled release validation or construction failure."""


@dataclass(frozen=True)
class PlannedSample:
    split: str
    sample_id: str
    group_id: str
    source_image: Path
    destination_image: str
    destination_label: str
    label_text: str
    image_checksum: str
    annotation_class_ids: tuple[int, ...]
    source_empty_negative: bool
    exclusion_created_negative: bool


@dataclass(frozen=True)
class ReleasePlan:
    source_root: Path
    source_manifest_path: Path
    source_yaml_path: Path
    inspection_report_path: Path
    mapping_path: Path
    output_root: Path
    release_root: Path
    release_name: str
    release_version: str
    empty_image_policy: str
    source_manifest: dict[str, object]
    mapping: dict[str, object]
    samples: tuple[PlannedSample, ...]
    source_counts: dict[int, int]
    target_counts: dict[int, int]
    excluded_counts: dict[int, int]
    input_checksums: dict[str, str]
    release_identity: str
    git_commit: str | None
    git_dirty: bool | None


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def _json_text(value: object) -> str:
    return json.dumps(value, indent=2, sort_keys=True, ensure_ascii=False) + "\n"


def _load_structured(path: Path, label: str) -> dict[str, object]:
    if not path.is_file():
        raise DatasetReleaseError(f"{label} is not an existing file: {path}")
    try:
        text = path.read_text(encoding="utf-8-sig")
        if path.suffix.casefold() == ".json":
            value = json.loads(text)
        else:
            if yaml is None:
                raise DatasetReleaseError("PyYAML is required to read YAML release inputs.")
            value = yaml.safe_load(text)
    except json.JSONDecodeError as exc:
        raise DatasetReleaseError(f"{label} is not valid JSON: {path}") from exc
    except OSError as exc:
        raise DatasetReleaseError(f"{label} could not be read: {path}") from exc
    except YAML_ERROR as exc:  # type: ignore[misc]
        raise DatasetReleaseError(f"{label} is not valid YAML: {path}") from exc
    if not isinstance(value, dict):
        raise DatasetReleaseError(f"{label} root must be an object: {path}")
    return value


def _safe_name(value: str, label: str) -> str:
    if not value or value != value.strip() or any(character in value for character in "/\\"):
        raise DatasetReleaseError(f"{label} must be a non-empty single path component.")
    if value in {".", ".."} or not all(character.isalnum() or character in "._-" for character in value):
        raise DatasetReleaseError(f"{label} may contain only letters, numbers, dots, underscores, and hyphens.")
    return value


def _reject_nonlocal_path(path: Path, label: str) -> None:
    """Reject remote and drive-relative input locations before filesystem access."""
    raw = str(path)
    folded = raw.casefold()
    windows_path = PureWindowsPath(raw)
    if (
        folded.startswith(("http://", "https://", "http:\\", "https:\\", "file:"))
        or raw.startswith(("\\\\", "//"))
        or (windows_path.drive.endswith(":") and len(windows_path.drive) > 2)
        or (windows_path.drive and not windows_path.is_absolute())
    ):
        raise DatasetReleaseError(f"{label} must be a controlled local filesystem path, not a URL, URI, UNC, or drive-relative path.")


def _is_beneath(root: Path, path: Path) -> bool:
    try:
        path.resolve().relative_to(root.resolve())
    except ValueError:
        return False
    return True


def _require_beneath(root: Path, path: Path, label: str) -> Path:
    resolved = path.resolve()
    if not _is_beneath(root, resolved):
        raise DatasetReleaseError(f"{label} must resolve beneath the controlled source dataset root.")
    return resolved


def _relative_reference(root: Path, raw: object, label: str) -> Path:
    valid, reason = manifest_validator._is_safe_relative_path(raw)
    if not valid or not isinstance(raw, str):
        raise DatasetReleaseError(f"{label} is unsafe: {reason or 'expected a safe relative path.'}")
    resolved = manifest_validator._resolve_dataset_reference(root, raw)
    if resolved is None:
        raise DatasetReleaseError(f"{label} escapes the controlled source dataset root.")
    return resolved


def _mapping(value: object, label: str) -> Mapping[str, object]:
    if not isinstance(value, Mapping):
        raise DatasetReleaseError(f"{label} must be an object.")
    return value


def _list(value: object, label: str) -> list[object]:
    if not isinstance(value, list):
        raise DatasetReleaseError(f"{label} must be an array.")
    return value


def _integer(value: object, label: str) -> int:
    if not isinstance(value, int) or isinstance(value, bool) or value < 0:
        raise DatasetReleaseError(f"{label} must be a non-negative integer.")
    return value


def _string(value: object, label: str) -> str:
    if not isinstance(value, str) or not value.strip():
        raise DatasetReleaseError(f"{label} must be a non-empty string.")
    return value.strip()


def _exact_string(value: object, label: str) -> str:
    """Require identifiers and class names without silent whitespace normalisation."""
    if not isinstance(value, str) or not value or value != value.strip():
        raise DatasetReleaseError(f"{label} must be a non-empty string without surrounding whitespace.")
    return value


def _only_fields(value: Mapping[str, object], label: str, allowed: set[str]) -> None:
    unexpected = sorted(set(value) - allowed)
    if unexpected:
        raise DatasetReleaseError(f"{label} has unsupported field(s): {', '.join(unexpected)}.")


def _source_taxonomy(dataset_yaml: Mapping[str, object]) -> dict[int, str]:
    names = dataset_yaml.get("names")
    pairs: list[tuple[int, str]] = []
    if isinstance(names, list):
        pairs = [(index, _exact_string(name, f"source dataset YAML names[{index}]")) for index, name in enumerate(names)]
    elif isinstance(names, Mapping):
        for raw_id, raw_name in names.items():
            try:
                class_id = int(raw_id)
            except (TypeError, ValueError) as exc:
                raise DatasetReleaseError("source dataset YAML names contains a non-integer class ID.") from exc
            if isinstance(raw_id, bool):
                raise DatasetReleaseError("source dataset YAML names contains a boolean class ID.")
            pairs.append((_integer(class_id, "source dataset YAML class ID"), _exact_string(raw_name, "source dataset YAML class name")))
    else:
        raise DatasetReleaseError("source dataset YAML must define names as a list or ID-to-name object.")
    pairs.sort(key=lambda item: item[0])
    if [class_id for class_id, _ in pairs] != list(range(len(pairs))):
        raise DatasetReleaseError("source dataset YAML class IDs must be contiguous and start at zero.")
    if len({name.casefold() for _, name in pairs}) != len(pairs):
        raise DatasetReleaseError("source dataset YAML class names must be unique.")
    if "nc" in dataset_yaml and _integer(dataset_yaml["nc"], "source dataset YAML nc") != len(pairs):
        raise DatasetReleaseError("source dataset YAML nc must exactly match the number of named source classes.")
    return dict(pairs)


def _config_source_taxonomy(mapping_config: Mapping[str, object]) -> dict[int, str]:
    result: dict[int, str] = {}
    configured_ids: list[int] = []
    for index, raw_item in enumerate(_list(mapping_config.get("source_taxonomy"), "mapping source_taxonomy")):
        item = _mapping(raw_item, f"mapping source_taxonomy[{index}]")
        _only_fields(item, f"mapping source_taxonomy[{index}]", {"id", "name"})
        class_id = _integer(item.get("id"), f"mapping source_taxonomy[{index}].id")
        name = _exact_string(item.get("name"), f"mapping source_taxonomy[{index}].name")
        if class_id in result or name.casefold() in {known.casefold() for known in result.values()}:
            raise DatasetReleaseError("mapping source_taxonomy contains duplicate class IDs or names.")
        result[class_id] = name
        configured_ids.append(class_id)
    if not result or configured_ids != list(range(len(result))):
        raise DatasetReleaseError("mapping source_taxonomy must use contiguous IDs starting at zero in exact ID order.")
    return dict(sorted(result.items()))


def _class_decisions(mapping_config: Mapping[str, object], source_taxonomy: Mapping[int, str]) -> tuple[dict[int, tuple[int, str, str]], dict[int, str], dict[int, str]]:
    mapped: dict[int, tuple[int, str, str]] = {}
    excluded: dict[int, str] = {}
    unresolved: dict[int, str] = {}
    for key, target in (("class_mapping", mapped), ("excluded_source_classes", excluded), ("unmapped_source_classes", unresolved)):
        for index, raw_item in enumerate(_list(mapping_config.get(key, []), f"mapping {key}")):
            item = _mapping(raw_item, f"mapping {key}[{index}]")
            _only_fields(
                item,
                f"mapping {key}[{index}]",
                {"source_class_id", "target_class_id", "target_class_name", "mapping_rationale"}
                if key == "class_mapping"
                else {"source_class_id", "reason"},
            )
            source_id = _integer(item.get("source_class_id"), f"mapping {key}[{index}].source_class_id")
            if source_id not in source_taxonomy:
                raise DatasetReleaseError(f"mapping {key}[{index}] references unknown source class ID {source_id}.")
            if source_id in mapped or source_id in excluded or source_id in unresolved:
                raise DatasetReleaseError(f"source class ID {source_id} has duplicate or ambiguous mapping decisions.")
            if key == "class_mapping":
                target_id = _integer(item.get("target_class_id"), f"mapping class_mapping[{index}].target_class_id")
                target_name = _exact_string(item.get("target_class_name"), f"mapping class_mapping[{index}].target_class_name")
                rationale = _string(item.get("mapping_rationale"), f"mapping class_mapping[{index}].mapping_rationale")
                if CANONICAL_TARGETS.get(target_id) != target_name:
                    raise DatasetReleaseError(f"mapping class_mapping[{index}] must use an exact approved target ID/name pair.")
                mapped[source_id] = (target_id, target_name, rationale)
            else:
                reason = _string(item.get("reason"), f"mapping {key}[{index}].reason")
                target[source_id] = reason  # type: ignore[index]
    missing = sorted(set(source_taxonomy) - set(mapped) - set(excluded) - set(unresolved))
    if missing:
        raise DatasetReleaseError(f"mapping has no explicit decision for source class IDs: {missing}.")
    if unresolved:
        raise DatasetReleaseError(f"mapping has unresolved source class IDs and cannot build a release: {sorted(unresolved)}.")
    return mapped, excluded, unresolved


def _parse_label(label_path: Path, source_taxonomy: Mapping[int, str], mapped: Mapping[int, tuple[int, str, str]], excluded: Mapping[int, str]) -> tuple[list[tuple[int, tuple[str, str, str, str]]], Counter[int], Counter[int]]:
    try:
        lines = label_path.read_text(encoding="utf-8-sig").splitlines()
    except UnicodeDecodeError as exc:
        raise DatasetReleaseError(f"source label is not UTF-8 text: {label_path.name}") from exc
    except OSError as exc:
        raise DatasetReleaseError(f"source label could not be read: {label_path.name}") from exc
    kept: list[tuple[int, tuple[str, str, str, str]]] = []
    source_counts: Counter[int] = Counter()
    excluded_counts: Counter[int] = Counter()
    for line_number, line in enumerate(lines, start=1):
        if not line.strip():
            continue
        values = line.split()
        if len(values) != 5:
            raise DatasetReleaseError(f"{label_path.name}:{line_number} must contain exactly five YOLO fields.")
        try:
            source_id = int(values[0])
        except ValueError as exc:
            raise DatasetReleaseError(f"{label_path.name}:{line_number} has a non-integer class ID.") from exc
        if str(source_id) != values[0] or source_id not in source_taxonomy:
            raise DatasetReleaseError(f"{label_path.name}:{line_number} references unknown source class ID {values[0]!r}.")
        coordinates: list[float] = []
        for coordinate in values[1:]:
            try:
                parsed = float(coordinate)
            except ValueError as exc:
                raise DatasetReleaseError(f"{label_path.name}:{line_number} contains a non-numeric coordinate.") from exc
            if not math.isfinite(parsed):
                raise DatasetReleaseError(f"{label_path.name}:{line_number} contains a non-finite coordinate.")
            coordinates.append(parsed)
        x_center, y_center, width, height = coordinates
        if width <= 0 or height <= 0 or x_center - width / 2 < 0 or x_center + width / 2 > 1 or y_center - height / 2 < 0 or y_center + height / 2 > 1:
            raise DatasetReleaseError(f"{label_path.name}:{line_number} has an out-of-bounds normalized YOLO bounding box.")
        source_counts[source_id] += 1
        if source_id in excluded:
            excluded_counts[source_id] += 1
            continue
        target = mapped.get(source_id)
        if target is None:
            raise DatasetReleaseError(f"{label_path.name}:{line_number} refers to an unresolved source class ID {source_id}.")
        kept.append((target[0], (values[1], values[2], values[3], values[4])))
    return kept, source_counts, excluded_counts


def _label_text(rows: Sequence[tuple[int, tuple[str, str, str, str]]]) -> str:
    return "".join(f"{class_id} {' '.join(coordinates)}\n" for class_id, coordinates in rows)


def _canonical_yaml(*, include_test: bool) -> str:
    lines = ["path: .", "train: images/train", "val: images/val", "nc: 8", "names:"]
    if include_test:
        lines.insert(3, "test: images/test")
    lines.extend(f"  {class_id}: {name}" for class_id, name in CANONICAL_TAXONOMY)
    return "\n".join(lines) + "\n"


def _git_metadata() -> tuple[str | None, bool | None]:
    try:
        commit = subprocess.run(["git", "rev-parse", "HEAD"], cwd=REPOSITORY_ROOT, text=True, stdout=subprocess.PIPE, stderr=subprocess.DEVNULL, check=False).stdout.strip()
        dirty = bool(subprocess.run(["git", "status", "--porcelain"], cwd=REPOSITORY_ROOT, text=True, stdout=subprocess.PIPE, stderr=subprocess.DEVNULL, check=False).stdout.strip())
    except OSError:
        return None, None
    return (commit or None), dirty


def _report_source_taxonomy(report: Mapping[str, object]) -> dict[int, str]:
    raw_items = report.get("source_taxonomy")
    if not isinstance(raw_items, list):
        raise DatasetReleaseError("inspection report lacks source_taxonomy; regenerate it with the current inspector.")
    items = _list(raw_items, "inspection report source_taxonomy")
    taxonomy: dict[int, str] = {}
    for index, raw_item in enumerate(items):
        item = _mapping(raw_item, f"inspection report source_taxonomy[{index}]")
        _only_fields(item, f"inspection report source_taxonomy[{index}]", {"id", "name"})
        class_id = _integer(item.get("id"), f"inspection report source_taxonomy[{index}].id")
        if class_id in taxonomy:
            raise DatasetReleaseError("inspection report source_taxonomy contains duplicate class IDs.")
        taxonomy[class_id] = _exact_string(item.get("name"), f"inspection report source_taxonomy[{index}].name")
    if list(taxonomy) != list(range(len(taxonomy))):
        raise DatasetReleaseError("inspection report source_taxonomy must use contiguous IDs in exact ID order; regenerate it.")
    return taxonomy


def _inspection_eligibility(
    report: Mapping[str, object], manifest: Mapping[str, object], source_taxonomy: Mapping[int, str]
) -> None:
    if report.get("quality_verdict") == "fail" or report.get("validation_errors"):
        raise DatasetReleaseError("dataset inspection report records a failing quality result.")
    dataset = _mapping(manifest.get("dataset"), "source manifest dataset")
    manifest_id = _exact_string(dataset.get("id"), "source manifest dataset.id")
    manifest_version = _exact_string(dataset.get("source_version"), "source manifest dataset.source_version")
    report_id = report.get("dataset_identity")
    report_version = report.get("dataset_source_version")
    if not isinstance(report_id, str) or not report_id or report_id != report_id.strip():
        raise DatasetReleaseError(
            "inspection report lacks dataset_identity; regenerate it with the current inspector and reviewed metadata."
        )
    if not isinstance(report_version, str) or not report_version or report_version != report_version.strip():
        raise DatasetReleaseError(
            "inspection report lacks dataset_source_version; regenerate it with the current inspector and reviewed metadata."
        )
    if report_id != manifest_id:
        raise DatasetReleaseError("inspection report dataset identity does not match the source manifest.")
    if report_version != manifest_version:
        raise DatasetReleaseError("inspection report source version does not match the source manifest.")
    if _report_source_taxonomy(report) != dict(source_taxonomy):
        raise DatasetReleaseError(
            "inspection report source taxonomy does not exactly match the current source dataset YAML; regenerate it."
        )
    duplicates = _mapping(report.get("duplicates"), "inspection report duplicates")
    for key in ("cross_split_duplicate_images", "cross_split_group_leakage"):
        if duplicates.get(key):
            raise DatasetReleaseError(f"inspection report records {key}; split leakage blocks release generation.")


def _manifest_eligibility(manifest: Mapping[str, object], source_root: Path) -> None:
    issues = manifest_validator.validate_manifest(manifest, dataset_root=source_root, check_files=True)
    if issues:
        raise DatasetReleaseError("source manifest is invalid:\n" + manifest_validator.format_issues(issues))
    licence = _mapping(manifest.get("licence"), "source manifest licence")
    if licence.get("review_decision") != "approved" or licence.get("machine_learning_use_permitted") is not True:
        raise DatasetReleaseError("source manifest requires an approved licence review permitting machine-learning use.")


def _release_metadata(mapping_config: Mapping[str, object], release_name: str, release_version: str) -> dict[str, object]:
    raw = _mapping(mapping_config.get("release_metadata"), "mapping release_metadata")
    _only_fields(
        raw,
        "mapping release_metadata",
        {"dataset", "source_provenance", "licence", "storage_release", "quality_review_status", "known_limitations"},
    )
    result = copy.deepcopy(raw)
    dataset = _mapping(result.get("dataset"), "release metadata dataset")
    dataset = dict(dataset)
    dataset.setdefault("release_decision", "under_review")
    if dataset.get("id") != release_name:
        raise DatasetReleaseError("release metadata dataset.id must exactly match --release-name.")
    result["dataset"] = dataset
    storage = _mapping(result.get("storage_release"), "release metadata storage_release")
    storage = dict(storage)
    storage["release_version"] = release_version
    # A manifest cannot truthfully checksum itself.  The completed checksum is
    # recorded in release_checksums.json and the build report instead.
    storage.pop("manifest_checksum", None)
    result["storage_release"] = storage
    if dataset.get("release_decision") == "approved_for_training":
        licence = _mapping(result.get("licence"), "release metadata licence")
        if licence.get("review_decision") != "approved" or licence.get("machine_learning_use_permitted") is not True:
            raise DatasetReleaseError(
                "approved_for_training requires an explicitly approved release licence review permitting machine-learning use."
            )
        if result.get("quality_review_status") != "completed":
            raise DatasetReleaseError(
                "approved_for_training requires explicitly completed release quality review metadata."
            )
    return result


def _check_output_boundary(source_root: Path, output_root: Path) -> None:
    resolved_source, resolved_output = source_root.resolve(), output_root.resolve()
    if _is_beneath(resolved_source, resolved_output):
        raise DatasetReleaseError("output root must not be inside the source dataset root.")
    if _is_beneath(resolved_output, resolved_source):
        raise DatasetReleaseError("source dataset root must not be inside the output root.")
    if _is_beneath(REPOSITORY_ROOT, resolved_output):
        raise DatasetReleaseError("output root must be outside the repository so generated releases cannot enter Git.")


def _output_split_directory(split: str) -> str:
    """Use YOLO's common ``val`` directory while retaining manifest ``validation``."""
    return "val" if split == "validation" else split


def _source_samples(manifest: Mapping[str, object]) -> list[tuple[str, Mapping[str, object]]]:
    samples: list[tuple[str, Mapping[str, object]]] = []
    for split, _, sample in manifest_validator._iter_samples(manifest):
        if split not in SPLITS:
            raise DatasetReleaseError(f"source manifest contains unsupported split {split!r}.")
        samples.append((split, sample))
    return sorted(samples, key=lambda value: (SPLITS.index(value[0]), str(value[1].get("sample_id")), str(value[1].get("image_path"))))


def _validate_source_layout(
    source_root: Path,
    source_yaml: Mapping[str, object],
    source_samples: Sequence[tuple[str, Mapping[str, object]]],
) -> None:
    """Ensure the manifest represents the inspected YAML split directories exactly."""
    layout_errors: list[dict[str, str]] = []
    layout = inspector._resolve_layout(source_root, source_yaml, layout_errors)
    if layout_errors:
        raise DatasetReleaseError(
            "source dataset YAML has unsafe or missing split paths: " + json.dumps(layout_errors, sort_keys=True)
        )
    manifest_paths: dict[str, tuple[set[Path], set[Path]]] = {
        split: (set(), set()) for split in SPLITS
    }
    for split, sample in source_samples:
        image = _relative_reference(source_root, sample.get("image_path"), f"source manifest image_path for {sample.get('sample_id')}")
        label = _relative_reference(source_root, sample.get("label_path"), f"source manifest label_path for {sample.get('sample_id')}")
        if split not in layout:
            raise DatasetReleaseError(f"source dataset YAML does not define the manifest {split} split.")
        image_directory = layout[split]["image_directory"]
        label_directory = layout[split]["label_directory"]
        assert isinstance(image_directory, Path) and isinstance(label_directory, Path)
        if not _is_beneath(image_directory, image) or not _is_beneath(label_directory, label):
            raise DatasetReleaseError(f"source manifest sample {sample.get('sample_id')!r} is outside its declared {split} YAML split.")
        manifest_paths[split][0].add(image)
        manifest_paths[split][1].add(label)
    for split, details in layout.items():
        image_directory, label_directory = details["image_directory"], details["label_directory"]
        assert isinstance(image_directory, Path) and isinstance(label_directory, Path)
        if not label_directory.is_dir():
            raise DatasetReleaseError(f"source dataset YAML {split} labels directory is missing.")
        actual_images = {
            path.resolve()
            for path in image_directory.rglob("*")
            if path.is_file() and path.suffix.casefold() in manifest_validator.IMAGE_EXTENSIONS and _is_beneath(source_root, path)
        }
        actual_labels = {
            path.resolve()
            for path in label_directory.rglob("*")
            if path.is_file() and path.suffix.casefold() == ".txt" and _is_beneath(source_root, path)
        }
        expected_images, expected_labels = manifest_paths[split]
        if actual_images != expected_images:
            raise DatasetReleaseError(f"source manifest does not exactly represent the supported images in the {split} split.")
        if actual_labels != expected_labels:
            raise DatasetReleaseError(f"source manifest does not exactly represent the label files in the {split} split (including orphan labels).")


def create_release_plan(
    *, source_root: Path, source_yaml_path: Path, source_manifest_path: Path, inspection_report_path: Path,
    mapping_path: Path, output_root: Path, release_name: str, release_version: str,
    empty_image_policy: str | None = None,
) -> ReleasePlan:
    """Validate local inputs and calculate a complete deterministic release plan."""
    for path, label in ((source_root, "source dataset root"), (source_yaml_path, "source dataset YAML"), (source_manifest_path, "source manifest"), (inspection_report_path, "inspection report"), (mapping_path, "mapping configuration"), (output_root, "output root")):
        _reject_nonlocal_path(path, label)
    source_root = source_root.resolve()
    if not source_root.is_dir():
        raise DatasetReleaseError("source dataset root is not an existing directory.")
    source_yaml_path = _require_beneath(source_root, source_yaml_path, "source dataset YAML")
    source_manifest_path = source_manifest_path.resolve()
    inspection_report_path = inspection_report_path.resolve()
    mapping_path = mapping_path.resolve()
    for path, label in ((source_manifest_path, "source manifest"), (inspection_report_path, "inspection report"), (mapping_path, "mapping configuration")):
        if not path.is_file():
            raise DatasetReleaseError(f"{label} is not an existing file: {path}")
    output_root = output_root.resolve()
    _check_output_boundary(source_root, output_root)
    release_name, release_version = _safe_name(release_name, "release name"), _safe_name(release_version, "release version")
    release_root = output_root / release_name / release_version
    if release_root.exists():
        raise DatasetReleaseError("completed or partial release path already exists and is protected from overwrite.")

    source_yaml = _load_structured(source_yaml_path, "source dataset YAML")
    manifest_path, source_manifest = manifest_validator.load_manifest(source_manifest_path)
    report = _load_structured(inspection_report_path, "inspection report")
    mapping_config = _load_structured(mapping_path, "mapping configuration")
    if mapping_config.get("schema_version") != "1.0.0":
        raise DatasetReleaseError("mapping configuration schema_version must be '1.0.0'.")
    _only_fields(
        mapping_config,
        "mapping configuration",
        {
            "schema_version",
            "source_taxonomy",
            "class_mapping",
            "excluded_source_classes",
            "unmapped_source_classes",
            "empty_image_policy",
            "release_metadata",
        },
    )
    source_taxonomy = _source_taxonomy(source_yaml)
    _manifest_eligibility(source_manifest, source_root)
    _inspection_eligibility(report, source_manifest, source_taxonomy)
    if source_taxonomy != _config_source_taxonomy(mapping_config):
        raise DatasetReleaseError("source dataset YAML taxonomy does not exactly match mapping source_taxonomy.")
    mapped, excluded, _ = _class_decisions(mapping_config, source_taxonomy)
    chosen_policy = empty_image_policy or _exact_string(mapping_config.get("empty_image_policy", "retain_negative"), "mapping empty_image_policy")
    if chosen_policy not in EMPTY_POLICIES:
        raise DatasetReleaseError("empty image policy must be retain_negative or exclude_image.")
    _release_metadata(mapping_config, release_name, release_version)
    source_samples = _source_samples(source_manifest)
    _validate_source_layout(source_root, source_yaml, source_samples)

    samples: list[PlannedSample] = []
    source_counts: Counter[int] = Counter()
    target_counts: Counter[int] = Counter()
    excluded_counts: Counter[int] = Counter()
    stems_by_split: dict[str, set[str]] = {split: set() for split in SPLITS}
    image_checksum_splits: dict[str, set[str]] = {}
    for split, sample in source_samples:
        sample_id = _string(sample.get("sample_id"), "source manifest sample_id")
        group_id = _string(sample.get("group_id"), "source manifest group_id")
        if sample.get("labelled") is not True:
            raise DatasetReleaseError(f"source manifest sample {sample_id!r} is not a labelled YOLO sample.")
        image = _relative_reference(source_root, sample.get("image_path"), f"source manifest image_path for {sample_id}")
        label = _relative_reference(source_root, sample.get("label_path"), f"source manifest label_path for {sample_id}")
        if not image.is_file() or not label.is_file():
            raise DatasetReleaseError(f"source manifest sample {sample_id!r} is missing its required image or label file.")
        if image.suffix.casefold() not in manifest_validator.IMAGE_EXTENSIONS:
            raise DatasetReleaseError(f"source manifest sample {sample_id!r} has an unsupported image extension.")
        stem_key = image.stem.casefold()
        if stem_key in stems_by_split[split]:
            raise DatasetReleaseError(f"source manifest has a same-stem image collision in {split}: {image.stem!r}.")
        stems_by_split[split].add(stem_key)
        image_checksum = _sha256(image)
        image_checksum_splits.setdefault(image_checksum, set()).add(split)
        rows, current_source_counts, current_excluded_counts = _parse_label(label, source_taxonomy, mapped, excluded)
        source_counts.update(current_source_counts)
        excluded_counts.update(current_excluded_counts)
        source_empty_negative = not current_source_counts
        exclusion_created_negative = bool(current_source_counts) and not rows
        if exclusion_created_negative and chosen_policy == "exclude_image":
            continue
        label_text = _label_text(rows)
        target_counts.update(class_id for class_id, _ in rows)
        output_split = _output_split_directory(split)
        destination_image = f"images/{output_split}/{image.name}"
        destination_label = f"labels/{output_split}/{image.stem}.txt"
        samples.append(PlannedSample(split, sample_id, group_id, image, destination_image, destination_label, label_text, image_checksum, tuple(class_id for class_id, _ in rows), source_empty_negative, exclusion_created_negative))
    if not samples:
        raise DatasetReleaseError("mapping and empty-image policy leave no samples for the release.")
    leaking_checksums = [checksum for checksum, split_names in image_checksum_splits.items() if len(split_names) > 1]
    if leaking_checksums:
        raise DatasetReleaseError("source file checksums reveal duplicate images across splits; split leakage blocks release generation.")

    inputs = {
        "source_manifest_sha256": _sha256(manifest_path),
        "source_inspection_report_sha256": _sha256(inspection_report_path),
        "source_dataset_yaml_sha256": _sha256(source_yaml_path),
        "mapping_configuration_sha256": _sha256(mapping_path),
    }
    identity_material = {
        "tool": {"name": TOOL_NAME, "version": TOOL_VERSION}, "release_name": release_name, "release_version": release_version,
        "input_checksums": inputs,
        "samples": [{"split": sample.split, "sample_id": sample.sample_id, "image": sample.destination_image, "image_sha256": sample.image_checksum, "label": sample.destination_label, "label_sha256": hashlib.sha256(sample.label_text.encode("utf-8")).hexdigest()} for sample in samples],
    }
    commit, dirty = _git_metadata()
    plan = ReleasePlan(source_root, manifest_path, source_yaml_path, inspection_report_path, mapping_path, output_root, release_root, release_name, release_version, chosen_policy, source_manifest, mapping_config, tuple(samples), dict(source_counts), dict(target_counts), dict(excluded_counts), inputs, hashlib.sha256(_json_text(identity_material).encode("utf-8")).hexdigest(), commit, dirty)
    manifest_issues = manifest_validator.validate_manifest(_release_manifest(plan))
    if manifest_issues:
        raise DatasetReleaseError("release metadata cannot produce a valid manifest:\n" + manifest_validator.format_issues(manifest_issues))
    return plan


def _release_manifest(plan: ReleasePlan) -> dict[str, object]:
    metadata = _release_metadata(plan.mapping, plan.release_name, plan.release_version)
    source_taxonomy = _config_source_taxonomy(plan.mapping)
    mapped, excluded, _ = _class_decisions(plan.mapping, source_taxonomy)
    split_samples: dict[str, list[dict[str, object]]] = {split: [] for split in SPLITS}
    for sample in plan.samples:
        split_samples[sample.split].append({
            "sample_id": sample.sample_id, "image_path": sample.destination_image, "label_path": sample.destination_label,
            "group_id": sample.group_id, "labelled": True, "checksum": f"sha256:{sample.image_checksum}",
            "annotation_summary": {"bounding_box_count": len(sample.annotation_class_ids), "class_ids": list(sample.annotation_class_ids)},
        })
    return {
        "schema_version": "1.0.0", "dataset": metadata["dataset"], "source_provenance": metadata["source_provenance"], "licence": metadata["licence"],
        "taxonomy": {
            "target_classes": [{"id": class_id, "name": name} for class_id, name in CANONICAL_TAXONOMY],
            "class_mappings": [{"source_class": source_taxonomy[source_id], "target_class_id": target_id, "target_class_name": target_name, "mapping_rationale": rationale, "review_decision": "mapped"} for source_id, (target_id, target_name, rationale) in sorted(mapped.items())],
            "excluded_source_classes": [{"source_class": source_taxonomy[source_id], "reason": reason} for source_id, reason in sorted(excluded.items())],
            "unmapped_source_classes": [], "bounding_box_coordinate_format": "normalized_xywh",
        },
        "splits": {split: {"samples": split_samples[split]} for split in SPLITS},
        "quality": {"image_count": len(plan.samples), "annotation_count": sum(plan.target_counts.values()), "duplicate_count": 0, "corrupt_file_count": 0, "invalid_annotation_count": 0, "excluded_sample_count": len(_source_samples(plan.source_manifest)) - len(plan.samples), "quality_review_status": metadata["quality_review_status"], "known_limitations": metadata["known_limitations"], "checksums": {"release_identity": f"sha256:{plan.release_identity}"}},
        "storage_release": metadata["storage_release"],
    }


def _report_payload(plan: ReleasePlan, status: str, *, output_checksums: Mapping[str, str] | None = None, verification: Mapping[str, object] | None = None) -> dict[str, object]:
    split_counts = {split: sum(1 for sample in plan.samples if sample.split == split) for split in SPLITS}
    source_split_counts = {split: 0 for split in SPLITS}
    for split, _ in _source_samples(plan.source_manifest):
        source_split_counts[split] += 1
    return {
        "tool": {"name": TOOL_NAME, "version": TOOL_VERSION, "network_access": False}, "status": status,
        "release": {"name": plan.release_name, "version": plan.release_version, "identity_sha256": plan.release_identity, "release_decision": _release_metadata(plan.mapping, plan.release_name, plan.release_version)["dataset"]["release_decision"]},
        "source": {"dataset_id": _mapping(plan.source_manifest["dataset"], "source manifest dataset")["id"], "source_version": _mapping(plan.source_manifest["dataset"], "source manifest dataset")["source_version"], "input_checksums": plan.input_checksums},
        "counts": {"source_images_by_split": source_split_counts, "output_images_by_split": split_counts, "output_label_files": len(plan.samples), "excluded_images": sum(source_split_counts.values()) - len(plan.samples), "source_annotations_by_class": [{"id": key, "name": _config_source_taxonomy(plan.mapping)[key], "count": plan.source_counts.get(key, 0)} for key in sorted(_config_source_taxonomy(plan.mapping))], "mapped_annotations_by_target_class": [{"id": key, "name": CANONICAL_TARGETS[key], "count": plan.target_counts.get(key, 0)} for key in sorted(CANONICAL_TARGETS)], "excluded_annotations_by_source_class": [{"id": key, "name": _config_source_taxonomy(plan.mapping)[key], "count": plan.excluded_counts.get(key, 0)} for key in sorted(plan.excluded_counts)], "retained_negative_images": sum(1 for sample in plan.samples if sample.source_empty_negative or sample.exclusion_created_negative), "source_empty_negative_images": sum(1 for sample in plan.samples if sample.source_empty_negative), "exclusion_created_negative_images": sum(1 for sample in plan.samples if sample.exclusion_created_negative), "file_copy_total": len(plan.samples) * 2},
        "empty_image_policy": plan.empty_image_policy, "output_checksums": dict(sorted((output_checksums or {}).items())), "verification": dict(verification or {}),
        "intended_output_files": sorted({"dataset.yaml", "release_manifest.json", "release_build_report.json", "release_build_report.md", "release_checksums.json", *(sample.destination_image for sample in plan.samples), *(sample.destination_label for sample in plan.samples)}),
        "git": {"commit": plan.git_commit, "dirty": plan.git_dirty},
        "warnings": ["A completed release is not legal, privacy, ethical, model-quality, safety, or production approval."], "failures": [],
    }


def _markdown_report(report: Mapping[str, object]) -> str:
    def table(headers: Sequence[str], rows: Sequence[Sequence[object]]) -> list[str]:
        return [
            "| " + " | ".join(headers) + " |",
            "| " + " | ".join("---" for _ in headers) + " |",
            *("| " + " | ".join(str(value) for value in row) + " |" for row in rows),
        ]

    counts = _mapping(report["counts"], "report counts")
    release = _mapping(report["release"], "release")
    source = _mapping(report["source"], "source")
    lines = [
        "# WalkBuddy navigation dataset release build",
        "",
        f"Status: `{report['status']}`.",
        "",
        "## Release",
        "",
        f"- Name: `{release['name']}`",
        f"- Version: `{release['version']}`",
        f"- Decision: `{release['release_decision']}`",
        f"- Deterministic identity: `{release['identity_sha256']}`",
        f"- Source dataset: `{source['dataset_id']}` version `{source['source_version']}`",
        "",
        "## Sample counts",
        "",
    ]
    source_split_counts = _mapping(counts["source_images_by_split"], "source split counts")
    output_split_counts = _mapping(counts["output_images_by_split"], "output split counts")
    lines.extend(
        table(
            ["Split", "Source images", "Released images"],
            [(split, source_split_counts[split], output_split_counts[split]) for split in SPLITS],
        )
    )
    lines.extend(
        [
            "",
            f"- Excluded images: {_integer(counts['excluded_images'], 'excluded images')}",
            f"- Retained negative images: {_integer(counts['retained_negative_images'], 'retained negative images')}",
            f"- Source-empty negatives retained: {_integer(counts['source_empty_negative_images'], 'source-empty negatives')}",
            f"- Exclusion-created negatives retained: {_integer(counts['exclusion_created_negative_images'], 'exclusion-created negatives')}",
            f"- Output label files: {_integer(counts['output_label_files'], 'output label files')}",
            f"- File copies: {_integer(counts['file_copy_total'], 'file copy total')}",
            "",
            "## Annotation counts",
            "",
        ]
    )
    lines.extend(
        table(
            ["Source ID", "Class", "Source annotations", "Excluded annotations"],
            [
                (item["id"], item["name"], item["count"], next((excluded["count"] for excluded in counts["excluded_annotations_by_source_class"] if excluded["id"] == item["id"]), 0))
                for item in counts["source_annotations_by_class"]
            ],
        )
    )
    lines.extend(["", "## Canonical mapped annotations", ""])
    lines.extend(
        table(
            ["Target ID", "Class", "Mapped annotations"],
            [(item["id"], item["name"], item["count"]) for item in counts["mapped_annotations_by_target_class"]],
        )
    )
    lines.extend(["", "## Verification and checksums", ""])
    verification = _mapping(report["verification"], "verification")
    lines.extend(f"- `{key}`: `{value}`" for key, value in sorted(verification.items()))
    lines.extend(f"- Input `{key}`: `{value}`" for key, value in sorted(_mapping(source["input_checksums"], "input checksums").items()))
    lines.extend(f"- Output `{key}`: `{value}`" for key, value in sorted(_mapping(report["output_checksums"], "output checksums").items()))
    lines.extend(["", "## Warnings and failures", ""])
    warnings = _list(report["warnings"], "warnings")
    failures = _list(report["failures"], "failures")
    lines.extend(f"- Warning: {warning}" for warning in warnings) if warnings else lines.append("- No warnings.")
    lines.extend(f"- Failure: {failure}" for failure in failures) if failures else lines.append("- No failures.")
    lines.extend(["", "## Limitations", "", "- A completed release does not establish legal, privacy, ethical, model-quality, safety, or production approval.", "- Only an explicitly reviewed manifest decision may make this release eligible for training.", ""])
    return "\n".join(lines)


def _write_text(path: Path, content: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding="utf-8", newline="\n")


def _inspection_metadata() -> dict[str, object]:
    return {"class_mapping": [{"source_class_id": class_id, "target_class_id": class_id, "target_class_name": name, "mapping_rationale": "Canonical release verification identity mapping."} for class_id, name in CANONICAL_TAXONOMY], "excluded_source_classes": [], "unmapped_source_classes": []}


def _verify_staging(plan: ReleasePlan, staging: Path, manifest: Mapping[str, object]) -> dict[str, object]:
    issues = manifest_validator.validate_manifest(manifest, dataset_root=staging, check_files=True)
    if issues:
        raise DatasetReleaseError("generated release manifest is invalid:\n" + manifest_validator.format_issues(issues))
    for sample in plan.samples:
        image = staging / sample.destination_image
        label = staging / sample.destination_label
        if not image.is_file() or not label.is_file() or not _is_beneath(staging, image) or not _is_beneath(staging, label):
            raise DatasetReleaseError("generated release contains a missing or escaped destination file.")
        rows, _, _ = _parse_label(label, dict(CANONICAL_TAXONOMY), {key: (key, name, "identity") for key, name in CANONICAL_TAXONOMY}, {})
        if tuple(class_id for class_id, _ in rows) != sample.annotation_class_ids:
            raise DatasetReleaseError("generated release label verification found a changed class mapping.")
    metadata_path = staging / ".release_inspection_metadata.json"
    group_map_path = staging / ".release_groups.json"
    try:
        _write_text(metadata_path, _json_text(_inspection_metadata()))
        _write_text(group_map_path, _json_text({"groups": {sample.destination_image: sample.group_id for sample in plan.samples}}))
        report, _ = inspector.inspect_dataset(staging, staging / "dataset.yaml", metadata_path=metadata_path, group_map_path=group_map_path, generate_manifest=False)
    finally:
        metadata_path.unlink(missing_ok=True)
        group_map_path.unlink(missing_ok=True)
    if report.get("quality_verdict") not in {"pass", "pass_with_warnings"}:
        findings = report.get("validation_errors")
        raise DatasetReleaseError(
            "generated release fails the existing candidate dataset inspector: "
            + json.dumps(findings, sort_keys=True)
        )
    return {"manifest_validator": "pass", "candidate_inspector_verdict": report.get("quality_verdict"), "destination_sample_count": len(plan.samples)}


def _output_checksums(staging: Path) -> dict[str, str]:
    return {path.relative_to(staging).as_posix(): _sha256(path) for path in sorted(staging.rglob("*")) if path.is_file()}


def build_release(plan: ReleasePlan, *, confirm_build: bool) -> dict[str, object]:
    """Construct a verified release only after explicit caller confirmation."""
    if not confirm_build:
        raise DatasetReleaseError("real release creation requires --confirm-build; use --dry-run first.")
    if plan.release_root.exists():
        raise DatasetReleaseError("completed or partial release path already exists and is protected from overwrite.")
    plan.release_root.parent.mkdir(parents=True, exist_ok=True)
    staging = plan.release_root.parent / f".{plan.release_root.name}.staging-{uuid.uuid4().hex}"
    try:
        staging.mkdir()
        for sample in plan.samples:
            destination_image = staging / sample.destination_image
            destination_label = staging / sample.destination_label
            destination_image.parent.mkdir(parents=True, exist_ok=True)
            destination_label.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(sample.source_image, destination_image)
            _write_text(destination_label, sample.label_text)
        _write_text(staging / "dataset.yaml", _canonical_yaml(include_test=any(sample.split == "test" for sample in plan.samples)))
        manifest = _release_manifest(plan)
        _write_text(staging / "release_manifest.json", _json_text(manifest))
        verification = _verify_staging(plan, staging, manifest)
        checksums = _output_checksums(staging)
        for relative_path, checksum in checksums.items():
            if _sha256(staging / relative_path) != checksum:
                raise DatasetReleaseError("generated release checksum verification failed.")
        _write_text(staging / "release_checksums.json", _json_text({"algorithm": "sha256", "release_identity": plan.release_identity, "files": checksums}))
        report = _report_payload(plan, "completed", output_checksums=checksums, verification=verification)
        _write_text(staging / "release_build_report.json", _json_text(report))
        _write_text(staging / "release_build_report.md", _markdown_report(report))
        staging.replace(plan.release_root)
        return report
    except BaseException:
        shutil.rmtree(staging, ignore_errors=True)
        raise


def dry_run(plan: ReleasePlan) -> dict[str, object]:
    """Return the complete plan without creating directories or copying files."""
    return _report_payload(plan, "planned", verification={"validation": "completed without filesystem writes"})


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Build a reviewed local YOLO dataset release in the canonical WalkBuddy taxonomy.")
    parser.add_argument("--source-root", required=True, type=Path, help="Controlled local source dataset root.")
    parser.add_argument("--source-yaml", required=True, type=Path, help="Source YOLO dataset YAML beneath --source-root.")
    parser.add_argument("--source-manifest", required=True, type=Path, help="Validated local source manifest JSON.")
    parser.add_argument("--inspection-report", required=True, type=Path, help="Passing local candidate-inspection JSON report.")
    parser.add_argument("--mapping-config", required=True, type=Path, help="Reviewed local source-to-WalkBuddy mapping JSON or YAML.")
    parser.add_argument("--output-root", required=True, type=Path, help="Controlled external root for generated releases.")
    parser.add_argument("--release-name", required=True, help="Release dataset identifier, matching mapping release_metadata.dataset.id.")
    parser.add_argument("--release-version", required=True, help="Version component for the controlled release directory.")
    parser.add_argument("--empty-image-policy", choices=sorted(EMPTY_POLICIES), help="Override the reviewed mapping policy for labels emptied by exclusion.")
    parser.add_argument("--dry-run", action="store_true", help="Validate and print the release plan without writing files.")
    parser.add_argument("--confirm-build", action="store_true", help="Explicitly permit creation of the copied release after validation.")
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    if args.dry_run and args.confirm_build:
        print("Dataset release build failed: --dry-run and --confirm-build cannot be used together.", file=sys.stderr)
        return 1
    try:
        plan = create_release_plan(source_root=args.source_root, source_yaml_path=args.source_yaml, source_manifest_path=args.source_manifest, inspection_report_path=args.inspection_report, mapping_path=args.mapping_config, output_root=args.output_root, release_name=args.release_name, release_version=args.release_version, empty_image_policy=args.empty_image_policy)
        report = dry_run(plan) if args.dry_run else build_release(plan, confirm_build=args.confirm_build)
    except DatasetReleaseError as exc:
        print(f"Dataset release build failed: {exc}", file=sys.stderr)
        return 1
    print(_json_text(report), end="")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
