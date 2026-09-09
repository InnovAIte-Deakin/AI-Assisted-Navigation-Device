"""Read-only orchestrator for candidate deployment readiness."""

from __future__ import annotations

import argparse
import json
import sys
from collections.abc import Callable, Mapping
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from common import DeploymentError, REPO_ROOT, check, durable_backend_url, durable_path_reference, result_for, write_json
from evidence import render_markdown, validate_evidence
from manifest import load_and_compare_registry, load_manifest, validate_manifest, validate_reference_existence


TOOLS_DIR = Path(__file__).resolve().parents[2] / "tools"
if str(TOOLS_DIR) not in sys.path:
    sys.path.insert(0, str(TOOLS_DIR))
import runtime_preflight


TOOL_VERSION = "1.0.0"
GOVERNANCE_NOTE = (
    "This read-only deployment-readiness evidence is not a held-out model-quality evaluation, "
    "not production authorization, does not change lifecycle, and does not replace human review "
    "or physical-device acceptance testing."
)


def _timestamp() -> str:
    return datetime.now(UTC).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def _runtime_expected(manifest: Mapping[str, object]) -> runtime_preflight.ExpectedIdentity:
    taxonomy = manifest.get("ordered_taxonomy")
    return runtime_preflight.ExpectedIdentity(
        filename=manifest.get("expected_artifact_filename") if isinstance(manifest.get("expected_artifact_filename"), str) else None,
        sha256=manifest.get("expected_sha256") if isinstance(manifest.get("expected_sha256"), str) else None,
        size_bytes=manifest.get("expected_size_bytes") if isinstance(manifest.get("expected_size_bytes"), int) else None,
        taxonomy=tuple(taxonomy) if isinstance(taxonomy, list) and all(isinstance(item, str) for item in taxonomy) else None,
        source="deployment_manifest",
    )


def _compute_policy_checks(manifest: Mapping[str, object], runtime: Mapping[str, object]) -> list[dict[str, str]]:
    policy = manifest.get("compute_policy")
    usable = runtime.get("cuda_usable") is True
    if policy == "cuda_required":
        return [check("compute_policy", "pass" if usable else "fail", "CUDA requirement is satisfied." if usable else "Manifest requires usable CUDA.")]
    if policy == "cuda_preferred":
        return [check("compute_policy", "pass" if usable else "warning", "CUDA preference is satisfied." if usable else "CUDA is preferred but unavailable or unusable.")]
    return [check("compute_policy", "pass", "CPU-capable deployment is allowed by the manifest.")]


def _runtime_checks_to_deployment(runtime_report: Mapping[str, object]) -> list[dict[str, str]]:
    raw = runtime_report.get("checks", [])
    if not isinstance(raw, list):
        return [check("runtime_preflight_contract", "fail", "Runtime preflight returned malformed checks.")]
    converted: list[dict[str, str]] = []
    for item in raw:
        if isinstance(item, Mapping) and isinstance(item.get("name"), str) and item.get("status") in {"pass", "warning", "fail", "not_checked"}:
            converted.append(check(f"runtime_{item['name']}", str(item["status"]), str(item.get("detail", ""))))
    return converted or [check("runtime_preflight_contract", "fail", "Runtime preflight returned no checks.")]


def _metrics_snapshot(runtime_report: Mapping[str, object]) -> dict[str, object]:
    backend = runtime_report.get("backend_status")
    if not isinstance(backend, Mapping):
        return {}
    endpoints = backend.get("endpoints")
    if not isinstance(endpoints, Mapping):
        return {}
    metrics = endpoints.get("/ml/metrics")
    return dict(metrics.get("payload", {})) if isinstance(metrics, Mapping) and isinstance(metrics.get("payload"), Mapping) else {}


def _durable_artifact_identity(identity: object, reference_root: Path) -> dict[str, object]:
    """Keep verified identity while removing a machine-specific model location."""
    durable = dict(identity) if isinstance(identity, Mapping) else {}
    if "path" in durable:
        durable["path"] = durable_path_reference(durable.get("path"), reference_root)
    return durable


def _durable_backend_status(status: object) -> dict[str, object]:
    durable = dict(status) if isinstance(status, Mapping) else {}
    if "base_url" in durable:
        durable["base_url"] = durable_backend_url(durable.get("base_url"))
    return durable


def check_readiness(
    *,
    manifest_path: str | Path,
    model_path: str | Path,
    base_url: str | None = None,
    require_cuda: bool = False,
    timeout_seconds: float = runtime_preflight.DEFAULT_TIMEOUT_SECONDS,
    api_key: str | None = None,
    reference_root: Path = REPO_ROOT,
    runtime_runner: Callable[..., dict[str, object]] = runtime_preflight.run_preflight,
) -> dict[str, object]:
    manifest, resolved_manifest = load_manifest(manifest_path)
    checks = validate_manifest(manifest, reference_root=reference_root)
    if any(item["status"] == "fail" for item in checks):
        runtime_report: dict[str, object] = {}
        registry: dict[str, object] | None = None
    else:
        registry, registry_checks = load_and_compare_registry(manifest, reference_root=reference_root)
        checks.extend(registry_checks)
        checks.extend(validate_reference_existence(manifest, reference_root=reference_root))
        expected = _runtime_expected(manifest)
        runtime_report = runtime_runner(
            model_path=model_path,
            expected=expected,
            base_url=base_url,
            require_cuda=require_cuda or manifest.get("compute_policy") == "cuda_required",
            timeout_seconds=timeout_seconds,
            api_key=api_key,
        )
        runtime = runtime_report.get("runtime_environment")
        if isinstance(runtime, Mapping):
            checks.extend(_compute_policy_checks(manifest, runtime))
        else:
            checks.append(check("compute_policy", "fail", "Runtime environment is unavailable."))
        checks.extend(_runtime_checks_to_deployment(runtime_report))
        if manifest.get("minimum_backend_contract_version") is not None:
            checks.append(check("minimum_backend_contract_version", "warning", "The current backend endpoints do not expose a contract version; this optional requirement was not verified."))
    warnings = [item["detail"] for item in checks if item["status"] == "warning"]
    failures = [item["detail"] for item in checks if item["status"] == "fail"]
    runtime_env = runtime_report.get("runtime_environment", {}) if runtime_report else {}
    model_identity = _durable_artifact_identity(runtime_report.get("model_identity", {}), reference_root) if runtime_report else {}
    backend = _durable_backend_status(runtime_report.get("backend_status", {})) if runtime_report else {}
    report: dict[str, object] = {
        "schema_version": "1.0.0",
        "tool": {"name": "walkbuddy_candidate_deployment_readiness", "version": TOOL_VERSION},
        "generated_at": _timestamp(),
        "candidate": {"candidate_id": manifest.get("candidate_id"), "run_id": manifest.get("run_id"), "expected_lifecycle": manifest.get("expected_lifecycle")},
        "manifest": {"reference": durable_path_reference(resolved_manifest, reference_root)},
        "registry": {"reference": manifest.get("registry_record_reference"), "lifecycle": registry.get("lifecycle") if isinstance(registry, Mapping) else None},
        "local_artifact": model_identity,
        "runtime_environment": runtime_env,
        "cuda": {"available": runtime_env.get("cuda_available") if isinstance(runtime_env, Mapping) else None, "usable": runtime_env.get("cuda_usable") if isinstance(runtime_env, Mapping) else None},
        "backend": backend,
        "metrics_snapshot": _metrics_snapshot(runtime_report),
        "checks": checks,
        "warnings": warnings,
        "failures": failures,
        "overall_result": result_for(checks),
        "governance_note": GOVERNANCE_NOTE,
    }
    evidence_errors = validate_evidence(report)
    if evidence_errors:
        report["checks"].extend(check("evidence_structure", "fail", error) for error in evidence_errors)
        report["failures"].extend(evidence_errors)
        report["overall_result"] = "FAIL"
    return report


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Read-only WalkBuddy candidate deployment-readiness check.")
    parser.add_argument("--manifest", required=True)
    parser.add_argument("--model", required=True)
    parser.add_argument("--base-url")
    parser.add_argument("--api-key", help="Optional backend key; it is not recorded in reports.")
    parser.add_argument("--timeout-seconds", type=float, default=runtime_preflight.DEFAULT_TIMEOUT_SECONDS)
    parser.add_argument("--require-cuda", action="store_true")
    parser.add_argument("--json-out")
    parser.add_argument("--markdown-out")
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    try:
        runtime_preflight.validate_report_outputs(args.model, args.json_out, args.markdown_out)
        report = check_readiness(manifest_path=args.manifest, model_path=args.model, base_url=args.base_url, require_cuda=args.require_cuda, timeout_seconds=args.timeout_seconds, api_key=args.api_key)
        if args.json_out:
            write_json(Path(args.json_out).expanduser().resolve(), report)
        if args.markdown_out:
            from common import atomic_write
            atomic_write(Path(args.markdown_out).expanduser().resolve(), render_markdown(report))
    except DeploymentError as exc:
        print(f"Deployment readiness failed: {exc}", file=sys.stderr)
        return 2
    except runtime_preflight.PreflightError as exc:
        print(f"Deployment readiness failed: {exc}", file=sys.stderr)
        return 2
    print(f"Candidate deployment readiness result: {report['overall_result']}")
    return 1 if report["overall_result"] == "FAIL" else 0


if __name__ == "__main__":
    raise SystemExit(main())
