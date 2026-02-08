# main.py

import sys
from pathlib import Path
import os
from typing import List, Optional, Dict
import httpx
import logging
import asyncio
import sqlite3
import hashlib
import secrets
import uuid
import json
from datetime import datetime, timedelta

# 1. SETUP PATHS & LOGGING
CURRENT_FILE = Path(__file__).resolve()
BACKEND_DIR = CURRENT_FILE.parent
PROJECT_ROOT = Path(__file__).resolve().parents[3]

if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

ML_MODELS_DIR = PROJECT_ROOT / "ML_models"
LLM_MODEL_PATH = PROJECT_ROOT / "ML_side/models/llama-3.2-1b-instruct-q4_k_m.gguf"

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# 2. IMPORTS
from fastapi import FastAPI, HTTPException, Query, WebSocket, WebSocketDisconnect, Depends, status
from fastapi.middleware.cors import CORSMiddleware
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from pydantic import BaseModel, EmailStr

# Internal Imports
from internal.state import collaboration_sessions, llm_brain
from slow_lane import SlowLaneBrain
import internal.state as app_state

# Routers
from routers import audiobooks as audiobooks_router
from routers import ai_service as ai_router

# Telemetry
from telemetry import init_telemetry
from opentelemetry import trace

# 3. CREATE APP
app = FastAPI(title="WalkBuddy Unified Backend")

# 4. MIDDLEWARE (your middleware first)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# 5. MOUNT ROUTERS
app.include_router(audiobooks_router.router)
app.include_router(ai_router.router)

# 6. TELEMETRY (instrument last so it wraps the final middleware stack)
init_telemetry(app)

# Tracer for manual spans (e.g., websocket lifecycle)
tracer = trace.get_tracer("main.websocket")

# 7. CONSTANTS
SESSION_EXPIRY_HOURS = 1
DB_PATH = BACKEND_DIR / "helpers.db"

# 8. LIFECYCLE EVENTS
def init_database():
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    cursor.execute(
        "CREATE TABLE IF NOT EXISTS helpers (id INTEGER PRIMARY KEY, email TEXT)"
    )  # Simplified
    conn.commit()
    conn.close()

async def cleanup_expired_sessions():
    # ... (Existing cleanup logic) ...
    pass

@app.on_event("startup")
async def startup_event():
    # A. Init Database
    init_database()

    # B. Load LLM Brain
    if os.path.exists(LLM_MODEL_PATH):
        logger.info(f"Loading Slow Lane LLM from {LLM_MODEL_PATH}...")
        try:
            app_state.llm_brain = SlowLaneBrain(str(LLM_MODEL_PATH))
            logger.info("✅ Slow Lane LLM Ready.")
        except Exception as e:
            logger.error(f"❌ Failed to load LLM: {e}")
    else:
        logger.warning(f"⚠️ LLM not found at {LLM_MODEL_PATH}")

    asyncio.create_task(cleanup_expired_sessions())

# ... (Auth & Navigation sections omitted for brevity, they are unchanged) ...

# ============================================================================
#  SECTION 10: COLLABORATION / WEBSOCKETS (Updated)
# ============================================================================
def normalize_session_id(sid: str) -> str:
    return sid.strip().upper() if sid else ""

def validate_session_id(sid: str) -> bool:
    return len(normalize_session_id(sid)) == 8

@app.get("/ping")
async def ping():
    return {"ok": True}

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
    # One span for the lifetime of the websocket connection
    with tracer.start_as_current_span(f"ws.session.{role}") as span:
        sid = normalize_session_id(session_id)
        span.set_attribute("session_id", sid)

        if role not in ["user", "guide"]:
            await websocket.close(1008, "Invalid role")
            span.set_status(trace.Status(trace.StatusCode.ERROR, "Invalid role"))
            return

        session = collaboration_sessions.get(sid)
        if not session:
            await websocket.close(1008, "Session not found")
            span.set_status(trace.Status(trace.StatusCode.ERROR, "Session not found"))
            return

        if datetime.now() > (session["created_at"] + timedelta(hours=SESSION_EXPIRY_HOURS)):
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
        if role == "user":
            session["user_ws"] = websocket
        else:
            session["guide_ws"] = websocket

        logger.info(f"[WS] {role} connected to {sid}")
        span.add_event("connected")

        # Notify peer
        other_peer = session["guide_ws"] if role == "user" else session["user_ws"]
        if other_peer:
            await other_peer.send_json({"type": f"{role}_connected", "session_id": sid})

        try:
            while True:
                data = await websocket.receive_json()
                msg_type = data.get("type")

                # Not tracing frames individually (noise control)
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

                elif msg_type in ["webrtc_offer", "webrtc_answer", "webrtc_ice"]:
                    target = session["guide_ws"] if role == "user" else session["user_ws"]
                    if target:
                        await target.send_json(data)

                elif role == "guide" and msg_type == "guidance":
                    if session["user_ws"]:
                        await session["user_ws"].send_json(data)

        except WebSocketDisconnect:
            logger.info(f"[WS] {role} disconnected {sid}")
            span.add_event("client_disconnected")
        except Exception as e:
            logger.error(f"[WS] Error {sid}: {e}")
            span.record_exception(e)
            span.set_status(trace.Status(trace.StatusCode.ERROR))
        finally:
            if role == "user":
                session["user_ws"] = None
            else:
                session["guide_ws"] = None

            other = session["guide_ws"] if role == "user" else session["user_ws"]
            if other:
                try:
                    await other.send_json({"type": f"{role}_disconnected"})
                except Exception:
                    pass

if __name__ == "__main__":
    import uvicorn
    uvicorn.run("main:app", host="0.0.0.0", port=8000, reload=True)
