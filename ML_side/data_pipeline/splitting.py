from __future__ import annotations

import hashlib
import json
import random
from collections import Counter, defaultdict

from .database import PipelineDatabase
from .models import PipelineConfig, StageResult, StageStatus


SPLITS = ("train", "val", "test")


def _stable_tie(seed: int, group_id: str, split: str) -> str:
    return hashlib.sha256(f"{seed}:{group_id}:{split}".encode("utf-8")).hexdigest()


def assign_splits(db: PipelineDatabase, run_id: str, config: PipelineConfig) -> StageResult:
    rows = db.rows(
        """SELECT a.asset_id, a.source_id, a.group_id, a.environment_tags_json, n.target_class_id
           FROM assets a LEFT JOIN annotations n ON n.run_id=a.run_id AND n.asset_id=a.asset_id
           WHERE a.run_id=? AND a.status='annotated' AND a.group_id IS NOT NULL
           ORDER BY a.group_id, a.asset_id, n.annotation_id""",
        (run_id,),
    )
    group_assets: dict[str, set[str]] = defaultdict(set)
    group_classes: dict[str, Counter[int]] = defaultdict(Counter)
    group_sources: dict[str, Counter[str]] = defaultdict(Counter)
    group_environments: dict[str, Counter[str]] = defaultdict(Counter)
    for row in rows:
        group = str(row["group_id"])
        group_assets[group].add(str(row["asset_id"]))
        if row["target_class_id"] is not None:
            group_classes[group][int(row["target_class_id"])] += 1
    asset_rows = db.rows(
        """SELECT asset_id, source_id, group_id, environment_tags_json FROM assets
           WHERE run_id=? AND status='annotated' AND group_id IS NOT NULL""",
        (run_id,),
    )
    for row in asset_rows:
        group = str(row["group_id"])
        group_sources[group][str(row["source_id"])] += 1
        for tag in json.loads(str(row["environment_tags_json"])):
            group_environments[group][str(tag)] += 1
    if not group_assets:
        result = StageResult("splitting", StageStatus.FAIL, "No grouped annotated assets are available.")
        db.record_stage(run_id, result)
        return result

    ratios = {"train": config.train_ratio, "val": config.val_ratio, "test": config.test_ratio}
    total_assets = sum(len(values) for values in group_assets.values())
    total_classes = sum(group_classes.values(), Counter())
    total_sources = sum(group_sources.values(), Counter())
    total_environments = sum(group_environments.values(), Counter())
    target_assets = {split: total_assets * ratio for split, ratio in ratios.items()}
    target_classes = {
        split: {class_id: count * ratios[split] for class_id, count in total_classes.items()} for split in SPLITS
    }
    target_sources = {
        split: {source: count * ratios[split] for source, count in total_sources.items()} for split in SPLITS
    }
    target_environments = {
        split: {tag: count * ratios[split] for tag, count in total_environments.items()} for split in SPLITS
    }
    current_assets = Counter()
    current_classes = {split: Counter() for split in SPLITS}
    current_sources = {split: Counter() for split in SPLITS}
    current_environments = {split: Counter() for split in SPLITS}

    assignments: dict[str, str] = {}

    def place(group: str, split: str) -> None:
        assignments[group] = split
        current_assets[split] += len(group_assets[group])
        current_classes[split].update(group_classes[group])
        current_sources[split].update(group_sources[group])
        current_environments[split].update(group_environments[group])

    # Seed class coverage before optimizing totals. Without this, numerous
    # common-only groups can consume the train quota before rare groups arrive.
    groups_by_class: dict[int, list[str]] = defaultdict(list)
    for group, counts in group_classes.items():
        for class_id in counts:
            groups_by_class[class_id].append(group)
    for class_id in sorted(groups_by_class, key=lambda value: (total_classes[value], value)):
        candidates = sorted(
            groups_by_class[class_id],
            key=lambda group: (sum(group_classes[group].values()), _stable_tie(config.seed, group, f"seed-{class_id}")),
        )
        desired_splits = [split for split in SPLITS if ratios[split] > 0]
        for split in desired_splits:
            if current_classes[split][class_id] > 0:
                continue
            available = [group for group in candidates if group not in assignments]
            if not available:
                break
            place(available[0], split)

    # Large and rare-class-heavy groups are placed first; deterministic hashes break ties.
    ordered_groups = sorted(
        group_assets,
        key=lambda group: (
            -sum(group_classes[group].values()),
            -sum(1 / max(total_classes[class_id], 1) for class_id in group_classes[group]),
            _stable_tie(config.seed, group, "order"),
        ),
    )
    for group in ordered_groups:
        if group in assignments:
            continue
        scores: list[tuple[float, str, str]] = []
        for split in SPLITS:
            asset_score = abs((current_assets[split] + len(group_assets[group])) - target_assets[split]) / max(target_assets[split], 1)
            class_score = sum(
                abs((current_classes[split][class_id] + count) - target_classes[split][class_id])
                / max(target_classes[split][class_id], 1)
                for class_id, count in group_classes[group].items()
            )
            source_score = sum(
                abs((current_sources[split][source] + count) - target_sources[split][source])
                / max(target_sources[split][source], 1)
                for source, count in group_sources[group].items()
            )
            environment_score = sum(
                abs((current_environments[split][tag] + count) - target_environments[split][tag])
                / max(target_environments[split][tag], 1)
                for tag, count in group_environments[group].items()
            )
            scores.append((
                asset_score + class_score + source_score + environment_score,
                _stable_tie(config.seed, group, split), split,
            ))
        split = min(scores)[2]
        place(group, split)

    for group, split in assignments.items():
        db.connection.execute(
            "UPDATE assets SET split=? WHERE run_id=? AND group_id=? AND status='annotated'", (split, run_id, group)
        )
    db.connection.commit()
    metrics = {
        "assets": dict(current_assets),
        "classes": {split: dict(sorted(current_classes[split].items())) for split in SPLITS},
        "sources": {split: dict(sorted(current_sources[split].items())) for split in SPLITS},
        "environments": {split: dict(sorted(current_environments[split].items())) for split in SPLITS},
        "groups": len(assignments),
        "seed": config.seed,
    }
    result = StageResult(
        "splitting", StageStatus.PASS,
        f"Assigned {total_assets} assets in {len(assignments)} intact groups using seed {config.seed}.",
        metrics=metrics,
    )
    db.record_stage(run_id, result)
    return result
