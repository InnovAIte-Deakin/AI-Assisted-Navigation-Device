"""
Unit tests for slow_lane: safetygate, memorybuffer, brain.

Run from the backend directory:
    pytest tests/test_slow_lane.py -v
"""

import json
import sys
from unittest.mock import MagicMock, patch

import pytest

# Guard: if llama_cpp native library is absent (e.g. CI), inject a stub so
# the brain module can be imported without the compiled extension.
if "llama_cpp" not in sys.modules:
    sys.modules["llama_cpp"] = MagicMock()

from slow_lane.safetygate import extract_hazards, safe_or_stop_recommendation
from slow_lane.memorybuffer import NavigationMemory
from slow_lane.brain import SlowLaneBrain


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _event(label, direction="ahead", confidence=0.9, distance_m=1.5):
    return {"label": label, "direction": direction, "confidence": confidence, "distance_m": distance_m}


def _make_brain(response_content: str) -> SlowLaneBrain:
    """Return a SlowLaneBrain backed by a mock Llama that returns response_content."""
    mock_instance = MagicMock()
    mock_instance.create_chat_completion.return_value = {
        "choices": [{"message": {"content": response_content}}]
    }
    with patch("slow_lane.brain.Llama", return_value=mock_instance):
        brain = SlowLaneBrain(model_path="/fake/model.gguf")
    brain.llm = mock_instance
    return brain


# ---------------------------------------------------------------------------
# safetygate — extract_hazards
# ---------------------------------------------------------------------------

def test_extract_hazards_no_hazards():
    events = [_event("bench", "ahead"), _event("tree", "left")]
    assert extract_hazards(events) == []


def test_extract_hazards_hazard_ahead():
    events = [_event("stairs", "ahead")]
    result = extract_hazards(events)
    assert len(result) == 1
    assert "stairs" in result[0]


def test_extract_hazards_hazard_not_ahead():
    # Only "ahead" direction should trigger — left/right should not
    events = [_event("stairs", "left"), _event("wall", "right")]
    assert extract_hazards(events) == []


def test_extract_hazards_multiple_hazards():
    events = [_event("stairs", "ahead"), _event("pole", "ahead"), _event("bench", "ahead")]
    result = extract_hazards(events)
    labels = " ".join(result)
    assert "stairs" in labels
    assert "pole" in labels
    assert "bench" not in labels  # bench is not a hazard keyword


# ---------------------------------------------------------------------------
# safetygate — safe_or_stop_recommendation
# ---------------------------------------------------------------------------

def test_safe_or_stop_no_hazards():
    events = [_event("bench", "ahead"), _event("tree", "left")]
    assert safe_or_stop_recommendation(events) is None


def test_safe_or_stop_returns_stop_message():
    events = [_event("stairs", "ahead")]
    result = safe_or_stop_recommendation(events)
    assert result is not None
    assert "stairs" in result.lower()
    assert "stop" in result.lower() or "not safe" in result.lower()


def test_safe_or_stop_message_names_all_hazards():
    events = [_event("wall", "ahead"), _event("door", "ahead")]
    result = safe_or_stop_recommendation(events)
    assert "wall" in result
    assert "door" in result


# ---------------------------------------------------------------------------
# NavigationMemory
# ---------------------------------------------------------------------------

def test_memorybuffer_add_and_retrieve():
    mem = NavigationMemory(max_events=10)
    mem.add_event("car", "ahead", 3.0, 0.85)
    mem.add_event("person", "left", 1.2, 0.92)
    assert len(mem.buffer) == 2
    labels = [e["label"] for e in mem.buffer]
    assert "car" in labels
    assert "person" in labels


def test_memorybuffer_maxlen_eviction():
    mem = NavigationMemory(max_events=2)
    mem.add_event("first", "ahead", 1.0, 0.9)
    mem.add_event("second", "left", 1.0, 0.9)
    mem.add_event("third", "right", 1.0, 0.9)  # should evict "first"
    assert len(mem.buffer) == 2
    labels = [e["label"] for e in mem.buffer]
    assert "first" not in labels
    assert "third" in labels


def test_memorybuffer_context_text_format():
    mem = NavigationMemory(max_events=10)
    mem.add_event("stairs", "ahead", 2.5, 0.88)
    text = mem.to_context_text()
    assert "stairs" in text
    assert "ahead" in text
    assert "2.5" in text
    assert "0.88" in text


def test_memorybuffer_context_text_empty():
    mem = NavigationMemory(max_events=10)
    assert mem.to_context_text() == ""


# ---------------------------------------------------------------------------
# SlowLaneBrain
# ---------------------------------------------------------------------------

def test_brain_ask_no_history_returns_suggested_action():
    payload = json.dumps({
        "suggested_action": "Move left to avoid the wall.",
        "summary": "Wall directly ahead.",
        "hazards": [],
    })
    brain = _make_brain(payload)
    result = brain.ask([_event("wall", "ahead")], "Is it safe to go forward?")
    assert result == "Move left to avoid the wall."


def test_brain_ask_history_is_injected_into_messages():
    payload = json.dumps({
        "suggested_action": "Continue ahead.",
        "summary": "Path clear.",
        "hazards": [],
    })
    mock_instance = MagicMock()
    mock_instance.create_chat_completion.return_value = {
        "choices": [{"message": {"content": payload}}]
    }
    with patch("slow_lane.brain.Llama", return_value=mock_instance):
        brain = SlowLaneBrain(model_path="/fake/model.gguf")
    brain.llm = mock_instance

    history = [
        {"role": "user", "content": "What was behind me?"},
        {"role": "assistant", "content": "A bench was behind you."},
    ]
    brain.ask([], "What is ahead?", history=history)

    call_args = mock_instance.create_chat_completion.call_args
    messages = call_args.kwargs.get("messages") or call_args.args[0]

    roles = [m["role"] for m in messages]
    assert roles[0] == "system"
    # history messages should appear before the final user message
    assert {"role": "user", "content": "What was behind me?"} in messages
    assert {"role": "assistant", "content": "A bench was behind you."} in messages
    assert messages[-1]["role"] == "user"


def test_brain_ask_json_parse_fallback():
    brain = _make_brain("this is not json at all !!!")
    result = brain.ask([], "Any hazards?")
    # Should not raise — should return the raw text
    assert isinstance(result, str)
    assert len(result) > 0
