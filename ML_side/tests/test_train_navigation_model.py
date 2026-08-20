"""Local-only tests for the controlled navigation-model training preflight."""

from __future__ import annotations

import hashlib
import json
import sys
from pathlib import Path

import pytest
import yaml


ML_SIDE_DIR = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ML_SIDE_DIR / "training"))
sys.path.insert(0, str(ML_SIDE_DIR / "tools"))

import train_navigation_model as training


SAMPLE_MANIFEST = ML_SIDE_DIR / "datasets" / "sample_manifest.json"
SHIPPED_SMOKE_CONFIG = ML_SIDE_DIR / "config" / "training_navigation_smoke.yaml"


def write_yaml(path: Path, names: list[str] | None = None) -> Path:
    names = names or [name for _, name in training.manifest_validator.APPROVED_TAXONOMY]
    path.write_text(
        "path: .\ntrain: train/images\nval: validation/images\ntest: test/images\nnames:\n"
        + "".join(f"  {index}: {name}\n" for index, name in enumerate(names)),
        encoding="utf-8",
    )
    return path


def create_fixture(tmp_path: Path) -> tuple[Path, Path, Path]:
    repository = tmp_path / "repository"
    dataset_root = tmp_path / "dataset"
    repository.mkdir()
    dataset_root.mkdir()
    manifest = json.loads(SAMPLE_MANIFEST.read_text(encoding="utf-8"))
    manifest["dataset"]["release_decision"] = "approved_for_training"
    manifest["licence"]["review_decision"] = "approved"
    (repository / "manifest.json").write_text(json.dumps(manifest), encoding="utf-8")
    for split in manifest["splits"].values():
        for sample in split["samples"]:
            for field in ("image_path", "label_path"):
                value = sample.get(field)
                if value:
                    target = dataset_root / value
                    target.parent.mkdir(parents=True, exist_ok=True)
                    target.write_text("fixture", encoding="utf-8")
    write_yaml(dataset_root / "dataset.yaml")
    (repository / "architecture.yaml").write_text("nc: 8\n", encoding="utf-8")
    config = {
        "schema_version": "1.0.0",
        "experiment_name": "Navigation MVP Test",
        "dataset": {"manifest_path": "manifest.json", "yaml_path": "dataset.yaml", "inspection_report_path": None, "stage": "approved_for_internal_training"},
        "model": {"architecture_path": "architecture.yaml", "initial_weights_path": None},
        "training": {"epochs": 2, "image_size": 640, "batch_size": 2, "device": "cpu", "workers": 1, "seed": 17, "optimizer": "AdamW", "learning_rate": 0.001, "confidence": 0.001, "iou": 0.7, "deterministic": True, "resume_behavior": "never"},
        "output": {"root": "artifacts/navigation_mvp"},
        "notes": "Fictional test-only configuration.",
    }
    config_path = repository / "training.yaml"
    config_path.write_text(json.dumps(config), encoding="utf-8")
    return repository, dataset_root, config_path


def load_plan(repository: Path, dataset_root: Path, config_path: Path, **kwargs: object) -> training.TrainingPlan:
    return training.load_training_plan(config_path, dataset_root_override=dataset_root, repository_root=repository, **kwargs)


def config_data(config_path: Path) -> dict[str, object]:
    return json.loads(config_path.read_text(encoding="utf-8"))


def save_config(config_path: Path, config: dict[str, object]) -> None:
    config_path.write_text(json.dumps(config), encoding="utf-8")


def write_external_manifest(tmp_path: Path, manifest: dict[str, object]) -> Path:
    external_root = tmp_path / "external-release"
    external_root.mkdir(parents=True)
    manifest_path = external_root / "release_manifest.json"
    manifest_path.write_text(json.dumps(manifest), encoding="utf-8")
    return manifest_path


def write_workspace_evidence(manifest_path: Path, workspace: Path, identity: str) -> Path:
    """Emit authoritative checksum evidence describing a workspace's released bytes."""
    import hashlib as _hashlib

    files = {
        path.relative_to(workspace).as_posix(): _hashlib.sha256(path.read_bytes()).hexdigest()
        for path in sorted(workspace.rglob("*"))
        if path.is_file()
    }
    evidence = manifest_path.parent / training.CHECKSUM_EVIDENCE_FILENAME
    evidence.write_text(
        json.dumps({"algorithm": "sha256", "release_identity": identity, "files": files}),
        encoding="utf-8",
    )
    return evidence


def test_valid_dry_run_succeeds_without_trainer_or_artifacts(tmp_path: Path) -> None:
    repository, dataset_root, config_path = create_fixture(tmp_path)
    plan = load_plan(repository, dataset_root, config_path)

    result = training.dry_run(plan)

    assert result["status"] == "dry_run_valid"
    assert plan.manifest_reference == "manifest.json"
    assert not plan.run_directory.exists()
    assert result["plan"]["dataset_root"] == "externally supplied local root"  # type: ignore[index]


def test_dry_run_does_not_invoke_trainer(tmp_path: Path) -> None:
    repository, dataset_root, config_path = create_fixture(tmp_path)
    plan = load_plan(repository, dataset_root, config_path)

    assert training.dry_run(plan)["status"] == "dry_run_valid"
    assert not plan.run_directory.exists()


def test_dry_run_does_not_require_ultralytics(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    repository, dataset_root, config_path = create_fixture(tmp_path)
    monkeypatch.setitem(sys.modules, "ultralytics", None)

    assert training.dry_run(load_plan(repository, dataset_root, config_path))["status"] == "dry_run_valid"


def test_external_approved_manifest_override_is_accepted_and_sanitised(tmp_path: Path) -> None:
    repository, dataset_root, config_path = create_fixture(tmp_path)
    manifest = json.loads((repository / "manifest.json").read_text(encoding="utf-8"))
    external_manifest = write_external_manifest(tmp_path, manifest)

    plan = load_plan(repository, dataset_root, config_path, manifest_path_override=external_manifest)
    dry_run = training.dry_run(plan)

    assert plan.manifest_path == external_manifest.resolve()
    assert plan.manifest_reference == training.EXTERNAL_MANIFEST_REFERENCE
    assert dry_run["plan"]["manifest_path"] == training.EXTERNAL_MANIFEST_REFERENCE  # type: ignore[index]
    assert str(external_manifest) not in json.dumps(dry_run)


def test_external_manifest_location_is_not_persisted_in_run_metadata(tmp_path: Path) -> None:
    repository, dataset_root, config_path = create_fixture(tmp_path)
    manifest = json.loads((repository / "manifest.json").read_text(encoding="utf-8"))
    external_manifest = write_external_manifest(tmp_path, manifest)
    config = config_data(config_path)
    config["dataset"]["manifest_path"] = str(external_manifest)  # type: ignore[index]
    save_config(config_path, config)
    plan = load_plan(repository, dataset_root, config_path, manifest_path_override=external_manifest)

    training.run_training(plan, lambda _: {"ok": True})

    persisted = "\n".join(
        path.read_text(encoding="utf-8")
        for path in (
            plan.run_directory / "run_metadata.json",
            plan.run_directory / "resolved_training_config.json",
            plan.run_directory / "dataset_reference.json",
        )
    )
    assert training.EXTERNAL_MANIFEST_REFERENCE in persisted
    assert str(external_manifest) not in persisted
    assert str(external_manifest.parent) not in persisted
    assert str(external_manifest) not in json.dumps(training.dry_run(plan))


def test_missing_or_uri_external_manifest_is_rejected(tmp_path: Path) -> None:
    repository, dataset_root, config_path = create_fixture(tmp_path)

    with pytest.raises(training.TrainingPipelineError, match="external manifest path"):
        load_plan(repository, dataset_root, config_path, manifest_path_override=tmp_path / "missing.json")
    non_json = tmp_path / "release_manifest.txt"
    non_json.write_text("{}", encoding="utf-8")
    with pytest.raises(training.TrainingPipelineError, match="JSON file"):
        load_plan(repository, dataset_root, config_path, manifest_path_override=non_json)
    directory = tmp_path / "release_manifest.json"
    directory.mkdir()
    with pytest.raises(training.TrainingPipelineError, match="regular JSON file"):
        load_plan(repository, dataset_root, config_path, manifest_path_override=directory)
    for value in ("https://example.invalid/release_manifest.json", "file:///release_manifest.json", "s3://example/release_manifest.json"):
        with pytest.raises(training.TrainingPipelineError, match="URL or URI"):
            load_plan(repository, dataset_root, config_path, manifest_path_override=Path(value))


def test_external_manifest_preserves_validation_and_eligibility_gates(tmp_path: Path) -> None:
    repository, dataset_root, config_path = create_fixture(tmp_path)
    manifest = json.loads((repository / "manifest.json").read_text(encoding="utf-8"))
    invalid_manifest = write_external_manifest(tmp_path, {})
    with pytest.raises(training.TrainingPipelineError, match="manifest validation failed"):
        load_plan(repository, dataset_root, config_path, manifest_path_override=invalid_manifest)

    manifest["licence"]["review_decision"] = "conditional"
    external_manifest = write_external_manifest(tmp_path / "licence", manifest)
    with pytest.raises(training.TrainingPipelineError, match="licence review"):
        load_plan(repository, dataset_root, config_path, manifest_path_override=external_manifest)


def test_external_manifest_preserves_taxonomy_and_split_gates(tmp_path: Path) -> None:
    repository, dataset_root, config_path = create_fixture(tmp_path)
    manifest = json.loads((repository / "manifest.json").read_text(encoding="utf-8"))
    external_manifest = write_external_manifest(tmp_path, manifest)
    write_yaml(dataset_root / "dataset.yaml", ["person", "stairs", "door", "chair", "table", "pole", "bicycle", "wrong"])
    with pytest.raises(training.TrainingPipelineError, match="taxonomy"):
        load_plan(repository, dataset_root, config_path, manifest_path_override=external_manifest)

    write_yaml(dataset_root / "dataset.yaml")
    (dataset_root / "validation" / "images" / "wrong-split.jpg").write_text("fixture", encoding="utf-8")
    manifest["splits"]["train"]["samples"][0]["image_path"] = "validation/images/wrong-split.jpg"
    external_manifest.write_text(json.dumps(manifest), encoding="utf-8")
    with pytest.raises(training.TrainingPipelineError, match="outside the dataset YAML train"):
        load_plan(repository, dataset_root, config_path, manifest_path_override=external_manifest)


def test_cli_valid_fictional_dry_run_does_not_write_artifacts(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    repository, dataset_root, config_path = create_fixture(tmp_path)
    monkeypatch.setattr(training, "REPOSITORY_ROOT", repository)

    assert training.main(["--config", str(config_path), "--dataset-root", str(dataset_root), "--dry-run"]) == 0
    assert '"status": "dry_run_valid"' in capsys.readouterr().out
    assert not (repository / "artifacts").exists()


def test_invalid_manifest_fails(tmp_path: Path) -> None:
    repository, dataset_root, config_path = create_fixture(tmp_path)
    manifest = json.loads((repository / "manifest.json").read_text(encoding="utf-8"))
    del manifest["dataset"]["name"]
    (repository / "manifest.json").write_text(json.dumps(manifest), encoding="utf-8")

    with pytest.raises(training.TrainingPipelineError, match="manifest validation failed"):
        load_plan(repository, dataset_root, config_path)


def test_wrong_dataset_yaml_taxonomy_fails(tmp_path: Path) -> None:
    repository, dataset_root, config_path = create_fixture(tmp_path)
    write_yaml(dataset_root / "dataset.yaml", ["person", "stairs", "door", "chair", "table", "pole", "bicycle", "wrong"])

    with pytest.raises(training.TrainingPipelineError, match="taxonomy"):
        load_plan(repository, dataset_root, config_path)


@pytest.mark.parametrize("decision, expected", [("rejected", "rejected"), ("draft", "not approved"), ("under_review", "not approved")])
def test_ineligible_manifest_release_status_fails(tmp_path: Path, decision: str, expected: str) -> None:
    repository, dataset_root, config_path = create_fixture(tmp_path)
    manifest = json.loads((repository / "manifest.json").read_text(encoding="utf-8"))
    manifest["dataset"]["release_decision"] = decision
    (repository / "manifest.json").write_text(json.dumps(manifest), encoding="utf-8")

    with pytest.raises(training.TrainingPipelineError, match=expected):
        load_plan(repository, dataset_root, config_path)


@pytest.mark.parametrize("stage", ["candidate", "in_review", "rejected"])
def test_ineligible_training_stage_fails(tmp_path: Path, stage: str) -> None:
    repository, dataset_root, config_path = create_fixture(tmp_path)
    config = config_data(config_path)
    config["dataset"]["stage"] = stage  # type: ignore[index]
    save_config(config_path, config)

    with pytest.raises(training.TrainingPipelineError, match="not eligible"):
        load_plan(repository, dataset_root, config_path)


def test_ineligible_licence_review_status_fails(tmp_path: Path) -> None:
    repository, dataset_root, config_path = create_fixture(tmp_path)
    manifest = json.loads((repository / "manifest.json").read_text(encoding="utf-8"))
    manifest["licence"]["review_decision"] = "conditional"
    (repository / "manifest.json").write_text(json.dumps(manifest), encoding="utf-8")

    with pytest.raises(training.TrainingPipelineError, match="licence review"):
        load_plan(repository, dataset_root, config_path)


def test_missing_yaml_and_local_model_fail(tmp_path: Path) -> None:
    repository, dataset_root, config_path = create_fixture(tmp_path)
    (dataset_root / "dataset.yaml").unlink()
    with pytest.raises(training.TrainingPipelineError, match="dataset YAML path"):
        load_plan(repository, dataset_root, config_path)
    write_yaml(dataset_root / "dataset.yaml")
    (repository / "architecture.yaml").unlink()
    with pytest.raises(training.TrainingPipelineError, match="model architecture"):
        load_plan(repository, dataset_root, config_path)


@pytest.mark.parametrize("path", ["https://example.invalid/model.pt", "../outside.pt", r"C:\\outside.pt", "yolov8n.pt"])
def test_remote_identifier_urls_and_unsafe_model_paths_fail(tmp_path: Path, path: str) -> None:
    repository, dataset_root, config_path = create_fixture(tmp_path)
    config = config_data(config_path)
    config["model"]["architecture_path"] = path  # type: ignore[index]
    save_config(config_path, config)

    with pytest.raises(training.TrainingPipelineError):
        load_plan(repository, dataset_root, config_path)


def test_dataset_yaml_traversal_and_output_escape_fail(tmp_path: Path) -> None:
    repository, dataset_root, config_path = create_fixture(tmp_path)
    config = config_data(config_path)
    config["dataset"]["yaml_path"] = "../dataset.yaml"  # type: ignore[index]
    save_config(config_path, config)
    with pytest.raises(training.TrainingPipelineError, match="dataset YAML path"):
        load_plan(repository, dataset_root, config_path)
    config["dataset"]["yaml_path"] = "dataset.yaml"  # type: ignore[index]
    config["output"]["root"] = "../outside"  # type: ignore[index]
    save_config(config_path, config)
    with pytest.raises(training.TrainingPipelineError, match="output root"):
        load_plan(repository, dataset_root, config_path)


@pytest.mark.parametrize("value", [float("nan"), float("inf"), True])
def test_nonfinite_or_boolean_numeric_thresholds_fail(tmp_path: Path, value: object) -> None:
    repository, dataset_root, config_path = create_fixture(tmp_path)
    config = config_data(config_path)
    config["training"]["confidence"] = value  # type: ignore[index]
    save_config(config_path, config)

    with pytest.raises(training.TrainingPipelineError, match="confidence"):
        load_plan(repository, dataset_root, config_path)


def test_unknown_configuration_field_and_manifest_yaml_split_mismatch_fail(tmp_path: Path) -> None:
    repository, dataset_root, config_path = create_fixture(tmp_path)
    config = config_data(config_path)
    config["training"]["unexpected"] = "ignored-before-hardening"  # type: ignore[index]
    save_config(config_path, config)
    with pytest.raises(training.TrainingPipelineError, match="unsupported field"):
        load_plan(repository, dataset_root, config_path)
    config["training"].pop("unexpected")  # type: ignore[index]
    save_config(config_path, config)
    write_yaml(dataset_root / "dataset.yaml")
    (dataset_root / "dataset.yaml").write_text(
        (dataset_root / "dataset.yaml").read_text(encoding="utf-8").replace("train: train/images", "train: validation/images"),
        encoding="utf-8",
    )
    with pytest.raises(training.TrainingPipelineError, match="outside the dataset YAML train"):
        load_plan(repository, dataset_root, config_path)


def test_failing_inspection_evidence_blocks_training(tmp_path: Path) -> None:
    repository, dataset_root, config_path = create_fixture(tmp_path)
    (dataset_root / "inspection.json").write_text('{"quality_verdict":"fail"}', encoding="utf-8")
    config = config_data(config_path)
    config["dataset"]["inspection_report_path"] = "inspection.json"  # type: ignore[index]
    save_config(config_path, config)

    with pytest.raises(training.TrainingPipelineError, match="failing quality verdict"):
        load_plan(repository, dataset_root, config_path)


def test_nonfailing_inspection_evidence_is_accepted(tmp_path: Path) -> None:
    repository, dataset_root, config_path = create_fixture(tmp_path)
    (dataset_root / "inspection.json").write_text('{"quality_verdict":"pass_with_warnings"}', encoding="utf-8")
    config = config_data(config_path)
    config["dataset"]["inspection_report_path"] = "inspection.json"  # type: ignore[index]
    save_config(config_path, config)

    assert load_plan(repository, dataset_root, config_path).run_id


def test_dataset_root_is_not_accepted_from_committed_configuration(tmp_path: Path) -> None:
    repository, dataset_root, config_path = create_fixture(tmp_path)
    config = config_data(config_path)
    config["dataset"]["root"] = str(dataset_root)
    save_config(config_path, config)

    with pytest.raises(training.TrainingPipelineError, match="unsupported field"):
        training.load_training_plan(config_path, repository_root=repository)


def test_stable_run_id_checksums_and_seed(tmp_path: Path) -> None:
    repository, dataset_root, config_path = create_fixture(tmp_path)
    first = load_plan(repository, dataset_root, config_path)
    second = load_plan(repository, dataset_root, config_path)

    assert first.run_id == second.run_id
    assert first.config_checksum == second.config_checksum
    assert training.trainer_arguments(first)["seed"] == 17


def test_smoke_controls_default_to_full_training_behaviour(tmp_path: Path) -> None:
    repository, dataset_root, config_path = create_fixture(tmp_path)
    plan = load_plan(repository, dataset_root, config_path)
    arguments = training.trainer_arguments(plan)

    assert plan.config["training"]["fraction"] == 1.0  # type: ignore[index]
    assert plan.config["training"]["val"] is True  # type: ignore[index]
    assert arguments["fraction"] == 1.0
    assert arguments["val"] is True


def test_smoke_controls_are_validated_and_forwarded(tmp_path: Path) -> None:
    repository, dataset_root, config_path = create_fixture(tmp_path)
    config = config_data(config_path)
    config["training"]["fraction"] = 0.002  # type: ignore[index]
    config["training"]["val"] = False  # type: ignore[index]
    save_config(config_path, config)

    arguments = training.trainer_arguments(load_plan(repository, dataset_root, config_path))

    assert arguments["fraction"] == 0.002
    assert arguments["val"] is False


def test_auto_device_is_preserved_in_config_and_translated_for_ultralytics(tmp_path: Path) -> None:
    repository, dataset_root, config_path = create_fixture(tmp_path)
    config = config_data(config_path)
    config["training"]["device"] = "auto"  # type: ignore[index]
    save_config(config_path, config)
    plan = load_plan(repository, dataset_root, config_path)

    assert plan.config["training"]["device"] == "auto"  # type: ignore[index]
    assert training.trainer_arguments(plan)["device"] == ""
    assert training._metadata_trainer_arguments(plan)["device"] == ""

    training.run_training(plan, lambda _: {"ok": True})

    resolved_config = json.loads((plan.run_directory / "resolved_training_config.json").read_text(encoding="utf-8"))
    metadata = json.loads((plan.run_directory / "run_metadata.json").read_text(encoding="utf-8"))
    assert resolved_config["training"]["device"] == "auto"
    assert metadata["resolved_parameters"]["device"] == ""


@pytest.mark.parametrize("device", ["cpu", "cuda:0", "0"])
def test_explicit_device_is_forwarded_unchanged(tmp_path: Path, device: str) -> None:
    repository, dataset_root, config_path = create_fixture(tmp_path)
    config = config_data(config_path)
    config["training"]["device"] = device  # type: ignore[index]
    save_config(config_path, config)

    assert training.trainer_arguments(load_plan(repository, dataset_root, config_path))["device"] == device


@pytest.mark.parametrize("fraction", [0.0, -0.1, 1, 1.1, True, float("nan"), float("inf")])
def test_invalid_smoke_fraction_is_rejected(tmp_path: Path, fraction: object) -> None:
    repository, dataset_root, config_path = create_fixture(tmp_path)
    config = config_data(config_path)
    config["training"]["fraction"] = fraction  # type: ignore[index]
    save_config(config_path, config)

    with pytest.raises(training.TrainingPipelineError, match="fraction"):
        load_plan(repository, dataset_root, config_path)


def test_non_boolean_smoke_val_is_rejected(tmp_path: Path) -> None:
    repository, dataset_root, config_path = create_fixture(tmp_path)
    config = config_data(config_path)
    config["training"]["val"] = "false"  # type: ignore[index]
    save_config(config_path, config)

    with pytest.raises(training.TrainingPipelineError, match="training val"):
        load_plan(repository, dataset_root, config_path)


def test_changed_configuration_changes_the_run_identity(tmp_path: Path) -> None:
    repository, dataset_root, config_path = create_fixture(tmp_path)
    first = load_plan(repository, dataset_root, config_path)
    config = config_data(config_path)
    config["training"]["epochs"] = 3  # type: ignore[index]
    save_config(config_path, config)
    second = load_plan(repository, dataset_root, config_path)

    assert first.config_checksum != second.config_checksum
    assert first.run_id != second.run_id


def test_existing_local_initial_weights_are_accepted(tmp_path: Path) -> None:
    repository, dataset_root, config_path = create_fixture(tmp_path)
    (repository / "initial.pt").write_bytes(b"fictional local weights")
    config = config_data(config_path)
    config["model"] = {"architecture_path": None, "initial_weights_path": "initial.pt"}
    save_config(config_path, config)

    assert load_plan(repository, dataset_root, config_path).model_kind == "initial_weights"


def test_existing_run_is_protected(tmp_path: Path) -> None:
    repository, dataset_root, config_path = create_fixture(tmp_path)
    plan = load_plan(repository, dataset_root, config_path)
    plan.run_directory.mkdir(parents=True)

    with pytest.raises(training.TrainingPipelineError, match="already exists"):
        load_plan(repository, dataset_root, config_path)


def test_existing_run_can_only_resume_with_explicit_policy_and_flag(tmp_path: Path) -> None:
    repository, dataset_root, config_path = create_fixture(tmp_path)
    config = config_data(config_path)
    config["training"]["resume_behavior"] = "allow"  # type: ignore[index]
    save_config(config_path, config)
    plan = load_plan(repository, dataset_root, config_path)
    plan.run_directory.mkdir(parents=True)

    resumed = load_plan(repository, dataset_root, config_path, allow_existing_run=True)
    assert resumed.run_directory.exists()


def test_trainer_arguments_match_resolved_config(tmp_path: Path) -> None:
    repository, dataset_root, config_path = create_fixture(tmp_path)
    plan = load_plan(repository, dataset_root, config_path, overrides={"epochs": 3, "batch_size": 4})
    arguments = training.trainer_arguments(plan)

    assert arguments["epochs"] == 3
    assert arguments["batch"] == 4
    assert arguments["data"] == str(dataset_root / "dataset.yaml")
    assert arguments["cache"] is False


def test_successful_mocked_training_writes_sanitised_metadata(tmp_path: Path) -> None:
    repository, dataset_root, config_path = create_fixture(tmp_path)
    plan = load_plan(repository, dataset_root, config_path)
    called: list[str] = []

    assert training.run_training(plan, lambda received: called.append(received.run_id) or {"ok": True}) == {"ok": True}
    metadata = json.loads((plan.run_directory / "run_metadata.json").read_text(encoding="utf-8"))

    assert called == [plan.run_id]
    assert metadata["status"] == "succeeded"
    assert metadata["manifest_checksum_sha256"] == plan.manifest_checksum
    assert metadata["manifest_reference"] == "manifest.json"
    assert metadata["resolved_parameters"]["fraction"] == 1.0
    assert metadata["resolved_parameters"]["val"] is True
    assert metadata["dataset_release"]["source_version"] == "fictional-source-v1.0"
    assert str(dataset_root) not in json.dumps(metadata)
    assert "environ" not in json.dumps(metadata).casefold()
    resolved_config = json.loads((plan.run_directory / "resolved_training_config.json").read_text(encoding="utf-8"))
    assert resolved_config["training"]["fraction"] == 1.0
    assert resolved_config["training"]["val"] is True


def test_failed_mocked_training_records_failure_and_preserves_partial_output(tmp_path: Path) -> None:
    repository, dataset_root, config_path = create_fixture(tmp_path)
    plan = load_plan(repository, dataset_root, config_path)

    def failed_trainer(_: training.TrainingPlan) -> object:
        (plan.run_directory / "partial.txt").write_text("partial", encoding="utf-8")
        raise RuntimeError("fictional trainer failure")

    with pytest.raises(training.TrainingPipelineError, match="fictional trainer failure"):
        training.run_training(plan, failed_trainer)
    metadata = json.loads((plan.run_directory / "run_metadata.json").read_text(encoding="utf-8"))

    assert metadata["status"] == "failed"
    assert "RuntimeError" in metadata["failure_summary"]
    assert (plan.run_directory / "partial.txt").is_file()


def test_cli_errors_do_not_show_traceback_and_help_succeeds(capsys: pytest.CaptureFixture[str], tmp_path: Path) -> None:
    with pytest.raises(SystemExit) as exit_result:
        training.main(["--help"])
    assert exit_result.value.code == 0
    assert "--confirm-training" in capsys.readouterr().out
    assert training.main(["--config", str(tmp_path / "missing.yaml"), "--dry-run"]) == 1
    assert "Traceback" not in capsys.readouterr().err


def test_cli_conflicting_confirmation_flags_fail_without_trainer(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    repository, dataset_root, config_path = create_fixture(tmp_path)
    monkeypatch.setattr(training, "REPOSITORY_ROOT", repository)

    assert training.main(["--config", str(config_path), "--dataset-root", str(dataset_root), "--dry-run", "--confirm-training"]) == 1
    assert "cannot be used together" in capsys.readouterr().err


def test_missing_confirmation_blocks_trainer_invocation(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    repository, dataset_root, config_path = create_fixture(tmp_path)
    monkeypatch.setattr(training, "REPOSITORY_ROOT", repository)
    monkeypatch.setattr(training, "default_trainer", lambda _: (_ for _ in ()).throw(AssertionError("must not run")))

    assert training.main(["--config", str(config_path), "--dataset-root", str(dataset_root)]) == 1
    assert "requires --confirm-training" in capsys.readouterr().err
    assert not (repository / "artifacts").exists()


@pytest.mark.parametrize("workers", [0, 1])
def test_non_negative_worker_counts_are_accepted(tmp_path: Path, workers: int) -> None:
    repository, dataset_root, config_path = create_fixture(tmp_path)
    config = config_data(config_path)
    config["training"]["workers"] = workers  # type: ignore[index]
    save_config(config_path, config)

    plan = load_plan(repository, dataset_root, config_path)

    assert plan.config["training"]["workers"] == workers  # type: ignore[index]
    assert training.trainer_arguments(plan)["workers"] == workers


@pytest.mark.parametrize("workers", [-1, True, 0.0, "0", None])
def test_invalid_worker_counts_are_rejected(tmp_path: Path, workers: object) -> None:
    repository, dataset_root, config_path = create_fixture(tmp_path)
    config = config_data(config_path)
    config["training"]["workers"] = workers  # type: ignore[index]
    save_config(config_path, config)

    with pytest.raises(training.TrainingPipelineError, match="training workers"):
        load_plan(repository, dataset_root, config_path)


@pytest.mark.parametrize("key", ["epochs", "image_size", "batch_size", "seed"])
def test_zero_is_still_rejected_for_strictly_positive_fields(tmp_path: Path, key: str) -> None:
    repository, dataset_root, config_path = create_fixture(tmp_path)
    config = config_data(config_path)
    config["training"][key] = 0  # type: ignore[index]
    save_config(config_path, config)

    with pytest.raises(training.TrainingPipelineError, match=f"training {key}"):
        load_plan(repository, dataset_root, config_path)


def test_shipped_smoke_configuration_passes_its_own_preflight(tmp_path: Path) -> None:
    """Guard the shipped smoke configuration against validator drift.

    The configuration file itself is loaded rather than a hand-copied set of
    values, so a future contract change that invalidates the shipped file fails
    here instead of during a real smoke run.
    """
    repository, dataset_root, _ = create_fixture(tmp_path)
    shipped = yaml.safe_load(SHIPPED_SMOKE_CONFIG.read_text(encoding="utf-8"))
    weights = repository / str(shipped["model"]["initial_weights_path"])
    weights.parent.mkdir(parents=True, exist_ok=True)
    weights.write_bytes(b"local placeholder; preflight never loads model weights")
    identity = "b" * 64
    manifest = json.loads((repository / "manifest.json").read_text(encoding="utf-8"))
    manifest["quality"]["checksums"] = {"release_identity": f"sha256:{identity}"}
    external_manifest = write_external_manifest(tmp_path, manifest)
    write_workspace_evidence(external_manifest, dataset_root, identity)

    plan = training.load_training_plan(
        SHIPPED_SMOKE_CONFIG,
        dataset_root_override=dataset_root,
        manifest_path_override=external_manifest,
        repository_root=repository,
    )

    assert training.dry_run(plan)["status"] == "dry_run_valid"
    assert plan.config["training"]["workers"] == shipped["training"]["workers"]  # type: ignore[index]
    assert training.trainer_arguments(plan)["workers"] == shipped["training"]["workers"]
    assert not plan.run_directory.exists()


def materialise_samples(manifest: dict[str, object], root: Path) -> None:
    """Write placeholder bytes for every manifest sample beneath one root."""
    for split in manifest["splits"].values():  # type: ignore[attr-defined]
        for sample in split["samples"]:
            for field in ("image_path", "label_path"):
                value = sample.get(field)
                if value:
                    target = root / value
                    target.parent.mkdir(parents=True, exist_ok=True)
                    target.write_text("fixture", encoding="utf-8")


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    digest.update(path.read_bytes())
    return digest.hexdigest()


def write_release_checksums(release_root: Path, identity: str) -> Path:
    """Emit checksum evidence exactly as the release builder does.

    The builder computes checksums before writing this file, so the evidence
    deliberately does not checksum itself.
    """
    files = {
        path.relative_to(release_root).as_posix(): sha256_file(path)
        for path in sorted(release_root.rglob("*"))
        if path.is_file() and path.name != training.CHECKSUM_EVIDENCE_FILENAME
    }
    evidence = release_root / training.CHECKSUM_EVIDENCE_FILENAME
    evidence.write_text(
        json.dumps({"algorithm": "sha256", "release_identity": identity, "files": files}),
        encoding="utf-8",
    )
    return evidence


def create_released_fixture(tmp_path: Path) -> tuple[Path, Path, Path, Path, Path]:
    """Build an authoritative release plus a separate faithful training workspace.

    The release hosts its own manifest and checksum evidence, matching the
    approved controlled-release layout. The workspace holds the same dataset
    bytes, including the manifest copy the checksum evidence covers.
    """
    repository = tmp_path / "repository"
    release_root = tmp_path / "release"
    workspace = tmp_path / "workspace"
    for directory in (repository, release_root, workspace):
        directory.mkdir()
    identity = "a" * 64
    manifest = json.loads(SAMPLE_MANIFEST.read_text(encoding="utf-8"))
    manifest["dataset"]["release_decision"] = "approved_for_training"
    manifest["licence"]["review_decision"] = "approved"
    manifest["quality"]["checksums"] = {"release_identity": f"sha256:{identity}"}
    manifest_text = json.dumps(manifest)
    for root in (release_root, workspace):
        materialise_samples(manifest, root)
        write_yaml(root / "dataset.yaml")
        (root / "release_manifest.json").write_text(manifest_text, encoding="utf-8")
    release_manifest = release_root / "release_manifest.json"
    write_release_checksums(release_root, identity)
    (repository / "architecture.yaml").write_text("nc: 8\n", encoding="utf-8")
    config = {
        "schema_version": "1.0.0",
        "experiment_name": "Navigation Released Test",
        "dataset": {"yaml_path": "dataset.yaml", "inspection_report_path": None, "stage": "released"},
        "model": {"architecture_path": "architecture.yaml", "initial_weights_path": None},
        "training": {
            "epochs": 1, "image_size": 640, "batch_size": 2, "device": "auto", "workers": 0,
            "seed": 42, "optimizer": "AdamW", "learning_rate": 0.001, "confidence": 0.001,
            "iou": 0.7, "deterministic": True, "fraction": 0.002, "val": False,
            "resume_behavior": "never",
        },
        "output": {"root": "artifacts/navigation_mvp"},
        "notes": "Fictional released test configuration.",
    }
    config_path = repository / "training.yaml"
    save_config(config_path, config)
    return repository, release_root, workspace, release_manifest, config_path


def released_plan(tmp_path: Path) -> training.TrainingPlan:
    repository, _, workspace, release_manifest, config_path = create_released_fixture(tmp_path)
    return training.load_training_plan(
        config_path,
        dataset_root_override=workspace,
        manifest_path_override=release_manifest,
        repository_root=repository,
    )


def runtime_dataset_root(plan: training.TrainingPlan, descriptor: Path) -> Path:
    return Path(yaml.safe_load(descriptor.read_text(encoding="utf-8"))["path"])


# --------------------------------------------------------- CWD independence


def test_runtime_descriptor_resolves_absolute_root_from_relative_path(tmp_path: Path) -> None:
    plan = released_plan(tmp_path)

    assert yaml.safe_load(plan.dataset_yaml_path.read_text(encoding="utf-8"))["path"] == "."
    with training.runtime_dataset_descriptor(plan) as descriptor:
        resolved = runtime_dataset_root(plan, descriptor)

    assert resolved.is_absolute()
    assert resolved == plan.dataset_root.resolve()


def test_runtime_descriptor_is_independent_of_process_working_directory(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    plan = released_plan(tmp_path)
    unrelated = tmp_path / "unrelated-cwd"
    unrelated.mkdir()
    monkeypatch.chdir(unrelated)

    with training.runtime_dataset_descriptor(plan) as descriptor:
        resolved = runtime_dataset_root(plan, descriptor)

    assert resolved == plan.dataset_root.resolve()
    assert not str(resolved).startswith(str(unrelated))


def test_runtime_descriptor_preserves_splits_and_taxonomy(tmp_path: Path) -> None:
    plan = released_plan(tmp_path)
    original = yaml.safe_load(plan.dataset_yaml_path.read_text(encoding="utf-8"))

    with training.runtime_dataset_descriptor(plan) as descriptor:
        runtime = yaml.safe_load(descriptor.read_text(encoding="utf-8"))

    assert runtime["train"] == original["train"]
    assert runtime["val"] == original["val"]
    assert runtime["test"] == original["test"]
    assert runtime["names"] == original["names"]
    assert set(runtime) == set(original)


def test_trainer_receives_the_resolved_runtime_descriptor(tmp_path: Path) -> None:
    plan = released_plan(tmp_path)
    received: dict[str, object] = {}

    def trainer(active_plan: training.TrainingPlan) -> object:
        with training.runtime_dataset_descriptor(active_plan) as descriptor:
            arguments = training.runtime_trainer_arguments(active_plan, descriptor)
            received["data"] = arguments["data"]
            received["root"] = str(runtime_dataset_root(active_plan, descriptor))
        return {"ok": True}

    training.run_training(plan, trainer)

    assert Path(str(received["data"])).name == "dataset.yaml"
    assert received["root"] == str(plan.dataset_root.resolve())
    assert training.trainer_arguments(plan)["data"] == str(plan.dataset_yaml_path)


# ----------------------------------------------------- ephemeral descriptor


def test_original_dataset_yaml_is_not_modified(tmp_path: Path) -> None:
    plan = released_plan(tmp_path)
    before = plan.dataset_yaml_path.read_bytes()

    with training.runtime_dataset_descriptor(plan):
        pass

    assert plan.dataset_yaml_path.read_bytes() == before


def test_runtime_descriptor_is_removed_after_success(tmp_path: Path) -> None:
    plan = released_plan(tmp_path)

    with training.runtime_dataset_descriptor(plan) as descriptor:
        assert descriptor.is_file()
        captured = descriptor

    assert not captured.exists()
    assert not captured.parent.exists()


def test_runtime_descriptor_is_removed_after_trainer_failure(tmp_path: Path) -> None:
    plan = released_plan(tmp_path)
    captured: dict[str, Path] = {}

    with pytest.raises(RuntimeError):
        with training.runtime_dataset_descriptor(plan) as descriptor:
            captured["path"] = descriptor
            raise RuntimeError("simulated trainer failure")

    assert not captured["path"].exists()
    assert not captured["path"].parent.exists()


def test_runtime_descriptor_is_not_written_inside_the_dataset(tmp_path: Path) -> None:
    plan = released_plan(tmp_path)

    with training.runtime_dataset_descriptor(plan) as descriptor:
        with pytest.raises(ValueError):
            descriptor.relative_to(plan.dataset_root)


# ------------------------------------------------- released-root isolation


def test_released_manifest_inside_supplied_dataset_root_is_rejected(tmp_path: Path) -> None:
    repository, release_root, _, release_manifest, config_path = create_released_fixture(tmp_path)

    with pytest.raises(training.TrainingPipelineError, match="must not be used directly"):
        training.load_training_plan(
            config_path,
            dataset_root_override=release_root,
            manifest_path_override=release_manifest,
            repository_root=repository,
        )


def test_separate_workspace_with_authoritative_manifest_is_accepted(tmp_path: Path) -> None:
    repository, _, workspace, release_manifest, config_path = create_released_fixture(tmp_path)

    plan = training.load_training_plan(
        config_path,
        dataset_root_override=workspace,
        manifest_path_override=release_manifest,
        repository_root=repository,
    )

    assert training.dry_run(plan)["status"] == "dry_run_valid"
    assert plan.manifest_reference == training.EXTERNAL_MANIFEST_REFERENCE
    assert plan.dataset_root == workspace.resolve()


def test_incomplete_workspace_fails_manifest_validation(tmp_path: Path) -> None:
    repository, _, workspace, release_manifest, config_path = create_released_fixture(tmp_path)
    manifest = json.loads(release_manifest.read_text(encoding="utf-8"))
    missing = workspace / manifest["splits"]["train"]["samples"][0]["image_path"]
    missing.unlink()

    with pytest.raises(training.TrainingPipelineError, match="manifest validation failed"):
        training.load_training_plan(
            config_path,
            dataset_root_override=workspace,
            manifest_path_override=release_manifest,
            repository_root=repository,
        )


def test_dry_run_enforces_the_same_isolation_requirement(tmp_path: Path) -> None:
    """The isolation gate lives in preflight, so dry-run cannot diverge from training."""
    repository, release_root, _, release_manifest, config_path = create_released_fixture(tmp_path)

    # Dry-run and confirmed training share load_training_plan, so a rejected
    # release root can never reach either path.
    with pytest.raises(training.TrainingPipelineError, match="must not be used directly"):
        training.load_training_plan(
            config_path,
            dataset_root_override=release_root,
            manifest_path_override=release_manifest,
            repository_root=repository,
        )
    assert not (repository / "artifacts").exists()


def test_repository_relative_manifest_flow_is_unaffected(tmp_path: Path) -> None:
    """A repository-relative manifest is never treated as an external release root."""
    repository, dataset_root, config_path = create_fixture(tmp_path)

    plan = load_plan(repository, dataset_root, config_path)

    assert training.dry_run(plan)["status"] == "dry_run_valid"
    assert plan.manifest_reference == "manifest.json"


# ------------------------------------------------------------ cache boundary


def test_simulated_label_cache_lands_only_in_the_workspace(tmp_path: Path) -> None:
    repository, release_root, workspace, release_manifest, config_path = create_released_fixture(tmp_path)
    release_snapshot = {
        path.relative_to(release_root).as_posix(): path.read_bytes()
        for path in sorted(release_root.rglob("*"))
        if path.is_file()
    }
    plan = training.load_training_plan(
        config_path,
        dataset_root_override=workspace,
        manifest_path_override=release_manifest,
        repository_root=repository,
    )

    def cache_writing_trainer(active_plan: training.TrainingPlan) -> object:
        with training.runtime_dataset_descriptor(active_plan) as descriptor:
            root = runtime_dataset_root(active_plan, descriptor)
            # Emulate Ultralytics writing a label cache beside the label directory.
            cache = root / "train" / "labels.cache"
            cache.parent.mkdir(parents=True, exist_ok=True)
            cache.write_text("simulated cache", encoding="utf-8")
            return {"cache": str(cache)}

    training.run_training(plan, cache_writing_trainer)

    assert (workspace / "train" / "labels.cache").is_file()
    assert not (release_root / "train" / "labels.cache").exists()
    assert not list(release_root.rglob("*.cache"))
    after = {
        path.relative_to(release_root).as_posix(): path.read_bytes()
        for path in sorted(release_root.rglob("*"))
        if path.is_file()
    }
    assert after == release_snapshot


# ------------------------------------------------------ failure sanitisation


def test_failure_summary_is_sanitised_of_local_paths(tmp_path: Path) -> None:
    plan = released_plan(tmp_path)
    leaked = (
        f"Dataset '{plan.dataset_yaml_path}' images not found, missing path "
        f"'{plan.dataset_root}\\images\\val'. Manifest {plan.manifest_path.as_posix()} "
        f"and repository {plan.repository_root} and run {plan.run_directory}."
    )

    def failing_trainer(_: training.TrainingPlan) -> object:
        raise RuntimeError(leaked)

    with pytest.raises(training.TrainingPipelineError):
        training.run_training(plan, failing_trainer)

    metadata = json.loads((plan.run_directory / "run_metadata.json").read_text(encoding="utf-8"))
    summary = metadata["failure_summary"]
    assert metadata["status"] == "failed"
    assert "RuntimeError" in summary
    assert "images not found" in summary
    for absolute in (
        str(plan.dataset_root),
        plan.dataset_root.as_posix(),
        str(plan.manifest_path),
        plan.manifest_path.as_posix(),
        str(plan.repository_root),
        plan.repository_root.as_posix(),
        str(tmp_path),
        tmp_path.as_posix(),
    ):
        assert absolute not in summary
    assert "<dataset-root>" in summary or "<local-path>" in summary


@pytest.mark.parametrize("template", [
    "missing path '{native}\\images\\val'",
    "missing path '{posix}/images/val'",
    "Dataset '{doubled}/dataset.yaml' error",
    "cache written to {native}\\labels\\train.cache",
])
def test_path_variants_are_all_sanitised(tmp_path: Path, template: str) -> None:
    plan = released_plan(tmp_path)
    root = plan.dataset_root
    posix = root.as_posix()
    text = template.format(
        native=str(root), posix=posix, doubled=f"{posix[:2]}//{posix[3:]}"
    )

    sanitised = training._sanitise_local_paths(text, plan)

    assert str(root) not in sanitised
    assert posix not in sanitised
    assert "C:" not in sanitised.replace("<", "").replace(">", "")


def test_runtime_descriptor_path_is_sanitised_from_failure_text(tmp_path: Path) -> None:
    plan = released_plan(tmp_path)
    with training.runtime_dataset_descriptor(plan) as descriptor:
        text = f"RuntimeError: Dataset '{descriptor}' error"
        sanitised = training._sanitise_local_paths(text, plan, descriptor)

    assert str(descriptor) not in sanitised
    assert descriptor.as_posix() not in sanitised
    assert "RuntimeError" in sanitised


def test_successful_run_metadata_contains_no_absolute_paths(tmp_path: Path) -> None:
    plan = released_plan(tmp_path)

    training.run_training(plan, lambda _: {"ok": True})

    metadata = (plan.run_directory / "run_metadata.json").read_text(encoding="utf-8")
    resolved = (plan.run_directory / "resolved_training_config.json").read_text(encoding="utf-8")
    reference = (plan.run_directory / "dataset_reference.json").read_text(encoding="utf-8")
    for document in (metadata, resolved, reference):
        assert str(plan.dataset_root) not in document
        assert plan.dataset_root.as_posix() not in document
        assert str(plan.manifest_path) not in document
        assert plan.manifest_path.as_posix() not in document


# ------------------------------------------------- workspace integrity


def corrupt_file(path: Path) -> None:
    """Change one file's bytes while keeping it structurally parseable.

    A structurally valid mutation proves the checksum gate rejects the file
    rather than an earlier syntax check firing first.
    """
    path.write_bytes(path.read_bytes() + b"\n# tampered\n")


def load_evidence(release_root: Path) -> dict[str, object]:
    return json.loads((release_root / training.CHECKSUM_EVIDENCE_FILENAME).read_text(encoding="utf-8"))


def save_evidence(release_root: Path, payload: object) -> None:
    (release_root / training.CHECKSUM_EVIDENCE_FILENAME).write_text(
        json.dumps(payload), encoding="utf-8"
    )


def load_released_plan(
    repository: Path, workspace: Path, release_manifest: Path, config_path: Path
) -> training.TrainingPlan:
    return training.load_training_plan(
        config_path,
        dataset_root_override=workspace,
        manifest_path_override=release_manifest,
        repository_root=repository,
    )


def test_faithful_workspace_passes_checksum_verification(tmp_path: Path) -> None:
    repository, _, workspace, release_manifest, config_path = create_released_fixture(tmp_path)

    plan = load_released_plan(repository, workspace, release_manifest, config_path)

    assert training.dry_run(plan)["status"] == "dry_run_valid"
    assert plan.release_checksums_reference == training.EXTERNAL_CHECKSUM_REFERENCE
    assert plan.release_checksums_checksum is not None
    assert len(plan.release_checksums_checksum) == 64


@pytest.mark.parametrize(
    "relative",
    ["dataset.yaml", "release_manifest.json", "train/images/person_001.jpg", "train/labels/person_001.txt"],
)
def test_modified_workspace_file_fails_verification(tmp_path: Path, relative: str) -> None:
    repository, _, workspace, release_manifest, config_path = create_released_fixture(tmp_path)
    corrupt_file(workspace / relative)

    with pytest.raises(training.TrainingPipelineError, match="does not match the approved release checksum"):
        load_released_plan(repository, workspace, release_manifest, config_path)


def test_missing_checksummed_workspace_file_fails_verification(tmp_path: Path) -> None:
    """Delete a file only the checksum gate covers, so this proves that gate."""
    repository, _, workspace, release_manifest, config_path = create_released_fixture(tmp_path)
    (workspace / "release_manifest.json").unlink()

    with pytest.raises(training.TrainingPipelineError, match="missing a released file"):
        load_released_plan(repository, workspace, release_manifest, config_path)


def test_missing_checksum_evidence_is_rejected(tmp_path: Path) -> None:
    repository, release_root, workspace, release_manifest, config_path = create_released_fixture(tmp_path)
    (release_root / training.CHECKSUM_EVIDENCE_FILENAME).unlink()

    with pytest.raises(training.TrainingPipelineError, match="require release_checksums.json"):
        load_released_plan(repository, workspace, release_manifest, config_path)


def test_malformed_checksum_evidence_is_rejected(tmp_path: Path) -> None:
    repository, release_root, workspace, release_manifest, config_path = create_released_fixture(tmp_path)
    (release_root / training.CHECKSUM_EVIDENCE_FILENAME).write_text("not json", encoding="utf-8")

    with pytest.raises(training.TrainingPipelineError, match="not valid JSON"):
        load_released_plan(repository, workspace, release_manifest, config_path)


def test_non_object_checksum_evidence_is_rejected(tmp_path: Path) -> None:
    repository, release_root, workspace, release_manifest, config_path = create_released_fixture(tmp_path)
    save_evidence(release_root, ["not", "an", "object"])

    with pytest.raises(training.TrainingPipelineError, match="root must be an object"):
        load_released_plan(repository, workspace, release_manifest, config_path)


def test_unsupported_checksum_algorithm_is_rejected(tmp_path: Path) -> None:
    repository, release_root, workspace, release_manifest, config_path = create_released_fixture(tmp_path)
    evidence = load_evidence(release_root)
    evidence["algorithm"] = "md5"
    save_evidence(release_root, evidence)

    with pytest.raises(training.TrainingPipelineError, match="sha256 algorithm"):
        load_released_plan(repository, workspace, release_manifest, config_path)


@pytest.mark.parametrize("digest", ["", "abc", "z" * 64, "A" * 63, 12345, None])
def test_invalid_checksum_digest_is_rejected(tmp_path: Path, digest: object) -> None:
    repository, release_root, workspace, release_manifest, config_path = create_released_fixture(tmp_path)
    evidence = load_evidence(release_root)
    evidence["files"]["dataset.yaml"] = digest  # type: ignore[index]
    save_evidence(release_root, evidence)

    with pytest.raises(training.TrainingPipelineError, match="invalid SHA-256 digest"):
        load_released_plan(repository, workspace, release_manifest, config_path)


@pytest.mark.parametrize("unsafe", ["../escape.txt", "C:/absolute/escape.txt", "/absolute/escape.txt", "\\\\server\\share\\x.txt", "https://example.invalid/x.png"])
def test_unsafe_checksum_paths_are_rejected(tmp_path: Path, unsafe: str) -> None:
    repository, release_root, workspace, release_manifest, config_path = create_released_fixture(tmp_path)
    evidence = load_evidence(release_root)
    evidence["files"][unsafe] = "c" * 64  # type: ignore[index]
    save_evidence(release_root, evidence)

    with pytest.raises(training.TrainingPipelineError, match="release checksum path"):
        load_released_plan(repository, workspace, release_manifest, config_path)


def test_empty_checksum_file_list_is_rejected(tmp_path: Path) -> None:
    repository, release_root, workspace, release_manifest, config_path = create_released_fixture(tmp_path)
    evidence = load_evidence(release_root)
    evidence["files"] = {}
    save_evidence(release_root, evidence)

    with pytest.raises(training.TrainingPipelineError, match="at least one checksummed file"):
        load_released_plan(repository, workspace, release_manifest, config_path)


@pytest.mark.parametrize("identity", ["d" * 64, "not-a-digest", ""])
def test_release_identity_mismatch_is_rejected(tmp_path: Path, identity: str) -> None:
    repository, release_root, workspace, release_manifest, config_path = create_released_fixture(tmp_path)
    evidence = load_evidence(release_root)
    evidence["release_identity"] = identity
    save_evidence(release_root, evidence)

    with pytest.raises(training.TrainingPipelineError):
        load_released_plan(repository, workspace, release_manifest, config_path)


def test_manifest_without_recorded_identity_is_rejected(tmp_path: Path) -> None:
    repository, release_root, workspace, release_manifest, config_path = create_released_fixture(tmp_path)
    manifest = json.loads(release_manifest.read_text(encoding="utf-8"))
    manifest["quality"].pop("checksums")
    text = json.dumps(manifest)
    release_manifest.write_text(text, encoding="utf-8")
    (workspace / "release_manifest.json").write_text(text, encoding="utf-8")
    write_release_checksums(release_root, "a" * 64)

    with pytest.raises(training.TrainingPipelineError, match="release identity to cross-check"):
        load_released_plan(repository, workspace, release_manifest, config_path)


# ------------------------------------------------------- extra-file policy


@pytest.mark.parametrize(
    "relative", ["train/images/unlisted.png", "train/images/unlisted.jpg", "train/labels/unlisted.txt"]
)
def test_unexpected_training_files_are_rejected(tmp_path: Path, relative: str) -> None:
    repository, _, workspace, release_manifest, config_path = create_released_fixture(tmp_path)
    (workspace / relative).write_text("smuggled", encoding="utf-8")

    with pytest.raises(training.TrainingPipelineError, match="approved release does not include"):
        load_released_plan(repository, workspace, release_manifest, config_path)


@pytest.mark.parametrize("relative", ["train/labels.cache", "train/images/train.cache", "train/labels/val.cache"])
def test_ultralytics_cache_files_are_allowed(tmp_path: Path, relative: str) -> None:
    repository, _, workspace, release_manifest, config_path = create_released_fixture(tmp_path)
    (workspace / relative).write_text("simulated cache", encoding="utf-8")

    plan = load_released_plan(repository, workspace, release_manifest, config_path)

    assert training.dry_run(plan)["status"] == "dry_run_valid"


def test_unrelated_non_training_files_are_tolerated(tmp_path: Path) -> None:
    repository, _, workspace, release_manifest, config_path = create_released_fixture(tmp_path)
    (workspace / "train" / "images" / "notes.md").write_text("operator note", encoding="utf-8")

    plan = load_released_plan(repository, workspace, release_manifest, config_path)

    assert training.dry_run(plan)["status"] == "dry_run_valid"


# --------------------------------------------- release immutability / gating


def test_verification_leaves_the_authoritative_release_unchanged(tmp_path: Path) -> None:
    repository, release_root, workspace, release_manifest, config_path = create_released_fixture(tmp_path)
    before = {
        path.relative_to(release_root).as_posix(): (path.read_bytes(), path.stat().st_mtime_ns)
        for path in sorted(release_root.rglob("*"))
        if path.is_file()
    }

    training.dry_run(load_released_plan(repository, workspace, release_manifest, config_path))

    after = {
        path.relative_to(release_root).as_posix(): (path.read_bytes(), path.stat().st_mtime_ns)
        for path in sorted(release_root.rglob("*"))
        if path.is_file()
    }
    assert after == before
    assert not list(release_root.rglob("*.cache"))


def test_dry_run_rejects_a_corrupted_workspace(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    repository, _, workspace, release_manifest, config_path = create_released_fixture(tmp_path)
    corrupt_file(workspace / "train" / "images" / "person_001.jpg")
    monkeypatch.setattr(training, "REPOSITORY_ROOT", repository)

    exit_code = training.main([
        "--config", str(config_path),
        "--dataset-root", str(workspace),
        "--manifest-path", str(release_manifest),
        "--dry-run",
    ])

    assert exit_code == 1
    assert "does not match the approved release checksum" in capsys.readouterr().err


def test_confirmed_training_rejects_the_same_corrupted_workspace(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    repository, _, workspace, release_manifest, config_path = create_released_fixture(tmp_path)
    corrupt_file(workspace / "train" / "images" / "person_001.jpg")
    monkeypatch.setattr(training, "REPOSITORY_ROOT", repository)
    monkeypatch.setattr(
        training, "default_trainer", lambda _: pytest.fail("trainer must not be invoked")
    )

    exit_code = training.main([
        "--config", str(config_path),
        "--dataset-root", str(workspace),
        "--manifest-path", str(release_manifest),
        "--confirm-training",
    ])

    assert exit_code == 1
    assert "does not match the approved release checksum" in capsys.readouterr().err
    assert not (repository / "artifacts").exists()


def test_integrity_failure_happens_before_any_trainer_import(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    repository, _, workspace, release_manifest, config_path = create_released_fixture(tmp_path)
    corrupt_file(workspace / "train" / "labels" / "person_001.txt")
    monkeypatch.setitem(sys.modules, "ultralytics", None)

    with pytest.raises(training.TrainingPipelineError, match="does not match the approved release checksum"):
        load_released_plan(repository, workspace, release_manifest, config_path)


def test_release_checksum_evidence_is_recorded_in_run_metadata(tmp_path: Path) -> None:
    repository, _, workspace, release_manifest, config_path = create_released_fixture(tmp_path)
    plan = load_released_plan(repository, workspace, release_manifest, config_path)

    training.run_training(plan, lambda _: {"ok": True})

    metadata = json.loads((plan.run_directory / "run_metadata.json").read_text(encoding="utf-8"))
    assert metadata["release_checksums_reference"] == training.EXTERNAL_CHECKSUM_REFERENCE
    assert metadata["release_checksums_checksum_sha256"] == plan.release_checksums_checksum
    assert str(release_manifest.parent) not in json.dumps(metadata)


def test_local_manifest_flow_does_not_require_checksum_evidence(tmp_path: Path) -> None:
    """The repository-relative, non-released flow is unchanged by this gate."""
    repository, dataset_root, config_path = create_fixture(tmp_path)

    plan = load_plan(repository, dataset_root, config_path)

    assert training.dry_run(plan)["status"] == "dry_run_valid"
    assert plan.release_checksums_reference is None
    assert plan.release_checksums_checksum is None
