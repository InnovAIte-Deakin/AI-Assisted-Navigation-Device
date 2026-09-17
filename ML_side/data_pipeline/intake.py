from __future__ import annotations

import hashlib
import csv
import json
import uuid
from pathlib import Path

from .database import PipelineDatabase, utc_now
from .models import PipelineConfig, SourceConfig, StageResult, StageStatus
from .utils import (
    IMAGE_EXTENSIONS, directory_fingerprint, git_is_dirty, git_sha, runtime_versions,
    safe_relative, sha256_file,
)


ASSET_NAMESPACE = uuid.UUID("fcae13f2-1ee8-5a56-9758-42852a51b6b4")


def _paired_label(image: Path, source_root: Path) -> Path | None:
    candidates = [image.with_suffix(".txt"), image.with_suffix(".xml")]
    parts = list(image.relative_to(source_root).parts)
    for index, part in enumerate(parts):
        if part.lower() == "images":
            replaced = parts.copy()
            replaced[index] = "labels"
            base = source_root.joinpath(*replaced)
            candidates.extend([base.with_suffix(".txt"), base.with_suffix(".xml")])
    for candidate in candidates:
        if candidate.is_file():
            return candidate.resolve()
    return None


def _asset_id(source_id: str, relative_path: str, digest: str) -> str:
    return str(uuid.uuid5(ASSET_NAMESPACE, f"{source_id}\0{relative_path}\0{digest}"))


def _source_metadata(source: SourceConfig, metadata_file: Path | None = None) -> dict[str, dict[str, str]]:
    path = metadata_file if metadata_file is not None else source.metadata_file
    if path is None:
        return {}
    if not path.is_file():
        raise ValueError(f"metadata_file does not exist: {path}")
    result: dict[str, dict[str, str]] = {}
    with path.open("r", encoding="utf-8-sig", newline="") as handle:
        reader = csv.DictReader(handle)
        if "relative_path" not in (reader.fieldnames or []):
            raise ValueError("metadata_file must contain a relative_path column")
        for row in reader:
            relative = str(row.get("relative_path", "")).replace("\\", "/").strip()
            if not relative or relative.startswith("/") or ".." in Path(relative).parts:
                raise ValueError(f"unsafe metadata relative_path: {relative!r}")
            if relative in result:
                raise ValueError(f"duplicate metadata relative_path: {relative}")
            result[relative] = {key: str(value or "").strip() for key, value in row.items() if key}
    return result


def initialise_run(db: PipelineDatabase, run_id: str, config: PipelineConfig, config_path: Path) -> None:
    config_digest = sha256_file(config_path)
    db.connection.execute(
        """INSERT OR IGNORE INTO runs
           (run_id, release_id, status, started_at, seed, git_sha, git_dirty, code_sha256,
            config_path, config_sha256, download_sheet_path, download_sheet_sha256, runtime_json)
           VALUES (?, ?, 'running', ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
        (
            run_id,
            config.release_id,
            utc_now(),
            config.seed,
            git_sha(config.project_root),
            git_is_dirty(config.project_root),
            directory_fingerprint(Path(__file__).resolve().parent),
            str(config_path.resolve()),
            config_digest,
            str(config.download_sheet_path) if config.download_sheet_path else None,
            sha256_file(config.download_sheet_path) if config.download_sheet_path else None,
            json.dumps(runtime_versions(["PIL", "yaml", "cv2", "cvat_sdk"]), sort_keys=True),
        ),
    )
    db.connection.commit()


def register_source(db: PipelineDatabase, run_id: str, source: SourceConfig) -> None:
    db.connection.execute(
        """INSERT OR REPLACE INTO sources
           (run_id, source_id, provider, source_version, source_url, licence, licence_url, governance_status,
            raw_folder, annotation_format,
            environment_tags_json, status)
           VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 'registered')""",
        (
            run_id,
            source.source_id,
            source.provider,
            None if source.version is None else str(source.version),
            source.url,
            source.licence,
            source.licence_url,
            source.governance_status,
            str(source.folder),
            source.annotation_format,
            json.dumps(source.environment_tags),
        ),
    )
    db.connection.commit()


def ingest_source(
    db: PipelineDatabase,
    run_id: str,
    source: SourceConfig,
    max_assets: int | None = None,
    seed: int = 42,
    input_root: Path | None = None,
    metadata_file: Path | None = None,
) -> StageResult:
    register_source(db, run_id, source)
    source_root = input_root.resolve() if input_root is not None else source.folder
    if not source_root.is_dir():
        result = StageResult("intake", StageStatus.FAIL, f"Source folder does not exist: {source_root}", source.source_id)
        db.connection.execute(
            "UPDATE sources SET status='failed' WHERE run_id=? AND source_id=?", (run_id, source.source_id)
        )
        db.connection.commit()
        db.record_stage(run_id, result)
        return result
    try:
        metadata = _source_metadata(source, metadata_file)
    except (OSError, ValueError) as exc:
        result = StageResult("intake", StageStatus.FAIL, f"Source metadata is invalid: {exc}", source.source_id)
        db.record_stage(run_id, result)
        return result

    images = sorted(
        (path for path in source_root.rglob("*") if path.is_file() and path.suffix.lower() in IMAGE_EXTENSIONS),
        key=lambda path: path.as_posix().lower(),
    )
    discovered = len(images)
    if max_assets is not None and len(images) > max_assets:
        images = sorted(
            images,
            key=lambda path: hashlib.sha256(
                f"{seed}:{source.source_id}:{safe_relative(path, source_root).as_posix()}".encode("utf-8")
            ).hexdigest(),
        )[:max_assets]
        images.sort(key=lambda path: path.as_posix().lower())
    registered = 0
    for image in images:
        relative = safe_relative(image, source_root).as_posix()
        digest = sha256_file(image)
        asset_id = _asset_id(source.source_id, relative, digest)
        label = _paired_label(image, source_root)
        metadata_row = metadata.get(relative, metadata.get(image.name, {}))
        tag_text = metadata_row.get("environment_tags", "")
        environment_tags = tuple(tag.strip() for tag in tag_text.split("|") if tag.strip()) or source.environment_tags
        provided_group = metadata_row.get("group_id") or metadata_row.get("session_id") or metadata_row.get("video_id")
        group_id = (
            str(provided_group)
            if provided_group and metadata_row.get("source_video")
            else f"{source.source_id}:metadata:{provided_group}" if provided_group else None
        )
        db.connection.execute(
            """INSERT OR IGNORE INTO assets
               (run_id, asset_id, source_id, original_filename, original_relative_path,
                raw_image_path, raw_label_path, original_sha256, status,
                environment_tags_json, group_id, created_at)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, 'registered', ?, ?, ?)""",
            (
                run_id,
                asset_id,
                source.source_id,
                image.name,
                relative,
                str(image.resolve()),
                str(label) if label else None,
                digest,
                json.dumps(environment_tags),
                group_id,
                utc_now(),
            ),
        )
        if metadata_row.get("source_video"):
            existing_transform = db.connection.execute(
                """SELECT 1 FROM transformations
                   WHERE run_id=? AND asset_id=? AND stage='video_extraction' LIMIT 1""",
                (run_id, asset_id),
            ).fetchone()
            if existing_transform is None:
                db.add_transform(
                    run_id,
                    asset_id,
                    "video_extraction",
                    "extract_annotated_frame",
                    {
                        "source_video": metadata_row["source_video"],
                        "frame_index": int(metadata_row.get("frame_index", "0")),
                        "group_id": provided_group,
                    },
                    metadata_row.get("video_sha256") or None,
                    digest,
                )
        registered += 1
    source_status = "registered" if images else "failed"
    db.connection.execute(
        "UPDATE sources SET status=? WHERE run_id=? AND source_id=?", (source_status, run_id, source.source_id)
    )
    db.connection.commit()
    status = StageStatus.PASS if images else StageStatus.FAIL
    result = StageResult(
        "intake",
        status,
        f"Registered {registered} image assets." if images else "No supported images were found.",
        source.source_id,
        {"registered_images": registered, "discovered_images": discovered, "sampled": max_assets is not None},
    )
    db.record_stage(run_id, result)
    return result


def run_id_for(config: PipelineConfig, config_path: Path) -> str:
    code_digest = directory_fingerprint(Path(__file__).resolve().parent)
    download_sheet_digest = sha256_file(config.download_sheet_path) if config.download_sheet_path else ""
    identity = hashlib.sha256(
        f"{config.release_id}\0{config.seed}\0{sha256_file(config_path)}\0{download_sheet_digest}\0{code_digest}".encode("utf-8")
    ).hexdigest()[:12]
    return f"{config.release_id}-{identity}"
