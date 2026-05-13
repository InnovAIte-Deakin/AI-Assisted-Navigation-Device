from typing import Dict, List, Optional

# Navigation hazards (general)
_NAV_HAZARDS = {
    "stairs", "stair", "wall", "door", "person", "obstacle", "pole", "edge",
}

# Indoor obstacles detected by the YOLO model (8 trained classes)
_YOLO_OBSTACLES = {
    "table", "monitor", "office-chair", "whiteboard", "tv", "couch", "books",
}

HAZARD_KEYWORDS = _NAV_HAZARDS | _YOLO_OBSTACLES

# Only flag detections above this confidence as hazards
HAZARD_CONFIDENCE_THRESHOLD = 0.5


def extract_hazards(events: List[Dict]) -> List[str]:
    hazards = []
    for e in events:
        label = str(e.get("label", "")).lower()
        direction = str(e.get("direction", "")).lower()
        confidence = float(e.get("confidence", 0.0))
        if (
            any(h in label for h in HAZARD_KEYWORDS)
            and "ahead" in direction
            and confidence >= HAZARD_CONFIDENCE_THRESHOLD
        ):
            hazards.append(f"{e.get('label')} {e.get('direction')}")
    return hazards


def safe_or_stop_recommendation(events: List[Dict]) -> Optional[str]:
    """
    Deterministic safety override.
    The LLM is NEVER allowed to override this.
    """
    hazards = extract_hazards(events)
    if hazards:
        return (
            "Not safe to move forward. Hazard ahead: "
            + ", ".join(hazards)
            + ". Stop and reassess or change direction."
        )
    return None
