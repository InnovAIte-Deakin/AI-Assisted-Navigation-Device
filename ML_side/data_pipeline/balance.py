from __future__ import annotations

from collections import Counter

from .database import PipelineDatabase
from .models import PipelineConfig, StageResult, StageStatus


def class_counts(db: PipelineDatabase, run_id: str, split: str | None = None) -> Counter[int]:
    where_split = " AND a.split=?" if split else ""
    parameters: tuple[object, ...] = (run_id, split) if split else (run_id,)
    rows = db.rows(
        """SELECT n.target_class_id, COUNT(*) AS count
           FROM annotations n JOIN assets a ON a.run_id=n.run_id AND a.asset_id=n.asset_id
           WHERE a.run_id=? AND a.status IN ('annotated', 'augmented')"""
        + where_split
        + " GROUP BY n.target_class_id",
        parameters,
    )
    return Counter({int(row["target_class_id"]): int(row["count"]) for row in rows})


def check_balance(db: PipelineDatabase, run_id: str, config: PipelineConfig) -> StageResult:
    per_split = {split: class_counts(db, run_id, split) for split in ("train", "val", "test")}
    training = per_split["train"]
    nonzero = [training.get(class_id, 0) for class_id in range(len(config.taxonomy)) if training.get(class_id, 0)]
    missing = [config.taxonomy[class_id] for class_id in range(len(config.taxonomy)) if training.get(class_id, 0) == 0]
    ratio = max(nonzero) / min(nonzero) if nonzero else float("inf")
    if missing or ratio > config.imbalance_ratio:
        status = StageStatus.FAIL
        message = f"Training class balance gate failed: ratio={ratio:.2f}, missing={missing}."
    else:
        status = StageStatus.PASS
        message = f"Training class balance gate passed at {ratio:.2f}:1."
    result = StageResult(
        "class_balance",
        status,
        message,
        metrics={
            "threshold": config.imbalance_ratio,
            "ratio": ratio,
            "missing_classes": missing,
            "per_split": {
                split: {config.taxonomy[class_id]: counts.get(class_id, 0) for class_id in range(len(config.taxonomy))}
                for split, counts in per_split.items()
            },
        },
    )
    db.record_stage(run_id, result)
    return result

