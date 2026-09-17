from __future__ import annotations

import math
from pathlib import Path

from .database import PipelineDatabase
from .models import PipelineConfig, StageResult, StageStatus
from .utils import copy_or_link, json_dump


def inspect_quality(
    db: PipelineDatabase,
    run_id: str,
    config: PipelineConfig,
    *,
    min_width: int = 64,
    min_height: int = 64,
    dark_mean: float = 12.0,
    bright_mean: float = 243.0,
    min_entropy: float = 1.5,
    min_edge_variance: float = 4.0,
) -> StageResult:
    from PIL import Image, ImageFilter, ImageStat

    rows = db.rows(
        "SELECT asset_id, source_id, standard_image_path, width, height FROM assets WHERE run_id=? AND status='annotated'",
        (run_id,),
    )
    flagged = 0
    review_root = config.workspace_root / run_id / "review" / "quality"
    for row in rows:
        reasons: list[str] = []
        if int(row["width"]) < min_width or int(row["height"]) < min_height:
            reasons.append("low_resolution")
        path = Path(str(row["standard_image_path"]))
        with Image.open(path) as image:
            gray = image.convert("L")
            mean = float(ImageStat.Stat(gray).mean[0])
            histogram = gray.histogram()
            total = sum(histogram)
            entropy = -sum((count / total) * math.log2(count / total) for count in histogram if count)
            edge_variance = float(ImageStat.Stat(gray.filter(ImageFilter.FIND_EDGES)).var[0])
        if mean <= dark_mean:
            reasons.append("very_dark")
        if mean >= bright_mean:
            reasons.append("very_bright")
        if entropy < min_entropy:
            reasons.append("low_information")
        if edge_variance < min_edge_variance:
            reasons.append("possible_blur")
        if reasons:
            flagged += 1
            asset_id = str(row["asset_id"])
            destination = review_root / str(row["source_id"]) / asset_id
            copy_or_link(path, destination / path.name)
            json_dump(
                destination / "quality.json",
                {"asset_id": asset_id, "flags": reasons, "brightness_mean": mean, "entropy": entropy, "edge_variance": edge_variance},
            )
            db.connection.execute(
                """INSERT INTO reviews
                   (run_id, asset_id, review_type, decision, notes, created_at)
                   VALUES (?, ?, 'image_quality', 'pending', ?, datetime('now'))""",
                (run_id, asset_id, ",".join(reasons)),
            )
    db.connection.commit()
    result = StageResult(
        "quality_inspection",
        StageStatus.REVIEW_REQUIRED if flagged else StageStatus.PASS,
        f"Flagged {flagged} images for quality review; no subjective quality decision was applied automatically.",
        metrics={"inspected": len(rows), "flagged": flagged},
    )
    db.record_stage(run_id, result)
    return result
