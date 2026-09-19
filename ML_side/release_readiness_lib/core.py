"""Evidence discovery and checks for the WalkBuddy release-readiness handover.

The module deliberately validates committed metadata and evidence only.  It does
not open a model artifact, enumerate a dataset, run an evaluation, alter the
registry, or make a lifecycle decision.
"""

from __future__ import annotations

import json
import math
import re
import subprocess
import sys
from collections.abc import Callable, Mapping, Sequence
from datetime import datetime, timezone
from ipaddress import ip_address
from pathlib import Path
from typing import Any


ML_SIDE_DIR = Path(__file__).resolve().parents[1]
DEFAULT_REPOSITORY_ROOT = ML_SIDE_DIR.parent
DEPLOYMENT_TOOLS_DIR = ML_SIDE_DIR / "deployment" / "tools"
ML_TOOLS_DIR = ML_SIDE_DIR / "tools"

# The existing deployment helpers are script-oriented modules.  Add their
# directory once so this package can reuse their manifest/schema logic without
# duplicating it.
if str(DEPLOYMENT_TOOLS_DIR) not in sys.path:
    sys.path.insert(0, str(DEPLOYMENT_TOOLS_DIR))
if str(ML_SIDE_DIR) not in sys.path:
    sys.path.insert(0, str(ML_SIDE_DIR))
if str(ML_TOOLS_DIR) not in sys.path:
    sys.path.insert(0, str(ML_TOOLS_DIR))

from common import (  # noqa: E402
    DeploymentError,
    durable_backend_url,
    durable_path_reference,
    read_json,
    resolve_portable_reference,
)
from manifest import (  # noqa: E402
    load_and_compare_registry,
    validate_manifest,
)
from evaluation.taxonomy import TAXONOMY_CLASSES  # noqa: E402


STATUS_PASS = "PASS"
STATUS_FAIL = "FAIL"
STATUS_WARNING = "WARNING"
STATUS_NOT_CHECKED = "NOT_CHECKED"
_STATUS_ORDER = {
    STATUS_PASS: 0,
    STATUS_NOT_CHECKED: 1,
    STATUS_WARNING: 2,
    STATUS_FAIL: 3,
}
_WEIGHT_PATTERNS = ("*.pt", "*.pth", "*.onnx", "*.tflite", "*.ckpt", "*.weights")
_IPV4_PATTERN = re.compile(r"(?<![\w.])(?:\d{1,3}\.){3}\d{1,3}(?![\w.])")
_WINDOWS_ABSOLUTE_PATTERN = re.compile(r"(?<![A-Za-z0-9])[A-Za-z]:[\\/]")
_POSIX_DEVELOPER_PATH_PATTERN = re.compile(
    r"(?<![A-Za-z0-9:])/(?:Users|home|private|var|tmp|mnt|opt)/", re.IGNORECASE
)
_SENSITIVE_RESPONSE_KEY_PARTS = ("api_key", "apikey", "authorization", "password", "secret", "token")


class ReleaseReadinessError(Exception):
    """Raised for a controlled release-readiness invocation error."""


def _utc_now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def make_check(name: str, status: str, detail: str) -> dict[str, str]:
    if status not in _STATUS_ORDER:
        raise ValueError(f"Unsupported release-readiness status: {status}")
    return {"name": name, "status": status, "detail": detail}


def _normalise_check(raw: Mapping[str, object]) -> dict[str, str]:
    raw_status = str(raw.get("status", "fail")).upper()
    if raw_status == "NOT_CHECKED":
        status = STATUS_NOT_CHECKED
    elif raw_status in _STATUS_ORDER:
        status = raw_status
    else:
        status = STATUS_FAIL
    return make_check(str(raw.get("name", "unnamed_check")), status, str(raw.get("detail", "")))


def section(name: str, checks: Sequence[Mapping[str, str]]) -> dict[str, object]:
    normalised = [_normalise_check(item) for item in checks]
    if not normalised or all(item["status"] == STATUS_NOT_CHECKED for item in normalised):
        status = STATUS_NOT_CHECKED
    else:
        status = max((item["status"] for item in normalised), key=_STATUS_ORDER.__getitem__)
    return {"name": name, "status": status, "checks": normalised}


def _mapping(value: object) -> Mapping[str, object] | None:
    return value if isinstance(value, Mapping) else None


def _nested(mapping: Mapping[str, object] | None, *keys: str) -> object:
    current: object = mapping
    for key in keys:
        if not isinstance(current, Mapping):
            return None
        current = current.get(key)
    return current


def _is_finite_positive(value: object) -> bool:
    return isinstance(value, (int, float)) and not isinstance(value, bool) and math.isfinite(value) and value > 0


def _same_taxonomy(value: object, canonical: Sequence[str]) -> bool:
    return isinstance(value, list) and value == list(canonical)


def _safe_json(path: Path) -> tuple[Mapping[str, object] | None, str | None]:
    try:
        payload = read_json(path)
    except DeploymentError:
        return None, "Evidence JSON could not be read."
    if not isinstance(payload, Mapping):
        return None, "Evidence JSON must contain an object."
    return payload, None


def _relative_reference(path: Path | None, root: Path) -> str | None:
    return durable_path_reference(path, root)


def _candidate_manifests(root: Path, candidate_id: str) -> list[Path]:
    manifest_dir = root / "ML_side" / "deployment" / "manifests"
    if not manifest_dir.is_dir():
        return []
    matches: list[Path] = []
    for path in sorted(manifest_dir.glob("*.json")):
        payload, _ = _safe_json(path)
        if payload and payload.get("candidate_id") == candidate_id:
            matches.append(path)
    return matches


def _candidate_records(root: Path, candidate_id: str) -> list[Path]:
    records_dir = root / "ML_side" / "model_registry" / "records"
    if not records_dir.is_dir():
        return []
    matches: list[Path] = []
    for path in sorted(records_dir.glob("*.json")):
        payload, _ = _safe_json(path)
        if payload and payload.get("model_id") == candidate_id:
            matches.append(path)
    return matches


def _path_from_reference(reference: object, root: Path) -> Path | None:
    try:
        return resolve_portable_reference(reference, root)
    except DeploymentError:
        return None


def _candidate_evidence_paths(
    root: Path,
    candidate_id: str,
    *,
    manifest_path: Path | None = None,
    benchmark_path: Path | None = None,
    acceptance_path: Path | None = None,
) -> dict[str, Path | None]:
    manifests = [manifest_path] if manifest_path else _candidate_manifests(root, candidate_id)
    manifest = manifests[0] if len(manifests) == 1 else None
    registry: Path | None = None
    heldout: Path | None = None
    training: Path | None = None
    if manifest:
        manifest_payload, _ = _safe_json(manifest)
        if manifest_payload:
            registry = _path_from_reference(manifest_payload.get("registry_record_reference"), root)
            heldout = _path_from_reference(manifest_payload.get("evaluation_evidence_reference"), root)
            training = _path_from_reference(manifest_payload.get("training_configuration_reference"), root)
    if registry is None:
        records = _candidate_records(root, candidate_id)
        registry = records[0] if len(records) == 1 else None
    return {
        "manifest": manifest,
        "registry": registry,
        "benchmark": benchmark_path or root / "ML_side" / "benchmark_results" / "inference_performance.json",
        "acceptance": acceptance_path or root / "ML_side" / "evaluation" / "candidates" / "navigation-mvp-full-candidate-56c445bb8c85-runtime-acceptance" / "issue-74-real-candidate-safety-validation.json",
        "heldout": heldout,
        "training": training,
        "manifest_ambiguous": None if manifest_path or len(manifests) <= 1 else Path("ambiguous"),
    }


def _manifest_and_registry_checks(
    root: Path,
    candidate_id: str,
    paths: Mapping[str, Path | None],
) -> tuple[list[dict[str, str]], Mapping[str, object] | None, Mapping[str, object] | None]:
    manifest_path = paths["manifest"]
    if manifest_path is None:
        return [make_check("candidate_manifest", STATUS_FAIL, "No unique deployment manifest was found for the candidate.")], None, None
    if paths.get("manifest_ambiguous") is not None:
        return [make_check("candidate_manifest", STATUS_FAIL, "More than one deployment manifest matches the candidate.")], None, None
    manifest, error = _safe_json(manifest_path)
    if error:
        return [make_check("candidate_manifest", STATUS_FAIL, error)], None, None
    assert manifest is not None
    deployment_checks = [_normalise_check(item) for item in validate_manifest(manifest, reference_root=root)]
    checks: list[dict[str, str]] = [
        make_check("candidate_manifest", STATUS_PASS, "A unique candidate deployment manifest exists."),
        *deployment_checks,
        make_check(
            "manifest_candidate_id",
            STATUS_PASS if manifest.get("candidate_id") == candidate_id else STATUS_FAIL,
            "Manifest candidate ID matches the requested candidate." if manifest.get("candidate_id") == candidate_id else "Manifest candidate ID does not match the requested candidate.",
        ),
    ]
    try:
        registry, comparison_checks = load_and_compare_registry(manifest, reference_root=root)
    except (DeploymentError, OSError):
        registry, comparison_checks = None, [make_check("registry_record", STATUS_FAIL, "Registry record could not be loaded.")]
    checks.extend(_normalise_check(item) for item in comparison_checks)
    if registry is None or not isinstance(registry, Mapping):
        return checks, manifest, None
    registry_path = paths.get("registry")
    checks.append(make_check(
        "registry_record_exists",
        STATUS_PASS if registry_path and registry_path.is_file() else STATUS_FAIL,
        "Referenced registry record exists." if registry_path and registry_path.is_file() else "Referenced registry record is missing.",
    ))
    checks.append(make_check(
        "registry_candidate_id",
        STATUS_PASS if registry.get("model_id") == candidate_id else STATUS_FAIL,
        "Registry candidate ID matches the requested candidate." if registry.get("model_id") == candidate_id else "Registry candidate ID does not match the requested candidate.",
    ))
    return checks, manifest, registry


def _taxonomy_checks(manifest: Mapping[str, object] | None, registry: Mapping[str, object] | None) -> list[dict[str, str]]:
    if manifest is None or registry is None:
        return [make_check("canonical_taxonomy", STATUS_NOT_CHECKED, "Candidate manifest and registry are required before taxonomy can be checked.")]
    canonical = list(TAXONOMY_CLASSES)
    return [
        make_check(
            "registry_taxonomy_matches_canonical",
            STATUS_PASS if _same_taxonomy(_nested(registry, "taxonomy", "classes"), canonical) else STATUS_FAIL,
            "Registry taxonomy exactly matches the canonical navigation taxonomy." if _same_taxonomy(_nested(registry, "taxonomy", "classes"), canonical) else "Registry taxonomy does not exactly match the canonical navigation taxonomy.",
        ),
        make_check(
            "manifest_taxonomy_matches_canonical",
            STATUS_PASS if _same_taxonomy(manifest.get("ordered_taxonomy"), canonical) else STATUS_FAIL,
            "Manifest taxonomy exactly matches the canonical navigation taxonomy." if _same_taxonomy(manifest.get("ordered_taxonomy"), canonical) else "Manifest taxonomy does not exactly match the canonical navigation taxonomy.",
        ),
    ]


def _dataset_lineage_checks(
    manifest: Mapping[str, object] | None,
    registry: Mapping[str, object] | None,
    heldout: Mapping[str, object] | None,
) -> list[dict[str, str]]:
    if manifest is None or registry is None:
        return [make_check("controlled_dataset_lineage", STATUS_NOT_CHECKED, "Candidate manifest and registry are required before lineage can be checked.")]
    dataset = _mapping(registry.get("dataset"))
    heldout_count = _nested(heldout, "validation_metrics", "validation_image_count")
    if heldout_count is None:
        heldout_count = _nested(heldout, "results", "validation_metrics", "validation_image_count")
    return [
        make_check(
            "dataset_release_identity",
            STATUS_PASS if dataset and isinstance(dataset.get("release_id"), str) and dataset.get("release_id") else STATUS_FAIL,
            "Registry records a controlled dataset release ID." if dataset and isinstance(dataset.get("release_id"), str) and dataset.get("release_id") else "Registry is missing a controlled dataset release ID.",
        ),
        make_check(
            "dataset_manifest_reference",
            STATUS_PASS if dataset and isinstance(dataset.get("manifest_reference"), str) and dataset.get("manifest_reference") else STATUS_FAIL,
            "Registry records the controlled dataset-manifest reference." if dataset and isinstance(dataset.get("manifest_reference"), str) and dataset.get("manifest_reference") else "Registry is missing the controlled dataset-manifest reference.",
        ),
        make_check(
            "heldout_evaluation_record",
            STATUS_PASS if heldout and heldout.get("dataset_split") == "test" and heldout.get("mode") == "labelled_validation" and isinstance(heldout_count, int) and not isinstance(heldout_count, bool) and heldout_count > 0 else STATUS_FAIL,
            "Corrected held-out evidence records labelled evaluation on the test split." if heldout and heldout.get("dataset_split") == "test" and heldout.get("mode") == "labelled_validation" and isinstance(heldout_count, int) and not isinstance(heldout_count, bool) and heldout_count > 0 else "Corrected held-out evidence is missing its labelled test-split record or image count.",
        ),
    ]


def _identity_matches(candidate: Mapping[str, object], manifest: Mapping[str, object]) -> bool:
    return (
        candidate.get("candidate_id") == manifest.get("candidate_id")
        and candidate.get("run_id") == manifest.get("run_id")
        and candidate.get("artifact_filename") == manifest.get("expected_artifact_filename")
        and candidate.get("sha256") == manifest.get("expected_sha256")
        and candidate.get("size_bytes") == manifest.get("expected_size_bytes")
        and candidate.get("ordered_taxonomy") == manifest.get("ordered_taxonomy")
    )


def _heldout_checks(paths: Mapping[str, Path | None], manifest: Mapping[str, object] | None) -> tuple[list[dict[str, str]], Mapping[str, object] | None]:
    path = paths["heldout"]
    if path is None or not path.is_file():
        return [make_check("heldout_evidence_exists", STATUS_FAIL, "Referenced corrected held-out evaluation evidence is missing.")], None
    evidence, error = _safe_json(path)
    if error:
        return [make_check("heldout_evidence", STATUS_FAIL, error)], None
    assert evidence is not None
    model = _mapping(evidence.get("model"))
    metrics = _mapping(evidence.get("validation_metrics")) or _mapping(_nested(evidence, "results", "validation_metrics"))
    expected_identity = manifest is not None and model is not None and (
        model.get("filename") == manifest.get("expected_artifact_filename")
        and model.get("sha256") == manifest.get("expected_sha256")
        and model.get("file_size_bytes") == manifest.get("expected_size_bytes")
        and model.get("ordered_class_names") == manifest.get("ordered_taxonomy")
    )
    metric_values = [metrics.get(name) if metrics else None for name in ("precision", "recall", "mAP50", "mAP50_95")]
    return [
        make_check("heldout_evidence_exists", STATUS_PASS, "Referenced corrected held-out evaluation evidence exists."),
        make_check(
            "heldout_identity_matches_candidate",
            STATUS_PASS if expected_identity else STATUS_FAIL,
            "Held-out evidence matches the candidate identity and taxonomy." if expected_identity else "Held-out evidence does not match the candidate identity or taxonomy.",
        ),
        make_check(
            "heldout_is_test_split",
            STATUS_PASS if evidence.get("dataset_split") == "test" and evidence.get("mode") == "labelled_validation" else STATUS_FAIL,
            "Evidence records labelled evaluation on the held-out test split." if evidence.get("dataset_split") == "test" and evidence.get("mode") == "labelled_validation" else "Evidence does not record labelled evaluation on the held-out test split.",
        ),
        make_check(
            "heldout_metrics_material",
            STATUS_PASS if all(_is_finite_positive(value) for value in metric_values) else STATUS_FAIL,
            "Held-out aggregate metrics are present and finite." if all(_is_finite_positive(value) for value in metric_values) else "Held-out aggregate metrics are missing or invalid.",
        ),
    ], evidence


def _benchmark_checks(paths: Mapping[str, Path | None], manifest: Mapping[str, object] | None) -> list[dict[str, str]]:
    path = paths["benchmark"]
    if path is None or not path.is_file():
        return [make_check("benchmark_evidence_exists", STATUS_FAIL, "Formal inference benchmark evidence is missing.")]
    evidence, error = _safe_json(path)
    if error:
        return [make_check("benchmark_evidence", STATUS_FAIL, error)]
    assert evidence is not None
    model = _mapping(evidence.get("model"))
    environment = _mapping(evidence.get("environment"))
    results = evidence.get("results")
    identity_ok = manifest is not None and model is not None and (
        model.get("filename") == manifest.get("expected_artifact_filename")
        and model.get("sha256") == manifest.get("expected_sha256")
        and model.get("size_bytes") == manifest.get("expected_size_bytes")
    )
    results_ok = isinstance(results, list) and bool(results) and all(
        isinstance(item, Mapping)
        and isinstance(item.get("device"), str)
        and _is_finite_positive(item.get("mean_latency_ms"))
        and _is_finite_positive(item.get("throughput_fps"))
        for item in results
    )
    limitations = evidence.get("limitations")
    heldout_excluded = isinstance(limitations, list) and any(
        isinstance(item, str) and "held-out test set is not used" in item.casefold() for item in limitations
    )
    environment_ok = environment is not None and all(
        isinstance(environment.get(field), str) and environment.get(field)
        for field in ("platform", "python_version", "pytorch_version", "ultralytics_version")
    )
    return [
        make_check("benchmark_evidence_exists", STATUS_PASS, "Formal inference benchmark evidence exists."),
        make_check(
            "benchmark_identity_matches_candidate",
            STATUS_PASS if identity_ok else STATUS_FAIL,
            "Benchmark artifact matches the deployment manifest; candidate association is derived from that canonical identity." if identity_ok else "Benchmark artifact identity does not match the deployment manifest.",
        ),
        make_check(
            "benchmark_excludes_heldout_data",
            STATUS_PASS if heldout_excluded else STATUS_FAIL,
            "Benchmark explicitly records that it did not use held-out test data." if heldout_excluded else "Benchmark does not explicitly exclude held-out test data.",
        ),
        make_check(
            "benchmark_environment_recorded",
            STATUS_PASS if environment_ok else STATUS_FAIL,
            "Benchmark environment and device context are recorded." if environment_ok else "Benchmark environment/device context is incomplete.",
        ),
        make_check(
            "benchmark_latency_throughput_material",
            STATUS_PASS if results_ok else STATUS_FAIL,
            "Benchmark records finite latency and throughput results." if results_ok else "Benchmark latency or throughput results are missing or invalid.",
        ),
    ]


def _acceptance_checks(paths: Mapping[str, Path | None], manifest: Mapping[str, object] | None) -> tuple[list[dict[str, str]], list[dict[str, str]]]:
    path = paths["acceptance"]
    if path is None or not path.is_file():
        missing = make_check("runtime_acceptance_evidence_exists", STATUS_FAIL, "Candidate safety acceptance evidence is missing.")
        return [missing], [missing]
    evidence, error = _safe_json(path)
    if error:
        malformed = make_check("runtime_acceptance_evidence", STATUS_FAIL, error)
        return [malformed], [malformed]
    assert evidence is not None
    candidate = _mapping(evidence.get("candidate"))
    runtime = _mapping(evidence.get("runtime"))
    endpoints = _mapping(evidence.get("operational_endpoints"))
    model_info = _mapping(endpoints.get("model_info")) if endpoints else None
    ready = _mapping(endpoints.get("ready")) if endpoints else None
    health = _mapping(endpoints.get("health")) if endpoints else None
    deployment = _mapping(evidence.get("deployment_readiness"))
    identity_ok = manifest is not None and candidate is not None and _identity_matches(candidate, manifest)
    endpoint_ok = bool(
        model_info and model_info.get("http_status") == 200 and model_info.get("loaded") is True
        and model_info.get("filename") == (manifest or {}).get("expected_artifact_filename")
        and model_info.get("sha256_matches_manifest") is True
        and model_info.get("size_matches_manifest") is True
        and model_info.get("taxonomy_compatible") is True
        and ready and ready.get("http_status") == 200 and ready.get("ready") is True
        and health and health.get("http_status") == 200 and health.get("status") == "ok"
    )
    deployment_ok = deployment is not None and all(
        deployment.get(field) == "PASS" for field in ("cuda_required_preflight", "live_readiness", "startup")
    )
    runtime_ok = runtime is not None and runtime.get("mock_mode") is False and runtime.get("cuda_usable") is True
    safety = _mapping(evidence.get("real_candidate_safety_validation"))
    hazard = _mapping(safety.get("vision_hazard_case")) if safety else None
    non_trigger = _mapping(safety.get("vision_non_trigger_case")) if safety else None
    chat = _mapping(safety.get("chat_safety_override")) if safety else None
    depth = _mapping(safety.get("depth_semantics")) if safety else None
    safety_ok = all(item and item.get("result") == "PASS" for item in (hazard, non_trigger, chat))
    chat_ok = chat is not None and isinstance(chat.get("llm_dependency"), str) and "deterministic" in str(chat.get("llm_dependency")).casefold()
    depth_ok = depth is not None and depth.get("result") == "PASS" and depth.get("relative_depth_unit") == "unitless relative score" and depth.get("distance_m_observed") is None and depth.get("distance_m_derived_from_relative_depth") is False
    input_policy = _mapping(evidence.get("input_policy"))
    nonheldout_ok = input_policy is not None and input_policy.get("result") == "PASS" and isinstance(input_policy.get("summary"), str) and "no held-out" in str(input_policy.get("summary")).casefold()
    return [
        make_check("runtime_acceptance_evidence_exists", STATUS_PASS, "Real Candidate 1 runtime acceptance evidence exists."),
        make_check("runtime_identity_matches_candidate", STATUS_PASS if identity_ok else STATUS_FAIL, "Runtime evidence matches the candidate identity." if identity_ok else "Runtime evidence does not match the candidate identity."),
        make_check("controlled_runtime_launch", STATUS_PASS if runtime_ok else STATUS_FAIL, "Runtime evidence records a controlled non-mock launch with usable CUDA." if runtime_ok else "Runtime evidence does not record a controlled non-mock launch with usable CUDA."),
        make_check("deployment_preflight_evidence", STATUS_PASS if deployment_ok else STATUS_FAIL, "CUDA preflight, live readiness, and controlled startup all passed." if deployment_ok else "Deployment preflight/readiness evidence is incomplete or failed."),
        make_check("runtime_operational_endpoints", STATUS_PASS if endpoint_ok else STATUS_FAIL, "Model-info, ready, and health endpoint acceptance passed." if endpoint_ok else "Model-info, ready, or health endpoint evidence is incomplete or failed."),
    ], [
        make_check("safety_hazard_and_nontrigger", STATUS_PASS if safety_ok else STATUS_FAIL, "Real hazard, non-trigger, and chat safety cases passed." if safety_ok else "Real safety acceptance cases are incomplete or failed."),
        make_check("deterministic_chat_override", STATUS_PASS if chat_ok else STATUS_FAIL, "Safety evidence confirms deterministic chat handling before the LLM path." if chat_ok else "Safety evidence does not confirm deterministic pre-LLM chat handling."),
        make_check("validation_only_runtime_inputs", STATUS_PASS if nonheldout_ok else STATUS_FAIL, "Runtime acceptance records validation-only inputs and no held-out data." if nonheldout_ok else "Runtime acceptance does not clearly exclude held-out inputs."),
        make_check("relative_depth_semantics", STATUS_PASS if depth_ok else STATUS_FAIL, "relative_depth is unitless and distance_m is not derived from it." if depth_ok else "Relative-depth evidence does not preserve the unitless/distance_m constraint."),
        make_check("issue_74_acceptance", STATUS_PASS if _nested(evidence, "issue_74_acceptance", "result") == "PASS" else STATUS_FAIL, "Issue #74 real-candidate acceptance passed." if _nested(evidence, "issue_74_acceptance", "result") == "PASS" else "Issue #74 acceptance is absent or failed."),
    ]


def _companion_markdown(path: Path) -> Path | None:
    candidate = path.with_suffix(".md")
    return candidate if candidate.is_file() else None


def _evidence_files(paths: Mapping[str, Path | None]) -> list[Path]:
    files: list[Path] = []
    for name in ("manifest", "registry", "benchmark", "acceptance", "heldout", "training"):
        path = paths.get(name)
        if path and path.is_file():
            files.append(path)
            markdown = _companion_markdown(path)
            if markdown:
                files.append(markdown)
    return sorted(set(files))


def _private_ips(text: str) -> list[str]:
    found: list[str] = []
    for value in _IPV4_PATTERN.findall(text):
        try:
            address = ip_address(value)
        except ValueError:
            continue
        if address.is_private or address.is_loopback:
            found.append(value)
    return sorted(set(found))


def _sanitize_live_value(value: object, *, key: str | None = None) -> object:
    """Keep optional live reports safe even when a backend returns extra data."""
    if key and any(part in key.casefold() for part in _SENSITIVE_RESPONSE_KEY_PARTS):
        return "redacted"
    if isinstance(value, Mapping):
        return {str(item_key): _sanitize_live_value(item_value, key=str(item_key)) for item_key, item_value in value.items()}
    if isinstance(value, list):
        return [_sanitize_live_value(item) for item in value]
    if not isinstance(value, str):
        return value
    text = value
    for private_ip in _private_ips(text):
        text = text.replace(private_ip, "<PRIVATE_IP>")
    text = _WINDOWS_ABSOLUTE_PATTERN.sub("<LOCAL_PATH>/", text)
    text = _POSIX_DEVELOPER_PATH_PATTERN.sub("<LOCAL_PATH>/", text)
    return text


def _tracked_weight_check(root: Path) -> dict[str, str]:
    if not (root / ".git").exists():
        return make_check("tracked_model_weights", STATUS_NOT_CHECKED, "Git metadata is unavailable; tracked model weights were not checked.")
    try:
        completed = subprocess.run(
            ["git", "ls-files", "--", *_WEIGHT_PATTERNS],
            cwd=root,
            check=False,
            capture_output=True,
            text=True,
            timeout=10,
        )
    except (OSError, subprocess.TimeoutExpired):
        return make_check("tracked_model_weights", STATUS_NOT_CHECKED, "Git tracked-file inspection was unavailable.")
    if completed.returncode != 0:
        return make_check("tracked_model_weights", STATUS_NOT_CHECKED, "Git tracked-file inspection did not complete.")
    tracked = [line for line in completed.stdout.splitlines() if line.strip()]
    return make_check(
        "tracked_model_weights",
        STATUS_PASS if not tracked else STATUS_FAIL,
        "No model-weight artifact is tracked." if not tracked else "Tracked model-weight artifact(s) were found.",
    )


def _evidence_hygiene_checks(root: Path, paths: Mapping[str, Path | None]) -> list[dict[str, str]]:
    files = _evidence_files(paths)
    if not files:
        return [make_check("candidate_evidence_files", STATUS_NOT_CHECKED, "No candidate evidence files were available for hygiene checks.")]
    absolute_paths: list[str] = []
    private_ips: list[str] = []
    metre_claims: list[str] = []
    for path in files:
        try:
            content = path.read_text(encoding="utf-8")
        except (OSError, UnicodeDecodeError):
            absolute_paths.append(_relative_reference(path, root) or path.name)
            continue
        reference = _relative_reference(path, root) or path.name
        if _WINDOWS_ABSOLUTE_PATTERN.search(content) or _POSIX_DEVELOPER_PATH_PATTERN.search(content):
            absolute_paths.append(reference)
        private_ips.extend(_private_ips(content))
        for line in content.splitlines():
            lower = line.casefold()
            if "relative_depth" in lower and ("metre" in lower or "meter" in lower) and "not" not in lower and "unitless" not in lower:
                metre_claims.append(reference)
    return [
        _tracked_weight_check(root),
        make_check(
            "portable_evidence_paths",
            STATUS_PASS if not absolute_paths else STATUS_FAIL,
            "Candidate evidence contains no developer-local absolute paths." if not absolute_paths else "Candidate evidence contains a developer-local absolute path.",
        ),
        make_check(
            "private_ip_free_evidence",
            STATUS_PASS if not private_ips else STATUS_FAIL,
            "Candidate evidence contains no private or loopback IP address." if not private_ips else "Candidate evidence contains a private or loopback IP address.",
        ),
        make_check(
            "relative_depth_not_metres",
            STATUS_PASS if not metre_claims else STATUS_FAIL,
            "Candidate evidence does not represent relative_depth as metres." if not metre_claims else "Candidate evidence represents relative_depth as metres.",
        ),
    ]


def _live_checks(
    manifest: Mapping[str, object] | None,
    live_base_url: str | None,
    *,
    api_key: str | None,
    timeout_seconds: float,
    http_get: Callable[[str, float, str | None], tuple[int, object]] | None,
) -> tuple[list[dict[str, str]], Mapping[str, object] | None]:
    if not live_base_url:
        return [make_check("live_mode", STATUS_NOT_CHECKED, "No live backend URL was supplied.")], None
    if manifest is None:
        return [make_check("live_mode", STATUS_FAIL, "A valid candidate manifest is required for live verification.")], None
    import runtime_preflight as preflight

    expected = preflight.ExpectedIdentity(
        filename=manifest.get("expected_artifact_filename"),
        sha256=manifest.get("expected_sha256"),
        size_bytes=manifest.get("expected_size_bytes"),
        taxonomy=tuple(manifest.get("ordered_taxonomy", [])),
        source="candidate deployment manifest",
    )
    try:
        backend, checks = preflight._backend_checks(  # noqa: SLF001 - shared verified contract logic
            live_base_url,
            expected,
            timeout_seconds=timeout_seconds,
            api_key=api_key,
            http_get=http_get or preflight._http_get,  # noqa: SLF001 - testable transport seam
        )
    except (preflight.PreflightError, ValueError):
        return [make_check("live_mode", STATUS_FAIL, "Live backend verification could not be completed.")], {"base_url": durable_backend_url(live_base_url), "endpoints": {}}
    normalised_checks = [_normalise_check(item) for item in checks]
    endpoints = backend.get("endpoints", {}) if isinstance(backend, Mapping) else {}
    model_info = _nested(endpoints if isinstance(endpoints, Mapping) else None, "/ml/model-info", "payload")
    if not isinstance(model_info, Mapping) or "checksum_verified" not in model_info:
        normalised_checks.append(make_check(
            "backend_checksum_observability",
            STATUS_FAIL,
            "Model-info is missing the current checksum_verified observability field.",
        ))
    elif model_info.get("checksum_verified") is None or isinstance(model_info.get("checksum_verified"), bool):
        normalised_checks.append(make_check(
            "backend_checksum_observability",
            STATUS_PASS,
            "Model-info exposes checksum_verified; null is valid when no controlled expected SHA is configured. /ml/ready remains the runtime gate.",
        ))
    else:
        normalised_checks.append(make_check(
            "backend_checksum_observability",
            STATUS_FAIL,
            "Model-info checksum_verified must be true, false, or null.",
        ))
    return normalised_checks, {
        "base_url": durable_backend_url(live_base_url),
        "endpoints": _sanitize_live_value(endpoints),
    }


def _technical_status(sections: Sequence[Mapping[str, object]]) -> str:
    relevant = [section_data.get("status") for section_data in sections if section_data.get("name") != "Live verification"]
    if STATUS_FAIL in relevant:
        return STATUS_FAIL
    if STATUS_WARNING in relevant:
        return STATUS_WARNING
    return STATUS_PASS


def run_release_readiness(
    candidate_id: str,
    *,
    repository_root: str | Path = DEFAULT_REPOSITORY_ROOT,
    manifest_path: str | Path | None = None,
    benchmark_path: str | Path | None = None,
    acceptance_path: str | Path | None = None,
    live_base_url: str | None = None,
    api_key: str | None = None,
    timeout_seconds: float = 5.0,
    http_get: Callable[[str, float, str | None], tuple[int, object]] | None = None,
    generated_at_utc: str | None = None,
) -> dict[str, object]:
    """Run deterministic offline checks and optional live endpoint verification."""
    if not isinstance(candidate_id, str) or not candidate_id.strip():
        raise ReleaseReadinessError("--candidate must be a non-empty candidate ID.")
    if timeout_seconds <= 0:
        raise ReleaseReadinessError("--timeout-seconds must be greater than zero.")
    root = Path(repository_root).expanduser().resolve()
    if not root.is_dir():
        raise ReleaseReadinessError("Repository root does not exist.")
    paths = _candidate_evidence_paths(
        root,
        candidate_id,
        manifest_path=Path(manifest_path).expanduser().resolve() if manifest_path else None,
        benchmark_path=Path(benchmark_path).expanduser().resolve() if benchmark_path else None,
        acceptance_path=Path(acceptance_path).expanduser().resolve() if acceptance_path else None,
    )
    identity_checks, manifest, registry = _manifest_and_registry_checks(root, candidate_id, paths)
    heldout_checks, heldout = _heldout_checks(paths, manifest)
    runtime_checks, safety_checks = _acceptance_checks(paths, manifest)
    sections = [
        section("Candidate identity", identity_checks),
        section("Taxonomy", _taxonomy_checks(manifest, registry)),
        section("Dataset lineage", _dataset_lineage_checks(manifest, registry, heldout)),
        section("Held-out evaluation evidence", heldout_checks),
        section("Benchmark evidence", _benchmark_checks(paths, manifest)),
        section("Runtime evidence", runtime_checks),
        section("Safety acceptance", safety_checks),
        section("Evidence hygiene", _evidence_hygiene_checks(root, paths)),
    ]
    live_checks, live_result = _live_checks(
        manifest,
        live_base_url,
        api_key=api_key,
        timeout_seconds=timeout_seconds,
        http_get=http_get,
    )
    sections.append(section("Live verification", live_checks))
    lifecycle = _nested(registry, "lifecycle", "status")
    return {
        "schema_version": "1.0.0",
        "tool": {"name": "walkbuddy_release_readiness", "version": "1.0.0"},
        "generated_at_utc": generated_at_utc or _utc_now(),
        "candidate": {
            "candidate_id": candidate_id,
            "run_id": manifest.get("run_id") if manifest else None,
            "artifact_filename": manifest.get("expected_artifact_filename") if manifest else None,
            "expected_sha256": manifest.get("expected_sha256") if manifest else None,
            "expected_size_bytes": manifest.get("expected_size_bytes") if manifest else None,
            "lifecycle_state": lifecycle,
        },
        "evidence_references": {
            name: _relative_reference(paths.get(name), root)
            for name in ("manifest", "registry", "training", "heldout", "benchmark", "acceptance")
            if paths.get(name) is not None
        },
        "sections": sections,
        "technical_readiness": _technical_status(sections),
        "lifecycle_state": lifecycle,
        "production_authorization": "NOT GRANTED",
        "automatic_promotion_performed": False,
        "live_verification": live_result,
        "governance_note": "Technical verification is read-only. It does not alter lifecycle state, authorize production, or perform automatic promotion.",
    }
