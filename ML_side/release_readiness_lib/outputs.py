"""Stable JSON and Markdown output for the release-readiness workflow."""

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
    assert isinstance(candidate, Mapping)
    lines = [
        "# WalkBuddy ML Release Readiness",
        "",
        f"- Candidate: `{candidate.get('candidate_id')}`",
        f"- Run: `{candidate.get('run_id')}`",
        f"- Lifecycle state: `{report.get('lifecycle_state')}`",
        "",
        "| Section | Status |",
        "| --- | --- |",
    ]
    sections = report.get("sections", [])
    assert isinstance(sections, list)
    for item in sections:
        assert isinstance(item, Mapping)
        lines.append(f"| {item.get('name')} | **{item.get('status')}** |")
    lines.extend([
        "",
        f"## Technical readiness: {report.get('technical_readiness')}",
        "",
        f"- Lifecycle state: `{report.get('lifecycle_state')}`",
        f"- Production authorization: **{report.get('production_authorization')}**",
        f"- Automatic promotion performed: **{'YES' if report.get('automatic_promotion_performed') else 'NO'}**",
        "",
        "## Evidence references",
        "",
    ])
    references = report.get("evidence_references", {})
    assert isinstance(references, Mapping)
    for name in sorted(references):
        lines.append(f"- {name.replace('_', ' ')}: `{references[name]}`")
    non_pass_checks = []
    for item in sections:
        assert isinstance(item, Mapping)
        checks = item.get("checks", [])
        assert isinstance(checks, list)
        for check in checks:
            assert isinstance(check, Mapping)
            if check.get("status") not in {"PASS", "NOT_CHECKED"}:
                non_pass_checks.append(check)
    if non_pass_checks:
        lines.extend(["", "## Attention needed", "", "| Check | Status | Detail |", "| --- | --- | --- |"])
        for check in non_pass_checks:
            detail = str(check.get("detail", "")).replace("|", "\\|")
            lines.append(f"| {check.get('name')} | {check.get('status')} | {detail} |")
    lines.extend(["", "## Governance boundary", "", str(report.get("governance_note")), ""])
    return "\n".join(lines)


def write_reports(out_dir: str | Path, report: Mapping[str, Any]) -> tuple[Path, Path]:
    directory = validate_nonartifact_output(out_dir)
    json_path = directory / "release_readiness.json"
    markdown_path = directory / "release_readiness.md"
    try:
        payload = json.dumps(report, indent=2, sort_keys=True, allow_nan=False) + "\n"
    except (TypeError, ValueError) as exc:
        raise DeploymentError("Release-readiness report is not safely serialisable.") from exc
    atomic_write(json_path, payload)
    atomic_write(markdown_path, render_markdown(report))
    return json_path, markdown_path
