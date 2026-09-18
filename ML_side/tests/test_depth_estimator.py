from pathlib import Path

import numpy as np
import pytest

from depth.depth_estimator import (
    baseline_depth_score,
    estimate_depth,
    improved_depth_score,
)


def test_baseline_depth_score_matches_notebook_formula():
    assert baseline_depth_score(120, 480) == pytest.approx(0.25)


def test_improved_depth_score_matches_notebook_formula():
    score = improved_depth_score(120, 300, 480, alpha=0.7, beta=0.3)
    expected = 0.7 * (120 / 480) + 0.3 * (300 / 480)
    assert score == pytest.approx(expected)


def test_estimate_depth_accepts_numpy_image_and_mapping_boxes():
    image = np.zeros((480, 640, 3), dtype=np.uint8)
    result = estimate_depth(
        image,
        bounding_boxes=[{"x_min": 10, "y_min": 50, "x_max": 110, "y_max": 290}],
    )

    assert result["image_height"] == 480
    assert result["image_width"] == 640
    assert result["unit"] == "relative_depth_score"
    assert result["depth_map"] is None
    assert len(result["boxes"]) == 1
    assert result["boxes"][0]["baseline_depth_score"] == pytest.approx(240 / 480)


def test_estimate_depth_accepts_sequence_boxes():
    image = np.zeros((200, 300), dtype=np.uint8)
    result = estimate_depth(image, bounding_boxes=[(5, 20, 25, 120)])

    assert result["boxes"][0]["bbox"] == {
        "x_min": 5,
        "y_min": 20,
        "x_max": 25,
        "y_max": 120,
    }


def test_estimate_depth_supports_png_file_paths():
    repo_root = Path(__file__).resolve().parents[2]
    image_path = repo_root / "ML_side" / "testing_pipeline" / "test_assets" / "test.png"

    result = estimate_depth(
        image_path,
        bounding_boxes=[{"x_min": 0, "y_min": 0, "x_max": 100, "y_max": 200}],
    )

    assert result["image_height"] > 0
    assert result["image_width"] > 0
    assert result["boxes"][0]["improved_depth_score"] > 0


def test_estimate_depth_returns_empty_boxes_when_none_supplied():
    image = np.zeros((100, 150, 3), dtype=np.uint8)
    result = estimate_depth(image)
    assert result["boxes"] == []


def test_estimate_depth_rejects_invalid_array_shape():
    with pytest.raises(ValueError, match="at least 2 dimensions"):
        estimate_depth(np.array([1, 2, 3]))


def test_estimate_depth_rejects_missing_box_keys():
    image = np.zeros((100, 150, 3), dtype=np.uint8)
    with pytest.raises(ValueError, match="x_min"):
        estimate_depth(image, bounding_boxes=[{"x_min": 1, "y_min": 2, "x_max": 5}])


def test_estimate_depth_rejects_invalid_box_geometry():
    image = np.zeros((100, 150, 3), dtype=np.uint8)
    with pytest.raises(ValueError, match="positive width and height"):
        estimate_depth(image, bounding_boxes=[(10, 20, 10, 30)])
