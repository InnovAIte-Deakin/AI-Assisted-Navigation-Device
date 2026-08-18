import json
import sys
from pathlib import Path


# Defines which lifecycle transitions are permitted.
# Each key represents the model's current lifecycle status,
# while the associated set contains the statuses it can move to.
ALLOWED_TRANSITIONS = {
    "experimental": {"candidate", "rejected"},
    "candidate": {"production", "rejected"},
    "production": {"deprecated", "rolled_back"},
    "deprecated": {"rolled_back"},
    "rejected": set(),
    "rolled_back": set()
}


# Evidence that must be present before an experimental model
# can be promoted to candidate status.
CANDIDATE_REQUIREMENTS = [
    "dataset.release_id",
    "dataset.manifest_reference",
    "training.training_date",
    "training.configuration_reference",
    "artifact.filename",
    "artifact.location",
    "artifact.sha256"
]


# Evidence that must be present before a candidate model
# can be promoted to production status.
# Production additionally requires evaluation evidence.
PRODUCTION_REQUIREMENTS = [
    "dataset.release_id",
    "dataset.manifest_reference",
    "training.training_date",
    "training.configuration_reference",
    "artifact.filename",
    "artifact.location",
    "artifact.sha256",
    "evaluation.evidence_reference"
]


def load_json(path):
    """Load and return a model metadata record from a JSON file."""
    with open(path, "r", encoding="utf-8") as file:
        return json.load(file)


def save_json(path, record):
    """Save an updated model metadata record back to its JSON file."""
    with open(path, "w", encoding="utf-8") as file:
        json.dump(record, file, indent=2)
        file.write("\n")


def get_nested_value(record, field_path):
    """
    Retrieve a nested value from the metadata record using a
    dot-separated field path, such as 'artifact.sha256'.

    Returns None if any part of the path does not exist.
    """
    value = record

    for part in field_path.split("."):
        if not isinstance(value, dict) or part not in value:
            return None

        value = value[part]

    return value


def find_missing_requirements(record, target_status):
    """
    Check whether all evidence required for the requested target
    lifecycle status is present in the model record.

    Only candidate and production promotions require additional
    evidence checks.
    """
    if target_status == "candidate":
        requirements = CANDIDATE_REQUIREMENTS

    elif target_status == "production":
        requirements = PRODUCTION_REQUIREMENTS

    else:
        # Other lifecycle transitions do not require promotion evidence.
        return []

    missing = []

    # Check each required nested field and record fields that
    # are missing or contain an empty value.
    for field in requirements:
        value = get_nested_value(record, field)

        if value is None or value == "":
            missing.append(field)

    return missing


def transition_model(record, target_status):
    """
    Attempt to move a model record to a new lifecycle status.

    The transition is approved only when:
    1. The target status is recognised.
    2. The requested transition is permitted.
    3. All evidence required for the target status is present.

    Returns True if the transition succeeds, otherwise False.
    Invalid transitions raise ValueError.
    """

    # Read the model's current lifecycle status from the metadata record.
    current_status = record["lifecycle"]["status"]

    # Prevent transitions to lifecycle states that are not recognised.
    if target_status not in ALLOWED_TRANSITIONS:
        raise ValueError(f"Unknown lifecycle status: {target_status}")

    # Determine which target states are permitted from the current state.
    allowed_targets = ALLOWED_TRANSITIONS[current_status]

    if target_status not in allowed_targets:
        raise ValueError(
            f"Invalid lifecycle transition: "
            f"{current_status} -> {target_status}"
        )

    # Check whether the metadata contains all evidence required
    # for promotion to the requested lifecycle status.
    missing = find_missing_requirements(record, target_status)

    if missing:
        print(
            f"Promotion blocked: "
            f"{current_status} -> {target_status}"
        )

        print("Missing required evidence:")

        # Report every missing requirement so the developer knows
        # which metadata must be completed before retrying.
        for field in missing:
            print(f"- {field}")

        return False

    # All transition and evidence checks have passed.
    # Update the lifecycle status in the in-memory record.
    record["lifecycle"]["status"] = target_status

    print(
        f"Lifecycle transition approved: "
        f"{current_status} -> {target_status}"
    )

    return True


def main():
    """
    Command-line entry point.

    Expected usage:
        python transition.py <model-record.json> <target-status>
    """

    # The command requires exactly two arguments:
    # the model record path and the requested target status.
    if len(sys.argv) != 3:
        print(
            "Usage: python transition.py "
            "<model-record.json> <target-status>"
        )
        sys.exit(1)

    # Convert the supplied record path into a Path object
    # for easier file existence checking.
    record_path = Path(sys.argv[1])
    target_status = sys.argv[2]

    if not record_path.exists():
        print(f"File not found: {record_path}")
        sys.exit(1)

    try:
        # Load the model metadata record.
        record = load_json(record_path)

        # Attempt the requested lifecycle transition.
        success = transition_model(record, target_status)

        # A failed evidence check blocks the promotion without
        # modifying the original metadata file.
        if not success:
            sys.exit(1)

        # Persist the lifecycle change only after all checks succeed.
        save_json(record_path, record)

    except (KeyError, ValueError, json.JSONDecodeError) as error:
        # Handle malformed metadata, invalid transitions,
        # and invalid JSON in a consistent way.
        print(f"Transition failed: {error}")
        sys.exit(1)


# Run main() only when this script is executed directly.
if __name__ == "__main__":
    main()