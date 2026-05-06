"""
Integration Tests — FastAPI ML Navigation Service
Issue: Sprint 2 / bravine6
Run: pytest ML_side/tests/test_api.py -v
Requires: pip install httpx pytest
Start API first: cd ML_side/deployment && python api.py
"""

import pytest
from fastapi.testclient import TestClient
import sys
import os

from api import app

client = TestClient(app)


# ── Tests: Health & Info ───────────────────────────────────────────────────────

class TestHealthEndpoints:

    def test_root_returns_200(self):
        r = client.get("/")
        assert r.status_code == 200

    def test_root_contains_service_name(self):
        r = client.get("/")
        assert "navigation" in r.json()["service"].lower()

    def test_health_returns_200(self):
        r = client.get("/health")
        assert r.status_code == 200

    def test_health_status_is_ok(self):
        r = client.get("/health")
        assert r.json()["status"] in ("ok", "healthy")


# ── Tests: Classes Endpoint ────────────────────────────────────────────────────

class TestClassesEndpoint:

    def test_classes_returns_200(self):
        r = client.get("/classes")
        assert r.status_code == 200

    def test_classes_returns_list(self):
        r = client.get("/classes")
        assert isinstance(r.json()["classes"], list)

    def test_classes_contains_stairs(self):
        r = client.get("/classes")
        assert "stairs" in r.json()["classes"]

    def test_classes_contains_person(self):
        r = client.get("/classes")
        assert "person" in r.json()["classes"]

    def test_classes_count_is_15(self):
        r = client.get("/classes")
        assert r.json()["total"] == 15


# ── Tests: Navigate Endpoint ───────────────────────────────────────────────────

class TestNavigateEndpoint:

    def test_navigate_returns_200(self):
        r = client.post("/navigate", json={})
        assert r.status_code == 200

    def test_navigate_contains_required_fields(self):
        r = client.post("/navigate", json={})
        body = r.json()
        for field in ["direction", "guidance", "safety_level",
                      "highest_priority_object", "highest_priority_level",
                      "highest_priority_label", "processing_time_ms"]:
            assert field in body, f"Missing field: {field}"

    def test_navigate_safety_level_is_valid(self):
        r = client.post("/navigate", json={})
        assert r.json()["safety_level"] in ("low", "medium", "high")

    def test_navigate_with_stairs_returns_stop(self):
        payload = {
            "location": "Hallway",
            "user_intent": "Find exit",
            "detections": [
                {
                    "class_name": "stairs",
                    "confidence": 0.92,
                    "position": "center",
                    "distance_estimate": "near",
                    "priority": 5,
                    "priority_label": "CRITICAL"
                }
            ]
        }
        r = client.post("/navigate", json=payload)
        body = r.json()
        assert body["direction"] == "stop"
        assert body["safety_level"] == "high"
        assert body["highest_priority_level"] == 5
        assert body["highest_priority_label"] == "CRITICAL"

    def test_navigate_stairs_overrides_book(self):
        payload = {
            "detections": [
                {"class_name": "book",   "confidence": 0.95, "position": "center",
                 "distance_estimate": "near", "priority": 1, "priority_label": "MINIMAL"},
                {"class_name": "stairs", "confidence": 0.80, "position": "right",
                 "distance_estimate": "far",  "priority": 5, "priority_label": "CRITICAL"},
            ]
        }
        r = client.post("/navigate", json=payload)
        body = r.json()
        assert body["highest_priority_object"] == "stairs"
        assert body["direction"] == "stop"

    def test_navigate_person_returns_caution(self):
        payload = {
            "detections": [
                {"class_name": "person", "confidence": 0.85, "position": "center",
                 "distance_estimate": "near", "priority": 4, "priority_label": "HIGH"}
            ]
        }
        r = client.post("/navigate", json=payload)
        body = r.json()
        assert body["direction"] == "caution"
        assert body["highest_priority_level"] == 4

    def test_navigate_processing_time_is_positive(self):
        r = client.post("/navigate", json={})
        assert r.json()["processing_time_ms"] > 0


# ── Tests: Detect Endpoint ─────────────────────────────────────────────────────

class TestDetectEndpoint:

    def test_detect_returns_200(self):
        r = client.post("/detect", json={})
        assert r.status_code == 200

    def test_detect_returns_list(self):
        r = client.post("/detect", json={})
        assert isinstance(r.json()["detections"], list)

    def test_detect_objects_have_priority_field(self):
        r = client.post("/detect", json={})
        for det in r.json()["detections"]:
            assert "priority" in det
            assert "priority_label" in det

    def test_detect_priority_label_is_valid(self):
        valid_labels = {"CRITICAL", "HIGH", "MEDIUM", "LOW", "MINIMAL"}
        r = client.post("/detect", json={})
        for det in r.json()["detections"]:
            assert det["priority_label"] in valid_labels

    def test_detect_priority_range_is_valid(self):
        r = client.post("/detect", json={})
        for det in r.json()["detections"]:
            assert 1 <= det["priority"] <= 5

    def test_detect_sorted_highest_priority_first(self):
        r = client.post("/detect", json={})
        detections = r.json()["detections"]
        if len(detections) > 1:
            priorities = [d["priority"] for d in detections]
            assert priorities == sorted(priorities, reverse=True)


# ── Tests: Demo Endpoint ───────────────────────────────────────────────────────

class TestDemoEndpoint:

    def test_demo_returns_200(self):
        r = client.get("/demo")
        assert r.status_code == 200

    def test_demo_contains_scenario(self):
        r = client.get("/demo")
        assert "scenario" in r.json()

    def test_demo_contains_navigation(self):
        r = client.get("/demo")
        assert "navigation" in r.json()
