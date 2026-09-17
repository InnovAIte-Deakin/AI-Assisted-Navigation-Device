from __future__ import annotations

import html
import json
from collections import Counter
from pathlib import Path

from .database import PipelineDatabase
from .models import PipelineConfig
from .utils import json_dump


def build_report(db: PipelineDatabase, run_id: str, config: PipelineConfig) -> dict[str, object]:
    assets = db.rows("SELECT * FROM assets WHERE run_id=?", (run_id,))
    annotations = db.rows(
        """SELECT n.target_class_id, a.split, a.source_id
           FROM annotations n JOIN assets a ON a.run_id=n.run_id AND a.asset_id=n.asset_id
           WHERE a.run_id=? AND a.status IN ('annotated', 'augmented')""",
        (run_id,),
    )
    class_counts = Counter(config.taxonomy[int(row["target_class_id"])] for row in annotations)
    class_split_counts: dict[str, Counter[str]] = {split: Counter() for split in ("train", "val", "test")}
    source_split_counts: dict[str, Counter[str]] = {split: Counter() for split in ("train", "val", "test")}
    for row in annotations:
        split = str(row["split"] or "unassigned")
        if split in class_split_counts:
            class_split_counts[split][config.taxonomy[int(row["target_class_id"])]] += 1
            source_split_counts[split][str(row["source_id"])] += 1
    split_counts = Counter(str(row["split"] or "unassigned") for row in assets if row["status"] in ("annotated", "augmented"))
    source_counts = Counter(str(row["source_id"]) for row in assets if row["status"] in ("annotated", "augmented"))
    environment_counts: Counter[str] = Counter()
    for row in assets:
        if row["status"] not in ("annotated", "augmented"):
            continue
        for tag in json.loads(str(row["environment_tags_json"])):
            environment_counts[str(tag)] += 1
    quarantined = Counter(str(row["quarantine_reason"]) for row in assets if row["status"] == "quarantined")
    duplicates = db.rows(
        "SELECT kind, COUNT(DISTINCT cluster_id) clusters, COUNT(*) members FROM duplicate_candidates WHERE run_id=? GROUP BY kind",
        (run_id,),
    )
    stages = db.rows(
        "SELECT source_id, stage, status, message, metrics_json, created_at FROM stage_results WHERE run_id=? ORDER BY result_id",
        (run_id,),
    )
    sources = db.rows("SELECT * FROM sources WHERE run_id=? ORDER BY source_id", (run_id,))
    reviews = db.rows(
        "SELECT review_type, decision, reviewer, reviewed_at, COUNT(*) count FROM reviews WHERE run_id=? GROUP BY review_type, decision, reviewer, reviewed_at",
        (run_id,),
    )
    return {
        "run_id": run_id,
        "release_id": config.release_id,
        "image_count": sum(split_counts.values()),
        "annotation_count": len(annotations),
        "counts_per_class": dict(sorted(class_counts.items())),
        "class_annotations_per_split": {
            split: dict(sorted(counts.items())) for split, counts in class_split_counts.items()
        },
        "counts_per_split": dict(sorted(split_counts.items())),
        "counts_per_source": dict(sorted(source_counts.items())),
        "source_annotations_per_split": {
            split: dict(sorted(counts.items())) for split, counts in source_split_counts.items()
        },
        "counts_per_environment": dict(sorted(environment_counts.items())),
        "quarantined": {"total": sum(quarantined.values()), "by_reason": dict(sorted(quarantined.items()))},
        "duplicates": [dict(row) for row in duplicates],
        "sequence_groups": int(db.connection.execute(
            "SELECT COUNT(DISTINCT group_id) FROM assets WHERE run_id=? AND group_id IS NOT NULL", (run_id,)
        ).fetchone()[0]),
        "sources": [dict(row) for row in sources],
        "human_reviews": [dict(row) for row in reviews],
        "stages": [
            {**dict(row), "metrics": json.loads(str(row["metrics_json"]))} | {"metrics_json": None} for row in stages
        ],
        "governance": {
            "all_sources_have_licence": all(str(row["licence"]).strip().lower() not in {"", "unknown"} for row in sources),
            "all_sources_governance_approved": all(row["governance_status"] == "approved" for row in sources),
            "source_count": len(sources),
        },
        "integrity_verification": {"status": "pending", "unexpected_files": None},
    }


def write_report(output_dir: Path, report: dict[str, object]) -> None:
    reports_dir = output_dir / "reports"
    json_dump(reports_dir / "qa_report.json", report)
    rows = []
    for key in (
        "image_count", "annotation_count", "counts_per_class", "class_annotations_per_split", "counts_per_split", "counts_per_source",
        "source_annotations_per_split",
        "counts_per_environment", "quarantined", "duplicates", "sequence_groups", "governance", "integrity_verification",
    ):
        rows.append(
            f"<tr><th>{html.escape(key.replace('_', ' ').title())}</th>"
            f"<td><pre>{html.escape(json.dumps(report.get(key), indent=2, sort_keys=True))}</pre></td></tr>"
        )
    document = (
        "<!doctype html><html><head><meta charset='utf-8'><title>WalkBuddy dataset QA</title>"
        "<style>body{font-family:system-ui;max-width:1100px;margin:2rem auto;padding:0 1rem}"
        "table{border-collapse:collapse;width:100%}th,td{border:1px solid #ccc;padding:.7rem;text-align:left;vertical-align:top}"
        "th{width:14rem;background:#f5f5f5}pre{white-space:pre-wrap;margin:0}</style></head><body>"
        f"<h1>Dataset QA: {html.escape(str(report['release_id']))}</h1><table>{''.join(rows)}</table></body></html>"
    )
    (reports_dir / "qa_report.html").write_text(document, encoding="utf-8")
