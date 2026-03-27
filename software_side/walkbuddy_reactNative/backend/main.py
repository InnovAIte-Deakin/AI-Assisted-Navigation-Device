# main.py

import sys
from pathlib import Path
import os
import logging
import asyncio
import sqlite3
import uuid
import json
from datetime import datetime, timedelta
from contextlib import asynccontextmanager
from ultralytics import YOLO
import easyocr


# =========================
# 1. PATHS & LOGGING
# =========================
CURRENT_FILE = Path(__file__).resolve()
BACKEND_DIR = CURRENT_FILE.parent

try:
    PROJECT_ROOT = CURRENT_FILE.parents[3]
    if str(PROJECT_ROOT) not in sys.path:
        sys.path.insert(0, str(PROJECT_ROOT))
except IndexError:
    PROJECT_ROOT = BACKEND_DIR  # running in Docker — path is too shallow

# WALKBUDDY_MODEL_DIR env var lets Docker mount models without relying on
# the repo path structure (parents[3] is only 2 levels deep in containers).
_model_base = Path(os.environ["WALKBUDDY_MODEL_DIR"]) if "WALKBUDDY_MODEL_DIR" in os.environ else PROJECT_ROOT / "ML_side/models"
LLM_MODEL_PATH = _model_base / "llama-3.2-1b-instruct-q4_k_m.gguf"
YOLO_MODEL_PATH = _model_base / "best.pt"


logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# =========================
# 2. IMPORTS
# =========================
from fastapi import (
    FastAPI,
    HTTPException,
    WebSocket,
    WebSocketDisconnect,
)
from fastapi.middleware.cors import CORSMiddleware

# Internal
import internal.state as app_state
from internal.state import collaboration_sessions
from slow_lane import SlowLaneBrain

# Routers
from routers import audiobooks as audiobooks_router
from routers import ai_service as ai_router

# Telemetry
from telemetry import init_telemetry
from opentelemetry import trace

# AnyIO (for limiters)
import anyio

# =========================
# 3. CONSTANTS
# =========================
SESSION_EXPIRY_HOURS = 1
DB_PATH = BACKEND_DIR / "helpers.db"

tracer = trace.get_tracer("main.websocket")

# =========================
# 4. DB HELPERS
# =========================
def init_database():
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    cursor.execute(
        "CREATE TABLE IF NOT EXISTS helpers (id INTEGER PRIMARY KEY, email TEXT)"
    )
    conn.commit()
    conn.close()

async def cleanup_expired_sessions():
    # unchanged placeholder
    pass

# =========================
# 5. APP LIFESPAN (PHASE B)
# =========================
@asynccontextmanager
async def lifespan(app: FastAPI):
    logger.info("🚀 Backend startup")

    # --- init DB ---
    init_database()

    # --- load YOLO ---
    try:
        logger.info(f"Loading YOLO from {YOLO_MODEL_PATH}")
        app.state.yolo = YOLO(str(YOLO_MODEL_PATH))
        logger.info("✅ YOLO ready")
    except Exception as e:
        logger.error(f"❌ YOLO load failed: {e}")
        app.state.yolo = None

    # --- load EasyOCR ---
    try:
        logger.info("Loading EasyOCR reader")
        app.state.ocr_reader = easyocr.Reader(["en"], gpu=False)
        logger.info("✅ EasyOCR ready (CPU mode)")
    except Exception as e:
        logger.error(f"❌ EasyOCR load failed: {e}")
        app.state.ocr_reader = None

    # --- load LLM ---
    if not LLM_MODEL_PATH.exists():
        logger.warning(f"⚠️ LLM not found at {LLM_MODEL_PATH}")
        app_state.llm_brain = None
    else:
        try:
            logger.info(f"Loading LLM from {LLM_MODEL_PATH}")
            app_state.llm_brain = SlowLaneBrain(str(LLM_MODEL_PATH))
            logger.info("✅ LLM ready")
        except Exception as e:
            logger.error(f"❌ Failed to load LLM: {e}")
            app_state.llm_brain = None

    # --- execution capacity ---
    app.state.vision_limiter = anyio.CapacityLimiter(2)
    app.state.ocr_limiter = anyio.CapacityLimiter(2)
    app.state.llm_limiter = anyio.CapacityLimiter(1)

    asyncio.create_task(cleanup_expired_sessions())

    yield

    logger.info("🛑 Backend shutdown")


# =========================
# 6. CREATE APP
# =========================
app = FastAPI(
    title="WalkBuddy Unified Backend",
    lifespan=lifespan,
)

# =========================
# 7. MIDDLEWARE
# =========================
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# =========================
# 8. ROUTERS
# =========================
app.include_router(audiobooks_router.router)
app.include_router(ai_router.router)

# =========================
# 9. TELEMETRY
# =========================
init_telemetry(app)

# =========================
# 10. HEALTH
# =========================
@app.get("/ping")
async def ping():
    return {"ok": True}

# =========================
# 11. COLLABORATION
# =========================
def normalize_session_id(sid: str) -> str:
    return sid.strip().upper() if sid else ""

@app.post("/collaboration/create-session", tags=["collaboration"])
async def create_collaboration_session():
    session_id = str(uuid.uuid4())[:8].upper()
    expires_at = datetime.now() + timedelta(hours=SESSION_EXPIRY_HOURS)

    collaboration_sessions[session_id] = {
        "created_at": datetime.now(),
        "user_ws": None,
        "guide_ws": None,
        "guide_name": None,
        "last_frame_time": 0,
    }

    return {"session_id": session_id, "expires_at": expires_at.isoformat()}

@app.get("/collaboration/session/{session_id}/status", tags=["collaboration"])
async def get_session_status(session_id: str):
    sid = normalize_session_id(session_id)
    session = collaboration_sessions.get(sid)
    if not session:
        raise HTTPException(404, "Session not found")

    return {
        "session_id": sid,
        "user_connected": session["user_ws"] is not None,
        "guide_connected": session["guide_ws"] is not None,
        "created_at": session["created_at"].isoformat(),
    }

@app.websocket("/collaboration/ws/{session_id}/{role}")
async def collaboration_websocket(websocket: WebSocket, session_id: str, role: str):
    with tracer.start_as_current_span(f"ws.session.{role}") as span:
        sid = normalize_session_id(session_id)
        span.set_attribute("session_id", sid)

        if role not in {"user", "guide"}:
            await websocket.close(1008, "Invalid role")
            return

        session = collaboration_sessions.get(sid)
        if not session:
            await websocket.close(1008, "Session not found")
            return

        if datetime.now() > session["created_at"] + timedelta(hours=SESSION_EXPIRY_HOURS):
            await websocket.close(1008, "Expired")
            del collaboration_sessions[sid]
            return

        if role == "user" and session["user_ws"]:
            await websocket.close(1008, "User active")
            return
        if role == "guide" and session["guide_ws"]:
            await websocket.close(1008, "Guide active")
            return

        await websocket.accept()
        session[f"{role}_ws"] = websocket

        try:
            while True:
                data = await websocket.receive_json()
                msg_type = data.get("type")

                if msg_type == "ping":
                    await websocket.send_json({"type": "pong"})
                    continue

                if role == "guide" and msg_type == "helper_info":
                    session["guide_name"] = data.get("helper_name")
                    if session["user_ws"]:
                        await session["user_ws"].send_json(
                            {"type": "guide_connected", "helper_name": session["guide_name"]}
                        )

                elif role == "user" and msg_type == "frame":
                    if session["guide_ws"]:
                        await session["guide_ws"].send_json(data)

                elif msg_type in {"webrtc_offer", "webrtc_answer", "webrtc_ice"}:
                    target = session["guide_ws"] if role == "user" else session["user_ws"]
                    if target:
                        await target.send_json(data)

                elif role == "guide" and msg_type == "guidance":
                    if session["user_ws"]:
                        await session["user_ws"].send_json(data)

        except WebSocketDisconnect:
            pass
        finally:
            session[f"{role}_ws"] = None

# =========================
# 12. DEV ENTRYPOINT
# =========================
if __name__ == "__main__":
    import uvicorn
    uvicorn.run("main:app", host="0.0.0.0", port=8000, reload=True)
