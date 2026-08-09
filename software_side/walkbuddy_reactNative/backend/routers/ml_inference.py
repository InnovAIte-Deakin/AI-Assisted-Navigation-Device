"""
Production ML inference endpoint for the WalkBuddy navigation model.

This router is a *pure addition* on top of the existing vision pipeline. It
reuses the already-loaded YOLO model (`app.state.yolo`), the shared capacity
limiter (`app.state.vision_limiter`), the `vision_adapter` detection logic, the
`_event_from_detection` / `_guidance_payload` helpers, and `state.memory`. It
introduces no new inference logic and does not touch `/vision`, `/ws/vision`,
or any other route.

The `model` and `classes` fields are read from `app.state.yolo.names` at request
time, so the contract works unchanged for both the 7-class and 8-class weights
without hardcoding the taxonomy. (See `ML_side/models/README.md` and
`ML_side/docs/current_model_baseline.md` for the known best.pt vs. newdata.yaml
class-lineage discrepancy — resolving that is separate follow-up work.)

Mock mode: set `WALKBUDDY_ML_MOCK=1` (default off) to make both endpoints return
a deterministic fake result in the exact same contract, with no weights and no
inference. This lets the frontend / API be developed before a navigation model
exists. The mock reports the approved eight-class taxonomy.
"""

import os
import time
import tempfile
import logging

import anyio
from fastapi import APIRouter, UploadFile, File, Request, HTTPException

from adapters.vision_adapter import vision_adapter
from internal import state
from routers.ai_service import _event_from_detection, _guidance_payload

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/ml", tags=["ml"])

# ── Mock mode ───────────────────────────────────────────────────────────────
# When WALKBUDDY_ML_MOCK is truthy the endpoints return a deterministic fake
# result (no weights, no inference) so the API can be developed before a real
# navigation model exists. Off by default.
_TRUTHY = {"1", "true", "yes", "on"}

# Approved eight-class navigation taxonomy (matches ML_side/config/newdata.yaml).
MOCK_CLASSES = [
    "book", "books", "monitor", "office-chair",
    "whiteboard", "table", "tv", "couch",
]
MOCK_MODEL = "walkbuddy-yolo-mock"

# A single deterministic detection in the exact shape vision_adapter produces.
_MOCK_RESULT = {
    "image_id": "mock",
    "detections": [
        {
            "category": "table",
            "confidence": 0.87,
            "bbox": {"x_min": 220, "y_min": 180, "x_max": 420, "y_max": 400},
            "direction": "ahead",
            "priority": "HIGH",
        }
    ],
    "metadata": {"image_shape": [480, 640]},
}


def _mock_enabled() -> bool:
    return os.getenv("WALKBUDDY_ML_MOCK", "").strip().lower() in _TRUTHY


def _model_classes(yolo) -> list[str]:
    """Return the model's class names in class-index order.

    Reads directly from the loaded model's `.names` so the contract reflects the
    actual weights (7- or 8-class) rather than a hardcoded list. Ultralytics
    exposes `.names` as a dict keyed by int class id; a plain list is also
    handled defensively.
    """
    names = getattr(yolo, "names", None)
    if names is None:
        return []
    if isinstance(names, dict):
        return [names[key] for key in sorted(names)]
    return list(names)


def _model_descriptor(classes: list[str]) -> str:
    return f"walkbuddy-yolo-{len(classes)}class"


@router.get("/model-info")
async def model_info(request: Request):
    """Expose the authoritative class list/order baked into the active weights."""
    if _mock_enabled():
        return {
            "model": MOCK_MODEL,
            "classes": list(MOCK_CLASSES),
            "class_count": len(MOCK_CLASSES),
            "mock": True,
        }

    yolo = request.app.state.yolo
    if yolo is None:
        raise HTTPException(503, "Vision model unavailable")

    classes = _model_classes(yolo)
    return {
        "model": _model_descriptor(classes),
        "classes": classes,
        "class_count": len(classes),
    }


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

    yolo = request.app.state.yolo
    if yolo is None:
        raise HTTPException(503, "Vision model unavailable")

    classes = _model_classes(yolo)

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

        t0 = time.monotonic()
        try:
            async with request.app.state.vision_limiter:
                result = await anyio.to_thread.run_sync(
                    vision_adapter,
                    yolo,
                    temp_path,
                )
        except Exception as e:
            logger.error(f"ML navigate adapter error: {e}")
            raise HTTPException(500, "Vision processing failed")
        inference_ms = int((time.monotonic() - t0) * 1000)

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
