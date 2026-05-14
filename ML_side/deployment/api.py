"""
AI Navigation API - ML Stream
FastAPI service exposing navigation intelligence to mobile/hardware streams
"""

from fastapi import FastAPI, UploadFile, File
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from typing import List, Optional
import random
import time
import uvicorn

app = FastAPI(
    title="AI Navigation API",
    description="ML stream navigation service for AI-Assisted Navigation Device",
    version="2.0.0"
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

# ── Models ────────────────────────────────────────────────────────────────────

OBJECT_PRIORITY = {
    # Critical — immediate hazard or evacuation route
    "stairs":            5,
    "emergency-exit":    5,
    # High — moving hazard or emergency equipment
    "person":            4,
    "fire-extinguisher": 4,
    # Medium — navigation aids
    "door":              3,
    "elevator":          3,
    "handrail":          3,
    # Low — informational
    "signage":           2,
    "whiteboard":        2,
    "tv":                2,
    # Minimal — static furniture
    "book":              1,
    "books":             1,
    "monitor":           1,
    "office-chair":      1,
    "table":             1,
}

PRIORITY_LABELS = {5: "CRITICAL", 4: "HIGH", 3: "MEDIUM", 2: "LOW", 1: "MINIMAL"}


class DetectedObject(BaseModel):
    class_name: str
    confidence: float
    position: str           # "left", "center", "right"
    distance_estimate: str  # "near", "medium", "far"
    priority: int = 1
    priority_label: str = "MINIMAL"

class NavigationRequest(BaseModel):
    location: Optional[str] = "Library"
    user_intent: Optional[str] = "Navigate safely"
    detections: Optional[List[DetectedObject]] = []

class NavigationResponse(BaseModel):
    direction: str
    guidance: str
    safety_level: str       # "low", "medium", "high"
    obstacles: List[str]
    environment_type: str
    confidence: float
    processing_time_ms: float
    highest_priority_object: str
    highest_priority_level: int
    highest_priority_label: str

# ── Dummy Navigation Algorithm ─────────────────────────────────────────────────

OBJECT_CLASSES = list(OBJECT_PRIORITY.keys())  # derived from priority map — no duplication

ENVIRONMENTS = ["computer_lab", "study_area", "reading_area", "hallway", "entrance"]

def dummy_detect_objects() -> List[DetectedObject]:
    """Simulate YOLO object detection"""
    n = random.randint(1, 4)
    positions = ["left", "center", "right"]
    distances = ["near", "medium", "far"]

    objects = []
    for _ in range(n):
        name = random.choice(OBJECT_CLASSES)
        p    = OBJECT_PRIORITY.get(name, 1)
        objects.append(DetectedObject(
            class_name=name,
            confidence=round(random.uniform(0.60, 0.97), 2),
            position=random.choice(positions),
            distance_estimate=random.choice(distances),
            priority=p,
            priority_label=PRIORITY_LABELS[p],
        ))
    # Return sorted highest priority first
    return sorted(objects, key=lambda o: o.priority, reverse=True)

def dummy_navigation_algorithm(detections: List[DetectedObject], location: str) -> dict:
    """
    Dummy navigation algorithm simulating full ML pipeline:
    Detection → Semantic Mapping → Pathfinding → LLM Guidance
    """

    # Simulate processing time (real model would take 30-500ms)
    time.sleep(random.uniform(0.05, 0.15))

    # Sort detections by priority (already done in dummy_detect_objects, but safe to re-sort)
    detections = sorted(detections, key=lambda d: d.priority, reverse=True)

    center_obstacles = [d for d in detections if d.position == "center"]
    left_obstacles   = [d for d in detections if d.position == "left"]
    right_obstacles  = [d for d in detections if d.position == "right"]

    # Highest priority object across all detections
    top = detections[0]

    # Direction & guidance — driven by priority first
    if top.priority == 5:
        direction = "stop"
        guidance  = f"CRITICAL: {top.class_name.upper()} detected. Stop and assess your surroundings immediately."
    elif top.priority == 4:
        direction = "caution"
        guidance  = f"Caution: {top.class_name} detected nearby. Slow down and navigate carefully."
    elif not center_obstacles:
        direction = "straight"
        guidance  = "Path is clear. Continue moving forward."
    elif len(left_obstacles) <= len(right_obstacles):
        direction = "left"
        guidance  = f"Move left to avoid {center_obstacles[0].class_name} blocking your path."
    else:
        direction = "right"
        guidance  = f"Move right to avoid {center_obstacles[0].class_name} blocking your path."

    # Override guidance with specific object rules (informational additions)
    if any(d.class_name == "elevator" for d in detections) and top.priority < 4:
        guidance += " Elevator detected nearby — can take you to another floor."
    elif any(d.class_name == "door" and d.position == "center" for d in detections) and top.priority < 4:
        guidance = "Door ahead. Push or pull to open and continue through."

    # Safety level from highest priority
    if top.priority >= 5 or (top.priority >= 4 and top.distance_estimate == "near"):
        safety_level = "high"
    elif center_obstacles or top.priority >= 3:
        safety_level = "medium"
    else:
        safety_level = "low"

    # Environment classification
    class_names = [d.class_name for d in detections]
    if "monitor" in class_names:
        env = "computer_lab"
    elif "whiteboard" in class_names:
        env = "study_area"
    elif "books" in class_names or "book" in class_names:
        env = "reading_area"
    elif "stairs" in class_names or "elevator" in class_names:
        env = "transition_zone"
    else:
        env = random.choice(ENVIRONMENTS)

    return {
        "direction":               direction,
        "guidance":                guidance,
        "safety_level":            safety_level,
        "obstacles":               [d.class_name for d in center_obstacles],
        "environment_type":        env,
        "confidence":              round(random.uniform(0.78, 0.96), 2),
        "highest_priority_object": top.class_name,
        "highest_priority_level":  top.priority,
        "highest_priority_label":  top.priority_label,
    }

# ── Endpoints ─────────────────────────────────────────────────────────────────

@app.get("/")
def root():
    return {
        "service": "AI Navigation API",
        "version": "2.0.0",
        "status":  "running",
        "streams": ["ML Engine", "Mobile App", "Backend Integration"],
        "docs":    "/docs"
    }

@app.get("/health")
def health():
    return {"status": "healthy", "model": "dummy_v2", "classes": 15}

@app.post("/navigate", response_model=NavigationResponse)
def navigate(request: NavigationRequest):
    """
    Main navigation endpoint.
    Accepts optional detections or generates dummy ones.
    Returns direction, guidance, safety level.
    """
    start = time.time()

    # Use provided detections or generate dummy ones
    detections = request.detections if request.detections else dummy_detect_objects()

    # Run navigation algorithm
    result = dummy_navigation_algorithm(detections, request.location)

    elapsed = round((time.time() - start) * 1000, 2)

    return NavigationResponse(
        **result,
        processing_time_ms=elapsed
    )

@app.post("/detect")
def detect_only():
    """
    Simulate object detection only (no guidance).
    Returns list of detected objects with confidence scores.
    """
    detections = dummy_detect_objects()
    return {
        "detections": [d.dict() for d in detections],
        "count":      len(detections),
        "model":      "YOLOv8s-15class-dummy"
    }

@app.get("/classes")
def get_classes():
    """Return all 15 supported object classes"""
    return {
        "total":   len(OBJECT_CLASSES),
        "classes": OBJECT_CLASSES,
        "sprint1": OBJECT_CLASSES[:7],
        "sprint2": OBJECT_CLASSES[7:]
    }

@app.get("/demo")
def demo():
    """Run a full demo navigation scenario"""
    scenarios = [
        {"location": "Computer Lab",  "user_intent": "Find an empty seat"},
        {"location": "Reading Area",  "user_intent": "Find the exit"},
        {"location": "Hallway",       "user_intent": "Navigate to the elevator"},
        {"location": "Study Area",    "user_intent": "Navigate safely"},
    ]
    scenario   = random.choice(scenarios)
    detections = dummy_detect_objects()
    result     = dummy_navigation_algorithm(detections, scenario["location"])

    return {
        "scenario":   scenario,
        "detections": [d.dict() for d in detections],
        "navigation": result
    }

# ── Entry Point ───────────────────────────────────────────────────────────────

if __name__ == "__main__":
    uvicorn.run("api:app", host="0.0.0.0", port=8000, reload=True)
