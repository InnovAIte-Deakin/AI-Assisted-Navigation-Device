from __future__ import annotations

import re
from pathlib import Path

from .database import PipelineDatabase
from .models import SourceConfig, StageResult, StageStatus


def assign_groups(db: PipelineDatabase, run_id: str, source: SourceConfig) -> StageResult:
    rows = db.rows(
        """SELECT asset_id, original_relative_path, group_id FROM assets
           WHERE run_id=? AND source_id=? AND status='annotated' ORDER BY original_relative_path""",
        (run_id, source.source_id),
    )
    pattern = re.compile(source.group_pattern) if source.group_pattern else None
    group_ids: set[str] = set()
    unknown = 0
    for row in rows:
        relative = Path(str(row["original_relative_path"]))
        if source.video_extraction.enabled and row["group_id"]:
            # Video extraction writes the source-video identity at intake. It
            # always takes precedence so frames from one video cannot leak.
            group = str(row["group_id"])
        elif source.grouping == "dataset":
            group = f"{source.source_id}:dataset"
        elif source.grouping == "folder":
            parent = relative.parent.as_posix() or "root"
            group = f"{source.source_id}:folder:{parent}"
        elif source.grouping == "filename-regex" and pattern:
            match = pattern.search(relative.as_posix())
            if match:
                value = match.groupdict().get("group") or match.group(1) if match.groups() else match.group(0)
                group = f"{source.source_id}:regex:{value}"
            else:
                unknown += 1
                group = f"{source.source_id}:unknown"
        elif source.grouping in {"metadata", "metadata-column"}:
            if row["group_id"]:
                group = str(row["group_id"])
            else:
                unknown += 1
                group = f"{source.source_id}:unknown"
        elif source.grouping == "none":
            unknown += 1
            group = f"{source.source_id}:unknown"
        else:
            result = StageResult(
                "grouping", StageStatus.FAIL, f"Unsupported grouping strategy {source.grouping!r}.", source.source_id
            )
            db.record_stage(run_id, result)
            return result
        group_ids.add(group)
        db.connection.execute(
            "UPDATE assets SET group_id=? WHERE run_id=? AND asset_id=?", (group, run_id, row["asset_id"])
        )
    db.connection.commit()
    status = StageStatus.FAIL if not rows else StageStatus.WARNING if unknown else StageStatus.PASS
    result = StageResult(
        "grouping", status, f"Assigned {len(rows)} assets to {len(group_ids)} non-splittable groups.",
        source.source_id, {"assets": len(rows), "groups": len(group_ids), "unknown_group_assets": unknown},
    )
    db.record_stage(run_id, result)
    return result
