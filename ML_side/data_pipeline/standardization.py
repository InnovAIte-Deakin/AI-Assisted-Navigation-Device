from __future__ import annotations

from pathlib import Path

from .database import PipelineDatabase
from .models import PipelineConfig, StageResult, StageStatus
from .quarantine import quarantine_asset
from .utils import sha256_file


def standardize_images(db: PipelineDatabase, run_id: str, config: PipelineConfig) -> StageResult:
    try:
        from PIL import Image, ImageOps
    except ImportError as exc:
        result = StageResult("standardization", StageStatus.FAIL, "Pillow is required to standardize images.")
        db.record_stage(run_id, result)
        return result

    rows = db.rows(
        """SELECT asset_id, source_id, raw_image_path, original_sha256 FROM assets
           WHERE run_id=? AND status='registered' ORDER BY source_id, original_relative_path""",
        (run_id,),
    )
    standardized = 0
    failed = 0
    extension = ".jpg" if config.image_format == "JPEG" else ".png"
    for row in rows:
        asset_id = str(row["asset_id"])
        source_path = Path(str(row["raw_image_path"]))
        destination = config.workspace_root / run_id / "standardized" / str(row["source_id"]) / f"{asset_id}{extension}"
        try:
            with Image.open(source_path) as image:
                image.load()
                original_width, original_height = image.size
                orientation = int(image.getexif().get(274, 1))
                transformed = ImageOps.exif_transpose(image)
                transformed = transformed.convert("RGB")
                final_width, final_height = transformed.size
                destination.parent.mkdir(parents=True, exist_ok=True)
                temporary = destination.with_suffix(destination.suffix + ".tmp")
                save_format = config.image_format
                save_options = {"quality": config.jpeg_quality, "optimize": True} if save_format == "JPEG" else {}
                transformed.save(temporary, format=save_format, **save_options)
                temporary.replace(destination)
        except Exception:
            failed += 1
            quarantine_asset(db, run_id, asset_id, config.invalid_root, "unreadable_image")
            continue
        output_digest = sha256_file(destination)
        db.connection.execute(
            """UPDATE assets SET standard_image_path=?, current_sha256=?, original_width=?, original_height=?,
               width=?, height=?, image_format=?, exif_orientation=?, status='standardized'
               WHERE run_id=? AND asset_id=?""",
            (
                str(destination), output_digest, original_width, original_height, final_width, final_height,
                save_format, orientation, run_id, asset_id,
            ),
        )
        db.add_transform(
            run_id,
            asset_id,
            "standardization",
            "exif_transpose_and_reencode",
            {
                "original_size": [original_width, original_height],
                "final_size": [final_width, final_height],
                "exif_orientation": orientation,
                "output_format": save_format,
                "jpeg_quality": config.jpeg_quality if save_format == "JPEG" else None,
            },
            str(row["original_sha256"]),
            output_digest,
        )
        standardized += 1
    db.connection.commit()
    status = StageStatus.FAIL if rows and standardized == 0 else StageStatus.WARNING if failed else StageStatus.PASS
    result = StageResult(
        "standardization",
        status,
        f"Standardized {standardized} images; quarantined {failed} unreadable images.",
        metrics={"standardized": standardized, "unreadable": failed},
    )
    db.record_stage(run_id, result)
    return result
