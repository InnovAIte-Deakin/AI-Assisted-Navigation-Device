"""Tests for adapters/ocr_adapter.py.

ocr_adapter() takes its EasyOCR `reader` as a dependency-injected argument,
so these tests use a small fake reader instead of the real (heavy) EasyOCR
engine — no model download or GPU needed.
"""
from pathlib import Path
import sys

import cv2
import numpy as np
import pytest

BACKEND_DIR = Path(__file__).resolve().parents[1]
if str(BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(BACKEND_DIR))

from adapters.ocr_adapter import ocr_adapter, _convert_4corners_to_bbox  # noqa: E402


class FakeReader:
    """Stands in for easyocr.Reader. `readtext_result` and `raise_cv2_error`
    are set by each test to control what the fake OCR engine reports."""

    def __init__(self, readtext_result=None, raise_cv2_error=False):
        self.readtext_result = readtext_result or []
        self.raise_cv2_error = raise_cv2_error
        self.seen_image_shape = None

    def readtext(self, img):
        self.seen_image_shape = img.shape
        if self.raise_cv2_error:
            raise cv2.error("synthetic EasyOCR crop error")
        return self.readtext_result


def write_image(path: Path, size=(200, 100), color=(128, 128, 128)):
    path.parent.mkdir(parents=True, exist_ok=True)
    img = np.full((size[1], size[0], 3), color, dtype=np.uint8)
    cv2.imwrite(str(path), img)


def box(x_min, y_min, x_max, y_max):
    """EasyOCR reports boxes as 4 (x, y) corners, clockwise from top-left."""
    return [[x_min, y_min], [x_max, y_min], [x_max, y_max], [x_min, y_max]]


def test_missing_file_raises_file_not_found(tmp_path):
    with pytest.raises(FileNotFoundError):
        ocr_adapter(FakeReader(), str(tmp_path / "does_not_exist.jpg"))


def test_unreadable_image_returns_empty_detections(tmp_path):
    # A .jpg extension but not actually image bytes — cv2.imread returns None for this.
    bad_path = tmp_path / "not_really_an_image.jpg"
    bad_path.write_bytes(b"this is not image data")

    result = ocr_adapter(FakeReader(), str(bad_path))

    assert result == {"image_id": "not_really_an_image", "detections": []}


def test_low_confidence_text_is_filtered_out(tmp_path):
    image_path = tmp_path / "sign.jpg"
    write_image(image_path)
    reader = FakeReader(readtext_result=[
        (box(0, 0, 50, 20), "keep me", 0.9),
        (box(0, 30, 50, 50), "drop me", 0.24),  # just under the 0.25 threshold
    ])

    result = ocr_adapter(reader, str(image_path))

    categories = [d["category"] for d in result["detections"]]
    assert categories == ["keep me"]


def test_confidence_exactly_at_threshold_is_kept(tmp_path):
    image_path = tmp_path / "sign.jpg"
    write_image(image_path)
    reader = FakeReader(readtext_result=[(box(0, 0, 50, 20), "borderline", 0.25)])

    result = ocr_adapter(reader, str(image_path))

    assert [d["category"] for d in result["detections"]] == ["borderline"]


def test_whitespace_only_text_is_filtered_out(tmp_path):
    image_path = tmp_path / "sign.jpg"
    write_image(image_path)
    reader = FakeReader(readtext_result=[(box(0, 0, 50, 20), "   ", 0.9)])

    result = ocr_adapter(reader, str(image_path))

    assert result["detections"] == []


def test_text_is_stripped_of_surrounding_whitespace(tmp_path):
    image_path = tmp_path / "sign.jpg"
    write_image(image_path)
    reader = FakeReader(readtext_result=[(box(0, 0, 50, 20), "  EXIT  ", 0.9)])

    result = ocr_adapter(reader, str(image_path))

    assert result["detections"][0]["category"] == "EXIT"


def test_detections_are_sorted_top_to_bottom_for_reading_order(tmp_path):
    image_path = tmp_path / "sign.jpg"
    write_image(image_path)
    # Deliberately out of order: bottom line first, then top, then middle.
    reader = FakeReader(readtext_result=[
        (box(0, 80, 50, 100), "third line", 0.9),
        (box(0, 0, 50, 20), "first line", 0.9),
        (box(0, 40, 50, 60), "second line", 0.9),
    ])

    result = ocr_adapter(reader, str(image_path))

    assert [d["category"] for d in result["detections"]] == [
        "first line", "second line", "third line",
    ]


def test_bbox_is_converted_from_four_corners_to_min_max_form():
    corners = box(10, 20, 110, 220)

    bbox = _convert_4corners_to_bbox(corners)

    assert bbox == {"x_min": 10, "y_min": 20, "x_max": 110, "y_max": 220}


def test_detection_bbox_uses_min_max_conversion(tmp_path):
    image_path = tmp_path / "sign.jpg"
    write_image(image_path)
    reader = FakeReader(readtext_result=[(box(5, 6, 55, 26), "hello", 0.9)])

    result = ocr_adapter(reader, str(image_path))

    assert result["detections"][0]["bbox"] == {
        "x_min": 5, "y_min": 6, "x_max": 55, "y_max": 26,
    }


def test_large_image_is_downscaled_before_being_passed_to_the_reader(tmp_path):
    image_path = tmp_path / "big.jpg"
    write_image(image_path, size=(2048, 1024))  # longer side well over the 1024px cap
    reader = FakeReader(readtext_result=[])

    ocr_adapter(reader, str(image_path))

    seen_h, seen_w = reader.seen_image_shape[:2]
    assert max(seen_h, seen_w) <= 1024


def test_small_image_is_not_resized(tmp_path):
    image_path = tmp_path / "small.jpg"
    write_image(image_path, size=(200, 100))
    reader = FakeReader(readtext_result=[])

    ocr_adapter(reader, str(image_path))

    assert reader.seen_image_shape[:2] == (100, 200)


def test_cv2_error_during_readtext_is_handled_and_returns_empty(tmp_path):
    image_path = tmp_path / "sign.jpg"
    write_image(image_path)
    reader = FakeReader(raise_cv2_error=True)

    result = ocr_adapter(reader, str(image_path))

    assert result["detections"] == []


def test_image_id_uses_the_file_stem(tmp_path):
    image_path = tmp_path / "receipt_042.jpg"
    write_image(image_path)

    result = ocr_adapter(FakeReader(), str(image_path))

    assert result["image_id"] == "receipt_042"
