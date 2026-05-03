import os
import tempfile
import logging
import anyio
from fastapi import APIRouter, UploadFile, File, HTTPException, Request

from adapters.vision_adapter import vision_adapter
from adapters.ocr_adapter import ocr_adapter
from internal import state
from tts_service.message_reasoning import process_adapter_output, calculate_spatial_position
from slow_lane import safe_or_stop_recommendation

logger = logging.getLogger(__name__)
router = APIRouter()

@router.post("/vision")
async def vision_endpoint(request: Request, file: UploadFile = File(...)):
    if not request.app.state.yolo:
        raise HTTPException(503, "Vision model unavailable")

    content = await file.read()
    if not content:
        return {"detections": [], "guidance_message": ""}

    temp_path = None
    try:
        suffix = os.path.splitext(file.filename or "frame.jpg")[1] or ".jpg"
        with tempfile.NamedTemporaryFile(delete=False, suffix=suffix) as f:
            f.write(content)
            temp_path = f.name

        try:
            async with request.app.state.vision_limiter:
                result = await anyio.to_thread.run_sync(
                    vision_adapter,
                    request.app.state.yolo,
                    temp_path,
                )
        except Exception as e:
            logger.error(f"Vision adapter error: {e}")
            raise HTTPException(500, "Vision processing failed")

        # Use real spatial direction from bounding box instead of hardcoding "ahead"
        image_width = result.get("metadata", {}).get("image_shape", [480, 640])[1]
        for d in result["detections"]:
            direction = calculate_spatial_position(d["bbox"], image_width)
            state.memory.add_event(
                label=d["category"],
                direction=direction,
                distance_m=None,
                confidence=d["confidence"],
            )

        msgs = process_adapter_output(result, max_messages=1)
        guidance = msgs[0].message if msgs else "Path clear"

        return {
            "detections": result["detections"],
            "guidance_message": guidance,
            "image_id": result["image_id"],
        }

    finally:
        if temp_path and os.path.exists(temp_path):
            os.unlink(temp_path)

@router.post("/ocr")
async def ocr_endpoint(request: Request, file: UploadFile = File(...)):
    if not request.app.state.ocr_reader:
        raise HTTPException(503, "OCR model unavailable")

    content = await file.read()
    if not content:
        return {"detections": [], "guidance_message": "Image error"}

    temp_path = None
    try:
        suffix = os.path.splitext(file.filename or "frame.jpg")[1] or ".jpg"
        with tempfile.NamedTemporaryFile(delete=False, suffix=suffix) as f:
            f.write(content)
            temp_path = f.name

        try:
            async with request.app.state.ocr_limiter:
                result = await anyio.to_thread.run_sync(
                    ocr_adapter,
                    request.app.state.ocr_reader,
                    temp_path,
                )
        except Exception as e:
            logger.error(f"OCR adapter error: {e}")
            raise HTTPException(500, "OCR processing failed")

        # Store OCR detections to NavigationMemory so the LLM has context
        for d in result["detections"]:
            state.memory.add_event(
                label=f"sign: {d['category']}",
                direction="ahead",
                distance_m=None,
                confidence=d["confidence"],
            )

        texts = [d["category"] for d in result["detections"]]
        return {
            "detections": result["detections"],
            "guidance_message": " ".join(texts) if texts else "No text detected.",
        }

    finally:
        if temp_path and os.path.exists(temp_path):
            os.unlink(temp_path)

@router.post("/chat")
async def chat_endpoint(request: Request, query: dict):
    user_q = query.get("query", "").strip()
    if not user_q:
        return {"response": "I didn't hear a question."}

    events = list(state.memory.buffer)
    hazard = safe_or_stop_recommendation(events[-10:])
    if hazard:
        return {"response": hazard}

    if not state.llm_brain:
        return {"response": "Brain offline."}

    async with request.app.state.llm_limiter:
        response = await anyio.to_thread.run_sync(
            state.llm_brain.ask,
            events,
            user_q,
        )

    return {"response": response}
