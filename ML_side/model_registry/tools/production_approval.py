"""Fail-closed validation for the first approved eight-class production decision.

This module deliberately supports one documented decision only.  It is not a
generic substitute for the normal PASS comparison and approved-policy route
used by future candidates.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Mapping

from jsonschema import Draft202012Validator, FormatChecker


ML_SIDE_DIR = Path(__file__).resolve().parents[2]
DEFAULT_REPOSITORY_ROOT = ML_SIDE_DIR.parent
APPROVAL_SCHEMA_PATH = ML_SIDE_DIR / "model_registry" / "schema" / "production-approval.schema.json"

FIRST_EIGHT_CLASS_SCOPE = "first_structurally_valid_eight_class_production_promotion"
HUMAN_TEAM_DECISION_TYPE = "explicit_human_team_approval"
APPROVED_OUTCOME = "approved"
APPROVED_MODEL_ID = "WB-OD-NAV-001"
APPROVED_MODEL_VERSION = "0.1.0"
APPROVED_TAXONOMY_ID = "walkbuddy-mvp-8-v1"
APPROVED_TAXONOMY = (
    "person", "stairs", "door", "chair", "table", "pole", "bicycle", "vehicle",
)


def _load_json(path: Path) -> object:
    with path.open("r", encoding="utf-8") as file:
        return json.load(file)


def _resolve_reference(reference: object, repository_root: Path) -> Path | None:
    if not isinstance(reference, str) or not reference or Path(reference).is_absolute():
        return None
    path = (repository_root / reference).resolve()
    try:
        path.relative_to(repository_root.resolve())
    except ValueError:
        return None
    return path


def _schema_errors(approval: object) -> list[str]:
    schema = _load_json(APPROVAL_SCHEMA_PATH)
    validator = Draft202012Validator(schema, format_checker=FormatChecker())
    return [
        f"{'.'.join(str(part) for part in error.absolute_path) or 'approval'}: {error.message}"
        for error in sorted(validator.iter_errors(approval), key=lambda error: list(error.absolute_path))
    ]


def _evaluation_lineage_errors(record: Mapping[str, object], repository_root: Path) -> list[str]:
    evaluation = record.get("evaluation")
    reference = evaluation.get("evidence_reference") if isinstance(evaluation, Mapping) else None
    path = _resolve_reference(reference, repository_root)
    if path is None or not path.is_file():
        return ["registered evaluation evidence is missing or has a non-portable reference"]
    try:
        payload = _load_json(path)
    except (OSError, json.JSONDecodeError) as error:
        return [f"registered evaluation evidence is unreadable: {error}"]
    if not isinstance(payload, Mapping):
        return ["registered evaluation evidence is not an object"]
    model = payload.get("model")
    artifact = record.get("artifact")
    taxonomy = record.get("taxonomy")
    if not isinstance(model, Mapping) or not isinstance(artifact, Mapping) or not isinstance(taxonomy, Mapping):
        return ["registered evaluation lineage is incomplete"]
    expected = {
        "filename": artifact.get("filename"),
        "sha256": artifact.get("sha256"),
        "class_count": len(taxonomy.get("classes", [])),
        "ordered_class_names": taxonomy.get("classes"),
    }
    errors = [
        f"registered evaluation lineage field {field!r} does not match the registry"
        for field, value in expected.items()
        if model.get(field) != value
    ]
    if payload.get("dataset_split") != "test" or payload.get("mode") != "labelled_validation":
        errors.append("registered evaluation evidence is not labelled test-split validation")
    return errors


def validate_first_eight_class_approval(
    record: Mapping[str, object],
    approval: object,
    *,
    repository_root: str | Path = DEFAULT_REPOSITORY_ROOT,
    approval_path: str | Path | None = None,
) -> list[str]:
    """Return all errors for the narrowly scoped human-approval mechanism."""
    root = Path(repository_root).resolve()
    errors = _schema_errors(approval)
    if not isinstance(approval, Mapping):
        return errors or ["approval record is not an object"]

    binding = record.get("production_approval")
    reference = binding.get("decision_record_reference") if isinstance(binding, Mapping) else None
    registered_path = _resolve_reference(reference, root)
    if registered_path is None:
        errors.append("registry production approval reference is missing or non-portable")
    elif approval_path is not None and registered_path != Path(approval_path).resolve():
        errors.append("supplied approval record does not match the registry reference")

    identity = approval.get("model")
    artifact = record.get("artifact")
    taxonomy = record.get("taxonomy")
    evaluation = record.get("evaluation")
    if not all(isinstance(value, Mapping) for value in (identity, artifact, taxonomy, evaluation)):
        return errors + ["registry or approval model binding is incomplete"]

    expected = {
        "model_id": record.get("model_id"),
        "model_version": record.get("model_version"),
        "artifact_filename": artifact.get("filename"),
        "sha256": artifact.get("sha256"),
        "ordered_taxonomy": taxonomy.get("classes"),
        "evaluation_evidence_reference": evaluation.get("evidence_reference"),
    }
    for field, value in expected.items():
        if identity.get(field) != value:
            errors.append(f"approval {field!r} does not match the registry")

    if record.get("model_id") != APPROVED_MODEL_ID or record.get("model_version") != APPROVED_MODEL_VERSION:
        errors.append("human approval is restricted to WB-OD-NAV-001 version 0.1.0")
    if taxonomy.get("taxonomy_id") != APPROVED_TAXONOMY_ID or taxonomy.get("classes") != list(APPROVED_TAXONOMY):
        errors.append("human approval is restricted to the canonical ordered eight-class taxonomy")
    if approval.get("scope") != FIRST_EIGHT_CLASS_SCOPE:
        errors.append("approval scope is not the documented first-eight-class promotion scope")
    if approval.get("decision_type") != HUMAN_TEAM_DECISION_TYPE:
        errors.append("approval decision type is not explicit human team approval")
    if approval.get("approval_outcome") != APPROVED_OUTCOME:
        errors.append("approval outcome is not positive")

    reviewed = approval.get("reviewed_evidence_references")
    expected_evaluation = evaluation.get("evidence_reference")
    if not isinstance(reviewed, list) or expected_evaluation not in reviewed:
        errors.append("approval does not reference the registered evaluation evidence")
    elif any(not (_resolve_reference(item, root) or Path()).is_file() for item in reviewed):
        errors.append("approval references missing or non-portable reviewed evidence")

    limitations = approval.get("accepted_limitations")
    if not isinstance(limitations, list) or not any("pole" in item.lower() for item in limitations if isinstance(item, str)):
        errors.append("approval does not record the accepted pole limitation")

    errors.extend(_evaluation_lineage_errors(record, root))
    return errors


def load_and_validate_first_eight_class_approval(
    record: Mapping[str, object],
    *,
    repository_root: str | Path = DEFAULT_REPOSITORY_ROOT,
) -> tuple[object | None, list[str], Path | None]:
    """Load the registry-bound approval record without mutating any state."""
    root = Path(repository_root).resolve()
    binding = record.get("production_approval")
    reference = binding.get("decision_record_reference") if isinstance(binding, Mapping) else None
    path = _resolve_reference(reference, root)
    if path is None or not path.is_file():
        return None, ["registry production approval record is missing"], path
    try:
        approval = _load_json(path)
    except (OSError, json.JSONDecodeError) as error:
        return None, [f"registry production approval record is unreadable: {error}"], path
    return approval, validate_first_eight_class_approval(
        record, approval, repository_root=root, approval_path=path,
    ), path
