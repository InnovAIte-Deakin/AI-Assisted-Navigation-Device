"""Deterministic, sanitized report rendering for runtime soak validation."""

from __future__ import annotations

import json
import sys
from collections.abc import Mapping
from pathlib import Path
from typing import Any


DEPLOYMENT_TOOLS_DIR = Path(__file__).resolve().parents[1] / "deployment" / "tools"
if str(DEPLOYMENT_TOOLS_DIR) not in sys.path:
    sys.path.insert(0, str(DEPLOYMENT_TOOLS_DIR))

from common import DeploymentError, atomic_write, validate_nonartifact_output  # noqa: E402


def render_markdown(report: Mapping[str, object]) -> str:
    candidate = report.get("candidate", {})
    frame_summary = report.get("frame_summary", {})
    latency = report.get("client_end_to_end_latency", {})
    backend_metrics = report.get("backend_metrics", {})
    runtime_environment = report.get("runtime_environment", {})
    assert isinstance(candidate, Mapping) and isinstance(frame_summary, Mapping) and isinstance(latency, Mapping)
    assert isinstance(backend_metrics, Mapping) and isinstance(runtime_environment, Mapping)
    lines = [
        "# WalkBuddy Candidate Runtime Soak Validation",
        "",
        f"- Evidence mode: **{report.get('evidence_mode')}**",
        f"- Real Candidate runtime validated: **{'YES' if report.get('real_candidate_runtime_validated') else 'NO'}**",
        f"- Candidate: `{candidate.get('candidate_id')}`",
        f"- Run: `{candidate.get('run_id')}`",
        f"- Runtime soak result: **{report.get('technical_verdict')}**",
        "- Performance threshold gate: **NOT CONFIGURED**",
        "",
        "## Frame and connection summary",
        "",
        f"- Configured frames: {frame_summary.get('configured_frames')}",
        f"- Attempted valid frames: {frame_summary.get('attempted_valid_frames')}",
        f"- Successful valid responses: {frame_summary.get('successful_valid_responses')}",
        f"- Inference failures (public errors): {frame_summary.get('inference_failures')}",
        f"- Deliberate reconnects: {frame_summary.get('successful_reconnects')} / {frame_summary.get('deliberate_reconnect_attempts')}",
        f"- Unexpected disconnects: {frame_summary.get('unexpected_disconnects')}",
        f"- Malformed input injections: {frame_summary.get('malformed_input_injections')}",
        f"- Malformed stable public errors: {frame_summary.get('malformed_public_errors')}",
        f"- Malformed-input recovery: {frame_summary.get('malformed_recovery_status')}",
        "",
        "## Runtime environment",
        "",
        f"- PyTorch: `{runtime_environment.get('torch_version')}`",
        f"- CUDA usable: `{runtime_environment.get('cuda_usable')}`",
        f"- Device: `{runtime_environment.get('selected_device')}`",
        f"- GPU: `{runtime_environment.get('gpu_name')}`",
        "",
        "## Client end-to-end WebSocket latency",
        "",
        "| Count | Mean ms | P50 ms | P95 ms | P99 ms | Min ms | Max ms | Throughput FPS |",
        "| ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |",
        f"| {latency.get('count')} | {latency.get('mean_ms')} | {latency.get('p50_ms')} | {latency.get('p95_ms')} | {latency.get('p99_ms')} | {latency.get('min_ms')} | {latency.get('max_ms')} | {latency.get('throughput_fps')} |",
        "",
        "Client end-to-end WebSocket latency is distinct from aggregate backend inference latency; this report does not compare them as equivalent.",
        "",
        "## Backend metric reconciliation",
        "",
        f"- Reconciliation: **{backend_metrics.get('status')}**",
        f"- Final active inferences: {backend_metrics.get('after', {}).get('active_inferences') if isinstance(backend_metrics.get('after'), Mapping) else None}",
        "",
        "## Governance boundary",
        "",
        f"- Lifecycle state: `{report.get('lifecycle_state')}`",
        f"- Production authorization: **{report.get('production_authorization')}**",
        f"- Automatic promotion performed: **{'YES' if report.get('automatic_promotion_performed') else 'NO'}**",
        "",
        str(report.get("governance_note")),
        "",
    ]
    failures = report.get("hard_failure_conditions", [])
    assert isinstance(failures, list)
    if failures:
        lines.extend(["## Hard-failure detail", ""])
        lines.extend(f"- {item}" for item in failures)
        lines.append("")
    return "\n".join(lines)


def write_reports(out_dir: str | Path, report: Mapping[str, Any]) -> tuple[Path, Path]:
    directory = validate_nonartifact_output(out_dir)
    json_path = directory / "candidate_runtime_soak.json"
    markdown_path = directory / "candidate_runtime_soak.md"
    try:
        payload = json.dumps(report, indent=2, sort_keys=True, allow_nan=False) + "\n"
    except (TypeError, ValueError) as exc:
        raise DeploymentError("Runtime-soak report is not safely serialisable.") from exc
    atomic_write(json_path, payload)
    atomic_write(markdown_path, render_markdown(report))
    return json_path, markdown_path
