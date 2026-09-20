"""Synthetic coverage for the read-only release-readiness handover workflow."""

from __future__ import annotations

import json
import sys
from pathlib import Path

import pytest


ML_SIDE_DIR = Path(__file__).resolve().parents[1]
if str(ML_SIDE_DIR) not in sys.path:
    sys.path.insert(0, str(ML_SIDE_DIR))

from release_readiness_lib.core import run_release_readiness
from release_readiness_lib.outputs import render_markdown, write_reports
import runtime_preflight as preflight


CANDIDATE = "WB-OD-NAV-001"
FUTURE_CANDIDATE = "WB-OD-NAV-002"
RUN_ID = "navigation-mvp-full-candidate-56c445bb8c85"
SHA = "a" * 64
TAXONOMY = ["person", "stairs", "door", "chair", "table", "pole", "bicycle", "vehicle"]


def _write_json(path: Path, payload: object) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2), encoding="utf-8")


def _json(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def _paths(root: Path) -> dict[str, Path]:
    return {
        "manifest": root / "ML_side/deployment/manifests/candidate.json",
        "registry": root / "ML_side/model_registry/records/candidate.json",
        "training": root / "ML_side/config/training.yaml",
        "heldout": root / "ML_side/evaluation/candidates/heldout/summary.json",
        "benchmark": root / "ML_side/benchmark_results/inference_performance.json",
        "acceptance": root / "ML_side/evaluation/candidates/navigation-mvp-full-candidate-56c445bb8c85-runtime-acceptance/issue-74-real-candidate-safety-validation.json",
        "approval": root / "ML_side/model_registry/approvals/WB-OD-NAV-001-v0.1.0-production-approval.json",
        "automatic": root / "ML_side/model_registry/promotions/WB-OD-NAV-002-v1.0.0-comparison.json",
    }


def make_release_tree(tmp_path: Path) -> dict[str, Path]:
    paths = _paths(tmp_path)
    registry = {
        "schema_version": "1.0", "model_id": CANDIDATE, "model_version": "0.1.0",
        "identity": {"name": "Candidate", "architecture": "YOLO", "framework": "Ultralytics", "task": "object_detection"},
        "taxonomy": {"taxonomy_id": "walkbuddy-mvp-8-v1", "classes": TAXONOMY},
        "dataset": {
            "release_id": "walkbuddy-navigation-v5", "manifest_reference": "external-local/manifest.json",
        },
        "training": {"training_date": "2026-09-01", "configuration_reference": "ML_side/config/training.yaml"},
        "artifact": {"filename": "best.pt", "location": "approved-store/best.pt", "sha256": SHA},
        "evaluation": {"evidence_reference": "ML_side/evaluation/candidates/heldout/summary.json"},
        "lifecycle": {"status": "candidate"}, "limitations": [],
    }
    manifest = {
        "schema_version": "1.0.0", "candidate_id": CANDIDATE, "run_id": RUN_ID, "expected_lifecycle": "candidate",
        "expected_artifact_filename": "best.pt", "expected_sha256": SHA, "expected_size_bytes": 5364741,
        "ordered_taxonomy": TAXONOMY, "registry_record_reference": "ML_side/model_registry/records/candidate.json",
        "training_configuration_reference": "ML_side/config/training.yaml",
        "evaluation_evidence_reference": "ML_side/evaluation/candidates/heldout/summary.json",
        "compute_policy": "cuda_preferred", "known_limitations": [],
    }
    heldout = {
        "dataset_split": "test", "mode": "labelled_validation",
        "model": {"filename": "best.pt", "sha256": SHA, "file_size_bytes": 5364741, "class_count": len(TAXONOMY), "ordered_class_names": TAXONOMY},
        "validation_metrics": {"precision": 0.6, "recall": 0.5, "mAP50": 0.4, "mAP50_95": 0.3, "validation_image_count": 3497},
    }
    benchmark = {
        "model": {"filename": "best.pt", "sha256": SHA, "size_bytes": 5364741},
        "environment": {"platform": "test", "python_version": "3.11", "pytorch_version": "2.test", "ultralytics_version": "8.test"},
        "results": [{"device": "cpu", "mean_latency_ms": 1.5, "throughput_fps": 10.0}],
        "limitations": ["The held-out test set is not used by this benchmark."],
    }
    acceptance = {
        "candidate": {"candidate_id": CANDIDATE, "run_id": RUN_ID, "artifact_filename": "best.pt", "sha256": SHA, "size_bytes": 5364741, "ordered_taxonomy": TAXONOMY},
        "runtime": {"mock_mode": False, "cuda_usable": True},
        "deployment_readiness": {"cuda_required_preflight": "PASS", "live_readiness": "PASS", "startup": "PASS"},
        "operational_endpoints": {
            "model_info": {"http_status": 200, "loaded": True, "filename": "best.pt", "sha256_matches_manifest": True, "size_matches_manifest": True, "taxonomy_compatible": True},
            "ready": {"http_status": 200, "ready": True}, "health": {"http_status": 200, "status": "ok"},
        },
        "input_policy": {"result": "PASS", "summary": "No held-out test-split input was used."},
        "real_candidate_safety_validation": {
            "vision_hazard_case": {"result": "PASS"}, "vision_non_trigger_case": {"result": "PASS"},
            "chat_safety_override": {"result": "PASS", "llm_dependency": "deterministic before LLM path"},
            "depth_semantics": {"result": "PASS", "relative_depth_unit": "unitless relative score", "distance_m_observed": None, "distance_m_derived_from_relative_depth": False},
        },
        "issue_74_acceptance": {"result": "PASS"},
    }
    _write_json(paths["registry"], registry)
    _write_json(paths["manifest"], manifest)
    paths["training"].parent.mkdir(parents=True, exist_ok=True)
    paths["training"].write_text("training: candidate\n", encoding="utf-8")
    _write_json(paths["heldout"], heldout)
    _write_json(paths["benchmark"], benchmark)
    _write_json(paths["acceptance"], acceptance)
    return paths


def promote_with_first_eight_class_approval(paths: dict[str, Path]) -> None:
    registry = _json(paths["registry"])
    registry["lifecycle"]["status"] = "production"
    registry["production_approval"] = {
        "decision_record_reference": "ML_side/model_registry/approvals/WB-OD-NAV-001-v0.1.0-production-approval.json"
    }
    _write_json(paths["registry"], registry)
    manifest = _json(paths["manifest"])
    manifest["expected_lifecycle"] = "production"
    _write_json(paths["manifest"], manifest)
    _write_json(paths["approval"], {
        "schema_version": "1.0",
        "decision_type": "explicit_human_team_approval",
        "scope": "first_structurally_valid_eight_class_production_promotion",
        "approval_outcome": "approved",
        "decision_date": "2026-09-20",
        "decision_summary": "Synthetic approved first eight-class decision.",
        "model": {
            "model_id": CANDIDATE,
            "model_version": "0.1.0",
            "artifact_filename": "best.pt",
            "sha256": SHA,
            "ordered_taxonomy": TAXONOMY,
            "evaluation_evidence_reference": "ML_side/evaluation/candidates/heldout/summary.json",
        },
        "reviewed_evidence_references": ["ML_side/evaluation/candidates/heldout/summary.json"],
        "accepted_limitations": ["Pole remains recall-limited."],
    })


def _automatic_promotion_report() -> dict:
    return {
        "schema_version": "1.0.0",
        "tool": {"name": "compare_model_evaluations", "version": "1.0.0"},
        "candidate": {
            "artifact": "summary.json", "baseline_type": "evaluation",
            "filename": "best.pt", "sha256": SHA,
            "class_count": len(TAXONOMY), "ordered_class_names": TAXONOMY,
            "mode": "labelled_validation",
        },
        "candidate_validation": {
            "supplied": True, "source_filename": "candidate_model_report.json",
            "sha256": "c" * 64, "verdict": "pass",
        },
        "technical_compatibility": {"status": "compatible", "reasons": []},
        "policy_gate": {
            "configuration_supplied": True, "source_filename": "approved-gates.json",
            "sha256": "d" * 64, "schema_version": "1.0.0",
            "policy_status": "APPROVED_POLICY", "gates": {}, "result": "PASS", "reasons": [],
        },
        "verdict": "PASS",
    }


def promote_with_automatic_policy_pass(paths: dict[str, Path]) -> None:
    registry = _json(paths["registry"])
    registry["model_id"] = FUTURE_CANDIDATE
    registry["model_version"] = "1.0.0"
    registry["lifecycle"]["status"] = "production"
    registry["automatic_promotion_evidence"] = {
        "promotion_report_reference": "ML_side/model_registry/promotions/WB-OD-NAV-002-v1.0.0-comparison.json"
    }
    _write_json(paths["registry"], registry)
    manifest = _json(paths["manifest"])
    manifest["candidate_id"] = FUTURE_CANDIDATE
    manifest["expected_lifecycle"] = "production"
    _write_json(paths["manifest"], manifest)
    acceptance = _json(paths["acceptance"])
    acceptance["candidate"]["candidate_id"] = FUTURE_CANDIDATE
    _write_json(paths["acceptance"], acceptance)
    heldout = _json(paths["heldout"])
    heldout.update({
        "schema_version": "1.0.0",
        "tool": {"name": "evaluate_current_model", "version": "2.0.0"},
        "evaluation_settings": {"operating_point_inference": None, "validation_ap": {"engine": "ultralytics_model_val"}},
    })
    heldout["model"]["class_id_to_name"] = {str(index): name for index, name in enumerate(TAXONOMY)}
    _write_json(paths["heldout"], heldout)
    _write_json(paths["automatic"], _automatic_promotion_report())


def statuses(report: dict) -> dict[str, str]:
    return {
        check["name"]: check["status"]
        for section in report["sections"]
        for check in section["checks"]
    }


def run_fixture(tmp_path: Path) -> tuple[dict, dict[str, Path]]:
    paths = make_release_tree(tmp_path)
    return run_release_readiness(CANDIDATE, repository_root=tmp_path, generated_at_utc="2026-09-18T00:00:00Z"), paths


def test_current_production_evidence_passes_from_repository() -> None:
    report = run_release_readiness(CANDIDATE, generated_at_utc="2026-09-18T00:00:00Z")

    assert report["technical_readiness"] == "PASS"
    assert report["lifecycle_state"] == "production"
    assert report["production_authorization"] == "GRANTED (EXPLICIT HUMAN TEAM APPROVAL)"


def test_valid_registry_and_evidence_passes(tmp_path: Path) -> None:
    report, _ = run_fixture(tmp_path)

    assert report["technical_readiness"] == "PASS"
    assert statuses(report)["registry_record_exists"] == "PASS"


def test_missing_candidate_is_a_clean_failure(tmp_path: Path) -> None:
    make_release_tree(tmp_path)
    report = run_release_readiness("MISSING", repository_root=tmp_path, generated_at_utc="2026-09-18T00:00:00Z")

    assert report["technical_readiness"] == "FAIL"
    assert statuses(report)["candidate_manifest"] == "FAIL"


def test_registry_sha_mismatch_fails(tmp_path: Path) -> None:
    _, paths = run_fixture(tmp_path)
    registry = _json(paths["registry"])
    registry["artifact"]["sha256"] = "b" * 64
    _write_json(paths["registry"], registry)

    report = run_release_readiness(CANDIDATE, repository_root=tmp_path, generated_at_utc="2026-09-18T00:00:00Z")

    assert statuses(report)["registry_expected_sha256"] == "FAIL"


def test_taxonomy_mismatch_fails_against_canonical_contract(tmp_path: Path) -> None:
    _, paths = run_fixture(tmp_path)
    registry = _json(paths["registry"])
    registry["taxonomy"]["classes"] = list(reversed(TAXONOMY))
    _write_json(paths["registry"], registry)

    report = run_release_readiness(CANDIDATE, repository_root=tmp_path, generated_at_utc="2026-09-18T00:00:00Z")

    assert statuses(report)["registry_taxonomy_matches_canonical"] == "FAIL"


def test_missing_corrected_heldout_lineage_fails(tmp_path: Path) -> None:
    _, paths = run_fixture(tmp_path)
    heldout = _json(paths["heldout"])
    heldout["dataset_split"] = "validation"
    _write_json(paths["heldout"], heldout)

    report = run_release_readiness(CANDIDATE, repository_root=tmp_path, generated_at_utc="2026-09-18T00:00:00Z")

    assert statuses(report)["heldout_evaluation_record"] == "FAIL"


def test_missing_or_wrong_candidate_benchmark_evidence_fails(tmp_path: Path) -> None:
    _, paths = run_fixture(tmp_path)
    paths["benchmark"].unlink()
    missing = run_release_readiness(CANDIDATE, repository_root=tmp_path, generated_at_utc="2026-09-18T00:00:00Z")
    assert statuses(missing)["benchmark_evidence_exists"] == "FAIL"

    make_release_tree(tmp_path)
    benchmark = _json(paths["benchmark"])
    benchmark["model"]["sha256"] = "b" * 64
    _write_json(paths["benchmark"], benchmark)
    wrong = run_release_readiness(CANDIDATE, repository_root=tmp_path, generated_at_utc="2026-09-18T00:00:00Z")
    assert statuses(wrong)["benchmark_identity_matches_candidate"] == "FAIL"


def test_missing_safety_evidence_or_sha_mismatch_fails(tmp_path: Path) -> None:
    _, paths = run_fixture(tmp_path)
    paths["acceptance"].unlink()
    missing = run_release_readiness(CANDIDATE, repository_root=tmp_path, generated_at_utc="2026-09-18T00:00:00Z")
    assert statuses(missing)["runtime_acceptance_evidence_exists"] == "FAIL"

    make_release_tree(tmp_path)
    acceptance = _json(paths["acceptance"])
    acceptance["candidate"]["sha256"] = "b" * 64
    _write_json(paths["acceptance"], acceptance)
    mismatch = run_release_readiness(CANDIDATE, repository_root=tmp_path, generated_at_utc="2026-09-18T00:00:00Z")
    assert statuses(mismatch)["runtime_identity_matches_candidate"] == "FAIL"


def test_unitless_relative_depth_and_metres_claim_are_enforced(tmp_path: Path) -> None:
    _, paths = run_fixture(tmp_path)
    acceptance = _json(paths["acceptance"])
    acceptance["real_candidate_safety_validation"]["depth_semantics"]["relative_depth_unit"] = "metres"
    _write_json(paths["acceptance"], acceptance)

    report = run_release_readiness(CANDIDATE, repository_root=tmp_path, generated_at_utc="2026-09-18T00:00:00Z")

    assert statuses(report)["relative_depth_semantics"] == "FAIL"


def test_technical_pass_never_mutates_lifecycle_or_grants_production(tmp_path: Path) -> None:
    report, paths = run_fixture(tmp_path)

    assert _json(paths["registry"])["lifecycle"]["status"] == "candidate"
    assert report["lifecycle_state"] == "candidate"
    assert report["automatic_promotion_performed"] is False
    assert report["production_authorization"] == "NOT GRANTED"


def test_valid_explicit_first_eight_class_approval_is_read_only_and_authorizes_production(tmp_path: Path) -> None:
    paths = make_release_tree(tmp_path)
    promote_with_first_eight_class_approval(paths)

    report = run_release_readiness(CANDIDATE, repository_root=tmp_path, generated_at_utc="2026-09-18T00:00:00Z")

    assert report["technical_readiness"] == "PASS"
    assert report["lifecycle_state"] == "production"
    assert report["production_authorization"] == "GRANTED (EXPLICIT HUMAN TEAM APPROVAL)"
    assert report["automatic_promotion_performed"] is False
    assert _json(paths["registry"])["lifecycle"]["status"] == "production"


def test_malformed_explicit_approval_fails_closed(tmp_path: Path) -> None:
    paths = make_release_tree(tmp_path)
    promote_with_first_eight_class_approval(paths)
    approval = _json(paths["approval"])
    approval["model"]["sha256"] = "b" * 64
    _write_json(paths["approval"], approval)

    report = run_release_readiness(CANDIDATE, repository_root=tmp_path, generated_at_utc="2026-09-18T00:00:00Z")

    assert report["technical_readiness"] == "FAIL"
    assert report["production_authorization"] == "NOT GRANTED"
    assert statuses(report)["production_approval"] == "FAIL"


def test_missing_candidate1_human_approval_fails_closed(tmp_path: Path) -> None:
    paths = make_release_tree(tmp_path)
    registry = _json(paths["registry"])
    registry["lifecycle"]["status"] = "production"
    _write_json(paths["registry"], registry)
    manifest = _json(paths["manifest"])
    manifest["expected_lifecycle"] = "production"
    _write_json(paths["manifest"], manifest)

    report = run_release_readiness(CANDIDATE, repository_root=tmp_path, generated_at_utc="2026-09-18T00:00:00Z")

    assert report["technical_readiness"] == "FAIL"
    assert report["production_authorization"] == "NOT GRANTED"
    assert statuses(report)["production_approval"] == "FAIL"


def test_future_production_lifecycle_without_authorization_evidence_fails_closed(tmp_path: Path) -> None:
    paths = make_release_tree(tmp_path)
    promote_with_automatic_policy_pass(paths)
    registry = _json(paths["registry"])
    registry.pop("automatic_promotion_evidence")
    _write_json(paths["registry"], registry)

    report = run_release_readiness(FUTURE_CANDIDATE, repository_root=tmp_path, generated_at_utc="2026-09-18T00:00:00Z")

    assert report["technical_readiness"] == "FAIL"
    assert report["lifecycle_state"] == "production"
    assert report["production_authorization"] == "NOT GRANTED"
    assert statuses(report)["automatic_promotion_evidence"] == "FAIL"


def test_future_automatic_policy_pass_authorizes_production(tmp_path: Path) -> None:
    paths = make_release_tree(tmp_path)
    promote_with_automatic_policy_pass(paths)

    report = run_release_readiness(FUTURE_CANDIDATE, repository_root=tmp_path, generated_at_utc="2026-09-18T00:00:00Z")

    assert report["technical_readiness"] == "PASS"
    assert report["lifecycle_state"] == "production"
    assert report["production_authorization"] == "GRANTED (AUTOMATIC APPROVED POLICY PASS)"
    assert statuses(report)["automatic_promotion_evidence"] == "PASS"


@pytest.mark.parametrize(
    ("field", "value"),
    [("sha256", "b" * 64), ("ordered_class_names", list(reversed(TAXONOMY)))],
)
def test_future_automatic_policy_evidence_mismatch_fails_closed(tmp_path: Path, field: str, value: object) -> None:
    paths = make_release_tree(tmp_path)
    promote_with_automatic_policy_pass(paths)
    report_payload = _json(paths["automatic"])
    report_payload["candidate"][field] = value
    _write_json(paths["automatic"], report_payload)

    report = run_release_readiness(FUTURE_CANDIDATE, repository_root=tmp_path, generated_at_utc="2026-09-18T00:00:00Z")

    assert report["technical_readiness"] == "FAIL"
    assert report["production_authorization"] == "NOT GRANTED"
    assert statuses(report)["automatic_promotion_evidence"] == "FAIL"


def test_json_markdown_output_is_deterministic_and_portable(tmp_path: Path) -> None:
    report, _ = run_fixture(tmp_path)
    second, _ = run_fixture(tmp_path)

    assert report == second
    json_path, markdown_path = write_reports(tmp_path / "reports", report)
    assert json.loads(json_path.read_text(encoding="utf-8")) == report
    markdown = markdown_path.read_text(encoding="utf-8")
    assert markdown == render_markdown(report)
    assert str(tmp_path) not in json_path.read_text(encoding="utf-8")
    assert "Production authorization: **NOT GRANTED**" in markdown


def _live_responses(*, sha: str = SHA):
    responses = {
        "/ml/model-info": (200, {"loaded": True, "filename": "best.pt", "sha256": sha, "size_bytes": 5364741, "classes": TAXONOMY, "taxonomy_compatible": True, "checksum_verified": None}),
        "/ml/ready": (200, {"ready": True}),
        "/ml/health": (200, {"status": "ok"}),
        "/ml/metrics": (200, {**{key: 0 for key in preflight.METRIC_COUNTERS}, **{key: None for key in preflight.METRIC_LATENCIES}}),
    }
    return lambda url, _timeout, _key: responses[next(endpoint for endpoint in responses if url.endswith(endpoint))]


def test_optional_live_endpoint_success_and_identity_mismatch(tmp_path: Path) -> None:
    make_release_tree(tmp_path)
    passed = run_release_readiness(CANDIDATE, repository_root=tmp_path, live_base_url="http://backend:8000", http_get=_live_responses(), generated_at_utc="2026-09-18T00:00:00Z")
    assert next(item for item in passed["sections"] if item["name"] == "Live verification")["status"] == "PASS"
    assert statuses(passed)["backend_checksum_observability"] == "PASS"

    mismatch = run_release_readiness(CANDIDATE, repository_root=tmp_path, live_base_url="http://backend:8000", http_get=_live_responses(sha="b" * 64), generated_at_utc="2026-09-18T00:00:00Z")
    assert statuses(mismatch)["backend_model_sha256"] == "FAIL"


def test_optional_live_endpoint_unavailable_is_reported(tmp_path: Path) -> None:
    make_release_tree(tmp_path)

    def unavailable(*_args):
        raise preflight.BackendTransportError("unavailable")

    report = run_release_readiness(CANDIDATE, repository_root=tmp_path, live_base_url="http://backend:8000", http_get=unavailable, generated_at_utc="2026-09-18T00:00:00Z")

    assert statuses(report)["backend_transport/ml/model-info"] == "FAIL"


def test_optional_live_output_redacts_private_paths_ips_and_secrets(tmp_path: Path) -> None:
    make_release_tree(tmp_path)

    def responses(url, _timeout, _key):
        response = _live_responses()(url, _timeout, _key)
        if url.endswith("/ml/health"):
            return 200, {"status": "ok", "diagnostic_path": r"C:\Users\developer\run.log", "api_key": "must-not-leak", "host": "127.0.0.1"}
        return response

    report = run_release_readiness(CANDIDATE, repository_root=tmp_path, live_base_url="http://127.0.0.1:8000", http_get=responses, generated_at_utc="2026-09-18T00:00:00Z")

    encoded = json.dumps(report)
    assert r"C:\\Users\\developer" not in encoded
    assert "must-not-leak" not in encoded
    assert "127.0.0.1" not in encoded
