from __future__ import annotations

import csv
import json
from pathlib import Path

from .database import PipelineDatabase, utc_now
from .models import PipelineConfig, PipelineError, StageResult, StageStatus
from .quarantine import quarantine_asset


ALLOWED_DECISIONS = {"approve", "reject", "keep", "duplicate", "not_duplicate"}


def import_review_csv(
    db: PipelineDatabase, run_id: str, config: PipelineConfig, path: Path, reviewer: str
) -> StageResult:
    applied = 0
    with path.open("r", encoding="utf-8-sig", newline="") as handle:
        reader = csv.DictReader(handle)
        required = {"review_type", "decision", "notes"}
        if not required.issubset(reader.fieldnames or []):
            raise PipelineError(f"Review CSV must include {sorted(required)}.")
        for row in reader:
            decision = row["decision"].strip().lower()
            if decision not in ALLOWED_DECISIONS:
                raise PipelineError(f"Unsupported review decision: {decision!r}")
            asset_id = row.get("asset_id", "").strip() or None
            external_id = row.get("external_task_id", "").strip() or None
            findings = {
                name: row.get(name, "").strip().lower() in {"1", "true", "yes", "y"}
                for name in ("incorrect_class", "missed_objects", "loose_box", "tight_box", "ambiguous_object")
            }
            db.connection.execute(
                """INSERT INTO reviews
                   (run_id, asset_id, review_type, reviewer, decision, notes, findings_json,
                    external_task_id, reviewed_at, created_at)
                   VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                (
                    run_id, asset_id, row["review_type"].strip(), reviewer, decision, row["notes"].strip(),
                    json.dumps(findings, sort_keys=True), external_id, utc_now(), utc_now(),
                ),
            )
            if asset_id and decision in {"reject", "duplicate"}:
                quarantine_asset(db, run_id, asset_id, config.invalid_root, f"review_{row['review_type'].strip()}")
            if row["review_type"].strip() == "near_duplicate" and asset_id and external_id:
                db.connection.execute(
                    """UPDATE duplicate_candidates SET decision=?
                       WHERE run_id=? AND cluster_id=? AND asset_id=?""",
                    (decision, run_id, external_id, asset_id),
                )
            applied += 1
    db.connection.commit()
    result = StageResult("review_import", StageStatus.PASS, f"Imported {applied} auditable review decisions.", metrics={"decisions": applied})
    db.record_stage(run_id, result)
    return result


def unresolved_review_count(db: PipelineDatabase, run_id: str) -> int:
    row = db.connection.execute(
        """SELECT COUNT(*) FROM reviews pending
           WHERE pending.run_id=? AND pending.decision='pending'
             AND NOT EXISTS (
               SELECT 1 FROM reviews resolved
               WHERE resolved.run_id=pending.run_id
                 AND resolved.review_type=pending.review_type
                 AND (
                   (pending.asset_id IS NOT NULL AND resolved.asset_id=pending.asset_id)
                   OR
                   (pending.asset_id IS NULL AND pending.external_task_id IS NOT NULL
                    AND resolved.external_task_id=pending.external_task_id)
                 )
                 AND resolved.decision!='pending'
             )""",
        (run_id,),
    ).fetchone()
    return int(row[0])
