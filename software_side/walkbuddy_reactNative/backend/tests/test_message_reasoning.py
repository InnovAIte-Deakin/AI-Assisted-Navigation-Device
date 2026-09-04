"""Tests for message_reasoning.py — rule-based detection-to-TTS conversion.

This module is deterministic and has no external dependencies (no model,
no network, no I/O), which makes it the highest-value, lowest-risk file to
cover first: every test here is a pure function call against a known input.
"""

from __future__ import annotations

import sys
from pathlib import Path

import pytest

BACKEND_DIR = Path(__file__).resolve().parents[1]
if str(BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(BACKEND_DIR))

from tts_service.message_reasoning import (
    Detection,
    ObjectType,
    calculate_proximity,
    calculate_spatial_position,
    assess_risk_level,
    format_object_name,
    generate_clear_path_message,
    generate_guidance_message,
    process_adapter_output,
    process_detections,
)
from tts_service.tts_service import RiskLevel


def make_bbox(x_min, y_min, x_max, y_max):
    return {"x_min": x_min, "y_min": y_min, "x_max": x_max, "y_max": y_max}


def make_detection(category="table", confidence=0.8, bbox=None, **kwargs):
    return Detection(
        category=category,
        confidence=confidence,
        bbox=bbox or make_bbox(280, 200, 360, 280),  # centered, small
        **kwargs,
    )


class TestCalculateSpatialPosition:
    def test_center_box_is_ahead(self):
        bbox = make_bbox(280, 0, 360, 100)  # center_x = 320, image_width = 640
        assert calculate_spatial_position(bbox, image_width=640) == "ahead"

    def test_left_third_box_is_left(self):
        bbox = make_bbox(0, 0, 100, 100)  # center_x = 50
        assert calculate_spatial_position(bbox, image_width=640) == "left"

    def test_right_third_box_is_right(self):
        bbox = make_bbox(550, 0, 640, 100)  # center_x = 595
        assert calculate_spatial_position(bbox, image_width=640) == "right"

    def test_exact_left_threshold_is_not_left(self):
        # center_x exactly at image_width/3 is not "< threshold", so it's "ahead".
        bbox = make_bbox(0, 0, 427, 0)  # center_x = 213.5, threshold = 213.33
        assert calculate_spatial_position(bbox, image_width=640) == "ahead"


class TestCalculateProximity:
    def test_large_bbox_is_nearby(self):
        # 300x300 = 90000 area on a 640x480 = 307200 image -> ~29% > 10%.
        bbox = make_bbox(0, 0, 300, 300)
        assert calculate_proximity(bbox, image_width=640, image_height=480) == "nearby"

    def test_small_bbox_is_ahead(self):
        bbox = make_bbox(0, 0, 20, 20)  # 400 / 307200 ~= 0.13%
        assert calculate_proximity(bbox, image_width=640, image_height=480) == "ahead"

    def test_exactly_ten_percent_is_not_nearby(self):
        # area_ratio must be strictly > 0.10, not >=.
        image_area = 640 * 480
        side = int(image_area * 0.10) ** 0.5
        bbox = make_bbox(0, 0, int(side), int(side))
        assert calculate_proximity(bbox, image_width=640, image_height=480) == "ahead"


class TestAssessRiskLevel:
    def test_obstacle_far_high_confidence_is_medium(self):
        risk = assess_risk_level(ObjectType.OBSTACLE, confidence=0.9, proximity="ahead")
        assert risk == RiskLevel.MEDIUM

    def test_sign_far_high_confidence_is_low(self):
        risk = assess_risk_level(ObjectType.SIGN, confidence=0.9, proximity="ahead")
        assert risk == RiskLevel.LOW

    def test_safe_object_is_clear(self):
        risk = assess_risk_level(ObjectType.SAFE, confidence=0.9, proximity="ahead")
        assert risk == RiskLevel.CLEAR

    def test_obstacle_nearby_escalates_to_high(self):
        risk = assess_risk_level(ObjectType.OBSTACLE, confidence=0.9, proximity="nearby")
        assert risk == RiskLevel.HIGH

    def test_approaching_forces_at_least_high(self):
        # SAFE (CLEAR) + approaching must still jump to HIGH.
        risk = assess_risk_level(ObjectType.SAFE, confidence=0.9, proximity="ahead", approaching=True)
        assert risk == RiskLevel.HIGH

    def test_low_confidence_bumps_risk_by_one_level(self):
        risk = assess_risk_level(ObjectType.SIGN, confidence=0.2, proximity="ahead")
        assert risk == RiskLevel.MEDIUM  # LOW -> MEDIUM due to low confidence

    def test_low_confidence_never_exceeds_high(self):
        # OBSTACLE + nearby is already HIGH; low confidence must not push to CRITICAL.
        risk = assess_risk_level(ObjectType.OBSTACLE, confidence=0.1, proximity="nearby")
        assert risk == RiskLevel.HIGH


class TestFormatObjectName:
    def test_approved_class_uses_contract_spoken_name(self):
        # "chair" is an approved MVP class; its spoken name comes from ml_contract.
        assert format_object_name("chair") == "chair"

    def test_approved_class_alias_resolves_via_contract(self):
        assert format_object_name("office-chair") == "chair"

    def test_legacy_exit_gets_sign_suffix(self):
        assert format_object_name("EXIT") == "exit sign"

    def test_legacy_entrance_gets_sign_suffix(self):
        assert format_object_name("Entrance") == "entrance sign"

    def test_unrecognized_category_is_lowercased_as_is(self):
        assert format_object_name("Whiteboard") == "whiteboard"


class TestGenerateGuidanceMessage:
    def test_ahead_far_message(self):
        d = make_detection(category="table", confidence=0.9, bbox=make_bbox(280, 0, 360, 20))
        msg = generate_guidance_message(d, image_width=640, image_height=480)
        assert msg.message == "table ahead"

    def test_left_nearby_message(self):
        d = make_detection(category="table", confidence=0.9, bbox=make_bbox(0, 0, 300, 300))
        msg = generate_guidance_message(d, image_width=640, image_height=480)
        assert msg.message == "table on your left, nearby"

    def test_approaching_ahead_overrides_position_phrasing(self):
        d = make_detection(
            category="person",
            confidence=0.9,
            bbox=make_bbox(280, 0, 360, 20),
            approaching=True,
        )
        msg = generate_guidance_message(d, image_width=640, image_height=480)
        assert msg.message == "person approaching ahead"

    def test_moving_toward_center_message(self):
        d = make_detection(
            category="table",
            confidence=0.9,
            bbox=make_bbox(280, 0, 360, 20),
            is_moving=True,
            motion_direction="toward_center",
        )
        msg = generate_guidance_message(d, image_width=640, image_height=480)
        assert msg.message == "table moving into your path"

    def test_priority_scales_with_risk_and_confidence(self):
        low_conf = make_detection(category="table", confidence=0.5, bbox=make_bbox(280, 0, 360, 20))
        high_conf = make_detection(category="table", confidence=0.95, bbox=make_bbox(280, 0, 360, 20))
        low_msg = generate_guidance_message(low_conf, image_width=640, image_height=480)
        high_msg = generate_guidance_message(high_conf, image_width=640, image_height=480)
        assert high_msg.priority > low_msg.priority
        assert low_msg.risk_level == high_msg.risk_level  # same risk tier, confidence differs


class TestProcessDetections:
    def test_low_confidence_detections_are_skipped(self):
        detections = [make_detection(confidence=0.1)]
        assert process_detections(detections) == []

    def test_sorted_by_priority_highest_first(self):
        low_risk = make_detection(category="book", confidence=0.9, bbox=make_bbox(280, 0, 360, 20))
        high_risk = make_detection(category="stairs", confidence=0.9, bbox=make_bbox(280, 0, 360, 20))
        messages = process_detections([low_risk, high_risk], max_messages=2)
        assert messages[0].risk_level.value >= messages[1].risk_level.value

    def test_max_messages_truncates_output(self):
        detections = [make_detection(category="table", bbox=make_bbox(280, 0, 360, 20)) for _ in range(5)]
        messages = process_detections(detections, max_messages=2)
        assert len(messages) == 2


class TestProcessAdapterOutput:
    def test_extracts_detections_from_dict(self):
        adapter_output = {
            "detections": [
                {"category": "table", "confidence": 0.9, "bbox": make_bbox(280, 0, 360, 20)},
            ]
        }
        messages = process_adapter_output(adapter_output)
        assert len(messages) == 1
        assert "table" in messages[0].message

    def test_uses_image_shape_from_metadata_when_present(self):
        # A tiny declared image_shape makes the same bbox proportionally huge,
        # i.e. "nearby" — proving the metadata dimensions are actually used.
        adapter_output = {
            "detections": [
                {"category": "table", "confidence": 0.9, "bbox": make_bbox(0, 0, 50, 50)},
            ],
            "metadata": {"image_shape": [60, 60]},
        }
        messages = process_adapter_output(adapter_output)
        assert "nearby" in messages[0].message

    def test_empty_detections_returns_empty_list(self):
        assert process_adapter_output({"detections": []}) == []


def test_generate_clear_path_message():
    msg = generate_clear_path_message()
    assert msg.risk_level == RiskLevel.CLEAR
    assert msg.priority == 0
    assert "clear" in msg.message.lower()
