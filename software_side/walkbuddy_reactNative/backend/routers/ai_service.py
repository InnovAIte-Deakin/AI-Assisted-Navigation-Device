import os
import json
import time
import tempfile
import logging
import anyio
from fastapi import APIRouter, UploadFile, File, Request, WebSocket, WebSocketDisconnect, HTTPException
from opentelemetry import trace

from adapters.vision_adapter import vision_adapter
from adapters.ocr_adapter import ocr_adapter
from internal import state
from internal.motion_tracker import MotionTracker
from tts_service.message_reasoning import process_adapter_output
from slow_lane import safe_or_stop_recommendation

logger = logging.getLogger(__name__)
router = APIRouter()
tracer = trace.get_tracer("ai_service")


def normalize_vision_events(raw_events):
    if not isinstance(raw_events, list):
        return []

    events = []
    for event in raw_events:
        if not isinstance(event, dict):
            continue

        label = event.get("label") or event.get("category")
        if not label:
            continue

        try:
            confidence = float(event.get("confidence", 0))
        except (TypeError, ValueError):
            confidence = 0.0

        events.append({
            "label": str(label),
            "direction": str(event.get("direction") or "ahead"),
            "distance_m": event.get("distance_m"),
            "confidence": confidence,
        })

    return events


def is_current_scene_question(question: str) -> bool:
    q = question.lower()
    scene_terms = (
        "front",
        "ahead",
        "around",
        "near me",
        "nearby",
        "surrounding",
        "surroundings",
        "see",
        "seeing",
        "object",
        "objects",
        "obstacle",
        "obstacles",
        "danger",
        "dangerous",
        "hazard",
        "hazards",
    )
    return any(term in q for term in scene_terms)


def current_scene_response(events):
    if not events:
        return "I do not detect any clear objects in view right now. Try pointing the camera at the area ahead."

    top_events = sorted(
        events,
        key=lambda e: float(e.get("confidence", 0)),
        reverse=True,
    )[:3]

    descriptions = []
    for event in top_events:
        label = event["label"]
        direction = event.get("direction") or "ahead"
        descriptions.append(f"{label} {direction}")

    return "I can see " + ", ".join(descriptions) + "."


def _image_dimensions(result: dict) -> tuple[int, int]:
    shape = result.get("metadata", {}).get("image_shape") or ()
    if len(shape) >= 2:
        return int(shape[1]), int(shape[0])
    return 640, 480


def _event_from_detection(detection: dict) -> dict:
    return {
        "label": detection["category"],
        "direction": detection.get("direction", "ahead"),
        "distance_m": None,
        "confidence": detection["confidence"],
        "track_id": detection.get("track_id"),
        "is_moving": detection.get("is_moving", False),
        "motion_direction": detection.get("motion_direction", "unknown"),
        "motion_magnitude": detection.get("motion_magnitude", "low"),
        "approaching": detection.get("approaching", False),
    }


def _guidance_payload(result: dict, max_messages: int = 1) -> tuple[str, str]:
    events = [_event_from_detection(d) for d in result["detections"]]
    safety_message = safe_or_stop_recommendation(events)
    if safety_message:
        return safety_message, "CRITICAL"

    image_width, image_height = _image_dimensions(result)
    msgs = process_adapter_output(result, image_width=image_width, image_height=image_height, max_messages=max_messages)
    if msgs:
        return msgs[0].message, msgs[0].risk_level.name
    return "Path clear", "CLEAR"


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

        for d in result["detections"]:
            state.memory.add_event(**_event_from_detection(d))

        guidance, _risk = _guidance_payload(result, max_messages=1)

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

        for d in result["detections"]:
            state.memory.add_event(
                label=f"text: {d['category']}",
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
    start_time = time.monotonic()
    user_q = query.get("query", "").strip()
    request_events = normalize_vision_events(query.get("vision_events"))
    memory_events = list(state.memory.buffer)
    events = request_events or memory_events
    logger.info(
        "[Chat] query=%r request_events=%d memory_events=%d",
        user_q,
        len(request_events),
        len(memory_events),
    )
    if not user_q:
        response = "I didn't hear a question."
        logger.info(
            "[Chat] source=empty duration_ms=%d response=%r",
            int((time.monotonic() - start_time) * 1000),
            response,
        )
        return {"response": response}

    if is_current_scene_question(user_q):
        response = current_scene_response(request_events)
        logger.info(
            "[Chat] source=current_scene request_events=%d memory_events=%d duration_ms=%d response=%r",
            len(request_events),
            len(memory_events),
            int((time.monotonic() - start_time) * 1000),
            response,
        )
        return {"response": response}

    hazard = safe_or_stop_recommendation(events[-10:])
    if hazard:
        logger.info(
            "[Chat] source=safety_gate events=%d duration_ms=%d response=%r",
            len(events),
            int((time.monotonic() - start_time) * 1000),
            hazard,
        )
        return {"response": hazard}

    if not state.llm_brain:
        response = "Brain offline."
        logger.info(
            "[Chat] source=offline duration_ms=%d response=%r",
            int((time.monotonic() - start_time) * 1000),
            response,
        )
        return {"response": response}

    session_id = query.get("session_id", "default")
    history = list(state.conversation_histories[session_id])

    async with request.app.state.llm_limiter:
        response = await anyio.to_thread.run_sync(
            state.llm_brain.ask,
            events,
            user_q,
            history,
        )

    state.conversation_histories[session_id].append({"role": "user", "content": user_q})
    state.conversation_histories[session_id].append({"role": "assistant", "content": response})

    logger.info(
        "[Chat] source=llm events=%d duration_ms=%d response=%r",
        len(events),
        int((time.monotonic() - start_time) * 1000),
        response,
    )
    return {"response": response}


@router.post("/chat/clear")
async def clear_chat_history(query: dict):
    session_id = query.get("session_id", "default")
    if session_id in state.conversation_histories:
        state.conversation_histories[session_id].clear()
    return {"cleared": True, "session_id": session_id}


@router.websocket("/ws/vision")
async def vision_ws_endpoint(websocket: WebSocket):
    """
    Bidirectional WebSocket for real-time vision streaming.

    Protocol (per frame):
      Client → text:   {"type": "frame_meta", "frame_id": str, "width": int,
                         "height": int, "timestamp_ms": int}
      Client → binary: raw JPEG bytes
      Server → text:   {"type": "detection_result", "frame_id": str,
                         "detections": [...], "guidance_message": str,
                         "risk_level": str, "inference_time_ms": int,
                         "server_timestamp_ms": int}
                    OR {"type": "frame_dropped", "frame_id": str, "reason": str}
                    OR {"type": "error", "frame_id": str|null, "message": str}
      Server → text:   {"type": "ping"}  (every ~15 s)
      Client → text:   {"type": "pong"}
    """
    await websocket.accept()

    yolo = websocket.app.state.yolo
    if yolo is None:
        await websocket.send_text(json.dumps({
            "type": "error",
            "frame_id": None,
            "message": "YOLO model not loaded",
        }))
        await websocket.close(1011)
        return

    limiter = websocket.app.state.vision_limiter
    tracker = MotionTracker()
    client_host = websocket.client.host if websocket.client else "unknown"
    frames_processed = 0
    total_inference_ms = 0
    frame_meta: dict | None = None
    last_ping_at = time.monotonic()

    with tracer.start_as_current_span("ws.vision.connection") as conn_span:
        conn_span.set_attribute("ws.client_host", client_host)
        logger.info(f"[WS Vision] Connected: {client_host}")

        try:
            while True:
                # Send keepalive ping every 15 s to survive Cloudflare's 100 s idle timeout
                now = time.monotonic()
                if now - last_ping_at >= 15:
                    await websocket.send_text(json.dumps({"type": "ping"}))
                    last_ping_at = now

                msg = await websocket.receive()
                text_data = msg.get("text")
                bytes_data = msg.get("bytes")

                # ── Text messages: metadata or keepalive ───────────────────
                if text_data is not None:
                    try:
                        data = json.loads(text_data)
                    except json.JSONDecodeError:
                        continue
                    if data.get("type") == "frame_meta":
                        frame_meta = data
                    # "pong" responses are silently consumed
                    continue

                # ── Binary messages: JPEG frame ────────────────────────────
                if bytes_data is None:
                    continue

                if frame_meta is None:
                    logger.debug("[WS Vision] Binary received without frame_meta — skipped")
                    continue

                fid = frame_meta.get("frame_id", "unknown")
                client_ts = frame_meta.get("timestamp_ms", 0)
                saved_meta = frame_meta
                frame_meta = None  # clear before any await so next message is clean

                temp_path = None

                # Block (don't drop) until YOLO is free.  anyio queues waiters
                # in FIFO order, so multiple WS clients share the slot fairly.
                async with limiter:
                    t0 = time.monotonic()

                    with tracer.start_as_current_span("ws.vision.frame") as frame_span:
                        frame_span.set_attribute("frame.id", fid)
                        frame_span.set_attribute("frame.width", saved_meta.get("width", 0))
                        frame_span.set_attribute("frame.height", saved_meta.get("height", 0))
                        frame_span.set_attribute("frame.client_timestamp_ms", client_ts)

                        try:
                            with tempfile.NamedTemporaryFile(delete=False, suffix=".jpg") as f:
                                f.write(bytes_data)
                                temp_path = f.name

                            result = await anyio.to_thread.run_sync(
                                vision_adapter, yolo, temp_path
                            )
                            image_width, image_height = _image_dimensions(result)
                            result["detections"] = tracker.update(
                                result["detections"],
                                image_width=image_width,
                                image_height=image_height,
                            )

                            inference_ms = int((time.monotonic() - t0) * 1000)
                            total_inference_ms += inference_ms
                            frames_processed += 1

                            for d in result["detections"]:
                                state.memory.add_event(**_event_from_detection(d))

                            guidance, risk_level_str = _guidance_payload(result, max_messages=1)

                            frame_span.set_attribute("frame.inference_ms", inference_ms)
                            frame_span.set_attribute("frame.detection_count", len(result["detections"]))
                            frame_span.set_attribute("frame.risk_level", risk_level_str)
                            if client_ts:
                                frame_span.set_attribute(
                                    "frame.e2e_latency_ms",
                                    int(time.time() * 1000) - client_ts,
                                )

                            await websocket.send_text(json.dumps({
                                "type": "detection_result",
                                "frame_id": fid,
                                "detections": result["detections"],
                                "guidance_message": guidance,
                                "risk_level": risk_level_str,
                                "inference_time_ms": inference_ms,
                                "server_timestamp_ms": int(time.time() * 1000),
                            }))

                        except Exception as exc:
                            logger.error(f"[WS Vision] Inference error (frame {fid}): {exc}")
                            await websocket.send_text(json.dumps({
                                "type": "error",
                                "frame_id": fid,
                                "message": str(exc),
                            }))

                        finally:
                            if temp_path and os.path.exists(temp_path):
                                os.unlink(temp_path)

        except WebSocketDisconnect:
            logger.info(
                f"[WS Vision] Disconnected: {client_host} "
                f"(processed={frames_processed})"
            )
        except Exception as exc:
            logger.error(f"[WS Vision] Unexpected error ({client_host}): {exc}")
        finally:
            avg_ms = (total_inference_ms // frames_processed) if frames_processed > 0 else 0
            conn_span.set_attribute("ws.frames_processed", frames_processed)
            conn_span.set_attribute("ws.avg_inference_ms", avg_ms)
