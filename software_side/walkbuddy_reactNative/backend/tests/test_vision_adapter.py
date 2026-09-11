"""Tests for adapters/vision_adapter.py's own logic.

get_priority() already has direct coverage (test_navigation_semantics.py::
test_vision_priority_consumer_uses_the_agreed_contract), and the endpoint
layer is tested with vision_adapter() faked out entirely (test_ml_runtime.py,
test_ml_inference*.py). Neither exercises vision_adapter()'s own function
body — bbox construction, direction/priority integration, sort order, and
image-dimension handling — so that's what this file covers, using a fake
YOLO model instead of a real one.
"""
from pathlib import Path
import sys

import cv2
import numpy as np
import pytest

BACKEND_DIR = Path(__file__).resolve().parents[1]
if str(BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(BACKEND_DIR))

from adapters.vision_adapter import vision_adapter  # noqa: E402


class _Array(list):
    """box.xyxy[0] is a tensor in real Ultralytics output; only .tolist() is
    actually used, so a list that knows how to give itself back is enough."""

    def tolist(self):
        return list(self)


class FakeBox:
    def __init__(self, x1, y1, x2, y2, conf, cls_id):
        self.xyxy = [_Array([x1, y1, x2, y2])]
        self.conf = [conf]
        self.cls = [cls_id]


class FakeResult:
    def __init__(self, boxes, names, orig_shape=(480, 640)):
        self.boxes = boxes
        self.names = names
        self.orig_shape = orig_shape


class FakeModel:
    """Stands in for ultralytics.YOLO — vision_adapter() only ever calls
    model.predict(...) and reads the first result."""

    def __init__(self, boxes=(), names=None, orig_shape=(480, 640)):
        self.result = FakeResult(list(boxes), names or {}, orig_shape)

    def predict(self, **_kwargs):
        return [self.result]


def write_image(path: Path, size=(200, 100), color=(128, 128, 128)):
    """size is (width, height), matching how the app talks about images."""
    path.parent.mkdir(parents=True, exist_ok=True)
    width, height = size
    img = np.full((height, width, 3), color, dtype=np.uint8)
    cv2.imwrite(str(path), img)


def test_no_detections_returns_empty_list(tmp_path):
    image_path = tmp_path / "empty.jpg"
    write_image(image_path)
    model = FakeModel(boxes=[], names={})

    result = vision_adapter(model, str(image_path))

    assert result["detections"] == []


def test_single_detection_has_all_expected_fields(tmp_path):
    image_path = tmp_path / "frame.jpg"
    write_image(image_path, size=(300, 150))
    box = FakeBox(10, 20, 60, 80, conf=0.876543, cls_id=0)
    model = FakeModel(boxes=[box], names={0: "stairs"})

    result = vision_adapter(model, str(image_path))

    assert len(result["detections"]) == 1
    detection = result["detections"][0]
    assert detection["category"] == "stairs"
    assert detection["confidence"] == 0.877  # rounded to 3 decimals
    assert detection["bbox"] == {"x_min": 10, "y_min": 20, "x_max": 60, "y_max": 80}
    assert detection["priority"] == "CRITICAL"
    assert detection["direction"] in {"left", "ahead", "right"}


@pytest.mark.parametrize("label,expected_priority", [
    ("stairs", "CRITICAL"),
    ("vehicle", "CRITICAL"),
    ("person", "HIGH"),
    ("door", "MEDIUM"),
    ("office-chair", "MEDIUM"),  # alias for "chair" in the navigation contract
    ("some-legacy-label", "LOW"),  # unrecognized: falls back to LOW, not an error
])
def test_priority_comes_from_the_navigation_contract(tmp_path, label, expected_priority):
    image_path = tmp_path / "frame.jpg"
    write_image(image_path, size=(300, 150))
    box = FakeBox(0, 0, 50, 50, conf=0.9, cls_id=0)
    model = FakeModel(boxes=[box], names={0: label})

    result = vision_adapter(model, str(image_path))

    assert result["detections"][0]["priority"] == expected_priority


def test_direction_uses_the_bbox_center_against_image_thirds(tmp_path):
    image_path = tmp_path / "frame.jpg"
    write_image(image_path, size=(300, 150))  # thirds at x=100 and x=200
    left_box = FakeBox(0, 0, 20, 20, conf=0.9, cls_id=0)     # center x = 10
    ahead_box = FakeBox(130, 0, 170, 20, conf=0.9, cls_id=0)  # center x = 150
    right_box = FakeBox(280, 0, 300, 20, conf=0.9, cls_id=0)  # center x = 290
    model = FakeModel(boxes=[left_box, ahead_box, right_box], names={0: "door"})

    result = vision_adapter(model, str(image_path))

    # Equal priority and confidence across all three, so the sort is stable
    # and insertion order (left, ahead, right) is preserved.
    directions = [d["direction"] for d in result["detections"]]
    assert directions == ["left", "ahead", "right"]


def test_detections_are_sorted_by_severity_then_confidence(tmp_path):
    image_path = tmp_path / "frame.jpg"
    write_image(image_path, size=(300, 150))
    # Deliberately out of order, and a low-confidence CRITICAL should still
    # outrank a high-confidence MEDIUM.
    medium_high_conf = FakeBox(0, 0, 20, 20, conf=0.95, cls_id=0)
    critical_low_conf = FakeBox(0, 0, 20, 20, conf=0.30, cls_id=1)
    high_mid_conf = FakeBox(0, 0, 20, 20, conf=0.60, cls_id=2)
    model = FakeModel(
        boxes=[medium_high_conf, critical_low_conf, high_mid_conf],
        names={0: "door", 1: "stairs", 2: "person"},
    )

    result = vision_adapter(model, str(image_path))

    categories = [d["category"] for d in result["detections"]]
    assert categories == ["stairs", "person", "door"]


def test_equal_priority_breaks_ties_by_confidence_descending(tmp_path):
    image_path = tmp_path / "frame.jpg"
    write_image(image_path, size=(300, 150))
    box_a = FakeBox(0, 0, 20, 20, conf=0.4, cls_id=0)
    box_b = FakeBox(0, 0, 20, 20, conf=0.9, cls_id=0)
    model = FakeModel(boxes=[box_a, box_b], names={0: "person"})

    result = vision_adapter(model, str(image_path))

    confidences = [d["confidence"] for d in result["detections"]]
    assert confidences == [0.9, 0.4]


def test_image_dimensions_come_from_the_loaded_image_not_the_model_result(tmp_path):
    # vision_adapter() re-derives dimensions from cv2.imread whenever the
    # image loads successfully, regardless of what the model reported as
    # orig_shape — this locks in that (possibly surprising) current behavior.
    image_path = tmp_path / "frame.jpg"
    write_image(image_path, size=(300, 150))  # actual: width=300, height=150
    model = FakeModel(boxes=[], names={}, orig_shape=(999, 999))

    result = vision_adapter(model, str(image_path))

    assert result["metadata"]["image_shape"] == [150, 300]  # [height, width]


def test_falls_back_to_640x480_when_the_image_cannot_be_loaded(tmp_path):
    # A path the fake model is happy to "detect" in, but that doesn't exist
    # on disk for cv2.imread to actually read.
    missing_path = tmp_path / "does_not_exist.jpg"
    model = FakeModel(boxes=[], names={})

    result = vision_adapter(model, str(missing_path))

    assert result["metadata"]["image_shape"] == [480, 640]


def test_image_id_uses_the_file_stem(tmp_path):
    image_path = tmp_path / "frame_007.jpg"
    write_image(image_path)
    model = FakeModel(boxes=[], names={})

    result = vision_adapter(model, str(image_path))

    assert result["image_id"] == "frame_007"
