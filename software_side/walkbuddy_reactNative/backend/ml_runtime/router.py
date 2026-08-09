"""Operational HTTP endpoints for the backend ML runtime."""

from __future__ import annotations

from fastapi import APIRouter, Request
from fastapi.responses import JSONResponse

from .state import MLRuntimeState


router = APIRouter(prefix="/ml", tags=["ml-runtime"])


def _runtime_state(request: Request) -> MLRuntimeState:
    """Get initialized state or a zero-safe view for unusual pre-startup calls."""
    runtime_state = getattr(request.app.state, "ml_runtime", None)
    if isinstance(runtime_state, MLRuntimeState):
        return runtime_state
    return MLRuntimeState()


@router.get("/health")
async def ml_health(request: Request) -> dict[str, object]:
    """Report high-level component health without exposing model lineage."""
    vision_loaded = bool(getattr(request.app.state, "yolo", None))
    ocr_loaded = bool(getattr(request.app.state, "ocr_reader", None))
    return {
        "status": "ok" if vision_loaded and ocr_loaded else "degraded",
        "vision": {"loaded": vision_loaded},
        "ocr": {"loaded": ocr_loaded},
    }


@router.get("/ready")
async def ml_ready(request: Request) -> JSONResponse:
    """Return container readiness for the vision MVP independently of liveness."""
    vision_loaded = bool(getattr(request.app.state, "yolo", None))
    return JSONResponse(status_code=200 if vision_loaded else 503, content={"ready": vision_loaded})


@router.get("/model-info")
async def model_info(request: Request) -> dict[str, object]:
    """Return the safe active-model lineage captured once during startup."""
    return _runtime_state(request).model_info()


@router.get("/metrics")
async def metrics(request: Request) -> dict[str, object]:
    """Return the bounded, aggregate inference metrics for this process."""
    return _runtime_state(request).metrics.snapshot()
