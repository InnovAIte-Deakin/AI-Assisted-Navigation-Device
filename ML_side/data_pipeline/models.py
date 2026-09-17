from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from pathlib import Path
from typing import Any


class StageStatus(str, Enum):
    PASS = "pass"
    WARNING = "warning"
    REVIEW_REQUIRED = "review_required"
    FAIL = "fail"
    SKIPPED = "skipped"


@dataclass(frozen=True)
class StageResult:
    stage: str
    status: StageStatus
    message: str
    source_id: str | None = None
    metrics: dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class VideoExtractionConfig:
    enabled: bool = False
    video_extensions: tuple[str, ...] = (".avi", ".mp4", ".mov", ".mkv")
    annotation_pattern: str = "{stem}.csv"
    annotation_format: str = "csv"
    coordinate_format: str = "xywh_pixels"
    frame_column: str | None = None
    class_column: str | None = None
    default_class_id: int | None = 0
    x_column: str = "x"
    y_column: str = "y"
    width_column: str = "w"
    height_column: str = "h"
    x_max_column: str = "xmax"
    y_max_column: str = "ymax"
    frame_index_base: int = 0


@dataclass(frozen=True)
class SourceConfig:
    source_id: str
    folder: Path
    provider: str = "local"
    url: str = ""
    version: str | int | None = None
    licence: str = "unknown"
    licence_url: str = ""
    governance_status: str = "review_required"
    annotation_format: str = "auto"
    annotation_file: Path | None = None
    metadata_file: Path | None = None
    class_names: tuple[str, ...] = ()
    class_mapping: tuple[tuple[int, str | None], ...] = ()
    environment_tags: tuple[str, ...] = ("unknown",)
    grouping: str = "folder"
    group_pattern: str | None = None
    video_extraction: VideoExtractionConfig = field(default_factory=VideoExtractionConfig)

    def target_for(self, source_class_id: int) -> str | None | object:
        for class_id, target in self.class_mapping:
            if class_id == source_class_id:
                return target
        return _UNMAPPED


_UNMAPPED = object()


@dataclass(frozen=True)
class PipelineConfig:
    project_root: Path
    raw_root: Path
    workspace_root: Path
    invalid_root: Path
    output_root: Path
    release_id: str
    taxonomy: tuple[str, ...]
    taxonomy_version: str
    sources: tuple[SourceConfig, ...]
    train_ratio: float = 0.70
    val_ratio: float = 0.20
    test_ratio: float = 0.10
    seed: int = 42
    near_duplicate_distance: int = 6
    near_duplicate_review_distance: int = 10
    near_duplicates_enabled: bool = True
    imbalance_ratio: float = 4.0
    distribution_drift_threshold: float = 0.25
    qa_sample_per_source: int = 50
    image_format: str = "JPEG"
    jpeg_quality: int = 95
    cvat_enabled: bool = False
    cvat_project_name: str = "WalkBuddy semantic QA"
    mode: str = "full"
    max_assets_per_source: int | None = None
    empty_after_mapping_policy: str = "retain_negative"
    dataset_yaml_mode: str = "generate"
    dataset_yaml_path: Path | None = None
    download_sheet_path: Path | None = None

    @property
    def release_dir(self) -> Path:
        return self.output_root / f"dataset_{self.release_id}"


class PipelineError(RuntimeError):
    """An expected, user-actionable pipeline failure."""
