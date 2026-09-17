from __future__ import annotations

import csv
import math
from collections import defaultdict
from dataclasses import dataclass
from pathlib import Path
from typing import Iterator

from .database import PipelineDatabase
from .models import PipelineConfig, SourceConfig, StageResult, StageStatus, VideoExtractionConfig
from .utils import json_dump, safe_relative, sha256_file


@dataclass(frozen=True)
class VideoAnnotation:
    frame_index: int
    class_id: int
    first: float
    second: float
    third: float
    fourth: float


def extracted_source_root(config: PipelineConfig, run_id: str, source: SourceConfig) -> Path:
    return config.workspace_root / run_id / "extracted" / source.source_id


def extracted_metadata_path(config: PipelineConfig, run_id: str, source: SourceConfig) -> Path:
    return extracted_source_root(config, run_id, source) / "metadata.csv"


def _annotation_path(source: SourceConfig, video_path: Path) -> Path:
    relative = safe_relative(video_path, source.folder)
    rendered = source.video_extraction.annotation_pattern.format(
        stem=video_path.stem,
        name=video_path.name,
        suffix=video_path.suffix,
        parent=relative.parent.as_posix(),
    )
    candidate = (source.folder / rendered).resolve()
    safe_relative(candidate, source.folder)
    return candidate


def _load_csv_annotations(path: Path, config: VideoExtractionConfig) -> dict[int, list[VideoAnnotation]]:
    if not path.is_file():
        raise ValueError(f"video annotation CSV does not exist: {path}")
    annotations: dict[int, list[VideoAnnotation]] = defaultdict(list)
    with path.open("r", encoding="utf-8-sig", newline="") as handle:
        reader = csv.DictReader(handle)
        fieldnames = set(reader.fieldnames or [])
        required = {config.x_column, config.y_column}
        if config.coordinate_format == "xyxy_pixels":
            required.update({config.x_max_column, config.y_max_column})
        else:
            required.update({config.width_column, config.height_column})
        if config.frame_column:
            required.add(config.frame_column)
        if config.class_column:
            required.add(config.class_column)
        missing = sorted(required - fieldnames)
        if missing:
            raise ValueError(f"{path.name} is missing required columns: {', '.join(missing)}")
        for row_offset, row in enumerate(reader):
            line_number = row_offset + 2
            try:
                frame_index = (
                    int(float(row[config.frame_column])) - config.frame_index_base
                    if config.frame_column
                    else row_offset
                )
                class_id = (
                    int(float(row[config.class_column]))
                    if config.class_column
                    else int(config.default_class_id)  # validated by config.py
                )
                if config.coordinate_format == "xyxy_pixels":
                    values = (
                        float(row[config.x_column]),
                        float(row[config.y_column]),
                        float(row[config.x_max_column]),
                        float(row[config.y_max_column]),
                    )
                else:
                    values = (
                        float(row[config.x_column]),
                        float(row[config.y_column]),
                        float(row[config.width_column]),
                        float(row[config.height_column]),
                    )
            except (KeyError, TypeError, ValueError) as exc:
                raise ValueError(f"{path.name}:{line_number}: malformed video annotation") from exc
            if frame_index < 0 or class_id < 0:
                raise ValueError(f"{path.name}:{line_number}: frame and class IDs must be non-negative")
            annotations[frame_index].append(VideoAnnotation(frame_index, class_id, *values))
    if not annotations:
        raise ValueError(f"video annotation CSV is empty: {path}")
    return dict(annotations)


def _normalise_annotation(
    annotation: VideoAnnotation,
    image_width: int,
    image_height: int,
    coordinate_format: str,
) -> tuple[int, float, float, float, float]:
    if image_width <= 0 or image_height <= 0:
        raise ValueError("video frame has invalid dimensions")
    if not all(math.isfinite(value) for value in (annotation.first, annotation.second, annotation.third, annotation.fourth)):
        raise ValueError("video annotation contains a non-finite coordinate")
    if coordinate_format == "xywh_pixels":
        x_min, y_min = annotation.first, annotation.second
        box_width, box_height = annotation.third, annotation.fourth
        x_max, y_max = x_min + box_width, y_min + box_height
    elif coordinate_format == "xyxy_pixels":
        x_min, y_min, x_max, y_max = (
            annotation.first,
            annotation.second,
            annotation.third,
            annotation.fourth,
        )
        box_width, box_height = x_max - x_min, y_max - y_min
    else:
        center_x, center_y, box_width, box_height = (
            annotation.first,
            annotation.second,
            annotation.third,
            annotation.fourth,
        )
        if not all(0 <= value <= 1 for value in (center_x, center_y, box_width, box_height)):
            raise ValueError("normalized video annotation lies outside 0..1")
        x_min, y_min = center_x - box_width / 2, center_y - box_height / 2
        x_max, y_max = center_x + box_width / 2, center_y + box_height / 2
        if box_width <= 0 or box_height <= 0 or x_min < 0 or y_min < 0 or x_max > 1 or y_max > 1:
            raise ValueError("normalized video annotation box is invalid or outside the frame")
        return annotation.class_id, center_x, center_y, box_width, box_height
    tolerance = 1.0
    if (
        box_width <= 0
        or box_height <= 0
        or x_min < -tolerance
        or y_min < -tolerance
        or x_max > image_width + tolerance
        or y_max > image_height + tolerance
    ):
        raise ValueError("pixel video annotation is invalid or outside the frame")
    x_min, y_min = max(0.0, x_min), max(0.0, y_min)
    x_max, y_max = min(float(image_width), x_max), min(float(image_height), y_max)
    return (
        annotation.class_id,
        ((x_min + x_max) / 2) / image_width,
        ((y_min + y_max) / 2) / image_height,
        (x_max - x_min) / image_width,
        (y_max - y_min) / image_height,
    )


def _iter_video_frames(path: Path) -> Iterator[tuple[int, object]]:
    try:
        import cv2  # type: ignore
        from PIL import Image
    except ImportError as exc:
        raise RuntimeError("opencv-python and Pillow are required for video extraction") from exc
    capture = cv2.VideoCapture(str(path))
    if not capture.isOpened():
        capture.release()
        raise RuntimeError(f"OpenCV could not open video: {path}")
    frame_index = 0
    try:
        while True:
            readable, frame = capture.read()
            if not readable:
                break
            rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
            yield frame_index, Image.fromarray(rgb)
            frame_index += 1
    finally:
        capture.release()


def extract_video_source(
    db: PipelineDatabase,
    run_id: str,
    config: PipelineConfig,
    source: SourceConfig,
) -> StageResult:
    video_config = source.video_extraction
    if not video_config.enabled:
        result = StageResult(
            "video_extraction", StageStatus.SKIPPED, "Video extraction is disabled.", source.source_id
        )
        db.record_stage(run_id, result)
        return result
    videos = sorted(
        (
            path
            for path in source.folder.rglob("*")
            if path.is_file() and path.suffix.lower() in video_config.video_extensions
        ),
        key=lambda path: path.as_posix().lower(),
    )
    if not videos:
        result = StageResult(
            "video_extraction", StageStatus.FAIL,
            f"No configured video files were found in {source.folder}.", source.source_id,
        )
        db.record_stage(run_id, result)
        return result

    destination = extracted_source_root(config, run_id, source)
    temporary = destination.parent / f".{source.source_id}.extracting"
    if destination.exists() or temporary.exists():
        result = StageResult(
            "video_extraction", StageStatus.FAIL,
            f"Video extraction output already exists without a completed checkpoint: {destination if destination.exists() else temporary}",
            source.source_id,
        )
        db.record_stage(run_id, result)
        return result
    temporary.mkdir(parents=True)
    metadata_rows: list[dict[str, object]] = []
    video_records: list[dict[str, object]] = []
    total_frames_read = 0
    total_frames_written = 0
    total_annotations = 0
    try:
        for video_path in videos:
            relative_video = safe_relative(video_path, source.folder)
            annotation_path = _annotation_path(source, video_path)
            annotations = _load_csv_annotations(annotation_path, video_config)
            video_digest = sha256_file(video_path)
            seen_annotated_frames: set[int] = set()
            frames_read = 0
            frames_written = 0
            relative_parent = relative_video.with_suffix("")
            video_group = f"{source.source_id}:video:{relative_video.as_posix()}"
            for frame_index, image in _iter_video_frames(video_path):
                frames_read += 1
                total_frames_read += 1
                frame_annotations = annotations.get(frame_index)
                if not frame_annotations:
                    continue
                width, height = image.size  # PIL image supplied by _iter_video_frames
                label_rows = [
                    _normalise_annotation(item, width, height, video_config.coordinate_format)
                    for item in frame_annotations
                ]
                frame_stem = f"{video_path.stem}_{frame_index:06d}"
                image_relative = Path("images") / relative_parent / f"{frame_stem}.jpg"
                label_relative = Path("labels") / relative_parent / f"{frame_stem}.txt"
                image_output = temporary / image_relative
                label_output = temporary / label_relative
                image_output.parent.mkdir(parents=True, exist_ok=True)
                label_output.parent.mkdir(parents=True, exist_ok=True)
                image.convert("RGB").save(image_output, format="JPEG", quality=config.jpeg_quality, optimize=True)
                label_output.write_text(
                    "\n".join(
                        f"{class_id} {center_x:.8f} {center_y:.8f} {box_width:.8f} {box_height:.8f}"
                        for class_id, center_x, center_y, box_width, box_height in label_rows
                    )
                    + "\n",
                    encoding="utf-8",
                )
                metadata_rows.append(
                    {
                        "relative_path": image_relative.as_posix(),
                        "group_id": video_group,
                        "source_video": relative_video.as_posix(),
                        "frame_index": frame_index,
                        "video_sha256": video_digest,
                    }
                )
                seen_annotated_frames.add(frame_index)
                frames_written += 1
                total_frames_written += 1
                total_annotations += len(label_rows)
            missing_frames = sorted(set(annotations) - seen_annotated_frames)
            if missing_frames:
                preview = ", ".join(str(value) for value in missing_frames[:10])
                raise ValueError(
                    f"{annotation_path.name} refers to frames not present in {relative_video}: {preview}"
                )
            video_records.append(
                {
                    "video": relative_video.as_posix(),
                    "video_sha256": video_digest,
                    "annotation_file": safe_relative(annotation_path, source.folder).as_posix(),
                    "frames_read": frames_read,
                    "annotated_frames_written": frames_written,
                    "group_id": video_group,
                }
            )
        metadata_path = temporary / "metadata.csv"
        with metadata_path.open("w", encoding="utf-8", newline="") as handle:
            writer = csv.DictWriter(
                handle,
                fieldnames=["relative_path", "group_id", "source_video", "frame_index", "video_sha256"],
            )
            writer.writeheader()
            writer.writerows(metadata_rows)
        json_dump(
            temporary / "video_extraction.json",
            {
                "run_id": run_id,
                "source_id": source.source_id,
                "coordinate_format": video_config.coordinate_format,
                "videos": video_records,
                "frames_read": total_frames_read,
                "annotated_frames_written": total_frames_written,
                "annotations_written": total_annotations,
            },
        )
        destination.parent.mkdir(parents=True, exist_ok=True)
        temporary.replace(destination)
    except Exception as exc:
        result = StageResult(
            "video_extraction", StageStatus.FAIL,
            f"Video extraction failed; staged evidence was preserved: {exc}", source.source_id,
            {"videos_discovered": len(videos), "staging_directory": str(temporary)},
        )
        db.record_stage(run_id, result)
        return result

    result = StageResult(
        "video_extraction", StageStatus.PASS,
        f"Extracted {total_frames_written} annotated frames from {len(videos)} videos.",
        source.source_id,
        {
            "videos": len(videos),
            "frames_read": total_frames_read,
            "annotated_frames_written": total_frames_written,
            "annotations_written": total_annotations,
            "output": str(destination),
        },
    )
    db.record_stage(run_id, result)
    return result
