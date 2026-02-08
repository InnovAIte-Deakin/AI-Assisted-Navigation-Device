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
# Ensure backend root is in sys.path
CURRENT_FILE = Path(__file__).resolve()
BACKEND_DIR = CURRENT_FILE.parent
PROJECT_ROOT = Path(__file__).resolve().parents[3] 


if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

# ML_MODELS_DIR needed for loading weights
ML_MODELS_DIR = PROJECT_ROOT / "ML_models"
LLM_MODEL_PATH = PROJECT_ROOT / "ML_side/models/llama-3.2-1b-instruct-q4_k_m.gguf"

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# 2. IMPORTS
from fastapi import FastAPI, HTTPException, Query, WebSocket, WebSocketDisconnect, Depends, status
from fastapi.middleware.cors import CORSMiddleware
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from pydantic import BaseModel, EmailStr

# Internal Imports (The "Brain" & State)
from internal.state import collaboration_sessions, llm_brain
from slow_lane import SlowLaneBrain  
import internal.state as app_state # For setting the singleton

# Routers
from routers import audiobooks as audiobooks_router
from routers import ai_service as ai_router

# 3. CREATE APP
app = FastAPI(title="WalkBuddy Unified Backend")

# 4. MIDDLEWARE
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# 5. MOUNT ROUTERS
app.include_router(audiobooks_router.router)
app.include_router(ai_router.router) # The new Vision/Chat brain

# 6. CONSTANTS
SESSION_EXPIRY_HOURS = 1
MAX_FRAME_SIZE_BYTES = 400 * 1024  # 400KB
MIN_FRAME_INTERVAL_MS = 500  # 2 FPS max
DB_PATH = BACKEND_DIR / "helpers.db"

# 7. LIFECYCLE EVENTS (Startup/Shutdown)
def init_database():
    """Initialize SQLite database for helpers"""
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS helpers (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL,
            age INTEGER,
            email TEXT UNIQUE NOT NULL,
            phone TEXT,
            address TEXT,
            emergency_contact_name TEXT,
            emergency_contact_phone TEXT,
            experience_level TEXT,
            password_hash TEXT NOT NULL,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            last_login TIMESTAMP
        )
    """)
    
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS helper_sessions (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            helper_id INTEGER NOT NULL,
            token TEXT UNIQUE NOT NULL,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            expires_at TIMESTAMP NOT NULL,
            FOREIGN KEY (helper_id) REFERENCES helpers(id)
        )
    """)
    
    conn.commit()
    conn.close()
    logger.info("[Database] ✅ Database initialized")

async def cleanup_expired_sessions():
    """Background task to clean up expired sessions"""
    while True:
        try:
            now = datetime.now()
            # collaboration_sessions is imported from internal.state
            expired_sessions = [
                sid for sid, session in collaboration_sessions.items()
                if now > (session["created_at"] + timedelta(hours=SESSION_EXPIRY_HOURS))
            ]
            for sid in expired_sessions:
                session = collaboration_sessions.get(sid)
                if session:
                    # Close WebSocket connections if still open
                    if session["user_ws"]:
                        try:
                            await session["user_ws"].close()
                        except:
                            pass
                    if session["guide_ws"]:
                        try:
                            await session["guide_ws"].close()
                        except:
                            pass
                del collaboration_sessions[sid]
                logger.info(f"[Collaboration] Cleaned up expired session: {sid}")
        except Exception as e:
            logger.error(f"[Collaboration] Error in cleanup task: {e}")
        
        await asyncio.sleep(300)  # Check every 5 minutes

@app.on_event("startup")
async def startup_event():
    # A. Init Database
    init_database()

    # B. Load LLM Brain
    if os.path.exists(LLM_MODEL_PATH):
        logger.info(f"Loading Slow Lane LLM from {LLM_MODEL_PATH}...")
        try:
            # Set the global variable in the state module
            app_state.llm_brain = SlowLaneBrain(str(LLM_MODEL_PATH))
            logger.info("✅ Slow Lane LLM Ready.")
        except Exception as e:
            logger.error(f"❌ Failed to load LLM: {e}")
    else:
        logger.warning(f"⚠️ LLM not found at {LLM_MODEL_PATH}. /chat will fail.")

    # C. Start Background Tasks
    asyncio.create_task(cleanup_expired_sessions())

# ============================================================================
#  SECTION 8: AUTHENTICATION & HELPERS (Ported from ask_a_friend.py)
# ============================================================================
security = HTTPBearer()

class HelperSignup(BaseModel):
    name: str
    age: Optional[int] = None
    email: EmailStr
    phone: Optional[str] = None
    address: Optional[str] = None
    emergency_contact_name: Optional[str] = None
    emergency_contact_phone: Optional[str] = None
    experience_level: Optional[str] = None
    password: str

class HelperLogin(BaseModel):
    email: EmailStr
    password: str

class HelperResponse(BaseModel):
    id: int
    name: str
    age: Optional[int]
    email: str
    phone: Optional[str]
    address: Optional[str]
    emergency_contact_name: Optional[str]
    emergency_contact_phone: Optional[str]
    experience_level: Optional[str]
    created_at: str

class LoginResponse(BaseModel):
    token: str
    helper: HelperResponse
    expires_at: str

def hash_password(password: str) -> str:
    return hashlib.sha256(password.encode()).hexdigest()

def verify_password(password: str, password_hash: str) -> bool:
    return hash_password(password) == password_hash

def generate_token() -> str:
    return secrets.token_urlsafe(32)

def get_db_connection():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn

def get_helper_by_email(email: str) -> Optional[Dict]:
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM helpers WHERE email = ?", (email,))
    row = cursor.fetchone()
    conn.close()
    if row:
        return dict(row)
    return None

def get_helper_by_phone(phone: str) -> Optional[Dict]:
    if not phone: return None
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM helpers WHERE phone = ?", (phone,))
    row = cursor.fetchone()
    conn.close()
    if row:
        return dict(row)
    return None

def get_helper_by_token(token: str) -> Optional[Dict]:
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("""
        SELECT h.* FROM helpers h
        JOIN helper_sessions s ON h.id = s.helper_id
        WHERE s.token = ? AND s.expires_at > datetime('now')
    """, (token,))
    row = cursor.fetchone()
    conn.close()
    if row:
        return dict(row)
    return None

# --- Auth Routes ---
@app.post("/helpers/signup", response_model=LoginResponse, tags=['helpers'])
async def signup_helper(helper_data: HelperSignup):
    try:
        if get_helper_by_email(helper_data.email):
            raise HTTPException(400, "Email exists.")
        if helper_data.phone and get_helper_by_phone(helper_data.phone):
            raise HTTPException(400, "Phone exists.")
        
        password_hash = hash_password(helper_data.password)
        conn = get_db_connection()
        cursor = conn.cursor()
        cursor.execute("""
            INSERT INTO helpers (name, age, email, phone, address, emergency_contact_name, emergency_contact_phone, experience_level, password_hash) 
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (helper_data.name, helper_data.age, helper_data.email, helper_data.phone, helper_data.address, helper_data.emergency_contact_name, helper_data.emergency_contact_phone, helper_data.experience_level, password_hash))
        helper_id = cursor.lastrowid
        
        token = generate_token()
        expires_at = datetime.now() + timedelta(days=30)
        cursor.execute("INSERT INTO helper_sessions (helper_id, token, expires_at) VALUES (?, ?, ?)", (helper_id, token, expires_at))
        conn.commit()
        
        # Get full object
        cursor.execute("SELECT * FROM helpers WHERE id = ?", (helper_id,))
        helper_dict = dict(cursor.fetchone())
        conn.close()
        
        return LoginResponse(
            token=token,
            helper=HelperResponse(**helper_dict),
            expires_at=expires_at.isoformat()
        )
    except HTTPException: raise
    except Exception as e:
        logger.error(f"Signup error: {e}")
        raise HTTPException(500, f"Signup failed: {str(e)}")

@app.post("/helpers/login", response_model=LoginResponse, tags=['helpers'])
async def login_helper(login_data: HelperLogin):
    try:
        helper = get_helper_by_email(login_data.email)
        if not helper or not verify_password(login_data.password, helper["password_hash"]):
            raise HTTPException(401, "Invalid credentials")
        
        token = generate_token()
        expires_at = datetime.now() + timedelta(days=30)
        conn = get_db_connection()
        conn.execute("INSERT INTO helper_sessions (helper_id, token, expires_at) VALUES (?, ?, ?)", (helper["id"], token, expires_at))
        conn.execute("UPDATE helpers SET last_login = datetime('now') WHERE id = ?", (helper["id"],))
        conn.commit()
        conn.close()
        
        return LoginResponse(token=token, helper=HelperResponse(**helper), expires_at=expires_at.isoformat())
    except HTTPException: raise
    except Exception as e:
        raise HTTPException(500, f"Login failed: {e}")

@app.get("/helpers/me", response_model=HelperResponse, tags=['helpers'])
async def get_current_helper(credentials: HTTPAuthorizationCredentials = Depends(security)):
    helper = get_helper_by_token(credentials.credentials)
    if not helper: raise HTTPException(401, "Invalid token")
    return HelperResponse(**helper)

@app.post("/helpers/logout", tags=['helpers'])
async def logout_helper(credentials: HTTPAuthorizationCredentials = Depends(security)):
    conn = get_db_connection()
    conn.execute("DELETE FROM helper_sessions WHERE token = ?", (credentials.credentials,))
    conn.commit()
    conn.close()
    return {"message": "Logged out"}

@app.delete("/helpers/delete-account", tags=['helpers'])
async def delete_helper_account(credentials: HTTPAuthorizationCredentials = Depends(security)):
    helper = get_helper_by_token(credentials.credentials)
    if not helper: raise HTTPException(401, "Invalid token")
    
    conn = get_db_connection()
    try:
        conn.execute("DELETE FROM helper_sessions WHERE helper_id = ?", (helper["id"],))
        conn.execute("DELETE FROM helpers WHERE id = ?", (helper["id"],))
        conn.commit()
        return {"message": "Deleted"}
    finally:
        conn.close()

# ============================================================================
#  SECTION 9: NAVIGATION & GEOCODING (Ported from ask_a_friend.py)
# ============================================================================
class RoutingRequest(BaseModel):
    origin: List[float]
    destination: List[float]
    profile: str = "foot-walking"

@app.get("/geocode", tags=['routing'])
async def geocode_place(q: str = Query(..., description="Place name")):
    try:
        async with httpx.AsyncClient(timeout=10.0) as client:
            response = await client.get(
                "https://nominatim.openstreetmap.org/search",
                params={"q": q, "format": "json", "limit": 1, "addressdetails": 1},
                headers={"User-Agent": "WalkBuddie/1.0"}
            )
            if response.status_code == 200:
                data = response.json()
                if data:
                    res = data[0]
                    return {"name": res.get("display_name"), "lat": float(res.get("lat")), "lng": float(res.get("lon")), "address": res.get("address")}
                raise HTTPException(404, "Location not found")
            raise HTTPException(response.status_code, "Geocoding error")
    except Exception as e:
        raise HTTPException(500, f"Geocoding failed: {e}")

async def get_osm_route(origin: List[float], destination: List[float], profile: str):
    # (Implementation copied from original file - strictly OSM based)
    try:
        osrm_profile = {"foot-walking": "foot", "driving-car": "driving", "cycling-regular": "bike"}.get(profile, "foot")
        url = f"http://router.project-osrm.org/route/v1/{osrm_profile}/{origin[0]},{origin[1]};{destination[0]},{destination[1]}"
        
        async with httpx.AsyncClient(timeout=10.0) as client:
            resp = await client.get(url, params={"overview": "full", "geometries": "geojson", "steps": "true"}, headers={"User-Agent": "WalkBuddie/1.0"})
            if resp.status_code == 200:
                data = resp.json()
                if data.get("code") == "Ok" and data.get("routes"):
                    # Process OSRM response into Standard GeoJSON
                    route = data["routes"][0]
                    legs = route.get("legs", [])
                    geometry = route.get("geometry", {})
                    coordinates = geometry.get("coordinates", [])
                    
                    segments = []
                    coord_index = 0
                    for leg in legs:
                        leg_steps = []
                        for step in leg.get("steps", []):
                             # Extract step details...
                             # Simplified for brevity, assumes standard OSRM step structure
                             step_geom = step.get("geometry", {}).get("coordinates", [])
                             start_idx = coord_index
                             end_idx = coord_index + len(step_geom) if step_geom else coord_index + 1
                             leg_steps.append({
                                 "distance": step.get("distance", 0),
                                 "duration": step.get("duration", 0),
                                 "instruction": step.get("name", "Continue"),
                                 "way_points": [start_idx, end_idx]
                             })
                             if step_geom: coord_index += len(step_geom)
                        segments.append({"distance": leg.get("distance"), "duration": leg.get("duration"), "steps": leg_steps})
                    
                    return {
                        "type": "FeatureCollection",
                        "features": [{
                            "type": "Feature",
                            "geometry": {"type": "LineString", "coordinates": coordinates},
                            "properties": {"segments": segments}
                        }]
                    }
    except Exception as e:
        logger.error(f"Routing error: {e}")
    return None

@app.post("/routing", tags=['routing'])
async def get_route(request: RoutingRequest):
    # Try OSM
    osm_route = await get_osm_route(request.origin, request.destination, request.profile)
    if osm_route: return osm_route
    
    # Fallback (Mock) - Warn user
    logger.warning("Using fallback mock route.")
    return {
        "type": "FeatureCollection", 
        "features": [], 
        "properties": {"_warning": "Routing Failed. Please check internet connection."}
    }


# ============================================================================
#  SECTION 10: COLLABORATION / WEBSOCKETS (Updated to use Shared State)
# ============================================================================
def normalize_session_id(sid: str) -> str: return sid.strip().upper() if sid else ""
def validate_session_id(sid: str) -> bool: return len(normalize_session_id(sid)) == 8

@app.post("/collaboration/create-session", tags=['collaboration'])
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
    logger.info(f"[Collaboration] Created session {session_id}")
    return {"session_id": session_id, "expires_at": expires_at.isoformat()}

@app.get("/collaboration/session/{session_id}/status", tags=['collaboration'])
async def get_session_status(session_id: str):
    sid = normalize_session_id(session_id)
    if not validate_session_id(sid): raise HTTPException(400, "Invalid ID")
    
    session = collaboration_sessions.get(sid)
    if not session: raise HTTPException(404, "Session not found")
    
    return {
        "session_id": sid,
        "user_connected": session["user_ws"] is not None,
        "guide_connected": session["guide_ws"] is not None,
        "created_at": session["created_at"].isoformat()
    }

@app.websocket("/collaboration/ws/{session_id}/{role}")
async def collaboration_websocket(websocket: WebSocket, session_id: str, role: str):
    sid = normalize_session_id(session_id)
    if role not in ["user", "guide"]: 
        await websocket.close(1008, "Invalid role")
        return
    
    session = collaboration_sessions.get(sid)
    if not session:
        await websocket.close(1008, "Session not found")
        return

    # Check expiration
    if datetime.now() > (session["created_at"] + timedelta(hours=SESSION_EXPIRY_HOURS)):
         await websocket.close(1008, "Expired")
         del collaboration_sessions[sid]
         return

    # Connect
    if role == "user" and session["user_ws"]: await websocket.close(1008, "User active"); return
    if role == "guide" and session["guide_ws"]: await websocket.close(1008, "Guide active"); return

    await websocket.accept()
    if role == "user": session["user_ws"] = websocket
    else: session["guide_ws"] = websocket
    
    logger.info(f"[WS] {role} connected to {sid}")
    
    # Notify peer
    other_peer = session["guide_ws"] if role == "user" else session["user_ws"]
    if other_peer:
        await other_peer.send_json({"type": f"{role}_connected", "session_id": sid})
    
    try:
        while True:
            data = await websocket.receive_json()
            msg_type = data.get("type")
            
            if msg_type == "ping":
                await websocket.send_json({"type": "pong"})
                continue
            
            # Helper Info
            if role == "guide" and msg_type == "helper_info":
                session["guide_name"] = data.get("helper_name")
                if session["user_ws"]:
                    await session["user_ws"].send_json({"type": "guide_connected", "helper_name": session["guide_name"]})
            
            # Frame Forwarding (User -> Guide)
            elif role == "user" and msg_type == "frame":
                if session["guide_ws"]:
                    # Rate limiting logic could go here
                    await session["guide_ws"].send_json(data)
            
            # WebRTC Signaling (Offer/Answer/ICE)
            elif msg_type in ["webrtc_offer", "webrtc_answer", "webrtc_ice"]:
                target = session["guide_ws"] if role == "user" else session["user_ws"]
                if target: await target.send_json(data)
                
            # Guidance (Guide -> User)
            elif role == "guide" and msg_type == "guidance":
                 if session["user_ws"]:
                     await session["user_ws"].send_json(data)
                     
    except WebSocketDisconnect:
        logger.info(f"[WS] {role} disconnected {sid}")
    except Exception as e:
        logger.error(f"[WS] Error {sid}: {e}")
    finally:
        if role == "user": session["user_ws"] = None
        else: session["guide_ws"] = None
        
        # Notify disconnect
        other = session["guide_ws"] if role == "user" else session["user_ws"]
        if other:
            try: await other.send_json({"type": f"{role}_disconnected"})
            except: pass

# 11. RUN
if __name__ == "__main__":
    import uvicorn
    uvicorn.run("main:app", host="0.0.0.0", port=8000, reload=True)