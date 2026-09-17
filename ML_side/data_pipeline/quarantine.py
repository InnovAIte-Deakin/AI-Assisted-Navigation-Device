from __future__ import annotations

from pathlib import Path

from .database import PipelineDatabase
from .utils import copy_or_link, json_dump


def quarantine_asset(
    db: PipelineDatabase,
    run_id: str,
    asset_id: str,
    invalid_root: Path,
    reason: str,
    *,
    copy_files: bool = True,
) -> None:
    rows = db.rows(
        "SELECT source_id, original_filename, raw_image_path, raw_label_path FROM assets WHERE run_id=? AND asset_id=?",
        (run_id, asset_id),
    )
    if not rows:
        raise KeyError(f"Unknown asset: {asset_id}")
    row = rows[0]
    db.connection.execute(
        "UPDATE assets SET status='quarantined', quarantine_reason=? WHERE run_id=? AND asset_id=?",
        (reason, run_id, asset_id),
    )
    db.connection.commit()
    if not copy_files:
        return
    destination = invalid_root / run_id / reason / str(row["source_id"]) / asset_id
    image_path = Path(str(row["raw_image_path"]))
    copy_or_link(image_path, destination / image_path.name)
    label_value = row["raw_label_path"]
    if label_value:
        label_path = Path(str(label_value))
        if label_path.exists():
            copy_or_link(label_path, destination / label_path.name)
    json_dump(
        destination / "quarantine.json",
        {
            "asset_id": asset_id,
            "source_id": row["source_id"],
            "original_filename": row["original_filename"],
            "reason": reason,
            "raw_files_preserved": True,
        },
    )

