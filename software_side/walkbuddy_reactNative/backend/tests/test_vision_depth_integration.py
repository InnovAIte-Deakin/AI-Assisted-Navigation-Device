import importlib.util
import sys
from pathlib import Path
from types import ModuleType, SimpleNamespace

import numpy as np
import pytest


BACKEND_DIR = Path(__file__).resolve().parents[1]


class _FakeSpan:
    def set_attribute(self, *_args, **_kwargs):
        pass


class _FakeSpanContext:
    def __enter__(self):
        return _FakeSpan()

    def __exit__(self, exc_type, exc, tb):
        return False


class _FakeTracer:
    def start_as_current_span(self, _name):
        return _FakeSpanContext()


class _FakeBox:
    xyxy = np.array([[100, 120, 400, 460]])
    conf = np.array([0.91])
    cls = np.array([0])


class _FakeResult:
    orig_shape = (480, 640)
    boxes = [_FakeBox()]
    names = {0: "table"}


class _FakeModel:
    def predict(self, **_kwargs):
        return [_FakeResult()]


def _load_vision_adapter(
    monkeypatch: pytest.MonkeyPatch,
    enrich_func,
) -> ModuleType:
    fake_cv2 = ModuleType("cv2")
    fake_cv2.imread = lambda _path: None

    fake_ultralytics = ModuleType("ultralytics")
    fake_ultralytics.YOLO = object

    fake_opentelemetry = ModuleType("opentelemetry")
    fake_opentelemetry.trace = SimpleNamespace(
        get_tracer=lambda _: _FakeTracer()
    )

    fake_tts_package = ModuleType("tts_service")
    fake_tts_package.__path__ = []

    fake_reasoning = ModuleType("tts_service.message_reasoning")
    fake_reasoning.calculate_spatial_position = (
        lambda _bbox, _width: "ahead"
    )

    fake_depth_adapter = ModuleType("adapters.depth_adapter")
    fake_depth_adapter.enrich_detections_with_depth = enrich_func

    monkeypatch.setitem(sys.modules, "cv2", fake_cv2)
    monkeypatch.setitem(sys.modules, "ultralytics", fake_ultralytics)
    monkeypatch.setitem(sys.modules, "opentelemetry", fake_opentelemetry)
    monkeypatch.setitem(sys.modules, "tts_service", fake_tts_package)
    monkeypatch.setitem(
        sys.modules,
        "tts_service.message_reasoning",
        fake_reasoning,
    )
    monkeypatch.setitem(
        sys.modules,
        "adapters.depth_adapter",
        fake_depth_adapter,
    )

    path = BACKEND_DIR / "adapters" / "vision_adapter.py"

    spec = importlib.util.spec_from_file_location(
        "depth_integration_vision_adapter",
        path,
    )

    assert spec is not None
    assert spec.loader is not None

    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)

    return module


def test_vision_adapter_enriches_detection_with_relative_depth(
    monkeypatch: pytest.MonkeyPatch,
):
    calls = []

    def fake_enrich(image_path, detections):
        calls.append((image_path, detections))

        detections[0]["relative_depth"] = 0.625
        return detections

    vision_adapter_module = _load_vision_adapter(
        monkeypatch,
        fake_enrich,
    )

    result = vision_adapter_module.vision_adapter(
        _FakeModel(),
        "frame.jpg",
    )

    assert len(calls) == 1
    assert calls[0][0] == "frame.jpg"

    assert calls[0][1][0]["bbox"] == {
        "x_min": 100,
        "y_min": 120,
        "x_max": 400,
        "y_max": 460,
    }

    assert result["detections"][0]["category"] == "table"
    assert result["detections"][0]["relative_depth"] == 0.625


def test_vision_adapter_preserves_detection_when_depth_unavailable(
    monkeypatch: pytest.MonkeyPatch,
):
    def fallback_enrich(_image_path, detections):
        for detection in detections:
            detection["relative_depth"] = None

        return detections

    vision_adapter_module = _load_vision_adapter(
        monkeypatch,
        fallback_enrich,
    )

    result = vision_adapter_module.vision_adapter(
        _FakeModel(),
        "frame.jpg",
    )

    detection = result["detections"][0]

    assert detection["category"] == "table"
    assert detection["confidence"] == 0.91
    assert detection["relative_depth"] is None