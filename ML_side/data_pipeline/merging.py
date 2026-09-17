from __future__ import annotations

from collections import Counter

from .database import PipelineDatabase
from .models import StageResult, StageStatus


def merge_source_catalogue(db: PipelineDatabase, run_id: str) -> StageResult:
    """Create the logical merged dataset without copying or flattening source files.

    Persistent UUIDs remove the filename-collision problem that forced the old
    notebook to rename and physically merge every source into one directory.
    """
    rows = db.rows(
        """SELECT asset_id, source_id, standard_image_path, standard_label_path
           FROM assets WHERE run_id=? AND status='annotated' ORDER BY source_id, asset_id""",
        (run_id,),
    )
    source_counts = Counter(str(row["source_id"]) for row in rows)
    missing_materialized = [
        str(row["asset_id"]) for row in rows if not row["standard_image_path"] or not row["standard_label_path"]
    ]
    if missing_materialized:
        status = StageStatus.FAIL
        message = f"Logical merge rejected {len(missing_materialized)} incomplete assets."
    elif not rows:
        status = StageStatus.FAIL
        message = "No annotated source assets are available to merge."
    else:
        status = StageStatus.PASS
        message = f"Merged {len(rows)} assets from {len(source_counts)} sources into the UUID catalogue."
    result = StageResult(
        "merging", status, message,
        metrics={"assets": len(rows), "per_source": dict(sorted(source_counts.items())), "incomplete": missing_materialized},
    )
    db.record_stage(run_id, result)
    return result

