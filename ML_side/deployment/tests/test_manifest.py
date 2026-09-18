from __future__ import annotations

import json
import sys
from pathlib import Path

DEPLOYMENT_TOOLS = Path(__file__).resolve().parents[1] / "tools"
sys.path.insert(0, str(DEPLOYMENT_TOOLS))

from manifest import load_and_compare_registry, validate_manifest, validate_reference_existence


TAXONOMY = ["person", "stairs"]


def manifest(**overrides):
    value = {
        "schema_version": "1.0.0", "candidate_id": "candidate", "run_id": "run-1",
        "expected_lifecycle": "candidate", "expected_artifact_filename": "best.pt",
        "expected_sha256": "a" * 64, "expected_size_bytes": 12,
        "ordered_taxonomy": TAXONOMY, "registry_record_reference": "registry.json",
        "training_configuration_reference": "training.yaml", "evaluation_evidence_reference": "evidence.json",
        "compute_policy": "cpu_allowed", "known_limitations": [],
    }
    value.update(overrides)
    return value


def registry():
    return {
        "schema_version": "1.0", "model_id": "candidate", "model_version": "1",
        "identity": {"name": "test", "architecture": "YOLO", "framework": "Ultralytics", "task": "object_detection"},
        "taxonomy": {"taxonomy_id": "test", "classes": TAXONOMY},
        "dataset": {"release_id": "release", "manifest_reference": "manifest.json"},
        "training": {"training_date": "2026-01-01", "configuration_reference": "training.yaml"},
        "artifact": {"filename": "best.pt", "location": "external", "sha256": "a" * 64},
        "evaluation": {"evidence_reference": "evidence.json"}, "lifecycle": {"status": "candidate"}, "limitations": [],
    }


def statuses(checks):
    return {item["name"]: item["status"] for item in checks}


def test_valid_manifest_is_accepted():
    assert all(item["status"] != "fail" for item in validate_manifest(manifest()))


def test_manifest_rejects_required_and_identity_errors():
    checks = validate_manifest(manifest(candidate_id="", expected_sha256="bad", expected_size_bytes=True))
    state = statuses(checks)
    assert state["manifest_candidate_id"] == "fail"
    assert state["manifest_sha256_format"] == "fail"
    assert state["manifest_size"] == "fail"


def test_manifest_rejects_duplicate_empty_and_invalid_policy():
    checks = validate_manifest(manifest(ordered_taxonomy=[], compute_policy="gpu_only", expected_lifecycle="approved"))
    state = statuses(checks)
    assert state["manifest_taxonomy"] == "fail"
    assert state["manifest_compute_policy"] == "fail"
    assert state["manifest_lifecycle"] == "fail"


def test_manifest_rejects_absolute_or_escaping_references():
    checks = validate_manifest(manifest(registry_record_reference="C:/private/registry.json"))
    assert statuses(checks)["manifest_registry_record_reference"] == "fail"
    checks = validate_manifest(manifest(registry_record_reference="../registry.json"))
    assert statuses(checks)["manifest_registry_record_reference"] == "fail"


def test_registry_consistency_and_reference_existence(tmp_path):
    (tmp_path / "registry.json").write_text(json.dumps(registry()), encoding="utf-8")
    (tmp_path / "training.yaml").write_text("schema_version: '1'\n", encoding="utf-8")
    (tmp_path / "evidence.json").write_text("{}", encoding="utf-8")
    _, checks = load_and_compare_registry(manifest(), reference_root=tmp_path)
    assert all(item["status"] != "fail" for item in checks)
    assert all(item["status"] == "pass" for item in validate_reference_existence(manifest(), reference_root=tmp_path))


def test_registry_disagreement_and_missing_reference_are_visible(tmp_path):
    wrong = registry()
    wrong["artifact"]["sha256"] = "b" * 64
    (tmp_path / "registry.json").write_text(json.dumps(wrong), encoding="utf-8")
    _, checks = load_and_compare_registry(manifest(), reference_root=tmp_path)
    assert statuses(checks)["registry_expected_sha256"] == "fail"
    reference_checks = validate_reference_existence(manifest(), reference_root=tmp_path)
    assert statuses(reference_checks)["evaluation_evidence_reference_exists"] == "warning"
