"""Read-only runtime preflight for WalkBuddy navigation-model deployments.

The tool records enough local runtime and backend state to make an accidental
CPU-only PyTorch deployment visible before a physical-device run.  It does not
train, copy, promote, or alter any model artifact or lifecycle record.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import math
import os
import platform
import socket
import sys
import tempfile
from collections.abc import Callable, Mapping, Sequence
from dataclasses import asdict, dataclass
from datetime import UTC, datetime
from importlib.metadata import PackageNotFoundError, version
from pathlib import Path
from typing import Any
from urllib.error import HTTPError, URLError
from urllib.parse import urlparse
from urllib.request import Request, urlopen


TOOL_NAME = "walkbuddy_runtime_preflight"
TOOL_VERSION = "1.0.0"
CHECKSUM_CHUNK_SIZE = 1024 * 1024
DEFAULT_TIMEOUT_SECONDS = 5.0
METRIC_COUNTERS = (
    "total_attempts",
    "successful_inferences",
    "failed_inferences",
    "processed_frames",
    "dropped_frames",
)
METRIC_LATENCIES = (
    "latest_latency_ms",
    "mean_latency_ms",
    "p50_latency_ms",
    "p95_latency_ms",
    "max_latency_ms",
)
ML_SIDE_DIR = Path(__file__).resolve().parents[1]
KNOWN_MODEL_DIRECTORIES = (ML_SIDE_DIR / "models", ML_SIDE_DIR / "artifacts")


class PreflightError(Exception):
    """Raised for invalid CLI configuration or unsafe report output."""


class BackendTransportError(PreflightError):
    """Raised when a backend cannot be contacted at the supplied URL."""


class BackendHTTPError(PreflightError):
    """Raised when a backend endpoint returns a non-success status."""


class BackendResponseError(PreflightError):
    """Raised when a successful backend response cannot be parsed as JSON."""


@dataclass(frozen=True)
class ExpectedIdentity:
    filename: str | None = None
    sha256: str | None = None
    size_bytes: int | None = None
    taxonomy: tuple[str, ...] | None = None
    source: str | None = None


def _utc_now() -> str:
    return datetime.now(UTC).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def _check(name: str, status: str, detail: str) -> dict[str, str]:
    return {"name": name, "status": status, "detail": detail}


def calculate_sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as artifact:
        for chunk in iter(lambda: artifact.read(CHECKSUM_CHUNK_SIZE), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _normalise_classes(names: object) -> list[str]:
    if isinstance(names, Mapping):
        raw_items = names.items()
    elif isinstance(names, Sequence) and not isinstance(names, (str, bytes)):
        raw_items = enumerate(names)
    else:
        raise PreflightError("Model class metadata is missing or malformed.")

    classes: dict[int, str] = {}
    for raw_index, raw_name in raw_items:
        if isinstance(raw_index, bool):
            raise PreflightError("Model class metadata is missing or malformed.")
        if isinstance(raw_index, int):
            index = raw_index
        elif isinstance(raw_index, str) and raw_index.isascii() and raw_index.isdecimal():
            index = int(raw_index)
            if raw_index != str(index):
                raise PreflightError("Model class metadata is missing or malformed.")
        else:
            raise PreflightError("Model class metadata is missing or malformed.")
        if index < 0 or index in classes or not isinstance(raw_name, str) or not raw_name.strip():
            raise PreflightError("Model class metadata is missing or malformed.")
        classes[index] = raw_name.strip()
    if not classes:
        raise PreflightError("Model class metadata is missing or malformed.")
    if tuple(sorted(classes)) != tuple(range(len(classes))):
        raise PreflightError("Model class metadata IDs must be consecutive from zero.")
    return [classes[index] for index in sorted(classes)]


def _load_taxonomy(path: Path, model_loader: Callable[[str], Any] | None = None) -> list[str]:
    if model_loader is None:
        try:
            from ultralytics import YOLO
        except ImportError as exc:
            raise PreflightError("Ultralytics is unavailable; model taxonomy cannot be inspected.") from exc
        model_loader = YOLO
    try:
        model = model_loader(str(path))
        return _normalise_classes(model.names)
    except PreflightError:
        raise
    except Exception as exc:
        raise PreflightError("Model taxonomy could not be loaded.") from exc


def _torch_runtime(torch_module: Any | None = None) -> tuple[dict[str, object], list[dict[str, str]]]:
    checks: list[dict[str, str]] = []
    runtime: dict[str, object] = {
        "python_version": sys.version.split()[0],
        "platform": platform.platform(),
        "torch_version": None,
        "torchvision_version": None,
        "cuda_available": None,
        "cuda_usable": None,
        "cuda_build": None,
        "selected_device": "unknown",
        "gpu_name": None,
        "gpu_memory_bytes": None,
        "cpu_only": None,
    }
    checks.append(_check("python_version", "pass", f"Python {runtime['python_version']}"))
    if torch_module is None:
        try:
            import torch as torch_module  # type: ignore[no-redef]
        except ImportError:
            checks.append(_check("torch", "warning", "PyTorch is not installed; compute device is unknown."))
            return runtime, checks

    runtime["torch_version"] = getattr(torch_module, "__version__", None)
    try:
        runtime["torchvision_version"] = version("torchvision")
    except PackageNotFoundError:
        runtime["torchvision_version"] = None
    except Exception:
        runtime["torchvision_version"] = "unknown"

    try:
        cuda_available = bool(torch_module.cuda.is_available())
    except Exception:
        checks.append(_check("cuda_available", "warning", "CUDA availability could not be determined."))
        return runtime, checks

    runtime["cuda_available"] = cuda_available
    runtime["cuda_build"] = getattr(getattr(torch_module, "version", None), "cuda", None)
    runtime["cpu_only"] = not cuda_available
    if not cuda_available:
        runtime["selected_device"] = "cpu"
        checks.append(_check("cuda_available", "warning", "CUDA is unavailable; inference will use CPU."))
        return runtime, checks

    runtime["selected_device"] = "cuda:0"
    metadata_ok = True
    try:
        runtime["gpu_name"] = torch_module.cuda.get_device_name(0)
    except Exception:
        runtime["gpu_name"] = None
        metadata_ok = False
    try:
        runtime["gpu_memory_bytes"] = int(torch_module.cuda.get_device_properties(0).total_memory)
    except Exception:
        runtime["gpu_memory_bytes"] = None
        metadata_ok = False
    try:
        tensor = torch_module.empty(1, device="cuda:0")
        result = tensor + 1
        if hasattr(result, "item"):
            result.item()
        torch_module.cuda.synchronize(0)
    except Exception:
        runtime["cuda_usable"] = False
        checks.append(_check("cuda_available", "fail", "CUDA is reported available but allocation or execution is unusable."))
        return runtime, checks
    runtime["cuda_usable"] = True
    checks.append(_check("cuda_available", "pass", "CUDA is available and passed a minimal execution check."))
    if not metadata_ok:
        checks.append(_check("cuda_metadata", "warning", "CUDA is usable, but GPU name or memory could not be read."))
    return runtime, checks


def _load_candidate_record(path: Path) -> ExpectedIdentity:
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise PreflightError("Candidate record could not be read as JSON.") from exc
    if not isinstance(payload, Mapping):
        raise PreflightError("Candidate record must be a JSON object.")
    artifact = payload.get("artifact")
    taxonomy = payload.get("taxonomy")
    if not isinstance(artifact, Mapping) or not isinstance(taxonomy, Mapping):
        raise PreflightError("Candidate record is missing artifact or taxonomy metadata.")
    classes = taxonomy.get("classes")
    if not isinstance(classes, list) or not all(isinstance(item, str) and item for item in classes):
        raise PreflightError("Candidate record taxonomy classes are malformed.")
    filename = artifact.get("filename")
    sha256 = artifact.get("sha256")
    if not isinstance(filename, str) or not isinstance(sha256, str):
        raise PreflightError("Candidate record artifact metadata is malformed.")
    return ExpectedIdentity(filename=filename, sha256=sha256.lower(), taxonomy=tuple(classes), source=path.name)


def resolve_expected_identity(args: argparse.Namespace) -> ExpectedIdentity:
    record = _load_candidate_record(Path(args.candidate_record).expanduser()) if args.candidate_record else ExpectedIdentity()
    taxonomy = tuple(args.expected_class) if args.expected_class else record.taxonomy
    filename = args.expected_filename or record.filename
    sha256 = args.expected_sha256.lower() if args.expected_sha256 else record.sha256
    return ExpectedIdentity(
        filename=filename,
        sha256=sha256,
        size_bytes=args.expected_size if args.expected_size is not None else record.size_bytes,
        taxonomy=taxonomy,
        source=record.source,
    )


def _identity_checks(
    model_path: Path | None,
    expected: ExpectedIdentity,
    *,
    model_loader: Callable[[str], Any] | None = None,
) -> tuple[dict[str, object], list[dict[str, str]]]:
    identity: dict[str, object] = {
        "path": str(model_path) if model_path else None,
        "exists": None,
        "filename": None,
        "size_bytes": None,
        "sha256": None,
        "taxonomy": None,
        "taxonomy_compatible": None,
    }
    checks: list[dict[str, str]] = []
    if model_path is None:
        checks.append(_check("model_identity", "not_checked", "No --model path was supplied."))
        return identity, checks
    path = model_path.expanduser().resolve()
    identity["path"] = str(path)
    identity["exists"] = path.is_file()
    if not path.is_file():
        checks.append(_check("model_exists", "fail", "Model file is missing or is not a regular file."))
        return identity, checks
    identity["filename"] = path.name
    identity["size_bytes"] = path.stat().st_size
    identity["sha256"] = calculate_sha256(path)
    missing_identity_fields = [
        label
        for label, value in (
            ("filename", expected.filename),
            ("SHA-256", expected.sha256),
            ("size", expected.size_bytes),
            ("taxonomy", expected.taxonomy),
        )
        if value is None
    ]
    if missing_identity_fields:
        checks.append(
            _check(
                "model_identity_configuration",
                "warning",
                "Expected identity is partial; not checked: " + ", ".join(missing_identity_fields) + ".",
            )
        )
    for field, actual, expected_value in (
        ("model_filename", identity["filename"], expected.filename),
        ("model_size_bytes", identity["size_bytes"], expected.size_bytes),
        ("model_sha256", identity["sha256"], expected.sha256),
    ):
        if expected_value is None:
            checks.append(_check(field, "not_checked", "No expected value was supplied."))
        elif actual == expected_value:
            checks.append(_check(field, "pass", "Actual value matches the expected identity."))
        else:
            checks.append(_check(field, "fail", "Actual value does not match the expected identity."))
    if expected.taxonomy is not None:
        try:
            taxonomy = _load_taxonomy(path, model_loader)
        except PreflightError as exc:
            checks.append(_check("model_taxonomy", "fail", str(exc)))
        else:
            identity["taxonomy"] = taxonomy
            compatible = tuple(taxonomy) == expected.taxonomy
            identity["taxonomy_compatible"] = compatible
            checks.append(_check("model_taxonomy", "pass" if compatible else "fail", "Model taxonomy matches expected order." if compatible else "Model taxonomy does not match expected order."))
    return identity, checks


def _http_get(url: str, timeout_seconds: float, api_key: str | None) -> tuple[int, object]:
    parsed = urlparse(url)
    if parsed.scheme not in {"http", "https"} or not parsed.netloc:
        raise BackendTransportError("Backend URL must be an absolute http:// or https:// URL.")
    headers = {"Accept": "application/json"}
    if api_key:
        headers["X-API-Key"] = api_key
    request = Request(url, headers=headers)
    try:
        with urlopen(request, timeout=timeout_seconds) as response:  # nosec B310 - user-selected local backend URL
            status = int(response.status)
            raw_body = response.read()
    except HTTPError as exc:
        raise BackendHTTPError(f"Backend returned HTTP {int(exc.code)}.") from exc
    except (URLError, TimeoutError, socket.timeout, OSError, ValueError) as exc:
        if isinstance(exc, (TimeoutError, socket.timeout)) or (
            isinstance(exc, URLError) and isinstance(exc.reason, (TimeoutError, socket.timeout))
        ):
            raise BackendTransportError("Backend request timed out.") from exc
        raise BackendTransportError("Backend request could not be completed.") from exc
    try:
        body = raw_body.decode("utf-8")
    except UnicodeDecodeError as exc:
        raise BackendResponseError("Backend response is not valid UTF-8 JSON.") from exc
    try:
        return status, json.loads(body)
    except json.JSONDecodeError as exc:
        raise BackendResponseError("Backend returned malformed JSON.") from exc


def _backend_error_check(endpoint: str, error: PreflightError) -> dict[str, str]:
    if isinstance(error, BackendTransportError):
        category = "transport"
    elif isinstance(error, BackendHTTPError):
        category = "http"
    elif isinstance(error, BackendResponseError):
        category = "response"
    else:
        category = "request"
    return _check(f"backend_{category}{endpoint}", "fail", str(error))


def _is_finite_number(value: object) -> bool:
    return isinstance(value, (int, float)) and not isinstance(value, bool) and math.isfinite(float(value))


def _backend_checks(
    base_url: str | None,
    expected: ExpectedIdentity,
    *,
    timeout_seconds: float,
    api_key: str | None,
    http_get: Callable[[str, float, str | None], tuple[int, object]] = _http_get,
) -> tuple[dict[str, object], list[dict[str, str]]]:
    backend: dict[str, object] = {"base_url": base_url, "endpoints": {}}
    checks: list[dict[str, str]] = []
    if not base_url:
        checks.append(_check("backend", "not_checked", "No --base-url was supplied."))
        return backend, checks
    root = base_url.rstrip("/")
    responses: dict[str, object] = {}
    for endpoint in ("/ml/model-info", "/ml/ready", "/ml/health", "/ml/metrics"):
        try:
            status, payload = http_get(root + endpoint, timeout_seconds, api_key)
        except PreflightError as exc:
            checks.append(_backend_error_check(endpoint, exc))
            backend["endpoints"] = responses
            return backend, checks
        responses[endpoint] = {"http_status": status, "payload": payload}
    backend["endpoints"] = responses
    for endpoint, response in responses.items():
        if not isinstance(response, Mapping) or response.get("http_status") != 200:
            status = response.get("http_status") if isinstance(response, Mapping) else None
            checks.append(_check(f"backend_http_status{endpoint}", "fail", f"Backend endpoint returned HTTP {status}, expected HTTP 200."))
    info = responses["/ml/model-info"]
    info_payload = info["payload"] if isinstance(info, Mapping) else None
    if not isinstance(info_payload, Mapping):
        checks.append(_check("backend_model_info", "fail", "Model-info response is not a JSON object."))
    else:
        required_fields = {"loaded"}
        if expected.filename is not None:
            required_fields.add("filename")
        if expected.sha256 is not None:
            required_fields.add("sha256")
        if expected.size_bytes is not None:
            required_fields.add("size_bytes")
        if expected.taxonomy is not None:
            required_fields.update({"classes", "taxonomy_compatible"})
        missing_fields = sorted(field for field in required_fields if field not in info_payload)
        if missing_fields:
            checks.append(_check("backend_model_info_contract", "fail", "Model-info is missing required field(s): " + ", ".join(missing_fields) + "."))
        loaded = info_payload.get("loaded") is True
        checks.append(_check("backend_model_loaded", "pass" if loaded else "fail", "Backend model is loaded." if loaded else "Backend model is not loaded."))
        for field, expected_value in (("filename", expected.filename), ("sha256", expected.sha256), ("size_bytes", expected.size_bytes)):
            if expected_value is not None:
                checks.append(_check(f"backend_model_{field}", "pass" if info_payload.get(field) == expected_value else "fail", "Backend value matches expected identity." if info_payload.get(field) == expected_value else "Backend value does not match expected identity."))
        if expected.taxonomy is not None:
            classes = info_payload.get("classes")
            compatible = info_payload.get("taxonomy_compatible") is True and classes == list(expected.taxonomy)
            checks.append(_check("backend_model_taxonomy", "pass" if compatible else "fail", "Backend taxonomy is compatible." if compatible else "Backend taxonomy is incompatible or malformed."))
    ready = responses["/ml/ready"]
    ready_payload = ready["payload"] if isinstance(ready, Mapping) else None
    ready_ok = isinstance(ready_payload, Mapping) and ready["http_status"] == 200 and ready_payload.get("ready") is True
    checks.append(_check("backend_ready", "pass" if ready_ok else "fail", "Backend is ready." if ready_ok else "Backend readiness check failed."))
    health = responses["/ml/health"]
    health_payload = health["payload"] if isinstance(health, Mapping) else None
    health_ok = isinstance(health_payload, Mapping) and health["http_status"] == 200 and health_payload.get("status") == "ok"
    checks.append(_check("backend_health", "pass" if health_ok else "fail", "Backend health is ok." if health_ok else "Backend health check failed."))
    metrics = responses["/ml/metrics"]
    metrics_payload = metrics["payload"] if isinstance(metrics, Mapping) else None
    metrics_ok = isinstance(metrics_payload, Mapping) and metrics["http_status"] == 200
    if metrics_ok:
        metrics_ok = all(_is_finite_number(metrics_payload.get(key)) for key in METRIC_COUNTERS)
        metrics_ok = metrics_ok and all(metrics_payload.get(key) is None or _is_finite_number(metrics_payload.get(key)) for key in METRIC_LATENCIES)
    checks.append(_check("backend_metrics", "pass" if metrics_ok else "fail", "Backend metrics are parseable." if metrics_ok else "Backend metrics response is malformed."))
    return backend, checks


def _overall_result(checks: Sequence[Mapping[str, str]], require_cuda: bool, runtime: Mapping[str, object]) -> str:
    if require_cuda and runtime.get("cuda_usable") is not True:
        return "FAIL"
    if any(check["status"] == "fail" for check in checks):
        return "FAIL"
    if any(check["status"] == "warning" for check in checks):
        return "WARNING"
    return "PASS"


def run_preflight(
    *,
    model_path: str | Path | None = None,
    expected: ExpectedIdentity | None = None,
    base_url: str | None = None,
    require_cuda: bool = False,
    timeout_seconds: float = DEFAULT_TIMEOUT_SECONDS,
    api_key: str | None = None,
    torch_module: Any | None = None,
    model_loader: Callable[[str], Any] | None = None,
    http_get: Callable[[str, float, str | None], tuple[int, object]] = _http_get,
) -> dict[str, object]:
    if timeout_seconds <= 0:
        raise PreflightError("Timeout must be greater than zero.")
    expected = expected or ExpectedIdentity()
    runtime, runtime_checks = _torch_runtime(torch_module)
    if require_cuda and runtime.get("cuda_usable") is not True:
        runtime_checks.append(_check("require_cuda", "fail", "CUDA is required but unavailable or unusable."))
    elif require_cuda:
        runtime_checks.append(_check("require_cuda", "pass", "CUDA requirement is satisfied."))
    identity, identity_checks = _identity_checks(Path(model_path) if model_path else None, expected, model_loader=model_loader)
    backend, backend_checks = _backend_checks(base_url, expected, timeout_seconds=timeout_seconds, api_key=api_key, http_get=http_get)
    checks = [*runtime_checks, *identity_checks, *backend_checks]
    warnings = [check["detail"] for check in checks if check["status"] == "warning"]
    return {
        "schema_version": "1.0",
        "tool": {"name": TOOL_NAME, "version": TOOL_VERSION},
        "created_at_utc": _utc_now(),
        "overall_result": _overall_result(checks, require_cuda, runtime),
        "runtime_environment": runtime,
        "expected_identity": asdict(expected),
        "model_identity": identity,
        "backend_status": backend,
        "checks": checks,
        "warnings": warnings,
    }


def render_markdown(report: Mapping[str, object]) -> str:
    runtime = report["runtime_environment"]
    identity = report["model_identity"]
    backend = report["backend_status"]
    assert isinstance(runtime, Mapping) and isinstance(identity, Mapping) and isinstance(backend, Mapping)
    lines = [
        "# WalkBuddy Runtime Preflight",
        "",
        f"- Overall result: **{report['overall_result']}**",
        f"- Generated: {report['created_at_utc']}",
        "",
        "## Runtime Environment",
        "",
        f"- Python: `{runtime.get('python_version')}`",
        f"- Torch: `{runtime.get('torch_version')}`",
        f"- Torchvision: `{runtime.get('torchvision_version')}`",
        "",
        "## Compute Device",
        "",
        f"- Selected device: `{runtime.get('selected_device')}`",
        f"- CUDA available: `{runtime.get('cuda_available')}`",
        f"- CUDA usable: `{runtime.get('cuda_usable')}`",
        f"- CUDA build: `{runtime.get('cuda_build')}`",
        f"- GPU: `{runtime.get('gpu_name')}`",
        f"- GPU memory bytes: `{runtime.get('gpu_memory_bytes')}`",
        "",
        "## Model Identity",
        "",
        f"- File: `{identity.get('filename')}`",
        f"- Size bytes: `{identity.get('size_bytes')}`",
        f"- SHA-256: `{identity.get('sha256')}`",
        f"- Taxonomy compatible: `{identity.get('taxonomy_compatible')}`",
        "",
        "## Backend Status",
        "",
        f"- Base URL: `{backend.get('base_url')}`",
        "",
        "## Runtime Metrics",
        "",
        "```json",
        json.dumps((backend.get("endpoints") or {}).get("/ml/metrics", {}), indent=2, sort_keys=True),
        "```",
        "",
        "## Checks",
        "",
        "| Check | Status | Detail |",
        "| --- | --- | --- |",
    ]
    for check in report["checks"]:
        assert isinstance(check, Mapping)
        lines.append(f"| {check['name']} | {check['status']} | {check['detail']} |")
    warnings = report["warnings"]
    if warnings:
        lines.extend(["", "## Warnings", ""])
        lines.extend(f"- {warning}" for warning in warnings)
    lines.append("")
    return "\n".join(lines)


def _write_text(path: Path, content: str) -> None:
    path = path.expanduser().resolve()
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, temporary_name = tempfile.mkstemp(prefix=f".{path.name}.", dir=path.parent, text=True)
    try:
        with os.fdopen(fd, "w", encoding="utf-8", newline="\n") as output:
            output.write(content)
        os.replace(temporary_name, path)
    except OSError as exc:
        try:
            os.unlink(temporary_name)
        except OSError:
            pass
        raise PreflightError("Report output could not be written.") from exc


def _is_within(path: Path, directory: Path) -> bool:
    try:
        path.relative_to(directory)
        return True
    except ValueError:
        return False


def validate_report_outputs(
    model_path: str | Path | None,
    json_out: str | Path | None,
    markdown_out: str | Path | None,
) -> None:
    """Reject report destinations that could overwrite or sit beside model artifacts."""
    outputs = [Path(value).expanduser().resolve() for value in (json_out, markdown_out) if value]
    if len(outputs) == 2 and outputs[0] == outputs[1]:
        raise PreflightError("JSON and Markdown report paths must be different.")

    model = Path(model_path).expanduser().resolve() if model_path else None
    protected_directories = [directory.resolve() for directory in KNOWN_MODEL_DIRECTORIES]
    if model is not None:
        protected_directories.append(model.parent)

    for output in outputs:
        if model is not None and output == model:
            raise PreflightError("Report output cannot be the model artifact.")
        if any(_is_within(output, directory) for directory in protected_directories):
            raise PreflightError("Report output cannot be inside a model or artifact directory.")


def parse_args(argv: Sequence[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Read-only WalkBuddy ML runtime preflight.")
    parser.add_argument("--model", help="Local model artifact to inspect.")
    parser.add_argument("--candidate-record", help="Optional model-registry JSON record supplying filename, SHA-256, and taxonomy.")
    parser.add_argument("--expected-filename")
    parser.add_argument("--expected-sha256")
    parser.add_argument("--expected-size", type=int)
    parser.add_argument("--expected-class", action="append", default=[], help="Expected class in exact order; repeat once per class.")
    parser.add_argument("--base-url", help="Backend base URL, for example http://10.0.0.10:8000.")
    parser.add_argument("--api-key", help="Optional backend X-API-Key; do not place secrets in evidence reports.")
    parser.add_argument("--timeout-seconds", type=float, default=DEFAULT_TIMEOUT_SECONDS)
    parser.add_argument("--require-cuda", action="store_true", help="Fail if CUDA is unavailable.")
    parser.add_argument("--json-out", help="Write a durable JSON report.")
    parser.add_argument("--markdown-out", help="Write a concise Markdown report.")
    return parser.parse_args(argv)


def main(argv: Sequence[str] | None = None) -> int:
    args = parse_args(argv)
    try:
        validate_report_outputs(args.model, args.json_out, args.markdown_out)
        expected = resolve_expected_identity(args)
        report = run_preflight(
            model_path=args.model,
            expected=expected,
            base_url=args.base_url,
            require_cuda=args.require_cuda,
            timeout_seconds=args.timeout_seconds,
            api_key=args.api_key,
        )
        if args.json_out:
            _write_text(Path(args.json_out), json.dumps(report, indent=2, sort_keys=True) + "\n")
        if args.markdown_out:
            _write_text(Path(args.markdown_out), render_markdown(report))
    except PreflightError as exc:
        print(f"Runtime preflight failed: {exc}", file=sys.stderr)
        return 2
    print(f"Runtime preflight result: {report['overall_result']}")
    return {"PASS": 0, "WARNING": 0, "FAIL": 1}[str(report["overall_result"])]


if __name__ == "__main__":
    raise SystemExit(main())
