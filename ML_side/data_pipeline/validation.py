from __future__ import annotations

from pathlib import Path

from .database import PipelineDatabase
from .models import PipelineConfig, SourceConfig, StageResult, StageStatus
from .quarantine import quarantine_asset


SUPPORTED_FORMATS = {"auto", "yolo", "coco", "voc", "pascal_voc"}


def validate_source_structure(
    db: PipelineDatabase, run_id: str, config: PipelineConfig, source: SourceConfig
) -> StageResult:
    rows = db.rows(
        "SELECT asset_id, raw_label_path FROM assets WHERE run_id=? AND source_id=? AND status='registered'",
        (run_id, source.source_id),
    )
    if source.annotation_format not in SUPPORTED_FORMATS:
        for row in rows:
            quarantine_asset(db, run_id, str(row["asset_id"]), config.invalid_root, "unsupported_annotation_format")
        db.connection.execute(
            "UPDATE sources SET status='quarantined' WHERE run_id=? AND source_id=?", (run_id, source.source_id)
        )
        db.connection.commit()
        result = StageResult(
            "structure_validation", StageStatus.FAIL,
            f"Unsupported annotation format {source.annotation_format!r}.", source.source_id,
        )
        db.record_stage(run_id, result)
        return result
    if source.annotation_format == "coco" and (source.annotation_file is None or not source.annotation_file.is_file()):
        for row in rows:
            quarantine_asset(db, run_id, str(row["asset_id"]), config.invalid_root, "missing_coco_annotations")
        db.connection.execute(
            "UPDATE sources SET status='quarantined' WHERE run_id=? AND source_id=?", (run_id, source.source_id)
        )
        db.connection.commit()
        result = StageResult(
            "structure_validation", StageStatus.FAIL,
            "COCO source requires an existing annotation_file.", source.source_id,
        )
        db.record_stage(run_id, result)
        return result

    missing = 0
    if source.annotation_format != "coco":
        for row in rows:
            if not row["raw_label_path"]:
                missing += 1
                quarantine_asset(db, run_id, str(row["asset_id"]), config.invalid_root, "missing_annotation")
    remaining = len(rows) - missing
    if remaining == 0:
        status = StageStatus.FAIL
    elif missing:
        status = StageStatus.WARNING
    else:
        status = StageStatus.PASS
    db.connection.execute(
        "UPDATE sources SET status=? WHERE run_id=? AND source_id=?",
        ("quarantined" if status == StageStatus.FAIL else "validated", run_id, source.source_id),
    )
    db.connection.commit()
    result = StageResult(
        "structure_validation",
        status,
        f"Validated {remaining} assets; quarantined {missing} unlabelled assets.",
        source.source_id,
        {"valid_candidates": remaining, "missing_annotations": missing},
    )
    db.record_stage(run_id, result)
    return result
