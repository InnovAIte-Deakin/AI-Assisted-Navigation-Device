"""Portable deployment-manifest validation and registry comparison."""

from __future__ import annotations

import re
import importlib.util
from collections.abc import Mapping
from pathlib import Path
from typing import Any

from common import DEPLOYMENT_DIR, ML_SIDE_DIR, REPO_ROOT, DeploymentError, check, read_json, resolve_portable_reference


MANIFEST_SCHEMA_VERSION = "1.0.0"
ALLOWED_LIFECYCLES = {"experimental", "candidate", "production", "rejected", "deprecated", "rolled_back"}
ALLOWED_COMPUTE_POLICIES = {"cpu_allowed", "cuda_preferred", "cuda_required"}
SHA256_RE = re.compile(r"^[a-f0-9]{64}$")


def load_manifest(path: str | Path) -> tuple[dict[str, Any], Path]:
    manifest_path = Path(path).expanduser().resolve()
    payload = read_json(manifest_path)
    if not isinstance(payload, dict):
        raise DeploymentError("Deployment manifest must be a JSON object.")
    return payload, manifest_path


def validate_manifest(manifest: Mapping[str, object], *, reference_root: Path = REPO_ROOT) -> list[dict[str, str]]:
    checks: list[dict[str, str]] = []
    required_strings = (
        "candidate_id", "run_id", "expected_lifecycle", "expected_artifact_filename",
        "expected_sha256", "registry_record_reference", "compute_policy",
    )
    for field in required_strings:
        value = manifest.get(field)
        checks.append(check(f"manifest_{field}", "pass" if isinstance(value, str) and value.strip() else "fail", f"{field} is present." if isinstance(value, str) and value.strip() else f"{field} is required."))
    checks.append(check("manifest_schema_version", "pass" if manifest.get("schema_version") == MANIFEST_SCHEMA_VERSION else "fail", "Supported manifest schema version." if manifest.get("schema_version") == MANIFEST_SCHEMA_VERSION else "Unsupported manifest schema version."))
    sha = manifest.get("expected_sha256")
    checks.append(check("manifest_sha256_format", "pass" if isinstance(sha, str) and SHA256_RE.fullmatch(sha) else "fail", "Expected SHA-256 is well formed." if isinstance(sha, str) and SHA256_RE.fullmatch(sha) else "Expected SHA-256 must be 64 lowercase hexadecimal characters."))
    size = manifest.get("expected_size_bytes")
    valid_size = isinstance(size, int) and not isinstance(size, bool) and size > 0
    checks.append(check("manifest_size", "pass" if valid_size else "fail", "Expected artifact size is positive." if valid_size else "Expected artifact size must be a positive integer."))
    taxonomy = manifest.get("ordered_taxonomy")
    valid_taxonomy = isinstance(taxonomy, list) and bool(taxonomy) and all(isinstance(item, str) and item.strip() for item in taxonomy) and len(set(taxonomy)) == len(taxonomy)
    checks.append(check("manifest_taxonomy", "pass" if valid_taxonomy else "fail", "Ordered taxonomy is non-empty and unique." if valid_taxonomy else "Ordered taxonomy must contain unique non-empty class names."))
    lifecycle = manifest.get("expected_lifecycle")
    checks.append(check("manifest_lifecycle", "pass" if lifecycle in ALLOWED_LIFECYCLES else "fail", "Lifecycle is supported." if lifecycle in ALLOWED_LIFECYCLES else "Unsupported lifecycle."))
    policy = manifest.get("compute_policy")
    checks.append(check("manifest_compute_policy", "pass" if policy in ALLOWED_COMPUTE_POLICIES else "fail", "Compute policy is supported." if policy in ALLOWED_COMPUTE_POLICIES else "Unsupported compute policy."))
    for field in ("registry_record_reference", "training_configuration_reference", "evaluation_evidence_reference"):
        value = manifest.get(field)
        if value is None and field != "registry_record_reference":
            checks.append(check(f"manifest_{field}", "not_checked", f"{field} was not supplied."))
            continue
        try:
            resolve_portable_reference(value, reference_root)
        except DeploymentError as exc:
            checks.append(check(f"manifest_{field}", "fail", str(exc)))
        else:
            checks.append(check(f"manifest_{field}", "pass", "Reference is portable and contained."))
    return checks


def validate_reference_existence(manifest: Mapping[str, object], *, reference_root: Path = REPO_ROOT) -> list[dict[str, str]]:
    checks: list[dict[str, str]] = []
    for field in ("training_configuration_reference", "evaluation_evidence_reference"):
        value = manifest.get(field)
        if value is None:
            checks.append(check(f"{field}_exists", "warning", f"{field} was not supplied; lineage is incomplete."))
            continue
        try:
            exists = resolve_portable_reference(value, reference_root).is_file()
        except DeploymentError as exc:
            checks.append(check(f"{field}_exists", "fail", str(exc)))
        else:
            checks.append(check(f"{field}_exists", "pass" if exists else "warning", "Referenced lineage file exists." if exists else "Referenced lineage file is missing; deployment evidence is incomplete."))
    return checks


def _registry_validator() -> Any:
    registry_tools = ML_SIDE_DIR / "model_registry" / "tools"
    module_path = registry_tools / "validate.py"
    specification = importlib.util.spec_from_file_location("walkbuddy_registry_validate", module_path)
    if specification is None or specification.loader is None:
        raise DeploymentError("Registry validator could not be loaded.")
    module = importlib.util.module_from_spec(specification)
    specification.loader.exec_module(module)
    return module.validate_record


def _basic_registry_errors(record: Mapping[str, object]) -> list[str]:
    """Minimal read-only fallback when the registry's jsonschema extra is absent."""
    required = (
        ("schema_version",), ("model_id",), ("model_version",), ("identity",),
        ("taxonomy", "classes"), ("dataset",), ("training", "configuration_reference"),
        ("artifact", "filename"), ("artifact", "location"), ("artifact", "sha256"),
        ("evaluation",), ("lifecycle", "status"), ("limitations",),
    )
    errors: list[str] = []
    for parts in required:
        current: object = record
        for part in parts:
            current = current.get(part) if isinstance(current, Mapping) else None
        if current is None or current == "":
            errors.append(".".join(parts) + " is missing")
    sha = _nested(record, "artifact", "sha256")
    if not isinstance(sha, str) or not SHA256_RE.fullmatch(sha):
        errors.append("artifact.sha256 is malformed")
    lifecycle = _nested(record, "lifecycle", "status")
    if lifecycle not in ALLOWED_LIFECYCLES:
        errors.append("lifecycle.status is unsupported")
    taxonomy = _nested(record, "taxonomy", "classes")
    if not isinstance(taxonomy, list) or not taxonomy or len(set(taxonomy)) != len(taxonomy):
        errors.append("taxonomy.classes is malformed")
    return errors


def load_and_compare_registry(manifest: Mapping[str, object], *, reference_root: Path = REPO_ROOT) -> tuple[dict[str, object] | None, list[dict[str, str]]]:
    try:
        path = resolve_portable_reference(manifest.get("registry_record_reference"), reference_root)
        registry = read_json(path)
    except DeploymentError as exc:
        return None, [check("registry_record", "fail", str(exc))]
    if not isinstance(registry, dict):
        return None, [check("registry_record", "fail", "Registry record must be a JSON object.")]
    try:
        schema_errors = _registry_validator()(registry)
        schema_status = "pass" if not schema_errors else "fail"
        schema_detail = "Registry record is schema-valid." if not schema_errors else "Registry record is schema-invalid."
    except ModuleNotFoundError:
        schema_errors = _basic_registry_errors(registry)
        schema_status = "pass" if not schema_errors else "fail"
        schema_detail = "Registry record passed deterministic compatibility validation." if not schema_errors else "Registry record is structurally invalid."
    except Exception:
        return registry, [check("registry_schema", "fail", "Registry record schema could not be validated.")]
    checks = [check("registry_schema", schema_status, schema_detail)]
    comparisons = (
        ("candidate_id", registry.get("model_id")),
        ("expected_lifecycle", _nested(registry, "lifecycle", "status")),
        ("expected_artifact_filename", _nested(registry, "artifact", "filename")),
        ("expected_sha256", _nested(registry, "artifact", "sha256")),
        ("ordered_taxonomy", _nested(registry, "taxonomy", "classes")),
        ("training_configuration_reference", _nested(registry, "training", "configuration_reference")),
        ("evaluation_evidence_reference", _nested(registry, "evaluation", "evidence_reference")),
    )
    for field, registry_value in comparisons:
        manifest_value = manifest.get(field)
        if manifest_value is None:
            checks.append(check(f"registry_{field}", "not_checked", "Manifest does not supply this optional value."))
        elif manifest_value == registry_value:
            checks.append(check(f"registry_{field}", "pass", "Manifest and registry agree."))
        else:
            checks.append(check(f"registry_{field}", "fail", "Manifest and authoritative registry disagree."))
    return registry, checks


def _nested(record: Mapping[str, object], parent: str, child: str) -> object:
    value = record.get(parent)
    return value.get(child) if isinstance(value, Mapping) else None
