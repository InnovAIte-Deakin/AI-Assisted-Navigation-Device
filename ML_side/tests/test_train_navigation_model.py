"""Local-only tests for the controlled navigation-model training preflight."""

from __future__ import annotations

import json
import sys
from pathlib import Path

import pytest


ML_SIDE_DIR = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ML_SIDE_DIR / "training"))
sys.path.insert(0, str(ML_SIDE_DIR / "tools"))

import train_navigation_model as training


SAMPLE_MANIFEST = ML_SIDE_DIR / "datasets" / "sample_manifest.json"


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
