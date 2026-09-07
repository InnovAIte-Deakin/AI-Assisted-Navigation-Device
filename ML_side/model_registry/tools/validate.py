import json
import sys
from pathlib import Path

from jsonschema import Draft202012Validator, FormatChecker
from jsonschema.exceptions import SchemaError


BASE_DIR = Path(__file__).resolve().parents[1]
SCHEMA_PATH = BASE_DIR / "schema" / "model.schema.json"

FORMAT_CHECKER = FormatChecker()

# The schema file and its compiled validator do not change at runtime, so
# build the validator once and reuse it. validate_record() is called many
# times per test run and once per record in any bulk validation, and a
# fresh file read plus JSON parse plus validator construction each call is
# pure overhead.
_VALIDATOR = None


def load_json(path):
    with open(path, "r", encoding="utf-8") as file:
        return json.load(file)


def get_validator():
    global _VALIDATOR

    if _VALIDATOR is None:
        schema = load_json(SCHEMA_PATH)
        Draft202012Validator.check_schema(schema)
        _VALIDATOR = Draft202012Validator(
            schema,
            format_checker=FORMAT_CHECKER
        )

    return _VALIDATOR


def validate_record(record):
    validator = get_validator()

    errors = sorted(
        validator.iter_errors(record),
        key=lambda error: list(error.absolute_path)
    )

    return errors


def validate_model(record_path):
    record = load_json(record_path)

    errors = validate_record(record)

    if errors:
        print(f"Validation failed for: {record_path}")

        for error in errors:
            field = ".".join(
                str(part) for part in error.absolute_path
            )

            if field:
                print(f"- {field}: {error.message}")
            else:
                print(f"- {error.message}")

        return False

    print(f"Valid model record: {record_path}")
    return True


def main():
    if len(sys.argv) != 2:
        print("Usage: python validate.py <model-record.json>")
        sys.exit(1)

    record_path = Path(sys.argv[1])

    if not record_path.exists():
        print(f"File not found: {record_path}")
        sys.exit(1)

    try:
        valid = validate_model(record_path)

    except json.JSONDecodeError as error:
        print(f"Invalid JSON: {error}")
        sys.exit(1)

    except SchemaError as error:
        # The schema file itself is malformed. This is a tooling bug,
        # not an invalid record, so report it distinctly.
        print(f"Model schema is invalid: {error}")
        sys.exit(2)

    except OSError as error:
        print(f"Could not read file: {error}")
        sys.exit(1)

    if not valid:
        sys.exit(1)


if __name__ == "__main__":
    main()