from __future__ import annotations

import json
import math
import xml.etree.ElementTree as ET
from dataclasses import dataclass
from pathlib import Path

from .database import PipelineDatabase
from .models import PipelineConfig, SourceConfig, StageResult, StageStatus, _UNMAPPED
from .quarantine import quarantine_asset


@dataclass(frozen=True)
class PixelBox:
    class_id: int
    x_min: float
    y_min: float
    x_max: float
    y_max: float
    repaired: bool = False


def _validate_box(box: PixelBox, width: int, height: int) -> PixelBox:
    values = (box.x_min, box.y_min, box.x_max, box.y_max)
    if not all(math.isfinite(value) for value in values):
        raise ValueError("box contains a non-finite coordinate")
    tolerance = 1.0
    if (
        box.class_id < 0 or box.x_min < -tolerance or box.y_min < -tolerance
        or box.x_max > width + tolerance or box.y_max > height + tolerance
    ):
        raise ValueError("box is outside image bounds")
    x_min, y_min = max(0.0, box.x_min), max(0.0, box.y_min)
    x_max, y_max = min(float(width), box.x_max), min(float(height), box.y_max)
    if x_max <= x_min or y_max <= y_min:
        raise ValueError("box has non-positive size")
    repaired = box.repaired or (x_min, y_min, x_max, y_max) != (box.x_min, box.y_min, box.x_max, box.y_max)
    return PixelBox(box.class_id, x_min, y_min, x_max, y_max, repaired)


def parse_yolo(path: Path, width: int, height: int) -> list[PixelBox]:
    boxes: list[PixelBox] = []
    for line_number, raw_line in enumerate(path.read_text(encoding="utf-8-sig").splitlines(), start=1):
        line = raw_line.strip()
        if not line:
            continue
        fields = line.split()
        try:
            class_id = int(fields[0])
            numbers = [float(value) for value in fields[1:]]
        except (ValueError, IndexError) as exc:
            raise ValueError(f"line {line_number}: malformed numeric values") from exc
        if len(numbers) == 4:
            center_x, center_y, box_width, box_height = numbers
            if not all(0 <= value <= 1 for value in numbers) or box_width <= 0 or box_height <= 0:
                raise ValueError(f"line {line_number}: invalid normalized YOLO box")
            x_min = (center_x - box_width / 2) * width
            y_min = (center_y - box_height / 2) * height
            x_max = (center_x + box_width / 2) * width
            y_max = (center_y + box_height / 2) * height
        elif len(numbers) >= 6 and len(numbers) % 2 == 0:
            xs = numbers[0::2]
            ys = numbers[1::2]
            if not all(0 <= value <= 1 for value in numbers):
                raise ValueError(f"line {line_number}: polygon coordinate outside normalized bounds")
            x_min, x_max = min(xs) * width, max(xs) * width
            y_min, y_max = min(ys) * height, max(ys) * height
        else:
            raise ValueError(f"line {line_number}: expected a box or polygon row")
        boxes.append(_validate_box(PixelBox(class_id, x_min, y_min, x_max, y_max), width, height))
    return boxes


def parse_voc(path: Path, class_names: tuple[str, ...], width: int, height: int) -> list[PixelBox]:
    root = ET.parse(path).getroot()
    name_to_id = {name: index for index, name in enumerate(class_names)}
    boxes: list[PixelBox] = []
    for item in root.findall("object"):
        name = (item.findtext("name") or "").strip()
        if name not in name_to_id:
            raise ValueError(f"unknown Pascal VOC class {name!r}")
        node = item.find("bndbox")
        if node is None:
            raise ValueError("Pascal VOC object has no bndbox")
        box = PixelBox(
            name_to_id[name],
            float(node.findtext("xmin", "nan")),
            float(node.findtext("ymin", "nan")),
            float(node.findtext("xmax", "nan")),
            float(node.findtext("ymax", "nan")),
        )
        boxes.append(_validate_box(box, width, height))
    return boxes


def load_coco(path: Path) -> dict[str, list[PixelBox]]:
    value = json.loads(path.read_text(encoding="utf-8-sig"))
    images = {int(item["id"]): str(item["file_name"]).replace("\\", "/") for item in value.get("images", [])}
    result: dict[str, list[PixelBox]] = {filename: [] for filename in images.values()}
    for annotation in value.get("annotations", []):
        if annotation.get("iscrowd"):
            continue
        filename = images[int(annotation["image_id"])]
        x, y, width, height = (float(value) for value in annotation["bbox"])
        result[filename].append(
            PixelBox(int(annotation["category_id"]), x, y, x + width, y + height)
        )
    return result


def _transform_point(x: float, y: float, width: int, height: int, orientation: int) -> tuple[float, float]:
    return {
        1: (x, y),
        2: (width - x, y),
        3: (width - x, height - y),
        4: (x, height - y),
        5: (y, x),
        6: (height - y, x),
        7: (height - y, width - x),
        8: (y, width - x),
    }.get(orientation, (x, y))


def transform_orientation(box: PixelBox, width: int, height: int, orientation: int) -> PixelBox:
    points = [
        _transform_point(x, y, width, height, orientation)
        for x, y in ((box.x_min, box.y_min), (box.x_max, box.y_min), (box.x_min, box.y_max), (box.x_max, box.y_max))
    ]
    xs, ys = zip(*points)
    return PixelBox(box.class_id, min(xs), min(ys), max(xs), max(ys), box.repaired)


def convert_annotations(
    db: PipelineDatabase, run_id: str, config: PipelineConfig, source: SourceConfig
) -> StageResult:
    coco = load_coco(source.annotation_file) if source.annotation_format == "coco" and source.annotation_file else None
    rows = db.rows(
        """SELECT * FROM assets WHERE run_id=? AND source_id=? AND status='standardized'
           ORDER BY original_relative_path""",
        (run_id, source.source_id),
    )
    converted = 0
    invalid = 0
    excluded_annotations = 0
    repaired_annotations = 0
    retained_negatives = 0
    for row in rows:
        asset_id = str(row["asset_id"])
        try:
            raw_width, raw_height = int(row["original_width"]), int(row["original_height"])
            annotation_format = source.annotation_format
            label_value = row["raw_label_path"]
            if annotation_format == "auto":
                if not label_value:
                    raise ValueError("image has no paired annotation")
                annotation_format = "voc" if Path(str(label_value)).suffix.lower() == ".xml" else "yolo"
            if annotation_format == "yolo":
                if not label_value:
                    raise ValueError("image has no paired YOLO label")
                boxes = parse_yolo(Path(str(label_value)), raw_width, raw_height)
            elif annotation_format in {"voc", "pascal_voc"}:
                if not label_value:
                    raise ValueError("image has no paired Pascal VOC label")
                boxes = parse_voc(Path(str(label_value)), source.class_names, raw_width, raw_height)
            elif annotation_format == "coco":
                if coco is None:
                    raise ValueError("COCO annotation_file is missing")
                relative = str(row["original_relative_path"]).replace("\\", "/")
                boxes = coco.get(relative, coco.get(Path(relative).name, []))
            else:
                raise ValueError(f"unsupported annotation format: {annotation_format}")
            if not boxes:
                raise ValueError("image has no annotations")

            output_rows: list[str] = []
            db.connection.execute("DELETE FROM annotations WHERE run_id=? AND asset_id=?", (run_id, asset_id))
            for raw_box in boxes:
                if raw_box.repaired:
                    repaired_annotations += 1
                target_name = source.target_for(raw_box.class_id)
                if target_name is _UNMAPPED:
                    raise ValueError(f"source class {raw_box.class_id} has no explicit mapping decision")
                if target_name is None:
                    excluded_annotations += 1
                    continue
                target_id = config.taxonomy.index(str(target_name))
                box = transform_orientation(raw_box, raw_width, raw_height, int(row["exif_orientation"] or 1))
                final_width, final_height = int(row["width"]), int(row["height"])
                box = _validate_box(box, final_width, final_height)
                if box.repaired and not raw_box.repaired:
                    repaired_annotations += 1
                center_x = ((box.x_min + box.x_max) / 2) / final_width
                center_y = ((box.y_min + box.y_max) / 2) / final_height
                box_width = (box.x_max - box.x_min) / final_width
                box_height = (box.y_max - box.y_min) / final_height
                normalized = (center_x, center_y, box_width, box_height)
                if not all(0 <= value <= 1 for value in normalized):
                    raise ValueError("post-standardization box lies outside normalized bounds")
                db.connection.execute(
                    """INSERT INTO annotations
                       (run_id, asset_id, source_class_id, target_class_id, x_center, y_center, width, height, status)
                       VALUES (?, ?, ?, ?, ?, ?, ?, ?, 'valid')""",
                    (run_id, asset_id, raw_box.class_id, target_id, *normalized),
                )
                output_rows.append(f"{target_id} {center_x:.8f} {center_y:.8f} {box_width:.8f} {box_height:.8f}")
            if not output_rows and config.empty_after_mapping_policy == "quarantine":
                raise ValueError("no mapped target annotations remain")
            if not output_rows:
                retained_negatives += 1
            output_path = config.workspace_root / run_id / "labels" / source.source_id / f"{asset_id}.txt"
            output_path.parent.mkdir(parents=True, exist_ok=True)
            output_path.write_text(("\n".join(output_rows) + "\n") if output_rows else "", encoding="utf-8")
            db.connection.execute(
                "UPDATE assets SET standard_label_path=?, status='annotated' WHERE run_id=? AND asset_id=?",
                (str(output_path), run_id, asset_id),
            )
            db.add_transform(
                run_id, asset_id, "annotation_conversion", f"{annotation_format}_to_yolo",
                {"coordinate_basis": "standardized_image", "target_taxonomy": list(config.taxonomy)},
                None, None,
            )
            converted += 1
        except (OSError, ValueError, KeyError, ET.ParseError, json.JSONDecodeError) as exc:
            invalid += 1
            quarantine_asset(db, run_id, asset_id, config.invalid_root, "invalid_annotation")
            db.add_transform(
                run_id, asset_id, "annotation_conversion", "rejected", {"reason": str(exc)}, None, None
            )
    db.connection.commit()
    status = StageStatus.FAIL if converted == 0 else StageStatus.WARNING if invalid else StageStatus.PASS
    db.connection.execute(
        "UPDATE sources SET status=? WHERE run_id=? AND source_id=?",
        ("quarantined" if status == StageStatus.FAIL else "annotated", run_id, source.source_id),
    )
    db.connection.commit()
    result = StageResult(
        "annotation_conversion",
        status,
        f"Converted {converted} assets; quarantined {invalid} invalid or unmapped annotations.",
        source.source_id,
        {
            "converted": converted, "invalid": invalid, "excluded_annotations": excluded_annotations,
            "repaired_annotations": repaired_annotations, "retained_negatives": retained_negatives,
        },
    )
    db.record_stage(run_id, result)
    return result
