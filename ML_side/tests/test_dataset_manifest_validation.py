"""Tests for the Git-safe WalkBuddy navigation dataset manifest validator."""

from __future__ import annotations

import copy
import json
import sys
from pathlib import Path

import pytest


ML_SIDE_DIR = Path(__file__).resolve().parents[1]
TOOLS_DIR = ML_SIDE_DIR / "tools"
SAMPLE_MANIFEST_PATH = ML_SIDE_DIR / "datasets" / "sample_manifest.json"
sys.path.insert(0, str(TOOLS_DIR))

import validate_dataset_manifest as validator


def sample_manifest() -> dict[str, object]:
    return json.loads(SAMPLE_MANIFEST_PATH.read_text(encoding="utf-8"))


def validation_messages(
    manifest: dict[str, object], *, dataset_root: Path | None = None, check_files: bool = False
) -> list[str]:
    return [
        f"{issue.location}: {issue.message}"
        for issue in validator.validate_manifest(
            manifest, dataset_root=dataset_root, check_files=check_files
        )
    ]


def first_sample(manifest: dict[str, object], split: str = "train") -> dict[str, object]:
    return manifest["splits"][split]["samples"][0]  # type: ignore[index]


def write_manifest(tmp_path: Path, manifest: dict[str, object]) -> Path:
    path = tmp_path / "manifest.json"
    path.write_text(json.dumps(manifest), encoding="utf-8")
    return path


def test_sample_manifest_passes_without_dataset_file_checks() -> None:
    assert validation_messages(sample_manifest()) == []


def test_schema_guard_rejects_an_unsupported_keyword() -> None:
    with pytest.raises(validator.ManifestValidationError, match="Unsupported schema keyword"):
        validator._ensure_supported_schema_keywords({"format": "date"})


def test_missing_required_field_fails() -> None:
    manifest = sample_manifest()
    del manifest["dataset"]["description"]  # type: ignore[index]

    assert "missing required field 'description'" in "\n".join(validation_messages(manifest))


def test_missing_licence_evidence_fails() -> None:
    manifest = sample_manifest()
    manifest["licence"]["evidence_reference"] = ""  # type: ignore[index]

    assert "evidence_reference" in "\n".join(validation_messages(manifest))


def test_unknown_target_class_fails() -> None:
    manifest = sample_manifest()
    mapping = manifest["taxonomy"]["class_mappings"][0]  # type: ignore[index]
    mapping["target_class_id"] = 99
    mapping["target_class_name"] = "unsupported-target"

    assert "matching ID/name pair" in "\n".join(validation_messages(manifest))


def test_incorrect_target_class_id_or_order_fails() -> None:
    manifest = sample_manifest()
    targets = manifest["taxonomy"]["target_classes"]  # type: ignore[index]
    targets[0], targets[1] = targets[1], targets[0]

    assert "must exactly match the approved IDs and order" in "\n".join(validation_messages(manifest))


def test_duplicate_target_class_names_fail() -> None:
    manifest = sample_manifest()
    manifest["taxonomy"]["target_classes"][1]["name"] = "person"  # type: ignore[index]

    assert "duplicate target class name" in "\n".join(validation_messages(manifest))


def test_duplicate_target_class_ids_fail() -> None:
    manifest = sample_manifest()
    manifest["taxonomy"]["target_classes"][1]["id"] = 0  # type: ignore[index]

    assert "duplicate target class ID" in "\n".join(validation_messages(manifest))


def test_duplicate_sample_ids_fail() -> None:
    manifest = sample_manifest()
    first_sample(manifest, "validation")["sample_id"] = first_sample(manifest)["sample_id"]

    assert "duplicates sample_id" in "\n".join(validation_messages(manifest))


def test_image_reused_across_splits_fails() -> None:
    manifest = sample_manifest()
    first_sample(manifest, "validation")["image_path"] = first_sample(manifest)["image_path"]

    assert "image is reused across splits" in "\n".join(validation_messages(manifest))


def test_normalised_image_path_reused_across_splits_fails() -> None:
    manifest = sample_manifest()
    first_sample(manifest, "validation")["image_path"] = first_sample(manifest)["image_path"].replace(
        "/", "\\"
    )

    assert "image is reused across splits" in "\n".join(validation_messages(manifest))


def test_duplicate_image_record_in_one_split_fails() -> None:
    manifest = sample_manifest()
    duplicate = copy.deepcopy(first_sample(manifest))
    duplicate["sample_id"] = "example-train-person-duplicate"
    manifest["splits"]["train"]["samples"].append(duplicate)  # type: ignore[index]

    assert "image appears more than once in the same split" in "\n".join(
        validation_messages(manifest)
    )


def test_group_reused_across_splits_fails() -> None:
    manifest = sample_manifest()
    first_sample(manifest, "validation")["group_id"] = first_sample(manifest)["group_id"]

    assert "group or sequence" in "\n".join(validation_messages(manifest))


def test_path_traversal_fails() -> None:
    manifest = sample_manifest()
    first_sample(manifest)["image_path"] = "train/images/../private.jpg"

    assert "path traversal" in "\n".join(validation_messages(manifest))


def test_personal_absolute_windows_path_fails() -> None:
    manifest = sample_manifest()
    first_sample(manifest)["image_path"] = r"C:\dataset\private.jpg"

    assert "must not be an absolute Windows or POSIX path" in "\n".join(validation_messages(manifest))


def test_personal_absolute_posix_path_fails() -> None:
    manifest = sample_manifest()
    first_sample(manifest)["image_path"] = "/data/private.jpg"

    assert "must not be an absolute Windows or POSIX path" in "\n".join(validation_messages(manifest))


@pytest.mark.parametrize(
    "unsafe_path",
    (
        r"C:drive-relative.jpg",
        r"\\server\share\private.jpg",
        r"..\private.jpg",
        "%2e%2e%2fprivate.jpg",
        "file:///private.jpg",
    ),
)
def test_other_unsafe_windows_and_encoded_paths_fail(unsafe_path: str) -> None:
    manifest = sample_manifest()
    first_sample(manifest)["image_path"] = unsafe_path

    messages = "\n".join(validation_messages(manifest))
    assert "path traversal" in messages or "absolute" in messages or "file URI" in messages


def test_personal_absolute_provenance_and_storage_references_fail() -> None:
    manifest = sample_manifest()
    manifest["source_provenance"]["source_reference"] = r"C:\dataset\source"  # type: ignore[index]
    manifest["storage_release"]["authoritative_storage_reference"] = "/data/private"  # type: ignore[index]

    messages = "\n".join(validation_messages(manifest))
    assert "$.source_provenance.source_reference" in messages
    assert "$.storage_release.authoritative_storage_reference" in messages
def test_invalid_release_decision_fails() -> None:
    manifest = sample_manifest()
    manifest["dataset"]["release_decision"] = "approved-because-schema-passed"  # type: ignore[index]

    assert "must be one of" in "\n".join(validation_messages(manifest))


def test_negative_quality_counts_fail() -> None:
    manifest = sample_manifest()
    manifest["quality"]["invalid_annotation_count"] = -1  # type: ignore[index]

    assert "must be at least 0" in "\n".join(validation_messages(manifest))


def test_malformed_checksums_fail() -> None:
    manifest = sample_manifest()
    first_sample(manifest)["checksum"] = "not-a-sha256"

    assert "required format" in "\n".join(validation_messages(manifest))


@pytest.mark.parametrize("checksum", ("a" * 64, "sha256:" + "A" * 64))
def test_sha256_checksums_accept_uppercase_and_lowercase_hexadecimal(checksum: str) -> None:
    manifest = sample_manifest()
    first_sample(manifest)["checksum"] = checksum

    assert validation_messages(manifest) == []


def test_non_positive_image_dimensions_fail() -> None:
    manifest = sample_manifest()
    first_sample(manifest)["width"] = 0

    assert "must be at least 1" in "\n".join(validation_messages(manifest))


def test_missing_referenced_files_fail_when_checking_is_enabled(tmp_path: Path) -> None:
    messages = validation_messages(sample_manifest(), dataset_root=tmp_path, check_files=True)

    assert any("referenced file is missing" in message for message in messages)


def test_file_checking_requires_an_explicit_dataset_root() -> None:
    messages = validation_messages(sample_manifest(), check_files=True)

    assert messages == ["--check-files: requires --dataset-root."]


def test_valid_relative_paths_pass_with_file_checking(tmp_path: Path) -> None:
    manifest = sample_manifest()
    for _, _, sample in validator._iter_samples(manifest):
        for path_name in ("image_path", "label_path"):
            path_value = sample.get(path_name)
            if isinstance(path_value, str):
                path = tmp_path / Path(path_value)
                path.parent.mkdir(parents=True, exist_ok=True)
                path.write_text("placeholder", encoding="utf-8")

    assert validation_messages(manifest, dataset_root=tmp_path, check_files=True) == []


def test_file_checking_reports_a_missing_label_file_with_its_field_context(tmp_path: Path) -> None:
    manifest = sample_manifest()
    for _, _, sample in validator._iter_samples(manifest):
        image_path = tmp_path / Path(str(sample["image_path"]))
        image_path.parent.mkdir(parents=True, exist_ok=True)
        image_path.write_text("placeholder", encoding="utf-8")

    messages = validation_messages(manifest, dataset_root=tmp_path, check_files=True)

    assert any("$.splits.train.samples[0].label_path" in message for message in messages)
    assert any("referenced file is missing" in message for message in messages)


def test_file_checks_reject_a_symlink_that_resolves_outside_the_dataset_root(tmp_path: Path) -> None:
    dataset_root = tmp_path / "dataset-root"
    external_directory = tmp_path / "external-directory"
    dataset_root.mkdir()
    external_directory.mkdir()
    (external_directory / "outside.jpg").write_text("placeholder", encoding="utf-8")
    link = dataset_root / "linked"
    try:
        link.symlink_to(external_directory, target_is_directory=True)
    except OSError:
        pytest.skip("The current platform does not allow test symlink creation.")

    manifest = sample_manifest()
    sample = first_sample(manifest)
    sample["image_path"] = "linked/outside.jpg"
    sample["labelled"] = False
    sample.pop("label_path")

    assert "resolves outside the supplied dataset root" in "\n".join(
        validation_messages(manifest, dataset_root=dataset_root, check_files=True)
    )


def test_cli_reports_ordinary_validation_failure_without_traceback(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    manifest = sample_manifest()
    first_sample(manifest)["image_path"] = "../not-allowed.jpg"

    assert validator.main([str(write_manifest(tmp_path, manifest))]) == 1
    error_output = capsys.readouterr().err
    assert "Dataset manifest validation failed" in error_output
    assert "Traceback" not in error_output


def test_cli_reports_multiple_ordinary_validation_errors(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    manifest = sample_manifest()
    first_sample(manifest)["image_path"] = "../not-allowed.jpg"
    manifest["dataset"]["release_decision"] = "not-a-controlled-decision"  # type: ignore[index]
    manifest["quality"]["image_count"] = -1  # type: ignore[index]

    assert validator.main([str(write_manifest(tmp_path, manifest))]) == 1
    error_output = capsys.readouterr().err
    assert "failed (3 issue(s))" in error_output
    assert "image_path" in error_output
    assert "release_decision" in error_output
    assert "image_count" in error_output
    assert "Traceback" not in error_output


def test_cli_accepts_a_utf8_bom_manifest(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    manifest_path = tmp_path / "bom-manifest.json"
    manifest_path.write_text(json.dumps(sample_manifest()), encoding="utf-8-sig")

    assert validator.main([str(manifest_path)]) == 0
    assert "Dataset manifest validation passed" in capsys.readouterr().out


def test_cli_help_succeeds(capsys: pytest.CaptureFixture[str]) -> None:
    with pytest.raises(SystemExit) as exit_result:
        validator.main(["--help"])

    assert exit_result.value.code == 0
    assert "--check-files" in capsys.readouterr().out


def test_direct_bounding_boxes_must_fit_declared_normalized_bounds() -> None:
    manifest = sample_manifest()
    sample = first_sample(manifest)
    sample["bounding_boxes"] = [
        {"class_id": 0, "x": 0.8, "y": 0.1, "width": 0.3, "height": 0.2}
    ]

    assert "normalized image bounds" in "\n".join(validation_messages(manifest))


def test_conflicting_source_class_mapping_fails() -> None:
    manifest = sample_manifest()
    conflicting_mapping = copy.deepcopy(manifest["taxonomy"]["class_mappings"][0])  # type: ignore[index]
    conflicting_mapping["target_class_id"] = 1
    conflicting_mapping["target_class_name"] = "stairs"
    manifest["taxonomy"]["class_mappings"].append(conflicting_mapping)  # type: ignore[index]

    assert "conflicts with an existing source-class mapping" in "\n".join(
        validation_messages(manifest)
    )
