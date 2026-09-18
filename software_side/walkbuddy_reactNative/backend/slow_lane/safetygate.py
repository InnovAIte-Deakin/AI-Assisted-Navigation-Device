from typing import Dict, List, Optional

from ml_contract.navigation_semantics import get_spoken_name, is_potential_hazard


# Existing non-MVP labels this gate historically recognized: ``stair``,
# ``wall``, ``obstacle``, and ``edge`` came from its general-hazard list;
# ``monitor``, ``whiteboard``, ``tv``, ``couch``, and ``books`` came from its
# legacy indoor-model list. They are compatibility labels, not aliases, and do
# not acquire canonical MVP semantics through this fallback.
_LEGACY_HAZARD_LABELS = frozenset(
    {"stair", "wall", "obstacle", "edge", "monitor", "whiteboard", "tv", "couch", "books"}
)

# Potential-hazard identity alone is not activation. Preserve the existing
# direction/confidence gate; proximity and temporal policy remain future seams.
HAZARD_CONFIDENCE_THRESHOLD = 0.5


def _is_hazard_identity(label: str) -> bool:
    """Match canonical/aliased MVP labels exactly, with explicit legacy support."""

    return is_potential_hazard(label) or label.strip().casefold() in _LEGACY_HAZARD_LABELS


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

        if _is_hazard_identity(label) and confidence >= HAZARD_CONFIDENCE_THRESHOLD:
            hazards.append(_format_hazard(e))
            continue

        if confidence >= HAZARD_CONFIDENCE_THRESHOLD and (approaching or (is_moving and crossing_center)):
            hazards.append(_format_hazard(e))
    return hazards


def _format_hazard(event: Dict) -> str:
    raw_label = event.get("label") or event.get("category") or "object"
    label = get_spoken_name(raw_label) or raw_label
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
