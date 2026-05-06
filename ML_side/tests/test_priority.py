"""
Unit Tests — Object Priority Assignment System
Issue: Sprint 2 / bravine6
Run: pytest ML_side/tests/test_priority.py -v
"""

import pytest

# ── Priority config (mirrors navigation_pipeline.py) ──────────────────────────

OBJECT_PRIORITY = {
    "stairs":            5,
    "emergency-exit":    5,
    "person":            4,
    "fire-extinguisher": 4,
    "door":              3,
    "elevator":          3,
    "handrail":          3,
    "signage":           2,
    "whiteboard":        2,
    "tv":                2,
    "book":              1,
    "books":             1,
    "monitor":           1,
    "office-chair":      1,
    "table":             1,
}

PRIORITY_LABELS = {5: "CRITICAL", 4: "HIGH", 3: "MEDIUM", 2: "LOW", 1: "MINIMAL"}

PRIORITY_COLOURS = {
    5: (0,   0,   255),
    4: (0,   128, 255),
    3: (0,   255, 255),
    2: (0,   255, 128),
    1: (0,   255,   0),
}


def get_priority(class_name):
    p = OBJECT_PRIORITY.get(class_name, 1)
    return p, PRIORITY_LABELS[p]


def make_detection(class_name, confidence=0.8, position="center"):
    p, lbl = get_priority(class_name)
    return {
        "class_name": class_name,
        "confidence": confidence,
        "position": position,
        "priority": p,
        "priority_label": lbl,
    }


def sort_by_priority(detections):
    return sorted(detections, key=lambda d: d["priority"], reverse=True)


def navigation_decision(detections):
    """Mirrors _basic_navigation_reasoning logic."""
    if not detections:
        return "proceed", "Low", None
    top = detections[0]
    if top["priority"] == 5:
        return "stop", "High", top
    elif top["priority"] == 4:
        return "caution", "High", top
    elif top["priority"] == 3:
        return "aware", "Medium", top
    else:
        return "proceed", "Low", top


# ── Tests: Priority Values ─────────────────────────────────────────────────────

class TestPriorityValues:

    def test_stairs_is_critical(self):
        p, lbl = get_priority("stairs")
        assert p == 5
        assert lbl == "CRITICAL"

    def test_emergency_exit_is_critical(self):
        p, lbl = get_priority("emergency-exit")
        assert p == 5
        assert lbl == "CRITICAL"

    def test_person_is_high(self):
        p, lbl = get_priority("person")
        assert p == 4
        assert lbl == "HIGH"

    def test_fire_extinguisher_is_high(self):
        p, lbl = get_priority("fire-extinguisher")
        assert p == 4
        assert lbl == "HIGH"

    def test_door_is_medium(self):
        p, lbl = get_priority("door")
        assert p == 3
        assert lbl == "MEDIUM"

    def test_elevator_is_medium(self):
        p, lbl = get_priority("elevator")
        assert p == 3
        assert lbl == "MEDIUM"

    def test_handrail_is_medium(self):
        p, lbl = get_priority("handrail")
        assert p == 3
        assert lbl == "MEDIUM"

    def test_signage_is_low(self):
        p, lbl = get_priority("signage")
        assert p == 2
        assert lbl == "LOW"

    def test_book_is_minimal(self):
        p, lbl = get_priority("book")
        assert p == 1
        assert lbl == "MINIMAL"

    def test_monitor_is_minimal(self):
        p, lbl = get_priority("monitor")
        assert p == 1
        assert lbl == "MINIMAL"

    def test_office_chair_is_minimal(self):
        p, lbl = get_priority("office-chair")
        assert p == 1
        assert lbl == "MINIMAL"

    def test_unknown_class_defaults_to_minimal(self):
        p, lbl = get_priority("unknown-object")
        assert p == 1
        assert lbl == "MINIMAL"

    def test_all_15_classes_have_priority(self):
        for cls in OBJECT_PRIORITY:
            p, _ = get_priority(cls)
            assert 1 <= p <= 5, f"{cls} has invalid priority {p}"


# ── Tests: Sorting ─────────────────────────────────────────────────────────────

class TestPrioritySorting:

    def test_sorted_highest_first(self):
        detections = [
            make_detection("book"),
            make_detection("stairs"),
            make_detection("door"),
        ]
        sorted_dets = sort_by_priority(detections)
        assert sorted_dets[0]["class_name"] == "stairs"
        assert sorted_dets[-1]["class_name"] == "book"

    def test_critical_always_first(self):
        detections = [
            make_detection("monitor"),
            make_detection("person"),
            make_detection("emergency-exit"),
            make_detection("whiteboard"),
        ]
        sorted_dets = sort_by_priority(detections)
        assert sorted_dets[0]["priority"] == 5

    def test_equal_priority_preserves_both(self):
        detections = [
            make_detection("stairs"),
            make_detection("emergency-exit"),
        ]
        sorted_dets = sort_by_priority(detections)
        priorities = [d["priority"] for d in sorted_dets]
        assert priorities == [5, 5]

    def test_single_detection_returns_correctly(self):
        detections = [make_detection("table")]
        sorted_dets = sort_by_priority(detections)
        assert len(sorted_dets) == 1
        assert sorted_dets[0]["class_name"] == "table"

    def test_empty_detections(self):
        assert sort_by_priority([]) == []


# ── Tests: Navigation Decision ─────────────────────────────────────────────────

class TestNavigationDecision:

    def test_stairs_triggers_stop(self):
        detections = sort_by_priority([make_detection("stairs")])
        direction, safety, _ = navigation_decision(detections)
        assert direction == "stop"
        assert safety == "High"

    def test_emergency_exit_triggers_stop(self):
        detections = sort_by_priority([make_detection("emergency-exit")])
        direction, safety, _ = navigation_decision(detections)
        assert direction == "stop"
        assert safety == "High"

    def test_person_triggers_caution(self):
        detections = sort_by_priority([make_detection("person")])
        direction, safety, _ = navigation_decision(detections)
        assert direction == "caution"
        assert safety == "High"

    def test_door_triggers_aware(self):
        detections = sort_by_priority([make_detection("door")])
        direction, safety, _ = navigation_decision(detections)
        assert direction == "aware"
        assert safety == "Medium"

    def test_book_triggers_proceed(self):
        detections = sort_by_priority([make_detection("book")])
        direction, safety, _ = navigation_decision(detections)
        assert direction == "proceed"
        assert safety == "Low"

    def test_empty_scene_triggers_proceed(self):
        direction, safety, top = navigation_decision([])
        assert direction == "proceed"
        assert top is None

    def test_stairs_overrides_book_in_mixed_scene(self):
        detections = sort_by_priority([
            make_detection("book"),
            make_detection("stairs"),
            make_detection("monitor"),
        ])
        direction, safety, top = navigation_decision(detections)
        assert direction == "stop"
        assert top["class_name"] == "stairs"

    def test_person_overrides_furniture(self):
        detections = sort_by_priority([
            make_detection("table"),
            make_detection("person"),
            make_detection("whiteboard"),
        ])
        direction, _, top = navigation_decision(detections)
        assert direction == "caution"
        assert top["class_name"] == "person"


# ── Tests: Colour Coding ───────────────────────────────────────────────────────

class TestColourCoding:

    def test_critical_is_red(self):
        assert PRIORITY_COLOURS[5] == (0, 0, 255)

    def test_high_is_orange(self):
        assert PRIORITY_COLOURS[4] == (0, 128, 255)

    def test_minimal_is_green(self):
        assert PRIORITY_COLOURS[1] == (0, 255, 0)

    def test_all_priorities_have_colour(self):
        for p in range(1, 6):
            assert p in PRIORITY_COLOURS
