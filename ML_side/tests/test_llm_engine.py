"""
Unit Tests — Hybrid LLM Reasoning Engine (rule-based tier only)
Run: pytest tests/test_llm_engine.py -v
No Ollama or OpenAI key required.
"""

import pytest
import sys, os
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "src")))

from llm_integration.llm_reasoning_engine import LLMNavigationReasoner, _rule_based_fallback


def det(name, priority, position="center", confidence=0.85):
    return {"class_name": name, "priority": priority, "frame_position": position,
            "confidence": confidence, "priority_label": {5:"CRITICAL",4:"HIGH",3:"MEDIUM",2:"LOW",1:"MINIMAL"}[priority]}


SPATIAL = {"scene_density": "moderate", "object_count": 2}


class TestRuleBasedFallback:

    def test_empty_returns_clear_path(self):
        msg = _rule_based_fallback([], SPATIAL)
        assert "clear" in msg.lower()

    def test_critical_returns_stop(self):
        msg = _rule_based_fallback([det("stairs", 5)], SPATIAL)
        assert "stop" in msg.lower()

    def test_high_returns_caution(self):
        msg = _rule_based_fallback([det("person", 4)], SPATIAL)
        assert "caution" in msg.lower()

    def test_medium_mentions_object(self):
        msg = _rule_based_fallback([det("door", 3)], SPATIAL)
        assert "door" in msg.lower()

    def test_minimal_returns_proceed(self):
        msg = _rule_based_fallback([det("book", 1)], SPATIAL)
        assert "proceed" in msg.lower() or "clear" in msg.lower()


class TestLLMReasoner:

    def test_initialises_in_rule_based_mode(self):
        r = LLMNavigationReasoner(mode="rule-based")
        assert r.mode == "rule-based"

    def test_invalid_mode_defaults_to_hybrid(self):
        r = LLMNavigationReasoner(mode="nonsense")
        assert r.mode == "hybrid"

    def test_rule_based_returns_result(self):
        r = LLMNavigationReasoner(mode="rule-based")
        result = r.reason_about_navigation(
            [det("stairs", 5, "center")], SPATIAL
        )
        assert "direction" in result
        assert "safety_level" in result
        assert result["llm_tier"] == "rule-based"

    def test_stairs_gives_high_safety(self):
        r = LLMNavigationReasoner(mode="rule-based")
        result = r.reason_about_navigation([det("stairs", 5)], SPATIAL)
        assert result["safety_level"] == "High"

    def test_book_gives_low_safety(self):
        r = LLMNavigationReasoner(mode="rule-based")
        result = r.reason_about_navigation([det("book", 1)], SPATIAL)
        assert result["safety_level"] == "Low"

    def test_empty_detections_handled(self):
        r = LLMNavigationReasoner(mode="rule-based")
        result = r.reason_about_navigation([], SPATIAL)
        assert result["direction"] != ""

    def test_latency_recorded(self):
        r = LLMNavigationReasoner(mode="rule-based")
        result = r.reason_about_navigation([det("monitor", 1)], SPATIAL)
        assert result["latency_ms"] >= 0

    def test_backward_compat_model_type_param(self):
        r = LLMNavigationReasoner(model_type="openai")
        assert r.mode == "hybrid"
