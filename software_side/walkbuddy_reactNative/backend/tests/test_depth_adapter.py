from adapters import depth_adapter


def _detections():
    return [
        {
            "category": "table",
            "confidence": 0.91,
            "bbox": {
                "x_min": 100,
                "y_min": 120,
                "x_max": 400,
                "y_max": 460,
            },
            "direction": "ahead",
            "priority": "MEDIUM",
        }
    ]


def test_depth_enrichment_success(monkeypatch):
    def fake_estimate_depth(image_path, bounding_boxes):
        assert image_path == "frame.jpg"
        assert bounding_boxes == [
            {
                "x_min": 100,
                "y_min": 120,
                "x_max": 400,
                "y_max": 460,
            }
        ]

        return {
            "boxes": [
                {
                    "bbox": bounding_boxes[0],
                    "improved_depth_score": 0.625,
                }
            ]
        }

    monkeypatch.setattr(depth_adapter, "estimate_depth", fake_estimate_depth)

    detections = _detections()

    result = depth_adapter.enrich_detections_with_depth(
        "frame.jpg",
        detections,
    )

    assert result[0]["relative_depth"] == 0.625


def test_depth_enrichment_failure_falls_back(monkeypatch):
    def broken_estimator(image_path, bounding_boxes):
        raise RuntimeError("depth failed")

    monkeypatch.setattr(depth_adapter, "estimate_depth", broken_estimator)

    detections = _detections()

    result = depth_adapter.enrich_detections_with_depth(
        "frame.jpg",
        detections,
    )

    assert result[0]["relative_depth"] is None
    assert result[0]["category"] == "table"
    assert result[0]["confidence"] == 0.91
    
def test_depth_enrichment_unavailable_falls_back(monkeypatch):
    monkeypatch.setattr(depth_adapter, "estimate_depth", None)

    detections = _detections()

    result = depth_adapter.enrich_detections_with_depth(
        "frame.jpg",
        detections,
    )

    assert result[0]["relative_depth"] is None
    assert result[0]["category"] == "table"