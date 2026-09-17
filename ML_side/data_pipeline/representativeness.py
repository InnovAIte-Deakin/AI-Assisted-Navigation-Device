from __future__ import annotations

import json
from collections import Counter

from .database import PipelineDatabase
from .models import PipelineConfig, StageResult, StageStatus


def _distance(left: Counter[str], right: Counter[str]) -> float:
    left_total, right_total = sum(left.values()), sum(right.values())
    if left_total == 0 or right_total == 0:
        return 1.0
    keys = set(left) | set(right)
    return 0.5 * sum(abs(left[key] / left_total - right[key] / right_total) for key in keys)


def compare_split_distributions(
    db: PipelineDatabase, run_id: str, config: PipelineConfig
) -> StageResult:
    class_counts = {split: Counter() for split in ("train", "val", "test")}
    source_counts = {split: Counter() for split in ("train", "val", "test")}
    environment_counts = {split: Counter() for split in ("train", "val", "test")}
    for row in db.rows(
        """SELECT a.split, a.source_id, a.environment_tags_json, n.target_class_id
           FROM assets a JOIN annotations n ON n.run_id=a.run_id AND n.asset_id=a.asset_id
           WHERE a.run_id=? AND a.status='annotated'""",
        (run_id,),
    ):
        split = str(row["split"])
        if split not in class_counts:
            continue
        class_counts[split][config.taxonomy[int(row["target_class_id"])]] += 1
    for row in db.rows(
        """SELECT split, source_id, environment_tags_json FROM assets
           WHERE run_id=? AND status='annotated'""",
        (run_id,),
    ):
        split = str(row["split"])
        if split not in source_counts:
            continue
        source_counts[split][str(row["source_id"])] += 1
        for tag in json.loads(str(row["environment_tags_json"])):
            environment_counts[split][str(tag)] += 1
    distances = {
        split: {
            "class": _distance(class_counts["train"], class_counts[split]),
            "source": _distance(source_counts["train"], source_counts[split]),
            "environment": _distance(environment_counts["train"], environment_counts[split]),
        }
        for split in ("val", "test")
    }
    flagged = {
        f"{split}.{dimension}": value
        for split, values in distances.items()
        for dimension, value in values.items()
        if value > config.distribution_drift_threshold
    }
    status = StageStatus.WARNING if flagged else StageStatus.PASS
    result = StageResult(
        "split_representativeness",
        status,
        "Split distribution drift requires review." if flagged else "Train/val/test distributions are within the configured drift threshold.",
        metrics={
            "total_variation_distance": distances,
            "threshold": config.distribution_drift_threshold,
            "flagged": flagged,
            "counts": {
                "class": {split: dict(counts) for split, counts in class_counts.items()},
                "source": {split: dict(counts) for split, counts in source_counts.items()},
                "environment": {split: dict(counts) for split, counts in environment_counts.items()},
            },
        },
    )
    db.record_stage(run_id, result)
    return result
