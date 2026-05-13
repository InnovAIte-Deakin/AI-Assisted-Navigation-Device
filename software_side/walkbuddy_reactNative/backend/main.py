# main.py

import sys
from pathlib import Path
import os
import logging
import asyncio
import sqlite3
import uuid
import hashlib
import secrets
import re

_EMAIL_RE = re.compile(r"^[^\s@]+@[^\s@]+\.[^\s@]{2,}$")
import json
from datetime import datetime, timedelta
from contextlib import asynccontextmanager
from ultralytics import YOLO
import easyocr
import tempfile
from routers import stt


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
    UploadFile,
    File,
    Header,
    Request,
)
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from starlette.middleware.base import BaseHTTPMiddleware

# Internal
import internal.state as app_state
from internal.state import collaboration_sessions
from slow_lane import SlowLaneBrain

# Routers
from routers import audiobooks as audiobooks_router
from routers import ai_service as ai_router
from routers import helpers as helpers_router

# Telemetry
from telemetry import init_telemetry
from opentelemetry import trace

# AnyIO (for limiters)
import anyio
import httpx

# =========================
# 3. CONSTANTS
# =========================
SESSION_EXPIRY_HOURS = 1
SESSION_TIMEOUT_MINUTES = 30
DB_PATH = BACKEND_DIR / "helpers.db"

tracer = trace.get_tracer("main.websocket")

# In-memory token store: token -> helper_id
helper_tokens: dict[str, int] = {}

# =========================
# 4. DB HELPERS
# =========================
def init_database():
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS helpers (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL,
            email TEXT UNIQUE NOT NULL,
            password_hash TEXT NOT NULL,
            age INTEGER,
            phone TEXT,
            address TEXT,
            emergency_contact_name TEXT,
            emergency_contact_phone TEXT,
            experience_level TEXT,
            created_at TEXT DEFAULT (datetime('now'))
        )
    """)
    conn.commit()
    conn.close()


def _hash_password(password: str) -> str:
    salt = secrets.token_hex(16)
    hashed = hashlib.pbkdf2_hmac("sha256", password.encode(), salt.encode(), 260_000).hex()
    return f"{salt}:{hashed}"


def _verify_password(password: str, stored: str) -> bool:
    try:
        salt, hashed = stored.split(":", 1)
        expected = hashlib.pbkdf2_hmac("sha256", password.encode(), salt.encode(), 260_000).hex()
        return secrets.compare_digest(hashed, expected)
    except Exception:
        return False


def _get_helper_by_token(token: str) -> dict:
    helper_id = helper_tokens.get(token)
    if not helper_id:
        raise HTTPException(401, "Invalid or expired token")
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    cursor.execute(
        "SELECT id, name, email, age, phone, experience_level FROM helpers WHERE id=?",
        (helper_id,),
    )
    row = cursor.fetchone()
    conn.close()
    if not row:
        raise HTTPException(401, "User not found")
    return {
        "id": row[0],
        "name": row[1],
        "email": row[2],
        "age": row[3],
        "phone": row[4],
        "experience_level": row[5],
    }


async def _cleanup_sessions_loop():
    """Background task: remove expired collaboration sessions every 5 minutes."""
    while True:
        await asyncio.sleep(300)
        now = datetime.now()
        expired = [
            sid
            for sid, sess in list(collaboration_sessions.items())
            if now > sess["created_at"] + timedelta(hours=SESSION_EXPIRY_HOURS)
        ]
        for sid in expired:
            del collaboration_sessions[sid]
        if expired:
            logger.info(f"Cleaned up {len(expired)} expired collaboration sessions")


def _whisper_transcribe(model, path: str) -> str:
    """Run Whisper transcription synchronously (called from thread pool)."""
    segments, _ = model.transcribe(path, beam_size=5)
    return " ".join(seg.text.strip() for seg in segments).strip()

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
        # 检测GPU可用性
        import torch
        gpu_available = torch.cuda.is_available()
        gpu_status = "GPU" if gpu_available else "CPU"
        
        logger.info(f"Loading EasyOCR reader ({gpu_status} mode)")
        
        # 动态设置gpu参数
        app.state.ocr_reader = easyocr.Reader(["en"], gpu=gpu_available)
        
        logger.info(f"✅ EasyOCR ready ({gpu_status} mode)")
        
        # 记录GPU信息（如果可用）
        if gpu_available:
            logger.info(f"GPU Device: {torch.cuda.get_device_name(0)}")
            logger.info(f"GPU Memory: {torch.cuda.get_device_properties(0).total_memory / 1e9:.2f} GB")
        else:
            logger.info("Running in CPU mode - GPU not available")
            
    except Exception as e:
        logger.error(f"❌ EasyOCR load failed: {e}")
        
        # 尝试回退到CPU模式（如果GPU模式失败）
        try:
            logger.info("Attempting fallback to CPU mode...")
            app.state.ocr_reader = easyocr.Reader(["en"], gpu=False)
            logger.info("✅ EasyOCR fallback to CPU mode successful")
        except Exception as fallback_error:
            logger.error(f"❌ EasyOCR fallback also failed: {fallback_error}")
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

    # --- load Whisper STT ---
    try:
        from faster_whisper import WhisperModel
        logger.info("Loading Whisper STT (tiny model)")
        app.state.whisper = WhisperModel("tiny", device="cpu", compute_type="int8")
        logger.info("✅ Whisper STT ready")
    except Exception as e:
        logger.error(f"❌ Whisper STT load failed: {e}")
        app.state.whisper = None

    # --- execution capacity ---
    # vision: capacity=1 serialises YOLO — one inference at a time is faster
    # than two competing threads on a single CPU, and anyio's CapacityLimiter
    # queues waiters in FIFO order so multiple WS clients share it fairly.
    app.state.vision_limiter = anyio.CapacityLimiter(1)
    app.state.ocr_limiter = anyio.CapacityLimiter(1)
    app.state.llm_limiter = anyio.CapacityLimiter(1)

    asyncio.create_task(_cleanup_sessions_loop())

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
class APIKeyMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next):
        excluded_paths = {
            "/ping",
            "/docs",
            "/openapi.json",
            "/redoc",
        }

        if request.method == "OPTIONS" or request.url.path in excluded_paths:
            return await call_next(request)

        api_key = os.getenv("WALKBUDDY_API_KEY")

        if not api_key:
            return await call_next(request)

        header_key = request.headers.get("X-API-Key")
        auth_header = request.headers.get("Authorization", "")

        bearer_key = ""
        if auth_header.startswith("Bearer "):
            bearer_key = auth_header.replace("Bearer ", "", 1)

        if header_key != api_key and bearer_key != api_key:
            return JSONResponse(
                status_code=401,
                content={"detail": "Invalid or missing API key"},
            )

        return await call_next(request)

app.add_middleware(APIKeyMiddleware)

origins_env = os.getenv("WALKBUDDY_ALLOWED_ORIGINS")

if origins_env:
    allow_origins = [origin.strip() for origin in origins_env.split(",")]
else:
    allow_origins = [
        "http://localhost:8081",
        "http://localhost:8000"
    ]

app.add_middleware(
    CORSMiddleware,
    allow_origins = allow_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# =========================
# 8. ROUTERS
# =========================
app.include_router(audiobooks_router.router)
app.include_router(ai_router.router)
app.include_router(helpers_router.router)
app.include_router(stt.router)

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
# 11. GEOCODING (Nominatim proxy)
# =========================
@app.get("/geocode")
async def geocode_endpoint(q: str):
    """Geocode a place name to coordinates using OpenStreetMap Nominatim."""
    if not q.strip():
        raise HTTPException(400, "Query parameter 'q' is required")
    try:
        async with httpx.AsyncClient(
            timeout=10.0,
            follow_redirects=True,
            headers={"User-Agent": "WalkBuddy/1.0"},
        ) as client:
            resp = await client.get(
                "https://nominatim.openstreetmap.org/search",
                params={"q": q, "format": "json", "limit": "1", "addressdetails": "1"},
            )
            resp.raise_for_status()
            results = resp.json()
            if not results:
                raise HTTPException(404, f"No location found for: {q}")
            r = results[0]
            return {
                "name": r.get("display_name", q),
                "lat": float(r["lat"]),
                "lng": float(r["lon"]),
                "address": r.get("address", {}),
            }
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(502, f"Geocoding failed: {e}")


# =========================
# 12. ROUTING (OSRM proxy with fallback)
# =========================
# Try multiple OSRM servers in order (more reliable first)
OSRM_SERVERS = [
    "https://routing.openstreetmap.de/routed-{profile}/route/v1/{profile}",  # FOSSGIS (more stable)
    "http://router.project-osrm.org/route/v1/{profile}",  # Public OSRM demo (fallback)
]

@app.post("/routing")
async def routing_endpoint(body: dict):
    """
    Proxy routing requests to public OSRM servers with fallback.
    Body: { origin: [lng, lat], destination: [lng, lat], profile: "foot-walking" }
    """
    origin = body.get("origin")      # [lng, lat]
    destination = body.get("destination")  # [lng, lat]
    profile = body.get("profile", "foot-walking")

    if not origin or not destination:
        raise HTTPException(400, "origin and destination are required")

    # Map ORS profile names to OSRM profiles
    osrm_profile_map = {
        "foot-walking": "foot",
        "driving-car": "driving",
        "cycling-regular": "bike",
    }
    osrm_profile = osrm_profile_map.get(profile, "foot")

    coords = f"{origin[0]},{origin[1]};{destination[0]},{destination[1]}"
    params = {"overview": "full", "geometries": "geojson", "steps": "true"}

    last_error = None
    async with httpx.AsyncClient(timeout=15.0, follow_redirects=True) as client:
        for server_template in OSRM_SERVERS:
            base = server_template.format(profile=osrm_profile)
            url = f"{base}/{coords}"
            try:
                resp = await client.get(url, params=params)
                if resp.status_code == 200:
                    return resp.json()
                last_error = f"HTTP {resp.status_code} from {url}"
            except httpx.TimeoutException:
                last_error = f"Timeout from {url}"
            except Exception as e:
                last_error = str(e)

    raise HTTPException(502, f"All routing servers failed. Last error: {last_error}")


# =========================
# 11. STT TRANSCRIPTION
# =========================
@app.post("/stt/transcribe", tags=["stt"])
async def stt_transcribe(request: Request, file: UploadFile = File(...)):
    if not request.app.state.whisper:
        raise HTTPException(503, "STT service unavailable")

    content = await file.read()
    if not content:
        return {"text": "", "error": "No audio data received"}

    suffix = os.path.splitext(file.filename or "recording.m4a")[1] or ".m4a"
    temp_path = None
    try:
        with tempfile.NamedTemporaryFile(delete=False, suffix=suffix) as f:
            f.write(content)
            temp_path = f.name

        text = await anyio.to_thread.run_sync(
            _whisper_transcribe, request.app.state.whisper, temp_path
        )

        if not text:
            return {"text": "", "error": "No speech detected"}

        return {"text": text, "confidence": 0.9}

    except Exception as e:
        logger.error(f"STT transcription error: {e}")
        return {"text": "", "error": str(e)}
    finally:
        if temp_path and os.path.exists(temp_path):
            os.unlink(temp_path)


# =========================
# 12. HELPER AUTH
# =========================
@app.post("/helpers/signup", tags=["helpers"])
async def helpers_signup(data: dict):
    name = (data.get("name") or "").strip()
    email = (data.get("email") or "").strip().lower()
    password = data.get("password") or ""

    if not name or not email or not password:
        raise HTTPException(400, "Name, email, and password are required")
    if not _EMAIL_RE.match(email):
        raise HTTPException(400, "Please enter a valid email address")

    try:
        conn = sqlite3.connect(DB_PATH)
        cursor = conn.cursor()
        cursor.execute(
            """INSERT INTO helpers
               (name, email, password_hash, age, phone, address,
                emergency_contact_name, emergency_contact_phone, experience_level)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)""",
            (
                name,
                email,
                _hash_password(password),
                data.get("age"),
                data.get("phone"),
                data.get("address"),
                data.get("emergency_contact_name"),
                data.get("emergency_contact_phone"),
                data.get("experience_level"),
            ),
        )
        conn.commit()
        conn.close()
        return {"message": "Account created successfully"}
    except sqlite3.IntegrityError:
        raise HTTPException(400, "An account with this email already exists")


@app.post("/helpers/login", tags=["helpers"])
async def helpers_login(data: dict):
    email = (data.get("email") or "").strip().lower()
    password = data.get("password") or ""

    if not email or not password:
        raise HTTPException(400, "Email and password are required")
    if not _EMAIL_RE.match(email):
        raise HTTPException(400, "Please enter a valid email address")

    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    cursor.execute(
        "SELECT id, name, email, password_hash FROM helpers WHERE email=?",
        (email,),
    )
    row = cursor.fetchone()
    conn.close()

    if not row or not _verify_password(password, row[3]):
        raise HTTPException(401, "Invalid email or password")

    helper_id, name, helper_email, _ = row
    token = str(uuid.uuid4())
    helper_tokens[token] = helper_id

    return {
        "token": token,
        "helper": {"id": helper_id, "name": name, "email": helper_email},
    }


@app.get("/helpers/me", tags=["helpers"])
async def helpers_me(authorization: str = Header(None)):
    if not authorization or not authorization.startswith("Bearer "):
        raise HTTPException(401, "Authorization required")
    return _get_helper_by_token(authorization[7:])


@app.delete("/helpers/delete-account", tags=["helpers"])
async def helpers_delete_account(authorization: str = Header(None)):
    if not authorization or not authorization.startswith("Bearer "):
        raise HTTPException(401, "Authorization required")
    token = authorization[7:]
    helper = _get_helper_by_token(token)

    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    cursor.execute("DELETE FROM helpers WHERE id=?", (helper["id"],))
    conn.commit()
    conn.close()

    helper_tokens.pop(token, None)
    return {"message": "Account deleted successfully"}


@app.post("/helpers/oauth", tags=["helpers"])
async def helpers_oauth(data: dict):
    """Sign in or register via Google or Microsoft OAuth access token."""
    provider = (data.get("provider") or "").lower()
    access_token = (data.get("access_token") or "").strip()

    if not provider or not access_token:
        raise HTTPException(400, "provider and access_token are required")

    # Fetch user info from the provider
    userinfo_url = {
        "google": "https://www.googleapis.com/oauth2/v3/userinfo",
        "microsoft": "https://graph.microsoft.com/v1.0/me",
    }.get(provider)
    if not userinfo_url:
        raise HTTPException(400, f"Unsupported provider: {provider}")

    async with httpx.AsyncClient(timeout=10.0) as client:
        resp = await client.get(
            userinfo_url,
            headers={"Authorization": f"Bearer {access_token}"},
        )
    if resp.status_code != 200:
        raise HTTPException(401, "Could not verify OAuth token with provider")

    info = resp.json()
    if provider == "google":
        email = (info.get("email") or "").strip().lower()
        name = info.get("name") or email.split("@")[0]
    else:  # microsoft
        email = (info.get("mail") or info.get("userPrincipalName") or "").strip().lower()
        name = info.get("displayName") or email.split("@")[0]

    if not email:
        raise HTTPException(400, "Could not retrieve email from OAuth provider")

    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    cursor.execute("SELECT id, name, email FROM helpers WHERE email=?", (email,))
    row = cursor.fetchone()

    if row:
        helper_id, helper_name, helper_email = row
    else:
        # Auto-create account for new OAuth users (no password needed)
        cursor.execute(
            """INSERT INTO helpers (name, email, password_hash) VALUES (?, ?, ?)""",
            (name, email, ""),
        )
        conn.commit()
        helper_id = cursor.lastrowid
        helper_name, helper_email = name, email

    conn.close()

    token = str(uuid.uuid4())
    helper_tokens[token] = helper_id
    return {
        "token": token,
        "helper": {"id": helper_id, "name": helper_name, "email": helper_email},
    }


# =========================
# 13. COLLABORATION
# =========================
def normalize_session_id(sid: str) -> str:
    return sid.strip().upper() if sid else ""

@app.post("/collaboration/create-session", tags=["collaboration"])
async def create_collaboration_session():
    session_id = str(uuid.uuid4())[:8].upper()
    expires_at = datetime.now() + timedelta(hours=SESSION_EXPIRY_HOURS)

    collaboration_sessions[session_id] = {
        "created_at": datetime.now(),
        "last_active": datetime.now(),
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
            collaboration_sessions.pop(sid, None)
            return

        if role == "user" and session["user_ws"]:
            await websocket.close(1008, "User active")
            return
        if role == "guide" and session["guide_ws"]:
            await websocket.close(1008, "Guide active")
            return

        await websocket.accept()
        session[f"{role}_ws"] = websocket

        # Send connection confirmation with current session state
        await websocket.send_json({
            "type": "connected",
            "role": role,
            "session_id": sid,
            "user_connected": session["user_ws"] is not None,
            "guide_connected": session["guide_ws"] is not None,
        })

        # Notify the other side that this role has joined
        other_ws = session["guide_ws"] if role == "user" else session["user_ws"]
        if other_ws:
            if role == "user":
                await other_ws.send_json({"type": "user_connected", "session_id": sid})
            else:
                await other_ws.send_json({
                    "type": "guide_connected",
                    "helper_name": session.get("guide_name"),
                })

        try:
            while True:
                data = await websocket.receive_json()
                session["last_active"] = datetime.now()
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
            # Notify the other side that this role has left
            other_ws = session["guide_ws"] if role == "user" else session["user_ws"]
            if other_ws:
                disconnect_type = "user_disconnected" if role == "user" else "guide_disconnected"
                try:
                    await other_ws.send_json({"type": disconnect_type, "session_id": sid})
                except Exception:
                    pass


# =========================
# 14. DEV ENTRYPOINT
# =========================
if __name__ == "__main__":
    import uvicorn
    uvicorn.run("main:app", host="0.0.0.0", port=8000, reload=True)
