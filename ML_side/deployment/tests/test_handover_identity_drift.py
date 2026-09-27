"""Regression guard against handover documentation silently drifting from
the current production model identity.

This intentionally does NOT hardcode a second, independent model
definition (candidate ID, SHA-256, size, taxonomy, lifecycle). Instead it
reuses the project's own manifest-loading and manifest-vs-registry
comparison code (ML_side/deployment/tools/manifest.py) so there is a single
source of truth for what "current" means.

If this test fails, either:
  (a) a handover document (ML_side/models/README.md, docs/LOCAL_SETUP.md)
      is stale and needs updating, or
  (b) the manifest and the model registry have genuinely drifted apart,
      which is a deployment-tooling problem, not a docs problem.
"""

from __future__ import annotations

import sys
from pathlib import Path

DEPLOYMENT_TOOLS = Path(__file__).resolve().parents[1] / "tools"
sys.path.insert(0, str(DEPLOYMENT_TOOLS))

from common import REPO_ROOT
from manifest import load_and_compare_registry, load_manifest

MANIFEST_PATH = REPO_ROOT / "ML_side/deployment/manifests/navigation_candidate_56c445bb8c85.json"
MODELS_README = REPO_ROOT / "ML_side/models/README.md"
LOCAL_SETUP = REPO_ROOT / "docs/LOCAL_SETUP.md"


def _load_canonical_identity():
    manifest, _ = load_manifest(MANIFEST_PATH)
    registry, comparison_checks = load_and_compare_registry(manifest, reference_root=REPO_ROOT)
    assert registry is not None, "Registry record could not be loaded -- cannot verify handover docs."
    failed = [c for c in comparison_checks if c.get("status") == "fail"]
    assert not failed, (
        "Deployment manifest and model registry disagree on canonical model "
        f"identity: {failed}. Fix the manifest or registry before trusting "
        "handover documentation."
    )
    return registry


def test_manifest_and_registry_agree_on_canonical_identity():
    _load_canonical_identity()


def test_models_readme_matches_canonical_identity():
    registry = _load_canonical_identity()
    text = MODELS_README.read_text()

    assert registry["model_id"] in text, "models/README.md is missing the current candidate ID"
    assert registry["artifact"]["sha256"] in text, "models/README.md has a stale or missing SHA-256"
    assert registry["artifact"]["filename"] in text, "models/README.md is missing the artifact filename"

    lifecycle_status = registry["lifecycle"]["status"]
    assert f"Lifecycle status: **{lifecycle_status}**" in text, (
        f"models/README.md does not state the current lifecycle status "
        f"({lifecycle_status!r}) -- it may still show a stale lifecycle."
    )

    for class_name in registry["taxonomy"]["classes"]:
        assert class_name in text, f"models/README.md is missing taxonomy class {class_name!r}"


def test_local_setup_guide_file_size_matches_canonical_identity():
    manifest, _ = load_manifest(MANIFEST_PATH)
    text = LOCAL_SETUP.read_text()

    expected_size = str(manifest["expected_size_bytes"])
    assert expected_size in text, (
        f"docs/LOCAL_SETUP.md does not mention the current artifact size "
        f"({expected_size} bytes) -- its verified file sizes table may be stale."
    )
