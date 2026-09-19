"""Protocol, evidence, and metric checks for Candidate runtime soak validation.

This module deliberately exercises the existing backend contracts without
loading a model, changing a lifecycle record, or treating latency as a release
threshold.  The real transport is supplied by :mod:`runtime_soak`; tests use
the synthetic transport below so no backend, weights, dataset, CUDA, or network
is required.
"""

from __future__ import annotations

import asyncio
import base64
import json
import math
import statistics
import sys
import time
from collections.abc import Awaitable, Callable, Mapping, Sequence
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Any, Protocol
from urllib.parse import urlsplit


ML_SIDE_DIR = Path(__file__).resolve().parents[1]
REPOSITORY_ROOT = ML_SIDE_DIR.parent
DEPLOYMENT_TOOLS_DIR = ML_SIDE_DIR / "deployment" / "tools"
ML_TOOLS_DIR = ML_SIDE_DIR / "tools"
BACKEND_DIR = REPOSITORY_ROOT / "software_side" / "walkbuddy_reactNative" / "backend"

for directory in (DEPLOYMENT_TOOLS_DIR, ML_TOOLS_DIR, ML_SIDE_DIR, BACKEND_DIR):
    if str(directory) not in sys.path:
        sys.path.insert(0, str(directory))

from common import DeploymentError, durable_backend_url, read_json  # noqa: E402
from evaluation.geometry import refuse_held_out_path  # noqa: E402
from evaluation.taxonomy import TAXONOMY_CLASSES  # noqa: E402
from manifest import load_and_compare_registry, validate_manifest  # noqa: E402
import runtime_preflight as preflight  # noqa: E402


TOOL_NAME = "walkbuddy_candidate_runtime_soak"
TOOL_VERSION = "1.0.0"
REQUIRED_RESULT_FIELDS = frozenset(
    {
        "type",
        "frame_id",
        "detections",
        "guidance_message",
        "risk_level",
        "inference_time_ms",
        "server_timestamp_ms",
        "location",
    }
)
REQUIRED_ERROR_FIELDS = frozenset({"type", "code", "frame_id", "message"})
METRIC_COUNTERS = (*preflight.METRIC_COUNTERS, "active_inferences")
METRIC_LATENCIES = preflight.METRIC_LATENCIES
_SYNTHETIC_IMAGE = base64.b64decode(
    "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAYAAAAfFcSJAAAADUlEQVQIHWP4z8DwHwAFgAI/ScLq7wAAAABJRU5ErkJggg=="
)
_EVALUATION_ONLY_COMPONENTS = frozenset({"evaluation", "evaluations", "evaluation-only", "evaluation_only"})


class RuntimeSoakError(Exception):
    """Raised when a soak invocation cannot be performed safely."""


class TransportDisconnected(RuntimeSoakError):
    """Raised by a transport when a peer unexpectedly disconnects."""


@dataclass(frozen=True)
class CandidateIdentity:
    """Candidate identity resolved from the deployment manifest and registry."""

    candidate_id: str
    run_id: str
    lifecycle_state: str
    artifact_filename: str
    sha256: str
    size_bytes: int
    taxonomy: tuple[str, ...]
    manifest_reference: str
    registry_reference: str


@dataclass(frozen=True)
class SoakConfig:
    """Bounded runtime-soak parameters independent of the model itself."""

    candidate_id: str
    frames: int = 500
    interval_ms: int = 250
    reconnect_every: int = 50
    malformed_every: int = 0
    timeout_seconds: float = 10.0
    settle_ms: int = 250
    include_synthetic_location: bool = True

    def validate(self) -> None:
        if not isinstance(self.candidate_id, str) or not self.candidate_id.strip():
            raise RuntimeSoakError("--candidate must be a non-empty candidate ID.")
        if self.frames < 1:
            raise RuntimeSoakError("--frames must be at least one.")
        if self.interval_ms < 0 or self.reconnect_every < 0 or self.malformed_every < 0:
            raise RuntimeSoakError("Intervals and cadences cannot be negative.")
        if self.timeout_seconds <= 0:
            raise RuntimeSoakError("--timeout-seconds must be greater than zero.")
        if self.settle_ms < 0:
            raise RuntimeSoakError("--settle-ms cannot be negative.")


class VisionConnection(Protocol):
    """Minimal client surface of the current `/ws/vision` protocol."""

    async def send_text(self, message: str) -> None: ...

    async def send_bytes(self, payload: bytes) -> None: ...

    async def receive_text(self) -> str: ...

    async def close(self) -> None: ...


class VisionTransport(Protocol):
    """Factory for fresh WebSocket connections."""

    async def connect(self) -> VisionConnection: ...


def _utc_now() -> str:
    return datetime.now(UTC).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def _check(name: str, status: str, detail: str) -> dict[str, str]:
    return {"name": name, "status": status, "detail": detail}


def _finite_number(value: object) -> bool:
    return isinstance(value, (int, float)) and not isinstance(value, bool) and math.isfinite(float(value))


def _relative(path: Path, root: Path) -> str:
    try:
        return path.resolve().relative_to(root.resolve()).as_posix()
    except ValueError:
        return "external local path redacted"


def resolve_candidate(candidate_id: str, *, repository_root: str | Path = REPOSITORY_ROOT) -> CandidateIdentity:
    """Resolve one Candidate from existing manifest and registry evidence."""
    root = Path(repository_root).expanduser().resolve()
    manifest_dir = root / "ML_side" / "deployment" / "manifests"
    manifests: list[tuple[Path, Mapping[str, object]]] = []
    for path in sorted(manifest_dir.glob("*.json")):
        try:
            payload = read_json(path)
        except DeploymentError:
            continue
        if isinstance(payload, Mapping) and payload.get("candidate_id") == candidate_id:
            manifests.append((path, payload))
    if len(manifests) != 1:
        raise RuntimeSoakError("Exactly one candidate deployment manifest is required.")
    manifest_path, manifest = manifests[0]
    manifest_checks = validate_manifest(manifest, reference_root=root)
    if any(check.get("status") == "fail" for check in manifest_checks):
        raise RuntimeSoakError("Candidate deployment manifest is invalid.")
    registry, registry_checks = load_and_compare_registry(manifest, reference_root=root)
    if registry is None or any(check.get("status") == "fail" for check in registry_checks):
        raise RuntimeSoakError("Candidate registry does not agree with the deployment manifest.")
    taxonomy = manifest.get("ordered_taxonomy")
    canonical = tuple(TAXONOMY_CLASSES)
    if not isinstance(taxonomy, list) or tuple(taxonomy) != canonical:
        raise RuntimeSoakError("Candidate taxonomy does not match the canonical navigation taxonomy.")
    lifecycle = registry.get("lifecycle") if isinstance(registry, Mapping) else None
    lifecycle_state = lifecycle.get("status") if isinstance(lifecycle, Mapping) else None
    if lifecycle_state != manifest.get("expected_lifecycle"):
        raise RuntimeSoakError("Candidate lifecycle does not agree with the deployment manifest.")
    required = (
        manifest.get("run_id"),
        manifest.get("expected_artifact_filename"),
        manifest.get("expected_sha256"),
        manifest.get("expected_size_bytes"),
    )
    if not isinstance(required[0], str) or not isinstance(required[1], str) or not isinstance(required[2], str) or not isinstance(required[3], int):
        raise RuntimeSoakError("Candidate deployment identity is incomplete.")
    registry_ref = manifest.get("registry_record_reference")
    return CandidateIdentity(
        candidate_id=candidate_id,
        run_id=required[0],
        lifecycle_state=str(lifecycle_state),
        artifact_filename=required[1],
        sha256=required[2],
        size_bytes=required[3],
        taxonomy=canonical,
        manifest_reference=_relative(manifest_path, root),
        registry_reference=str(registry_ref),
    )


def _metric_snapshot_is_valid(snapshot: object) -> bool:
    if not isinstance(snapshot, Mapping):
        return False
    return all(_finite_number(snapshot.get(name)) and float(snapshot[name]) >= 0 for name in METRIC_COUNTERS) and all(
        snapshot.get(name) is None or (_finite_number(snapshot.get(name)) and float(snapshot[name]) >= 0)
        for name in METRIC_LATENCIES
    )


def validate_runtime_endpoints(candidate: CandidateIdentity, endpoints: Mapping[str, object]) -> list[dict[str, str]]:
    """Validate current runtime endpoint contracts before opening a socket."""
    info = endpoints.get("/ml/model-info")
    ready = endpoints.get("/ml/ready")
    health = endpoints.get("/ml/health")
    metrics = endpoints.get("/ml/metrics")
    info_payload = info.get("payload") if isinstance(info, Mapping) else None
    ready_payload = ready.get("payload") if isinstance(ready, Mapping) else None
    health_payload = health.get("payload") if isinstance(health, Mapping) else None
    metrics_payload = metrics.get("payload") if isinstance(metrics, Mapping) else None
    identity_ok = isinstance(info, Mapping) and info.get("http_status") == 200 and isinstance(info_payload, Mapping) and (
        info_payload.get("loaded") is True
        and info_payload.get("filename") == candidate.artifact_filename
        and info_payload.get("sha256") == candidate.sha256
        and info_payload.get("size_bytes") == candidate.size_bytes
        and info_payload.get("classes") == list(candidate.taxonomy)
        and info_payload.get("taxonomy_compatible") is True
    )
    checksum_value = info_payload.get("checksum_verified") if isinstance(info_payload, Mapping) else "missing"
    checksum_ok = checksum_value is None or isinstance(checksum_value, bool)
    ready_ok = isinstance(ready, Mapping) and ready.get("http_status") == 200 and isinstance(ready_payload, Mapping) and ready_payload.get("ready") is True
    health_ok = isinstance(health, Mapping) and health.get("http_status") == 200 and isinstance(health_payload, Mapping) and health_payload.get("status") == "ok"
    metrics_ok = isinstance(metrics, Mapping) and metrics.get("http_status") == 200 and _metric_snapshot_is_valid(metrics_payload)
    return [
        _check("runtime_candidate_identity", "PASS" if identity_ok else "FAIL", "Runtime model identity and ordered taxonomy match the selected manifest." if identity_ok else "Runtime identity or taxonomy does not match the selected Candidate."),
        _check("runtime_checksum_observability", "PASS" if checksum_ok else "FAIL", "checksum_verified is a current bool/null observability value; /ml/ready remains the gate." if checksum_ok else "checksum_verified is missing or malformed."),
        _check("runtime_ready", "PASS" if ready_ok else "FAIL", "Runtime is technically ready." if ready_ok else "Runtime /ml/ready did not report ready."),
        _check("runtime_health", "PASS" if health_ok else "FAIL", "Runtime health endpoint reported ok." if health_ok else "Runtime /ml/health did not report ok."),
        _check("runtime_metrics", "PASS" if metrics_ok else "FAIL", "Runtime metrics are finite and non-negative." if metrics_ok else "Runtime metrics are missing, non-finite, or malformed."),
    ]


def _endpoint_map_from_preflight(backend: Mapping[str, object]) -> Mapping[str, object]:
    endpoints = backend.get("endpoints", {})
    return endpoints if isinstance(endpoints, Mapping) else {}


def query_runtime_endpoints(
    candidate: CandidateIdentity,
    base_url: str,
    *,
    timeout_seconds: float,
    api_key: str | None = None,
    http_get: Callable[[str, float, str | None], tuple[int, object]] = preflight._http_get,  # noqa: SLF001
) -> tuple[Mapping[str, object], list[dict[str, str]]]:
    """Query all four established ML endpoints through runtime-preflight's transport."""
    expected = preflight.ExpectedIdentity(
        filename=candidate.artifact_filename,
        sha256=candidate.sha256,
        size_bytes=candidate.size_bytes,
        taxonomy=candidate.taxonomy,
        source="candidate deployment manifest",
    )
    backend, inherited = preflight._backend_checks(  # noqa: SLF001 - shared endpoint contract
        base_url,
        expected,
        timeout_seconds=timeout_seconds,
        api_key=api_key,
        http_get=http_get,
    )
    endpoints = _endpoint_map_from_preflight(backend)
    inherited_checks = [_check(str(item.get("name")), str(item.get("status", "fail")).upper(), str(item.get("detail", ""))) for item in inherited]
    return endpoints, [*inherited_checks, *validate_runtime_endpoints(candidate, endpoints)]


def collect_nonheldout_fixtures(directory: str | Path) -> list[bytes]:
    """Read caller-provided, non-held-out image fixtures without retaining paths."""
    root = Path(directory).expanduser().resolve()
    if not root.is_dir():
        raise RuntimeSoakError("--fixture-dir must be a readable directory for a real soak.")
    try:
        refuse_held_out_path(root)
    except ValueError as exc:
        raise RuntimeSoakError("Held-out fixture paths are forbidden for runtime soak validation.") from exc
    if any(part.casefold() in _EVALUATION_ONLY_COMPONENTS for part in root.parts):
        raise RuntimeSoakError("Evaluation-only fixture paths are forbidden for runtime soak validation.")
    allowed = {".jpg", ".jpeg", ".png", ".webp"}
    files = sorted(path for path in root.iterdir() if path.is_file() and path.suffix.lower() in allowed)
    if not files:
        raise RuntimeSoakError("--fixture-dir contains no supported non-held-out image fixtures.")
    payloads: list[bytes] = []
    for path in files:
        try:
            refuse_held_out_path(path)
        except ValueError as exc:
            raise RuntimeSoakError("Held-out fixture paths are forbidden for runtime soak validation.") from exc
        if any(part.casefold() in _EVALUATION_ONLY_COMPONENTS for part in path.parts):
            raise RuntimeSoakError("Evaluation-only fixture paths are forbidden for runtime soak validation.")
        data = path.read_bytes()
        if not data:
            raise RuntimeSoakError("Fixture images must not be empty.")
        payloads.append(data)
    return payloads


def _percentile(values: Sequence[float], percentile: float) -> float | None:
    if not values:
        return None
    ordered = sorted(float(value) for value in values)
    if len(ordered) == 1:
        return ordered[0]
    position = (len(ordered) - 1) * percentile
    lower = int(position)
    upper = min(lower + 1, len(ordered) - 1)
    return ordered[lower] + (ordered[upper] - ordered[lower]) * (position - lower)


def latency_summary(latencies_ms: Sequence[float], elapsed_seconds: float, successes: int) -> dict[str, object]:
    """Calculate client end-to-end measurements without assigning a threshold."""
    values = [float(value) for value in latencies_ms if _finite_number(value)]
    return {
        "count": len(values),
        "mean_ms": statistics.fmean(values) if values else None,
        "median_ms": statistics.median(values) if values else None,
        "p50_ms": _percentile(values, 0.50),
        "p95_ms": _percentile(values, 0.95),
        "p99_ms": _percentile(values, 0.99),
        "min_ms": min(values) if values else None,
        "max_ms": max(values) if values else None,
        "throughput_fps": (successes / elapsed_seconds) if elapsed_seconds > 0 else None,
    }


def _copy_metrics(snapshot: Mapping[str, object]) -> dict[str, object]:
    return {name: snapshot.get(name) for name in (*METRIC_COUNTERS, *METRIC_LATENCIES, "latency_window_size", "latency_window_capacity")}


def reconcile_metrics(before: Mapping[str, object], after: Mapping[str, object], *, client_successes: int, client_errors: int) -> dict[str, object]:
    """Compare only invariants justified by current InferenceMetrics semantics."""
    valid_before = _metric_snapshot_is_valid(before)
    valid_after = _metric_snapshot_is_valid(after)
    deltas: dict[str, float | None] = {}
    for name in METRIC_COUNTERS:
        if _finite_number(before.get(name)) and _finite_number(after.get(name)):
            deltas[name] = float(after[name]) - float(before[name])
        else:
            deltas[name] = None
    reasons: list[str] = []
    if not valid_before or not valid_after:
        reasons.append("Backend metrics are invalid or non-finite.")
    attempts = deltas.get("total_attempts")
    successful = deltas.get("successful_inferences")
    failed = deltas.get("failed_inferences")
    processed = deltas.get("processed_frames")
    if any(value is None or value < 0 for value in (attempts, successful, failed, processed)):
        reasons.append("Required inference counters decreased or were unavailable.")
    elif attempts != successful + failed:
        reasons.append("total_attempts delta does not equal successful plus failed inference deltas.")
    elif processed != successful:
        reasons.append("processed_frames delta does not equal successful_inferences delta.")
    if successful is not None and successful < client_successes:
        reasons.append("Backend successful_inferences delta is lower than client-observed successful responses.")
    if failed is not None and failed < client_errors:
        reasons.append("Backend failed_inferences delta is lower than client-observed public errors.")
    final_active = after.get("active_inferences")
    if final_active != 0:
        reasons.append("active_inferences did not return to zero after the settled run.")
    return {
        "status": "PASS" if not reasons else "FAIL",
        "details": reasons or ["Counters satisfy current aggregate invariants; extra concurrent runtime activity is not treated as a mismatch."],
        "before": _copy_metrics(before),
        "after": _copy_metrics(after),
        "delta": deltas,
        "client_observed_successes": client_successes,
        "client_observed_public_errors": client_errors,
        "dropped_frames_interpretation": "Informational only: the current server increments dropped_frames only when it deliberately skips a binary frame without metadata.",
    }


def _validate_location(value: object, expected_location: object) -> str | None:
    if expected_location is None:
        return None if value is None else "Successful response location must be null when no location metadata was sent."
    if not isinstance(value, Mapping) or value != expected_location:
        return "Successful response location does not preserve the supplied metadata contract."
    return None


def _validate_detections(value: object) -> list[str]:
    if not isinstance(value, list):
        return ["Successful response detections must be a list."]
    problems: list[str] = []
    for detection in value:
        if not isinstance(detection, Mapping):
            problems.append("Detection entries must be objects.")
            continue
        relative_depth = detection.get("relative_depth")
        if relative_depth is not None and not _finite_number(relative_depth):
            problems.append("relative_depth must be a unitless finite numeric score or null.")
        if relative_depth is not None and detection.get("distance_m") is not None:
            problems.append("distance_m must not be populated from relative_depth.")
    return problems


def _sanitized_backend_url(base_url: str | None) -> str:
    """Keep only protocol and port so reports never disclose a backend host."""
    if not base_url:
        return "not applicable in synthetic/mock mode"
    durable = durable_backend_url(base_url)
    if not isinstance(durable, str) or durable == "backend URL redacted":
        return "backend URL redacted"
    if "<LAN_IP>" in durable:
        return durable
    parsed = urlsplit(durable)
    if parsed.scheme not in {"http", "https"} or not parsed.hostname:
        return "backend URL redacted"
    try:
        port = parsed.port
    except ValueError:
        return "backend URL redacted"
    suffix = f":{port}" if port is not None else ""
    return f"{parsed.scheme}://<BACKEND_HOST>{suffix}"


def validate_protocol_response(raw: str, *, frame_id: str, malformed: bool, expected_location: object) -> tuple[dict[str, object], list[str]]:
    """Validate existing public result/error shapes without changing server behavior."""
    try:
        payload = json.loads(raw)
    except json.JSONDecodeError:
        return {"type": "invalid_json"}, ["Server returned malformed JSON."]
    if not isinstance(payload, Mapping):
        return {"type": "invalid_payload"}, ["Server response must be a JSON object."]
    response_type = payload.get("type")
    if response_type == "detection_result":
        missing = sorted(REQUIRED_RESULT_FIELDS.difference(payload))
        problems = [f"Successful response is missing required field(s): {', '.join(missing)}."] if missing else []
        if payload.get("frame_id") != frame_id:
            problems.append("Successful response frame_id does not match the sent frame.")
        if not isinstance(payload.get("guidance_message"), str) or not isinstance(payload.get("risk_level"), str):
            problems.append("Successful response guidance and risk fields must be strings.")
        if not isinstance(payload.get("inference_time_ms"), int) or not isinstance(payload.get("server_timestamp_ms"), int):
            problems.append("Successful response timing fields must be integers.")
        location_problem = _validate_location(payload.get("location"), expected_location)
        if location_problem:
            problems.append(location_problem)
        problems.extend(_validate_detections(payload.get("detections")))
        if malformed:
            problems.append("Malformed frame unexpectedly produced a successful detection result.")
        return {"type": "detection_result", "detection_count": len(payload.get("detections", [])), "error_code": None}, problems
    if response_type == "error":
        missing = sorted(REQUIRED_ERROR_FIELDS.difference(payload))
        problems = [f"Error response is missing required field(s): {', '.join(missing)}."] if missing else []
        if payload.get("frame_id") != frame_id:
            problems.append("Error response frame_id does not match the sent frame.")
        if not isinstance(payload.get("code"), str) or not isinstance(payload.get("message"), str):
            problems.append("Error response code and message must be strings.")
        if malformed and payload.get("code") != "inference_failed":
            problems.append("Malformed image did not receive the established inference_failed public error.")
        message = str(payload.get("message", "")).casefold()
        if any(token in message for token in ("traceback", "exception", "file ", "\\\\", "/users/", "c:\\")):
            problems.append("Public error response appears to expose private exception detail.")
        return {"type": "error", "detection_count": None, "error_code": payload.get("code")}, problems
    return {"type": str(response_type), "detection_count": None, "error_code": None}, ["Unexpected WebSocket response type."]


async def _receive_response(connection: VisionConnection) -> str:
    """Consume current keepalive pings without confusing them with a frame reply."""
    for _ in range(3):
        raw = await connection.receive_text()
        try:
            parsed = json.loads(raw)
        except json.JSONDecodeError:
            return raw
        if isinstance(parsed, Mapping) and parsed.get("type") == "ping":
            await connection.send_text(json.dumps({"type": "pong"}))
            continue
        return raw
    raise RuntimeSoakError("WebSocket keepalive loop prevented a frame response.")


async def run_protocol_soak(
    candidate: CandidateIdentity,
    config: SoakConfig,
    transport: VisionTransport,
    fixtures: Sequence[bytes],
    *,
    before_metrics: Mapping[str, object],
    after_metrics: Callable[[], Awaitable[Mapping[str, object]]],
    evidence_mode: str,
    real_candidate_runtime_validated: bool,
    base_url: str | None,
    endpoint_checks: Sequence[Mapping[str, str]],
    monotonic: Callable[[], float] = time.perf_counter,
    utc_now: Callable[[], str] = _utc_now,
) -> dict[str, object]:
    """Run bounded frames through a transport and create a sanitized report."""
    config.validate()
    if not fixtures:
        raise RuntimeSoakError("At least one non-empty fixture payload is required.")
    if any(not payload for payload in fixtures):
        raise RuntimeSoakError("Fixture payloads must not be empty.")
    startup_failures = [str(check.get("detail", "runtime contract failed")) for check in endpoint_checks if check.get("status") == "FAIL"]
    started_at = utc_now()
    started_monotonic = monotonic()
    records: list[dict[str, object]] = []
    failures: list[str] = list(startup_failures)
    connection: VisionConnection | None = None
    generation = 0
    reconnect_attempts = 0
    reconnect_successes = 0
    reconnect_failures = 0
    unexpected_disconnects = 0
    unrecovered_disconnects = 0
    malformed_injections = 0
    malformed_public_errors = 0
    post_malformed_valid_successes = 0
    waiting_for_post_malformed_success = False
    client_successes = 0
    client_errors = 0
    latencies: list[float] = []

    async def connect(*, deliberate: bool) -> bool:
        nonlocal connection, generation, reconnect_attempts, reconnect_successes, reconnect_failures
        if deliberate:
            reconnect_attempts += 1
        try:
            connection = await transport.connect()
        except Exception:
            connection = None
            if deliberate:
                reconnect_failures += 1
            return False
        generation += 1
        if deliberate:
            reconnect_successes += 1
        return True

    if not startup_failures and not await connect(deliberate=False):
        failures.append("Initial WebSocket connection failed.")

    for sequence in range(config.frames):
        if failures and connection is None:
            break
        if connection is not None and config.reconnect_every and sequence > 0 and sequence % config.reconnect_every == 0:
            try:
                await connection.close()
            except Exception:
                # The requested close can race the peer; the reconnection result is decisive.
                pass
            connection = None
            if not await connect(deliberate=True):
                failures.append("Deliberate reconnect failed.")
                break
        malformed = bool(config.malformed_every and (sequence + 1) % config.malformed_every == 0 and sequence < config.frames - 1)
        if malformed:
            malformed_injections += 1
        payload = b"not-a-valid-image" if malformed else fixtures[sequence % len(fixtures)]
        frame_id = f"soak-{sequence + 1}"
        expected_location: object = {"latitude": 0.0, "longitude": 0.0} if config.include_synthetic_location else None
        frame_meta: dict[str, object] = {
            "type": "frame_meta",
            "frame_id": frame_id,
            "width": 1,
            "height": 1,
            "timestamp_ms": int(time.time() * 1000),
            "latitude": 0.0 if config.include_synthetic_location else None,
            "longitude": 0.0 if config.include_synthetic_location else None,
        }
        recovered = False
        for attempt in range(2):
            if connection is None and not await connect(deliberate=False):
                failures.append("WebSocket reconnect after an unexpected disconnect failed.")
                unrecovered_disconnects += 1
                break
            sent_at = utc_now()
            sent_monotonic = monotonic()
            try:
                assert connection is not None
                await connection.send_text(json.dumps(frame_meta, separators=(",", ":")))
                await connection.send_bytes(payload)
                raw_response = await asyncio.wait_for(_receive_response(connection), timeout=config.timeout_seconds)
            except (TransportDisconnected, asyncio.TimeoutError):
                unexpected_disconnects += 1
                connection = None
                if attempt == 0 and await connect(deliberate=False):
                    recovered = True
                    continue
                failures.append("Unexpected WebSocket disconnect was not recovered.")
                unrecovered_disconnects += 1
                break
            received_at = utc_now()
            latency_ms = max(0.0, (monotonic() - sent_monotonic) * 1000)
            latencies.append(latency_ms)
            response, problems = validate_protocol_response(
                raw_response,
                frame_id=frame_id,
                malformed=malformed,
                expected_location=expected_location,
            )
            if problems:
                failures.extend(problems)
            if response["type"] == "detection_result":
                client_successes += 1
                if waiting_for_post_malformed_success:
                    post_malformed_valid_successes += 1
                    waiting_for_post_malformed_success = False
            elif response["type"] == "error":
                client_errors += 1
                if malformed and response.get("error_code") == "inference_failed":
                    malformed_public_errors += 1
                    waiting_for_post_malformed_success = True
                elif not malformed:
                    failures.append("Valid frame received a public error response.")
            else:
                failures.append("Frame did not receive a stable public result or error response.")
            records.append(
                {
                    "sequence": sequence + 1,
                    "connection_generation": generation,
                    "malformed_input": malformed,
                    "unexpected_disconnect_recovered": recovered,
                    "sent_at_utc": sent_at,
                    "response_at_utc": received_at,
                    "client_observed_latency_ms": latency_ms,
                    "response_type": response["type"],
                    "detection_count": response["detection_count"],
                    "error_code": response["error_code"],
                }
            )
            break
        if config.interval_ms and sequence < config.frames - 1:
            await asyncio.sleep(config.interval_ms / 1000)

    if connection is not None:
        try:
            await connection.close()
        except Exception:
            pass
    if waiting_for_post_malformed_success:
        failures.append("No later valid frame succeeded after controlled malformed input.")
    if config.settle_ms:
        await asyncio.sleep(config.settle_ms / 1000)
    after = await after_metrics()
    reconciliation = reconcile_metrics(before_metrics, after, client_successes=client_successes, client_errors=client_errors)
    if reconciliation["status"] != "PASS":
        failures.extend(str(detail) for detail in reconciliation["details"])
    elapsed = max(0.0, monotonic() - started_monotonic)
    verdict = "PASS" if not failures else "FAIL"
    return {
        "schema_version": "1.0.0",
        "tool": {"name": TOOL_NAME, "version": TOOL_VERSION},
        "evidence_mode": evidence_mode,
        "real_candidate_runtime_validated": real_candidate_runtime_validated,
        "candidate": {
            "candidate_id": candidate.candidate_id,
            "run_id": candidate.run_id,
            "artifact_filename": candidate.artifact_filename,
            "sha256": candidate.sha256,
            "size_bytes": candidate.size_bytes,
            "ordered_taxonomy": list(candidate.taxonomy),
            "lifecycle_state": candidate.lifecycle_state,
            "manifest_reference": candidate.manifest_reference,
            "registry_reference": candidate.registry_reference,
        },
        "runtime": {
            "base_url": _sanitized_backend_url(base_url),
            "endpoint_contract_checks": [dict(check) for check in endpoint_checks],
        },
        "parameters": {
            "frames": config.frames,
            "interval_ms": config.interval_ms,
            "reconnect_every": config.reconnect_every,
            "malformed_every": config.malformed_every,
            "settle_ms": config.settle_ms,
            "fixture_policy": "non-held-out caller fixtures" if real_candidate_runtime_validated else "synthetic encoded image payloads",
        },
        "started_at_utc": started_at,
        "completed_at_utc": utc_now(),
        "frame_summary": {
            "configured_frames": config.frames,
            "records": len(records),
            "successful_results": client_successes,
            "public_error_results": client_errors,
            "deliberate_reconnect_attempts": reconnect_attempts,
            "successful_reconnects": reconnect_successes,
            "reconnect_failures": reconnect_failures,
            "unexpected_disconnects": unexpected_disconnects,
            "unrecovered_unexpected_disconnects": unrecovered_disconnects,
            "malformed_input_injections": malformed_injections,
            "malformed_public_errors": malformed_public_errors,
            "post_malformed_valid_successes": post_malformed_valid_successes,
        },
        "frames": records,
        "client_end_to_end_latency": latency_summary(latencies, elapsed, client_successes),
        "backend_metrics": reconciliation,
        "technical_verdict": verdict,
        "hard_failure_conditions": failures,
        "performance_threshold_gate": "NOT CONFIGURED",
        "limitations": [
            "This is integrated WebSocket runtime reliability validation, not a controlled model inference benchmark.",
            "Client end-to-end WebSocket latency and backend inference latency are distinct measurements and are not compared as equivalent.",
            "Aggregate backend metrics can include concurrent process activity; reconciliation uses only current documented invariants and lower-bound client relationships.",
        ],
        "lifecycle_state": candidate.lifecycle_state,
        "production_authorization": "NOT GRANTED",
        "automatic_promotion_performed": False,
        "governance_note": "Technical soak validation is read-only. It does not alter lifecycle state, authorize production, promote a model, retrain, or create a new candidate.",
    }


class SyntheticBackend:
    """Stateful model-free backend used only for CI-safe protocol exercise."""

    def __init__(self, candidate: CandidateIdentity) -> None:
        self.candidate = candidate
        self.metrics: dict[str, object] = {
            "total_attempts": 0,
            "successful_inferences": 0,
            "failed_inferences": 0,
            "active_inferences": 0,
            "processed_frames": 0,
            "dropped_frames": 0,
            "latest_latency_ms": None,
            "mean_latency_ms": None,
            "p50_latency_ms": None,
            "p95_latency_ms": None,
            "max_latency_ms": None,
        }
        self.model_info: dict[str, object] = {
            "loaded": True,
            "filename": candidate.artifact_filename,
            "sha256": candidate.sha256,
            "size_bytes": candidate.size_bytes,
            "classes": list(candidate.taxonomy),
            "taxonomy_compatible": True,
            "checksum_verified": None,
        }
        self.ready = True
        self.health = "ok"
        self.force_final_active: int | None = None

    def endpoints(self) -> Mapping[str, object]:
        final_metrics = dict(self.metrics)
        if self.force_final_active is not None:
            final_metrics["active_inferences"] = self.force_final_active
        return {
            "/ml/model-info": {"http_status": 200, "payload": dict(self.model_info)},
            "/ml/ready": {"http_status": 200 if self.ready else 503, "payload": {"ready": self.ready}},
            "/ml/health": {"http_status": 200, "payload": {"status": self.health}},
            "/ml/metrics": {"http_status": 200, "payload": final_metrics},
        }

    def snapshot(self) -> Mapping[str, object]:
        return self.endpoints()["/ml/metrics"]["payload"]  # type: ignore[index]

    def handle_frame(self, meta: Mapping[str, object], payload: bytes) -> str:
        self.metrics["total_attempts"] = int(self.metrics["total_attempts"]) + 1
        self.metrics["active_inferences"] = int(self.metrics["active_inferences"]) + 1
        frame_id = meta.get("frame_id")
        if payload == b"not-a-valid-image":
            self.metrics["failed_inferences"] = int(self.metrics["failed_inferences"]) + 1
            self.metrics["active_inferences"] = int(self.metrics["active_inferences"]) - 1
            return json.dumps({"type": "error", "code": "inference_failed", "frame_id": frame_id, "message": "Vision inference failed."})
        self.metrics["successful_inferences"] = int(self.metrics["successful_inferences"]) + 1
        self.metrics["processed_frames"] = int(self.metrics["processed_frames"]) + 1
        self.metrics["active_inferences"] = int(self.metrics["active_inferences"]) - 1
        self.metrics["latest_latency_ms"] = 1.0
        self.metrics["mean_latency_ms"] = 1.0
        self.metrics["p50_latency_ms"] = 1.0
        self.metrics["p95_latency_ms"] = 1.0
        self.metrics["max_latency_ms"] = 1.0
        location = None
        if meta.get("latitude") is not None and meta.get("longitude") is not None:
            location = {"latitude": meta["latitude"], "longitude": meta["longitude"]}
        return json.dumps({
            "type": "detection_result",
            "frame_id": frame_id,
            "detections": [],
            "guidance_message": "Path clear",
            "risk_level": "CLEAR",
            "inference_time_ms": 1,
            "server_timestamp_ms": 1,
            "location": location,
        })


class SyntheticConnection:
    """In-memory implementation of the current metadata-then-bytes protocol."""

    def __init__(self, backend: SyntheticBackend, unexpected_sequences: set[int]) -> None:
        self.backend = backend
        self.unexpected_sequences = unexpected_sequences
        self.meta: Mapping[str, object] | None = None
        self.response: str | None = None
        self.closed = False

    async def send_text(self, message: str) -> None:
        if self.closed:
            raise TransportDisconnected("connection is closed")
        parsed = json.loads(message)
        if isinstance(parsed, Mapping) and parsed.get("type") == "frame_meta":
            self.meta = parsed

    async def send_bytes(self, payload: bytes) -> None:
        if self.closed or self.meta is None:
            raise TransportDisconnected("connection is unavailable")
        sequence = int(str(self.meta.get("frame_id", "soak-0")).rsplit("-", 1)[-1])
        if sequence in self.unexpected_sequences:
            self.unexpected_sequences.remove(sequence)
            self.closed = True
            raise TransportDisconnected("synthetic unexpected disconnect")
        self.response = self.backend.handle_frame(self.meta, payload)
        self.meta = None

    async def receive_text(self) -> str:
        if self.closed or self.response is None:
            raise TransportDisconnected("response is unavailable")
        response, self.response = self.response, None
        return response

    async def close(self) -> None:
        self.closed = True


class SyntheticTransport:
    """Configurable CI transport for reconnect and disconnect test cases."""

    def __init__(self, backend: SyntheticBackend, *, fail_connect_attempts: set[int] | None = None, unexpected_sequences: set[int] | None = None) -> None:
        self.backend = backend
        self.fail_connect_attempts = set(fail_connect_attempts or set())
        self.unexpected_sequences = set(unexpected_sequences or set())
        self.connect_attempts = 0

    async def connect(self) -> VisionConnection:
        self.connect_attempts += 1
        if self.connect_attempts in self.fail_connect_attempts:
            raise TransportDisconnected("synthetic connection failure")
        return SyntheticConnection(self.backend, self.unexpected_sequences)


async def run_mock_soak(
    config: SoakConfig,
    *,
    repository_root: str | Path = REPOSITORY_ROOT,
    backend: SyntheticBackend | None = None,
    transport: SyntheticTransport | None = None,
    monotonic: Callable[[], float] = time.perf_counter,
    utc_now: Callable[[], str] = _utc_now,
) -> dict[str, object]:
    """Run CI-safe synthetic protocol coverage; never claim real runtime evidence."""
    candidate = resolve_candidate(config.candidate_id, repository_root=repository_root)
    backend = backend or SyntheticBackend(candidate)
    transport = transport or SyntheticTransport(backend)
    endpoints_before = backend.endpoints()
    checks = validate_runtime_endpoints(candidate, endpoints_before)
    before_metrics = endpoints_before["/ml/metrics"]["payload"]  # type: ignore[index]

    async def after_metrics() -> Mapping[str, object]:
        return backend.snapshot()

    return await run_protocol_soak(
        candidate,
        config,
        transport,
        [_SYNTHETIC_IMAGE],
        before_metrics=before_metrics,  # type: ignore[arg-type]
        after_metrics=after_metrics,
        evidence_mode="synthetic/mock",
        real_candidate_runtime_validated=False,
        base_url=None,
        endpoint_checks=checks,
        monotonic=monotonic,
        utc_now=utc_now,
    )
