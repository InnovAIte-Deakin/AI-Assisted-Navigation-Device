"""Shared, dependency-light helpers for deployment-readiness tooling."""

from __future__ import annotations

import json
import math
import os
import tempfile
from collections.abc import Mapping, Sequence
from pathlib import Path
from typing import Any


DEPLOYMENT_DIR = Path(__file__).resolve().parents[1]
ML_SIDE_DIR = DEPLOYMENT_DIR.parent
REPO_ROOT = ML_SIDE_DIR.parent
ALLOWED_RESULTS = {"PASS", "WARNING", "FAIL"}


class DeploymentError(Exception):
    """A clean, user-facing deployment tooling error."""


def check(name: str, status: str, detail: str) -> dict[str, str]:
    if status not in {"pass", "warning", "fail", "not_checked"}:
        raise ValueError("Unsupported check status")
    return {"name": name, "status": status, "detail": detail}


def result_for(checks: Sequence[Mapping[str, str]]) -> str:
    if any(item.get("status") == "fail" for item in checks):
        return "FAIL"
    if any(item.get("status") == "warning" for item in checks):
        return "WARNING"
    return "PASS"


def read_json(path: Path) -> object:
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise DeploymentError(f"Could not read JSON: {path.name}") from exc


def is_within(path: Path, parent: Path) -> bool:
    try:
        path.relative_to(parent)
        return True
    except ValueError:
        return False


def resolve_portable_reference(reference: object, root: Path) -> Path:
    """Resolve a repository-relative reference without allowing path escape."""
    if not isinstance(reference, str) or not reference.strip():
        raise DeploymentError("Reference must be a non-empty relative path.")
    raw = Path(reference)
    if raw.is_absolute() or ":" in raw.drive or "\\" in reference:
        raise DeploymentError("Reference must be a portable relative POSIX path.")
    resolved_root = root.resolve()
    resolved = (resolved_root / raw).resolve()
    if not is_within(resolved, resolved_root):
        raise DeploymentError("Reference must not escape its repository root.")
    return resolved


def finite_number(value: object) -> bool:
    return isinstance(value, (int, float)) and not isinstance(value, bool) and math.isfinite(float(value))


def atomic_write(path: Path, content: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    descriptor, temporary_name = tempfile.mkstemp(prefix=f".{path.name}.", dir=path.parent, text=True)
    try:
        with os.fdopen(descriptor, "w", encoding="utf-8", newline="\n") as output:
            output.write(content)
        os.replace(temporary_name, path)
    except OSError as exc:
        try:
            os.unlink(temporary_name)
        except OSError:
            pass
        raise DeploymentError("Evidence output could not be written.") from exc


def write_json(path: Path, payload: Mapping[str, Any]) -> None:
    try:
        atomic_write(path, json.dumps(payload, indent=2, sort_keys=True, allow_nan=False) + "\n")
    except (TypeError, ValueError) as exc:
        raise DeploymentError("Evidence JSON is not safely serialisable.") from exc


def validate_nonartifact_output(path: str | Path) -> Path:
    """Prevent standalone deployment reports from landing in tracked model stores."""
    resolved = Path(path).expanduser().resolve()
    protected = ((ML_SIDE_DIR / "models").resolve(), (ML_SIDE_DIR / "artifacts").resolve())
    if any(is_within(resolved, directory) for directory in protected):
        raise DeploymentError("Evidence output cannot be inside a model or artifact directory.")
    return resolved
