"""Tests for the read-only WalkBuddy runtime preflight tool."""

from __future__ import annotations

import json
import sys
from pathlib import Path

import pytest


TOOLS_DIR = Path(__file__).resolve().parents[1] / "tools"
sys.path.insert(0, str(TOOLS_DIR))

import runtime_preflight as preflight


CLASSES = ("person", "stairs", "door", "chair", "table", "pole", "bicycle", "vehicle")
EXPECTED = preflight.ExpectedIdentity(
    filename="best.pt", sha256=None, size_bytes=None, taxonomy=CLASSES
)


class FakeTorch:
    __version__ = "2.test"

    class version:
        cuda = "13.0"

    class cuda:
        available = True

        @classmethod
        def is_available(cls):
            return cls.available

        @staticmethod
        def get_device_name(_index):
            return "Fake GPU"

        @staticmethod
        def get_device_properties(_index):
            return type("Props", (), {"total_memory": 8_000_000_000})()


class FakeModel:
    names = dict(enumerate(CLASSES))


def model_loader(_path: str):
    return FakeModel()


def make_model(tmp_path: Path, name: str = "best.pt", content: bytes = b"candidate") -> Path:
    path = tmp_path / name
    path.write_bytes(content)
    return path


def expected_for(path: Path, *, taxonomy=CLASSES, filename: str | None = None, size: int | None = None, sha: str | None = None):
    return preflight.ExpectedIdentity(
        filename=filename if filename is not None else path.name,
        size_bytes=size if size is not None else path.stat().st_size,
        sha256=sha if sha is not None else preflight.calculate_sha256(path),
        taxonomy=taxonomy,
    )


def backend_responses(*, ready=True, health="ok", malformed=False):
    info = {
        "loaded": True,
        "filename": "best.pt",
        "size_bytes": 9,
        "sha256": "abc",
        "classes": list(CLASSES),
        "taxonomy_compatible": True,
    }
    metrics = {key: 0 for key in preflight.METRIC_COUNTERS}
    metrics.update({key: None for key in preflight.METRIC_LATENCIES})
    responses = {
        "/ml/model-info": (200, "not-an-object" if malformed else info),
        "/ml/ready": (200 if ready else 503, {"ready": ready}),
        "/ml/health": (200, {"status": health}),
        "/ml/metrics": (200, metrics),
    }
    def get(url, _timeout, _key):
        return responses[next(endpoint for endpoint in responses if url.endswith(endpoint))]
    return get


def statuses(report):
    return {item["name"]: item["status"] for item in report["checks"]}


def test_correct_candidate_identity_passes(tmp_path):
    path = make_model(tmp_path)
    report = preflight.run_preflight(model_path=path, expected=expected_for(path), torch_module=FakeTorch, model_loader=model_loader)
    assert report["overall_result"] == "PASS"
    assert statuses(report)["model_taxonomy"] == "pass"


@pytest.mark.parametrize("field", ("sha", "size", "filename"))
def test_wrong_identity_fields_fail(tmp_path, field):
    path = make_model(tmp_path)
    kwargs = {field: "wrong" if field != "size" else 99}
    report = preflight.run_preflight(model_path=path, expected=expected_for(path, **kwargs), torch_module=FakeTorch, model_loader=model_loader)
    assert report["overall_result"] == "FAIL"


def test_wrong_taxonomy_order_fails(tmp_path):
    path = make_model(tmp_path)
    report = preflight.run_preflight(model_path=path, expected=expected_for(path, taxonomy=tuple(reversed(CLASSES))), torch_module=FakeTorch, model_loader=model_loader)
    assert statuses(report)["model_taxonomy"] == "fail"


def test_cuda_available_passes_and_records_gpu():
    report = preflight.run_preflight(torch_module=FakeTorch)
    assert report["runtime_environment"]["selected_device"] == "cuda:0"
    assert report["runtime_environment"]["gpu_name"] == "Fake GPU"
    assert report["overall_result"] == "PASS"


def test_cpu_only_is_warning_without_requirement():
    FakeTorch.cuda.available = False
    try:
        report = preflight.run_preflight(torch_module=FakeTorch)
    finally:
        FakeTorch.cuda.available = True
    assert report["overall_result"] == "WARNING"
    assert report["runtime_environment"]["cpu_only"] is True


def test_require_cuda_fails_when_unavailable():
    FakeTorch.cuda.available = False
    try:
        report = preflight.run_preflight(torch_module=FakeTorch, require_cuda=True)
    finally:
        FakeTorch.cuda.available = True
    assert report["overall_result"] == "FAIL"
    assert statuses(report)["require_cuda"] == "fail"


def test_backend_happy_path_and_metrics_parse():
    expected = preflight.ExpectedIdentity(filename="best.pt", sha256="abc", size_bytes=9, taxonomy=CLASSES)
    report = preflight.run_preflight(expected=expected, base_url="http://backend:8000", torch_module=FakeTorch, http_get=backend_responses())
    assert report["overall_result"] == "PASS"
    assert statuses(report)["backend_metrics"] == "pass"


def test_backend_unavailable_fails():
    def unavailable(*_args):
        raise preflight.PreflightError("Backend request failed.")
    report = preflight.run_preflight(base_url="http://backend:8000", torch_module=FakeTorch, http_get=unavailable)
    assert report["overall_result"] == "FAIL"


def test_backend_ready_false_health_failure_and_malformed_response_fail():
    expected = preflight.ExpectedIdentity(filename="best.pt", sha256="abc", size_bytes=9, taxonomy=CLASSES)
    report = preflight.run_preflight(expected=expected, base_url="http://backend:8000", torch_module=FakeTorch, http_get=backend_responses(ready=False, health="degraded"))
    assert statuses(report)["backend_ready"] == "fail"
    assert statuses(report)["backend_health"] == "fail"
    malformed = preflight.run_preflight(expected=expected, base_url="http://backend:8000", torch_module=FakeTorch, http_get=backend_responses(malformed=True))
    assert statuses(malformed)["backend_model_info"] == "fail"


def test_backend_wrong_identity_and_malformed_metrics_fail():
    expected = preflight.ExpectedIdentity(filename="best.pt", sha256="expected", size_bytes=9, taxonomy=CLASSES)
    wrong_identity = preflight.run_preflight(expected=expected, base_url="http://backend:8000", torch_module=FakeTorch, http_get=backend_responses())
    assert statuses(wrong_identity)["backend_model_sha256"] == "fail"

    def invalid_metrics(url, timeout, key):
        status, payload = backend_responses()(url, timeout, key)
        if url.endswith("/ml/metrics"):
            return status, {"total_attempts": "not-a-number"}
        return status, payload

    valid_identity = preflight.ExpectedIdentity(filename="best.pt", sha256="abc", size_bytes=9, taxonomy=CLASSES)
    malformed = preflight.run_preflight(expected=valid_identity, base_url="http://backend:8000", torch_module=FakeTorch, http_get=invalid_metrics)
    assert statuses(malformed)["backend_metrics"] == "fail"


def test_json_and_markdown_report_generation(tmp_path):
    report = preflight.run_preflight(torch_module=FakeTorch)
    json_path = tmp_path / "evidence" / "preflight.json"
    markdown_path = tmp_path / "evidence" / "preflight.md"
    preflight._write_text(json_path, json.dumps(report, indent=2) + "\n")
    preflight._write_text(markdown_path, preflight.render_markdown(report))
    assert json.loads(json_path.read_text(encoding="utf-8"))["overall_result"] == "PASS"
    assert "## Compute Device" in markdown_path.read_text(encoding="utf-8")


def test_candidate_record_is_optional_future_candidate_configuration(tmp_path):
    record = tmp_path / "candidate.json"
    record.write_text(json.dumps({"artifact": {"filename": "future.pt", "sha256": "future"}, "taxonomy": {"classes": list(CLASSES)}}), encoding="utf-8")
    args = preflight.parse_args(["--candidate-record", str(record), "--expected-size", "123"])
    expected = preflight.resolve_expected_identity(args)
    assert expected.filename == "future.pt"
    assert expected.size_bytes == 123
