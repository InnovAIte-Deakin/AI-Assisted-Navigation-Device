"""Temporary-fixture tests for the read-only candidate YOLO dataset inspector."""

from __future__ import annotations

import base64
import json
import sys
from pathlib import Path

import pytest


ML_SIDE_DIR = Path(__file__).resolve().parents[1]
TOOLS_DIR = ML_SIDE_DIR / "tools"
sys.path.insert(0, str(TOOLS_DIR))

import inspect_candidate_dataset as inspector
import validate_dataset_manifest as manifest_validator


# A tiny valid GIF fixture encoded directly in the test.  Pillow identifies
# it from the content, while the .png fixture names exercise path handling.
IMAGE_BYTES = base64.b64decode(
    "R0lGODlhAQABAIAAAAAAAP///ywAAAAAAQABAAACAUwAOw=="
)


def write_yaml(root: Path, *, names: list[str], train: str = "train/images", val: str = "val/images", test: str | None = None, path: str = ".") -> Path:
    lines = [f"path: {path}", f"train: {train}", f"val: {val}"]
    if test is not None:
        lines.append(f"test: {test}")
    lines.append("names:")
    lines.extend(f"  {index}: {name}" for index, name in enumerate(names))
    yaml_path = root / "candidate.yaml"
    yaml_path.write_text("\n".join(lines) + "\n", encoding="utf-8")
    return yaml_path


def add_pair(
    root: Path,
    split: str,
    name: str,
    label: str = "0 0.5 0.5 0.2 0.2\n",
    image: bytes | None = None,
) -> tuple[Path, Path]:
    image_path = root / split / "images" / name
    label_path = root / split / "labels" / Path(name).with_suffix(".txt")
    image_path.parent.mkdir(parents=True, exist_ok=True)
    label_path.parent.mkdir(parents=True, exist_ok=True)
    image_path.write_bytes(IMAGE_BYTES + name.encode("utf-8") if image is None else image)
    label_path.write_text(label, encoding="utf-8")
    return image_path, label_path


def create_dataset(
    tmp_path: Path,
    *,
    names: list[str] | None = None,
    include_test: bool = False,
) -> tuple[Path, Path]:
    root = tmp_path / "dataset"
    root.mkdir()
    names = names or ["person"]
    add_pair(root, "train", "train.png")
    add_pair(root, "val", "validation.png")
    if include_test:
        add_pair(root, "test", "test.png")
    return root, write_yaml(root, names=names, test="test/images" if include_test else None)


def approved_metadata(names: list[str]) -> dict[str, object]:
    target_ids = {name: class_id for class_id, name in inspector.APPROVED_TAXONOMY}
    mappings = []
    unmapped = []
    for source_id, name in enumerate(names):
        if name in target_ids:
            mappings.append(
                {
                    "source_class_id": source_id,
                    "target_class_id": target_ids[name],
                    "target_class_name": name,
                    "mapping_rationale": "Fictional test-only explicit mapping.",
                }
            )
        else:
            unmapped.append(
                {"source_class_id": source_id, "reason": "Fictional test-only unresolved class."}
            )
    return {
        "dataset": {
            "id": "fictional-candidate-v1",
            "name": "Fictional candidate dataset",
            "source_version": "fictional-v1",
            "description": "Temporary test metadata only.",
            "release_date": "2026-08-05",
            "release_decision": "example_only",
        },
        "source_provenance": {
            "source_reference": "example://fictional/source",
            "accessed_on": "2026-08-05",
            "original_source": "Fictional test source.",
            "publisher": "Test publisher",
        },
        "licence": {
            "name": "Fictional test licence",
            "evidence_reference": "example://fictional/licence",
            "machine_learning_use_permitted": True,
            "modification_permitted": True,
            "redistribution_permitted": False,
            "attribution_required": True,
            "attribution_requirements": "Test attribution only.",
            "restrictions": "Fictional test metadata.",
            "reviewer": "Test reviewer",
            "review_date": "2026-08-05",
            "review_decision": "example_only",
        },
        "storage_release": {
            "authoritative_storage_reference": "example://fictional/storage",
            "git_safe_metadata_only": True,
            "release_version": "test-v1",
        },
        "quality_review_status": "example_only",
        "known_limitations": ["Fictional temporary test dataset."],
        "class_mapping": mappings,
        "excluded_source_classes": [],
        "unmapped_source_classes": unmapped,
    }


def write_json(path: Path, data: object) -> Path:
    path.write_text(json.dumps(data, indent=2), encoding="utf-8")
    return path


def group_map_for(root: Path) -> Path:
    groups = {
        path.relative_to(root).as_posix(): f"group-{index}"
        for index, path in enumerate(sorted(root.glob("*/images/**/*.png")), start=1)
    }
    return write_json(root / "groups.json", {"groups": groups})


def inspect(root: Path, yaml_path: Path, **kwargs: object) -> dict[str, object]:
    report, _ = inspector.inspect_dataset(root, yaml_path, execution_time_utc="2026-08-05T00:00:00Z", **kwargs)
    return report


def messages(report: dict[str, object]) -> str:
    return "\n".join(
        f"{item['location']}: {item['message']}" for item in report["validation_errors"]  # type: ignore[index]
    )


def test_valid_minimal_dataset_passes_with_explicit_mapping_and_groups(tmp_path: Path) -> None:
    root, yaml_path = create_dataset(tmp_path)
    metadata_path = write_json(root / "metadata.json", approved_metadata(["person"]))
    report = inspect(root, yaml_path, metadata_path=metadata_path, group_map_path=group_map_for(root))

    assert report["quality_verdict"] == "pass"
    assert report["totals"]["image_count"] == 2  # type: ignore[index]
    assert report["annotation_counts_by_walkbuddy_target_class"][0]["count"] == 2  # type: ignore[index]


def test_train_validation_and_test_splits_are_counted(tmp_path: Path) -> None:
    root, yaml_path = create_dataset(tmp_path, include_test=True)
    report = inspect(root, yaml_path, decode_images=False)

    assert [report["splits"][split]["image_count"] for split in ("train", "validation", "test")] == [1, 1, 1]  # type: ignore[index]


def test_validation_alias_is_supported(tmp_path: Path) -> None:
    root, yaml_path = create_dataset(tmp_path)
    yaml_path.write_text(
        yaml_path.read_text(encoding="utf-8").replace("val: val/images", "validation: val/images"),
        encoding="utf-8",
    )
    report = inspect(root, yaml_path, decode_images=False, checksums=False)

    assert report["splits"]["validation"]["image_count"] == 1  # type: ignore[index]


def test_missing_source_class_definitions_fail(tmp_path: Path) -> None:
    root, _ = create_dataset(tmp_path)
    yaml_path = root / "missing-names.yaml"
    yaml_path.write_text("path: .\ntrain: train/images\nval: val/images\n", encoding="utf-8")
    report = inspect(root, yaml_path, decode_images=False)

    assert "$.names" in messages(report)


def test_missing_image_label_is_reported(tmp_path: Path) -> None:
    root, yaml_path = create_dataset(tmp_path)
    (root / "train" / "labels" / "train.txt").unlink()
    report = inspect(root, yaml_path, decode_images=False)

    assert report["totals"]["images_without_labels"] == 1  # type: ignore[index]


def test_orphan_label_is_reported(tmp_path: Path) -> None:
    root, yaml_path = create_dataset(tmp_path)
    orphan = root / "train" / "labels" / "orphan.txt"
    orphan.write_text("0 0.5 0.5 0.2 0.2\n", encoding="utf-8")
    report = inspect(root, yaml_path, decode_images=False)

    assert "train/labels/orphan.txt" in report["splits"]["train"]["labels_without_images"]  # type: ignore[index]


def test_empty_label_is_reported(tmp_path: Path) -> None:
    root, yaml_path = create_dataset(tmp_path)
    (root / "train" / "labels" / "train.txt").write_text("\n", encoding="utf-8")
    report = inspect(root, yaml_path, decode_images=False)

    assert "train/labels/train.txt" in report["splits"]["train"]["empty_label_files"]  # type: ignore[index]


@pytest.mark.parametrize(
    ("label", "expected"),
    [
        ("0 0.5 0.5 0.2\n", "exactly 5 fields"),
        ("0 not-a-number 0.5 0.2 0.2\n", "must be numeric"),
        ("0 nan 0.5 0.2 0.2\n", "must be finite"),
        ("5 0.5 0.5 0.2 0.2\n", "outside the source YAML taxonomy"),
        ("0 0.5 0.5 0 0.2\n", "must be positive"),
        ("0 0.95 0.5 0.2 0.2\n", "outside normalized YOLO bounds"),
    ],
)
def test_invalid_yolo_rows_fail(tmp_path: Path, label: str, expected: str) -> None:
    root, yaml_path = create_dataset(tmp_path)
    (root / "train" / "labels" / "train.txt").write_text(label, encoding="utf-8")
    report = inspect(root, yaml_path, decode_images=False)

    assert report["quality_verdict"] == "fail"
    assert expected in messages(report)


def test_valid_boundary_box_passes(tmp_path: Path) -> None:
    root, yaml_path = create_dataset(tmp_path)
    (root / "train" / "labels" / "train.txt").write_text("0 0.5 0.5 1.0 1.0\n", encoding="utf-8")
    report = inspect(root, yaml_path, decode_images=False)

    assert "normalized YOLO bounds" not in messages(report)


def test_duplicate_image_checksums_are_reported(tmp_path: Path) -> None:
    root, yaml_path = create_dataset(tmp_path)
    add_pair(root, "train", "duplicate.png", image=(root / "train" / "images" / "train.png").read_bytes())
    report = inspect(root, yaml_path, decode_images=False)

    assert len(report["duplicates"]["duplicate_checksums"]) == 1  # type: ignore[index]


def test_duplicate_images_across_splits_fail(tmp_path: Path) -> None:
    root, yaml_path = create_dataset(tmp_path)
    (root / "val" / "images" / "validation.png").write_bytes((root / "train" / "images" / "train.png").read_bytes())
    report = inspect(root, yaml_path, decode_images=False)

    assert report["duplicates"]["cross_split_duplicate_images"]  # type: ignore[index]
    assert report["quality_verdict"] == "fail"


def test_configured_group_leakage_across_splits_fails(tmp_path: Path) -> None:
    root, yaml_path = create_dataset(tmp_path)
    groups = {
        "train/images/train.png": "same-sequence",
        "val/images/validation.png": "same-sequence",
    }
    report = inspect(root, yaml_path, group_map_path=write_json(root / "groups.json", {"groups": groups}), decode_images=False, checksums=False)

    assert report["duplicates"]["cross_split_group_leakage"]  # type: ignore[index]
    assert report["quality_verdict"] == "fail"


def test_no_unconfigured_grouping_assumption_is_made(tmp_path: Path) -> None:
    root, yaml_path = create_dataset(tmp_path)
    report = inspect(root, yaml_path, decode_images=False, checksums=False)

    assert report["duplicates"]["grouping_configured"] is False  # type: ignore[index]
    assert "filename similarity was not used" in "\n".join(item["message"] for item in report["warnings"])  # type: ignore[index]


def test_unknown_walkbuddy_mapping_target_fails(tmp_path: Path) -> None:
    root, yaml_path = create_dataset(tmp_path)
    metadata = approved_metadata(["person"])
    metadata["class_mapping"][0]["target_class_id"] = 99  # type: ignore[index]
    metadata["class_mapping"][0]["target_class_name"] = "unknown"  # type: ignore[index]
    report = inspect(root, yaml_path, metadata_path=write_json(root / "metadata.json", metadata), decode_images=False)

    assert "approved WalkBuddy target" in messages(report)


def test_excluded_source_classes_are_reported_but_not_mapped(tmp_path: Path) -> None:
    root, yaml_path = create_dataset(tmp_path, names=["person", "ceiling"])
    (root / "train" / "labels" / "train.txt").write_text("1 0.5 0.5 0.2 0.2\n", encoding="utf-8")
    metadata = approved_metadata(["person", "ceiling"])
    metadata["unmapped_source_classes"] = []
    metadata["excluded_source_classes"] = [{"source_class_id": 1, "reason": "Out of scope."}]
    report = inspect(root, yaml_path, metadata_path=write_json(root / "metadata.json", metadata), decode_images=False, checksums=False)

    assert report["mapping_summary"]["excluded_source_classes"][0]["source_class_name"] == "ceiling"  # type: ignore[index]
    assert report["annotation_counts_by_walkbuddy_target_class"][0]["count"] == 1  # type: ignore[index]


def test_unmapped_source_classes_are_reported(tmp_path: Path) -> None:
    root, yaml_path = create_dataset(tmp_path, names=["person", "unclear"])
    metadata = approved_metadata(["person", "unclear"])
    report = inspect(root, yaml_path, metadata_path=write_json(root / "metadata.json", metadata), decode_images=False, checksums=False)

    assert report["mapping_summary"]["unmapped_source_classes"][0]["source_class_name"] == "unclear"  # type: ignore[index]


@pytest.mark.parametrize("unsafe_path", ["../outside", r"C:\\outside", "/outside"])
def test_path_traversal_and_absolute_paths_fail(tmp_path: Path, unsafe_path: str) -> None:
    root, _ = create_dataset(tmp_path)
    yaml_path = write_yaml(root, names=["person"], train=unsafe_path)
    report = inspect(root, yaml_path, decode_images=False)

    assert report["quality_verdict"] == "fail"
    assert "path traversal" in messages(report) or "absolute" in messages(report)


def test_symlink_escape_fails_where_supported(tmp_path: Path) -> None:
    root, _ = create_dataset(tmp_path)
    outside = tmp_path / "outside"
    (outside / "images").mkdir(parents=True)
    link = root / "linked"
    try:
        link.symlink_to(outside, target_is_directory=True)
    except OSError:
        pytest.skip("The current platform does not allow test symlink creation.")
    yaml_path = write_yaml(root, names=["person"], train="linked/images")
    report = inspect(root, yaml_path, decode_images=False)

    assert "outside the supplied dataset root" in messages(report)


def test_individual_image_symlink_escape_fails_where_supported(tmp_path: Path) -> None:
    root, yaml_path = create_dataset(tmp_path)
    outside_image = tmp_path / "outside.png"
    outside_image.write_bytes(IMAGE_BYTES)
    link = root / "train" / "images" / "linked.png"
    try:
        link.symlink_to(outside_image)
    except OSError:
        pytest.skip("The current platform does not allow test symlink creation.")
    report = inspect(root, yaml_path, decode_images=False)

    assert "image symlink resolves outside" in messages(report)


def test_missing_split_directory_is_reported(tmp_path: Path) -> None:
    root, _ = create_dataset(tmp_path)
    yaml_path = write_yaml(root, names=["person"], train="missing/images")
    report = inspect(root, yaml_path, decode_images=False)

    assert "existing split directory" in messages(report)


def test_corrupt_image_and_unsupported_extension_are_reported(tmp_path: Path) -> None:
    root, yaml_path = create_dataset(tmp_path)
    (root / "train" / "images" / "corrupt.jpg").write_bytes(b"not an image")
    (root / "train" / "images" / "unsupported.gif").write_bytes(b"gif")
    report = inspect(root, yaml_path)

    assert "train/images/corrupt.jpg" in report["image_issues"]["unreadable_images"]  # type: ignore[index]
    assert "train/images/unsupported.gif" in report["splits"]["train"]["unsupported_image_files"]  # type: ignore[index]


def test_duplicate_filename_stem_is_reported(tmp_path: Path) -> None:
    root, yaml_path = create_dataset(tmp_path)
    add_pair(root, "train", "nested/train.png")
    report = inspect(root, yaml_path, decode_images=False, checksums=False)

    assert report["duplicates"]["duplicate_sample_identifiers"]  # type: ignore[index]


def test_deterministic_json_and_markdown_report_generation(tmp_path: Path) -> None:
    root, yaml_path = create_dataset(tmp_path)
    report = inspect(root, yaml_path, decode_images=False, checksums=False)
    first_output = tmp_path / "first-output"
    second_output = tmp_path / "second-output"
    inspector.write_outputs(report, None, first_output, root)
    inspector.write_outputs(report, None, second_output, root)

    assert (first_output / "dataset_quality_report.json").read_bytes() == (second_output / "dataset_quality_report.json").read_bytes()
    assert (first_output / "dataset_quality_report.md").read_text(encoding="utf-8").startswith("# Candidate dataset quality report")


def test_output_directory_inside_dataset_root_is_rejected(tmp_path: Path) -> None:
    root, yaml_path = create_dataset(tmp_path)
    report = inspect(root, yaml_path, decode_images=False, checksums=False)

    with pytest.raises(inspector.CandidateInspectionError, match="outside the supplied dataset root"):
        inspector.write_outputs(report, None, root / "reports", root)


def test_candidate_manifest_is_generated_and_passes_existing_validator(tmp_path: Path) -> None:
    root, yaml_path = create_dataset(tmp_path)
    metadata_path = write_json(root / "metadata.json", approved_metadata(["person"]))
    report, candidate = inspector.inspect_dataset(
        root,
        yaml_path,
        metadata_path=metadata_path,
        group_map_path=group_map_for(root),
        generate_manifest=True,
        execution_time_utc="2026-08-05T00:00:00Z",
    )

    assert report["candidate_manifest"]["generated"] is True  # type: ignore[index]
    assert candidate is not None
    assert manifest_validator.validate_manifest(candidate) == []


def test_candidate_manifest_output_is_written_only_when_valid(tmp_path: Path) -> None:
    root, yaml_path = create_dataset(tmp_path)
    metadata_path = write_json(root / "metadata.json", approved_metadata(["person"]))
    report, candidate = inspector.inspect_dataset(
        root,
        yaml_path,
        metadata_path=metadata_path,
        group_map_path=group_map_for(root),
        generate_manifest=True,
        execution_time_utc="2026-08-05T00:00:00Z",
    )
    output = tmp_path / "reports"
    inspector.write_outputs(report, candidate, output, root)

    written = json.loads((output / "candidate_manifest.json").read_text(encoding="utf-8"))
    assert manifest_validator.validate_manifest(written) == []


def test_candidate_manifest_is_withheld_when_metadata_is_incomplete(tmp_path: Path) -> None:
    root, yaml_path = create_dataset(tmp_path)
    report, candidate = inspector.inspect_dataset(
        root, yaml_path, generate_manifest=True, execution_time_utc="2026-08-05T00:00:00Z"
    )

    assert candidate is None
    assert "metadata file" in report["candidate_manifest"]["missing_requirements"]  # type: ignore[index]


def test_cli_valid_fixture_writes_both_reports(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    root, yaml_path = create_dataset(tmp_path)
    output = tmp_path / "reports"

    assert inspector.main(
        [
            "--dataset-root",
            str(root),
            "--dataset-yaml",
            str(yaml_path),
            "--output-dir",
            str(output),
            "--skip-image-decode",
            "--skip-checksums",
        ]
    ) == 0
    assert (output / "dataset_quality_report.json").is_file()
    assert (output / "dataset_quality_report.md").is_file()
    assert "pass_with_warnings" in capsys.readouterr().out


def test_cli_invalid_input_exits_nonzero_without_traceback(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    root, _ = create_dataset(tmp_path)
    missing_yaml = root / "missing.yaml"

    assert inspector.main(["--dataset-root", str(root), "--dataset-yaml", str(missing_yaml), "--output-dir", str(tmp_path / "output")]) == 1
    error = capsys.readouterr().err
    assert "Candidate dataset inspection failed" in error
    assert "Traceback" not in error


def test_cli_invalid_label_fixture_exits_nonzero_without_traceback(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    root, yaml_path = create_dataset(tmp_path)
    (root / "train" / "labels" / "train.txt").write_text("invalid\n", encoding="utf-8")

    assert inspector.main(
        [
            "--dataset-root",
            str(root),
            "--dataset-yaml",
            str(yaml_path),
            "--output-dir",
            str(tmp_path / "reports"),
            "--skip-image-decode",
            "--skip-checksums",
        ]
    ) == 1
    output = capsys.readouterr().out
    assert "Candidate dataset inspection verdict: fail" in output
    assert "Traceback" not in output


def test_cli_help_succeeds(capsys: pytest.CaptureFixture[str]) -> None:
    with pytest.raises(SystemExit) as exit_result:
        inspector.main(["--help"])

    assert exit_result.value.code == 0
    assert "--generate-manifest" in capsys.readouterr().out
