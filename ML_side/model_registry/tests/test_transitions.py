import sys
from copy import deepcopy
from pathlib import Path

import pytest


TOOLS_DIR = Path(__file__).resolve().parents[1] / "tools"
sys.path.insert(0, str(TOOLS_DIR))

from transition import transition_model


def base_model():
    return {
        "schema_version": "1.0",
        "model_id": "WB-OD-TEST-001",
        "model_version": "1.0",
        "identity": {
            "name": "Test Model",
            "architecture": "YOLO",
            "framework": "Ultralytics",
            "task": "object_detection"
        },
        "taxonomy": {
            "taxonomy_id": "walkbuddy-mvp-8-v1",
            "classes": [
                "person",
                "stairs",
                "door",
                "chair",
                "table",
                "pole",
                "bicycle",
                "vehicle"
            ]
        },
        "dataset": {
            "release_id": "dataset-v2",
            "manifest_reference": "datasets/dataset-v2/manifest.json"
        },
        "training": {
            "training_date": "2026-08-11",
            "configuration_reference": "training/navigation-v1.yaml"
        },
        "artifact": {
            "filename": "navigation-v1.pt",
            "location": "approved-storage/navigation-v1.pt",
            "sha256": "a" * 64
        },
        "evaluation": {
            "evidence_reference": "evaluation/navigation-v1.json"
        },
        "lifecycle": {
            "status": "experimental"
        },
        "limitations": []
    }


def test_experimental_to_candidate_succeeds():
    model = base_model()

    result = transition_model(model, "candidate")

    assert result is True
    assert model["lifecycle"]["status"] == "candidate"


def test_candidate_to_production_succeeds():
    model = base_model()
    model["lifecycle"]["status"] = "candidate"

    result = transition_model(model, "production")

    assert result is True
    assert model["lifecycle"]["status"] == "production"


def test_candidate_promotion_blocked_without_lineage():
    model = base_model()
    model["dataset"]["release_id"] = None

    result = transition_model(model, "candidate")

    assert result is False
    assert model["lifecycle"]["status"] == "experimental"


def test_production_blocked_without_evaluation():
    model = base_model()
    model["lifecycle"]["status"] = "candidate"
    model["evaluation"]["evidence_reference"] = None

    result = transition_model(model, "production")

    assert result is False
    assert model["lifecycle"]["status"] == "candidate"


def test_invalid_transition_fails():
    model = base_model()

    with pytest.raises(ValueError):
        transition_model(model, "production")


def test_candidate_can_be_rejected():
    model = base_model()
    model["lifecycle"]["status"] = "candidate"

    result = transition_model(model, "rejected")

    assert result is True
    assert model["lifecycle"]["status"] == "rejected"


def test_production_can_be_deprecated():
    model = base_model()
    model["lifecycle"]["status"] = "production"

    result = transition_model(model, "deprecated")

    assert result is True
    assert model["lifecycle"]["status"] == "deprecated"


def test_production_can_be_rolled_back():
    model = base_model()
    model["lifecycle"]["status"] = "production"

    result = transition_model(model, "rolled_back")

    assert result is True
    assert model["lifecycle"]["status"] == "rolled_back"