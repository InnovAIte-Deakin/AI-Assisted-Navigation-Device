from __future__ import annotations

import json
import os
import tempfile
import zipfile
from collections import defaultdict
from pathlib import Path
from random import Random
from typing import Any, Callable

from .database import PipelineDatabase, utc_now
from .models import PipelineConfig, StageResult, StageStatus
from .utils import copy_or_link, json_dump


def _sample_assets(rows: list[object], amount: int, seed: int) -> list[object]:
    by_class: dict[int, list[object]] = defaultdict(list)
    unique: dict[str, object] = {}
    for row in rows:
        unique[str(row["asset_id"])] = row
        class_text = str(row["class_ids"] or "").strip()
        class_ids = {int(value) for value in class_text.split(",") if value.strip()}
        for class_id in class_ids or {-1}:
            by_class[class_id].append(row)
    rng = Random(seed)
    selected: dict[str, object] = {}
    for class_id in sorted(by_class):
        choices = sorted(by_class[class_id], key=lambda item: str(item["asset_id"]))
        choice = rng.choice(choices)
        selected[str(choice["asset_id"])] = choice
    remaining = [row for asset_id, row in sorted(unique.items()) if asset_id not in selected]
    rng.shuffle(remaining)
    for row in remaining:
        if len(selected) >= min(amount, len(unique)):
            break
        selected[str(row["asset_id"])] = row
    return list(selected.values())[:amount]


def _annotation_zip(sample: list[object], taxonomy: tuple[str, ...], destination: Path) -> None:
    with tempfile.TemporaryDirectory() as temp_value:
        temp = Path(temp_value)
        object_dir = temp / "obj_train_data"
        object_dir.mkdir()
        train_lines: list[str] = []
        for row in sample:
            image = Path(str(row["standard_image_path"]))
            label = Path(str(row["standard_label_path"]))
            copy_or_link(image, object_dir / image.name)
            copy_or_link(label, object_dir / f"{image.stem}.txt")
            train_lines.append(f"obj_train_data/{image.name}")
        (temp / "obj.names").write_text("\n".join(taxonomy) + "\n", encoding="utf-8")
        (temp / "train.txt").write_text("\n".join(train_lines) + "\n", encoding="utf-8")
        (temp / "obj.data").write_text(
            f"classes = {len(taxonomy)}\nnames = obj.names\ntrain = train.txt\n", encoding="utf-8"
        )
        destination.parent.mkdir(parents=True, exist_ok=True)
        with zipfile.ZipFile(destination, "w", compression=zipfile.ZIP_DEFLATED) as archive:
            for name in ("obj.data", "obj.names", "train.txt"):
                archive.write(temp / name, name)
            for path in sorted(object_dir.iterdir()):
                archive.write(path, f"obj_train_data/{path.name}")


def prepare_cvat_review(
    db: PipelineDatabase,
    run_id: str,
    config: PipelineConfig,
    sample_per_source: int | None = None,
    client_factory: Callable[..., Any] | None = None,
) -> StageResult:
    amount = sample_per_source if sample_per_source is not None else config.qa_sample_per_source
    if amount <= 0:
        result = StageResult("semantic_review", StageStatus.SKIPPED, "Semantic QA sampling was disabled.")
        db.record_stage(run_id, result)
        return result
    review_root = config.workspace_root / run_id / "review" / "semantic"
    task_records: list[dict[str, object]] = []
    client = None
    resource_type = None
    if config.cvat_enabled:
        try:
            if client_factory is None:
                from cvat_sdk import make_client
                from cvat_sdk.core.proxies.tasks import ResourceType

                client_factory = make_client
                resource_type = ResourceType.LOCAL
            host, username, password = (os.environ.get(name) for name in ("CVAT_HOST", "CVAT_USER", "CVAT_PASS"))
            if not host or not username or not password:
                raise RuntimeError("CVAT_HOST, CVAT_USER, and CVAT_PASS must be set")
            client = client_factory(host=host, credentials=(username, password))
        except (ImportError, RuntimeError) as exc:
            result = StageResult("semantic_review", StageStatus.FAIL, f"CVAT task creation failed: {exc}")
            db.record_stage(run_id, result)
            return result

    for source in config.sources:
        rows = db.rows(
            """SELECT a.asset_id, a.standard_image_path, a.standard_label_path,
                      GROUP_CONCAT(DISTINCT n.target_class_id) AS class_ids
               FROM assets a LEFT JOIN annotations n ON n.run_id=a.run_id AND n.asset_id=a.asset_id
               WHERE a.run_id=? AND a.source_id=? AND a.status='annotated'
               GROUP BY a.asset_id, a.standard_image_path, a.standard_label_path
               ORDER BY a.asset_id""",
            (run_id, source.source_id),
        )
        sample = _sample_assets(rows, amount, config.seed)
        if not sample:
            continue
        source_dir = review_root / source.source_id
        images_dir = source_dir / "images"
        labels_dir = source_dir / "labels"
        for row in sample:
            image = Path(str(row["standard_image_path"]))
            label = Path(str(row["standard_label_path"]))
            copy_or_link(image, images_dir / image.name)
            copy_or_link(label, labels_dir / f"{image.stem}.txt")
        archive_path = source_dir / "annotations_yolo.zip"
        _annotation_zip(sample, config.taxonomy, archive_path)
        task_id: str | None = None
        if client is not None:
            spec = {
                "name": f"{config.cvat_project_name} - {source.source_id} - {run_id}",
                "labels": [{"name": name} for name in config.taxonomy],
            }
            task = client.tasks.create_from_data(
                spec=spec,
                resources=[str(images_dir / Path(str(row["standard_image_path"])).name) for row in sample],
                resource_type=resource_type,
            )
            task.import_annotations(format_name="YOLO 1.1", filename=str(archive_path))
            task_id = str(task.id)
        else:
            task_id = f"local-{source.source_id}-{run_id}"
        unique_assets = sorted({str(row["asset_id"]) for row in sample})
        for asset_id in unique_assets:
            db.connection.execute(
                """INSERT INTO reviews
                   (run_id, asset_id, review_type, decision, notes, external_task_id, created_at)
                   VALUES (?, ?, 'semantic_annotation', 'pending', '', ?, ?)""",
                (run_id, asset_id, task_id, utc_now()),
            )
        task_records.append({"source_id": source.source_id, "task_id": task_id, "sample_count": len(unique_assets)})
    db.connection.commit()
    json_dump(review_root / "tasks.json", {"run_id": run_id, "sample_per_source": amount, "tasks": task_records})
    result = StageResult(
        "semantic_review",
        StageStatus.REVIEW_REQUIRED if task_records else StageStatus.FAIL,
        f"Prepared {len(task_records)} source-level semantic review tasks; completion is required before release.",
        metrics={"sample_per_source": amount, "tasks": task_records},
    )
    db.record_stage(run_id, result)
    return result
