import sys
from pathlib import Path
import os
from typing import List, Optional
import httpx

# 1. Fix Python path so ML_models/ imports work reliably
CURRENT_FILE = Path(__file__).resolve()
BACKEND_DIR = CURRENT_FILE.parent
PROJECT_ROOT = BACKEND_DIR.parent

if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

ML_MODELS_DIR = PROJECT_ROOT / "ML_models"

# 2. Imports
from fastapi import FastAPI, HTTPException, Query, WebSocket, WebSocketDisconnect, Depends, status
from fastapi.middleware.cors import CORSMiddleware
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from pydantic import BaseModel, EmailStr
import gradio as gr
import uuid
import json
import asyncio
import sqlite3
import hashlib
import secrets
from datetime import datetime, timedelta
from typing import Dict, Optional

# ML model app builders
from ML_models.yolo_nav.live_gradio import build_yolo_app
from ML_models.live_ocr.live_ocr_tts import build_ocr_app

# Routers
from routers import audiobooks as audiobooks_router


# 3. Create FastAPI app
app = FastAPI(title="AI Assist Backend")
app.include_router(audiobooks_router.router)

# 3.1. Collaboration session storage (in-memory)
collaboration_sessions: Dict[str, Dict] = {}  # session_id -> {created_at, user_ws, guide_ws, last_frame_time}
SESSION_EXPIRY_HOURS = 1
MAX_FRAME_SIZE_BYTES = 400 * 1024  # 400KB
MIN_FRAME_INTERVAL_MS = 500  # 2 FPS max

# 3.2. Database setup for helpers
DB_PATH = BACKEND_DIR / "helpers.db"

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
    print("[Database] ✅ Database initialized")

# Initialize database on startup
init_database()

# Security
security = HTTPBearer()


# 4. CORS (required for mobile/web)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],        # Allow all while developing
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# 4.1. Helper authentication models
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

# 4.2. Password hashing utilities
def hash_password(password: str) -> str:
    """Hash password using SHA256 (simple, can upgrade to bcrypt later)"""
    return hashlib.sha256(password.encode()).hexdigest()

def verify_password(password: str, password_hash: str) -> bool:
    """Verify password against hash"""
    return hash_password(password) == password_hash

def generate_token() -> str:
    """Generate a secure random token"""
    return secrets.token_urlsafe(32)

# 4.3. Database helper functions
def get_db_connection():
    """Get database connection"""
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn

def get_helper_by_email(email: str) -> Optional[Dict]:
    """Get helper by email"""
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM helpers WHERE email = ?", (email,))
    row = cursor.fetchone()
    conn.close()
    if row:
        return dict(row)
    return None

def get_helper_by_phone(phone: str) -> Optional[Dict]:
    """Get helper by phone number"""
    if not phone:
        return None
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM helpers WHERE phone = ?", (phone,))
    row = cursor.fetchone()
    conn.close()
    if row:
        return dict(row)
    return None

def get_helper_by_token(token: str) -> Optional[Dict]:
    """Get helper by session token"""
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


# 5. Health check endpoint
@app.get("/health")
def health():
    return {"ok": True}


# 6. Routing API endpoint
class RoutingRequest(BaseModel):
    origin: List[float]  # [lng, lat]
    destination: List[float]  # [lng, lat]
    profile: str = "foot-walking"  # foot-walking, driving-car, cycling-regular


async def get_osm_route(origin: List[float], destination: List[float], profile: str = "foot-walking") -> dict:
    """Get route from OSM Routing API (free, no key required) - follows real roads"""
    try:
        origin_lng, origin_lat = origin
        dest_lng, dest_lat = destination
        
        # Map profile to OSRM profile
        osrm_profile = {
            "foot-walking": "foot",
            "driving-car": "driving",
            "cycling-regular": "bike"
        }.get(profile, "foot")
        
        # Use OSRM (Open Source Routing Machine) - free, no API key needed
        # This follows real roads and footpaths from OpenStreetMap
        url = f"http://router.project-osrm.org/route/v1/{osrm_profile}/{origin_lng},{origin_lat};{dest_lng},{dest_lat}"
        
        async with httpx.AsyncClient(timeout=10.0) as client:
            response = await client.get(
                url,
                params={
                    "overview": "full",  # Get full geometry
                    "geometries": "geojson",  # Return GeoJSON format
                    "steps": "true",  # Include turn-by-turn steps
                    "alternatives": "false"
                },
                headers={
                    "User-Agent": "WalkBuddie/1.0"
                }
            )
            
            if response.status_code == 200:
                data = response.json()
                if data.get("code") == "Ok" and data.get("routes"):
                    route = data["routes"][0]
                    legs = route.get("legs", [])
                    
                    # OSRM returns geometry as GeoJSON LineString with [lng, lat] coordinates
                    geometry = route.get("geometry", {})
                    if isinstance(geometry, dict) and "coordinates" in geometry:
                        coordinates = geometry["coordinates"]  # [[lng, lat], ...]
                    else:
                        # Fallback: if geometry is missing, extract from steps
                        coordinates = []
                        for leg in legs:
                            for step in leg.get("steps", []):
                                step_geometry = step.get("geometry", {})
                                if isinstance(step_geometry, dict) and "coordinates" in step_geometry:
                                    coords = step_geometry["coordinates"]
                                    if coords and coords not in coordinates:
                                        coordinates.extend(coords)
                    
                    if not coordinates:
                        print("[Routing] OSRM route has no geometry coordinates")
                        return None
                    
                    # Build segments with steps
                    segments = []
                    total_distance = 0
                    total_duration = 0
                    coord_index = 0
                    
                    for leg in legs:
                        leg_distance = leg.get("distance", 0)
                        leg_duration = leg.get("duration", 0)
                        total_distance += leg_distance
                        total_duration += leg_duration
                        
                        # Extract steps from leg
                        leg_steps = []
                        for step in leg.get("steps", []):
                            step_distance = step.get("distance", 0)
                            step_duration = step.get("duration", 0)
                            maneuver = step.get("maneuver", {})
                            
                            # Calculate way_points based on geometry indices
                            step_geometry = step.get("geometry", {})
                            step_coords = step_geometry.get("coordinates", []) if isinstance(step_geometry, dict) else []
                            start_idx = coord_index
                            end_idx = coord_index + len(step_coords) if step_coords else coord_index + 1
                            
                            leg_steps.append({
                                "distance": step_distance,
                                "duration": step_duration,
                                "type": maneuver.get("type", "turn"),
                                "instruction": step.get("name", "Continue"),
                                "name": step.get("name", ""),
                                "way_points": [start_idx, end_idx],
                                "maneuver_location": maneuver.get("location", [])
                            })
                            
                            if step_coords:
                                coord_index += len(step_coords)
                        
                        segments.append({
                            "distance": leg_distance,
                            "duration": leg_duration,
                            "steps": leg_steps
                        })
                    
                    # Return in OpenRouteService GeoJSON format
                    return {
                        "type": "FeatureCollection",
                        "features": [{
                            "type": "Feature",
                            "geometry": {
                                "type": "LineString",
                                "coordinates": coordinates  # [[lng, lat], ...] format
                            },
                            "properties": {
                                "segments": segments
                            }
                        }]
                    }
                else:
                    print(f"[Routing] OSRM returned error code: {data.get('code')}")
                    return None
        
        # If OSRM fails, return None to trigger error
        return None
        
    except Exception as e:
        print(f"[Routing] OSRM routing error: {e}")
        return None


def generate_mock_route(origin: List[float], destination: List[float]) -> dict:
    """DEPRECATED: Generate a simple mock route - DO NOT USE IN PRODUCTION
    
    This creates straight-line paths that cut through buildings.
    Use get_osm_route() instead for real road-following routes.
    """
    import math
    
    print("[Routing] WARNING: Using deprecated straight-line mock route. This will cut through buildings!")
    print("[Routing] Set ORS_API_KEY or ensure OSRM routing is available for real routes.")
    
    origin_lng, origin_lat = origin
    dest_lng, dest_lat = destination
    
    # Calculate distance
    def haversine_distance(lat1, lon1, lat2, lon2):
        R = 6371000  # Earth radius in meters
        phi1 = math.radians(lat1)
        phi2 = math.radians(lat2)
        delta_phi = math.radians(lat2 - lat1)
        delta_lambda = math.radians(lon2 - lon1)
        
        a = math.sin(delta_phi / 2) ** 2 + \
            math.cos(phi1) * math.cos(phi2) * math.sin(delta_lambda / 2) ** 2
        c = 2 * math.atan2(math.sqrt(a), math.sqrt(1 - a))
        
        return R * c
    
    distance = haversine_distance(origin_lat, origin_lng, dest_lat, dest_lng)
    duration = distance / 1.4  # Walking speed ~1.4 m/s
    
    # Generate geometry with intermediate points (STRAIGHT LINE - NOT REALISTIC)
    num_points = max(10, int(distance / 50))  # Point every ~50m
    geometry = []
    for i in range(num_points + 1):
        t = i / num_points
        lng = origin_lng + (dest_lng - origin_lng) * t
        lat = origin_lat + (dest_lat - origin_lat) * t
        geometry.append([lng, lat])
    
    # Generate steps
    steps = []
    step_distance = distance / 3  # 3 steps
    
    # Step 1: Depart
    steps.append({
        "distance": step_distance,
        "duration": step_distance / 1.4,
        "geometry": {
            "coordinates": geometry[:num_points//3 + 1]
        },
        "maneuver": {
            "type": "depart",
            "location": [origin_lng, origin_lat]
        },
        "name": "Route"
    })
    
    # Step 2: Continue
    steps.append({
        "distance": step_distance,
        "duration": step_distance / 1.4,
        "geometry": {
            "coordinates": geometry[num_points//3:2*num_points//3 + 1]
        },
        "maneuver": {
            "type": "straight",
            "location": geometry[num_points//2]
        },
        "name": "Route"
    })
    
    # Step 3: Arrive
    steps.append({
        "distance": step_distance,
        "duration": step_distance / 1.4,
        "geometry": {
            "coordinates": geometry[2*num_points//3:]
        },
        "maneuver": {
            "type": "arrive",
            "location": [dest_lng, dest_lat]
        },
        "name": "Route"
    })
    
    return {
        "type": "FeatureCollection",
        "features": [{
            "type": "Feature",
            "geometry": {
                "type": "LineString",
                "coordinates": geometry
            },
            "properties": {
                "segments": [{
                    "distance": step_distance,
                    "duration": step_distance / 1.4,
                    "steps": [{
                        "distance": step_distance,
                        "duration": step_distance / 1.4,
                        "type": step["maneuver"]["type"],
                        "instruction": f"Continue for {int(step_distance)} meters",
                        "name": step["name"],
                        "way_points": [i * num_points // 3, (i + 1) * num_points // 3],
                        "maneuver_location": step["maneuver"]["location"]
                    }]
                } for i, step in enumerate(steps)]
            }
        }]
    }


# 6.5. Geocoding API endpoint
@app.get("/api/geocode")
async def geocode_place(q: str = Query(..., description="Place name to geocode")):
    """Geocode a place name to coordinates using Nominatim"""
    try:
        async with httpx.AsyncClient(timeout=10.0) as client:
            response = await client.get(
                "https://nominatim.openstreetmap.org/search",
                params={
                    "q": q,
                    "format": "json",
                    "limit": 1,
                    "addressdetails": 1
                },
                headers={
                    "User-Agent": "WalkBuddie/1.0"
                }
            )
            
            if response.status_code == 200:
                data = response.json()
                if data and len(data) > 0:
                    result = data[0]
                    return {
                        "name": result.get("display_name", q),
                        "lat": float(result.get("lat", 0)),
                        "lng": float(result.get("lon", 0)),
                        "address": result.get("address", {})
                    }
                else:
                    raise HTTPException(status_code=404, detail="Location not found")
            else:
                raise HTTPException(status_code=response.status_code, detail="Geocoding service error")
                
    except httpx.TimeoutException:
        raise HTTPException(status_code=504, detail="Geocoding service timeout")
    except Exception as e:
        print(f"[Geocoding] Error: {e}")
        raise HTTPException(status_code=500, detail=f"Geocoding failed: {str(e)}")


@app.post("/api/routing")
async def get_route(request: RoutingRequest):
    """Get route from origin to destination using OpenRouteService, OSM Routing, or fallback"""
    
    # Priority 1: Try OpenRouteService API (if API key is available)
    ors_api_key = os.getenv("ORS_API_KEY")
    
    if ors_api_key:
        try:
            # Map profile names
            profile_map = {
                "foot-walking": "foot-walking",
                "driving-car": "driving-car",
                "cycling-regular": "cycling-regular"
            }
            ors_profile = profile_map.get(request.profile, "foot-walking")
            
            url = f"https://api.openrouteservice.org/v2/directions/{ors_profile}"
            
            async with httpx.AsyncClient(timeout=10.0) as client:
                response = await client.post(
                    url,
                    json={
                        "coordinates": [request.origin, request.destination],
                        "format": "geojson",
                        "geometry": True,  # Ensure full geometry is returned
                        "instructions": True  # Include turn-by-turn instructions
                    },
                    headers={
                        "Authorization": f"Bearer {ors_api_key}" if not ors_api_key.startswith("Bearer") else ors_api_key,
                        "Content-Type": "application/json"
                    }
                )
                
                if response.status_code == 200:
                    print("[Routing] Successfully fetched route from OpenRouteService (road-following)")
                    return response.json()
                else:
                    print(f"[Routing] OpenRouteService error: {response.status_code}, trying OSM routing")
        except Exception as e:
            print(f"[Routing] Error calling OpenRouteService: {e}, trying OSM routing")
    
    # Priority 2: Use OSM Routing API (free, no key required, follows real roads)
    print("[Routing] Using OSM Routing API (free, road-following)")
    osm_route = await get_osm_route(request.origin, request.destination, request.profile)
    
    if osm_route:
        print("[Routing] Successfully fetched route from OSM Routing (road-following)")
        return osm_route
    
    # Priority 3: Fallback to deprecated mock route (straight-line, NOT RECOMMENDED)
    print("[Routing] WARNING: All routing APIs failed. Using deprecated straight-line mock route.")
    print("[Routing] WARNING: This route will cut through buildings and is NOT suitable for navigation!")
    print("[Routing] RECOMMENDATION: Set ORS_API_KEY or ensure internet connectivity for OSM routing.")
    
    mock_route = generate_mock_route(request.origin, request.destination)
    
    # Add warning flag to response
    if isinstance(mock_route, dict) and "features" in mock_route:
        mock_route["properties"] = mock_route.get("properties", {})
        mock_route["properties"]["_warning"] = "STRAIGHT_LINE_MOCK_ROUTE - NOT SUITABLE FOR NAVIGATION"
    
    return mock_route


# 6.6. Collaboration API endpoints

# 5. Helper Authentication Endpoints
@app.post("/api/helpers/signup", response_model=LoginResponse)
async def signup_helper(helper_data: HelperSignup):
    """Sign up a new helper"""
    try:
        # Check if email already exists
        existing_by_email = get_helper_by_email(helper_data.email)
        if existing_by_email:
            raise HTTPException(
                status_code=400, 
                detail="An account with this email already exists. Please login instead."
            )
        
        # Check if phone number already exists (if provided)
        if helper_data.phone:
            existing_by_phone = get_helper_by_phone(helper_data.phone)
            if existing_by_phone:
                raise HTTPException(
                    status_code=400,
                    detail="An account with this phone number already exists. Please login instead."
                )
        
        # Hash password
        password_hash = hash_password(helper_data.password)
        
        # Insert into database
        conn = get_db_connection()
        cursor = conn.cursor()
        cursor.execute("""
            INSERT INTO helpers (
                name, age, email, phone, address,
                emergency_contact_name, emergency_contact_phone,
                experience_level, password_hash
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (
            helper_data.name,
            helper_data.age,
            helper_data.email,
            helper_data.phone,
            helper_data.address,
            helper_data.emergency_contact_name,
            helper_data.emergency_contact_phone,
            helper_data.experience_level,
            password_hash
        ))
        helper_id = cursor.lastrowid
        
        # Create session token
        token = generate_token()
        expires_at = datetime.now() + timedelta(days=30)  # 30 day session
        cursor.execute("""
            INSERT INTO helper_sessions (helper_id, token, expires_at)
            VALUES (?, ?, ?)
        """, (helper_id, token, expires_at))
        
        conn.commit()
        
        # Get created helper
        cursor.execute("SELECT * FROM helpers WHERE id = ?", (helper_id,))
        helper_row = cursor.fetchone()
        conn.close()
        
        helper_dict = dict(helper_row)
        helper_response = HelperResponse(
            id=helper_dict["id"],
            name=helper_dict["name"],
            age=helper_dict["age"],
            email=helper_dict["email"],
            phone=helper_dict["phone"],
            address=helper_dict["address"],
            emergency_contact_name=helper_dict["emergency_contact_name"],
            emergency_contact_phone=helper_dict["emergency_contact_phone"],
            experience_level=helper_dict["experience_level"],
            created_at=helper_dict["created_at"]
        )
        
        print(f"[Auth] ✅ Helper signed up: {helper_data.email}")
        return LoginResponse(
            token=token,
            helper=helper_response,
            expires_at=expires_at.isoformat()
        )
    except HTTPException:
        raise
    except Exception as e:
        print(f"[Auth] ❌ Signup error: {e}")
        raise HTTPException(status_code=500, detail=f"Signup failed: {str(e)}")

@app.post("/api/helpers/login", response_model=LoginResponse)
async def login_helper(login_data: HelperLogin):
    """Login helper"""
    try:
        # Get helper by email
        helper = get_helper_by_email(login_data.email)
        if not helper:
            raise HTTPException(status_code=401, detail="Invalid email or password")
        
        # Verify password
        if not verify_password(login_data.password, helper["password_hash"]):
            raise HTTPException(status_code=401, detail="Invalid email or password")
        
        # Create new session token
        token = generate_token()
        expires_at = datetime.now() + timedelta(days=30)
        
        conn = get_db_connection()
        cursor = conn.cursor()
        
        # Insert session
        cursor.execute("""
            INSERT INTO helper_sessions (helper_id, token, expires_at)
            VALUES (?, ?, ?)
        """, (helper["id"], token, expires_at))
        
        # Update last login
        cursor.execute("""
            UPDATE helpers SET last_login = datetime('now') WHERE id = ?
        """, (helper["id"],))
        
        conn.commit()
        conn.close()
        
        helper_response = HelperResponse(
            id=helper["id"],
            name=helper["name"],
            age=helper["age"],
            email=helper["email"],
            phone=helper["phone"],
            address=helper["address"],
            emergency_contact_name=helper["emergency_contact_name"],
            emergency_contact_phone=helper["emergency_contact_phone"],
            experience_level=helper["experience_level"],
            created_at=helper["created_at"]
        )
        
        print(f"[Auth] ✅ Helper logged in: {login_data.email}")
        return LoginResponse(
            token=token,
            helper=helper_response,
            expires_at=expires_at.isoformat()
        )
    except HTTPException:
        raise
    except Exception as e:
        print(f"[Auth] ❌ Login error: {e}")
        raise HTTPException(status_code=500, detail=f"Login failed: {str(e)}")

@app.get("/api/helpers/me", response_model=HelperResponse)
async def get_current_helper(credentials: HTTPAuthorizationCredentials = Depends(security)):
    """Get current authenticated helper"""
    token = credentials.credentials
    helper = get_helper_by_token(token)
    if not helper:
        raise HTTPException(status_code=401, detail="Invalid or expired token")
    
    return HelperResponse(
        id=helper["id"],
        name=helper["name"],
        age=helper["age"],
        email=helper["email"],
        phone=helper["phone"],
        address=helper["address"],
        emergency_contact_name=helper["emergency_contact_name"],
        emergency_contact_phone=helper["emergency_contact_phone"],
        experience_level=helper["experience_level"],
        created_at=helper["created_at"]
    )

@app.post("/api/helpers/logout")
async def logout_helper(credentials: HTTPAuthorizationCredentials = Depends(security)):
    """Logout helper (invalidate token)"""
    token = credentials.credentials
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("DELETE FROM helper_sessions WHERE token = ?", (token,))
    conn.commit()
    conn.close()
    print(f"[Auth] ✅ Helper logged out")
    return {"message": "Logged out successfully"}

@app.delete("/api/helpers/delete-account")
async def delete_helper_account(credentials: HTTPAuthorizationCredentials = Depends(security)):
    """Delete helper account and all associated data"""
    token = credentials.credentials
    helper = get_helper_by_token(token)
    if not helper:
        raise HTTPException(status_code=401, detail="Invalid or expired token")
    
    helper_id = helper["id"]
    conn = get_db_connection()
    cursor = conn.cursor()
    
    try:
        # Delete all sessions for this helper
        cursor.execute("DELETE FROM helper_sessions WHERE helper_id = ?", (helper_id,))
        
        # Delete helper account
        cursor.execute("DELETE FROM helpers WHERE id = ?", (helper_id,))
        
        conn.commit()
        print(f"[Auth] ✅ Helper account deleted: {helper['email']}")
        return {"message": "Account deleted successfully"}
    except Exception as e:
        conn.rollback()
        print(f"[Auth] ❌ Error deleting account: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to delete account: {str(e)}")
    finally:
        conn.close()

def normalize_session_id(session_id: str) -> str:
    """Normalize session ID: trim whitespace and convert to uppercase"""
    if not session_id:
        return ""
    return session_id.strip().upper()


def validate_session_id(session_id: str) -> bool:
    """Validate session ID format: exactly 8 alphanumeric characters"""
    normalized = normalize_session_id(session_id)
    return len(normalized) == 8 and normalized.isalnum()


@app.post("/collaboration/create-session")
async def create_collaboration_session():
    """Create a new collaboration session and return session ID"""
    session_id = str(uuid.uuid4())[:8].upper()  # 8-character code
    
    collaboration_sessions[session_id] = {
        "created_at": datetime.now(),
        "user_ws": None,
        "guide_ws": None,
        "guide_name": None,
        "last_frame_time": 0,
    }
    
    expires_at = datetime.now() + timedelta(hours=SESSION_EXPIRY_HOURS)
    print(f"[Collaboration] ✅ Created session: {session_id}, expires at {expires_at}")
    print(f"[Collaboration] Active sessions: {len(collaboration_sessions)}")
    
    return {
        "session_id": session_id,
        "expires_at": expires_at.isoformat(),
    }


@app.get("/collaboration/session/{session_id}/status")
async def get_collaboration_session_status(session_id: str):
    """Get status of a collaboration session"""
    # Normalize session ID
    normalized_id = normalize_session_id(session_id)
    
    # Validate format
    if not validate_session_id(normalized_id):
        print(f"[Collaboration] ❌ Invalid session ID format: '{session_id}' (normalized: '{normalized_id}')")
        raise HTTPException(status_code=400, detail=f"Invalid session code format. Must be 8 alphanumeric characters.")
    
    session = collaboration_sessions.get(normalized_id)
    
    if not session:
        print(f"[Collaboration] ❌ Session not found: '{normalized_id}' (from '{session_id}')")
        print(f"[Collaboration] Available sessions: {list(collaboration_sessions.keys())}")
        raise HTTPException(status_code=404, detail="Session not found. Please check the code and try again.")
    
    # Check if expired
    created_at = session["created_at"]
    expires_at = created_at + timedelta(hours=SESSION_EXPIRY_HOURS)
    
    if datetime.now() > expires_at:
        # Clean up expired session
        del collaboration_sessions[normalized_id]
        print(f"[Collaboration] ⏰ Session expired: {normalized_id}")
        raise HTTPException(status_code=410, detail="Session expired. Please ask the user to create a new session.")
    
    expires_in = int((expires_at - datetime.now()).total_seconds())
    user_connected = session["user_ws"] is not None
    guide_connected = session["guide_ws"] is not None
    
    print(f"[Collaboration] 📊 Status check for '{normalized_id}': user={user_connected}, guide={guide_connected}, expires_in={expires_in}s")
    
    return {
        "session_id": normalized_id,
        "user_connected": user_connected,
        "guide_connected": guide_connected,
        "created_at": created_at.isoformat(),
        "expires_in": expires_in,
    }


async def cleanup_expired_sessions():
    """Background task to clean up expired sessions"""
    while True:
        try:
            now = datetime.now()
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
                print(f"[Collaboration] Cleaned up expired session: {sid}")
        except Exception as e:
            print(f"[Collaboration] Error in cleanup task: {e}")
        
        await asyncio.sleep(300)  # Check every 5 minutes


@app.websocket("/collaboration/ws/{session_id}/{role}")
async def collaboration_websocket(websocket: WebSocket, session_id: str, role: str):
    """WebSocket endpoint for real-time collaboration"""
    
    # Normalize session ID
    normalized_id = normalize_session_id(session_id)
    
    # Validate role
    if role not in ["user", "guide"]:
        print(f"[Collaboration] ❌ Invalid role: {role}")
        await websocket.close(code=1008, reason="Invalid role")
        return
    
    # Validate session ID format
    if not validate_session_id(normalized_id):
        print(f"[Collaboration] ❌ Invalid session ID format: '{session_id}' (normalized: '{normalized_id}')")
        await websocket.close(code=1008, reason=f"Invalid session code format")
        return
    
    # Validate session exists
    session = collaboration_sessions.get(normalized_id)
    if not session:
        print(f"[Collaboration] ❌ Session not found: '{normalized_id}' (from '{session_id}')")
        print(f"[Collaboration] Available sessions: {list(collaboration_sessions.keys())}")
        await websocket.close(code=1008, reason="Session not found")
        return
    
    # Check if expired
    if datetime.now() > (session["created_at"] + timedelta(hours=SESSION_EXPIRY_HOURS)):
        await websocket.close(code=1008, reason="Session expired")
        del collaboration_sessions[normalized_id]
        return
    
    # Check if role already connected
    if role == "user" and session["user_ws"] is not None:
        await websocket.close(code=1008, reason="User already connected")
        return
    if role == "guide" and session["guide_ws"] is not None:
        await websocket.close(code=1008, reason="Guide already connected")
        return
    
    # Accept connection
    await websocket.accept()
    
    # Store WebSocket connection
    if role == "user":
        session["user_ws"] = websocket
    else:
        session["guide_ws"] = websocket
    
    user_connected = session["user_ws"] is not None
    guide_connected = session["guide_ws"] is not None
    room = f"askafriend:{normalized_id}"
    
    print(f"[Collaboration] ✅ {role.upper()} connected to session '{normalized_id}'")
    print(f"[Collaboration] ✅ Client joined room: {room}")
    print(f"[Collaboration] Session state: user={user_connected}, guide={guide_connected}, clients={int(user_connected) + int(guide_connected)}")
    
    # Notify other peer if already connected
    other_peer = session["guide_ws"] if role == "user" else session["user_ws"]
    if other_peer:
        try:
            print(f"[Collaboration] 📤 Notifying {('guide' if role == 'user' else 'user')} that {role} connected")
            message_data = {
                "type": f"{role}_connected",
                "session_id": normalized_id,
                "timestamp": datetime.now().isoformat(),
            }
            # Include helper name if guide is connecting
            if role == "guide" and session.get("guide_name"):
                message_data["helper_name"] = session["guide_name"]
            await other_peer.send_json(message_data)
        except Exception as e:
            print(f"[Collaboration] ⚠️ Failed to notify other peer: {e}")
    
    # Send connection confirmation with current session state
    await websocket.send_json({
        "type": "connected",
        "role": role,
        "session_id": normalized_id,
        "user_connected": user_connected,
        "guide_connected": guide_connected,
        "timestamp": datetime.now().isoformat(),
    })
    
    # If helper connects and user is already connected, send user_connected message
    if role == "guide" and user_connected:
        try:
            await websocket.send_json({
                "type": "user_connected",
                "session_id": normalized_id,
                "timestamp": datetime.now().isoformat(),
            })
        except Exception as e:
            print(f"[Collaboration] ⚠️ Failed to send user_connected to guide: {e}")
    
    try:
        while True:
            # Receive message
            data = await websocket.receive_json()
            msg_type = data.get("type")
            timestamp = datetime.now().isoformat()
            
            # Handle ping/pong
            if msg_type == "ping":
                await websocket.send_json({
                    "type": "pong",
                    "timestamp": timestamp,
                })
                continue
            
            # Handle disconnect
            if msg_type == "disconnect":
                break
            
            # Handle helper info (guide -> store name)
            if role == "guide" and msg_type == "helper_info":
                helper_name = data.get("helper_name")
                if helper_name:
                    session["guide_name"] = helper_name
                    print(f"[Collaboration] ✅ Stored helper name: {helper_name}")
                    # If user is already connected, notify them about helper name
                    if session["user_ws"]:
                        try:
                            await session["user_ws"].send_json({
                                "type": "guide_connected",
                                "session_id": normalized_id,
                                "helper_name": helper_name,
                                "timestamp": timestamp,
                            })
                            print(f"[Collaboration] 📤 Notified user about helper: {helper_name}")
                        except Exception as e:
                            print(f"[Collaboration] ⚠️ Failed to notify user about helper name: {e}")
                continue
            
            # Handle camera frame (user -> guide) - CHECKPOINT B
            if role == "user" and msg_type == "frame":
                # CHECKPOINT B.1 - Server received frame
                image_data = data.get("image", "")
                if image_data.startswith("data:image"):
                    # Extract base64 part
                    base64_data = image_data.split(",")[1] if "," in image_data else image_data
                else:
                    base64_data = image_data
                
                code = normalized_id
                ts = int(datetime.now().timestamp() * 1000)
                bytes_size = len(base64_data)
                print(f"[FRAME] recv {{code: {code}, bytes: {bytes_size}, ts: {ts}}}")
                
                # Rate limiting: check frame interval
                now_ms = int(datetime.now().timestamp() * 1000)
                last_frame = session.get("last_frame_time", 0)
                if now_ms - last_frame < MIN_FRAME_INTERVAL_MS:
                    print(f"[FRAME] ⏭️ Dropping frame (too fast, {now_ms - last_frame}ms since last)")
                    continue  # Drop frame if too fast
                
                # Size limit check
                # Approximate size (base64 is ~33% larger than binary)
                estimated_size = len(base64_data) * 3 / 4
                if estimated_size > MAX_FRAME_SIZE_BYTES:
                    print(f"[FRAME] ❌ Frame too large: {estimated_size} bytes (max {MAX_FRAME_SIZE_BYTES})")
                    await websocket.send_json({
                        "type": "error",
                        "message": "Frame too large. Please reduce camera quality.",
                        "timestamp": timestamp,
                    })
                    continue
                
                session["last_frame_time"] = now_ms
                
                # CHECKPOINT B.2 - Broadcast to helper
                room = f"askafriend:{normalized_id}"
                helper_ws = session.get("guide_ws")
                helper_count = 1 if helper_ws else 0
                
                print(f"[FRAME] broadcast room={room}, clients={helper_count}")
                
                # Forward to guide if connected
                if helper_ws:
                    try:
                        await helper_ws.send_json({
                            "type": "frame",
                            "image": image_data,
                            "session_id": normalized_id,
                            "timestamp": timestamp,
                        })
                        # Log every frame for debugging (throttled)
                        frame_count = session.get("frame_count", 0) + 1
                        session["frame_count"] = frame_count
                        if frame_count == 1 or frame_count % 8 == 0:  # Log once per second at ~8 FPS
                            print(f"[FRAME] ✅ Broadcasted frame #{frame_count} to helper (room={room}, clients={helper_count})")
                    except Exception as e:
                        print(f"[FRAME] ❌ Error forwarding frame: {e}")
                        # Guide disconnected, clean up
                        session["guide_ws"] = None
                else:
                    print(f"[FRAME] ⚠️ Guide not connected, dropping frame (room={room}, clients=0)")
                # If guide not connected, silently drop frame
            
            # Handle WebRTC offer (user -> guide)
            elif role == "user" and msg_type == "webrtc_offer":
                sdp_data = data.get("sdp")
                if not sdp_data:
                    print(f"[Collaboration] ⚠️ WebRTC offer received but no SDP")
                    continue
                
                room = f"askafriend:{normalized_id}"
                # Forward to guide if connected
                if session["guide_ws"]:
                    try:
                        print(f"[Collaboration] 📤 Forwarding WebRTC offer to guide (room={room})")
                        await session["guide_ws"].send_json({
                            "type": "webrtc_offer",
                            "sdp": sdp_data,
                            "session_id": normalized_id,
                            "timestamp": timestamp,
                        })
                    except Exception as e:
                        print(f"[Collaboration] ❌ Error forwarding WebRTC offer: {e}")
                else:
                    print(f"[Collaboration] ⚠️ Guide not connected, dropping WebRTC offer (room={room})")
            
            # Handle WebRTC answer (guide -> user)
            elif role == "guide" and msg_type == "webrtc_answer":
                sdp_data = data.get("sdp")
                if not sdp_data:
                    print(f"[Collaboration] ⚠️ WebRTC answer received but no SDP")
                    continue
                
                room = f"askafriend:{normalized_id}"
                # Forward to user if connected
                if session["user_ws"]:
                    try:
                        print(f"[Collaboration] 📤 Forwarding WebRTC answer to user (room={room})")
                        await session["user_ws"].send_json({
                            "type": "webrtc_answer",
                            "sdp": sdp_data,
                            "session_id": normalized_id,
                            "timestamp": timestamp,
                        })
                    except Exception as e:
                        print(f"[Collaboration] ❌ Error forwarding WebRTC answer: {e}")
                else:
                    print(f"[Collaboration] ⚠️ User not connected, dropping WebRTC answer (room={room})")
            
            # Handle WebRTC ICE candidate (both ways)
            elif msg_type == "webrtc_ice":
                candidate_data = data.get("candidate")
                if not candidate_data:
                    print(f"[Collaboration] ⚠️ WebRTC ICE candidate received but no candidate data")
                    continue
                
                room = f"askafriend:{normalized_id}"
                # Forward to other peer
                other_peer = session["guide_ws"] if role == "user" else session["user_ws"]
                if other_peer:
                    try:
                        print(f"[Collaboration] 📤 Forwarding WebRTC ICE candidate (room={room})")
                        await other_peer.send_json({
                            "type": "webrtc_ice",
                            "candidate": candidate_data,
                            "session_id": normalized_id,
                            "timestamp": timestamp,
                        })
                    except Exception as e:
                        print(f"[Collaboration] ❌ Error forwarding WebRTC ICE candidate: {e}")
                else:
                    print(f"[Collaboration] ⚠️ Other peer not connected, dropping ICE candidate (room={room})")
            
            # Handle video_received acknowledgment (guide -> user)
            elif msg_type == "video_received":
                print(f"[Collaboration] ✅ Helper confirmed video received for session '{normalized_id}'")
                # Forward to user if connected
                if session["user_ws"]:
                    try:
                        await session["user_ws"].send_json({
                            "type": "video_received",
                            "session_id": normalized_id,
                            "timestamp": timestamp,
                        })
                    except Exception as e:
                        print(f"[Collaboration] ❌ Error forwarding video_received: {e}")
            
            # Handle guidance (guide -> user)
            elif role == "guide" and msg_type == "guidance":
                guidance_text = data.get("text", "").strip()
                if not guidance_text:
                    print(f"[Collaboration] ⚠️ Guidance message received but empty")
                    continue
                
                print(f"[Collaboration] 📢 Forwarding guidance message to user: '{guidance_text}'")
                
                # Forward to user if connected
                if session["user_ws"]:
                    try:
                        await session["user_ws"].send_json({
                            "type": "guidance",
                            "text": guidance_text,
                            "message": guidance_text,  # Also include "message" for compatibility
                            "timestamp": timestamp,
                        })
                        print(f"[Collaboration] ✅ Guidance message forwarded successfully")
                    except Exception as e:
                        print(f"[Collaboration] ❌ Error forwarding guidance: {e}")
                        # User disconnected, clean up
                        session["user_ws"] = None
                else:
                    print(f"[Collaboration] ⚠️ User not connected, dropping guidance message")
    
    except WebSocketDisconnect:
        print(f"[Collaboration] 🔌 {role.upper()} disconnected from session '{normalized_id}'")
    except Exception as e:
        print(f"[Collaboration] ❌ Error in WebSocket handler for '{normalized_id}': {e}")
    finally:
        # Clean up connection
        if role == "user":
            session["user_ws"] = None
        else:
            session["guide_ws"] = None
        
        user_connected = session["user_ws"] is not None
        guide_connected = session["guide_ws"] is not None
        print(f"[Collaboration] Session '{normalized_id}' state after disconnect: user={user_connected}, guide={guide_connected}")
        
        # Notify other peer
        other_peer = session["guide_ws"] if role == "user" else session["user_ws"]
        if other_peer:
            try:
                print(f"[Collaboration] 📤 Notifying {('guide' if role == 'user' else 'user')} that {role} disconnected")
                await other_peer.send_json({
                    "type": f"{role}_disconnected",
                    "session_id": normalized_id,
                    "timestamp": datetime.now().isoformat(),
                })
            except Exception as e:
                print(f"[Collaboration] ⚠️ Failed to notify other peer of disconnect: {e}")


# Start background cleanup task
@app.on_event("startup")
async def startup_event():
    asyncio.create_task(cleanup_expired_sessions())


# 7. Mount YOLO Vision at /vision
yolo_blocks = build_yolo_app()
app = gr.mount_gradio_app(app, yolo_blocks, path="/vision")


# 7. Mount OCR at /ocr
ocr_blocks = build_ocr_app()
app = gr.mount_gradio_app(app, ocr_blocks, path="/ocr")


# 8. Allow `python main.py` to run the server
if __name__ == "__main__":
    import uvicorn

    uvicorn.run(
        "ask_a_friend:app",
        host="0.0.0.0",
        port=8003,
        reload=True,
    )