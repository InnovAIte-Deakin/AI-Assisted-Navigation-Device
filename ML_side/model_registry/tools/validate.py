import json
import sys
from pathlib import Path

from jsonschema import Draft202012Validator


# Base directory of the model metadata workflow.
# This allows the script to locate the schema using a path
# relative to the repository structure rather than the current
# working directory.
BASE_DIR = Path(__file__).resolve().parents[1]

# Path to the JSON Schema used to validate model metadata records.
SCHEMA_PATH = BASE_DIR / "schema" / "model.schema.json"


def load_json(path):
    """Load and return JSON data from the specified file."""
    with open(path, "r", encoding="utf-8") as file:
        return json.load(file)


def validate_model(record_path):
    """
    Validate a model metadata record against the model JSON Schema.

    Returns True when the record satisfies the schema.
    Returns False when one or more validation errors are found.
    """

    # Load both the authoritative schema and the model record
    # that needs to be validated.
    schema = load_json(SCHEMA_PATH)
    record = load_json(record_path)

    # Create a validator that follows JSON Schema Draft 2020-12.
    validator = Draft202012Validator(schema)

    # Collect all validation errors instead of stopping at the first one.
    # Sorting them by their location in the JSON record makes the output
    # easier for developers to read and fix.
    errors = sorted(
        validator.iter_errors(record),
        key=lambda error: list(error.absolute_path)
    )

    if errors:
        print(f"Validation failed for: {record_path}")

        # Report each schema violation together with the field
        # where the error occurred.
        for error in errors:
            field = ".".join(str(part) for part in error.absolute_path)

            if field:
                print(f"- {field}: {error.message}")
            else:
                # Some schema errors apply to the whole record rather
                # than to a specific nested field.
                print(f"- {error.message}")

        return False

    # No schema violations were found.
    print(f"Valid model record: {record_path}")
    return True


def main():
    """
    Command-line entry point.

    Expected usage:
        python validate.py <model-record.json>
    """

    # Exactly one argument is required: the path to the
    # model metadata record that should be validated.
    if len(sys.argv) != 2:
        print("Usage: python validate.py <model-record.json>")
        sys.exit(1)

    record_path = Path(sys.argv[1])

    # Stop early if the supplied metadata file does not exist.
    if not record_path.exists():
        print(f"File not found: {record_path}")
        sys.exit(1)

    try:
        # Validate the supplied model record against the schema.
        valid = validate_model(record_path)

    except json.JSONDecodeError as error:
        # Handle malformed JSON separately so developers can
        # distinguish syntax problems from schema validation errors.
        print(f"Invalid JSON: {error}")
        sys.exit(1)

    except Exception as error:
        # Catch other unexpected validation or file-related errors
        # and report them without displaying an unhandled traceback.
        print(f"Validation error: {error}")
        sys.exit(1)

    # Return a non-zero exit code when schema validation fails.
    # This also allows the script to be used in automated checks or CI.
    if not valid:
        sys.exit(1)


# Run the validator only when this file is executed directly.
if __name__ == "__main__":
    main()