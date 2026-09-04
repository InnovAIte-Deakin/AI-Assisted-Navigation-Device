"""Tests for the pure helper functions in routers/ai_service.py:
normalize_vision_events, is_current_scene_question, current_scene_response.

routers.ai_service transitively imports adapters.vision_adapter (ultralytics)
and adapters.ocr_adapter (easyocr/cv2), so — matching the isolation pattern
already used in test_ml_runtime.py — the heavy/adjacent modules are faked
before import. These three functions don't touch any of that machinery, so
the fakes are never actually exercised; they only exist to keep collection
fast and independent of whether CV/OCR/model dependencies are installed.
"""
from pathlib import Path
import sys
from types import ModuleType

import pytest

BACKEND_DIR = Path(__file__).resolve().parents[1]
if str(BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(BACKEND_DIR))

_STUB_MODULES = (
    "adapters",
    "adapters.vision_adapter",
    "adapters.ocr_adapter",
    "internal",
    "internal.state",
    "internal.motion_tracker",
    "tts_service",
    "tts_service.message_reasoning",
    "slow_lane",
)


@pytest.fixture
def ai_service():
    """Import routers.ai_service with its heavy dependencies faked out."""
    original_modules = {name: sys.modules[name] for name in _STUB_MODULES if name in sys.modules}
    original_modules["routers.ai_service"] = sys.modules.get("routers.ai_service")
    for name in (*_STUB_MODULES, "routers.ai_service"):
        sys.modules.pop(name, None)

    adapters = ModuleType("adapters")
    adapters.__path__ = []
    vision = ModuleType("adapters.vision_adapter")
    vision.vision_adapter = lambda *_a, **_k: {"detections": [], "image_id": "frame", "metadata": {}}
    ocr = ModuleType("adapters.ocr_adapter")
    ocr.ocr_adapter = lambda *_a, **_k: {"detections": [], "image_id": "frame"}

    internal = ModuleType("internal")
    internal.__path__ = []
    state = ModuleType("internal.state")
    state.memory = type("FakeMemory", (), {"buffer": [], "add_event": lambda self, **_k: None})()
    motion = ModuleType("internal.motion_tracker")
    motion.MotionTracker = type("MotionTracker", (), {"update": lambda self, detections, **_k: detections})

    tts_service = ModuleType("tts_service")
    tts_service.__path__ = []
    reasoning = ModuleType("tts_service.message_reasoning")
    reasoning.process_adapter_output = lambda *_a, **_k: []

    slow_lane = ModuleType("slow_lane")
    slow_lane.safe_or_stop_recommendation = lambda *_a, **_k: None

    sys.modules.update({
        "adapters": adapters,
        "adapters.vision_adapter": vision,
        "adapters.ocr_adapter": ocr,
        "internal": internal,
        "internal.state": state,
        "internal.motion_tracker": motion,
        "tts_service": tts_service,
        "tts_service.message_reasoning": reasoning,
        "slow_lane": slow_lane,
    })

    import routers.ai_service as module
    try:
        yield module
    finally:
        sys.modules.pop("routers.ai_service", None)
        for name, original in original_modules.items():
            if original is not None:
                sys.modules[name] = original
            else:
                sys.modules.pop(name, None)


# ── normalize_vision_events ────────────────────────────────────────────────

def test_normalize_vision_events_rejects_non_list_input(ai_service):
    assert ai_service.normalize_vision_events("not a list") == []
    assert ai_service.normalize_vision_events(None) == []
    assert ai_service.normalize_vision_events({"label": "stairs"}) == []


def test_normalize_vision_events_skips_non_dict_entries(ai_service):
    result = ai_service.normalize_vision_events(["a string", 42, {"label": "door"}])

    assert len(result) == 1
    assert result[0]["label"] == "door"


def test_normalize_vision_events_skips_events_with_no_label_or_category(ai_service):
    result = ai_service.normalize_vision_events([{"confidence": 0.9}])

    assert result == []


def test_normalize_vision_events_falls_back_to_category_when_label_missing(ai_service):
    result = ai_service.normalize_vision_events([{"category": "stairs"}])

    assert result[0]["label"] == "stairs"


def test_normalize_vision_events_label_takes_precedence_over_category(ai_service):
    result = ai_service.normalize_vision_events([{"label": "stairs", "category": "door"}])

    assert result[0]["label"] == "stairs"


def test_normalize_vision_events_coerces_confidence_to_float(ai_service):
    result = ai_service.normalize_vision_events([{"label": "stairs", "confidence": "0.75"}])

    assert result[0]["confidence"] == 0.75
    assert isinstance(result[0]["confidence"], float)


def test_normalize_vision_events_invalid_confidence_defaults_to_zero(ai_service):
    result = ai_service.normalize_vision_events([{"label": "stairs", "confidence": "not-a-number"}])

    assert result[0]["confidence"] == 0.0


def test_normalize_vision_events_missing_confidence_defaults_to_zero(ai_service):
    result = ai_service.normalize_vision_events([{"label": "stairs"}])

    assert result[0]["confidence"] == 0.0


def test_normalize_vision_events_direction_defaults_to_ahead(ai_service):
    result = ai_service.normalize_vision_events([{"label": "stairs", "direction": ""}])

    assert result[0]["direction"] == "ahead"


def test_normalize_vision_events_preserves_given_direction(ai_service):
    result = ai_service.normalize_vision_events([{"label": "stairs", "direction": "left"}])

    assert result[0]["direction"] == "left"


def test_normalize_vision_events_passes_distance_m_through_unchanged(ai_service):
    result = ai_service.normalize_vision_events([{"label": "stairs", "distance_m": 2.5}])

    assert result[0]["distance_m"] == 2.5
    assert ai_service.normalize_vision_events([{"label": "stairs"}])[0]["distance_m"] is None


# ── is_current_scene_question ──────────────────────────────────────────────

@pytest.mark.parametrize("question", [
    "What's in front of me?",
    "What is ahead?",
    "Is there anything around me?",
    "Any obstacles nearby?",
    "Is it dangerous here?",
])
def test_is_current_scene_question_recognizes_scene_queries(ai_service, question):
    assert ai_service.is_current_scene_question(question) is True


@pytest.mark.parametrize("question", [
    "What's your name?",
    "Can you set a reminder?",
    "Play some music",
])
def test_is_current_scene_question_rejects_unrelated_queries(ai_service, question):
    assert ai_service.is_current_scene_question(question) is False


def test_is_current_scene_question_is_case_insensitive(ai_service):
    assert ai_service.is_current_scene_question("WHAT IS AHEAD") is True


# ── current_scene_response ─────────────────────────────────────────────────

def test_current_scene_response_with_no_events_returns_fallback_message(ai_service):
    message = ai_service.current_scene_response([])

    assert "do not detect any clear objects" in message


def test_current_scene_response_describes_a_single_event(ai_service):
    message = ai_service.current_scene_response([
        {"label": "stairs", "direction": "ahead", "confidence": 0.9},
    ])

    assert message == "I can see stairs ahead."


def test_current_scene_response_defaults_missing_direction_to_ahead(ai_service):
    message = ai_service.current_scene_response([{"label": "door", "confidence": 0.9}])

    assert message == "I can see door ahead."


def test_current_scene_response_keeps_only_the_top_three_by_confidence(ai_service):
    events = [
        {"label": "a", "direction": "ahead", "confidence": 0.1},
        {"label": "b", "direction": "ahead", "confidence": 0.9},
        {"label": "c", "direction": "ahead", "confidence": 0.8},
        {"label": "d", "direction": "ahead", "confidence": 0.7},
        {"label": "e", "direction": "ahead", "confidence": 0.6},
    ]

    message = ai_service.current_scene_response(events)

    assert message == "I can see b ahead, c ahead, d ahead."
