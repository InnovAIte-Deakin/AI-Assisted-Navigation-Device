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
from fastapi import FastAPI, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
import gradio as gr

# ML model app builders
from ML_models.yolo_nav.live_gradio import build_yolo_app
from ML_models.live_ocr.live_ocr_tts import build_ocr_app

# 3. Create FastAPI app
app = FastAPI(title="AI Assist Backend")


# 4. CORS (required for mobile/web)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],        # Allow all while developing
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


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
        "main:app",
        host="0.0.0.0",
        port=8000,
        reload=True,
    )
