"""Tests for the centralized, policy-neutral navigation ML contract."""

from __future__ import annotations

import importlib.util
import sys
from dataclasses import FrozenInstanceError
from pathlib import Path
from types import ModuleType, SimpleNamespace

import pytest


BACKEND_DIR = Path(__file__).resolve().parents[1]
if str(BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(BACKEND_DIR))

from ml_contract import navigation_semantics as semantics
from ml_contract.navigation_semantics import (
    BaseSeverity,
    NAVIGATION_CLASSES,
    NavigationClass,
    canonicalize_class_name,
    get_base_severity,
    get_navigation_class,
    get_navigation_class_by_id,
    get_spoken_name,
    is_potential_hazard,
    severity_rank,
)
from tts_service.message_reasoning import Detection, format_object_name, generate_guidance_message
from tts_service.tts_service import RiskLevel


EXPECTED_CLASSES = (
    (0, "person", BaseSeverity.HIGH),
    (1, "stairs", BaseSeverity.CRITICAL),
    (2, "door", BaseSeverity.MEDIUM),
    (3, "chair", BaseSeverity.MEDIUM),
    (4, "table", BaseSeverity.MEDIUM),
    (5, "pole", BaseSeverity.HIGH),
    (6, "bicycle", BaseSeverity.HIGH),
    (7, "vehicle", BaseSeverity.CRITICAL),
)


def _load_safetygate() -> ModuleType:
    path = BACKEND_DIR / "slow_lane" / "safetygate.py"
    spec = importlib.util.spec_from_file_location("navigation_semantics_safetygate", path)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _load_vision_adapter(monkeypatch: pytest.MonkeyPatch) -> ModuleType:
    fake_cv2 = ModuleType("cv2")
    fake_ultralytics = ModuleType("ultralytics")
    fake_ultralytics.YOLO = object
    fake_trace = SimpleNamespace(get_tracer=lambda _: object())
    fake_opentelemetry = ModuleType("opentelemetry")
    fake_opentelemetry.trace = fake_trace
    fake_tts_package = ModuleType("tts_service")
    fake_tts_package.__path__ = []
    fake_reasoning = ModuleType("tts_service.message_reasoning")
    fake_reasoning.calculate_spatial_position = lambda _bbox, _width: "ahead"

    monkeypatch.setitem(sys.modules, "cv2", fake_cv2)
    monkeypatch.setitem(sys.modules, "ultralytics", fake_ultralytics)
    monkeypatch.setitem(sys.modules, "opentelemetry", fake_opentelemetry)
    monkeypatch.setitem(sys.modules, "tts_service", fake_tts_package)
    monkeypatch.setitem(sys.modules, "tts_service.message_reasoning", fake_reasoning)

    path = BACKEND_DIR / "adapters" / "vision_adapter.py"
    spec = importlib.util.spec_from_file_location("navigation_semantics_vision_adapter", path)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_contract_has_the_exact_approved_taxonomy_and_order() -> None:
    assert tuple((item.class_id, item.name, item.base_severity) for item in NAVIGATION_CLASSES) == (
        EXPECTED_CLASSES
    )
    for class_id, name, _ in EXPECTED_CLASSES:
        assert get_navigation_class_by_id(class_id) is get_navigation_class(name)
    assert get_navigation_class_by_id(True) is None
    assert get_navigation_class_by_id(8) is None


def test_all_approved_classes_are_potential_hazards_with_canonical_spoken_names() -> None:
    for _, name, _ in EXPECTED_CLASSES:
        assert is_potential_hazard(name) is True
        assert get_spoken_name(name) == name


def test_office_chair_is_the_only_justified_alias() -> None:
    assert tuple(item.aliases for item in NAVIGATION_CLASSES) == (
        (),
        (),
        (),
        ("office-chair",),
        (),
        (),
        (),
        (),
    )
    navigation_class = get_navigation_class("office-chair")
    assert navigation_class is not None
    assert navigation_class.name == "chair"
    assert canonicalize_class_name("office-chair") == "chair"
    assert get_base_severity("office-chair") == BaseSeverity.MEDIUM


def test_contract_normalizes_case_and_whitespace_before_exact_matching() -> None:
    for label in ("person", "Person", "PERSON", " person", "person ", " person "):
        assert canonicalize_class_name(label) == "person"
    assert canonicalize_class_name("  OFFICE-CHAIR  ") == "chair"
    assert canonicalize_class_name("\tVehicle\n") == "vehicle"
    assert canonicalize_class_name("") is None
    assert canonicalize_class_name("   ") is None
    assert canonicalize_class_name(None) is None


@pytest.mark.parametrize(
    "label",
    (
        "chairish",
        "outdoor",
        "doorway",
        "door sign",
        "flagpole",
        "pole sign",
        "timetable",
        "wheelchair",
        "officechair",
        "office chair",
        "vehicle-sign",
        "vehicle-2",
    ),
)
def test_contract_uses_no_fuzzy_or_substring_matching(label: str) -> None:
    assert get_navigation_class(label) is None
    assert canonicalize_class_name(label) is None
    assert is_potential_hazard(label) is False


@pytest.mark.parametrize("label", ("unknown", "tree", "book", "books", "monitor", "tv", "random-label", ""))
def test_unknown_labels_do_not_acquire_canonical_semantics(label: str) -> None:
    assert get_navigation_class(label) is None
    assert canonicalize_class_name(label) is None
    assert get_base_severity(label) is None
    assert get_spoken_name(label) is None
    assert is_potential_hazard(label) is False


def test_contract_is_immutable_and_rejects_duplicate_definitions() -> None:
    with pytest.raises(FrozenInstanceError):
        NAVIGATION_CLASSES[0].name = "changed"  # type: ignore[misc]
    with pytest.raises(FrozenInstanceError):
        NAVIGATION_CLASSES[3].aliases += ("officechair",)  # type: ignore[misc]
    with pytest.raises(TypeError):
        semantics._BY_ID[0] = NAVIGATION_CLASSES[1]  # type: ignore[index]
    with pytest.raises(TypeError):
        semantics._BY_NORMALIZED_NAME["person"] = NAVIGATION_CLASSES[1]  # type: ignore[index]
    with pytest.raises(AttributeError):
        BaseSeverity.HIGH.value = 99  # type: ignore[misc]
    with pytest.raises(AttributeError):
        BaseSeverity.HIGH._value_ = 99  # type: ignore[misc]
    with pytest.raises(RuntimeError, match="unique"):
        semantics._build_class_name_lookup(
            (
                NavigationClass(0, "person", BaseSeverity.HIGH, "person", True),
                NavigationClass(1, "person", BaseSeverity.HIGH, "person", True),
            )
        )
    with pytest.raises(RuntimeError, match="consecutive"):
        semantics._build_class_id_lookup(
            (
                NavigationClass(0, "person", BaseSeverity.HIGH, "person", True),
                NavigationClass(0, "stairs", BaseSeverity.CRITICAL, "stairs", True),
            )
        )


def test_severity_order_is_explicit_and_no_approved_class_is_low() -> None:
    assert [severity_rank(level) for level in BaseSeverity] == [1, 2, 3, 4]
    assert BaseSeverity.LOW < BaseSeverity.MEDIUM < BaseSeverity.HIGH < BaseSeverity.CRITICAL
    assert all(item.base_severity is not BaseSeverity.LOW for item in NAVIGATION_CLASSES)


def test_vision_priority_consumer_uses_the_agreed_contract(monkeypatch: pytest.MonkeyPatch) -> None:
    vision_adapter = _load_vision_adapter(monkeypatch)

    for _, name, severity in EXPECTED_CLASSES:
        priority = vision_adapter.get_priority(name)
        assert isinstance(priority, str)
        assert priority == severity.name
    assert vision_adapter.get_priority("office-chair") == BaseSeverity.MEDIUM.name
    assert vision_adapter.get_priority("unknown") == BaseSeverity.LOW.name


def test_spoken_names_do_not_add_sign_heuristics_to_navigation_classes() -> None:
    for _, name, _ in EXPECTED_CLASSES:
        assert format_object_name(name) == name
    assert format_object_name("office-chair") == "chair"
    assert format_object_name("EXIT") == "exit sign"


def test_office_chair_guidance_uses_canonical_chair_semantics() -> None:
    message = generate_guidance_message(
        Detection(
            category="office-chair",
            confidence=0.9,
            bbox={"x_min": 0, "y_min": 0, "x_max": 10, "y_max": 10},
            direction="ahead",
        )
    )

    assert message is not None
    assert message.message == "chair ahead"
    assert message.risk_level is RiskLevel.MEDIUM


@pytest.mark.parametrize(("_class_id", "name", "severity"), EXPECTED_CLASSES)
def test_guidance_uses_the_contract_base_severity_for_every_canonical_class(
    _class_id: int,
    name: str,
    severity: BaseSeverity,
) -> None:
    message = generate_guidance_message(
        Detection(
            category=name,
            confidence=0.9,
            bbox={"x_min": 0, "y_min": 0, "x_max": 10, "y_max": 10},
            direction="ahead",
        )
    )

    assert message is not None
    assert message.message == f"{name} ahead"
    assert message.risk_level is RiskLevel[severity.name]


def test_bicycle_and_vehicle_are_recognized_by_the_contract() -> None:
    assert canonicalize_class_name("bicycle") == "bicycle"
    assert canonicalize_class_name("vehicle") == "vehicle"
    assert get_base_severity("bicycle") is BaseSeverity.HIGH
    assert get_base_severity("vehicle") is BaseSeverity.CRITICAL


def test_safetygate_preserves_context_before_a_potential_hazard_warns() -> None:
    safetygate = _load_safetygate()

    for _, name, _ in EXPECTED_CLASSES:
        assert safetygate.extract_hazards(
            [{"label": name, "direction": "left", "confidence": 0.9}]
        ) == []
        assert safetygate.extract_hazards(
            [{"label": name, "direction": "right", "confidence": 0.9}]
        ) == []
        assert safetygate.extract_hazards(
            [{"label": name, "direction": "ahead", "confidence": 0.49}]
        ) == []
        assert safetygate.extract_hazards(
            [{"label": name, "direction": "ahead", "confidence": 0.9}]
        )


def test_safetygate_uses_exact_identity_and_canonical_hazard_wording() -> None:
    safetygate = _load_safetygate()

    for label in (
        "outdoor",
        "doorway",
        "flagpole",
        "timetable",
        "wheelchair",
        "vehicle-sign",
    ):
        assert safetygate.extract_hazards(
            [{"label": label, "direction": "ahead", "confidence": 0.9}]
        ) == []
    assert safetygate.extract_hazards(
        [{"label": "office-chair", "direction": "ahead", "confidence": 0.9}]
    ) == ["chair ahead"]


@pytest.mark.parametrize(
    "label",
    ("stair", "wall", "obstacle", "edge", "monitor", "whiteboard", "tv", "couch", "books"),
)
def test_safetygate_retains_only_explicit_historical_non_mvp_labels(label: str) -> None:
    safetygate = _load_safetygate()

    assert get_navigation_class(label) is None
    assert safetygate.extract_hazards(
        [{"label": label, "direction": "ahead", "confidence": 0.9}]
    ) == [f"{label} ahead"]
