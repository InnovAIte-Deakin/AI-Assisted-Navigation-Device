import sys
from pathlib import Path

import pytest


REGISTRY_DIR = Path(__file__).resolve().parents[1]
TOOLS_DIR = REGISTRY_DIR / "tools"

sys.path.insert(0, str(TOOLS_DIR))

from transition import (
    APPROVED_CLASS_NAMES,
    transition_model,
)


def base_model():
    return {
        "schema_version": "1.0",
        "model_id": "WB-OD-TEST-001",
        "model_version": "1.0",

        "identity": {
            "name": "WalkBuddy Test Model",
            "architecture": "YOLO",
            "framework": "Ultralytics",
            "task": "object_detection"
        },

        "taxonomy": {
            "taxonomy_id": "walkbuddy-mvp-8-v1",
            "classes": list(APPROVED_CLASS_NAMES)
        },

        "dataset": {
            "release_id": "walkbuddy-dataset-v2",
            "manifest_reference": "dataset/releases/v2/manifest.json"
        },

        "training": {
            "training_date": "2026-08-30",
            "configuration_reference": "training/navigation-v1.yaml"
        },

        "artifact": {
            "filename": "candidate.pt",
            "location": "approved-storage/candidate.pt",
            "sha256": "b" * 64
        },

        "evaluation": {
            "evidence_reference": "evaluation/navigation-v1/summary.json"
        },

        "lifecycle": {
            "status": "experimental"
        },

        "limitations": []
    }


def promotion_report(
    *,
    verdict="PASS",
    sha256="b" * 64,
    filename="candidate.pt",
    classes=None,
    compatibility="compatible",
    policy_status="APPROVED_POLICY",
    policy_result=None,
    validation_verdict="pass",
    evaluation_artifact="summary.json",
):
    if classes is None:
        classes = list(APPROVED_CLASS_NAMES)

    if policy_result is None:
        policy_result = verdict

    return {
        "schema_version": "1.0.0",

        "tool": {
            "name": "compare_model_evaluations",
            "version": "1.0.0"
        },

        "candidate": {
            "artifact": evaluation_artifact,
            "baseline_type": "evaluation",
            "filename": filename,
            "sha256": sha256,
            "class_count": len(classes),
            "ordered_class_names": classes,
            "mode": "labelled_validation"
        },

        "candidate_validation": {
            "supplied": True,
            "source_filename": "candidate_model_report.json",
            "sha256": "c" * 64,
            "verdict": validation_verdict
        },

        "technical_compatibility": {
            "status": compatibility,
            "reasons": []
        },

        "policy_gate": {
            "configuration_supplied": True,
            "source_filename": "approved-gates.json",
            "sha256": "d" * 64,
            "schema_version": "1.0.0",
            "policy_status": policy_status,
            "gates": {},
            "result": policy_result,
            "reasons": []
        },

        "verdict": verdict
    }


def test_experimental_to_candidate_succeeds():
    model = base_model()

    result = transition_model(model, "candidate")

    assert result is True
    assert model["lifecycle"]["status"] == "candidate"


def test_candidate_promotion_blocked_without_lineage():
    model = base_model()
    model["dataset"]["release_id"] = None

    result = transition_model(model, "candidate")

    assert result is False
    assert model["lifecycle"]["status"] == "experimental"


def test_candidate_to_production_succeeds_with_matching_pass(
    tmp_path
):
    model = base_model()
    model["lifecycle"]["status"] = "candidate"

    evaluation = {
        "schema_version": "1.0.0",
        "tool": {
            "name": "evaluate_current_model",
            "version": "2.0.0"
        },
        "model": {
            "filename": "candidate.pt",
            "file_size_bytes": 42,
            "sha256": "b" * 64,
            "class_count": len(APPROVED_CLASS_NAMES),
            "class_id_to_name": {
                str(index): name
                for index, name in enumerate(
                    APPROVED_CLASS_NAMES
                )
            },
            "ordered_class_names": list(
                APPROVED_CLASS_NAMES
            )
        },
        "mode": "labelled_validation",
        "evaluation_settings": {
            "operating_point_inference": None,
            "validation_ap": {
                "engine": "ultralytics_model_val"
            }
        }
    }

    evaluation_path = tmp_path / "summary.json"

    import json

    evaluation_path.write_text(
        json.dumps(evaluation),
        encoding="utf-8"
    )

    model["evaluation"]["evidence_reference"] = str(
        evaluation_path
    )

    result = transition_model(
        model,
        "production",
        promotion_report=promotion_report()
    )

    assert result is True
    assert model["lifecycle"]["status"] == "production"


def test_fail_verdict_blocks_production():
    model = base_model()
    model["lifecycle"]["status"] = "candidate"

    result = transition_model(
        model,
        "production",
        promotion_report=promotion_report(
            verdict="FAIL",
            policy_result="FAIL"
        )
    )

    assert result is False
    assert model["lifecycle"]["status"] == "candidate"


def test_review_verdict_blocks_production():
    model = base_model()
    model["lifecycle"]["status"] = "candidate"

    result = transition_model(
        model,
        "production",
        promotion_report=promotion_report(
            verdict="REVIEW",
            policy_result="REVIEW"
        )
    )

    assert result is False
    assert model["lifecycle"]["status"] == "candidate"


def test_missing_promotion_report_blocks_production():
    model = base_model()
    model["lifecycle"]["status"] = "candidate"

    result = transition_model(model, "production")

    assert result is False
    assert model["lifecycle"]["status"] == "candidate"


def test_sha_mismatch_blocks_production():
    model = base_model()
    model["lifecycle"]["status"] = "candidate"

    result = transition_model(
        model,
        "production",
        promotion_report=promotion_report(
            sha256="a" * 64
        )
    )

    assert result is False
    assert model["lifecycle"]["status"] == "candidate"


def test_filename_mismatch_blocks_production():
    model = base_model()
    model["lifecycle"]["status"] = "candidate"

    result = transition_model(
        model,
        "production",
        promotion_report=promotion_report(
            filename="different-model.pt"
        )
    )

    assert result is False
    assert model["lifecycle"]["status"] == "candidate"


def test_taxonomy_mismatch_blocks_production():
    model = base_model()
    model["lifecycle"]["status"] = "candidate"

    wrong_classes = list(APPROVED_CLASS_NAMES)
    wrong_classes[0] = "book"

    result = transition_model(
        model,
        "production",
        promotion_report=promotion_report(
            classes=wrong_classes
        )
    )

    assert result is False
    assert model["lifecycle"]["status"] == "candidate"


def test_evaluation_lineage_mismatch_blocks_production(
    tmp_path
):
    import json

    model = base_model()
    model["lifecycle"]["status"] = "candidate"

    evaluation = {
        "schema_version": "1.0.0",
        "tool": {
            "name": "evaluate_current_model",
            "version": "2.0.0"
        },
        "model": {
            "filename": "candidate.pt",
            "file_size_bytes": 42,

            # Deliberately wrong SHA
            "sha256": "a" * 64,

            "class_count": len(APPROVED_CLASS_NAMES),
            "class_id_to_name": {
                str(index): name
                for index, name in enumerate(
                    APPROVED_CLASS_NAMES
                )
            },
            "ordered_class_names": list(
                APPROVED_CLASS_NAMES
            )
        },
        "mode": "labelled_validation",
        "evaluation_settings": {
            "operating_point_inference": None,
            "validation_ap": {
                "engine": "ultralytics_model_val"
            }
        }
    }

    evaluation_path = tmp_path / "summary.json"

    evaluation_path.write_text(
        json.dumps(evaluation),
        encoding="utf-8"
    )

    model["evaluation"]["evidence_reference"] = str(
        evaluation_path
    )

    result = transition_model(
        model,
        "production",
        promotion_report=promotion_report()
    )

    assert result is False
    assert model["lifecycle"]["status"] == "candidate"


def test_unapproved_policy_blocks_production():
    model = base_model()
    model["lifecycle"]["status"] = "candidate"

    result = transition_model(
        model,
        "production",
        promotion_report=promotion_report(
            policy_status="EXAMPLE_NOT_APPROVED_POLICY"
        )
    )

    assert result is False
    assert model["lifecycle"]["status"] == "candidate"


def test_failed_candidate_validation_blocks_production():
    model = base_model()
    model["lifecycle"]["status"] = "candidate"

    result = transition_model(
        model,
        "production",
        promotion_report=promotion_report(
            validation_verdict="fail"
        )
    )

    assert result is False
    assert model["lifecycle"]["status"] == "candidate"


def test_invalid_sha_in_registry_blocks_transition():
    model = base_model()
    model["artifact"]["sha256"] = "12345"

    result = transition_model(model, "candidate")

    assert result is False
    assert model["lifecycle"]["status"] == "experimental"


def test_invalid_training_date_blocks_transition():
    model = base_model()
    model["training"]["training_date"] = "not-a-date"

    result = transition_model(model, "candidate")

    assert result is False
    assert model["lifecycle"]["status"] == "experimental"


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