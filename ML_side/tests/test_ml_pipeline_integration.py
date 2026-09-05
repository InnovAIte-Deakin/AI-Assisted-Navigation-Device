from __future__ import annotations

"""Integration coverage for the WalkBuddy ML pipeline.

Checkpoints:
1. Inspect a synthetic dataset and generate a valid candidate manifest.
2. Build a controlled release from the generated manifest.
3. Run training preflight and mocked training against the released dataset.
4. Validate and evaluate a mocked candidate model using the real pipeline code.
5. Confirm invalid source data is blocked before release and training.

All data is synthetic and local. Model inference/training/evaluation objects are
mocked where required; no model weights or network access are used.
"""


import base64
import json
import sys
from pathlib import Path


# ---------------------------------------------------------------------------
# Existing WalkBuddy ML modules
# ---------------------------------------------------------------------------

ML_SIDE_DIR = Path(__file__).resolve().parents[1]
TOOLS_DIR = ML_SIDE_DIR / "tools"
TRAINING_DIR = ML_SIDE_DIR / "training"

sys.path.insert(0, str(TOOLS_DIR))
sys.path.insert(0, str(TRAINING_DIR))

import build_navigation_dataset_release as builder
import evaluate_current_model as evaluator
import inspect_candidate_dataset as inspector
import train_navigation_model as training
import validate_candidate_model as candidate_validator
import validate_dataset_manifest as manifest_validator


# ---------------------------------------------------------------------------
# Tiny fictional image fixture.
#
# No production dataset, downloaded dataset, or large model weights are used.
# ---------------------------------------------------------------------------

IMAGE_BYTES = base64.b64decode(
    "R0lGODlhAQABAIAAAAAAAP///ywAAAAAAQABAAACAUwAOw=="
)


# ---------------------------------------------------------------------------
# Shared fixture helpers
# ---------------------------------------------------------------------------

def write_json(path: Path, value: object) -> Path:
    """Write deterministic local JSON fixture data."""

    path.write_text(
        json.dumps(value, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    return path


def create_fictional_dataset(tmp_path: Path) -> tuple[Path, Path]:
    """Create a tiny local YOLO-format dataset."""

    dataset_root = tmp_path / "fictional_dataset"
    dataset_root.mkdir()

    samples = [
        ("train", "train_scene.png"),
        ("validation", "validation_scene.png"),
    ]

    for split, filename in samples:
        image_path = (
            dataset_root
            / split
            / "images"
            / filename
        )

        label_path = (
            dataset_root
            / split
            / "labels"
            / Path(filename).with_suffix(".txt")
        )

        image_path.parent.mkdir(
            parents=True,
            exist_ok=True,
        )

        label_path.parent.mkdir(
            parents=True,
            exist_ok=True,
        )

        image_path.write_bytes(
            IMAGE_BYTES + filename.encode("utf-8")
        )

        # YOLO:
        # class_id x_center y_center width height
        label_path.write_text(
            "0 0.5 0.5 0.2 0.2\n",
            encoding="utf-8",
        )

    dataset_yaml = dataset_root / "dataset.yaml"

    dataset_yaml.write_text(
        "\n".join(
            [
                "path: .",
                "train: train/images",
                "val: validation/images",
                "names:",
                "  0: fictional-person",
            ]
        )
        + "\n",
        encoding="utf-8",
    )

    return dataset_root, dataset_yaml


def fictional_metadata() -> dict[str, object]:
    """Metadata required by candidate-dataset inspection."""

    return {
        "dataset": {
            "id": "fictional-integration-source",
            "name": "Fictional integration dataset",
            "source_version": "fictional-v1",
            "description": (
                "Temporary integration-test fixture only."
            ),
            "release_date": "2026-08-16",
            "release_decision": "under_review",
        },

        "source_provenance": {
            "source_reference": (
                "example://fictional/integration-source"
            ),
            "accessed_on": "2026-08-16",
            "original_source": (
                "Generated integration-test fixture."
            ),
            "publisher": "WalkBuddy test suite",
        },

        "licence": {
            "name": "Fictional integration-test licence",
            "evidence_reference": (
                "example://fictional/licence"
            ),
            "machine_learning_use_permitted": True,
            "modification_permitted": True,
            "redistribution_permitted": False,
            "attribution_required": False,
            "attribution_requirements": "",
            "restrictions": "Test-only fixture.",
            "reviewer": "Integration test",
            "review_date": "2026-08-16",
            "review_decision": "approved",
        },

        "storage_release": {
            "authoritative_storage_reference": (
                "example://fictional/storage"
            ),
            "git_safe_metadata_only": True,
            "release_version": "fictional-v1",
        },

        "quality_review_status": "completed",

        "known_limitations": [
            (
                "Synthetic two-image dataset used only "
                "for integration testing."
            )
        ],

        "class_mapping": [
            {
                "source_class_id": 0,
                "target_class_id": 0,
                "target_class_name": "person",
                "mapping_rationale": (
                    "Explicit fictional mapping "
                    "for integration testing."
                ),
            }
        ],

        "excluded_source_classes": [],
        "unmapped_source_classes": [],
    }


def create_group_map() -> dict[str, object]:
    """Assign explicit independent groups to both samples."""

    return {
        "groups": {
            "train/images/train_scene.png": (
                "group-train-001"
            ),
            "validation/images/validation_scene.png": (
                "group-validation-001"
            ),
        }
    }


def release_mapping_config() -> dict[str, object]:
    """Mapping and reviewed metadata for controlled release creation."""

    return {
        "schema_version": "1.0.0",

        "source_taxonomy": [
            {
                "id": 0,
                "name": "fictional-person",
            },
        ],

        "class_mapping": [
            {
                "source_class_id": 0,
                "target_class_id": 0,
                "target_class_name": "person",
                "mapping_rationale": (
                    "Explicit integration-test mapping."
                ),
            }
        ],

        "excluded_source_classes": [],
        "unmapped_source_classes": [],

        "empty_image_policy": "retain_negative",

        "release_metadata": {
            "dataset": {
                "id": "fictional-integration-release",
                "name": "Fictional integration release",
                "source_version": "fictional-release-v1",
                "description": (
                    "Temporary integration-test release."
                ),
                "release_date": "2026-08-16",
                "release_decision": (
                    "approved_for_training"
                ),
            },

            "source_provenance": {
                "source_reference": (
                    "example://fictional/integration-source"
                ),
                "accessed_on": "2026-08-16",
                "original_source": (
                    "Generated integration-test fixture."
                ),
                "publisher": "WalkBuddy test suite",
            },

            "licence": {
                "name": (
                    "Fictional integration-test licence"
                ),
                "evidence_reference": (
                    "example://fictional/licence"
                ),
                "machine_learning_use_permitted": True,
                "modification_permitted": True,
                "redistribution_permitted": False,
                "attribution_required": False,
                "attribution_requirements": "",
                "restrictions": "Test-only fixture.",
                "reviewer": "Integration test",
                "review_date": "2026-08-16",
                "review_decision": "approved",
            },

            "storage_release": {
                "authoritative_storage_reference": (
                    "example://fictional/release"
                ),
                "git_safe_metadata_only": True,
                "release_version": "v1",
            },

            "quality_review_status": "completed",

            "known_limitations": [
                "Synthetic integration-test release only."
            ],
        },
    }


def training_config() -> dict[str, object]:
    """Training preflight configuration for the fictional release."""

    return {
        "schema_version": "1.0.0",

        "experiment_name": (
            "ML Pipeline Integration Test"
        ),

        "dataset": {
            "manifest_path": "release_manifest.json",
            "yaml_path": "dataset.yaml",
            "inspection_report_path": None,
            "stage": (
                "approved_for_internal_training"
            ),
        },

        "model": {
            "architecture_path": "architecture.yaml",
            "initial_weights_path": None,
        },

        "training": {
            "epochs": 1,
            "image_size": 32,
            "batch_size": 1,
            "device": "cpu",
            "workers": 1,
            "seed": 17,
            "optimizer": "AdamW",
            "learning_rate": 0.001,
            "confidence": 0.001,
            "iou": 0.7,
            "deterministic": True,
            "resume_behavior": "never",
        },

        "output": {
            "root": "artifacts/integration_training",
        },

        "notes": (
            "Temporary fictional configuration used only "
            "by the ML pipeline integration test."
        ),
    }


# ---------------------------------------------------------------------------
# Mock model/evaluation objects used by Checkpoint 4.
# ---------------------------------------------------------------------------

APPROVED_NAMES = [name for _, name in manifest_validator.APPROVED_TAXONOMY]


class FakeMetricsBox:
    """Mock per-class validation metrics."""

    ap_class_index = list(range(len(APPROVED_NAMES)))

    p = [
        0.90,
        0.88,
        0.86,
        0.84,
        0.82,
        0.80,
        0.78,
        0.76,
    ]

    r = [
        0.85,
        0.83,
        0.81,
        0.79,
        0.77,
        0.75,
        0.73,
        0.71,
    ]

    ap50 = [
        0.92,
        0.90,
        0.88,
        0.86,
        0.84,
        0.82,
        0.80,
        0.78,
    ]

    ap = [
        0.75,
        0.73,
        0.71,
        0.69,
        0.67,
        0.65,
        0.63,
        0.61,
    ]


class FakeEvaluationMetrics:
    """Mock aggregate Ultralytics validation output."""

    results_dict = {
        "metrics/precision(B)": 0.83,
        "metrics/recall(B)": 0.78,
        "metrics/mAP50(B)": 0.85,
        "metrics/mAP50-95(B)": 0.68,
    }

    speed = {
        "preprocess": 1.0,
        "inference": 5.0,
        "postprocess": 1.0,
    }

    box = FakeMetricsBox()


class FakeIntegratedModel:
    """Mock model implementing smoke inference and evaluation."""

    names = dict(enumerate(APPROVED_NAMES))
    task = "detect"

    def __init__(self) -> None:
        self.predict_calls: list[dict[str, object]] = []
        self.validation_arguments: dict[str, object] | None = None

    def predict(self, **kwargs: object) -> list[object]:
        self.predict_calls.append(kwargs)
        return [object()]

    def val(self, **kwargs: object) -> FakeEvaluationMetrics:
        self.validation_arguments = kwargs
        return FakeEvaluationMetrics()


# ===========================================================================
# CHECKPOINT 1
# ===========================================================================

def test_dataset_inspection_generates_valid_manifest(
    tmp_path: Path,
) -> None:

    dataset_root, dataset_yaml = (
        create_fictional_dataset(tmp_path)
    )

    metadata_path = write_json(
        tmp_path / "metadata.json",
        fictional_metadata(),
    )

    group_map_path = write_json(
        tmp_path / "groups.json",
        create_group_map(),
    )

    report, candidate_manifest = (
        inspector.inspect_dataset(
            dataset_root,
            dataset_yaml,
            metadata_path=metadata_path,
            group_map_path=group_map_path,
            decode_images=False,
            checksums=True,
            generate_manifest=True,
            execution_time_utc=(
                "2026-08-16T00:00:00Z"
            ),
        )
    )

    assert report["quality_verdict"] in {
        "pass",
        "pass_with_warnings",
    }

    assert (
        report["candidate_manifest"]["generated"]
        is True
    )

    assert candidate_manifest is not None

    validation_issues = (
        manifest_validator.validate_manifest(
            candidate_manifest,
            dataset_root=dataset_root,
            check_files=True,
        )
    )

    assert validation_issues == []

    assert (
        candidate_manifest["dataset"]["id"]
        == "fictional-integration-source"
    )


# ===========================================================================
# CHECKPOINT 2
# ===========================================================================

def test_generated_manifest_builds_controlled_release(
    tmp_path: Path,
) -> None:

    dataset_root, dataset_yaml = (
        create_fictional_dataset(tmp_path)
    )

    metadata_path = write_json(
        tmp_path / "metadata.json",
        fictional_metadata(),
    )

    group_map_path = write_json(
        tmp_path / "groups.json",
        create_group_map(),
    )

    report, candidate_manifest = (
        inspector.inspect_dataset(
            dataset_root,
            dataset_yaml,
            metadata_path=metadata_path,
            group_map_path=group_map_path,
            decode_images=False,
            checksums=True,
            generate_manifest=True,
            execution_time_utc=(
                "2026-08-16T00:00:00Z"
            ),
        )
    )

    assert candidate_manifest is not None

    manifest_path = write_json(
        tmp_path / "candidate_manifest.json",
        candidate_manifest,
    )

    inspection_report_path = write_json(
        tmp_path / "inspection_report.json",
        report,
    )

    mapping_path = write_json(
        tmp_path / "mapping.json",
        release_mapping_config(),
    )

    output_root = tmp_path / "release_output"

    release_plan = builder.create_release_plan(
        source_root=dataset_root,
        source_yaml_path=dataset_yaml,
        source_manifest_path=manifest_path,
        inspection_report_path=inspection_report_path,
        mapping_path=mapping_path,
        output_root=output_root,
        release_name="fictional-integration-release",
        release_version="v1",
    )

    build_report = builder.build_release(
        release_plan,
        confirm_build=True,
    )

    release_root = (
        output_root
        / "fictional-integration-release"
        / "v1"
    )

    assert build_report["status"] == "completed"

    assert (release_root / "dataset.yaml").is_file()
    assert (release_root / "release_manifest.json").is_file()
    assert (release_root / "release_checksums.json").is_file()

    released_manifest = json.loads(
        (
            release_root
            / "release_manifest.json"
        ).read_text(
            encoding="utf-8"
        )
    )

    assert (
        released_manifest["dataset"]["release_decision"]
        == "approved_for_training"
    )

    validation_issues = (
        manifest_validator.validate_manifest(
            released_manifest,
            dataset_root=release_root,
            check_files=True,
        )
    )

    assert validation_issues == []


# ===========================================================================
# CHECKPOINT 3
# ===========================================================================

def test_released_dataset_reaches_mocked_training(
    tmp_path: Path,
) -> None:

    dataset_root, dataset_yaml = (
        create_fictional_dataset(tmp_path)
    )

    metadata_path = write_json(
        tmp_path / "metadata.json",
        fictional_metadata(),
    )

    group_map_path = write_json(
        tmp_path / "groups.json",
        create_group_map(),
    )

    inspection_report, candidate_manifest = (
        inspector.inspect_dataset(
            dataset_root,
            dataset_yaml,
            metadata_path=metadata_path,
            group_map_path=group_map_path,
            decode_images=False,
            checksums=True,
            generate_manifest=True,
            execution_time_utc=(
                "2026-08-16T00:00:00Z"
            ),
        )
    )

    assert candidate_manifest is not None

    source_manifest_path = write_json(
        tmp_path / "candidate_manifest.json",
        candidate_manifest,
    )

    inspection_report_path = write_json(
        tmp_path / "inspection_report.json",
        inspection_report,
    )

    mapping_path = write_json(
        tmp_path / "mapping.json",
        release_mapping_config(),
    )

    release_output = tmp_path / "release_output"

    release_plan = builder.create_release_plan(
        source_root=dataset_root,
        source_yaml_path=dataset_yaml,
        source_manifest_path=source_manifest_path,
        inspection_report_path=inspection_report_path,
        mapping_path=mapping_path,
        output_root=release_output,
        release_name="fictional-integration-release",
        release_version="v1",
    )

    release_report = builder.build_release(
        release_plan,
        confirm_build=True,
    )

    assert release_report["status"] == "completed"

    release_root = (
        release_output
        / "fictional-integration-release"
        / "v1"
    )

    repository = tmp_path / "training_repository"
    repository.mkdir()

    released_manifest = json.loads(
        (
            release_root
            / "release_manifest.json"
        ).read_text(
            encoding="utf-8"
        )
    )

    write_json(
        repository / "release_manifest.json",
        released_manifest,
    )

    (
        repository / "architecture.yaml"
    ).write_text(
        "nc: 8\n",
        encoding="utf-8",
    )

    config_path = write_json(
        repository / "training.json",
        training_config(),
    )

    training_plan = training.load_training_plan(
        config_path,
        dataset_root_override=release_root,
        repository_root=repository,
    )

    assert (
        training_plan.dataset_id
        == "fictional-integration-release"
    )

    assert (
        training_plan.manifest_release_decision
        == "approved_for_training"
    )

    dry_run_result = training.dry_run(
        training_plan
    )

    assert (
        dry_run_result["status"]
        == "dry_run_valid"
    )

    assert not training_plan.run_directory.exists()

    def fake_trainer(
        received_plan: training.TrainingPlan,
    ) -> dict[str, object]:

        candidate_model = (
            received_plan.run_directory
            / "candidate.pt"
        )

        candidate_model.write_bytes(
            b"fictional-integration-model"
        )

        return {
            "status": "mock_training_complete",
            "candidate_model": "candidate.pt",
        }

    training_result = training.run_training(
        training_plan,
        trainer=fake_trainer,
    )

    assert training_result == {
        "status": "mock_training_complete",
        "candidate_model": "candidate.pt",
    }

    assert (
        training_plan.run_directory
        / "candidate.pt"
    ).is_file()

    assert (
        training_plan.run_directory
        / "run_metadata.json"
    ).is_file()

    run_metadata = json.loads(
        (
            training_plan.run_directory
            / "run_metadata.json"
        ).read_text(
            encoding="utf-8"
        )
    )

    assert run_metadata["status"] == "succeeded"

    assert (
        run_metadata["dataset_release"]["id"]
        == "fictional-integration-release"
    )


# ===========================================================================
# CHECKPOINT 4
# ===========================================================================

def test_mocked_candidate_reaches_validation_and_evaluation(
    tmp_path: Path,
    monkeypatch,
) -> None:

    dataset_root, dataset_yaml = (
        create_fictional_dataset(tmp_path)
    )

    metadata_path = write_json(
        tmp_path / "metadata.json",
        fictional_metadata(),
    )

    group_map_path = write_json(
        tmp_path / "groups.json",
        create_group_map(),
    )

    inspection_report, candidate_manifest = (
        inspector.inspect_dataset(
            dataset_root,
            dataset_yaml,
            metadata_path=metadata_path,
            group_map_path=group_map_path,
            decode_images=False,
            checksums=True,
            generate_manifest=True,
            execution_time_utc=(
                "2026-08-16T00:00:00Z"
            ),
        )
    )

    assert candidate_manifest is not None

    source_manifest_path = write_json(
        tmp_path / "candidate_manifest.json",
        candidate_manifest,
    )

    inspection_report_path = write_json(
        tmp_path / "inspection_report.json",
        inspection_report,
    )

    mapping_path = write_json(
        tmp_path / "mapping.json",
        release_mapping_config(),
    )

    release_output = tmp_path / "release_output"

    release_plan = builder.create_release_plan(
        source_root=dataset_root,
        source_yaml_path=dataset_yaml,
        source_manifest_path=source_manifest_path,
        inspection_report_path=inspection_report_path,
        mapping_path=mapping_path,
        output_root=release_output,
        release_name="fictional-integration-release",
        release_version="v1",
    )

    builder.build_release(
        release_plan,
        confirm_build=True,
    )

    release_root = (
        release_output
        / "fictional-integration-release"
        / "v1"
    )

    repository = tmp_path / "training_repository"
    repository.mkdir()

    released_manifest = json.loads(
        (
            release_root
            / "release_manifest.json"
        ).read_text(
            encoding="utf-8"
        )
    )

    write_json(
        repository / "release_manifest.json",
        released_manifest,
    )

    (
        repository / "architecture.yaml"
    ).write_text(
        "nc: 8\n",
        encoding="utf-8",
    )

    config_path = write_json(
        repository / "training.json",
        training_config(),
    )

    training_plan = training.load_training_plan(
        config_path,
        dataset_root_override=release_root,
        repository_root=repository,
    )

    def fake_trainer(
        received_plan: training.TrainingPlan,
    ) -> dict[str, object]:

        candidate_path = (
            received_plan.run_directory
            / "candidate.pt"
        )

        candidate_path.write_bytes(
            b"fictional-integration-model"
        )

        return {
            "candidate_model": "candidate.pt",
        }

    training.run_training(
        training_plan,
        trainer=fake_trainer,
    )

    candidate_path = (
        training_plan.run_directory
        / "candidate.pt"
    )

    assert candidate_path.is_file()

    smoke_image = (
        release_root
        / "images"
        / "train"
        / "train_scene.png"
    )

    assert smoke_image.is_file()

    validation_model = FakeIntegratedModel()

    candidate_report = (
        candidate_validator.run_validation(
            candidate_path=candidate_path,
            output_path=(
                tmp_path
                / "candidate_validation"
            ),
            smoke_image=smoke_image,
            yolo_loader=lambda _: validation_model,
        )
    )

    assert candidate_report["verdict"] == "pass"

    assert (
        candidate_report[
            "candidate"
        ]["ordered_class_names"]
        == APPROVED_NAMES
    )

    validation_statuses = {
        check["name"]: check["status"]
        for check in candidate_report["checks"]
    }

    assert (
        validation_statuses["approved_taxonomy"]
        == "pass"
    )

    assert (
        validation_statuses["smoke_inference"]
        == "pass"
    )

    assert validation_model.predict_calls

    evaluation_model = FakeIntegratedModel()

    evaluation_output = (
        tmp_path / "evaluation"
    )

    monkeypatch.chdir(release_root)

    evaluation_summary = evaluator.evaluate(
        model_path=candidate_path,
        dataset_yaml=(
            release_root / "dataset.yaml"
        ),
        output_path=evaluation_output,
        yolo_loader=lambda _: evaluation_model,
    )

    assert (
        evaluation_summary["mode"]
        == "labelled_validation"
    )

    metrics = (
        evaluation_summary[
            "validation_metrics"
        ]
    )

    assert metrics["precision"] == 0.83
    assert metrics["recall"] == 0.78
    assert metrics["mAP50"] == 0.85
    assert metrics["mAP50_95"] == 0.68

    assert metrics["validation_image_count"] == 1

    assert (
        metrics[
            "per_class_results"
        ]["0"]["class_name"]
        == "person"
    )

    assert (
        evaluation_output
        / "model_metadata.json"
    ).is_file()

    assert (
        evaluation_output
        / "validation_metrics.json"
    ).is_file()

    assert (
        evaluation_output
        / "summary.json"
    ).is_file()

    assert (
        evaluation_output
        / "baseline_report.md"
    ).is_file()


# ===========================================================================
# CHECKPOINT 5
#
# Invalid source data
#       ↓
# Inspection fails
#       ↓
# Candidate manifest withheld
#       ↓
# Release is never created
#       ↓
# Training is never reached
# ===========================================================================

def test_invalid_dataset_is_blocked_before_release_and_training(
    tmp_path: Path,
) -> None:

    dataset_root, dataset_yaml = (
        create_fictional_dataset(tmp_path)
    )

    # Make the YOLO box extend beyond the normalized image boundary.
    invalid_label = (
        dataset_root
        / "train"
        / "labels"
        / "train_scene.txt"
    )

    invalid_label.write_text(
        "0 0.95 0.5 0.2 0.2\n",
        encoding="utf-8",
    )

    metadata_path = write_json(
        tmp_path / "metadata.json",
        fictional_metadata(),
    )

    group_map_path = write_json(
        tmp_path / "groups.json",
        create_group_map(),
    )

    report, candidate_manifest = (
        inspector.inspect_dataset(
            dataset_root,
            dataset_yaml,
            metadata_path=metadata_path,
            group_map_path=group_map_path,
            decode_images=False,
            checksums=True,
            generate_manifest=True,
            execution_time_utc=(
                "2026-08-16T00:00:00Z"
            ),
        )
    )

    # Inspection must fail.
    assert report["quality_verdict"] == "fail"

    # Invalid data must never receive a candidate manifest.
    assert candidate_manifest is None

    assert (
        report["candidate_manifest"]["generated"]
        is False
    )

    error_messages = [
        item["message"]
        for item in report["validation_errors"]
    ]

    assert any(
        "outside normalized YOLO bounds"
        in message
        for message in error_messages
    )

    # No downstream release should exist.
    assert not (
        tmp_path
        / "release_output"
    ).exists()

    # Training should never have been reached.
    assert not (
        tmp_path
        / "training_repository"
    ).exists()

    assert not (
        tmp_path
        / "artifacts"
    ).exists()