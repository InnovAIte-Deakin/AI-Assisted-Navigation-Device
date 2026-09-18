"""
Production ML inference endpoint for the WalkBuddy navigation model.

This router is a *pure addition* on top of the existing vision pipeline. It
reuses the already-loaded YOLO model (`app.state.yolo`), the shared capacity
limiter (`app.state.vision_limiter`), the `vision_adapter` detection logic, the
`_event_from_detection` / `_guidance_payload` helpers, the shared ML-runtime
metrics + error helpers, and `state.memory`. It introduces no new inference
logic and does not touch `/vision`, `/ws/vision`, or any other route.

It exposes exactly one endpoint: `POST /ml/navigate`. The authoritative
`GET /ml/model-info` (and `/ml/health`, `/ml/ready`, `/ml/metrics`) are owned by
`ml_runtime.router`; this router deliberately does NOT define a second
`/ml/model-info` handler.

Real path: `model`/`classes` are read from `app.state.yolo.names` at request
time, so the contract works unchanged for whatever weights are loaded, without
hardcoding a taxonomy.

Mock mode: set `WALKBUDDY_ML_MOCK=1` (default off) to make `/ml/navigate` return
a deterministic fake result in the same contract, with no weights and no
inference. The mock taxonomy and per-class priority are DERIVED from
`ml_contract.navigation_semantics` (the approved MVP navigation classes), not
hardcoded here. This lets the frontend / API be developed before a real
navigation model exists.
"""

import os
import time
import tempfile
import logging

import anyio
from fastapi import APIRouter, UploadFile, File, Request
from fastapi.responses import JSONResponse

from adapters.vision_adapter import vision_adapter
from internal import state
from routers.ai_service import (
    _event_from_detection,
    _guidance_payload,
    _begin_vision_metrics,
    _finish_vision_metrics,
)
from ml_contract import NAVIGATION_CLASSES, get_base_severity
from ml_runtime import inference_failed_error, model_unavailable_error

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/ml", tags=["ml"])

# ── Mock mode ───────────────────────────────────────────────────────────────
# When WALKBUDDY_ML_MOCK is truthy the endpoint returns a deterministic fake
# result (no weights, no inference) so the API can be developed before a real
# navigation model exists. Off by default.
_TRUTHY = {"1", "true", "yes", "on"}

# Approved navigation MVP taxonomy, derived from the shared contract so there is
# a single source of truth (never a second hardcoded copy).
MOCK_CLASSES = [nav_class.name for nav_class in NAVIGATION_CLASSES]
MOCK_MODEL = "walkbuddy-yolo-mock"

# One deterministic detection in the exact shape vision_adapter produces. Its
# priority is read from the contract's base severity for that class (e.g. the
# contract rates "table" as MEDIUM), not hardcoded.
_MOCK_CATEGORY = "table"
_MOCK_RESULT = {
    "image_id": "mock",
    "detections": [
        {
            "category": _MOCK_CATEGORY,
            "confidence": 0.87,
            "bbox": {"x_min": 220, "y_min": 180, "x_max": 420, "y_max": 400},
            "direction": "ahead",
            "priority": get_base_severity(_MOCK_CATEGORY).name,
            "relative_depth": None,
        }
    ],
    "metadata": {"image_shape": [480, 640]},
}


def _mock_enabled() -> bool:
    return os.getenv("WALKBUDDY_ML_MOCK", "").strip().lower() in _TRUTHY


def _model_classes(yolo) -> list[str]:
    """Return the model's class names in class-index order.

    Reads directly from the loaded model's `.names` so the contract reflects the
    actual weights rather than a hardcoded list. Ultralytics exposes `.names` as
    a dict keyed by int class id; a plain list is also handled defensively.
    """
    names = getattr(yolo, "names", None)
    if names is None:
        return []
    if isinstance(names, dict):
        return [names[key] for key in sorted(names)]
    return list(names)


def _model_descriptor(classes: list[str]) -> str:
    return f"walkbuddy-yolo-{len(classes)}class"


@router.post("/navigate")
async def navigate_endpoint(request: Request, file: UploadFile = File(...)):
    """Run the approved navigation model on a single frame.

    Contract (200):
        {
          "model": str,                 # derived from app.state.yolo.names
          "classes": list[str],         # class names in index order
          "detections": list[dict],     # exactly what vision_adapter returns
          "guidance_message": str,
          "risk_level": str,
          "inference_time_ms": int,
          "image_id": str | None,
        }

    Errors use the stable ML error format from `ml_runtime.errors`:
      503 -> model_unavailable_error(); 500 -> inference_failed_error().
    Successful and failed inferences are recorded in the shared ML-runtime
    metrics, exactly like `/vision`.
    """
    if _mock_enabled():
        result = _MOCK_RESULT
        for d in result["detections"]:
            state.memory.add_event(**_event_from_detection(d))
        guidance, risk_level = _guidance_payload(result, max_messages=3)
        return {
            "model": MOCK_MODEL,
            "classes": list(MOCK_CLASSES),
            "detections": result["detections"],
            "guidance_message": guidance,
            "risk_level": risk_level,
            "inference_time_ms": 0,
            "image_id": result["image_id"],
        }

    if not request.app.state.yolo:
        return JSONResponse(status_code=503, content=model_unavailable_error())

    classes = _model_classes(request.app.state.yolo)

    content = await file.read()
    if not content:
        return {
            "model": _model_descriptor(classes),
            "classes": classes,
            "detections": [],
            "guidance_message": "",
            "risk_level": "CLEAR",
            "inference_time_ms": 0,
            "image_id": None,
        }

    temp_path = None
    try:
        suffix = os.path.splitext(file.filename or "frame.jpg")[1] or ".jpg"
        with tempfile.NamedTemporaryFile(delete=False, suffix=suffix) as f:
            f.write(content)
            temp_path = f.name

        try:
            async with request.app.state.vision_limiter:
                t0 = time.monotonic()
                metrics_started_at = _begin_vision_metrics(request.app)
                try:
                    result = await anyio.to_thread.run_sync(
                        vision_adapter,
                        request.app.state.yolo,
                        temp_path,
                    )
                except Exception:
                    _finish_vision_metrics(
                        request.app, metrics_started_at, successful=False
                    )
                    raise
                _finish_vision_metrics(request.app, metrics_started_at, successful=True)
                inference_ms = int((time.monotonic() - t0) * 1000)
        except Exception:
            logger.exception("ML navigate adapter error")
            return JSONResponse(status_code=500, content=inference_failed_error())

        for d in result["detections"]:
            state.memory.add_event(**_event_from_detection(d))

        guidance, risk_level = _guidance_payload(result, max_messages=3)

        return {
            "model": _model_descriptor(classes),
            "classes": classes,
            "detections": result["detections"],
            "guidance_message": guidance,
            "risk_level": risk_level,
            "inference_time_ms": inference_ms,
            "image_id": result["image_id"],
        }

    finally:
        if temp_path and os.path.exists(temp_path):
            os.unlink(temp_path)
