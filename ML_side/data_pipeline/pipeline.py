from __future__ import annotations

import csv
from pathlib import Path

from .annotations import convert_annotations
from .augmentation import augment_training_balance
from .balance import check_balance
from .collection import collect_source
from .config import load_config
from .cvat_review import prepare_cvat_review
from .database import PipelineDatabase
from .deduplication import exact_duplicates, near_duplicates
from .grouping import assign_groups
from .intake import ingest_source, initialise_run, register_source, run_id_for
from .layout import initialise_storage_layout
from .models import PipelineConfig, StageResult, StageStatus
from .merging import merge_source_catalogue
from .quality import inspect_quality
from .representativeness import compare_split_distributions
from .release import build_release
from .reviews import unresolved_review_count
from .splitting import assign_splits
from .standardization import standardize_images
from .validation import validate_source_structure
from .video_extraction import extract_video_source, extracted_metadata_path, extracted_source_root


def database_path(config: PipelineConfig, run_id: str) -> Path:
    return config.workspace_root / run_id / "pipeline.sqlite3"


def _has_stage(db: PipelineDatabase, run_id: str, stage: str, source_id: str | None = None) -> bool:
    if source_id is None:
        row = db.connection.execute(
            "SELECT status FROM stage_results WHERE run_id=? AND stage=? AND source_id IS NULL ORDER BY result_id DESC LIMIT 1",
            (run_id, stage),
        ).fetchone()
    else:
        row = db.connection.execute(
            "SELECT status FROM stage_results WHERE run_id=? AND stage=? AND source_id=? ORDER BY result_id DESC LIMIT 1",
            (run_id, stage, source_id),
        ).fetchone()
    return row is not None and row["status"] != "fail"


def _has_any_stage(db: PipelineDatabase, run_id: str, stage: str) -> bool:
    return db.connection.execute(
        "SELECT 1 FROM stage_results WHERE run_id=? AND stage=? LIMIT 1", (run_id, stage)
    ).fetchone() is not None


def _write_review_queue(db: PipelineDatabase, config: PipelineConfig, run_id: str) -> None:
    path = config.workspace_root / run_id / "review" / "review_decisions.csv"
    if path.exists() and len(path.read_text(encoding="utf-8-sig").splitlines()) > 1:
        return
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.writer(handle)
        writer.writerow([
            "review_type", "asset_id", "external_task_id", "decision", "incorrect_class",
            "missed_objects", "loose_box", "tight_box", "ambiguous_object", "notes",
        ])
        pending = db.rows(
            """SELECT asset_id, external_task_id, review_type, notes FROM reviews
               WHERE run_id=? AND decision='pending' ORDER BY review_type, external_task_id, asset_id""",
            (run_id,),
        )
        for row in pending:
            writer.writerow([
                row["review_type"], row["asset_id"] or "", row["external_task_id"] or "", "",
                "", "", "", "", "", row["notes"],
            ])


def execute(config_path: Path) -> StageResult:
    config = load_config(config_path)
    run_id = run_id_for(config, config_path)
    layout_result = initialise_storage_layout(config, run_id)
    with PipelineDatabase(database_path(config, run_id)) as db:
        initialise_run(db, run_id, config, config_path)
        if not _has_stage(db, run_id, "layout_initialization"):
            db.record_stage(run_id, layout_result)

        for source in config.sources:
            register_source(db, run_id, source)
            if not _has_stage(db, run_id, "collection", source.source_id):
                collect_source(db, run_id, source)
            input_root = None
            metadata_file = None
            if source.video_extraction.enabled:
                if not _has_stage(db, run_id, "video_extraction", source.source_id):
                    extraction_result = extract_video_source(db, run_id, config, source)
                    if extraction_result.status == StageStatus.FAIL:
                        continue
                input_root = extracted_source_root(config, run_id, source)
                metadata_file = extracted_metadata_path(config, run_id, source)
            if not _has_stage(db, run_id, "intake", source.source_id):
                ingest_source(
                    db, run_id, source, config.max_assets_per_source, config.seed,
                    input_root=input_root, metadata_file=metadata_file,
                )

        if not _has_stage(db, run_id, "exact_deduplication"):
            exact_duplicates(db, run_id, config.invalid_root)

        for source in config.sources:
            if not _has_stage(db, run_id, "structure_validation", source.source_id):
                validate_source_structure(db, run_id, config, source)

        if not _has_stage(db, run_id, "standardization"):
            standardize_images(db, run_id, config)

        for source in config.sources:
            if not _has_stage(db, run_id, "annotation_conversion", source.source_id):
                convert_annotations(db, run_id, config, source)

        if not _has_stage(db, run_id, "merging"):
            merge_source_catalogue(db, run_id)

        if not _has_stage(db, run_id, "quality_inspection"):
            inspect_quality(db, run_id, config)
        if not _has_stage(db, run_id, "near_deduplication"):
            if config.near_duplicates_enabled:
                near_duplicates(
                    db, run_id, config.workspace_root / run_id / "review" / "near_duplicates",
                    config.near_duplicate_distance, config.near_duplicate_review_distance,
                )
            else:
                db.record_stage(
                    run_id,
                    StageResult("near_deduplication", StageStatus.SKIPPED, "Near-duplicate detection disabled by config."),
                )
        for source in config.sources:
            if not _has_stage(db, run_id, "grouping", source.source_id):
                assign_groups(db, run_id, source)
        if not _has_stage(db, run_id, "semantic_review"):
            prepare_cvat_review(db, run_id, config)

        _write_review_queue(db, config, run_id)
        pending = unresolved_review_count(db, run_id)
        if pending:
            result = StageResult(
                "pipeline", StageStatus.REVIEW_REQUIRED,
                f"Processing is checkpointed; {pending} human review decisions remain pending.",
                metrics={"run_id": run_id, "database": str(database_path(config, run_id)), "pending_reviews": pending},
            )
            db.record_stage(run_id, result)
            return result

        if not _has_stage(db, run_id, "splitting"):
            assign_splits(db, run_id, config)
        if not _has_stage(db, run_id, "split_representativeness"):
            compare_split_distributions(db, run_id, config)
        latest_balance = db.connection.execute(
            "SELECT status FROM stage_results WHERE run_id=? AND stage='class_balance' ORDER BY result_id DESC LIMIT 1",
            (run_id,),
        ).fetchone()
        if latest_balance is None:
            latest_balance_result = check_balance(db, run_id, config)
        else:
            latest_balance_result = StageResult("class_balance", StageStatus(str(latest_balance["status"])), "Existing balance result.")
        if latest_balance_result.status == StageStatus.FAIL and not _has_any_stage(db, run_id, "augmentation"):
            augmentation_result = augment_training_balance(db, run_id, config)
            if augmentation_result.status in {StageStatus.PASS, StageStatus.SKIPPED}:
                check_balance(db, run_id, config)
        release_result = build_release(db, run_id, config)
        db.connection.execute(
            "UPDATE runs SET status=?, finished_at=datetime('now') WHERE run_id=?",
            (release_result.status.value, run_id),
        )
        db.connection.commit()
        return release_result
