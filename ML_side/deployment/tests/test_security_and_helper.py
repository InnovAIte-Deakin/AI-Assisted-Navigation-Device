from __future__ import annotations

import os
import shutil
import subprocess
import sys
from pathlib import Path

import pytest

DEPLOYMENT_DIR = Path(__file__).resolve().parents[1]
DEPLOYMENT_TOOLS = DEPLOYMENT_DIR / "tools"
sys.path.insert(0, str(DEPLOYMENT_TOOLS))

from common import DeploymentError, validate_nonartifact_output


RUNTIME_TOOLS = DEPLOYMENT_DIR.parent / "tools"
sys.path.insert(0, str(RUNTIME_TOOLS))
import runtime_preflight


def test_standalone_evidence_cannot_be_written_in_model_or_artifact_stores():
    with pytest.raises(DeploymentError):
        validate_nonartifact_output("ML_side/models/environment.json")
    with pytest.raises(DeploymentError):
        validate_nonartifact_output("ML_side/artifacts/environment.json")
    assert validate_nonartifact_output("evidence/environment.json").name == "environment.json"


def test_launch_helper_is_dry_run_first_and_uses_argument_arrays():
    helper = (DEPLOYMENT_DIR / "scripts" / "start_candidate_backend.ps1").read_text(encoding="utf-8")
    assert "[switch]$Execute" in helper
    assert "if (-not $Execute)" in helper
    assert "& $Python @preflightArguments" in helper
    assert "& $Python @uvicornArguments" in helper
    assert "WALKBUDDY_MODEL_DIR" in helper
    assert "WALKBUDDY_ML_MOCK = \"0\"" in helper
    assert '[Alias("Host")]' in helper
    assert "[string]$BindHost = \"0.0.0.0\"" in helper
    assert "[string]$Host" not in helper
    assert '"--host", $BindHost' in helper
    assert "Invoke-Expression" not in helper


POWERSHELL = shutil.which("powershell") or shutil.which("pwsh")


def _write_fake_python(tmp_path: Path, exit_code: int) -> Path:
    if os.name == "nt":
        fake_python = tmp_path / "fake_python.cmd"
        fake_python.write_text(
            "@echo %*>> \"%FAKE_PYTHON_LOG%\"\r\n"
            f"@exit /b {exit_code}\r\n",
            encoding="utf-8",
        )
    else:
        fake_python = tmp_path / "fake_python"
        fake_python.write_text(
            "#!/bin/sh\n"
            'printf "%s\\n" "$*" >> "$FAKE_PYTHON_LOG"\n'
            f"exit {exit_code}\n",
            encoding="utf-8",
        )
        fake_python.chmod(fake_python.stat().st_mode | 0o111)

    return fake_python


def _run_launcher(
    tmp_path: Path,
    fake_python: Path,
    log_path: Path,
    *extra_args: str,
) -> subprocess.CompletedProcess[str]:
    model = tmp_path / "weights" / "best.pt"
    model.parent.mkdir(parents=True, exist_ok=True)
    model.write_bytes(b"candidate")
    manifest = tmp_path / "candidate.json"
    manifest.write_text("{}", encoding="utf-8")
    environment = os.environ.copy()
    environment["FAKE_PYTHON_LOG"] = str(log_path)
    return subprocess.run(
        [
            POWERSHELL,
            "-NoProfile",
            "-ExecutionPolicy",
            "Bypass",
            "-File",
            str(DEPLOYMENT_DIR / "scripts" / "start_candidate_backend.ps1"),
            "-ModelPath",
            str(model),
            "-ManifestPath",
            str(manifest),
            "-Python",
            str(fake_python),
            *extra_args,
        ],
        capture_output=True,
        text=True,
        env=environment,
    )


@pytest.mark.skipif(POWERSHELL is None, reason="Windows PowerShell is required")
def test_launch_helper_binds_host_alias_and_keeps_dry_runs_nonexecuting(tmp_path):
    default_log = tmp_path / "default.log"
    default_run = _run_launcher(
        tmp_path / "default",
        _write_fake_python(tmp_path, 0),
        default_log,
    )
    assert default_run.returncode == 0, default_run.stderr
    assert "--host 0.0.0.0 --port 8000" in default_run.stdout
    assert default_log.exists()
    assert "-m uvicorn" not in default_log.read_text(encoding="utf-8")

    custom_log = tmp_path / "custom.log"
    custom_run = _run_launcher(
        tmp_path / "custom",
        _write_fake_python(tmp_path, 0),
        custom_log,
        "-Host",
        "127.0.0.1",
        "-Port",
        "8765",
    )
    assert custom_run.returncode == 0, custom_run.stderr
    assert "--host 127.0.0.1 --port 8765" in custom_run.stdout
    assert custom_log.exists()
    assert "-m uvicorn" not in custom_log.read_text(encoding="utf-8")


@pytest.mark.skipif(POWERSHELL is None, reason="Windows PowerShell is required")
def test_launch_helper_stops_before_uvicorn_when_readiness_fails(tmp_path):
    log_path = tmp_path / "failed-readiness.log"
    failed_run = _run_launcher(
        tmp_path / "failed-readiness",
        _write_fake_python(tmp_path, 1),
        log_path,
        "-Execute",
    )
    assert failed_run.returncode != 0
    assert "Deployment readiness failed; backend was not started." in failed_run.stderr
    assert log_path.exists()
    assert "-m uvicorn" not in log_path.read_text(encoding="utf-8")


def test_runtime_preflight_output_safety_remains_in_force(tmp_path):
    model = tmp_path / "weights" / "best.pt"
    model.parent.mkdir()
    model.write_bytes(b"candidate")
    with pytest.raises(runtime_preflight.PreflightError):
        runtime_preflight.validate_report_outputs(model, model, tmp_path / "evidence.md")
