from __future__ import annotations

import json
import sys
from pathlib import Path

DEPLOYMENT_TOOLS = Path(__file__).resolve().parents[1] / "tools"
sys.path.insert(0, str(DEPLOYMENT_TOOLS))

from check_candidate_readiness import check_readiness
from evidence import render_markdown, validate_evidence


TAXONOMY = ["person", "stairs"]


def write_inputs(tmp_path, *, policy="cpu_allowed", lifecycle="candidate", include_evidence=True):
    manifest = {
        "schema_version": "1.0.0", "candidate_id": "candidate", "run_id": "run-1", "expected_lifecycle": lifecycle,
        "expected_artifact_filename": "best.pt", "expected_sha256": "a" * 64, "expected_size_bytes": 4,
        "ordered_taxonomy": TAXONOMY, "registry_record_reference": "registry.json", "training_configuration_reference": "training.yaml",
        "evaluation_evidence_reference": "evidence.json", "compute_policy": policy, "known_limitations": [],
    }
    registry = {
        "schema_version": "1.0", "model_id": "candidate", "model_version": "1",
        "identity": {"name": "test", "architecture": "YOLO", "framework": "Ultralytics", "task": "object_detection"},
        "taxonomy": {"taxonomy_id": "test", "classes": TAXONOMY},
        "dataset": {"release_id": "release", "manifest_reference": "manifest.json"},
        "training": {"training_date": "2026-01-01", "configuration_reference": "training.yaml"},
        "artifact": {"filename": "best.pt", "location": "external", "sha256": "a" * 64},
        "evaluation": {"evidence_reference": "evidence.json"}, "lifecycle": {"status": "candidate"}, "limitations": [],
    }
    (tmp_path / "manifest.json").write_text(json.dumps(manifest), encoding="utf-8")
    (tmp_path / "registry.json").write_text(json.dumps(registry), encoding="utf-8")
    (tmp_path / "training.yaml").write_text("x: y\n", encoding="utf-8")
    if include_evidence: (tmp_path / "evidence.json").write_text("{}", encoding="utf-8")
    (tmp_path / "best.pt").write_bytes(b"fake")
    return tmp_path / "manifest.json", tmp_path / "best.pt"


def fake_runtime(*, model_path, expected, base_url, require_cuda, timeout_seconds, api_key):
    assert expected.filename == "best.pt"
    return {
        "runtime_environment": {"python_version": "3.11", "torch_version": "test", "cuda_available": True, "cuda_usable": True},
        "model_identity": {"filename": "best.pt", "sha256": "a" * 64, "size_bytes": 4, "taxonomy_compatible": True},
        "backend_status": {"base_url": base_url, "endpoints": {"/ml/metrics": {"payload": {"total_attempts": 1, "mean_latency_ms": 1.0}}}},
        "checks": [{"name": "model_identity", "status": "pass", "detail": "ok"}],
    }


def failing_runtime(**kwargs):
    report = fake_runtime(**kwargs)
    report["checks"] = [{"name": "backend_model_sha256", "status": "fail", "detail": "Backend value does not match expected identity."}]
    return report


def statuses(report): return {item["name"]: item["status"] for item in report["checks"]}


def test_full_readiness_pass_and_evidence_rendering(tmp_path):
    manifest, model = write_inputs(tmp_path)
    report = check_readiness(manifest_path=manifest, model_path=model, base_url="http://backend:8000", reference_root=tmp_path, runtime_runner=fake_runtime)
    assert report["overall_result"] == "PASS"
    assert not validate_evidence(report)
    assert "# Candidate Deployment Readiness" in render_markdown(report)


def test_cpu_preferred_and_required_policy_results(tmp_path):
    manifest, model = write_inputs(tmp_path, policy="cuda_preferred")
    def cpu_runtime(**kwargs):
        report = fake_runtime(**kwargs)
        report["runtime_environment"].update({"cuda_available": False, "cuda_usable": False})
        report["checks"] = [{"name": "cuda_available", "status": "warning", "detail": "CPU only"}]
        return report
    warning = check_readiness(manifest_path=manifest, model_path=model, reference_root=tmp_path, runtime_runner=cpu_runtime)
    assert warning["overall_result"] == "WARNING"
    manifest, model = write_inputs(tmp_path, policy="cuda_required")
    failure = check_readiness(manifest_path=manifest, model_path=model, reference_root=tmp_path, runtime_runner=cpu_runtime)
    assert failure["overall_result"] == "FAIL"
    assert statuses(failure)["compute_policy"] == "fail"


def test_wrong_local_backend_lifecycle_and_taxonomy_fail(tmp_path):
    manifest, model = write_inputs(tmp_path)
    wrong_backend = check_readiness(manifest_path=manifest, model_path=model, reference_root=tmp_path, runtime_runner=failing_runtime)
    assert wrong_backend["overall_result"] == "FAIL"
    manifest, model = write_inputs(tmp_path, lifecycle="production")
    lifecycle = check_readiness(manifest_path=manifest, model_path=model, reference_root=tmp_path, runtime_runner=fake_runtime)
    assert statuses(lifecycle)["registry_expected_lifecycle"] == "fail"
    payload = json.loads(manifest.read_text(encoding="utf-8")); payload["ordered_taxonomy"] = ["stairs", "person"]; manifest.write_text(json.dumps(payload), encoding="utf-8")
    taxonomy = check_readiness(manifest_path=manifest, model_path=model, reference_root=tmp_path, runtime_runner=fake_runtime)
    assert statuses(taxonomy)["registry_ordered_taxonomy"] == "fail"


def test_missing_evidence_is_warning_and_malformed_manifest_stops_before_runtime(tmp_path):
    manifest, model = write_inputs(tmp_path, include_evidence=False)
    report = check_readiness(manifest_path=manifest, model_path=model, reference_root=tmp_path, runtime_runner=fake_runtime)
    assert report["overall_result"] == "WARNING"
    payload = json.loads(manifest.read_text(encoding="utf-8")); payload.pop("expected_sha256"); manifest.write_text(json.dumps(payload), encoding="utf-8")
    called = False
    def not_called(**kwargs):
        nonlocal called; called = True; return fake_runtime(**kwargs)
    malformed = check_readiness(manifest_path=manifest, model_path=model, reference_root=tmp_path, runtime_runner=not_called)
    assert malformed["overall_result"] == "FAIL"
    assert called is False


def test_evidence_validator_rejects_production_approval_and_nonfinite_metrics(tmp_path):
    manifest, model = write_inputs(tmp_path)
    report = check_readiness(manifest_path=manifest, model_path=model, reference_root=tmp_path, runtime_runner=fake_runtime)
    report["governance_note"] = "production approved"
    report["metrics_snapshot"] = {"mean_latency_ms": float("inf")}
    errors = validate_evidence(report)
    assert any("production approval" in error for error in errors)
    assert any("non-finite" in error for error in errors)
