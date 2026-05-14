from collections import deque
from typing import Any, Deque, Dict, Optional


class NavigationMemory:
    """
    Text-only rolling memory buffer.
    Stores semantic events from the Fast Lane.
    """

    def __init__(self, max_events: int = 200):
        self.buffer: Deque[Dict] = deque(maxlen=max_events)

    def add_event(
        self,
        label: str,
        direction: str,
        distance_m: Optional[float],
        confidence: float,
        **extra: Any,
    ):
        event = {
            "label": label,
            "direction": direction,
            "distance_m": distance_m,
            "confidence": confidence,
        }
        event.update(extra)
        self.buffer.append(event)

    def to_context_text(self, n: int = 30) -> str:
        """
        Convert last n events into text lines for LLM context.
        """
        lines = []
        for e in list(self.buffer)[-n:]:
            dist = (
                f"~{e['distance_m']:.1f}m"
                if e.get("distance_m") is not None
                else "unknown distance"
            )
            lines.append(
                f"- {e['label']} {e['direction']}, {dist} "
                f"(conf {e['confidence']:.2f}, moving={e.get('is_moving', False)}, "
                f"approaching={e.get('approaching', False)})"
            )
        return "\n".join(lines)
