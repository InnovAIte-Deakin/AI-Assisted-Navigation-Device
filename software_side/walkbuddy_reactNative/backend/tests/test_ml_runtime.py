"""Tests for the production ML runtime operational state and public failures."""

from __future__ import annotations

import asyncio
from concurrent.futures import ThreadPoolExecutor
import importlib.util
import json
import math
import sys
from pathlib import Path
from types import ModuleType, SimpleNamespace
from typing import Iterator

import pytest
import httpx
from fastapi import FastAPI, WebSocketDisconnect
from fastapi import APIRouter
from fastapi.testclient import TestClient


BACKEND_DIR = Path(__file__).resolve().parents[1]
if str(BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(BACKEND_DIR))

from ml_runtime.metrics import InferenceMetrics
from ml_contract import NAVIGATION_CLASSES
from ml_runtime.model_info import (
    ModelMetadataError,
    calculate_sha256,
    capture_model_lineage,
    is_taxonomy_compatible,
    normalise_class_names,
    runtime_details,
)
from ml_runtime.router import router as ml_runtime_router
from ml_runtime.state import MLRuntimeState


class FakeModel:
    names = {
        0: "book",
        1: "books",
        2: "monitor",
        3: "office-chair",
        4: "whiteboard",
        5: "table",
        6: "tv",
    }


def canonical_class_names() -> list[str]:
    """Derive the approved ordered names from the single canonical contract."""
    return [navigation_class.name for navigation_class in NAVIGATION_CLASSES]


class CanonicalTaxonomyModel:
    """A model whose names exactly match the approved navigation taxonomy."""

    names = {index: name for index, name in enumerate(canonical_class_names())}


def _app_with_runtime(*, yolo: object | None, ocr_reader: object | None) -> FastAPI:
    app = FastAPI()
    app.state.yolo = yolo
    app.state.ocr_reader = ocr_reader
    app.state.ml_runtime = MLRuntimeState(latency_window_capacity=4)
    app.include_router(ml_runtime_router)
    return app


def test_model_sha256_is_calculated_without_mutating_artifact(tmp_path: Path) -> None:
    artifact = tmp_path / "best.pt"
    artifact.write_bytes(b"walkbuddy")

    assert calculate_sha256(artifact) == (
        "8c819d4eb6291df5e33d12e42ee44bb4413634751186d49641984d5f6ad26836"
    )
    assert artifact.read_bytes() == b"walkbuddy"


def test_model_lineage_captures_ordered_classes_and_class_count(tmp_path: Path) -> None:
    artifact = tmp_path / "private" / "best.pt"
    artifact.parent.mkdir()
    artifact.write_bytes(b"model")

    lineage = capture_model_lineage(artifact, FakeModel(), 12.3456)

    assert lineage.loaded is True
    assert lineage.filename == "best.pt"
    assert lineage.num_classes == 7
    assert lineage.classes == [
        "book", "books", "monitor", "office-chair", "whiteboard", "table", "tv"
    ]
    assert lineage.load_duration_ms == 12.346


def test_model_info_does_not_expose_absolute_model_path(tmp_path: Path) -> None:
    artifact = tmp_path / "private-model-dir" / "best.pt"
    artifact.parent.mkdir()
    artifact.write_bytes(b"model")
    runtime = MLRuntimeState()
    runtime.set_model_lineage(capture_model_lineage(artifact, FakeModel(), 1.0))

    model_info = runtime.model_info()

    assert model_info["filename"] == "best.pt"
    assert str(artifact.parent) not in json.dumps(model_info)


def test_model_names_property_failure_is_normalised_to_safe_metadata_error(
    tmp_path: Path,
) -> None:
    class FailingMetadataModel:
        @property
        def names(self) -> dict[int, str]:
            raise RuntimeError("private loader detail")

    artifact = tmp_path / "best.pt"
    artifact.write_bytes(b"model")

    with pytest.raises(ModelMetadataError, match="model.names"):
        capture_model_lineage(artifact, FailingMetadataModel(), 1.0)


@pytest.mark.parametrize("names", (None, {}, {"invalid": "book"}, ["", "book"]))
def test_malformed_model_names_are_rejected(names: object) -> None:
    with pytest.raises(ModelMetadataError, match="model.names"):
        normalise_class_names(names)


def test_model_load_failure_is_reported_without_exception_text(tmp_path: Path) -> None:
    runtime = MLRuntimeState()
    runtime.set_model_load_failure(tmp_path / "best.pt", 4.5, "model_file_missing")

    model_info = runtime.model_info()

    assert model_info["loaded"] is False
    assert model_info["failure_category"] == "model_file_missing"
    assert model_info["filename"] == "best.pt"


def test_ml_health_reports_healthy_components() -> None:
    app = _app_with_runtime(yolo=object(), ocr_reader=object())

    with TestClient(app) as client:
        response = client.get("/ml/health")

    assert response.status_code == 200
    assert response.json() == {
        "status": "ok",
        "vision": {"loaded": True},
        "ocr": {"loaded": True},
    }


def test_ml_health_reports_degraded_components() -> None:
    app = _app_with_runtime(yolo=None, ocr_reader=object())

    with TestClient(app) as client:
        response = client.get("/ml/health")

    assert response.status_code == 200
    assert response.json()["status"] == "degraded"
    assert response.json()["vision"] == {"loaded": False}


def test_ml_ready_returns_200_only_when_yolo_is_available() -> None:
    app = _app_with_runtime(yolo=object(), ocr_reader=None)

    with TestClient(app) as client:
        response = client.get("/ml/ready")

    assert response.status_code == 200
    assert response.json() == {"ready": True}


def test_ml_ready_returns_503_when_yolo_is_unavailable() -> None:
    app = _app_with_runtime(yolo=None, ocr_reader=None)

    with TestClient(app) as client:
        response = client.get("/ml/ready")

    assert response.status_code == 503
    assert response.json() == {"ready": False}


def test_model_info_endpoint_reports_captured_lineage(tmp_path: Path) -> None:
    artifact = tmp_path / "best.pt"
    artifact.write_bytes(b"model")
    app = _app_with_runtime(yolo=object(), ocr_reader=None)
    app.state.ml_runtime.set_model_lineage(
        capture_model_lineage(artifact, FakeModel(), 3.5)
    )

    with TestClient(app) as client:
        response = client.get("/ml/model-info")

    assert response.status_code == 200
    assert response.json()["loaded"] is True
    assert response.json()["filename"] == "best.pt"
    assert response.json()["num_classes"] == 7


def test_metrics_endpoint_is_zero_safe_before_inference() -> None:
    app = _app_with_runtime(yolo=object(), ocr_reader=None)

    with TestClient(app) as client:
        metrics = client.get("/ml/metrics").json()

    assert metrics["total_attempts"] == 0
    assert metrics["successful_inferences"] == 0
    assert metrics["failed_inferences"] == 0
    assert metrics["active_inferences"] == 0
    assert metrics["latency_window_size"] == 0
    assert metrics["p50_latency_ms"] is None


def test_successful_inference_increments_shared_metrics() -> None:
    metrics = InferenceMetrics()
    metrics.begin_inference()
    metrics.finish_inference(12.0, successful=True)

    snapshot = metrics.snapshot()

    assert snapshot["total_attempts"] == 1
    assert snapshot["successful_inferences"] == 1
    assert snapshot["failed_inferences"] == 0
    assert snapshot["processed_frames"] == 1
    assert snapshot["active_inferences"] == 0


def test_failed_inference_increments_shared_metrics() -> None:
    metrics = InferenceMetrics()
    metrics.begin_inference()
    metrics.finish_inference(8.0, successful=False)

    snapshot = metrics.snapshot()

    assert snapshot["total_attempts"] == 1
    assert snapshot["successful_inferences"] == 0
    assert snapshot["failed_inferences"] == 1
    assert snapshot["processed_frames"] == 0


def test_latency_statistics_use_deterministic_nearest_rank_percentiles() -> None:
    metrics = InferenceMetrics()
    for latency in (30.0, 10.0, 40.0, 20.0, 50.0):
        metrics.begin_inference()
        metrics.finish_inference(latency, successful=True)

    snapshot = metrics.snapshot()

    assert snapshot["latest_latency_ms"] == 50.0
    assert snapshot["mean_latency_ms"] == 30.0
    assert snapshot["p50_latency_ms"] == 30.0
    assert snapshot["p95_latency_ms"] == 50.0
    assert snapshot["max_latency_ms"] == 50.0


@pytest.mark.parametrize(
    ("samples", "expected_p50", "expected_p95"),
    (
        ([], None, None),
        ([5.0], 5.0, 5.0),
        ([1.0, 2.0, 3.0, 4.0], 2.0, 4.0),
        (list(range(1, 101)), 50, 95),
    ),
)
def test_latency_percentiles_cover_empty_small_and_large_windows(
    samples: list[float], expected_p50: float | None, expected_p95: float | None
) -> None:
    assert InferenceMetrics._percentile(samples, 0.50) == expected_p50
    assert InferenceMetrics._percentile(samples, 0.95) == expected_p95


def test_latency_window_is_bounded() -> None:
    metrics = InferenceMetrics(latency_window_capacity=2)
    for latency in (1.0, 2.0, 3.0):
        metrics.begin_inference()
        metrics.finish_inference(latency, successful=True)

    snapshot = metrics.snapshot()

    assert snapshot["total_attempts"] == 3
    assert snapshot["latency_window_size"] == 2
    assert snapshot["latency_window_capacity"] == 2
    assert snapshot["mean_latency_ms"] == 2.5


def test_metrics_normalise_nonfinite_latencies_for_safe_json_output() -> None:
    metrics = InferenceMetrics()
    for latency in (float("nan"), float("inf"), float("-inf")):
        metrics.begin_inference()
        metrics.finish_inference(latency, successful=True)

    snapshot = metrics.snapshot()
    numeric_values = (
        snapshot["latest_latency_ms"],
        snapshot["mean_latency_ms"],
        snapshot["p50_latency_ms"],
        snapshot["p95_latency_ms"],
        snapshot["max_latency_ms"],
    )
    assert all(value is not None and math.isfinite(value) for value in numeric_values)


def test_runtime_introspection_failure_does_not_escape(monkeypatch: pytest.MonkeyPatch) -> None:
    class FailingCuda:
        @staticmethod
        def is_available() -> bool:
            raise OSError("runtime probing failed")

    torch_stub = ModuleType("torch")
    torch_stub.__version__ = "test"
    torch_stub.cuda = FailingCuda()
    monkeypatch.setitem(sys.modules, "torch", torch_stub)

    details = runtime_details()

    assert details["cuda_available"] is False
    assert details["device"] == "unknown"


def test_metrics_are_thread_safe_for_worker_thread_inference() -> None:
    metrics = InferenceMetrics(latency_window_capacity=16)

    def record_attempt() -> None:
        for _ in range(25):
            metrics.begin_inference()
            metrics.finish_inference(1.0, successful=True)

    with ThreadPoolExecutor(max_workers=4) as executor:
        list(executor.map(lambda _index: record_attempt(), range(4)))

    snapshot = metrics.snapshot()
    assert snapshot["total_attempts"] == 100
    assert snapshot["successful_inferences"] == 100
    assert snapshot["active_inferences"] == 0
    assert snapshot["latency_window_size"] == 16


class _Memory:
    def add_event(self, **_kwargs: object) -> None:
        pass


class _AsyncLimiter:
    async def __aenter__(self) -> "_AsyncLimiter":
        return self

    async def __aexit__(self, *_args: object) -> bool:
        return False


class _BrokenMetrics:
    def __init__(self, failure_point: str) -> None:
        self._failure_point = failure_point

    def begin_inference(self) -> None:
        if self._failure_point == "begin":
            raise RuntimeError("metrics begin failed")

    def finish_inference(self, _latency_ms: float, *, successful: bool) -> None:
        if self._failure_point == "finish":
            raise RuntimeError("metrics finish failed")


class _Upload:
    filename = "frame.jpg"

    async def read(self) -> bytes:
        return b"image-bytes"


class _WebSocket:
    def __init__(self, app: object, messages: list[dict[str, object]]) -> None:
        self.app = app
        self.client = None
        self._messages = iter(messages)
        self.sent: list[dict[str, object]] = []
        self.close_code: int | None = None

    async def accept(self) -> None:
        pass

    async def send_text(self, message: str) -> None:
        self.sent.append(json.loads(message))

    async def close(self, code: int) -> None:
        self.close_code = code

    async def receive(self) -> dict[str, object]:
        try:
            return next(self._messages)
        except StopIteration as exc:
            raise WebSocketDisconnect() from exc


_AI_STUB_MODULES = (
    "adapters",
    "adapters.vision_adapter",
    "adapters.ocr_adapter",
    "internal",
    "internal.state",
    "internal.motion_tracker",
    "tts_service",
    "tts_service.message_reasoning",
    "slow_lane",
)

_MAIN_STUB_MODULES = (
    "ultralytics",
    "easyocr",
    "routers",
    "routers.stt",
    "routers.audiobooks",
    "routers.ai_service",
    "routers.helpers",
    "routers.auth",
    "internal",
    "internal.state",
    "slow_lane",
    "predictive_path",
    "predictive_path.router",
    "telemetry",
)


@pytest.fixture
def ai_service_module() -> Iterator[ModuleType]:
    """Import the router with fakes, avoiding CV, OCR, model, and GPU imports."""
    original_modules = {
        name: sys.modules[name] for name in _AI_STUB_MODULES if name in sys.modules
    }
    for name in _AI_STUB_MODULES:
        sys.modules.pop(name, None)

    adapters = ModuleType("adapters")
    adapters.__path__ = []
    vision = ModuleType("adapters.vision_adapter")
    vision.vision_adapter = lambda *_args: {"detections": [], "image_id": "frame", "metadata": {}}
    ocr = ModuleType("adapters.ocr_adapter")
    ocr.ocr_adapter = lambda *_args: {"detections": [], "image_id": "frame"}

    internal = ModuleType("internal")
    internal.__path__ = []
    state = ModuleType("internal.state")
    state.memory = _Memory()
    motion = ModuleType("internal.motion_tracker")
    motion.MotionTracker = type("MotionTracker", (), {"update": lambda self, detections, **_kwargs: detections})

    tts_service = ModuleType("tts_service")
    tts_service.__path__ = []
    reasoning = ModuleType("tts_service.message_reasoning")
    reasoning.process_adapter_output = lambda *_args, **_kwargs: []

    slow_lane = ModuleType("slow_lane")
    slow_lane.safe_or_stop_recommendation = lambda *_args: None

    sys.modules.update({
        "adapters": adapters,
        "adapters.vision_adapter": vision,
        "adapters.ocr_adapter": ocr,
        "internal": internal,
        "internal.state": state,
        "internal.motion_tracker": motion,
        "tts_service": tts_service,
        "tts_service.message_reasoning": reasoning,
        "slow_lane": slow_lane,
    })

    spec = importlib.util.spec_from_file_location(
        "ai_service_runtime_test", BACKEND_DIR / "routers" / "ai_service.py"
    )
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    try:
        spec.loader.exec_module(module)
        yield module
    finally:
        for name in _AI_STUB_MODULES:
            sys.modules.pop(name, None)
        sys.modules.update(original_modules)


@pytest.fixture
def main_module() -> Iterator[ModuleType]:
    """Import the FastAPI app without starting or importing heavy ML packages."""
    original_modules = {
        name: sys.modules[name] for name in _MAIN_STUB_MODULES if name in sys.modules
    }
    original_sys_path = sys.path.copy()
    for name in _MAIN_STUB_MODULES:
        sys.modules.pop(name, None)

    def router_module(name: str) -> ModuleType:
        module = ModuleType(name)
        module.router = APIRouter()
        return module

    ultralytics = ModuleType("ultralytics")
    ultralytics.YOLO = object
    easyocr = ModuleType("easyocr")
    easyocr.Reader = object

    routers = ModuleType("routers")
    routers.__path__ = []
    routers.stt = router_module("routers.stt")
    routers.audiobooks = router_module("routers.audiobooks")
    routers.ai_service = router_module("routers.ai_service")
    routers.helpers = router_module("routers.helpers")
    routers.auth = router_module("routers.auth")
    routers.ml_inference = router_module("routers.ml_inference")

    internal = ModuleType("internal")
    internal.__path__ = []
    internal_state = ModuleType("internal.state")
    internal_state.collaboration_sessions = {}
    internal_state.llm_brain = None
    internal.state = internal_state

    slow_lane = ModuleType("slow_lane")
    slow_lane.SlowLaneBrain = object

    predictive_path = ModuleType("predictive_path")
    predictive_path.__path__ = []
    predictive_path.router = router_module("predictive_path.router")

    telemetry = ModuleType("telemetry")
    telemetry.init_telemetry = lambda _app: None

    sys.modules.update({
        "ultralytics": ultralytics,
        "easyocr": easyocr,
        "routers": routers,
        "routers.stt": routers.stt,
        "routers.audiobooks": routers.audiobooks,
        "routers.ai_service": routers.ai_service,
        "routers.helpers": routers.helpers,
        "routers.auth": routers.auth,
    "routers.ml_inference": routers.ml_inference,
        "internal": internal,
        "internal.state": internal_state,
        "slow_lane": slow_lane,
        "predictive_path": predictive_path,
        "predictive_path.router": predictive_path.router,
        "telemetry": telemetry,
    })

    spec = importlib.util.spec_from_file_location(
        "ml_runtime_main_test", BACKEND_DIR / "main.py"
    )
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    try:
        spec.loader.exec_module(module)
        yield module
    finally:
        for name in _MAIN_STUB_MODULES:
            sys.modules.pop(name, None)
        sys.modules.update(original_modules)
        sys.path[:] = original_sys_path


def _vision_request(*, yolo: object | None) -> SimpleNamespace:
    return SimpleNamespace(
        app=SimpleNamespace(
            state=SimpleNamespace(
                yolo=yolo,
                vision_limiter=_AsyncLimiter(),
                ml_runtime=MLRuntimeState(),
            )
        )
    )


def test_only_readiness_is_public_when_an_api_key_is_configured(
    main_module: ModuleType, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("WALKBUDDY_API_KEY", "test-key")

    async def request_statuses() -> dict[str, int]:
        transport = httpx.ASGITransport(app=main_module.app)
        async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
            ready = await client.get("/ml/ready")
            health = await client.get("/ml/health")
            model_info = await client.get("/ml/model-info")
            metrics = await client.get("/ml/metrics")
            model_info_with_key = await client.get(
                "/ml/model-info", headers={"X-API-Key": "test-key"}
            )
            ping = await client.get("/ping")
        return {
            "ready": ready.status_code,
            "health": health.status_code,
            "model_info": model_info.status_code,
            "metrics": metrics.status_code,
            "model_info_with_key": model_info_with_key.status_code,
            "ping": ping.status_code,
        }

    statuses = asyncio.run(request_statuses())

    assert statuses == {
        "ready": 503,
        "health": 401,
        "model_info": 401,
        "metrics": 401,
        "model_info_with_key": 200,
        "ping": 200,
    }


def test_lifespan_records_missing_model_without_preventing_startup(
    main_module: ModuleType, monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    main_module.YOLO_MODEL_PATH = tmp_path / "missing-best.pt"
    main_module.init_database = lambda: None
    monkeypatch.setattr(main_module, "_cleanup_sessions_loop", lambda: None)
    monkeypatch.setattr(main_module.asyncio, "create_task", lambda _coroutine: None)

    async def start_with_missing_model() -> dict[str, object]:
        async with main_module.lifespan(main_module.app):
            return main_module.app.state.ml_runtime.model_info()

    model_info = asyncio.run(start_with_missing_model())

    assert main_module.app.state.yolo is None
    assert model_info["loaded"] is False
    assert model_info["failure_category"] == "model_file_missing"


def test_rest_model_unavailable_response_uses_stable_error_code(
    ai_service_module: ModuleType,
) -> None:
    response = asyncio.run(ai_service_module.vision_endpoint(_vision_request(yolo=None), _Upload()))

    assert response.status_code == 503
    assert json.loads(response.body) == {
        "error": {
            "code": "model_unavailable",
            "message": "Vision model is unavailable.",
        }
    }


def test_rest_inference_failure_hides_raw_exception_text(
    ai_service_module: ModuleType,
) -> None:
    ai_service_module.vision_adapter = lambda *_args: (_ for _ in ()).throw(
        RuntimeError("private model failure detail")
    )

    request = _vision_request(yolo=object())
    response = asyncio.run(ai_service_module.vision_endpoint(request, _Upload()))

    payload = json.loads(response.body)
    assert response.status_code == 500
    assert payload["error"]["code"] == "inference_failed"
    assert "private model failure detail" not in json.dumps(payload)
    assert request.app.state.ml_runtime.metrics.snapshot()["failed_inferences"] == 1


def test_successful_rest_vision_response_shape_is_preserved(
    ai_service_module: ModuleType,
) -> None:
    ai_service_module.vision_adapter = lambda *_args: {
        "detections": [],
        "guidance_message": "ignored",
        "image_id": "frame",
        "metadata": {"image_shape": [480, 640]},
    }
    ai_service_module._guidance_payload = lambda *_args, **_kwargs: ("Path clear", "CLEAR")

    request = _vision_request(yolo=object())
    response = asyncio.run(ai_service_module.vision_endpoint(request, _Upload()))

    assert response == {
        "detections": [],
        "guidance_message": "Path clear",
        "image_id": "frame",
    }
    assert request.app.state.ml_runtime.metrics.snapshot()["successful_inferences"] == 1


@pytest.mark.parametrize("failure_point", ("begin", "finish"))
def test_metrics_collection_failure_does_not_break_rest_vision(
    ai_service_module: ModuleType, failure_point: str
) -> None:
    ai_service_module.vision_adapter = lambda *_args: {
        "detections": [],
        "image_id": "frame",
        "metadata": {"image_shape": [480, 640]},
    }
    ai_service_module._guidance_payload = lambda *_args, **_kwargs: ("Path clear", "CLEAR")
    request = _vision_request(yolo=object())
    request.app.state.ml_runtime = SimpleNamespace(metrics=_BrokenMetrics(failure_point))

    response = asyncio.run(ai_service_module.vision_endpoint(request, _Upload()))

    assert response["guidance_message"] == "Path clear"


def test_websocket_model_unavailable_response_uses_stable_error_code(
    ai_service_module: ModuleType,
) -> None:
    websocket = _WebSocket(
        SimpleNamespace(state=SimpleNamespace(yolo=None)), messages=[]
    )

    asyncio.run(ai_service_module.vision_ws_endpoint(websocket))

    assert websocket.close_code == 1011
    assert websocket.sent == [{
        "type": "error",
        "code": "model_unavailable",
        "frame_id": None,
        "message": "Vision model is unavailable.",
    }]


def test_websocket_inference_failure_hides_raw_exception_text(
    ai_service_module: ModuleType,
) -> None:
    ai_service_module.vision_adapter = lambda *_args: (_ for _ in ()).throw(
        RuntimeError("private model failure detail")
    )
    app = SimpleNamespace(
        state=SimpleNamespace(
            yolo=object(), vision_limiter=_AsyncLimiter(), ml_runtime=MLRuntimeState()
        )
    )
    websocket = _WebSocket(app, [
        {"text": json.dumps({"type": "frame_meta", "frame_id": "frame-1"}), "bytes": None},
        {"text": None, "bytes": b"image-bytes"},
    ])

    asyncio.run(ai_service_module.vision_ws_endpoint(websocket))

    assert websocket.sent[-1]["code"] == "inference_failed"
    assert "private model failure detail" not in json.dumps(websocket.sent[-1])
    assert app.state.ml_runtime.metrics.snapshot()["failed_inferences"] == 1


def test_websocket_tracks_only_frames_the_server_actually_skips(
    ai_service_module: ModuleType,
) -> None:
    app = SimpleNamespace(
        state=SimpleNamespace(
            yolo=object(), vision_limiter=_AsyncLimiter(), ml_runtime=MLRuntimeState()
        )
    )
    websocket = _WebSocket(app, [{"text": None, "bytes": b"missing-metadata"}])

    asyncio.run(ai_service_module.vision_ws_endpoint(websocket))

    assert app.state.ml_runtime.metrics.snapshot()["dropped_frames"] == 1
    assert app.state.ml_runtime.metrics.snapshot()["total_attempts"] == 0


def test_successful_websocket_detection_result_shape_is_preserved(
    ai_service_module: ModuleType,
) -> None:
    ai_service_module.vision_adapter = lambda *_args: {
        "detections": [],
        "image_id": "frame",
        "metadata": {"image_shape": [480, 640]},
    }
    ai_service_module._guidance_payload = lambda *_args, **_kwargs: ("Path clear", "CLEAR")
    app = SimpleNamespace(
        state=SimpleNamespace(
            yolo=object(), vision_limiter=_AsyncLimiter(), ml_runtime=MLRuntimeState()
        )
    )
    websocket = _WebSocket(app, [
        {"text": json.dumps({"type": "frame_meta", "frame_id": "frame-1"}), "bytes": None},
        {"text": None, "bytes": b"image-bytes"},
    ])

    asyncio.run(ai_service_module.vision_ws_endpoint(websocket))

    payload = websocket.sent[-1]
    assert payload["type"] == "detection_result"
    assert set(payload) == {
        "type", "frame_id", "detections", "guidance_message", "risk_level",
        "inference_time_ms", "server_timestamp_ms",
    }
    assert app.state.ml_runtime.metrics.snapshot()["successful_inferences"] == 1


def test_model_info_before_startup_reports_unknown_taxonomy_compatibility() -> None:
    runtime = MLRuntimeState()

    model_info = runtime.model_info()

    assert model_info["loaded"] is False
    assert model_info["failure_category"] == "not_initialized"
    assert model_info["taxonomy_compatible"] is None


def test_model_info_endpoint_serialises_compatible_taxonomy(tmp_path: Path) -> None:
    artifact = tmp_path / "best.pt"
    artifact.write_bytes(b"model")
    app = _app_with_runtime(yolo=object(), ocr_reader=None)
    app.state.ml_runtime.set_model_lineage(
        capture_model_lineage(artifact, CanonicalTaxonomyModel(), 3.5)
    )

    with TestClient(app) as client:
        response = client.get("/ml/model-info")

    payload = response.json()
    assert response.status_code == 200
    assert payload["taxonomy_compatible"] is True
    assert payload["num_classes"] == len(NAVIGATION_CLASSES)
    assert payload["classes"] == canonical_class_names()
    assert payload["loaded"] is True
    assert payload["failure_category"] is None


def test_model_info_endpoint_serialises_incompatible_taxonomy(tmp_path: Path) -> None:
    artifact = tmp_path / "best.pt"
    artifact.write_bytes(b"model")
    app = _app_with_runtime(yolo=object(), ocr_reader=None)
    app.state.ml_runtime.set_model_lineage(
        capture_model_lineage(artifact, FakeModel(), 3.5)
    )

    with TestClient(app) as client:
        response = client.get("/ml/model-info")

    payload = response.json()
    assert response.status_code == 200
    assert payload["taxonomy_compatible"] is False
    # A taxonomy mismatch must never be reported as a load or metadata failure.
    assert payload["loaded"] is True
    assert payload["failure_category"] is None
    assert payload["num_classes"] == 7


def test_model_info_endpoint_preserves_existing_lineage_fields(tmp_path: Path) -> None:
    artifact = tmp_path / "best.pt"
    artifact.write_bytes(b"model")
    app = _app_with_runtime(yolo=object(), ocr_reader=None)
    app.state.ml_runtime.set_model_lineage(
        capture_model_lineage(artifact, FakeModel(), 3.5)
    )

    with TestClient(app) as client:
        payload = client.get("/ml/model-info").json()

    assert set(payload) == {
        "loaded",
        "filename",
        "sha256",
        "size_bytes",
        "num_classes",
        "classes",
        "taxonomy_compatible",
        "load_duration_ms",
        "loaded_at",
        "runtime",
        "failure_category",
    }
    assert payload["filename"] == "best.pt"
    assert payload["sha256"] == calculate_sha256(artifact)
    assert payload["size_bytes"] == artifact.stat().st_size
    assert payload["load_duration_ms"] == 3.5
    assert str(tmp_path) not in json.dumps(payload)


def test_incompatible_taxonomy_does_not_change_readiness(tmp_path: Path) -> None:
    """Scope guard: this PR reports compatibility and must not enforce it."""
    artifact = tmp_path / "best.pt"
    artifact.write_bytes(b"model")
    app = _app_with_runtime(yolo=object(), ocr_reader=object())
    app.state.ml_runtime.set_model_lineage(
        capture_model_lineage(artifact, FakeModel(), 3.5)
    )

    with TestClient(app) as client:
        ready = client.get("/ml/ready")
        health = client.get("/ml/health")
        model_info = client.get("/ml/model-info").json()

    assert model_info["taxonomy_compatible"] is False
    assert ready.status_code == 200
    assert ready.json() == {"ready": True}
    assert health.status_code == 200
    assert health.json()["status"] == "ok"
    assert app.state.yolo is not None


def test_readiness_still_depends_only_on_the_loaded_model(tmp_path: Path) -> None:
    artifact = tmp_path / "best.pt"
    artifact.write_bytes(b"model")
    app = _app_with_runtime(yolo=None, ocr_reader=None)
    app.state.ml_runtime.set_model_lineage(
        capture_model_lineage(artifact, CanonicalTaxonomyModel(), 3.5)
    )

    with TestClient(app) as client:
        ready = client.get("/ml/ready")
        model_info = client.get("/ml/model-info").json()

    assert model_info["taxonomy_compatible"] is True
    assert ready.status_code == 503
    assert ready.json() == {"ready": False}


def test_taxonomy_compatibility_helper_matches_the_canonical_contract() -> None:
    assert is_taxonomy_compatible(canonical_class_names()) is True
    assert is_taxonomy_compatible(list(FakeModel.names.values())) is False
