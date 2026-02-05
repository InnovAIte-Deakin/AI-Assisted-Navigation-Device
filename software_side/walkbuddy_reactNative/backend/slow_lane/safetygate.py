from typing import Dict, List, Optional

HAZARD_KEYWORDS = {
    "stairs",
    "stair",
    "wall",
    "door",
    "person",
    "obstacle",
    "pole",
    "edge",
}


def extract_hazards(events: List[Dict]) -> List[str]:
    hazards = []
    for e in events:
        label = str(e.get("label", "")).lower()
        direction = str(e.get("direction", "")).lower()
        if any(h in label for h in HAZARD_KEYWORDS) and "ahead" in direction:
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
