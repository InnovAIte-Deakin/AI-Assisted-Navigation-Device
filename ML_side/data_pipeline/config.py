from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any

from .models import PipelineConfig, PipelineError, SourceConfig, VideoExtractionConfig


SAFE_RELEASE_ID = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._-]*$")


def _load_mapping(path: Path) -> dict[str, Any]:
    try:
        text = path.read_text(encoding="utf-8-sig")
    except OSError as exc:
        raise PipelineError(f"Could not read configuration file {path}: {exc}") from exc
    if path.suffix.lower() == ".json":
        try:
            value = json.loads(text)
        except json.JSONDecodeError as exc:
            raise PipelineError(f"Invalid JSON in {path}: {exc}") from exc
    else:
        try:
            import yaml  # type: ignore
        except ImportError as exc:
            raise PipelineError("PyYAML is required for YAML configuration files.") from exc
        try:
            value = yaml.safe_load(text)
        except Exception as exc:
            raise PipelineError(f"Invalid YAML in {path}: {exc}") from exc
    if not isinstance(value, dict):
        raise PipelineError(f"Configuration file must contain an object: {path}")
    return value


def _path(base: Path, value: object, field: str) -> Path:
    if not isinstance(value, str) or not value.strip():
        raise PipelineError(f"{field} must be a non-empty path string.")
    candidate = Path(value)
    return candidate.resolve() if candidate.is_absolute() else (base / candidate).resolve()


PROVENANCE_FIELDS = {
    "provider", "source", "folder", "url", "version", "licence", "license",
    "licence_url", "license_url", "governance_status", "status", "ethics",
}


def _download_sheet_sources(path: Path) -> dict[str, dict[str, Any]]:
    sheet = _load_mapping(path)
    datasets = sheet.get("datasets")
    if not isinstance(datasets, dict) or not datasets:
        raise PipelineError("download_sheet must contain a non-empty 'datasets' object.")
    result: dict[str, dict[str, Any]] = {}
    for source_id, value in datasets.items():
        if not isinstance(source_id, str) or not source_id.strip() or not isinstance(value, dict):
            raise PipelineError("Every download_sheet dataset must have a string ID and an object value.")
        result[source_id.strip()] = value
    return result


def _registry_folder(raw_root: Path, source_id: str, provider: str, value: object) -> Path:
    folder_text = str(value or source_id).strip()
    folder = Path(folder_text)
    if folder.is_absolute() or ".." in folder.parts:
        raise PipelineError(f"download_sheet dataset {source_id}: folder must be a safe relative path.")
    if not folder.parts:
        raise PipelineError(f"download_sheet dataset {source_id}: folder cannot be empty.")
    # Raw storage is grouped by provider in the existing repository. A sheet may
    # explicitly include that prefix; do not add it twice.
    if folder.parts[0].lower() != provider.lower():
        folder = Path(provider) / folder
    return (raw_root / folder).resolve()


def load_config(path: Path) -> PipelineConfig:
    raw = _load_mapping(path.resolve())
    base = path.resolve().parent
    release_id = str(raw.get("release_id", "")).strip()
    if not SAFE_RELEASE_ID.fullmatch(release_id):
        raise PipelineError("release_id must contain only letters, numbers, dots, underscores, and hyphens.")

    taxonomy_value = raw.get("taxonomy")
    if not isinstance(taxonomy_value, list) or not taxonomy_value or not all(
        isinstance(item, str) and item.strip() for item in taxonomy_value
    ):
        raise PipelineError("taxonomy must be a non-empty list of class names.")
    taxonomy = tuple(item.strip() for item in taxonomy_value)
    if len(set(taxonomy)) != len(taxonomy):
        raise PipelineError("taxonomy class names must be unique.")

    download_sheet_value = raw.get("download_sheet")
    download_sheet_path = (
        _path(base, download_sheet_value, "download_sheet")
        if download_sheet_value is not None
        else None
    )
    registry = _download_sheet_sources(download_sheet_path) if download_sheet_path else None

    sources_value = raw.get("sources")
    if not isinstance(sources_value, list) or not sources_value:
        raise PipelineError("sources must be a non-empty list.")
    raw_root = _path(base, raw.get("raw_root", "../datasets/raw"), "raw_root")
    sources: list[SourceConfig] = []
    seen: set[str] = set()
    for entry in sources_value:
        if not isinstance(entry, dict):
            raise PipelineError("Every source entry must be an object.")
        source_id = str(entry.get("id", "")).strip()
        if not source_id or source_id in seen:
            raise PipelineError(f"Invalid or duplicate source id: {source_id!r}")
        seen.add(source_id)
        registry_entry: dict[str, Any] | None = None
        if registry is not None:
            registry_entry = registry.get(source_id)
            if registry_entry is None:
                raise PipelineError(f"Source {source_id!r} is not defined in download_sheet {download_sheet_path}.")
            overrides = sorted(PROVENANCE_FIELDS.intersection(entry))
            if overrides:
                raise PipelineError(
                    f"Source {source_id}: provenance fields must come from download_sheet, not sources: "
                    + ", ".join(overrides)
                )
        tags = entry.get("environment_tags", ["unknown"])
        if not isinstance(tags, list) or not all(isinstance(tag, str) and tag for tag in tags):
            raise PipelineError(f"Source {source_id}: environment_tags must be a list of strings.")
        class_names = entry.get("class_names", [])
        if not isinstance(class_names, list) or not all(isinstance(name, str) for name in class_names):
            raise PipelineError(f"Source {source_id}: class_names must be a list of strings.")
        mapping_value = entry.get("class_mapping", {})
        if not isinstance(mapping_value, dict):
            raise PipelineError(f"Source {source_id}: class_mapping must be an object keyed by source class ID.")
        class_mapping: list[tuple[int, str | None]] = []
        for source_class_id, target_name in mapping_value.items():
            try:
                numeric_id = int(source_class_id)
            except (TypeError, ValueError) as exc:
                raise PipelineError(f"Source {source_id}: invalid source class ID {source_class_id!r}.") from exc
            if target_name is not None and target_name not in taxonomy:
                raise PipelineError(f"Source {source_id}: target class {target_name!r} is not in taxonomy.")
            class_mapping.append((numeric_id, target_name))
        video_value = entry.get("video_extraction", {})
        if not isinstance(video_value, dict):
            raise PipelineError(f"Source {source_id}: video_extraction must be an object.")
        video_enabled = bool(video_value.get("enabled", False))
        extensions_value = video_value.get("video_extensions", [".avi", ".mp4", ".mov", ".mkv"])
        if not isinstance(extensions_value, list) or not extensions_value or not all(
            isinstance(extension, str) and extension.strip() for extension in extensions_value
        ):
            raise PipelineError(f"Source {source_id}: video_extensions must be a non-empty list of strings.")
        video_extensions = tuple(
            extension.strip().lower() if extension.strip().startswith(".") else f".{extension.strip().lower()}"
            for extension in extensions_value
        )
        video_annotation_format = str(video_value.get("annotation_format", "csv")).lower()
        coordinate_format = str(video_value.get("coordinate_format", "xywh_pixels")).lower()
        if video_annotation_format != "csv":
            raise PipelineError(f"Source {source_id}: video_extraction currently supports annotation_format: csv.")
        if coordinate_format not in {"xywh_pixels", "xyxy_pixels", "yolo_normalized"}:
            raise PipelineError(
                f"Source {source_id}: video coordinate_format must be xywh_pixels, xyxy_pixels, or yolo_normalized."
            )
        frame_column_value = video_value.get("frame_column")
        class_column_value = video_value.get("class_column")
        frame_column = str(frame_column_value).strip() if frame_column_value is not None else None
        class_column = str(class_column_value).strip() if class_column_value is not None else None
        default_class_value = video_value.get("default_class_id", 0)
        default_class_id = int(default_class_value) if default_class_value is not None else None
        if default_class_id is not None and default_class_id < 0:
            raise PipelineError(f"Source {source_id}: default_class_id cannot be negative.")
        if class_column is None and default_class_id is None:
            raise PipelineError(f"Source {source_id}: set class_column or default_class_id for video annotations.")
        frame_index_base = int(video_value.get("frame_index_base", 0))
        annotation_pattern = str(video_value.get("annotation_pattern", "{stem}.csv")).strip()
        if not annotation_pattern or "{stem}" not in annotation_pattern:
            raise PipelineError(f"Source {source_id}: annotation_pattern must contain {{stem}}.")
        video_config = VideoExtractionConfig(
            enabled=video_enabled,
            video_extensions=video_extensions,
            annotation_pattern=annotation_pattern,
            annotation_format=video_annotation_format,
            coordinate_format=coordinate_format,
            frame_column=frame_column or None,
            class_column=class_column or None,
            default_class_id=default_class_id,
            x_column=str(video_value.get("x_column", "x")),
            y_column=str(video_value.get("y_column", "y")),
            width_column=str(video_value.get("width_column", "w")),
            height_column=str(video_value.get("height_column", "h")),
            x_max_column=str(video_value.get("x_max_column", "xmax")),
            y_max_column=str(video_value.get("y_max_column", "ymax")),
            frame_index_base=frame_index_base,
        )
        if registry_entry is not None:
            provider = str(registry_entry.get("source", "")).strip().lower()
            if not provider:
                raise PipelineError(f"download_sheet dataset {source_id}: source/provider is required.")
            folder = _registry_folder(raw_root, source_id, provider, registry_entry.get("folder", source_id))
            ethics = registry_entry.get("ethics", {})
            if not isinstance(ethics, dict):
                raise PipelineError(f"download_sheet dataset {source_id}: ethics must be an object.")
            url = str(registry_entry.get("url", ""))
            version = registry_entry.get("version")
            licence = str(ethics.get("license", ethics.get("licence", "unknown")))
            licence_url = str(ethics.get("license_url", ethics.get("licence_url", "")))
            governance_status = str(registry_entry.get("status", "review_required")).lower()
        else:
            provider = str(entry.get("provider", "local"))
            folder_value = entry.get("folder", source_id)
            folder = Path(str(folder_value))
            folder = folder.resolve() if folder.is_absolute() else (raw_root / folder).resolve()
            url = str(entry.get("url", ""))
            version = entry.get("version")
            licence = str(entry.get("licence", "unknown"))
            licence_url = str(entry.get("licence_url", ""))
            governance_status = str(entry.get("governance_status", "review_required")).lower()
        if governance_status not in {"approved", "review_required", "rejected"}:
            raise PipelineError(f"Source {source_id}: invalid governance status {governance_status!r}.")
        annotation_format = str(entry.get("annotation_format", "auto")).lower()
        if video_enabled and annotation_format not in {"auto", "yolo"}:
            raise PipelineError(
                f"Source {source_id}: extracted video labels are YOLO; annotation_format must be auto or yolo."
            )
        if video_enabled and entry.get("metadata_file"):
            raise PipelineError(
                f"Source {source_id}: video extraction creates its own frame metadata; metadata_file is not supported."
            )
        sources.append(
            SourceConfig(
                source_id=source_id,
                folder=folder,
                provider=provider,
                url=url,
                version=version,
                licence=licence,
                licence_url=licence_url,
                governance_status=governance_status,
                annotation_format=annotation_format,
                annotation_file=(folder / str(entry["annotation_file"])).resolve() if entry.get("annotation_file") else None,
                metadata_file=(folder / str(entry["metadata_file"])).resolve() if entry.get("metadata_file") else None,
                class_names=tuple(class_names),
                class_mapping=tuple(sorted(class_mapping)),
                environment_tags=tuple(tags) or ("unknown",),
                grouping=str(entry.get("grouping", "folder")).lower(),
                group_pattern=str(entry["group_pattern"]) if entry.get("group_pattern") else None,
                video_extraction=video_config,
            )
        )

    splits = raw.get("splits", {})
    if not isinstance(splits, dict):
        raise PipelineError("splits must be an object.")
    train = float(splits.get("train", 0.70))
    val = float(splits.get("val", 0.20))
    test = float(splits.get("test", 0.10))
    if min(train, val, test) < 0 or abs(train + val + test - 1.0) > 1e-9:
        raise PipelineError("train, val, and test ratios must be non-negative and total 1.0.")

    mode = str(raw.get("mode", "full")).lower()
    max_assets_value = raw.get("max_assets_per_source")
    max_assets = int(max_assets_value) if max_assets_value is not None else None
    if mode not in {"full", "sample"}:
        raise PipelineError("mode must be 'full' or 'sample'.")
    if mode == "sample" and (max_assets is None or max_assets <= 0):
        raise PipelineError("sample mode requires a positive max_assets_per_source.")
    if mode == "full" and max_assets is not None:
        raise PipelineError("max_assets_per_source is only allowed in sample mode.")

    near_distance = int(raw.get("near_duplicate_distance", 6))
    near_review_distance = int(raw.get("near_duplicate_review_distance", 10))
    if not 0 <= near_distance <= near_review_distance <= 64:
        raise PipelineError("Near-duplicate distances must satisfy 0 <= automatic <= review <= 64.")
    imbalance_ratio = float(raw.get("imbalance_ratio", 4.0))
    drift_threshold = float(raw.get("distribution_drift_threshold", 0.25))
    qa_sample = int(raw.get("qa_sample_per_source", 50))
    image_format = str(raw.get("image_format", "JPEG")).upper()
    jpeg_quality = int(raw.get("jpeg_quality", 95))
    if imbalance_ratio <= 1:
        raise PipelineError("imbalance_ratio must be greater than 1.")
    if not 0 <= drift_threshold <= 1:
        raise PipelineError("distribution_drift_threshold must be between 0 and 1.")
    if qa_sample < 0:
        raise PipelineError("qa_sample_per_source must be non-negative.")
    if image_format not in {"JPEG", "PNG"}:
        raise PipelineError("image_format must be JPEG or PNG.")
    if not 1 <= jpeg_quality <= 100:
        raise PipelineError("jpeg_quality must be between 1 and 100.")
    empty_policy = str(raw.get("empty_after_mapping_policy", "retain_negative")).lower()
    if empty_policy not in {"retain_negative", "quarantine"}:
        raise PipelineError("empty_after_mapping_policy must be retain_negative or quarantine.")

    dataset_yaml = raw.get("dataset_yaml", {})
    if not isinstance(dataset_yaml, dict):
        raise PipelineError("dataset_yaml must be an object.")
    dataset_yaml_mode = str(dataset_yaml.get("mode", "generate")).lower()
    if dataset_yaml_mode not in {"generate", "supplied", "none"}:
        raise PipelineError("dataset_yaml.mode must be generate, supplied, or none.")
    dataset_yaml_path_value = dataset_yaml.get("path")
    dataset_yaml_path = (
        _path(base, dataset_yaml_path_value, "dataset_yaml.path")
        if dataset_yaml_path_value is not None
        else None
    )
    if dataset_yaml_mode == "supplied" and dataset_yaml_path is None:
        raise PipelineError("dataset_yaml.path is required when dataset_yaml.mode is supplied.")
    if dataset_yaml_mode != "supplied" and dataset_yaml_path is not None:
        raise PipelineError("dataset_yaml.path is only allowed when dataset_yaml.mode is supplied.")

    return PipelineConfig(
        project_root=_path(base, raw.get("project_root", ".."), "project_root"),
        raw_root=raw_root,
        workspace_root=_path(base, raw.get("workspace_root", "../datasets/pipeline_workspace"), "workspace_root"),
        invalid_root=_path(base, raw.get("invalid_root", "../datasets/invalid"), "invalid_root"),
        output_root=_path(base, raw.get("output_root", "../datasets"), "output_root"),
        release_id=release_id,
        taxonomy=taxonomy,
        taxonomy_version=str(raw.get("taxonomy_version", "1.0.0")),
        sources=tuple(sources),
        train_ratio=train,
        val_ratio=val,
        test_ratio=test,
        seed=int(raw.get("seed", 42)),
        near_duplicate_distance=near_distance,
        near_duplicate_review_distance=near_review_distance,
        near_duplicates_enabled=bool(raw.get("near_duplicates_enabled", True)),
        imbalance_ratio=imbalance_ratio,
        distribution_drift_threshold=drift_threshold,
        qa_sample_per_source=qa_sample,
        image_format=image_format,
        jpeg_quality=jpeg_quality,
        cvat_enabled=bool(raw.get("cvat", {}).get("enabled", False)) if isinstance(raw.get("cvat", {}), dict) else False,
        cvat_project_name=str(raw.get("cvat", {}).get("project_name", "WalkBuddy semantic QA")) if isinstance(raw.get("cvat", {}), dict) else "WalkBuddy semantic QA",
        mode=mode,
        max_assets_per_source=max_assets,
        empty_after_mapping_policy=empty_policy,
        dataset_yaml_mode=dataset_yaml_mode,
        dataset_yaml_path=dataset_yaml_path,
        download_sheet_path=download_sheet_path,
    )
