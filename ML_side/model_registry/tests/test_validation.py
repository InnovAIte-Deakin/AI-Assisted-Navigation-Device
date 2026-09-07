import json
import sys
from pathlib import Path

import pytest


TOOLS_DIR = Path(__file__).resolve().parents[1] / "tools"
sys.path.insert(0, str(TOOLS_DIR))

from validate import validate_model


BASE_DIR = Path(__file__).resolve().parents[1]
RECORDS_DIR = BASE_DIR / "records"


def test_legacy_record_is_valid():
    record = RECORDS_DIR / "legacy_baseline.json"

    assert validate_model(record) is True


def test_navigation_candidate_is_valid():
    record = RECORDS_DIR / "navigation_candidate.json"

    assert validate_model(record) is True


def test_missing_required_field_fails(tmp_path):
    record = {
        "schema_version": "1.0"
    }

    test_file = tmp_path / "invalid.json"

    with open(test_file, "w", encoding="utf-8") as file:
        json.dump(record, file)

    assert validate_model(test_file) is False


def test_invalid_status_fails(tmp_path):
    source = RECORDS_DIR / "navigation_candidate.json"

    with open(source, "r", encoding="utf-8") as file:
        record = json.load(file)

    record["lifecycle"]["status"] = "invalid_status"

    test_file = tmp_path / "invalid_status.json"

    with open(test_file, "w", encoding="utf-8") as file:
        json.dump(record, file)

    assert validate_model(test_file) is False


def test_invalid_sha256_fails(tmp_path):
    source = RECORDS_DIR / "navigation_candidate.json"

    with open(source, "r", encoding="utf-8") as file:
        record = json.load(file)

    record["artifact"]["sha256"] = "12345"

    test_file = tmp_path / "invalid_checksum.json"

    with open(test_file, "w", encoding="utf-8") as file:
        json.dump(record, file)

    assert validate_model(test_file) is False

def test_invalid_training_date_fails(tmp_path):
    source = RECORDS_DIR / "navigation_candidate.json"

    with open(source, "r", encoding="utf-8") as file:
        record = json.load(file)

    record["training"]["training_date"] = "banana"

    test_file = tmp_path / "invalid_date.json"

    with open(test_file, "w", encoding="utf-8") as file:
        json.dump(record, file)

    assert validate_model(test_file) is False