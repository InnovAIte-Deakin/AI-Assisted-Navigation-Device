from __future__ import annotations

import csv
import json
import shutil
from collections import defaultdict
from pathlib import Path

from .database import PipelineDatabase, utc_now
from .models import PipelineConfig, PipelineError, StageResult, StageStatus
from .reporting import build_report, write_report
from .reviews import unresolved_review_count
from .utils import json_dump, sha256_file


def _write_dataset_yaml(path: Path, taxonomy: tuple[str, ...]) -> None:
    names = "\n".join(f"  {index}: {json.dumps(name)}" for index, name in enumerate(taxonomy))
    path.write_text(
        "path: .\ntrain: images/train\nval: images/val\ntest: images/test\n"
        f"nc: {len(taxonomy)}\nnames:\n{names}\n",
        encoding="utf-8",
    )


def _load_supplied_dataset_yaml(path: Path, taxonomy: tuple[str, ...]) -> str:
    if not path.is_file():
        raise PipelineError(f"Supplied dataset YAML does not exist: {path}")
    try:
        import yaml  # type: ignore
    except ImportError as exc:
        raise PipelineError("PyYAML is required to validate a supplied dataset YAML.") from exc
    try:
        text = path.read_text(encoding="utf-8-sig")
        value = yaml.safe_load(text)
    except Exception as exc:
        raise PipelineError(f"Could not parse supplied dataset YAML {path}: {exc}") from exc
    if not isinstance(value, dict):
        raise PipelineError("Supplied dataset YAML must contain a mapping.")
    names_value = value.get("names")
    if isinstance(names_value, dict):
        try:
            names = [str(names_value[index]) for index in range(len(names_value))]
        except (KeyError, TypeError) as exc:
            raise PipelineError("Supplied dataset YAML names must use consecutive IDs starting at 0.") from exc
    elif isinstance(names_value, list):
        names = [str(name) for name in names_value]
    else:
        raise PipelineError("Supplied dataset YAML names must be a list or an ID-to-name mapping.")
    if tuple(names) != taxonomy:
        raise PipelineError(
            "Supplied dataset YAML class names/order do not match the configured taxonomy. "
            "The taxonomy list is the authoritative class-ID order."
        )
    if "nc" in value:
        try:
            supplied_count = int(value["nc"])
        except (TypeError, ValueError) as exc:
            raise PipelineError("Supplied dataset YAML nc must be an integer.") from exc
        if supplied_count != len(taxonomy):
            raise PipelineError("Supplied dataset YAML nc does not match the configured taxonomy.")
    expected_paths = {"path": ".", "train": "images/train", "val": "images/val", "test": "images/test"}
    mismatches = [key for key, expected in expected_paths.items() if str(value.get(key, "")) != expected]
    if mismatches:
        raise PipelineError(
            "Supplied dataset YAML must point inside the release package; invalid fields: "
            + ", ".join(mismatches)
        )
    return text


def _lineage_manifest(db: PipelineDatabase, run_id: str, config: PipelineConfig) -> dict[str, object]:
    run = dict(db.rows("SELECT * FROM runs WHERE run_id=?", (run_id,))[0])
    sources = [dict(row) for row in db.rows("SELECT * FROM sources WHERE run_id=? ORDER BY source_id", (run_id,))]
    transforms: dict[str, list[dict[str, object]]] = defaultdict(list)
    for row in db.rows("SELECT * FROM transformations WHERE run_id=? ORDER BY transformation_id", (run_id,)):
        item = dict(row)
        item["parameters"] = json.loads(str(item.pop("parameters_json")))
        transforms[str(row["asset_id"])].append(item)
    reviews: dict[str, list[dict[str, object]]] = defaultdict(list)
    for row in db.rows("SELECT * FROM reviews WHERE run_id=? ORDER BY review_id", (run_id,)):
        if row["asset_id"]:
            reviews[str(row["asset_id"])].append(dict(row))
    samples: list[dict[str, object]] = []
    rows = db.rows(
        """SELECT * FROM assets WHERE run_id=? AND status IN ('annotated', 'augmented')
           ORDER BY split, asset_id""",
        (run_id,),
    )
    for row in rows:
        asset_id = str(row["asset_id"])
        extension = Path(str(row["standard_image_path"])).suffix.lower()
        samples.append(
            {
                "asset_id": asset_id,
                "parent_asset_id": row["parent_asset_id"],
                "source_id": row["source_id"],
                "original_filename": row["original_filename"],
                "original_relative_path": row["original_relative_path"],
                "original_sha256": row["original_sha256"],
                "released_image_sha256": row["current_sha256"],
                "group_id": row["group_id"],
                "environment_tags": json.loads(str(row["environment_tags_json"])),
                "split": row["split"],
                "image": f"images/{row['split']}/{asset_id}{extension}",
                "label": f"labels/{row['split']}/{asset_id}.txt",
                "is_augmented": bool(row["is_augmented"]),
                "transformations": transforms.get(asset_id, []),
                "reviews": reviews.get(asset_id, []),
            }
        )
    run["runtime"] = json.loads(str(run.pop("runtime_json")))
    return {
        "schema_version": "2.0.0",
        "run": run,
        "taxonomy": {"version": config.taxonomy_version, "classes": list(config.taxonomy)},
        "dataset_yaml": {
            "mode": config.dataset_yaml_mode,
            "included": config.dataset_yaml_mode != "none",
            "source": str(config.dataset_yaml_path) if config.dataset_yaml_path else None,
            "class_count": len(config.taxonomy),
        },
        "sources": sources,
        "samples": samples,
        "created_at": utc_now(),
    }


def _write_assets_csv(path: Path, manifest: dict[str, object]) -> None:
    fields = [
        "asset_id", "parent_asset_id", "source_id", "original_filename", "original_relative_path",
        "original_sha256", "released_image_sha256", "group_id", "environment_tags", "split", "image", "label", "is_augmented",
    ]
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fields)
        writer.writeheader()
        for sample in manifest["samples"]:  # type: ignore[index]
            row = {field: sample.get(field) for field in fields}
            row["environment_tags"] = json.dumps(row["environment_tags"], separators=(",", ":"))
            writer.writerow(row)


def _write_checksums(root: Path) -> None:
    checksum_path = root / "checksums.sha256"
    files = sorted(path for path in root.rglob("*") if path.is_file() and path != checksum_path)
    lines = [f"{sha256_file(path)}  {path.relative_to(root).as_posix()}" for path in files]
    checksum_path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def verify_release(root: Path) -> tuple[bool, list[str]]:
    checksum_path = root / "checksums.sha256"
    if not checksum_path.is_file():
        return False, ["checksums.sha256 is missing"]
    expected: dict[str, str] = {}
    issues: list[str] = []
    for line_number, line in enumerate(checksum_path.read_text(encoding="utf-8").splitlines(), start=1):
        if not line.strip():
            continue
        try:
            digest, relative = line.split("  ", 1)
        except ValueError:
            issues.append(f"Malformed checksum row {line_number}")
            continue
        expected[relative] = digest.lower()
    actual_paths = {
        path.relative_to(root).as_posix(): path for path in root.rglob("*") if path.is_file() and path != checksum_path
    }
    for relative in sorted(set(expected) - set(actual_paths)):
        issues.append(f"Missing approved file: {relative}")
    for relative in sorted(set(actual_paths) - set(expected)):
        issues.append(f"Unexpected file: {relative}")
    for relative in sorted(set(expected) & set(actual_paths)):
        if sha256_file(actual_paths[relative]).lower() != expected[relative]:
            issues.append(f"Checksum mismatch: {relative}")
    return not issues, issues


def build_release(db: PipelineDatabase, run_id: str, config: PipelineConfig) -> StageResult:
    if unresolved_review_count(db, run_id):
        result = StageResult("release", StageStatus.REVIEW_REQUIRED, "Human review decisions are still pending.")
        db.record_stage(run_id, result)
        return result
    governance_failures = db.rows(
        """SELECT source_id, governance_status, licence FROM sources
           WHERE run_id=? AND (governance_status!='approved' OR licence='' OR lower(licence)='unknown')""",
        (run_id,),
    )
    if governance_failures:
        result = StageResult(
            "release", StageStatus.FAIL,
            "Release blocked by source licence/governance review: "
            + ", ".join(str(row["source_id"]) for row in governance_failures),
        )
        db.record_stage(run_id, result)
        return result
    failures = db.rows("SELECT stage, source_id, message FROM stage_results WHERE run_id=? AND status='fail'", (run_id,))
    # A pre-augmentation balance failure is allowed only when a later passing balance result exists.
    latest_by_stage: dict[tuple[str, object], object] = {}
    for row in db.rows("SELECT result_id, stage, source_id, status, message FROM stage_results WHERE run_id=? ORDER BY result_id", (run_id,)):
        latest_by_stage[(str(row["stage"]), row["source_id"])] = row
    active_failures = [row for row in latest_by_stage.values() if row["status"] == "fail"]
    if active_failures:
        result = StageResult(
            "release", StageStatus.FAIL,
            "Release blocked by failed gates: " + "; ".join(f"{row['stage']}: {row['message']}" for row in active_failures),
        )
        db.record_stage(run_id, result)
        return result
    destination = config.release_dir
    if destination.exists():
        previous = db.connection.execute(
            "SELECT status FROM stage_results WHERE run_id=? AND stage='release' ORDER BY result_id DESC LIMIT 1",
            (run_id,),
        ).fetchone()
        if previous is None or previous["status"] != "pass":
            raise PipelineError(f"Release directory already exists; refusing to overwrite it: {destination}")
        valid, issues = verify_release(destination)
        result = StageResult(
            "release", StageStatus.PASS if valid else StageStatus.FAIL,
            "Existing release remains checksum-valid." if valid else "Existing release has been modified.",
            metrics={"release_dir": str(destination), "checksum_valid": valid, "issues": issues},
        )
        db.record_stage(run_id, result)
        return result
    staging = destination.parent / f".{destination.name}.staging-{run_id}"
    if staging.exists():
        raise PipelineError(f"Staging directory already exists and requires manual inspection: {staging}")
    staging.mkdir(parents=True)
    try:
        rows = db.rows(
            """SELECT asset_id, split, standard_image_path, standard_label_path FROM assets
               WHERE run_id=? AND status IN ('annotated', 'augmented') ORDER BY split, asset_id""",
            (run_id,),
        )
        for row in rows:
            if row["split"] not in ("train", "val", "test"):
                raise PipelineError(f"Asset {row['asset_id']} has no valid final split.")
            image_source = Path(str(row["standard_image_path"]))
            label_source = Path(str(row["standard_label_path"]))
            image_destination = staging / "images" / str(row["split"]) / f"{row['asset_id']}{image_source.suffix.lower()}"
            label_destination = staging / "labels" / str(row["split"]) / f"{row['asset_id']}.txt"
            image_destination.parent.mkdir(parents=True, exist_ok=True)
            label_destination.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(image_source, image_destination)
            shutil.copy2(label_source, label_destination)
        if config.dataset_yaml_mode == "generate":
            _write_dataset_yaml(staging / "data.yaml", config.taxonomy)
        elif config.dataset_yaml_mode == "supplied":
            assert config.dataset_yaml_path is not None
            supplied_yaml = _load_supplied_dataset_yaml(config.dataset_yaml_path, config.taxonomy)
            (staging / "data.yaml").write_text(supplied_yaml, encoding="utf-8")
        manifest = _lineage_manifest(db, run_id, config)
        json_dump(staging / "manifest.json", manifest)
        _write_assets_csv(staging / "assets.csv", manifest)
        report = build_report(db, run_id, config)
        write_report(staging, report)
        _write_checksums(staging)
        valid, issues = verify_release(staging)
        if not valid:
            raise PipelineError("Release verification failed: " + "; ".join(issues))
        report["integrity_verification"] = {"status": "pass", "unexpected_files": 0}
        write_report(staging, report)
        _write_checksums(staging)
        valid, issues = verify_release(staging)
        if not valid:
            raise PipelineError("Final report/checksum verification failed: " + "; ".join(issues))
        staging.replace(destination)
    except Exception:
        # Preserve staging evidence for diagnosis; never publish a partial release.
        raise
    valid, issues = verify_release(destination)
    status = StageStatus.PASS if valid else StageStatus.FAIL
    result = StageResult(
        "release", status,
        f"Built and verified {destination}." if valid else "Published release verification failed.",
        metrics={"release_dir": str(destination), "checksum_valid": valid, "issues": issues},
    )
    db.record_stage(run_id, result)
    return result
