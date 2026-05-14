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
        label = str(e.get("label") or e.get("category", "")).lower()
        direction = str(e.get("direction", "")).lower()
        confidence = float(e.get("confidence", 0.0))
        is_ahead = "ahead" in direction or direction == "center"
        is_moving = bool(e.get("is_moving", False))
        approaching = bool(e.get("approaching", False))
        motion_direction = str(e.get("motion_direction", "")).lower()
        crossing_center = motion_direction in {"toward_center", "away_from_center"}

        if not is_ahead:
            continue

        if any(h in label for h in HAZARD_KEYWORDS) and confidence >= HAZARD_CONFIDENCE_THRESHOLD:
            hazards.append(_format_hazard(e))
            continue

        if confidence >= HAZARD_CONFIDENCE_THRESHOLD and (approaching or (is_moving and crossing_center)):
            hazards.append(_format_hazard(e))
    return hazards


def _format_hazard(event: Dict) -> str:
    label = event.get("label") or event.get("category") or "object"
    direction = event.get("direction", "ahead")
    if event.get("approaching"):
        return f"{label} approaching {direction}"
    if event.get("is_moving"):
        motion_direction = event.get("motion_direction", "moving")
        return f"{label} moving {motion_direction} {direction}"
    return f"{label} {direction}"


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
