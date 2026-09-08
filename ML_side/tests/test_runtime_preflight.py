"""Tests for the read-only WalkBuddy runtime preflight tool."""

from __future__ import annotations

import json
import sys
from io import BytesIO
from pathlib import Path
from urllib.error import HTTPError

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

        @staticmethod
        def synchronize(_index):
            return None

    @staticmethod
    def empty(_size, *, device):
        assert device == "cuda:0"
        return FakeTensor()


class FakeTensor:
    def __add__(self, _value):
        return self

    def item(self):
        return 1


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
    assert report["runtime_environment"]["cuda_usable"] is True
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


def test_cuda_reported_available_but_unusable_fails_without_traceback():
    class UnusableTorch(FakeTorch):
        @staticmethod
        def empty(_size, *, device):
            raise RuntimeError(f"cannot allocate on {device}")

    report = preflight.run_preflight(torch_module=UnusableTorch, require_cuda=True)
    assert report["overall_result"] == "FAIL"
    assert statuses(report)["cuda_available"] == "fail"
    assert statuses(report)["require_cuda"] == "fail"


def test_cuda_metadata_failure_is_warning_not_full_pass():
    class NoMetadataTorch(FakeTorch):
        class cuda(FakeTorch.cuda):
            @staticmethod
            def get_device_name(_index):
                raise RuntimeError("metadata unavailable")

    report = preflight.run_preflight(torch_module=NoMetadataTorch)
    assert report["overall_result"] == "WARNING"
    assert statuses(report)["cuda_metadata"] == "warning"


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


@pytest.mark.parametrize(
    ("error", "check"),
    (
        (preflight.BackendTransportError("Backend request timed out."), "backend_transport/ml/model-info"),
        (preflight.BackendHTTPError("Backend returned HTTP 401."), "backend_http/ml/model-info"),
        (preflight.BackendResponseError("Backend returned malformed JSON."), "backend_response/ml/model-info"),
    ),
)
def test_backend_errors_are_classified_cleanly(error, check):
    def failing(*_args):
        raise error

    report = preflight.run_preflight(base_url="http://backend:8000", torch_module=FakeTorch, http_get=failing)
    assert report["overall_result"] == "FAIL"
    assert statuses(report)[check] == "fail"


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


@pytest.mark.parametrize("bad_value", (True, float("nan"), float("inf"), float("-inf")))
def test_backend_metrics_reject_bool_and_nonfinite_values(bad_value):
    expected = preflight.ExpectedIdentity(filename="best.pt", sha256="abc", size_bytes=9, taxonomy=CLASSES)

    def invalid_metrics(url, timeout, key):
        status, payload = backend_responses()(url, timeout, key)
        if url.endswith("/ml/metrics"):
            payload = dict(payload)
            payload["mean_latency_ms"] = bad_value
        return status, payload

    report = preflight.run_preflight(expected=expected, base_url="http://backend:8000", torch_module=FakeTorch, http_get=invalid_metrics)
    assert statuses(report)["backend_metrics"] == "fail"


@pytest.mark.parametrize("missing_field", ("loaded", "filename", "sha256", "size_bytes", "classes", "taxonomy_compatible"))
def test_backend_model_info_required_fields_are_explicitly_checked(missing_field):
    expected = preflight.ExpectedIdentity(filename="best.pt", sha256="abc", size_bytes=9, taxonomy=CLASSES)

    def missing_info(url, timeout, key):
        status, payload = backend_responses()(url, timeout, key)
        if url.endswith("/ml/model-info"):
            payload = dict(payload)
            payload.pop(missing_field)
        return status, payload

    report = preflight.run_preflight(expected=expected, base_url="http://backend:8000", torch_module=FakeTorch, http_get=missing_info)
    assert statuses(report)["backend_model_info_contract"] == "fail"


def test_partial_local_identity_is_warning(tmp_path):
    path = make_model(tmp_path)
    report = preflight.run_preflight(model_path=path, expected=preflight.ExpectedIdentity(filename=path.name), torch_module=FakeTorch)
    assert report["overall_result"] == "WARNING"
    assert statuses(report)["model_identity_configuration"] == "warning"


def test_nonconsecutive_model_class_ids_fail(tmp_path):
    path = make_model(tmp_path)

    class GappedModel:
        names = {0: "person", 2: "stairs"}

    report = preflight.run_preflight(
        model_path=path,
        expected=preflight.ExpectedIdentity(taxonomy=("person", "stairs")),
        torch_module=FakeTorch,
        model_loader=lambda _path: GappedModel(),
    )
    assert statuses(report)["model_taxonomy"] == "fail"


def test_malformed_model_class_ids_fail():
    with pytest.raises(preflight.PreflightError, match="malformed"):
        preflight._normalise_classes({"01": "person"})


def test_missing_torchvision_is_reported_without_failing_torch_runtime(monkeypatch):
    def missing_package(_name):
        raise preflight.PackageNotFoundError

    monkeypatch.setattr(preflight, "version", missing_package)
    report = preflight.run_preflight(torch_module=FakeTorch)
    assert report["runtime_environment"]["torchvision_version"] is None
    assert report["overall_result"] == "PASS"


class FakeResponse:
    def __init__(self, body: bytes, status: int = 200):
        self.body = body
        self.status = status

    def __enter__(self):
        return self

    def __exit__(self, *_args):
        return False

    def read(self):
        return self.body


def test_http_get_rejects_invalid_url():
    with pytest.raises(preflight.BackendTransportError, match="absolute"):
        preflight._http_get("backend:8000/ml/ready", 1, None)


@pytest.mark.parametrize(
    "exception, error_type",
    (
        (TimeoutError(), preflight.BackendTransportError),
        (preflight.URLError(ConnectionRefusedError()), preflight.BackendTransportError),
        (HTTPError("http://backend", 401, "error", {}, BytesIO(b"")), preflight.BackendHTTPError),
        (HTTPError("http://backend", 404, "error", {}, BytesIO(b"")), preflight.BackendHTTPError),
        (HTTPError("http://backend", 500, "error", {}, BytesIO(b"")), preflight.BackendHTTPError),
    ),
)
def test_http_get_classifies_timeout_and_http_errors(monkeypatch, exception, error_type):
    def fail(*_args, **_kwargs):
        raise exception

    monkeypatch.setattr(preflight, "urlopen", fail)
    with pytest.raises(error_type):
        preflight._http_get("http://backend:8000/ml/ready", 1, None)


@pytest.mark.parametrize("body", (b"", b"not json", b"\xff"))
def test_http_get_rejects_empty_malformed_or_nonutf8_success_response(monkeypatch, body):
    monkeypatch.setattr(preflight, "urlopen", lambda *_args, **_kwargs: FakeResponse(body))
    with pytest.raises(preflight.BackendResponseError):
        preflight._http_get("http://backend:8000/ml/ready", 1, None)


@pytest.mark.parametrize("target", ("model", "markdown_model", "inside_model_dir", "same_reports"))
def test_unsafe_report_paths_fail_before_writing_and_preserve_model(tmp_path, target, capsys):
    model = tmp_path / "candidate_artifacts" / "weights" / "best.pt"
    model.parent.mkdir(parents=True)
    original = b"candidate bytes must remain unchanged"
    model.write_bytes(original)
    safe_dir = tmp_path / "evidence"
    safe_dir.mkdir()
    json_out = safe_dir / "preflight.json"
    markdown_out = safe_dir / "preflight.md"
    if target == "model":
        json_out = model
    elif target == "markdown_model":
        markdown_out = model
    elif target == "inside_model_dir":
        json_out = model.parent / "preflight.json"
    elif target == "same_reports":
        markdown_out = json_out

    result = preflight.main(["--model", str(model), "--json-out", str(json_out), "--markdown-out", str(markdown_out)])
    assert result == 2
    assert model.read_bytes() == original
    assert "Runtime preflight failed:" in capsys.readouterr().err


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
