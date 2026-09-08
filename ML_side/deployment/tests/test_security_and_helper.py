from __future__ import annotations

import sys
from pathlib import Path

import pytest

DEPLOYMENT_DIR = Path(__file__).resolve().parents[1]
DEPLOYMENT_TOOLS = DEPLOYMENT_DIR / "tools"
sys.path.insert(0, str(DEPLOYMENT_TOOLS))

from common import DeploymentError, validate_nonartifact_output


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
    assert "Invoke-Expression" not in helper
