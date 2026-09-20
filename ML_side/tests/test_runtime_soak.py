"""Model-free coverage for Candidate runtime soak validation."""

from __future__ import annotations

import asyncio
import json
import sys
from pathlib import Path

import pytest


ML_SIDE_DIR = Path(__file__).resolve().parents[1]
if str(ML_SIDE_DIR) not in sys.path:
    sys.path.insert(0, str(ML_SIDE_DIR))

from runtime_soak_lib.core import (
    RuntimeSoakError,
    SoakConfig,
    SyntheticBackend,
    SyntheticTransport,
    collect_nonheldout_fixtures,
    latency_summary,
    reconcile_metrics,
    resolve_candidate,
    run_mock_soak,
    run_protocol_soak,
    validate_protocol_response,
    validate_runtime_endpoints,
)
from runtime_soak_lib.outputs import render_markdown, write_reports


def _config(**overrides: object) -> SoakConfig:
    values: dict[str, object] = {
        "candidate_id": "WB-OD-NAV-001",
        "frames": 5,
        "interval_ms": 0,
        "reconnect_every": 0,
        "malformed_every": 0,
        "settle_ms": 0,
    }
    values.update(overrides)
    return SoakConfig(**values)  # type: ignore[arg-type]


def _report(config: SoakConfig, **kwargs: object) -> dict:
    return asyncio.run(run_mock_soak(config, **kwargs))


def _candidate():
    return resolve_candidate("WB-OD-NAV-001")


def test_resolves_current_candidate_from_manifest_registry_and_canonical_taxonomy() -> None:
    candidate = _candidate()

    assert candidate.run_id == "navigation-mvp-full-candidate-56c445bb8c85"
    assert candidate.lifecycle_state == "production"
    assert candidate.taxonomy == (
        "person", "stairs", "door", "chair", "table", "pole", "bicycle", "vehicle"
    )


def test_endpoint_contract_rejects_wrong_sha_taxonomy_and_not_ready() -> None:
    candidate = _candidate()
    backend = SyntheticBackend(candidate)
    backend.model_info["sha256"] = "b" * 64
    assert any(check["name"] == "runtime_candidate_identity" and check["status"] == "FAIL" for check in validate_runtime_endpoints(candidate, backend.endpoints()))

    backend = SyntheticBackend(candidate)
    backend.model_info["classes"] = list(reversed(candidate.taxonomy))
    assert any(check["name"] == "runtime_candidate_identity" and check["status"] == "FAIL" for check in validate_runtime_endpoints(candidate, backend.endpoints()))

    backend = SyntheticBackend(candidate)
    backend.ready = False
    assert any(check["name"] == "runtime_ready" and check["status"] == "FAIL" for check in validate_runtime_endpoints(candidate, backend.endpoints()))


def test_sustained_mock_session_is_explicitly_synthetic_and_passes() -> None:
    report = _report(_config())

    assert report["technical_verdict"] == "PASS"
    assert report["evidence_mode"] == "synthetic/mock"
    assert report["real_candidate_runtime_validated"] is False
    assert report["frame_summary"]["successful_results"] == 5
    assert report["frame_summary"]["attempted_valid_frames"] == 5
    assert report["frame_summary"]["successful_valid_responses"] == 5
    assert report["backend_metrics"]["status"] == "PASS"


def test_deliberate_reconnects_are_not_failures_when_the_next_frame_succeeds() -> None:
    report = _report(_config(frames=6, reconnect_every=2))

    assert report["technical_verdict"] == "PASS"
    assert report["frame_summary"]["deliberate_reconnect_attempts"] == 2
    assert report["frame_summary"]["successful_reconnects"] == 2
    assert report["frame_summary"]["reconnect_failures"] == 0


def test_reconnect_failure_is_a_hard_failure() -> None:
    candidate = _candidate()
    backend = SyntheticBackend(candidate)
    transport = SyntheticTransport(backend, fail_connect_attempts={2})

    report = _report(_config(frames=5, reconnect_every=2), backend=backend, transport=transport)

    assert report["technical_verdict"] == "FAIL"
    assert report["frame_summary"]["reconnect_failures"] == 1
    assert any("Deliberate reconnect failed" in detail for detail in report["hard_failure_conditions"])


def test_recovered_unexpected_disconnect_is_recorded_without_hiding_it() -> None:
    candidate = _candidate()
    backend = SyntheticBackend(candidate)
    transport = SyntheticTransport(backend, unexpected_sequences={3})

    report = _report(_config(), backend=backend, transport=transport)

    assert report["technical_verdict"] == "PASS"
    assert report["frame_summary"]["unexpected_disconnects"] == 1
    assert report["frame_summary"]["unrecovered_unexpected_disconnects"] == 0
    assert report["frames"][2]["unexpected_disconnect_recovered"] is True


def test_malformed_frame_uses_stable_error_and_later_valid_frame_succeeds() -> None:
    report = _report(_config(frames=5, malformed_every=2))

    assert report["technical_verdict"] == "PASS"
    assert report["frame_summary"]["malformed_input_injections"] == 2
    assert report["frame_summary"]["malformed_public_errors"] == 2
    assert report["frame_summary"]["post_malformed_valid_successes"] == 2
    assert report["frame_summary"]["malformed_recovery_status"] == "PASS"
    malformed_record = next(record for record in report["frames"] if record["malformed_input"])
    assert malformed_record["response_type"] == "error"
    assert malformed_record["error_code"] == "inference_failed"


def test_public_error_contract_rejects_private_exception_leak() -> None:
    response = json.dumps({
        "type": "error",
        "code": "inference_failed",
        "frame_id": "soak-000001",
        "message": "Traceback: C:\\private\\weights.pt failed",
    })

    _, problems = validate_protocol_response(
        response,
        frame_id="soak-000001",
        malformed=True,
        expected_location={"latitude": 0.0, "longitude": 0.0},
    )

    assert any("private exception" in problem for problem in problems)


def test_success_location_and_depth_contracts_are_checked_without_distance_inference() -> None:
    result = json.dumps({
        "type": "detection_result",
        "frame_id": "frame-1",
        "detections": [{"relative_depth": 0.4, "distance_m": None}],
        "guidance_message": "Path clear",
        "risk_level": "CLEAR",
        "inference_time_ms": 1,
        "server_timestamp_ms": 2,
        "location": {"latitude": 0.0, "longitude": 0.0},
    })
    response, problems = validate_protocol_response(
        result,
        frame_id="frame-1",
        malformed=False,
        expected_location={"latitude": 0.0, "longitude": 0.0},
    )
    assert response["type"] == "detection_result"
    assert problems == []

    invalid = result.replace('"distance_m": null', '"distance_m": 1.0')
    _, problems = validate_protocol_response(
        invalid,
        frame_id="frame-1",
        malformed=False,
        expected_location={"latitude": 0.0, "longitude": 0.0},
    )
    assert "distance_m must not be populated from relative_depth." in problems


def test_metrics_reconciliation_detects_impossible_deltas_and_nonzero_active() -> None:
    before = {
        "total_attempts": 1, "successful_inferences": 1, "failed_inferences": 0,
        "active_inferences": 0, "processed_frames": 1, "dropped_frames": 0,
        "latest_latency_ms": 1.0, "mean_latency_ms": 1.0, "p50_latency_ms": 1.0,
        "p95_latency_ms": 1.0, "max_latency_ms": 1.0,
    }
    after = dict(before, total_attempts=3, successful_inferences=2, failed_inferences=0, processed_frames=2, active_inferences=1)

    reconciliation = reconcile_metrics(before, after, client_successes=1, client_errors=0)

    assert reconciliation["status"] == "FAIL"
    assert any("total_attempts" in item for item in reconciliation["details"])
    assert any("active_inferences" in item for item in reconciliation["details"])


def test_nonzero_final_active_inferences_fails_the_soak() -> None:
    candidate = _candidate()
    backend = SyntheticBackend(candidate)
    backend.force_final_active = 1

    report = _report(_config(), backend=backend)

    assert report["technical_verdict"] == "FAIL"
    assert any("active_inferences" in detail for detail in report["hard_failure_conditions"])


def test_latency_statistics_include_linear_p50_p95_and_p99() -> None:
    summary = latency_summary([1.0, 2.0, 3.0, 4.0, 5.0], elapsed_seconds=2.5, successes=5)

    assert summary == {
        "count": 5,
        "mean_ms": 3.0,
        "median_ms": 3.0,
        "p50_ms": 3.0,
        "p95_ms": 4.8,
        "p99_ms": 4.96,
        "min_ms": 1.0,
        "max_ms": 5.0,
        "throughput_fps": 2.0,
    }


def test_reports_are_deterministic_sanitized_and_do_not_mutate_lifecycle(tmp_path: Path) -> None:
    record_path = ML_SIDE_DIR / "model_registry" / "records" / "navigation_candidate.json"
    original_record = record_path.read_bytes()

    def fixed_time() -> str:
        return "2026-09-19T00:00:00Z"

    def monotonic_values():
        values = iter(value / 1000 for value in range(1000))
        return lambda: next(values)

    first = _report(_config(frames=3), monotonic=monotonic_values(), utc_now=fixed_time)
    second = _report(_config(frames=3), monotonic=monotonic_values(), utc_now=fixed_time)
    assert first == second
    json_path, markdown_path = write_reports(tmp_path, first)
    encoded = json_path.read_text(encoding="utf-8")
    assert json.loads(encoded) == first
    assert str(tmp_path) not in encoded
    assert "Production authorization: **NOT GRANTED**" in markdown_path.read_text(encoding="utf-8")
    assert record_path.read_bytes() == original_record


def test_private_base_url_is_sanitized_in_a_synthetic_report() -> None:
    candidate = _candidate()
    backend = SyntheticBackend(candidate)
    endpoints = backend.endpoints()
    checks = validate_runtime_endpoints(candidate, endpoints)

    async def after_metrics():
        return backend.snapshot()

    report = asyncio.run(run_protocol_soak(
        candidate,
        _config(frames=1),
        SyntheticTransport(backend),
        [b"synthetic"],
        before_metrics=endpoints["/ml/metrics"]["payload"],
        after_metrics=after_metrics,
        evidence_mode="synthetic/mock",
        real_candidate_runtime_validated=False,
        base_url="http://192.168.50.10:8000",
        endpoint_checks=checks,
    ))

    assert "192.168.50.10" not in json.dumps(report)
    assert report["runtime"]["base_url"] == "http://<LAN_IP>:8000"


def test_fixture_provenance_and_runtime_facts_are_portable() -> None:
    candidate = _candidate()
    backend = SyntheticBackend(candidate)
    endpoints = backend.endpoints()
    checks = validate_runtime_endpoints(candidate, endpoints)

    async def after_metrics():
        return backend.snapshot()

    report = asyncio.run(run_protocol_soak(
        candidate,
        _config(frames=1),
        SyntheticTransport(backend),
        [b"synthetic"],
        before_metrics=endpoints["/ml/metrics"]["payload"],
        after_metrics=after_metrics,
        evidence_mode="synthetic/mock",
        real_candidate_runtime_validated=False,
        base_url=None,
        endpoint_checks=checks,
        fixture_provenance=r"C:\Users\developer\private-fixtures",
        runtime_environment={
            "torch_version": "2.test",
            "cuda_usable": True,
            "gpu_name": "test GPU",
            "untrusted_path": r"C:\Users\developer\secret",
        },
    ))

    encoded = json.dumps(report)
    assert "developer" not in encoded
    assert report["parameters"]["fixture_provenance"] == "synthetic encoded image payloads"
    assert report["runtime_environment"] == {
        "torch_version": "2.test", "cuda_usable": True, "gpu_name": "test GPU"
    }


def test_named_backend_host_is_also_sanitized_in_a_report() -> None:
    candidate = _candidate()
    backend = SyntheticBackend(candidate)
    endpoints = backend.endpoints()
    checks = validate_runtime_endpoints(candidate, endpoints)

    async def after_metrics():
        return backend.snapshot()

    report = asyncio.run(run_protocol_soak(
        candidate,
        _config(frames=1),
        SyntheticTransport(backend),
        [b"synthetic"],
        before_metrics=endpoints["/ml/metrics"]["payload"],
        after_metrics=after_metrics,
        evidence_mode="synthetic/mock",
        real_candidate_runtime_validated=False,
        base_url="https://runtime.internal.example:8443",
        endpoint_checks=checks,
    ))

    assert "runtime.internal.example" not in json.dumps(report)
    assert report["runtime"]["base_url"] == "https://<BACKEND_HOST>:8443"


def test_heldout_fixture_directory_is_refused(tmp_path: Path) -> None:
    heldout = tmp_path / "held-out"
    heldout.mkdir()
    (heldout / "fixture.png").write_bytes(b"data")

    with pytest.raises(RuntimeSoakError, match="Held-out"):
        collect_nonheldout_fixtures(heldout)


def test_evaluation_only_fixture_directory_is_refused(tmp_path: Path) -> None:
    evaluation = tmp_path / "evaluation-only"
    evaluation.mkdir()
    (evaluation / "fixture.png").write_bytes(b"data")

    with pytest.raises(RuntimeSoakError, match="Evaluation-only"):
        collect_nonheldout_fixtures(evaluation)
