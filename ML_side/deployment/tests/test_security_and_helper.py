from __future__ import annotations

import json
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
    assert "Resolve-BackendPythonInterpreter" in helper
    assert "Assert-CoreBackendPythonEnvironment" in helper
    assert "& $pythonSelection.Invocation @preflightArguments" in helper
    assert "& $pythonSelection.Invocation @uvicornArguments" in helper
    assert "WALKBUDDY_MODEL_DIR" in helper
    assert "WALKBUDDY_ML_MOCK = \"0\"" in helper
    assert '[Alias("Host")]' in helper
    assert "[string]$BindHost = \"0.0.0.0\"" in helper
    assert "[string]$Host" not in helper
    assert '"--host", $BindHost' in helper
    assert "WALKBUDDY_EXPECTED_MODEL_SHA256" in helper
    assert "ConvertFrom-Json" in helper
    assert "expected_sha256" in helper
    assert helper.index("Assert-CoreBackendPythonEnvironment") < helper.index("$preflightArguments")
    assert helper.index("WALKBUDDY_EXPECTED_MODEL_SHA256") > helper.index("$preflightArguments")
    assert "Invoke-Expression" not in helper
    assert "Start-Process" not in helper


POWERSHELL = shutil.which("powershell") or shutil.which("pwsh")


def _write_fake_python(
    tmp_path: Path,
    *,
    probe_exit_code: int = 0,
    readiness_exit_code: int = 0,
    name: str = "fake_python",
) -> Path:
    tmp_path.mkdir(parents=True, exist_ok=True)
    if os.name == "nt":
        fake_python = tmp_path / f"{name}.cmd"
        fake_python.write_text(
            "@echo %*>> \"%FAKE_PYTHON_LOG%\"\r\n"
            "@echo %* | findstr /C:\"--core-backend-probe\" >nul\r\n"
            f"@if not errorlevel 1 exit /b {probe_exit_code}\r\n"
            f"@exit /b {readiness_exit_code}\r\n",
            encoding="utf-8",
        )
    else:
        fake_python = tmp_path / name
        fake_python.write_text(
            "#!/bin/sh\n"
            'printf "%s\\n" "$*" >> "$FAKE_PYTHON_LOG"\n'
            'case "$*" in\n'
            f'  *--core-backend-probe*) exit {probe_exit_code} ;;\n'
            f'  *) exit {readiness_exit_code} ;;\n'
            "esac\n",
            encoding="utf-8",
        )
        fake_python.chmod(fake_python.stat().st_mode | 0o111)

    return fake_python


def _run_launcher(
    tmp_path: Path,
    fake_python: Path | None,
    log_path: Path,
    *extra_args: str,
    backend_directory: Path | None = None,
    environment_overrides: dict[str, str] | None = None,
) -> subprocess.CompletedProcess[str]:
    model = tmp_path / "weights" / "best.pt"
    model.parent.mkdir(parents=True, exist_ok=True)
    model.write_bytes(b"candidate")
    manifest = tmp_path / "candidate.json"
    manifest.write_text("{}", encoding="utf-8")
    environment = os.environ.copy()
    environment["FAKE_PYTHON_LOG"] = str(log_path)
    if environment_overrides:
        environment.update(environment_overrides)
    arguments = [
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
    ]
    if fake_python is not None:
        arguments.extend(["-Python", str(fake_python)])
    if backend_directory is not None:
        arguments.extend(
            [
                "-BackendDirectory",
                os.path.relpath(backend_directory, DEPLOYMENT_DIR.parents[1]),
            ]
        )
    return subprocess.run(
        [*arguments, *extra_args],
        capture_output=True,
        text=True,
        env=environment,
    )


def _resolve_launcher_python(
    tmp_path: Path,
    backend_directory: Path,
    *,
    explicit_python: Path | None = None,
) -> dict[str, str]:
    environment = os.environ.copy()
    environment["LAUNCHER_SCRIPT"] = str(DEPLOYMENT_DIR / "scripts" / "start_candidate_backend.ps1")
    environment["LAUNCHER_BACKEND"] = str(backend_directory)
    command = (
        ". $env:LAUNCHER_SCRIPT; "
        "$selection = Resolve-BackendPythonInterpreter -BackendDirectory $env:LAUNCHER_BACKEND"
    )
    if explicit_python is not None:
        environment["LAUNCHER_EXPLICIT_PYTHON"] = str(explicit_python)
        command += " -ExplicitPython $env:LAUNCHER_EXPLICIT_PYTHON -ExplicitPythonSupplied"
    command += "; $selection | ConvertTo-Json -Compress"
    result = subprocess.run(
        [POWERSHELL, "-NoProfile", "-ExecutionPolicy", "Bypass", "-Command", command],
        capture_output=True,
        text=True,
        env=environment,
        check=False,
    )
    assert result.returncode == 0, result.stderr
    return json.loads(result.stdout)


@pytest.mark.skipif(POWERSHELL is None, reason="Windows PowerShell is required")
def test_launch_helper_binds_host_alias_and_keeps_dry_runs_nonexecuting(tmp_path):
    default_log = tmp_path / "default.log"
    default_run = _run_launcher(
        tmp_path / "default",
        _write_fake_python(tmp_path),
        default_log,
    )
    assert default_run.returncode == 0, default_run.stderr
    assert "--host 0.0.0.0 --port 8000" in default_run.stdout
    assert "Python interpreter source: explicit -Python argument" in default_run.stdout
    assert default_log.exists()
    assert "-m uvicorn" not in default_log.read_text(encoding="utf-8")

    custom_log = tmp_path / "custom.log"
    custom_run = _run_launcher(
        tmp_path / "custom",
        _write_fake_python(tmp_path),
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
def test_explicit_python_is_authoritative_even_when_backend_venv_exists(tmp_path):
    backend = tmp_path / "backend"
    venv_python = backend / ".venv" / "Scripts" / "python.exe"
    venv_python.parent.mkdir(parents=True)
    venv_python.write_bytes(b"placeholder")
    explicit_python = _write_fake_python(tmp_path / "explicit", name="explicit python")

    selection = _resolve_launcher_python(tmp_path, backend, explicit_python=explicit_python)

    assert selection == {
        "Invocation": str(explicit_python),
        "Source": "explicit -Python argument",
    }


@pytest.mark.skipif(POWERSHELL is None, reason="Windows PowerShell is required")
def test_omitted_python_prefers_backend_windows_venv(tmp_path):
    backend = tmp_path / "backend with spaces"
    venv_python = backend / ".venv" / "Scripts" / "python.exe"
    venv_python.parent.mkdir(parents=True)
    venv_python.write_bytes(b"placeholder")

    selection = _resolve_launcher_python(tmp_path, backend)

    assert selection == {
        "Invocation": str(venv_python.resolve()),
        "Source": "backend virtual environment",
    }


@pytest.mark.skipif(POWERSHELL is None, reason="Windows PowerShell is required")
def test_omitted_python_falls_back_to_normal_python_command(tmp_path):
    backend = tmp_path / "backend without venv"
    backend.mkdir()
    log_path = tmp_path / "normal-python.log"
    normal_python = _write_fake_python(tmp_path / "python bin", name="python")
    path = str(normal_python.parent) + os.pathsep + os.environ.get("PATH", "")

    completed = _run_launcher(
        tmp_path / "normal python run",
        None,
        log_path,
        backend_directory=backend,
        environment_overrides={"PATH": path},
    )

    assert completed.returncode == 0, completed.stderr
    assert "Python interpreter source: normal python command" in completed.stdout
    calls = log_path.read_text(encoding="utf-8")
    assert "--core-backend-probe" in calls
    assert "check_candidate_readiness.py" in calls
    assert "-m uvicorn" not in calls


@pytest.mark.skipif(POWERSHELL is None, reason="Windows PowerShell is required")
def test_unsuitable_explicit_python_does_not_fall_back_or_start_readiness(tmp_path):
    backend = tmp_path / "backend"
    venv_python = backend / ".venv" / "Scripts" / "python.exe"
    venv_python.parent.mkdir(parents=True)
    venv_python.write_bytes(b"placeholder")
    log_path = tmp_path / "unsuitable-explicit.log"
    unsuitable = _write_fake_python(tmp_path / "explicit", probe_exit_code=1)

    completed = _run_launcher(
        tmp_path / "unsuitable",
        unsuitable,
        log_path,
        "-Execute",
        backend_directory=backend,
    )

    assert completed.returncode != 0
    assert "Python interpreter source: explicit -Python argument" in completed.stdout
    assert "Selected Python environment is not suitable" in completed.stderr
    calls = log_path.read_text(encoding="utf-8")
    assert "--core-backend-probe" in calls
    assert "check_candidate_readiness.py" not in calls
    assert "-m uvicorn" not in calls


@pytest.mark.skipif(POWERSHELL is None, reason="Windows PowerShell is required")
def test_launch_helper_stops_before_uvicorn_when_readiness_fails(tmp_path):
    log_path = tmp_path / "failed-readiness.log"
    failed_run = _run_launcher(
        tmp_path / "failed-readiness",
        _write_fake_python(tmp_path, readiness_exit_code=1),
        log_path,
        "-Execute",
    )
    assert failed_run.returncode != 0
    assert "Deployment readiness failed; backend was not started." in failed_run.stderr
    calls = log_path.read_text(encoding="utf-8")
    assert "--core-backend-probe" in calls
    assert "check_candidate_readiness.py" in calls
    assert "-m uvicorn" not in calls


@pytest.mark.skipif(POWERSHELL is None, reason="Windows PowerShell is required")
def test_missing_core_package_stops_before_readiness_or_uvicorn(tmp_path):
    log_path = tmp_path / "missing-core-package.log"
    completed = _run_launcher(
        tmp_path / "missing core package",
        _write_fake_python(tmp_path / "python with spaces", probe_exit_code=1),
        log_path,
        "-Execute",
    )

    assert completed.returncode != 0
    assert "Selected Python environment is not suitable" in completed.stderr
    calls = log_path.read_text(encoding="utf-8")
    assert "--core-backend-probe" in calls
    assert "check_candidate_readiness.py" not in calls
    assert "-m uvicorn" not in calls


def test_backend_docker_healthcheck_requires_ml_readiness():
    dockerfile = (
        DEPLOYMENT_DIR.parents[1]
        / "software_side"
        / "walkbuddy_reactNative"
        / "backend"
        / "Dockerfile"
    )
    contents = dockerfile.read_text(encoding="utf-8")

    assert "HEALTHCHECK" in contents
    assert "curl -f http://localhost:8000/ml/ready" in contents
    assert "curl -f http://localhost:8000/ml/health" not in contents


def test_runtime_preflight_output_safety_remains_in_force(tmp_path):
    model = tmp_path / "weights" / "best.pt"
    model.parent.mkdir()
    model.write_bytes(b"candidate")
    with pytest.raises(runtime_preflight.PreflightError):
        runtime_preflight.validate_report_outputs(model, model, tmp_path / "evidence.md")
