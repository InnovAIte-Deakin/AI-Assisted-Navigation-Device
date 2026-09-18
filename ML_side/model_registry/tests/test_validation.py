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


def _candidate_record():
    source = RECORDS_DIR / "navigation_candidate.json"

    with open(source, "r", encoding="utf-8") as file:
        return json.load(file)


def _write_record(tmp_path, record, filename="record.json"):
    test_file = tmp_path / filename

    with open(test_file, "w", encoding="utf-8") as file:
        json.dump(record, file)

    return test_file


@pytest.mark.parametrize(
    ("field", "reference"),
    [
        ("manifest_reference", "ML_side/datasets/releases/v5/release_manifest.json"),
        ("configuration_reference", "ML_side/config/training_navigation.yaml"),
    ],
)
def test_portable_repository_references_pass(tmp_path, field, reference):
    record = _candidate_record()
    section = "dataset" if field == "manifest_reference" else "training"
    record[section][field] = reference

    assert validate_model(_write_record(tmp_path, record)) is True


@pytest.mark.parametrize(
    ("field", "reference"),
    [
        ("manifest_reference", "datasets/releases/v5/release_manifest.json"),
        ("configuration_reference", "config/training_navigation.yaml"),
    ],
)
def test_portable_ml_side_references_pass(tmp_path, field, reference):
    record = _candidate_record()
    section = "dataset" if field == "manifest_reference" else "training"
    record[section][field] = reference

    assert validate_model(_write_record(tmp_path, record)) is True


def test_documented_external_manifest_reference_passes(tmp_path):
    record = _candidate_record()
    record["dataset"]["manifest_reference"] = "external-local/manifest.json"

    assert validate_model(_write_record(tmp_path, record)) is True


@pytest.mark.parametrize(
    "reference",
    [
        r"C:\Users\developer\release_manifest.json",
        r"\\server\developer-share\release_manifest.json",
        "/home/developer/release_manifest.json",
        "~/controlled-releases/release_manifest.json",
        "../../release_manifest.json",
        r"ML_side\\datasets\\release_manifest.json",
    ],
)
@pytest.mark.parametrize(
    ("section", "field"),
    [
        ("dataset", "manifest_reference"),
        ("training", "configuration_reference"),
    ],
)
def test_local_or_traversal_lineage_references_fail(tmp_path, section, field, reference):
    record = _candidate_record()
    record[section][field] = reference

    assert validate_model(_write_record(tmp_path, record)) is False


def test_artifact_location_remains_unrestricted(tmp_path):
    record = _candidate_record()
    record["artifact"]["location"] = r"C:\approved-model-storage\candidate.pt"

    assert validate_model(_write_record(tmp_path, record)) is True
