"""Controlled, local-only training entry point for a WalkBuddy YOLO candidate.

Dry runs never import Ultralytics or invoke a trainer.  Real training requires
an explicit confirmation and an existing local architecture or checkpoint.
"""

from __future__ import annotations

import argparse
import copy
import hashlib
import json
import math
import os
import platform
import re
import subprocess
import sys
import tempfile
from collections.abc import Callable, Mapping, Sequence
from dataclasses import asdict, dataclass
from datetime import UTC, datetime
from importlib.metadata import PackageNotFoundError, version
from pathlib import Path

TOOLS_DIRECTORY = Path(__file__).resolve().parents[1] / "tools"
if str(TOOLS_DIRECTORY) not in sys.path:
    sys.path.insert(0, str(TOOLS_DIRECTORY))

import validate_dataset_manifest as manifest_validator


REPOSITORY_ROOT = Path(__file__).resolve().parents[2]
TOOL_VERSION = "1.1.0"
ELIGIBLE_STAGES = frozenset({"approved_for_internal_training", "released"})
ALL_STAGES = frozenset(
    {"candidate", "in_review", "approved_for_internal_training", "rejected", "released"}
)
RESUME_BEHAVIOURS = frozenset({"never", "allow", "require"})
EXTERNAL_MANIFEST_REFERENCE = "external-local/manifest.json"


class TrainingPipelineError(Exception):
    """Raised for an ordinary configuration or preflight failure."""


@dataclass(frozen=True)
class TrainingPlan:
    config: dict[str, object]
    repository_root: Path
    dataset_root: Path
    manifest_path: Path
    manifest_reference: str
    dataset_yaml_path: Path
    model_path: Path
    model_kind: str
    output_root: Path
    run_id: str
    run_directory: Path
    config_checksum: str
    manifest_checksum: str
    dataset_yaml_checksum: str
    model_checksum: str
    dataset_id: str
    dataset_source_version: str
    manifest_release_decision: str
    git_commit: str | None
    git_dirty: bool | None


def _load_yaml(path: Path, label: str) -> dict[str, object]:
    try:
        import yaml
    except ImportError as exc:
        raise TrainingPipelineError(f"{label} requires PyYAML; no dependency was installed.") from exc
    try:
        data = yaml.safe_load(path.read_text(encoding="utf-8-sig"))
    except FileNotFoundError as exc:
        raise TrainingPipelineError(f"{label} is missing: {path}") from exc
    except OSError as exc:
        raise TrainingPipelineError(f"{label} could not be read: {path}") from exc
    except yaml.YAMLError as exc:
        raise TrainingPipelineError(f"{label} is not valid YAML: {path}") from exc
    if not isinstance(data, dict):
        raise TrainingPipelineError(f"{label} root must be an object: {path}")
    return data


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as source:
        for chunk in iter(lambda: source.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _safe_relative(value: object, label: str) -> str:
    safe, reason = manifest_validator._is_safe_relative_path(value)
    if not safe:
        raise TrainingPipelineError(f"{label} {reason or 'must be a safe relative path.'}")
    assert isinstance(value, str)
    if re.match(r"^[A-Za-z][A-Za-z0-9+.-]*:", value.strip()):
        raise TrainingPipelineError(f"{label} must not be a URL or URI.")
    return value.strip()


def _resolve_under(root: Path, raw_path: object, label: str) -> Path:
    relative = _safe_relative(raw_path, label)
    resolved = manifest_validator._resolve_dataset_reference(root.resolve(), relative)
    if resolved is None:
        raise TrainingPipelineError(f"{label} resolves outside its controlled root.")
    return resolved


def _resolve_external_manifest(raw_path: Path) -> Path:
    """Resolve a caller-supplied local manifest without persisting its location."""
    raw_value = str(raw_path).strip()
    if not raw_value:
        raise TrainingPipelineError("external manifest path must be a non-empty local JSON file path.")
    if raw_value.startswith(("\\\\", "//")):
        raise TrainingPipelineError("external manifest path must be a local filesystem path, not a UNC path.")
    if re.match(r"^[A-Za-z][A-Za-z0-9+.-]*:", raw_value) and not re.match(r"^[A-Za-z]:[\\/]", raw_value):
        raise TrainingPipelineError("external manifest path must be a local filesystem path, not a URL or URI.")
    candidate_path = Path(raw_value)
    if candidate_path.is_symlink():
        raise TrainingPipelineError("external manifest path must identify an existing regular JSON file.")
    try:
        manifest_path = candidate_path.resolve(strict=True)
    except (OSError, RuntimeError) as exc:
        raise TrainingPipelineError("external manifest path does not identify an existing local file.") from exc
    if manifest_path.suffix.casefold() != ".json":
        raise TrainingPipelineError("external manifest path must identify a JSON file.")
    if not manifest_path.is_file():
        raise TrainingPipelineError("external manifest path must identify an existing regular JSON file.")
    return manifest_path


def _mapping(config: Mapping[str, object], key: str) -> Mapping[str, object]:
    value = config.get(key)
    if not isinstance(value, Mapping):
        raise TrainingPipelineError(f"configuration field {key!r} must be an object.")
    return value


def _only_fields(config: Mapping[str, object], label: str, allowed: set[str]) -> None:
    unknown = sorted(set(config) - allowed)
    if unknown:
        raise TrainingPipelineError(f"{label} contains unsupported field(s): {', '.join(unknown)}.")


def _required_string(config: Mapping[str, object], key: str) -> str:
    value = config.get(key)
    if not isinstance(value, str) or not value.strip():
        raise TrainingPipelineError(f"configuration field {key!r} must be a non-empty string.")
    return value.strip()


def _require_positive_int(value: object, label: str) -> int:
    if not isinstance(value, int) or isinstance(value, bool) or value < 1:
        raise TrainingPipelineError(f"{label} must be a positive integer.")
    return value


def _require_number(value: object, label: str, *, minimum: float = 0.0) -> float:
    if (
        not isinstance(value, (int, float))
        or isinstance(value, bool)
        or not math.isfinite(float(value))
        or float(value) < minimum
    ):
        raise TrainingPipelineError(f"{label} must be a number greater than or equal to {minimum}.")
    return float(value)


def _package_versions() -> dict[str, str]:
    versions: dict[str, str] = {}
    for package in ("ultralytics", "torch", "PyYAML"):
        try:
            versions[package] = version(package)
        except PackageNotFoundError:
            versions[package] = "unavailable"
    return versions


def _git_metadata(repository_root: Path) -> tuple[str | None, bool | None]:
    try:
        commit = subprocess.run(
            ["git", "rev-parse", "HEAD"], cwd=repository_root, text=True, capture_output=True, timeout=5
        )
        status = subprocess.run(
            ["git", "status", "--porcelain"], cwd=repository_root, text=True, capture_output=True, timeout=5
        )
    except (OSError, subprocess.TimeoutExpired):
        return None, None
    if commit.returncode != 0 or status.returncode != 0:
        return None, None
    return commit.stdout.strip() or None, bool(status.stdout.strip())


def _normalise_experiment_name(value: str) -> str:
    normalised = re.sub(r"[^a-z0-9]+", "-", value.casefold()).strip("-")
    if not normalised:
        raise TrainingPipelineError("experiment_name must contain at least one letter or number.")
    return normalised


def _target_taxonomy_from_yaml(dataset_yaml: Mapping[str, object]) -> list[tuple[int, str]]:
    names = dataset_yaml.get("names")
    if isinstance(names, list):
        result = list(enumerate(names))
    elif isinstance(names, Mapping):
        result = []
        for raw_id, name in names.items():
            if isinstance(raw_id, bool):
                raise TrainingPipelineError("dataset YAML names contains a boolean class ID.")
            try:
                class_id = int(raw_id)
            except (TypeError, ValueError) as exc:
                raise TrainingPipelineError("dataset YAML names contains a non-integer class ID.") from exc
            result.append((class_id, name))
        result.sort(key=lambda item: item[0])
    else:
        raise TrainingPipelineError("dataset YAML must define names as a list or ID-to-name object.")
    if any(not isinstance(class_id, int) or not isinstance(name, str) or not name.strip() for class_id, name in result):
        raise TrainingPipelineError("dataset YAML names must contain non-empty string class names.")
    return [(class_id, name.strip()) for class_id, name in result]


def _validate_dataset_paths(dataset_root: Path, dataset_yaml: Mapping[str, object]) -> None:
    yaml_root = _resolve_under(dataset_root, dataset_yaml.get("path", "."), "dataset YAML path")
    if not yaml_root.is_dir():
        raise TrainingPipelineError("dataset YAML path does not resolve to an existing local directory.")
    for canonical, aliases in (("train", ("train",)), ("validation", ("validation", "val"))):
        value = next((dataset_yaml[key] for key in aliases if key in dataset_yaml), None)
        if value is None:
            raise TrainingPipelineError(f"dataset YAML must define the {canonical} split.")
        split_path = _resolve_under(yaml_root, value, f"dataset YAML {canonical} path")
        if not split_path.is_dir():
            raise TrainingPipelineError(f"dataset YAML {canonical} split directory is missing.")
    if "test" in dataset_yaml:
        test_path = _resolve_under(yaml_root, dataset_yaml["test"], "dataset YAML test path")
        if not test_path.is_dir():
            raise TrainingPipelineError("dataset YAML test split directory is missing.")


def _split_directories(dataset_root: Path, dataset_yaml: Mapping[str, object]) -> dict[str, Path]:
    yaml_root = _resolve_under(dataset_root, dataset_yaml.get("path", "."), "dataset YAML path")
    directories: dict[str, Path] = {}
    for canonical, aliases in (("train", ("train",)), ("validation", ("validation", "val")), ("test", ("test",))):
        value = next((dataset_yaml[key] for key in aliases if key in dataset_yaml), None)
        if value is not None:
            directories[canonical] = _resolve_under(yaml_root, value, f"dataset YAML {canonical} path")
    return directories


def _validate_manifest_matches_yaml_splits(
    manifest: Mapping[str, object], dataset_root: Path, dataset_yaml: Mapping[str, object]
) -> None:
    directories = _split_directories(dataset_root, dataset_yaml)
    for split_name, _, sample in manifest_validator._iter_samples(manifest):
        image_path = sample.get("image_path")
        if not isinstance(image_path, str):
            continue
        resolved_image = manifest_validator._resolve_dataset_reference(dataset_root, image_path)
        expected_directory = directories.get(split_name)
        if resolved_image is None or expected_directory is None:
            raise TrainingPipelineError("manifest and dataset YAML do not define matching controlled split paths.")
        try:
            resolved_image.relative_to(expected_directory)
        except ValueError as exc:
            raise TrainingPipelineError(
                f"manifest sample {image_path!r} is outside the dataset YAML {split_name} split directory."
            ) from exc


def _manifest_eligibility(manifest: Mapping[str, object], stage: str) -> None:
    dataset = manifest.get("dataset")
    if not isinstance(dataset, Mapping):
        raise TrainingPipelineError("manifest dataset metadata is missing.")
    release_decision = dataset.get("release_decision")
    if release_decision == "rejected":
        raise TrainingPipelineError("manifest release decision is rejected; training is forbidden.")
    if release_decision != "approved_for_training":
        raise TrainingPipelineError(
            "manifest release decision is not approved_for_training; draft, under-review, retired, and example-only datasets are ineligible."
        )
    if stage not in ELIGIBLE_STAGES:
        raise TrainingPipelineError(
            f"dataset stage {stage!r} is not eligible; only approved_for_internal_training or released may train."
        )
    licence = manifest.get("licence")
    if not isinstance(licence, Mapping):
        raise TrainingPipelineError("manifest licence review metadata is missing.")
    if licence.get("review_decision") != "approved" or licence.get("machine_learning_use_permitted") is not True:
        raise TrainingPipelineError("manifest licence review is not approved for machine-learning training.")


def _inspection_evidence(dataset_root: Path, raw_path: object | None) -> None:
    if raw_path is None:
        return
    report_path = _resolve_under(dataset_root, raw_path, "dataset inspection report path")
    try:
        report = json.loads(report_path.read_text(encoding="utf-8-sig"))
    except FileNotFoundError as exc:
        raise TrainingPipelineError("dataset inspection report is missing.") from exc
    except (OSError, json.JSONDecodeError) as exc:
        raise TrainingPipelineError("dataset inspection report is unreadable or invalid JSON.") from exc
    if not isinstance(report, Mapping) or report.get("quality_verdict") == "fail":
        raise TrainingPipelineError("dataset inspection evidence has a failing quality verdict.")


def _writable_output_root(output_root: Path) -> None:
    existing = output_root
    while not existing.exists() and existing.parent != existing:
        existing = existing.parent
    if not existing.is_dir() or not os.access(existing, os.W_OK):
        raise TrainingPipelineError("output root parent is not writable.")


def load_training_plan(
    config_path: Path,
    *,
    dataset_root_override: Path | None = None,
    manifest_path_override: Path | None = None,
    output_root_override: str | None = None,
    overrides: Mapping[str, object] | None = None,
    allow_existing_run: bool = False,
    repository_root: Path = REPOSITORY_ROOT,
) -> TrainingPlan:
    """Load a local configuration and complete all non-training preflight checks."""
    repository_root = repository_root.resolve()
    config = _load_yaml(config_path, "Training configuration")
    _only_fields(config, "training configuration", {"schema_version", "experiment_name", "dataset", "model", "training", "output", "notes"})
    if config.get("schema_version") != "1.0.0":
        raise TrainingPipelineError("configuration schema_version must be '1.0.0'.")
    if overrides:
        training = dict(_mapping(config, "training"))
        training.update(overrides)
        config["training"] = training
    experiment_name = _normalise_experiment_name(_required_string(config, "experiment_name"))
    dataset_config = _mapping(config, "dataset")
    model_config = _mapping(config, "model")
    training_config = dict(_mapping(config, "training"))
    training_config.setdefault("fraction", 1.0)
    training_config.setdefault("val", True)
    config["training"] = training_config
    output_config = _mapping(config, "output")
    _only_fields(dataset_config, "dataset configuration", {"manifest_path", "yaml_path", "inspection_report_path", "stage"})
    _only_fields(model_config, "model configuration", {"architecture_path", "initial_weights_path"})
    _only_fields(training_config, "training configuration", {"epochs", "image_size", "batch_size", "device", "workers", "seed", "optimizer", "learning_rate", "confidence", "iou", "deterministic", "resume_behavior", "fraction", "val"})
    _only_fields(output_config, "output configuration", {"root"})
    stage = _required_string(dataset_config, "stage")
    if stage not in ALL_STAGES:
        raise TrainingPipelineError(f"dataset stage must be one of {sorted(ALL_STAGES)!r}.")
    if manifest_path_override is None:
        manifest_path = _resolve_under(repository_root, dataset_config.get("manifest_path"), "manifest path")
        if not manifest_path.is_file():
            raise TrainingPipelineError("manifest path does not identify an existing local file.")
        manifest_reference = manifest_path.relative_to(repository_root).as_posix()
    else:
        manifest_path = _resolve_external_manifest(manifest_path_override)
        manifest_reference = EXTERNAL_MANIFEST_REFERENCE
    if dataset_root_override is None:
        raise TrainingPipelineError("an existing local --dataset-root is required for training preflight.")
    dataset_root = dataset_root_override.resolve()
    if not dataset_root.is_dir():
        raise TrainingPipelineError("an existing local --dataset-root is required for training preflight.")
    dataset_yaml_path = _resolve_under(dataset_root, dataset_config.get("yaml_path"), "dataset YAML path")
    if not dataset_yaml_path.is_file():
        raise TrainingPipelineError("dataset YAML path does not identify an existing local file.")
    architecture = model_config.get("architecture_path")
    initial_weights = model_config.get("initial_weights_path")
    if bool(architecture) == bool(initial_weights):
        raise TrainingPipelineError("model must specify exactly one local architecture_path or initial_weights_path.")
    model_kind, raw_model_path = ("architecture", architecture) if architecture else ("initial_weights", initial_weights)
    model_path = _resolve_under(repository_root, raw_model_path, f"model {model_kind} path")
    if model_path.suffix.casefold() not in {".pt", ".yaml", ".yml"}:
        raise TrainingPipelineError("model path must be a local .pt, .yaml, or .yml file; remote model identifiers are forbidden.")
    if not model_path.is_file():
        raise TrainingPipelineError("local model architecture or initial weights file is missing.")
    output_raw = output_root_override or output_config.get("root")
    output_root = _resolve_under(repository_root, output_raw, "output root")
    try:
        output_root.relative_to(dataset_root)
    except ValueError:
        pass
    else:
        raise TrainingPipelineError("output root must not be inside the supplied dataset root.")
    _writable_output_root(output_root)
    for key in ("epochs", "image_size", "batch_size", "workers", "seed"):
        _require_positive_int(training_config.get(key), f"training {key}")
    device = _required_string(training_config, "device")
    if re.fullmatch(r"(?:cpu|auto|mps|cuda(?::[0-9]+)?|[0-9]+)", device.casefold()) is None:
        raise TrainingPipelineError("training device must be cpu, auto, mps, cuda, cuda:<index>, or a numeric GPU index.")
    _required_string(training_config, "optimizer")
    _require_number(training_config.get("learning_rate"), "training learning_rate", minimum=0.0)
    _require_number(training_config.get("confidence"), "training confidence", minimum=0.0)
    _require_number(training_config.get("iou"), "training iou", minimum=0.0)
    fraction = training_config.get("fraction")
    if not isinstance(fraction, float) or not math.isfinite(fraction) or fraction <= 0.0 or fraction > 1.0:
        raise TrainingPipelineError("training fraction must be a finite float greater than 0 and less than or equal to 1.")
    if not isinstance(training_config.get("val"), bool):
        raise TrainingPipelineError("training val must be a boolean.")
    if not isinstance(training_config.get("deterministic"), bool):
        raise TrainingPipelineError("training deterministic must be a boolean.")
    resume_behaviour = _required_string(training_config, "resume_behavior")
    if resume_behaviour not in RESUME_BEHAVIOURS:
        raise TrainingPipelineError(f"training resume_behavior must be one of {sorted(RESUME_BEHAVIOURS)!r}.")
    if not isinstance(config.get("notes"), str):
        raise TrainingPipelineError("configuration notes must be a string.")
    try:
        manifest = json.loads(manifest_path.read_text(encoding="utf-8-sig"))
    except json.JSONDecodeError as exc:
        raise TrainingPipelineError("manifest is not valid JSON.") from exc
    if not isinstance(manifest, Mapping):
        raise TrainingPipelineError("manifest root must be an object.")
    manifest_issues = manifest_validator.validate_manifest(manifest, dataset_root=dataset_root, check_files=True)
    if manifest_issues:
        first = manifest_issues[0]
        raise TrainingPipelineError(f"manifest validation failed: {first.location}: {first.message}")
    _manifest_eligibility(manifest, stage)
    manifest_dataset = manifest.get("dataset")
    assert isinstance(manifest_dataset, Mapping)
    dataset_yaml = _load_yaml(dataset_yaml_path, "Dataset YAML")
    _validate_dataset_paths(dataset_root, dataset_yaml)
    if _target_taxonomy_from_yaml(dataset_yaml) != list(manifest_validator.APPROVED_TAXONOMY):
        raise TrainingPipelineError("dataset YAML taxonomy must exactly match the approved WalkBuddy IDs, names, and order.")
    _validate_manifest_matches_yaml_splits(manifest, dataset_root, dataset_yaml)
    _inspection_evidence(dataset_root, dataset_config.get("inspection_report_path"))
    config_checksum = _sha256(config_path)
    manifest_checksum = _sha256(manifest_path)
    yaml_checksum = _sha256(dataset_yaml_path)
    model_checksum = _sha256(model_path)
    run_id = f"{experiment_name}-{hashlib.sha256((config_checksum + manifest_checksum + yaml_checksum + model_checksum).encode()).hexdigest()[:12]}"
    run_directory = output_root / run_id
    metadata_path = run_directory / "run_metadata.json"
    if run_directory.exists() and not allow_existing_run:
        raise TrainingPipelineError("run directory already exists; explicit --allow-existing-run is required.")
    if run_directory.exists() and resume_behaviour == "never":
        raise TrainingPipelineError("resume_behavior=never forbids an existing run directory.")
    if not run_directory.exists() and resume_behaviour == "require":
        raise TrainingPipelineError("resume_behavior=require needs an existing run directory.")
    if metadata_path.exists() and not allow_existing_run:
        raise TrainingPipelineError("existing completed or partial run metadata is protected from overwrite.")
    commit, dirty = _git_metadata(repository_root)
    return TrainingPlan(
        config=config,
        repository_root=repository_root,
        dataset_root=dataset_root,
        manifest_path=manifest_path,
        manifest_reference=manifest_reference,
        dataset_yaml_path=dataset_yaml_path,
        model_path=model_path,
        model_kind=model_kind,
        output_root=output_root,
        run_id=run_id,
        run_directory=run_directory,
        config_checksum=config_checksum,
        manifest_checksum=manifest_checksum,
        dataset_yaml_checksum=yaml_checksum,
        model_checksum=model_checksum,
        dataset_id=str(manifest_dataset["id"]),
        dataset_source_version=str(manifest_dataset["source_version"]),
        manifest_release_decision=str(manifest_dataset["release_decision"]),
        git_commit=commit,
        git_dirty=dirty,
    )


def _sanitised_config(plan: TrainingPlan) -> dict[str, object]:
    """Return resolved configuration without an external manifest's local path."""
    config = copy.deepcopy(plan.config)
    if plan.manifest_reference == EXTERNAL_MANIFEST_REFERENCE:
        dataset = dict(_mapping(config, "dataset"))
        dataset["manifest_path"] = plan.manifest_reference
        config["dataset"] = dataset
    return config


def _sanitised_plan(plan: TrainingPlan) -> dict[str, object]:
    data = asdict(plan)
    for key in ("repository_root", "dataset_root", "manifest_path", "manifest_reference", "dataset_yaml_path", "model_path", "output_root", "run_directory"):
        data.pop(key, None)
    data["manifest_path"] = plan.manifest_reference
    data["model_path"] = plan.model_path.relative_to(plan.repository_root).as_posix()
    data["output_location"] = plan.run_directory.relative_to(plan.repository_root).as_posix()
    data["dataset_yaml_path"] = _safe_relative(plan.config["dataset"]["yaml_path"], "dataset YAML path")  # type: ignore[index]
    data["dataset_root"] = "externally supplied local root"
    data["config"] = _sanitised_config(plan)
    return data


def _ultralytics_device(value: str) -> str:
    """Translate the WalkBuddy automatic-device choice for Ultralytics 8.4.7."""
    return "" if value.casefold() == "auto" else value


def trainer_arguments(plan: TrainingPlan) -> dict[str, object]:
    training = _mapping(plan.config, "training")
    return {
        "data": str(plan.dataset_yaml_path),
        "epochs": training["epochs"],
        "imgsz": training["image_size"],
        "batch": training["batch_size"],
        "device": _ultralytics_device(_required_string(training, "device")),
        "workers": training["workers"],
        "seed": training["seed"],
        "optimizer": training["optimizer"],
        "lr0": training["learning_rate"],
        "conf": training["confidence"],
        "iou": training["iou"],
        "deterministic": training["deterministic"],
        "fraction": training["fraction"],
        "val": training["val"],
        "resume": _required_string(training, "resume_behavior") == "require",
        "project": str(plan.output_root),
        "name": plan.run_id,
        "exist_ok": True,
        "cache": False,
    }


def _metadata_trainer_arguments(plan: TrainingPlan) -> dict[str, object]:
    arguments = trainer_arguments(plan)
    arguments["data"] = _safe_relative(plan.config["dataset"]["yaml_path"], "dataset YAML path")  # type: ignore[index]
    arguments["project"] = plan.output_root.relative_to(plan.repository_root).as_posix()
    return arguments


def dry_run(plan: TrainingPlan) -> dict[str, object]:
    """Return a sanitised plan without creating artifacts or importing a trainer."""
    return {"status": "dry_run_valid", "plan": _sanitised_plan(plan)}


def _run_metadata(plan: TrainingPlan, status: str, *, started_at: str, completed_at: str | None = None, failure: str | None = None) -> dict[str, object]:
    dataset = _mapping(plan.config, "dataset")
    return {
        "tool": {"name": "train_navigation_model", "version": TOOL_VERSION},
        "run_id": plan.run_id,
        "status": status,
        "started_at_utc": started_at,
        "completed_at_utc": completed_at,
        "git_commit": plan.git_commit,
        "git_dirty": plan.git_dirty,
        "configuration_checksum_sha256": plan.config_checksum,
        "manifest_checksum_sha256": plan.manifest_checksum,
        "manifest_reference": plan.manifest_reference,
        "dataset_yaml_checksum_sha256": plan.dataset_yaml_checksum,
        "model_checksum_sha256": plan.model_checksum,
        "model_kind": plan.model_kind,
        "dataset_release": {
            "id": plan.dataset_id,
            "source_version": plan.dataset_source_version,
            "manifest_release_decision": plan.manifest_release_decision,
            "stage": dataset["stage"],
        },
        "approved_taxonomy": [{"id": class_id, "name": name} for class_id, name in manifest_validator.APPROVED_TAXONOMY],
        "python_version": platform.python_version(),
        "package_versions": _package_versions(),
        "operating_system": platform.platform(),
        "random_seed": _mapping(plan.config, "training")["seed"],
        "resolved_parameters": _metadata_trainer_arguments(plan),
        "output_location": plan.run_directory.relative_to(plan.repository_root).as_posix(),
        "failure_summary": failure,
    }


def _atomic_write(path: Path, content: str) -> None:
    with tempfile.NamedTemporaryFile("w", encoding="utf-8", dir=path.parent, delete=False) as temporary:
        temporary.write(content)
        temporary_path = Path(temporary.name)
    temporary_path.replace(path)


def _write_run_files(plan: TrainingPlan, metadata: Mapping[str, object]) -> None:
    plan.run_directory.mkdir(parents=True, exist_ok=True)
    _atomic_write(plan.run_directory / "run_metadata.json", json.dumps(metadata, indent=2, sort_keys=True) + "\n")
    _atomic_write(
        plan.run_directory / "resolved_training_config.json",
        json.dumps(_sanitised_config(plan), indent=2, sort_keys=True) + "\n",
    )
    _atomic_write(plan.run_directory / "dataset_reference.json",
        json.dumps(
            {
                "manifest_path": plan.manifest_reference,
                "manifest_checksum_sha256": plan.manifest_checksum,
                "dataset_id": plan.dataset_id,
                "dataset_source_version": plan.dataset_source_version,
                "manifest_release_decision": plan.manifest_release_decision,
                "dataset_yaml_path": _safe_relative(plan.config["dataset"]["yaml_path"], "dataset YAML path"),  # type: ignore[index]
                "dataset_yaml_checksum_sha256": plan.dataset_yaml_checksum,
                "dataset_root": "externally supplied local root",
            }, indent=2, sort_keys=True
        ) + "\n",
    )
    _atomic_write(plan.run_directory / "training_summary.md",
        f"# Navigation model training run\n\nRun ID: `{plan.run_id}`\n\nStatus: `{metadata['status']}`\n",
    )


def default_trainer(plan: TrainingPlan) -> object:
    """Invoke Ultralytics only for explicitly confirmed real training."""
    os.environ.setdefault("YOLO_OFFLINE", "true")
    os.environ.setdefault("WANDB_MODE", "disabled")
    try:
        from ultralytics import YOLO
    except ImportError as exc:
        raise TrainingPipelineError("Ultralytics is unavailable; real training cannot start.") from exc
    model = YOLO(str(plan.model_path))
    return model.train(**trainer_arguments(plan))


def run_training(plan: TrainingPlan, trainer: Callable[[TrainingPlan], object] | None = None) -> object:
    """Write reproducibility metadata and invoke an injected or real trainer."""
    started = datetime.now(UTC).replace(microsecond=0).isoformat().replace("+00:00", "Z")
    running = _run_metadata(plan, "running", started_at=started)
    _write_run_files(plan, running)
    try:
        result = (trainer or default_trainer)(plan)
    except Exception as exc:
        completed = datetime.now(UTC).replace(microsecond=0).isoformat().replace("+00:00", "Z")
        failed = _run_metadata(plan, "failed", started_at=started, completed_at=completed, failure=f"{type(exc).__name__}: {exc}")
        _write_run_files(plan, failed)
        raise TrainingPipelineError(f"training failed: {type(exc).__name__}: {exc}") from exc
    completed = datetime.now(UTC).replace(microsecond=0).isoformat().replace("+00:00", "Z")
    succeeded = _run_metadata(plan, "succeeded", started_at=started, completed_at=completed)
    _write_run_files(plan, succeeded)
    return result


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Controlled local-only WalkBuddy navigation-model training.")
    parser.add_argument("--config", required=True, type=Path, help="Versioned training configuration YAML.")
    parser.add_argument("--dataset-root", type=Path, help="Existing controlled local dataset root.")
    parser.add_argument("--manifest-path", type=Path, help="Existing local external JSON manifest override.")
    parser.add_argument("--output-root", help="Safe repository-relative artifact root override.")
    parser.add_argument("--epochs", type=int, help="Harmless epoch-count override recorded in metadata.")
    parser.add_argument("--batch-size", type=int, help="Harmless batch-size override recorded in metadata.")
    parser.add_argument("--device", help="Device override recorded in metadata.")
    parser.add_argument("--workers", type=int, help="Worker-count override recorded in metadata.")
    parser.add_argument("--dry-run", action="store_true", help="Validate and print the plan without writing artifacts or invoking a trainer.")
    parser.add_argument("--confirm-training", action="store_true", help="Explicitly allow a real local trainer invocation.")
    parser.add_argument("--allow-existing-run", action="store_true", help="Allow the configured resume policy to use an existing run directory.")
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    overrides = {key: value for key, value in {"epochs": args.epochs, "batch_size": args.batch_size, "device": args.device, "workers": args.workers}.items() if value is not None}
    try:
        if args.dry_run and args.confirm_training:
            raise TrainingPipelineError("--dry-run and --confirm-training cannot be used together.")
        plan = load_training_plan(
            args.config,
            dataset_root_override=args.dataset_root,
            manifest_path_override=args.manifest_path,
            output_root_override=args.output_root,
            overrides=overrides,
            allow_existing_run=args.allow_existing_run,
            repository_root=REPOSITORY_ROOT,
        )
        if args.dry_run:
            print(json.dumps(dry_run(plan), indent=2, sort_keys=True))
            return 0
        if not args.confirm_training:
            raise TrainingPipelineError("real training requires --confirm-training; use --dry-run for preflight only.")
        run_training(plan)
    except TrainingPipelineError as exc:
        print(f"Navigation training preflight failed: {exc}", file=sys.stderr)
        return 1
    print(f"Navigation training completed: {plan.run_id}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
