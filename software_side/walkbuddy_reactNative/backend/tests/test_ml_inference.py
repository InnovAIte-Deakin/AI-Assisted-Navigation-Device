"""
Unit tests for the production ML inference endpoint (routers/ml_inference.py).

These tests never load real model weights. They mount only the ml_inference
router on a bare FastAPI app, set a fake `app.state.yolo` (with a `.names`
mapping) plus a real capacity limiter, and stub out `vision_adapter` so the
contract can be verified without inference.

Run from the backend directory:
    pytest tests/test_ml_inference.py -v
"""

import anyio
import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

import routers.ml_inference as ml_inference


SEVEN_CLASSES = {
    0: "book",
    1: "books",
    2: "monitor",
    3: "office-chair",
    4: "whiteboard",
    5: "table",
    6: "tv",
}

EIGHT_CLASSES = {**SEVEN_CLASSES, 7: "couch"}


class FakeYolo:
    """Minimal stand-in for an Ultralytics YOLO model.

    Only `.names` is read by the endpoint; inference is stubbed separately.
    """

    def __init__(self, names):
        self.names = names


def _fake_result():
    return {
        "image_id": "frame",
        "detections": [
            {
                "category": "table",
                "confidence": 0.91,
                "bbox": {"x_min": 100, "y_min": 120, "x_max": 400, "y_max": 460},
                "direction": "ahead",
                "priority": "HIGH",
            }
        ],
        "metadata": {"image_shape": [480, 640]},
    }


def _build_app(yolo):
    app = FastAPI()
    app.include_router(ml_inference.router)
    app.state.yolo = yolo
    app.state.vision_limiter = anyio.CapacityLimiter(1)
    return app


@pytest.fixture
def stub_adapter(monkeypatch):
    """Replace vision_adapter with a canned result (no weights, no inference)."""
    monkeypatch.setattr(ml_inference, "vision_adapter", lambda model, path: _fake_result())


# ---------------------------------------------------------------------------
# /ml/navigate — contract
# ---------------------------------------------------------------------------

def test_navigate_contract_eight_class(stub_adapter):
    client = TestClient(_build_app(FakeYolo(EIGHT_CLASSES)))
    resp = client.post(
        "/ml/navigate",
        files={"file": ("frame.jpg", b"not-a-real-jpeg", "image/jpeg")},
    )
    assert resp.status_code == 200
    body = resp.json()

    # Exact contract keys, nothing missing.
    assert set(body) == {
        "model",
        "classes",
        "detections",
        "guidance_message",
        "risk_level",
        "inference_time_ms",
        "image_id",
    }

    # classes + model are derived from app.state.yolo.names (not hardcoded).
    assert body["classes"] == [
        "book", "books", "monitor", "office-chair",
        "whiteboard", "table", "tv", "couch",
    ]
    assert body["model"] == "walkbuddy-yolo-8class"

    # Detections pass through verbatim from vision_adapter.
    assert body["detections"] == _fake_result()["detections"]
    assert body["image_id"] == "frame"
    assert isinstance(body["inference_time_ms"], int)
    assert isinstance(body["guidance_message"], str)
    assert isinstance(body["risk_level"], str) and body["risk_level"]


def test_navigate_contract_seven_class(stub_adapter):
    """Same endpoint must work unchanged for the 7-class weights."""
    client = TestClient(_build_app(FakeYolo(SEVEN_CLASSES)))
    resp = client.post(
        "/ml/navigate",
        files={"file": ("frame.jpg", b"not-a-real-jpeg", "image/jpeg")},
    )
    assert resp.status_code == 200
    body = resp.json()
    assert body["model"] == "walkbuddy-yolo-7class"
    assert body["classes"] == [
        "book", "books", "monitor", "office-chair",
        "whiteboard", "table", "tv",
    ]
    assert "couch" not in body["classes"]


def test_navigate_empty_file_short_circuits(stub_adapter):
    client = TestClient(_build_app(FakeYolo(EIGHT_CLASSES)))
    resp = client.post(
        "/ml/navigate",
        files={"file": ("frame.jpg", b"", "image/jpeg")},
    )
    assert resp.status_code == 200
    body = resp.json()
    assert body["detections"] == []
    assert body["image_id"] is None
    assert body["model"] == "walkbuddy-yolo-8class"
    assert body["classes"][0] == "book"


# ---------------------------------------------------------------------------
# /ml/navigate — 503 when model unavailable
# ---------------------------------------------------------------------------

def test_navigate_503_when_model_unavailable():
    client = TestClient(_build_app(yolo=None))
    resp = client.post(
        "/ml/navigate",
        files={"file": ("frame.jpg", b"not-a-real-jpeg", "image/jpeg")},
    )
    assert resp.status_code == 503
    assert resp.json()["detail"] == "Vision model unavailable"


# ---------------------------------------------------------------------------
# /ml/navigate — 500 on inference failure (temp file still cleaned up)
# ---------------------------------------------------------------------------

def test_navigate_500_on_adapter_error(monkeypatch):
    def _boom(model, path):
        raise RuntimeError("cuda exploded")

    monkeypatch.setattr(ml_inference, "vision_adapter", _boom)
    client = TestClient(_build_app(FakeYolo(EIGHT_CLASSES)))
    resp = client.post(
        "/ml/navigate",
        files={"file": ("frame.jpg", b"not-a-real-jpeg", "image/jpeg")},
    )
    assert resp.status_code == 500
    assert resp.json()["detail"] == "Vision processing failed"


# ---------------------------------------------------------------------------
# /ml/model-info
# ---------------------------------------------------------------------------

def test_model_info_reports_active_classes():
    client = TestClient(_build_app(FakeYolo(EIGHT_CLASSES)))
    resp = client.get("/ml/model-info")
    assert resp.status_code == 200
    body = resp.json()
    assert body["model"] == "walkbuddy-yolo-8class"
    assert body["class_count"] == 8
    assert body["classes"][-1] == "couch"


def test_model_info_503_when_model_unavailable():
    client = TestClient(_build_app(yolo=None))
    resp = client.get("/ml/model-info")
    assert resp.status_code == 503


# ---------------------------------------------------------------------------
# Mock mode (WALKBUDDY_ML_MOCK) — works with NO weights loaded
# ---------------------------------------------------------------------------

def test_navigate_mock_mode_no_weights(monkeypatch):
    monkeypatch.setenv("WALKBUDDY_ML_MOCK", "1")
    # yolo is None on purpose: mock mode must not require weights.
    client = TestClient(_build_app(yolo=None))
    resp = client.post(
        "/ml/navigate",
        files={"file": ("frame.jpg", b"ignored-in-mock", "image/jpeg")},
    )
    assert resp.status_code == 200
    body = resp.json()

    # Exact same contract as the real path.
    assert set(body) == {
        "model",
        "classes",
        "detections",
        "guidance_message",
        "risk_level",
        "inference_time_ms",
        "image_id",
    }

    # Deterministic mock payload, approved eight-class taxonomy.
    assert body["model"] == "walkbuddy-yolo-mock"
    assert body["classes"] == [
        "book", "books", "monitor", "office-chair",
        "whiteboard", "table", "tv", "couch",
    ]
    assert body["detections"] == [
        {
            "category": "table",
            "confidence": 0.87,
            "bbox": {"x_min": 220, "y_min": 180, "x_max": 420, "y_max": 400},
            "direction": "ahead",
            "priority": "HIGH",
        }
    ]
    assert body["image_id"] == "mock"
    assert body["inference_time_ms"] == 0
    assert isinstance(body["guidance_message"], str) and body["guidance_message"]
    assert isinstance(body["risk_level"], str) and body["risk_level"]


def test_model_info_mock_mode_no_weights(monkeypatch):
    monkeypatch.setenv("WALKBUDDY_ML_MOCK", "1")
    client = TestClient(_build_app(yolo=None))
    resp = client.get("/ml/model-info")
    assert resp.status_code == 200
    body = resp.json()
    assert body["model"] == "walkbuddy-yolo-mock"
    assert body["class_count"] == 8
    assert body["mock"] is True
