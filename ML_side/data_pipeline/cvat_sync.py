from __future__ import annotations

import json
import os
import tempfile
import zipfile
from pathlib import Path
from typing import Any, Callable

from .database import PipelineDatabase, utc_now
from .models import PipelineConfig, PipelineError, StageResult, StageStatus
from .utils import json_dump, sha256_file


def _safe_extract(archive: Path, destination: Path) -> None:
    root = destination.resolve()
    with zipfile.ZipFile(archive) as handle:
        for member in handle.infolist():
            target = (destination / member.filename).resolve()
            try:
                target.relative_to(root)
            except ValueError as exc:
                raise PipelineError(f"Unsafe CVAT export member: {member.filename}") from exc
        handle.extractall(destination)


def _validated_rows(path: Path, class_count: int) -> list[tuple[int, float, float, float, float]]:
    result: list[tuple[int, float, float, float, float]] = []
    for line_number, line in enumerate(path.read_text(encoding="utf-8-sig").splitlines(), start=1):
        if not line.strip():
            continue
        fields = line.split()
        if len(fields) != 5:
            raise PipelineError(f"{path.name}:{line_number}: CVAT export must contain YOLO box rows.")
        try:
            class_id = int(fields[0])
            center_x, center_y, width, height = (float(value) for value in fields[1:])
        except ValueError as exc:
            raise PipelineError(f"{path.name}:{line_number}: malformed CVAT annotation.") from exc
        if class_id < 0 or class_id >= class_count:
            raise PipelineError(f"{path.name}:{line_number}: class {class_id} is outside the target taxonomy.")
        if width <= 0 or height <= 0 or not all(0 <= value <= 1 for value in (center_x, center_y, width, height)):
            raise PipelineError(f"{path.name}:{line_number}: invalid normalized box.")
        if center_x - width / 2 < 0 or center_x + width / 2 > 1 or center_y - height / 2 < 0 or center_y + height / 2 > 1:
            raise PipelineError(f"{path.name}:{line_number}: box lies outside image bounds.")
        result.append((class_id, center_x, center_y, width, height))
    if not result:
        raise PipelineError(f"{path.name}: reviewed annotation is empty.")
    return result


def sync_cvat_reviews(
    db: PipelineDatabase,
    run_id: str,
    config: PipelineConfig,
    reviewer: str,
    client_factory: Callable[..., Any] | None = None,
) -> StageResult:
    tasks_path = config.workspace_root / run_id / "review" / "semantic" / "tasks.json"
    if not tasks_path.is_file():
        raise PipelineError("No semantic CVAT task manifest exists for this run.")
    tasks = json.loads(tasks_path.read_text(encoding="utf-8"))["tasks"]
    if client_factory is None:
        try:
            from cvat_sdk import make_client
        except ImportError as exc:
            raise PipelineError("cvat-sdk is required to sync CVAT reviews.") from exc
        client_factory = make_client
    host, username, password = (os.environ.get(name) for name in ("CVAT_HOST", "CVAT_USER", "CVAT_PASS"))
    if not host or not username or not password:
        raise PipelineError("CVAT_HOST, CVAT_USER, and CVAT_PASS must be set.")
    client = client_factory(host=host, credentials=(username, password))
    imported_assets = 0
    for task_record in tasks:
        task_id = str(task_record["task_id"])
        if task_id.startswith("local-"):
            continue
        task = client.tasks.retrieve(int(task_id))
        with tempfile.TemporaryDirectory() as temporary_value:
            temporary = Path(temporary_value)
            archive = temporary / "export.zip"
            task.export_dataset(format_name="YOLO 1.1", filename=str(archive))
            extracted = temporary / "extracted"
            extracted.mkdir()
            _safe_extract(archive, extracted)
            label_files = {
                path.stem: path for path in extracted.rglob("*.txt")
                if path.name not in {"train.txt", "obj.names", "obj.data"}
            }
            pending = db.rows(
                """SELECT DISTINCT r.asset_id, a.standard_label_path
                   FROM reviews r JOIN assets a ON a.run_id=r.run_id AND a.asset_id=r.asset_id
                   WHERE r.run_id=? AND r.review_type='semantic_annotation'
                     AND r.external_task_id=? AND r.decision='pending'""",
                (run_id, task_id),
            )
            for row in pending:
                asset_id = str(row["asset_id"])
                exported = label_files.get(asset_id)
                if exported is None:
                    raise PipelineError(f"CVAT task {task_id} export is missing label for {asset_id}.")
                annotations = _validated_rows(exported, len(config.taxonomy))
                corrected = config.workspace_root / run_id / "reviewed_labels" / f"{asset_id}.txt"
                corrected.parent.mkdir(parents=True, exist_ok=True)
                corrected.write_text(exported.read_text(encoding="utf-8-sig"), encoding="utf-8")
                db.connection.execute("DELETE FROM annotations WHERE run_id=? AND asset_id=?", (run_id, asset_id))
                for class_id, center_x, center_y, width, height in annotations:
                    db.connection.execute(
                        """INSERT INTO annotations
                           (run_id, asset_id, source_class_id, target_class_id, x_center, y_center, width, height, status)
                           VALUES (?, ?, ?, ?, ?, ?, ?, ?, 'reviewed')""",
                        (run_id, asset_id, class_id, class_id, center_x, center_y, width, height),
                    )
                previous = Path(str(row["standard_label_path"]))
                db.connection.execute(
                    "UPDATE assets SET standard_label_path=? WHERE run_id=? AND asset_id=?",
                    (str(corrected), run_id, asset_id),
                )
                db.add_transform(
                    run_id, asset_id, "semantic_review", "cvat_annotation_correction",
                    {"task_id": task_id, "reviewer": reviewer}, sha256_file(previous), sha256_file(corrected),
                )
                db.connection.execute(
                    """INSERT INTO reviews
                       (run_id, asset_id, review_type, reviewer, decision, notes, external_task_id, reviewed_at, created_at)
                       VALUES (?, ?, 'semantic_annotation', ?, 'approve', 'Imported reviewed CVAT annotations.', ?, ?, ?)""",
                    (run_id, asset_id, reviewer, task_id, utc_now(), utc_now()),
                )
                imported_assets += 1
    db.connection.commit()
    result = StageResult(
        "cvat_sync", StageStatus.PASS,
        f"Imported and audited corrected annotations for {imported_assets} CVAT-reviewed assets.",
        metrics={"imported_assets": imported_assets, "reviewer": reviewer},
    )
    db.record_stage(run_id, result)
    return result

