"""Model-free tests for navigation-taxonomy compatibility reporting.

This module deliberately avoids importing the ``ml_runtime`` package, whose
``__init__`` pulls in the FastAPI router. Loading ``model_info`` directly keeps
these contract tests runnable in the lightweight ML safety workflow without
FastAPI, PyTorch, Ultralytics, model weights, or network access.
"""

from __future__ import annotations

import importlib.util
import sys
from pathlib import Path
from types import ModuleType

import pytest


BACKEND_DIR = Path(__file__).resolve().parents[1]
if str(BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(BACKEND_DIR))

from ml_contract import NAVIGATION_CLASSES


def _load_model_info() -> ModuleType:
    path = BACKEND_DIR / "ml_runtime" / "model_info.py"
    spec = importlib.util.spec_from_file_location("walkbuddy_model_info", path)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    # Registered before execution so the frozen dataclass can resolve its own
    # postponed annotations.
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


model_info = _load_model_info()

HISTORICAL_CLASS_NAMES = [
    "book",
    "books",
    "monitor",
    "office-chair",
    "whiteboard",
    "table",
    "tv",
]


def canonical_class_names() -> list[str]:
    """Derive the approved ordered names from the single canonical contract."""
    return [navigation_class.name for navigation_class in NAVIGATION_CLASSES]


def write_artifact(tmp_path: Path) -> Path:
    artifact = tmp_path / "best.pt"
    artifact.write_bytes(b"walkbuddy-model")
    return artifact


class NamedModel:
    def __init__(self, names: object) -> None:
        self.names = names


def test_approved_taxonomy_is_derived_from_the_navigation_contract() -> None:
    assert model_info.APPROVED_TAXONOMY == tuple(canonical_class_names())
    assert list(model_info.APPROVED_TAXONOMY) == [
        "person",
        "stairs",
        "door",
        "chair",
        "table",
        "pole",
        "bicycle",
        "vehicle",
    ]


def test_exact_canonical_taxonomy_is_compatible() -> None:
    assert model_info.is_taxonomy_compatible(canonical_class_names()) is True


def test_historical_seven_class_taxonomy_is_incompatible() -> None:
    assert model_info.is_taxonomy_compatible(HISTORICAL_CLASS_NAMES) is False


def test_reordered_canonical_taxonomy_is_incompatible() -> None:
    reordered = canonical_class_names()
    reordered[0], reordered[1] = reordered[1], reordered[0]

    assert model_info.is_taxonomy_compatible(reordered) is False


def test_legacy_alias_does_not_satisfy_the_production_contract() -> None:
    aliased = canonical_class_names()
    aliased[aliased.index("chair")] = "office-chair"

    assert model_info.is_taxonomy_compatible(aliased) is False


def test_additional_class_is_incompatible() -> None:
    extended = canonical_class_names() + ["kerb"]

    assert model_info.is_taxonomy_compatible(extended) is False


def test_missing_class_is_incompatible() -> None:
    reduced = canonical_class_names()
    reduced.remove("pole")

    assert model_info.is_taxonomy_compatible(reduced) is False


@pytest.mark.parametrize("replacement", ["Person", "PERSON", "person "])
def test_case_and_spacing_variants_are_incompatible(replacement: str) -> None:
    variant = canonical_class_names()
    variant[0] = replacement

    assert model_info.is_taxonomy_compatible(variant) is False


def test_empty_class_names_are_incompatible() -> None:
    assert model_info.is_taxonomy_compatible([]) is False


def test_mapping_model_names_produce_a_compatible_lineage(tmp_path: Path) -> None:
    names = {index: name for index, name in enumerate(canonical_class_names())}

    lineage = model_info.capture_model_lineage(
        write_artifact(tmp_path), NamedModel(names), 12.5
    )

    assert lineage.loaded is True
    assert lineage.taxonomy_compatible is True
    assert lineage.num_classes == len(NAVIGATION_CLASSES)
    assert lineage.classes == canonical_class_names()
    assert lineage.as_dict()["taxonomy_compatible"] is True


def test_sequence_model_names_produce_a_compatible_lineage(tmp_path: Path) -> None:
    lineage = model_info.capture_model_lineage(
        write_artifact(tmp_path), NamedModel(canonical_class_names()), 12.5
    )

    assert lineage.taxonomy_compatible is True
    assert lineage.classes == canonical_class_names()


def test_loaded_model_with_historical_taxonomy_is_reported_incompatible(
    tmp_path: Path,
) -> None:
    names = {index: name for index, name in enumerate(HISTORICAL_CLASS_NAMES)}

    lineage = model_info.capture_model_lineage(
        write_artifact(tmp_path), NamedModel(names), 12.5
    )

    payload = lineage.as_dict()
    assert payload["loaded"] is True
    assert payload["taxonomy_compatible"] is False
    assert payload["failure_category"] is None
    assert payload["num_classes"] == len(HISTORICAL_CLASS_NAMES)


@pytest.mark.parametrize("names", [None, "person", 7, {}, [], {0: ""}, {-1: "person"}])
def test_malformed_model_names_still_raise_metadata_error(
    tmp_path: Path, names: object
) -> None:
    with pytest.raises(model_info.ModelMetadataError):
        model_info.capture_model_lineage(
            write_artifact(tmp_path), NamedModel(names), 12.5
        )


def test_failed_model_lineage_reports_unknown_compatibility() -> None:
    lineage = model_info.unavailable_model_lineage(
        Path("best.pt"), 5.0, "model_artifact_missing"
    )

    payload = lineage.as_dict()
    assert payload["loaded"] is False
    assert payload["taxonomy_compatible"] is None
    assert payload["failure_category"] == "model_artifact_missing"


def test_metadata_unavailable_lineage_reports_unknown_compatibility() -> None:
    lineage = model_info.metadata_unavailable_model_lineage(Path("best.pt"), 5.0)

    payload = lineage.as_dict()
    assert payload["loaded"] is True
    assert payload["taxonomy_compatible"] is None
    assert payload["failure_category"] == "model_metadata_unavailable"


def test_lineage_payload_preserves_existing_fields(tmp_path: Path) -> None:
    lineage = model_info.capture_model_lineage(
        write_artifact(tmp_path), NamedModel(canonical_class_names()), 12.5
    )

    payload = lineage.as_dict()
    assert set(payload) == {
        "loaded",
        "filename",
        "sha256",
        "size_bytes",
        "num_classes",
        "classes",
        "taxonomy_compatible",
        "load_duration_ms",
        "loaded_at",
        "runtime",
        "failure_category",
    }
    assert payload["filename"] == "best.pt"
    assert str(tmp_path) not in repr(payload)
