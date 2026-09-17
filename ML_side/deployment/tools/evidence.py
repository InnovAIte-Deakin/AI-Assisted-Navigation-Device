"""Validation and rendering for durable deployment-readiness evidence."""

from __future__ import annotations

import json
from collections.abc import Mapping, Sequence
from pathlib import Path

from common import ALLOWED_RESULTS, DeploymentError, finite_number, read_json


EVIDENCE_SCHEMA_VERSION = "1.0.0"
FORBIDDEN_APPROVAL_TEXT = "production approved"


def validate_evidence(payload: object) -> list[str]:
    if not isinstance(payload, Mapping):
        return ["Evidence must be a JSON object."]
    errors: list[str] = []
    if payload.get("schema_version") != EVIDENCE_SCHEMA_VERSION:
        errors.append("Unsupported evidence schema version.")
    if payload.get("overall_result") not in ALLOWED_RESULTS:
        errors.append("Evidence overall_result is invalid.")
    candidate = payload.get("candidate")
    if not isinstance(candidate, Mapping) or not isinstance(candidate.get("candidate_id"), str) or not candidate.get("candidate_id"):
        errors.append("Candidate identity is missing.")
    artifact = payload.get("local_artifact")
    if isinstance(artifact, Mapping) and artifact.get("sha256") is not None:
        sha = artifact.get("sha256")
        if not isinstance(sha, str) or len(sha) != 64 or any(char not in "0123456789abcdef" for char in sha.lower()):
            errors.append("Artifact SHA-256 is invalid.")
    metrics = payload.get("metrics_snapshot")
    if metrics is not None:
        if not isinstance(metrics, Mapping):
            errors.append("Metrics snapshot is malformed.")
        elif any(value is not None and not finite_number(value) for value in metrics.values()):
            errors.append("Metrics snapshot contains non-finite numeric data.")
    for field in ("warnings", "failures"):
        value = payload.get(field)
        if not isinstance(value, list) or not all(isinstance(item, str) for item in value):
            errors.append(f"Evidence {field} must be a list of strings.")
    governance = payload.get("governance_note")
    if not isinstance(governance, str) or not governance:
        errors.append("Governance note is missing.")
    text = json.dumps(payload, sort_keys=True).lower()
    if FORBIDDEN_APPROVAL_TEXT in text:
        errors.append("Evidence must not state production approval.")
    return errors


def load_and_validate(path: str | Path) -> list[str]:
    return validate_evidence(read_json(Path(path).expanduser().resolve()))


def render_markdown(report: Mapping[str, object]) -> str:
    candidate = report.get("candidate", {})
    manifest = report.get("manifest", {})
    registry = report.get("registry", {})
    artifact = report.get("local_artifact", {})
    runtime = report.get("runtime_environment", {})
    backend = report.get("backend", {})
    metrics = report.get("metrics_snapshot", {})
    lines = [
        "# Candidate Deployment Readiness", "",
        "## Candidate", "", f"- ID: `{candidate.get('candidate_id') if isinstance(candidate, Mapping) else None}`", f"- Run: `{candidate.get('run_id') if isinstance(candidate, Mapping) else None}`", "",
        "## Manifest", "", f"- Reference: `{manifest.get('reference') if isinstance(manifest, Mapping) else None}`", "",
        "## Registry Lineage", "", f"- Reference: `{registry.get('reference') if isinstance(registry, Mapping) else None}`", "",
        "## Artifact Identity", "", f"- Filename: `{artifact.get('filename') if isinstance(artifact, Mapping) else None}`", f"- SHA-256: `{artifact.get('sha256') if isinstance(artifact, Mapping) else None}`", "",
        "## Runtime Environment", "", f"- Python: `{runtime.get('python_version') if isinstance(runtime, Mapping) else None}`", f"- Torch: `{runtime.get('torch_version') if isinstance(runtime, Mapping) else None}`", "",
        "## Compute", "", f"- CUDA available: `{runtime.get('cuda_available') if isinstance(runtime, Mapping) else None}`", f"- CUDA usable: `{runtime.get('cuda_usable') if isinstance(runtime, Mapping) else None}`", "",
        "## Backend Contract", "", f"- Base URL: `{backend.get('base_url') if isinstance(backend, Mapping) else None}`", "",
        "## Metrics Snapshot", "", "```json", json.dumps(metrics, indent=2, sort_keys=True), "```", "",
        "## Warnings", "",
    ]
    warnings = report.get("warnings", [])
    lines.extend(f"- {item}" for item in warnings if isinstance(item, str))
    lines.extend(["", "## Failures", ""])
    failures = report.get("failures", [])
    lines.extend(f"- {item}" for item in failures if isinstance(item, str))
    lines.extend(["", "## Overall Result", "", f"**{report.get('overall_result')}**", "", "## Governance Note", "", str(report.get("governance_note", "")), ""])
    return "\n".join(lines)
