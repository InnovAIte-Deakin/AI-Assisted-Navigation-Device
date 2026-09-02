import argparse
import json
import sys
from pathlib import Path


# Make the existing ML tooling available to the registry.
ML_SIDE_DIR = Path(__file__).resolve().parents[2]
REPO_ROOT = ML_SIDE_DIR.parent
ML_TOOLS_DIR = ML_SIDE_DIR / "tools"

if str(ML_TOOLS_DIR) not in sys.path:
    sys.path.insert(0, str(ML_TOOLS_DIR))


import compare_model_evaluations as comparison
import validate_dataset_manifest as manifest_validator

from validate import validate_record


ALLOWED_TRANSITIONS = {
    "experimental": {"candidate", "rejected"},
    "candidate": {"production", "rejected"},
    "production": {"deprecated", "rolled_back"},
    "deprecated": {"rolled_back"},
    "rejected": set(),
    "rolled_back": set(),
}


CANDIDATE_REQUIREMENTS = [
    "dataset.release_id",
    "dataset.manifest_reference",
    "training.training_date",
    "training.configuration_reference",
    "artifact.filename",
    "artifact.location",
    "artifact.sha256",
]


PRODUCTION_REQUIREMENTS = [
    *CANDIDATE_REQUIREMENTS,
    "evaluation.evidence_reference",
]


APPROVED_CLASS_NAMES = [
    name for _, name in manifest_validator.APPROVED_TAXONOMY
]


def load_json(path):
    with open(path, "r", encoding="utf-8") as file:
        return json.load(file)


def save_json(path, record):
    with open(path, "w", encoding="utf-8") as file:
        json.dump(record, file, indent=2)
        file.write("\n")


def resolve_reference_path(reference):
    """
    Resolve a lineage reference string to a filesystem path.

    Absolute references are used as-is. Relative references are resolved
    against the repository root first (matching the ``ML_side/...`` style
    used for ``manifest_reference`` and ``configuration_reference`` in the
    registry README), and fall back to ``ML_side/`` so that a reference
    written relative to the ML side (for example ``evaluation/...``) also
    resolves. This keeps both documented reference styles working instead
    of silently blocking a valid promotion.
    """
    candidate_path = Path(reference)

    if candidate_path.is_absolute():
        return candidate_path

    repo_relative = REPO_ROOT / candidate_path

    if repo_relative.exists():
        return repo_relative

    ml_side_relative = ML_SIDE_DIR / candidate_path

    if ml_side_relative.exists():
        return ml_side_relative

    # Neither location exists. Return the repo-root form so the caller's
    # existing "evidence is invalid" handling reports a stable path.
    return repo_relative


def get_nested_value(record, field_path):
    value = record

    for part in field_path.split("."):
        if not isinstance(value, dict) or part not in value:
            return None

        value = value[part]

    return value


def find_missing_requirements(record, target_status):
    if target_status == "candidate":
        requirements = CANDIDATE_REQUIREMENTS

    elif target_status == "production":
        requirements = PRODUCTION_REQUIREMENTS

    else:
        return []

    missing = []

    for field in requirements:
        value = get_nested_value(record, field)

        if value is None or value == "":
            missing.append(field)

    return missing


def validate_registry_record(record):
    """
    Validate the full registry record before any lifecycle transition.
    """
    errors = validate_record(record)

    if not errors:
        return True

    print("Transition blocked: model record is invalid.")

    for error in errors:
        field = ".".join(
            str(part) for part in error.absolute_path
        )

        if field:
            print(f"- {field}: {error.message}")
        else:
            print(f"- {error.message}")

    return False


def uses_approved_taxonomy(record):
    """
    Check the registry taxonomy against the project's canonical taxonomy.
    """
    classes = get_nested_value(record, "taxonomy.classes")

    return classes == APPROVED_CLASS_NAMES


def validate_production_evidence(record, promotion_report):
    """
    Verify that a PR #177 comparison result authorises the exact
    model represented by this registry record.
    """
    if promotion_report is None:
        print("Production promotion blocked.")
        print("- A PR #177 model comparison report is required.")
        return False

    if promotion_report.get("schema_version") != comparison.SCHEMA_VERSION:
        print("Production promotion blocked.")
        print("- Promotion report schema version is unsupported.")
        return False

    tool = promotion_report.get("tool")

    if (
        not isinstance(tool, dict)
        or tool.get("name") != comparison.TOOL_NAME
    ):
        print("Production promotion blocked.")
        print("- Evidence is not a PR #177 model comparison report.")
        return False

    if promotion_report.get("verdict") != "PASS":
        print("Production promotion blocked.")
        print(
            f"- Promotion verdict is "
            f"{promotion_report.get('verdict')!r}, not 'PASS'."
        )
        return False

    compatibility = promotion_report.get("technical_compatibility")

    if (
        not isinstance(compatibility, dict)
        or compatibility.get("status") != "compatible"
    ):
        print("Production promotion blocked.")
        print("- Promotion evidence is not technically compatible.")
        return False

    policy_gate = promotion_report.get("policy_gate")

    if (
        not isinstance(policy_gate, dict)
        or policy_gate.get("configuration_supplied") is not True
        or policy_gate.get("policy_status")
        != comparison.APPROVED_POLICY_STATUS
        or policy_gate.get("result") != "PASS"
    ):
        print("Production promotion blocked.")
        print("- An approved promotion policy did not produce PASS.")
        return False

    candidate_validation = promotion_report.get(
        "candidate_validation"
    )

    if (
        not isinstance(candidate_validation, dict)
        or candidate_validation.get("supplied") is not True
        or candidate_validation.get("verdict")
        not in {"pass", "pass_with_warnings"}
    ):
        print("Production promotion blocked.")
        print(
            "- A successful candidate-validation report "
            "is not linked."
        )
        return False

    candidate = promotion_report.get("candidate")

    if not isinstance(candidate, dict):
        print("Production promotion blocked.")
        print("- Candidate lineage is missing from promotion evidence.")
        return False

    registry_sha = get_nested_value(record, "artifact.sha256")
    registry_filename = get_nested_value(
        record,
        "artifact.filename"
    )
    registry_classes = get_nested_value(
        record,
        "taxonomy.classes"
    )

    if candidate.get("sha256") != registry_sha:
        print("Production promotion blocked.")
        print("- Candidate SHA-256 does not match the registry.")
        return False

    if candidate.get("filename") != registry_filename:
        print("Production promotion blocked.")
        print("- Candidate filename does not match the registry.")
        return False

    if candidate.get("ordered_class_names") != registry_classes:
        print("Production promotion blocked.")
        print("- Candidate taxonomy does not match the registry.")
        return False

    # The registry taxonomy is already guaranteed to equal
    # APPROVED_CLASS_NAMES here: transition_model() runs
    # uses_approved_taxonomy() for the production target before it
    # calls this function, so re-checking it would be dead code.

    if candidate.get("class_count") != len(APPROVED_CLASS_NAMES):
        print("Production promotion blocked.")
        print("- Candidate class count is not the approved class count.")
        return False

    evaluation_reference = get_nested_value(
        record,
        "evaluation.evidence_reference"
    )

    if not isinstance(evaluation_reference, str):
        print("Production promotion blocked.")
        print("- Evaluation evidence reference is missing.")
        return False

    evaluation_path = resolve_reference_path(evaluation_reference)

    try:
        evaluation_source, evaluation_artifact = (
            comparison.load_evaluation_artifact(
                evaluation_path
            )
        )
    except comparison.ComparisonError as error:
        print("Production promotion blocked.")
        print(
            f"- Registered evaluation evidence is invalid: {error}"
        )
        return False

    evaluation_model = evaluation_artifact.get("model")

    if not isinstance(evaluation_model, dict):
        print("Production promotion blocked.")
        print("- Evaluation model lineage is missing.")
        return False

    lineage_fields = [
        "filename",
        "sha256",
        "class_count",
        "ordered_class_names",
    ]

    for field in lineage_fields:
        if evaluation_model.get(field) != candidate.get(field):
            print("Production promotion blocked.")
            print(
                f"- Evaluation lineage field '{field}' "
                "does not match the PASS comparison."
            )
            return False

    if evaluation_artifact.get("mode") != candidate.get("mode"):
        print("Production promotion blocked.")
        print(
            "- Evaluation mode does not match "
            "the PASS comparison."
        )
        return False

    comparison_evaluation_file = candidate.get("artifact")

    if evaluation_source.name != comparison_evaluation_file:
        print("Production promotion blocked.")
        print(
            "- Registered evaluation artifact does not match "
            "the PASS comparison."
        )
        return False

    return True


def transition_model(
    record,
    target_status,
    promotion_report=None,
):
    """
    Apply a controlled lifecycle transition.

    Every transition requires a schema-valid registry record.
    Candidate and production promotion also require the canonical
    WalkBuddy taxonomy. Production requires a matching PR #177 PASS.
    """

    if not validate_registry_record(record):
        return False

    current_status = record["lifecycle"]["status"]

    if target_status not in ALLOWED_TRANSITIONS:
        raise ValueError(
            f"Unknown lifecycle status: {target_status}"
        )

    allowed_targets = ALLOWED_TRANSITIONS[current_status]

    if target_status not in allowed_targets:
        raise ValueError(
            f"Invalid lifecycle transition: "
            f"{current_status} -> {target_status}"
        )

    if target_status in {"candidate", "production"}:
        if not uses_approved_taxonomy(record):
            print(
                f"Promotion blocked: "
                f"{current_status} -> {target_status}"
            )
            print(
                "- Model taxonomy does not match the canonical "
                "WalkBuddy taxonomy."
            )
            return False

    missing = find_missing_requirements(
        record,
        target_status
    )

    if missing:
        print(
            f"Promotion blocked: "
            f"{current_status} -> {target_status}"
        )

        print("Missing required evidence:")

        for field in missing:
            print(f"- {field}")

        return False

    if target_status == "production":
        if not validate_production_evidence(
            record,
            promotion_report,
        ):
            return False

    record["lifecycle"]["status"] = target_status

    print(
        f"Lifecycle transition approved: "
        f"{current_status} -> {target_status}"
    )

    return True


def parse_args():
    parser = argparse.ArgumentParser(
        description=(
            "Apply a controlled WalkBuddy model lifecycle transition."
        )
    )

    parser.add_argument(
        "record",
        help="Path to the model registry JSON record.",
    )

    parser.add_argument(
        "target_status",
        choices=ALLOWED_TRANSITIONS.keys(),
        help="Requested lifecycle status.",
    )

    parser.add_argument(
        "--promotion-report",
        help=(
            "PR #177 model_comparison.json report. "
            "Required for candidate -> production."
        ),
    )

    return parser.parse_args()


def main():
    args = parse_args()

    record_path = Path(args.record)

    if not record_path.exists():
        print(f"File not found: {record_path}")
        sys.exit(1)

    try:
        record = load_json(record_path)

        promotion_report = None

        if args.promotion_report:
            promotion_report_path = Path(
                args.promotion_report
            )

            if not promotion_report_path.exists():
                print(
                    "Promotion report not found: "
                    f"{promotion_report_path}"
                )
                sys.exit(1)

            promotion_report = load_json(
                promotion_report_path
            )

        success = transition_model(
            record,
            args.target_status,
            promotion_report=promotion_report,
        )

        if not success:
            sys.exit(1)

        save_json(record_path, record)

    except (
        KeyError,
        ValueError,
        json.JSONDecodeError,
    ) as error:
        print(f"Transition failed: {error}")
        sys.exit(1)


if __name__ == "__main__":
    main()