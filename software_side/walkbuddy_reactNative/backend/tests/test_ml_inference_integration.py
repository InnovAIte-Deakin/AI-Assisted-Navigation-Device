"""
Real-app integration tests for the ML inference wiring.

Unlike test_ml_inference.py (which mounts only my router in isolation), these
tests import the actual `main.app` — with every router, middleware, and the
shared `ml_runtime` state wired exactly as production does — and verify the
integration the team lead asked for:

  * POST /ml/navigate is registered on the real app.
  * There is exactly ONE authoritative GET /ml/model-info, and it belongs to
    ml_runtime (my duplicate handler has been removed).
  * Mock mode reports the approved 8 navigation classes.
  * Shared ML-runtime metrics update on BOTH successful and failed inference.
  * Existing /vision, /ws/vision and the /ml/* runtime endpoints stay intact.

The app's lifespan is intentionally NOT run (TestClient is used without its
context manager), so no real model weights, OCR, Whisper, or LLM are loaded.
We set the two pieces of state that lifespan would normally create.

Run from the backend directory:
    pytest tests/test_ml_inference_integration.py -v
"""

import sys
from unittest.mock import MagicMock

import anyio
import pytest
from fastapi.testclient import TestClient

# llama_cpp's native library may be absent (it's not a hard test dependency).
# Stub it before importing main so `from slow_lane import SlowLaneBrain` works.
if "llama_cpp" not in sys.modules:
    sys.modules["llama_cpp"] = MagicMock()

import main  # noqa: E402  (import after the llama_cpp guard above)
import routers.ml_inference as ml_inference  # noqa: E402
from ml_runtime import MLRuntimeState  # noqa: E402


APPROVED_NAV_CLASSES = ["person", "stairs", "door", "chair", "table", "pole", "bicycle", "vehicle"]


class FakeYolo:
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
                "priority": "MEDIUM",
            }
        ],
        "metadata": {"image_shape": [480, 640]},
    }


@pytest.fixture
def app():
    """The real production app, with the state lifespan would create.

    A fresh MLRuntimeState per test keeps metric deltas isolated. The lifespan
    is not executed, so no heavy models load.
    """
    application = main.app
    application.state.ml_runtime = MLRuntimeState()
    application.state.vision_limiter = anyio.CapacityLimiter(1)
    application.state.yolo = None
    return application


def _routes_with_path(application, path):
    return [r for r in application.routes if getattr(r, "path", None) == path]


# ---------------------------------------------------------------------------
# Route registration + single authoritative /ml/model-info
# ---------------------------------------------------------------------------

def test_navigate_registered_and_single_authoritative_model_info(app):
    paths = {getattr(r, "path", None) for r in app.routes}
    assert "/ml/navigate" in paths

    info_routes = _routes_with_path(app, "/ml/model-info")
    # Exactly one handler for the shared path...
    assert len(info_routes) == 1
    # ...and it is ml_runtime's, not the one I used to define in ml_inference.
    assert info_routes[0].endpoint.__module__ == "ml_runtime.router"
    assert not hasattr(ml_inference, "model_info")


def test_existing_and_ml_endpoints_remain_intact(app):
    paths = {getattr(r, "path", None) for r in app.routes}
    # Existing vision routes untouched.
    assert "/vision" in paths
    assert "/ws/vision" in paths
    # My endpoint plus the full ml_runtime surface.
    for expected in ["/ml/navigate", "/ml/model-info", "/ml/health", "/ml/ready", "/ml/metrics"]:
        assert expected in paths, expected


# ---------------------------------------------------------------------------
# Mock mode via the real app
# ---------------------------------------------------------------------------

def test_mock_mode_reports_approved_navigation_classes(app, monkeypatch):
    monkeypatch.setenv("WALKBUDDY_ML_MOCK", "1")
    client = TestClient(app)  # no context manager -> lifespan is not run
    resp = client.post("/ml/navigate", files={"file": ("f.jpg", b"x", "image/jpeg")})
    assert resp.status_code == 200
    body = resp.json()
    assert body["model"] == "walkbuddy-yolo-mock"
    assert body["classes"] == APPROVED_NAV_CLASSES
    assert body["detections"][0]["priority"] == "MEDIUM"  # table is MEDIUM in the contract


# ---------------------------------------------------------------------------
# Shared ML-runtime metrics update on success AND failure
# ---------------------------------------------------------------------------

def test_metrics_update_on_successful_inference(app, monkeypatch):
    monkeypatch.delenv("WALKBUDDY_ML_MOCK", raising=False)
    monkeypatch.setattr(ml_inference, "vision_adapter", lambda model, path: _fake_result())
    app.state.yolo = FakeYolo({0: "table"})
    client = TestClient(app)

    before = app.state.ml_runtime.metrics.snapshot()
    resp = client.post("/ml/navigate", files={"file": ("f.jpg", b"x", "image/jpeg")})
    assert resp.status_code == 200
    after = app.state.ml_runtime.metrics.snapshot()

    assert after["total_attempts"] == before["total_attempts"] + 1
    assert after["successful_inferences"] == before["successful_inferences"] + 1
    assert after["failed_inferences"] == before["failed_inferences"]
    assert after["last_inference_at"] is not None


def test_metrics_update_on_failed_inference(app, monkeypatch):
    monkeypatch.delenv("WALKBUDDY_ML_MOCK", raising=False)

    def _boom(model, path):
        raise RuntimeError("boom")

    monkeypatch.setattr(ml_inference, "vision_adapter", _boom)
    app.state.yolo = FakeYolo({0: "table"})
    client = TestClient(app)

    before = app.state.ml_runtime.metrics.snapshot()
    resp = client.post("/ml/navigate", files={"file": ("f.jpg", b"x", "image/jpeg")})
    assert resp.status_code == 500
    assert resp.json() == {
        "error": {"code": "inference_failed", "message": "Vision inference failed."}
    }
    after = app.state.ml_runtime.metrics.snapshot()

    assert after["total_attempts"] == before["total_attempts"] + 1
    assert after["failed_inferences"] == before["failed_inferences"] + 1
    assert after["successful_inferences"] == before["successful_inferences"]


def test_model_unavailable_uses_stable_error(app, monkeypatch):
    monkeypatch.delenv("WALKBUDDY_ML_MOCK", raising=False)
    app.state.yolo = None
    client = TestClient(app)
    resp = client.post("/ml/navigate", files={"file": ("f.jpg", b"x", "image/jpeg")})
    assert resp.status_code == 503
    assert resp.json() == {
        "error": {"code": "model_unavailable", "message": "Vision model is unavailable."}
    }
