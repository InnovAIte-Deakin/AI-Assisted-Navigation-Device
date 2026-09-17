from __future__ import annotations

import math
import random
import uuid
from collections import Counter, defaultdict
from pathlib import Path

from .balance import class_counts
from .database import PipelineDatabase, utc_now
from .models import PipelineConfig, StageResult, StageStatus
from .utils import sha256_file


AUGMENT_NAMESPACE = uuid.UUID("8554135c-863f-55f1-bbfe-0ad4d7ce63f5")


def _crop_bounds(annotation: object, image_width: int, image_height: int, rng: random.Random) -> tuple[int, int, int, int]:
    box_width = float(annotation["width"]) * image_width
    box_height = float(annotation["height"]) * image_height
    center_x = float(annotation["x_center"]) * image_width
    center_y = float(annotation["y_center"]) * image_height
    scale = rng.uniform(1.35, 2.0)
    crop_width = min(image_width, max(32, int(box_width * scale)))
    crop_height = min(image_height, max(32, int(box_height * scale)))
    left = max(0, min(image_width - crop_width, int(center_x - crop_width / 2)))
    top = max(0, min(image_height - crop_height, int(center_y - crop_height / 2)))
    return left, top, left + crop_width, top + crop_height


def augment_training_balance(
    db: PipelineDatabase, run_id: str, config: PipelineConfig, max_generated: int = 10000
) -> StageResult:
    from PIL import Image, ImageEnhance, ImageFilter

    counts = class_counts(db, run_id, "train")
    if not counts:
        result = StageResult("augmentation", StageStatus.FAIL, "No training annotations are available.")
        db.record_stage(run_id, result)
        return result
    largest = max(counts.values())
    target = math.ceil(largest / config.imbalance_ratio)
    deficits = {class_id: max(0, target - counts.get(class_id, 0)) for class_id in range(len(config.taxonomy))}
    if not any(deficits.values()):
        result = StageResult("augmentation", StageStatus.SKIPPED, "Training classes already satisfy the balance gate.")
        db.record_stage(run_id, result)
        return result

    annotation_rows = db.rows(
        """SELECT n.*, a.source_id, a.standard_image_path, a.group_id, a.environment_tags_json,
                  a.original_filename, a.original_relative_path
           FROM annotations n JOIN assets a ON a.run_id=n.run_id AND a.asset_id=n.asset_id
           WHERE a.run_id=? AND a.status='annotated' AND a.split='train'
           ORDER BY n.target_class_id, a.asset_id, n.annotation_id""",
        (run_id,),
    )
    by_class: dict[int, list[object]] = defaultdict(list)
    by_asset: dict[str, list[object]] = defaultdict(list)
    for row in annotation_rows:
        by_class[int(row["target_class_id"])].append(row)
        by_asset[str(row["asset_id"])].append(row)

    rng = random.Random(config.seed + 1)
    generated = 0
    attempts = 0
    impossible: dict[int, int] = {}
    while any(deficits.values()) and generated < max_generated and attempts < max_generated * 20:
        attempts += 1
        target_class = max(deficits, key=lambda class_id: (deficits[class_id], -class_id))
        if deficits[target_class] <= 0 or not by_class[target_class]:
            if deficits[target_class] > 0:
                impossible[target_class] = deficits[target_class]
            deficits[target_class] = 0
            continue
        anchor = rng.choice(by_class[target_class])
        parent_id = str(anchor["asset_id"])
        source_path = Path(str(anchor["standard_image_path"]))
        with Image.open(source_path) as source_image:
            image = source_image.convert("RGB")
            crop = _crop_bounds(anchor, image.width, image.height, rng)
            left, top, right, bottom = crop
            kept: list[tuple[object, float, float, float, float]] = []
            has_nondeficit = False
            for item in by_asset[parent_id]:
                x_min = (float(item["x_center"]) - float(item["width"]) / 2) * image.width
                y_min = (float(item["y_center"]) - float(item["height"]) / 2) * image.height
                x_max = (float(item["x_center"]) + float(item["width"]) / 2) * image.width
                y_max = (float(item["y_center"]) + float(item["height"]) / 2) * image.height
                clipped = max(x_min, left), max(y_min, top), min(x_max, right), min(y_max, bottom)
                if clipped[2] > clipped[0] and clipped[3] > clipped[1]:
                    class_id = int(item["target_class_id"])
                    if deficits.get(class_id, 0) <= 0:
                        has_nondeficit = True
                        break
                    kept.append((item, *clipped))
            if has_nondeficit or not any(int(item[0]["target_class_id"]) == target_class for item in kept):
                continue
            output = image.crop(crop)
            variant = generated % 3
            if variant == 1:
                output = ImageEnhance.Brightness(output).enhance(rng.uniform(0.75, 1.25))
                operation = "crop_brightness"
            elif variant == 2:
                output = output.filter(ImageFilter.GaussianBlur(radius=rng.uniform(0.4, 1.2)))
                operation = "crop_blur"
            else:
                operation = "crop"
            augmentation_id = str(uuid.uuid5(AUGMENT_NAMESPACE, f"{run_id}:{parent_id}:{generated}:{crop}:{operation}"))
            output_path = config.workspace_root / run_id / "augmented" / f"{augmentation_id}.jpg"
            label_path = config.workspace_root / run_id / "augmented_labels" / f"{augmentation_id}.txt"
            output_path.parent.mkdir(parents=True, exist_ok=True)
            label_path.parent.mkdir(parents=True, exist_ok=True)
            output.save(output_path, format="JPEG", quality=config.jpeg_quality, optimize=True)
            crop_width, crop_height = right - left, bottom - top
            label_lines: list[str] = []
            db.connection.execute(
                """INSERT INTO assets
                   (run_id, asset_id, source_id, parent_asset_id, original_filename, original_relative_path,
                    raw_image_path, standard_image_path, standard_label_path, original_sha256, current_sha256,
                    original_width, original_height, width, height, image_format, exif_orientation, group_id,
                    split, status, environment_tags_json, is_augmented, created_at)
                   VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 'JPEG', 1, ?, 'train', 'augmented', ?, 1, ?)""",
                (
                    run_id, augmentation_id, anchor["source_id"], parent_id, f"aug_{anchor['original_filename']}",
                    f"augmentation/{augmentation_id}.jpg", str(source_path), str(output_path), str(label_path),
                    sha256_file(source_path), sha256_file(output_path), image.width, image.height,
                    crop_width, crop_height, anchor["group_id"], anchor["environment_tags_json"], utc_now(),
                ),
            )
            added_classes: Counter[int] = Counter()
            for item, x_min, y_min, x_max, y_max in kept:
                class_id = int(item["target_class_id"])
                center_x = ((x_min + x_max) / 2 - left) / crop_width
                center_y = ((y_min + y_max) / 2 - top) / crop_height
                box_width = (x_max - x_min) / crop_width
                box_height = (y_max - y_min) / crop_height
                db.connection.execute(
                    """INSERT INTO annotations
                       (run_id, asset_id, source_class_id, target_class_id, x_center, y_center, width, height, status)
                       VALUES (?, ?, ?, ?, ?, ?, ?, ?, 'valid')""",
                    (run_id, augmentation_id, item["source_class_id"], class_id, center_x, center_y, box_width, box_height),
                )
                label_lines.append(f"{class_id} {center_x:.8f} {center_y:.8f} {box_width:.8f} {box_height:.8f}")
                added_classes[class_id] += 1
            label_path.write_text("\n".join(label_lines) + "\n", encoding="utf-8")
            db.add_transform(
                run_id, augmentation_id, "augmentation", operation,
                {"parent_asset_id": parent_id, "crop": list(crop), "seed": config.seed + 1},
                sha256_file(source_path), sha256_file(output_path),
            )
            for class_id, amount in added_classes.items():
                deficits[class_id] = max(0, deficits[class_id] - amount)
            generated += 1
    db.connection.commit()
    remaining_values = {**{class_id: amount for class_id, amount in deficits.items() if amount > 0}, **impossible}
    remaining = {config.taxonomy[class_id]: amount for class_id, amount in remaining_values.items() if amount > 0}
    status = StageStatus.PASS if not remaining else StageStatus.FAIL
    message = (
        f"Generated {generated} training-only augmentations without adding already-balanced classes."
        if not remaining
        else f"Generated {generated} safe augmentations, but additional source data is required for {remaining}."
    )
    result = StageResult(
        "augmentation", status, message,
        metrics={"generated": generated, "target_minimum": target, "remaining_deficits": remaining, "seed": config.seed + 1},
    )
    db.record_stage(run_id, result)
    return result
