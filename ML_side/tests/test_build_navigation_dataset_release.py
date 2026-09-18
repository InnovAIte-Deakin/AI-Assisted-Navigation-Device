"""Temporary-fixture tests for controlled canonical YOLO release construction."""

from __future__ import annotations

import base64
import json
import shutil
import sys
from pathlib import Path, PurePosixPath

import pytest


ML_SIDE_DIR = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ML_SIDE_DIR / "tools"))
sys.path.insert(0, str(ML_SIDE_DIR / "training"))

import build_navigation_dataset_release as builder
import inspect_candidate_dataset as inspector
import train_navigation_model as training
import validate_dataset_manifest as manifest_validator


IMAGE_BYTES = base64.b64decode("R0lGODlhAQABAIAAAAAAAP///ywAAAAAAQABAAACAUwAOw==")
TARGETS = list(manifest_validator.APPROVED_TAXONOMY)


def write_json(path: Path, value: object) -> Path:
    path.write_text(json.dumps(value, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return path


def source_manifest(samples: dict[str, list[dict[str, object]]]) -> dict[str, object]:
    return {
        "schema_version": "1.0.0",
        "dataset": {"id": "fictional-source", "name": "Fictional source", "source_version": "fictional-v1", "description": "Temporary fixture only.", "release_date": "2026-08-05", "release_decision": "under_review"},
        "source_provenance": {"source_reference": "example://fictional/source", "accessed_on": "2026-08-05", "original_source": "Temporary fixture.", "publisher": "Test publisher"},
        "licence": {"name": "Fictional licence", "evidence_reference": "example://fictional/licence", "machine_learning_use_permitted": True, "modification_permitted": True, "redistribution_permitted": False, "attribution_required": True, "attribution_requirements": "Test only.", "restrictions": "Temporary fixture.", "reviewer": "Test reviewer", "review_date": "2026-08-05", "review_decision": "approved"},
        "taxonomy": {"target_classes": [{"id": class_id, "name": name} for class_id, name in TARGETS], "class_mappings": [{"source_class": "fictional-person", "target_class_id": 0, "target_class_name": "person", "mapping_rationale": "Fixture mapping.", "review_decision": "mapped"}], "excluded_source_classes": [{"source_class": "fictional-ceiling", "reason": "Fixture exclusion."}], "unmapped_source_classes": [], "bounding_box_coordinate_format": "normalized_xywh"},
        "splits": {split: {"samples": samples.get(split, [])} for split in ("train", "validation", "test")},
        "quality": {"image_count": sum(len(items) for items in samples.values()), "annotation_count": sum(item["annotation_summary"]["bounding_box_count"] for items in samples.values() for item in items), "duplicate_count": 0, "corrupt_file_count": 0, "invalid_annotation_count": 0, "excluded_sample_count": 0, "quality_review_status": "completed", "known_limitations": ["Fictional temporary fixture."]},
        "storage_release": {"authoritative_storage_reference": "example://fictional/storage", "git_safe_metadata_only": True, "release_version": "fictional-v1"},
    }


def mapping_config(*, policy: str = "retain_negative") -> dict[str, object]:
    return {
        "schema_version": "1.0.0", "source_taxonomy": [{"id": 0, "name": "fictional-person"}, {"id": 1, "name": "fictional-ceiling"}],
        "class_mapping": [{"source_class_id": 0, "target_class_id": 0, "target_class_name": "person", "mapping_rationale": "Explicit fixture decision."}],
        "excluded_source_classes": [{"source_class_id": 1, "reason": "Outside fixture target taxonomy."}], "unmapped_source_classes": [], "empty_image_policy": policy,
        "release_metadata": {
            "dataset": {"id": "fictional-release", "name": "Fictional canonical release", "source_version": "fictional-release-v1", "description": "Temporary fixture release only.", "release_date": "2026-08-05"},
            "source_provenance": {"source_reference": "example://fictional/source", "accessed_on": "2026-08-05", "original_source": "Temporary fixture.", "publisher": "Test publisher"},
            "licence": {"name": "Fictional licence", "evidence_reference": "example://fictional/licence", "machine_learning_use_permitted": True, "modification_permitted": True, "redistribution_permitted": False, "attribution_required": True, "attribution_requirements": "Test only.", "restrictions": "Temporary fixture.", "reviewer": "Test reviewer", "review_date": "2026-08-05", "review_decision": "approved"},
            "storage_release": {"authoritative_storage_reference": "example://fictional/release", "git_safe_metadata_only": True, "release_version": "overwritten"}, "quality_review_status": "not_reviewed", "known_limitations": ["Fictional test-only release."],
        },
    }


def fixture(tmp_path: Path, *, policy: str = "retain_negative", include_test: bool = False) -> dict[str, Path]:
    source_root = tmp_path / "source"
    source_root.mkdir(parents=True)
    records: dict[str, list[dict[str, object]]] = {"train": [], "validation": [], "test": []}
    examples = [("train", "mapped.png", "0 0.5 0.5 0.2 0.2\n1 0.5 0.5 0.2 0.2\n"), ("train", "excluded.png", "1 0.5 0.5 0.2 0.2\n"), ("validation", "validation.png", "0 0.5 0.5 0.2 0.2\n")]
    if include_test:
        examples.append(("test", "test.png", "0 0.5 0.5 0.2 0.2\n"))
    for index, (split, image_name, label) in enumerate(examples, start=1):
        image = source_root / split / "images" / image_name
        label_path = source_root / split / "labels" / Path(image_name).with_suffix(".txt")
        image.parent.mkdir(parents=True, exist_ok=True)
        label_path.parent.mkdir(parents=True, exist_ok=True)
        image.write_bytes(IMAGE_BYTES + image_name.encode("utf-8"))
        label_path.write_text(label, encoding="utf-8")
        records[split].append({"sample_id": f"fixture-{split}-{index}", "image_path": image.relative_to(source_root).as_posix(), "label_path": label_path.relative_to(source_root).as_posix(), "group_id": f"fixture-group-{split}-{index}", "labelled": True, "annotation_summary": {"bounding_box_count": len([line for line in label.splitlines() if line]), "class_ids": [int(line.split()[0]) for line in label.splitlines() if line]}})
    source_yaml = source_root / "dataset.yaml"
    source_yaml.write_text("path: .\ntrain: train/images\nval: validation/images\n" + ("test: test/images\n" if include_test else "") + "names:\n  0: fictional-person\n  1: fictional-ceiling\n", encoding="utf-8")
    manifest_path = write_json(tmp_path / "source_manifest.json", source_manifest(records))
    report_path = write_json(tmp_path / "inspection.json", {"dataset_identity": "fictional-source", "dataset_source_version": "fictional-v1", "source_taxonomy": [{"id": 0, "name": "fictional-person"}, {"id": 1, "name": "fictional-ceiling"}], "quality_verdict": "pass", "validation_errors": [], "duplicates": {"cross_split_duplicate_images": [], "cross_split_group_leakage": []}})
    mapping_path = write_json(tmp_path / "mapping.json", mapping_config(policy=policy))
    return {"source": source_root, "yaml": source_yaml, "manifest": manifest_path, "report": report_path, "mapping": mapping_path, "output": tmp_path / "releases"}


def plan(paths: dict[str, Path], **kwargs: object) -> builder.ReleasePlan:
    return builder.create_release_plan(source_root=paths["source"], source_yaml_path=paths["yaml"], source_manifest_path=paths["manifest"], inspection_report_path=paths["report"], mapping_path=paths["mapping"], output_root=paths["output"], release_name="fictional-release", release_version="v1", **kwargs)


def test_valid_dry_run_succeeds_and_creates_no_output(tmp_path: Path) -> None:
    paths = fixture(tmp_path)
    result = builder.dry_run(plan(paths))

    assert result["status"] == "planned"
    assert not paths["output"].exists()
    assert "dataset.yaml" in result["intended_output_files"]  # type: ignore[operator]


def test_confirmed_build_rewrites_to_exact_canonical_ids_and_keeps_source_unchanged(tmp_path: Path) -> None:
    paths = fixture(tmp_path)
    source_hash = builder._sha256(paths["source"] / "train" / "labels" / "mapped.txt")
    source_image_hash = builder._sha256(paths["source"] / "train" / "images" / "mapped.png")
    result = builder.build_release(plan(paths), confirm_build=True)
    release = paths["output"] / "fictional-release" / "v1"

    assert result["status"] == "completed"
    assert (release / "labels/train/mapped.txt").read_text(encoding="utf-8") == "0 0.5 0.5 0.2 0.2\n"
    assert builder._sha256(paths["source"] / "train" / "labels" / "mapped.txt") == source_hash
    assert builder._sha256(paths["source"] / "train" / "images" / "mapped.png") == source_image_hash
    generated = json.loads((release / "release_manifest.json").read_text(encoding="utf-8"))
    assert generated["taxonomy"]["target_classes"] == [{"id": class_id, "name": name} for class_id, name in TARGETS]
    assert generated["dataset"]["release_decision"] == "under_review"


def test_excluded_annotations_and_retained_negative_policy_are_reported(tmp_path: Path) -> None:
    paths = fixture(tmp_path, policy="retain_negative")
    report = builder.build_release(plan(paths), confirm_build=True)
    release = paths["output"] / "fictional-release" / "v1"

    assert (release / "labels/train/excluded.txt").read_text(encoding="utf-8") == ""
    assert report["counts"]["retained_negative_images"] == 1  # type: ignore[index]
    assert report["counts"]["exclusion_created_negative_images"] == 1  # type: ignore[index]
    assert report["counts"]["source_empty_negative_images"] == 0  # type: ignore[index]
    assert report["counts"]["excluded_annotations_by_source_class"] == [{"id": 1, "name": "fictional-ceiling", "count": 2}]  # type: ignore[index]


def test_exclude_empty_image_policy_removes_images_and_labels(tmp_path: Path) -> None:
    paths = fixture(tmp_path, policy="exclude_image")
    release_plan = plan(paths)

    assert {sample.sample_id for sample in release_plan.samples} == {"fixture-train-1", "fixture-validation-3"}
    builder.build_release(release_plan, confirm_build=True)
    release = paths["output"] / "fictional-release" / "v1"
    assert not (release / "images/train/excluded.png").exists()
    assert json.loads((release / "release_manifest.json").read_text(encoding="utf-8"))["quality"]["excluded_sample_count"] == 1


def test_original_empty_negative_is_retained_separately_from_exclusion_created_negative(tmp_path: Path) -> None:
    paths = fixture(tmp_path, policy="exclude_image")
    (paths["source"] / "validation/labels/validation.txt").write_text("\n", encoding="utf-8")

    report = builder.build_release(plan(paths), confirm_build=True)
    release = paths["output"] / "fictional-release" / "v1"

    assert (release / "images/val/validation.png").is_file()
    assert (release / "labels/val/validation.txt").read_text(encoding="utf-8") == ""
    assert report["counts"]["source_empty_negative_images"] == 1  # type: ignore[index]
    assert report["counts"]["exclusion_created_negative_images"] == 0  # type: ignore[index]


@pytest.mark.parametrize("change, expected", [
    (lambda mapping: mapping["unmapped_source_classes"].append({"source_class_id": 1, "reason": "Needs review."}), "duplicate or ambiguous"),
    (lambda mapping: mapping["class_mapping"].append({"source_class_id": 1, "target_class_id": 99, "target_class_name": "unknown", "mapping_rationale": "Bad."}), "approved target"),
    (lambda mapping: mapping["class_mapping"].append({"source_class_id": 0, "target_class_id": 0, "target_class_name": "person", "mapping_rationale": "Duplicate."}), "duplicate or ambiguous"),
])
def test_unresolved_unknown_target_and_duplicate_source_decisions_fail(tmp_path: Path, change: object, expected: str) -> None:
    paths = fixture(tmp_path)
    mapping = json.loads(paths["mapping"].read_text(encoding="utf-8"))
    change(mapping)  # type: ignore[operator]
    write_json(paths["mapping"], mapping)

    with pytest.raises(builder.DatasetReleaseError, match=expected):
        plan(paths)


def test_unknown_source_annotation_and_malformed_label_fail(tmp_path: Path) -> None:
    paths = fixture(tmp_path)
    label = paths["source"] / "train" / "labels" / "mapped.txt"
    label.write_text("2 0.5 0.5 0.2 0.2\n", encoding="utf-8")
    with pytest.raises(builder.DatasetReleaseError, match="unknown source"):
        plan(paths)
    label.write_text("0 0.5 0.5 0.2\n", encoding="utf-8")
    with pytest.raises(builder.DatasetReleaseError, match="five YOLO fields"):
        plan(paths)


def test_invalid_manifest_unapproved_licence_and_failing_inspection_block(tmp_path: Path) -> None:
    paths = fixture(tmp_path)
    manifest = json.loads(paths["manifest"].read_text(encoding="utf-8"))
    manifest["licence"]["review_decision"] = "conditional"
    write_json(paths["manifest"], manifest)
    with pytest.raises(builder.DatasetReleaseError, match="approved licence"):
        plan(paths)
    manifest["licence"]["review_decision"] = "approved"
    manifest["dataset"].pop("name")
    write_json(paths["manifest"], manifest)
    with pytest.raises(builder.DatasetReleaseError, match="source manifest is invalid"):
        plan(paths)
    paths = fixture(tmp_path / "second")
    report = json.loads(paths["report"].read_text(encoding="utf-8"))
    report["quality_verdict"] = "fail"
    write_json(paths["report"], report)
    with pytest.raises(builder.DatasetReleaseError, match="failing quality"):
        plan(paths)


def test_inspection_identity_version_taxonomy_and_leakage_mismatches_fail(tmp_path: Path) -> None:
    paths = fixture(tmp_path)
    report = json.loads(paths["report"].read_text(encoding="utf-8"))
    report["dataset_identity"] = "different"
    write_json(paths["report"], report)
    with pytest.raises(builder.DatasetReleaseError, match="identity"):
        plan(paths)
    report["dataset_identity"] = "fictional-source"
    report["dataset_source_version"] = "different"
    write_json(paths["report"], report)
    with pytest.raises(builder.DatasetReleaseError, match="source version"):
        plan(paths)
    report["dataset_source_version"] = "fictional-v1"
    report["duplicates"]["cross_split_duplicate_images"] = [{"fixture": "duplicate"}]
    write_json(paths["report"], report)
    with pytest.raises(builder.DatasetReleaseError, match="split leakage"):
        plan(paths)
    paths = fixture(tmp_path / "taxonomy")
    mapping = json.loads(paths["mapping"].read_text(encoding="utf-8"))
    mapping["source_taxonomy"][0]["name"] = "different"
    write_json(paths["mapping"], mapping)
    with pytest.raises(builder.DatasetReleaseError, match="does not exactly match"):
        plan(paths)


def test_missing_new_inspection_identity_fields_require_regeneration(tmp_path: Path) -> None:
    paths = fixture(tmp_path)
    report = json.loads(paths["report"].read_text(encoding="utf-8"))
    report.pop("dataset_source_version")
    write_json(paths["report"], report)
    with pytest.raises(builder.DatasetReleaseError, match="regenerate"):
        plan(paths)


def test_inspection_report_taxonomy_mismatch_requires_regeneration(tmp_path: Path) -> None:
    paths = fixture(tmp_path)
    report = json.loads(paths["report"].read_text(encoding="utf-8"))
    report["source_taxonomy"][1]["name"] = "different"
    write_json(paths["report"], report)
    with pytest.raises(builder.DatasetReleaseError, match="source taxonomy"):
        plan(paths)


@pytest.mark.parametrize("unsafe", ["../outside.png", r"C:\\outside.png", r"\\server\\share\\file.png", "..%2foutside.png"])
def test_manifest_path_traversal_absolute_unc_and_encoded_paths_fail(tmp_path: Path, unsafe: str) -> None:
    paths = fixture(tmp_path)
    manifest = json.loads(paths["manifest"].read_text(encoding="utf-8"))
    manifest["splits"]["train"]["samples"][0]["image_path"] = unsafe
    write_json(paths["manifest"], manifest)

    with pytest.raises(builder.DatasetReleaseError):
        plan(paths)


def test_missing_files_same_stem_collision_and_output_overlap_fail(tmp_path: Path) -> None:
    paths = fixture(tmp_path)
    (paths["source"] / "train" / "labels" / "mapped.txt").unlink()
    with pytest.raises(builder.DatasetReleaseError, match="source manifest is invalid"):
        plan(paths)
    paths = fixture(tmp_path / "collision")
    manifest = json.loads(paths["manifest"].read_text(encoding="utf-8"))
    duplicate = dict(manifest["splits"]["train"]["samples"][0])
    duplicate["sample_id"] = "different-id"
    duplicate["image_path"] = "train/images/mapped.jpg"
    duplicate["label_path"] = "train/labels/mapped-duplicate.txt"
    source_image = paths["source"] / duplicate["image_path"]
    source_label = paths["source"] / duplicate["label_path"]
    source_image.parent.mkdir(parents=True, exist_ok=True)
    source_label.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy2(paths["source"] / "train/images/mapped.png", source_image)
    shutil.copy2(paths["source"] / "train/labels/mapped.txt", source_label)
    manifest["splits"]["train"]["samples"].append(duplicate)
    manifest["quality"]["image_count"] += 1
    manifest["quality"]["annotation_count"] += 2
    write_json(paths["manifest"], manifest)
    with pytest.raises(builder.DatasetReleaseError, match="same-stem"):
        plan(paths)
    paths = fixture(tmp_path / "overlap")
    with pytest.raises(builder.DatasetReleaseError, match="output root"):
        builder.create_release_plan(source_root=paths["source"], source_yaml_path=paths["yaml"], source_manifest_path=paths["manifest"], inspection_report_path=paths["report"], mapping_path=paths["mapping"], output_root=paths["source"] / "releases", release_name="fictional-release", release_version="v1")


def test_existing_release_is_protected_and_staging_is_removed_after_failure(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    paths = fixture(tmp_path)
    planned = plan(paths)
    planned.release_root.mkdir(parents=True)
    with pytest.raises(builder.DatasetReleaseError, match="protected"):
        builder.build_release(planned, confirm_build=True)
    shutil.rmtree(planned.release_root)
    monkeypatch.setattr(builder.shutil, "copy2", lambda *_: (_ for _ in ()).throw(OSError("fixture copy failure")))
    with pytest.raises(OSError, match="fixture copy failure"):
        builder.build_release(plan(paths), confirm_build=True)
    assert not list((paths["output"] / "fictional-release").glob(".*.staging-*"))
    assert not (paths["output"] / "fictional-release" / "v1").exists()


def test_deterministic_outputs_checksums_and_optional_test_split(tmp_path: Path) -> None:
    paths = fixture(tmp_path / "one", include_test=True)
    first = builder.build_release(plan(paths), confirm_build=True)
    second_paths = fixture(tmp_path / "two", include_test=True)
    second = builder.build_release(plan(second_paths), confirm_build=True)
    first_root = paths["output"] / "fictional-release" / "v1"
    second_root = second_paths["output"] / "fictional-release" / "v1"

    assert first["release"]["identity_sha256"] == second["release"]["identity_sha256"]  # type: ignore[index]
    for relative in ("dataset.yaml", "release_manifest.json", "release_checksums.json", "labels/train/mapped.txt"):
        assert (first_root / relative).read_bytes() == (second_root / relative).read_bytes()
    assert "test: images/test" in (first_root / "dataset.yaml").read_text(encoding="utf-8")
    assert "nc: 8" in (first_root / "dataset.yaml").read_text(encoding="utf-8")


def test_generated_release_passes_validator_and_existing_inspector(tmp_path: Path) -> None:
    paths = fixture(tmp_path)
    builder.build_release(plan(paths), confirm_build=True)
    release = paths["output"] / "fictional-release" / "v1"
    manifest = json.loads((release / "release_manifest.json").read_text(encoding="utf-8"))
    metadata = write_json(tmp_path / "canonical-metadata.json", builder._inspection_metadata())
    groups = write_json(tmp_path / "groups.json", {"groups": {sample["image_path"]: sample["group_id"] for split in manifest["splits"].values() for sample in split["samples"]}})

    assert not manifest_validator.validate_manifest(manifest, dataset_root=release, check_files=True)
    report, _ = inspector.inspect_dataset(release, release / "dataset.yaml", metadata_path=metadata, group_map_path=groups)
    assert report["quality_verdict"] != "fail"


def test_training_dry_run_is_compatible_after_explicit_reviewed_promotion(tmp_path: Path) -> None:
    paths = fixture(tmp_path)
    builder.build_release(plan(paths), confirm_build=True)
    release = paths["output"] / "fictional-release" / "v1"
    repository = tmp_path / "repository"
    repository.mkdir()
    manifest = json.loads((release / "release_manifest.json").read_text(encoding="utf-8"))
    manifest["dataset"]["release_decision"] = "approved_for_training"
    write_json(repository / "manifest.json", manifest)
    shutil.rmtree(paths["source"])
    (repository / "architecture.yaml").write_text("nc: 8\n", encoding="utf-8")
    config = {"schema_version": "1.0.0", "experiment_name": "Release builder test", "dataset": {"manifest_path": "manifest.json", "yaml_path": "dataset.yaml", "inspection_report_path": None, "stage": "approved_for_internal_training"}, "model": {"architecture_path": "architecture.yaml", "initial_weights_path": None}, "training": {"epochs": 1, "image_size": 32, "batch_size": 1, "device": "cpu", "workers": 1, "seed": 1, "optimizer": "AdamW", "learning_rate": 0.001, "confidence": 0.001, "iou": 0.7, "deterministic": True, "resume_behavior": "never"}, "output": {"root": "artifacts"}, "notes": "Temporary test configuration."}
    config_path = write_json(repository / "training.json", config)

    assert training.dry_run(training.load_training_plan(config_path, dataset_root_override=release, repository_root=repository))["status"] == "dry_run_valid"


def test_group_leakage_and_actual_cross_split_checksum_leakage_block(tmp_path: Path) -> None:
    paths = fixture(tmp_path)
    report = json.loads(paths["report"].read_text(encoding="utf-8"))
    report["duplicates"]["cross_split_group_leakage"] = [{"group_id": "shared"}]
    write_json(paths["report"], report)
    with pytest.raises(builder.DatasetReleaseError, match="group_leakage"):
        plan(paths)
    paths = fixture(tmp_path / "checksum")
    (paths["source"] / "validation/images/validation.png").write_bytes(
        (paths["source"] / "train/images/mapped.png").read_bytes()
    )
    with pytest.raises(builder.DatasetReleaseError, match="checksums reveal duplicate"):
        plan(paths)


def test_source_image_missing_or_orphan_label_blocks_release(tmp_path: Path) -> None:
    paths = fixture(tmp_path)
    (paths["source"] / "validation/images/validation.png").unlink()
    with pytest.raises(builder.DatasetReleaseError, match="source manifest is invalid"):
        plan(paths)
    paths = fixture(tmp_path / "orphan")
    orphan = paths["source"] / "train/labels/orphan.txt"
    orphan.write_text("0 0.5 0.5 0.2 0.2\n", encoding="utf-8")
    with pytest.raises(builder.DatasetReleaseError, match="orphan labels"):
        plan(paths)


@pytest.mark.parametrize("unsafe", ["../outside/images", r"C:\\outside\\images", r"\\server\\share\\images", "..%2foutside/images"])
def test_source_yaml_path_escape_forms_block_release(tmp_path: Path, unsafe: str) -> None:
    paths = fixture(tmp_path)
    paths["yaml"].write_text(f"path: .\ntrain: {unsafe}\nval: validation/images\nnames:\n  0: fictional-person\n  1: fictional-ceiling\n", encoding="utf-8")
    with pytest.raises(builder.DatasetReleaseError, match="source dataset YAML"):
        plan(paths)


def test_source_root_inside_output_root_blocks_release(tmp_path: Path) -> None:
    paths = fixture(tmp_path)
    with pytest.raises(builder.DatasetReleaseError, match="source dataset root"):
        builder.create_release_plan(source_root=paths["source"], source_yaml_path=paths["yaml"], source_manifest_path=paths["manifest"], inspection_report_path=paths["report"], mapping_path=paths["mapping"], output_root=tmp_path, release_name="fictional-release", release_version="v1")


@pytest.mark.parametrize("unsafe", [r"\\server\share", r"C:drive-relative", "file:///controlled/source", "https://example.invalid/source"])
def test_nonlocal_cli_input_forms_are_rejected(tmp_path: Path, unsafe: str) -> None:
    paths = fixture(tmp_path)
    with pytest.raises(builder.DatasetReleaseError, match="controlled local filesystem path"):
        builder.create_release_plan(source_root=paths["source"], source_yaml_path=paths["yaml"], source_manifest_path=paths["manifest"], inspection_report_path=paths["report"], mapping_path=paths["mapping"], output_root=Path(unsafe), release_name="fictional-release", release_version="v1")


@pytest.mark.parametrize("unsafe", ["http://example.invalid/source", "https://example.invalid/source", "file://controlled/source"])
def test_posix_normalised_uri_inputs_are_rejected_before_filesystem_resolution(unsafe: str) -> None:
    posix_value = PurePosixPath(unsafe)
    assert str(posix_value).startswith(unsafe.split(":", 1)[0] + ":/")

    with pytest.raises(builder.DatasetReleaseError, match="controlled local filesystem path"):
        builder._reject_nonlocal_path(posix_value, "output root")


def test_repository_output_root_and_wrong_mapping_schema_version_are_rejected(tmp_path: Path) -> None:
    paths = fixture(tmp_path)
    with pytest.raises(builder.DatasetReleaseError, match="outside the repository"):
        builder.create_release_plan(source_root=paths["source"], source_yaml_path=paths["yaml"], source_manifest_path=paths["manifest"], inspection_report_path=paths["report"], mapping_path=paths["mapping"], output_root=builder.REPOSITORY_ROOT / "generated-release", release_name="fictional-release", release_version="v1")
    mapping = json.loads(paths["mapping"].read_text(encoding="utf-8"))
    mapping["schema_version"] = "other"
    write_json(paths["mapping"], mapping)
    with pytest.raises(builder.DatasetReleaseError, match="schema_version"):
        plan(paths)


def test_symlink_escape_blocks_release_where_supported(tmp_path: Path) -> None:
    paths = fixture(tmp_path)
    outside = tmp_path / "outside.png"
    outside.write_bytes(IMAGE_BYTES)
    link = paths["source"] / "train/images/mapped.png"
    link.unlink()
    try:
        link.symlink_to(outside)
    except (NotImplementedError, OSError):
        pytest.skip("Symlink creation is unavailable in this environment.")
    with pytest.raises(builder.DatasetReleaseError):
        plan(paths)


@pytest.mark.parametrize("mutation, expected", [
    (lambda mapping: mapping["class_mapping"].pop(), "no explicit decision"),
    (lambda mapping: mapping["class_mapping"].append({"source_class_id": 4, "target_class_id": 0, "target_class_name": "person", "mapping_rationale": "Unknown source."}), "unknown source"),
    (lambda mapping: mapping["release_metadata"]["dataset"].pop("name"), "cannot produce a valid manifest"),
])
def test_mapping_completeness_unknown_source_and_invalid_release_metadata_block(tmp_path: Path, mutation: object, expected: str) -> None:
    paths = fixture(tmp_path)
    mapping = json.loads(paths["mapping"].read_text(encoding="utf-8"))
    mutation(mapping)  # type: ignore[operator]
    write_json(paths["mapping"], mapping)
    with pytest.raises(builder.DatasetReleaseError, match=expected):
        plan(paths)


@pytest.mark.parametrize("target, field", [
    ("mapping", "unexpected"),
    ("source_taxonomy", "unexpected"),
    ("class_mapping", "unexpected"),
])
def test_unknown_mapping_configuration_fields_and_whitespace_taxonomy_fail(tmp_path: Path, target: str, field: str) -> None:
    paths = fixture(tmp_path)
    mapping = json.loads(paths["mapping"].read_text(encoding="utf-8"))
    if target == "mapping":
        mapping[field] = True
    else:
        mapping[target][0][field] = True
    write_json(paths["mapping"], mapping)
    with pytest.raises(builder.DatasetReleaseError, match="unsupported field"):
        plan(paths)
    paths = fixture(tmp_path / "whitespace")
    paths["yaml"].write_text("path: .\ntrain: train/images\nval: validation/images\nnames:\n  0: 'fictional-person '\n  1: fictional-ceiling\n", encoding="utf-8")
    with pytest.raises(builder.DatasetReleaseError, match="surrounding whitespace"):
        plan(paths)


def test_mapping_source_taxonomy_reordering_is_rejected(tmp_path: Path) -> None:
    paths = fixture(tmp_path)
    mapping = json.loads(paths["mapping"].read_text(encoding="utf-8"))
    mapping["source_taxonomy"].reverse()
    write_json(paths["mapping"], mapping)
    with pytest.raises(builder.DatasetReleaseError, match="exact ID order"):
        plan(paths)


def test_source_yaml_declared_class_count_must_match_named_taxonomy(tmp_path: Path) -> None:
    paths = fixture(tmp_path)
    paths["yaml"].write_text("path: .\ntrain: train/images\nval: validation/images\nnc: 3\nnames:\n  0: fictional-person\n  1: fictional-ceiling\n", encoding="utf-8")
    with pytest.raises(builder.DatasetReleaseError, match="nc"):
        plan(paths)


def test_explicit_reviewed_training_status_is_preserved_without_invention(tmp_path: Path) -> None:
    paths = fixture(tmp_path)
    mapping = json.loads(paths["mapping"].read_text(encoding="utf-8"))
    mapping["release_metadata"]["dataset"]["release_decision"] = "approved_for_training"
    mapping["release_metadata"]["quality_review_status"] = "completed"
    write_json(paths["mapping"], mapping)

    assert builder._release_manifest(plan(paths))["dataset"]["release_decision"] == "approved_for_training"  # type: ignore[index]


def test_approved_training_status_requires_explicit_licence_and_completed_quality_review(tmp_path: Path) -> None:
    paths = fixture(tmp_path)
    mapping = json.loads(paths["mapping"].read_text(encoding="utf-8"))
    mapping["release_metadata"]["dataset"]["release_decision"] = "approved_for_training"
    write_json(paths["mapping"], mapping)
    with pytest.raises(builder.DatasetReleaseError, match="quality review"):
        plan(paths)
    mapping["release_metadata"]["quality_review_status"] = "completed"
    mapping["release_metadata"]["licence"]["review_decision"] = "conditional"
    write_json(paths["mapping"], mapping)
    with pytest.raises(builder.DatasetReleaseError, match="licence review"):
        plan(paths)


def test_stale_manifest_checksum_metadata_is_not_reused(tmp_path: Path) -> None:
    paths = fixture(tmp_path)
    mapping = json.loads(paths["mapping"].read_text(encoding="utf-8"))
    mapping["release_metadata"]["storage_release"]["manifest_checksum"] = "sha256:" + "0" * 64
    write_json(paths["mapping"], mapping)

    assert "manifest_checksum" not in builder._release_manifest(plan(paths))["storage_release"]  # type: ignore[operator]


@pytest.mark.parametrize("label_text, expected", [
    ("0 0.5 0.5 0 0.2\n", "out-of-bounds"),
    ("0 nan 0.5 0.2 0.2\n", "non-finite"),
    ("0 0.95 0.5 0.2 0.2\n", "out-of-bounds"),
])
def test_invalid_yolo_coordinate_forms_block_release(tmp_path: Path, label_text: str, expected: str) -> None:
    paths = fixture(tmp_path)
    (paths["source"] / "train/labels/mapped.txt").write_text(label_text, encoding="utf-8")
    with pytest.raises(builder.DatasetReleaseError, match=expected):
        plan(paths)


def test_bom_crlf_blank_lines_and_duplicate_detection_rows_are_preserved_deterministically(tmp_path: Path) -> None:
    paths = fixture(tmp_path)
    label_text = "\ufeff0 0.500000 0.5 0.2 0.2\r\n\r\n0 0.250000 0.5 0.2 0.2\r\n"
    (paths["source"] / "train/labels/mapped.txt").write_text(label_text, encoding="utf-8")

    builder.build_release(plan(paths), confirm_build=True)

    output = (paths["output"] / "fictional-release" / "v1/labels/train/mapped.txt").read_text(encoding="utf-8")
    assert output == "0 0.500000 0.5 0.2 0.2\n0 0.250000 0.5 0.2 0.2\n"


def test_interrupt_is_not_reported_as_validation_error_and_cleans_staging(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    paths = fixture(tmp_path)
    source_image = paths["source"] / "train/images/mapped.png"
    source_label = paths["source"] / "train/labels/mapped.txt"
    source_hashes = (builder._sha256(source_image), builder._sha256(source_label))
    monkeypatch.setattr(builder.shutil, "copy2", lambda *_: (_ for _ in ()).throw(KeyboardInterrupt()))
    with pytest.raises(KeyboardInterrupt):
        builder.build_release(plan(paths), confirm_build=True)
    assert not list((paths["output"] / "fictional-release").glob(".*.staging-*"))
    assert (builder._sha256(source_image), builder._sha256(source_label)) == source_hashes


def test_deterministic_machine_and_human_reports_and_checksum_records(tmp_path: Path) -> None:
    paths = fixture(tmp_path / "one")
    builder.build_release(plan(paths), confirm_build=True)
    second_paths = fixture(tmp_path / "two")
    builder.build_release(plan(second_paths), confirm_build=True)
    first_root = paths["output"] / "fictional-release" / "v1"
    second_root = second_paths["output"] / "fictional-release" / "v1"
    for relative in ("release_build_report.json", "release_build_report.md", "release_checksums.json"):
        assert (first_root / relative).read_bytes() == (second_root / relative).read_bytes()
    checksums = json.loads((first_root / "release_checksums.json").read_text(encoding="utf-8"))
    assert checksums["files"]["dataset.yaml"] == builder._sha256(first_root / "dataset.yaml")
    markdown = (first_root / "release_build_report.md").read_text(encoding="utf-8")
    assert "Source annotations" in markdown
    assert "Input `source_manifest_sha256`" in markdown
    assert "No failures." in markdown
    assert not list(first_root.glob(".release_*"))


def test_cli_fictional_dry_run_and_confirmed_build_succeed(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    paths = fixture(tmp_path)
    arguments = ["--source-root", str(paths["source"]), "--source-yaml", str(paths["yaml"]), "--source-manifest", str(paths["manifest"]), "--inspection-report", str(paths["report"]), "--mapping-config", str(paths["mapping"]), "--output-root", str(paths["output"]), "--release-name", "fictional-release", "--release-version", "v1"]

    assert builder.main([*arguments, "--dry-run"]) == 0
    assert '"status": "planned"' in capsys.readouterr().out
    assert not paths["output"].exists()
    assert builder.main([*arguments, "--confirm-build"]) == 0
    assert '"status": "completed"' in capsys.readouterr().out
    assert (paths["output"] / "fictional-release" / "v1" / "release_manifest.json").is_file()


def test_cli_help_confirmation_conflict_and_ordinary_errors_are_controlled(tmp_path: Path, capsys: pytest.CaptureFixture[str], monkeypatch: pytest.MonkeyPatch) -> None:
    with pytest.raises(SystemExit) as result:
        builder.main(["--help"])
    assert result.value.code == 0
    paths = fixture(tmp_path)
    arguments = ["--source-root", str(paths["source"]), "--source-yaml", str(paths["yaml"]), "--source-manifest", str(paths["manifest"]), "--inspection-report", str(paths["report"]), "--mapping-config", str(paths["mapping"]), "--output-root", str(paths["output"]), "--release-name", "fictional-release", "--release-version", "v1"]
    assert builder.main([*arguments, "--dry-run", "--confirm-build"]) == 1
    assert "Traceback" not in capsys.readouterr().err
    assert builder.main(arguments) == 1
    assert "requires --confirm-build" in capsys.readouterr().err
    monkeypatch.setattr(builder, "create_release_plan", lambda **_: (_ for _ in ()).throw(KeyboardInterrupt()))
    with pytest.raises(KeyboardInterrupt):
        builder.main(arguments + ["--dry-run"])
