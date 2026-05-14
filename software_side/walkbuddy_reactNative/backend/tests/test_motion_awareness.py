from pathlib import Path
import importlib.util
import sys


BACKEND_DIR = Path(__file__).resolve().parents[1]
if str(BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(BACKEND_DIR))

SAFETYGATE_PATH = BACKEND_DIR / "slow_lane" / "safetygate.py"
spec = importlib.util.spec_from_file_location("motion_test_safetygate", SAFETYGATE_PATH)
safetygate = importlib.util.module_from_spec(spec)
assert spec is not None and spec.loader is not None
spec.loader.exec_module(safetygate)

from internal.motion_tracker import MotionTracker
from tts_service.message_reasoning import Detection, generate_guidance_message
from tts_service.tts_service import RiskLevel


def _detection(category: str, x_min: int, y_min: int, x_max: int, y_max: int, direction: str) -> dict:
    return {
        "category": category,
        "confidence": 0.9,
        "bbox": {
            "x_min": x_min,
            "y_min": y_min,
            "x_max": x_max,
            "y_max": y_max,
        },
        "direction": direction,
    }


def test_motion_tracker_reuses_track_id_for_same_object():
    tracker = MotionTracker()
    first = tracker.update([_detection("person", 80, 100, 180, 300, "left")], 640, 480)
    second = tracker.update([_detection("person", 110, 100, 210, 300, "left")], 640, 480)

    assert first[0]["track_id"] == second[0]["track_id"]
    assert second[0]["is_moving"] is True
    assert second[0]["motion_direction"] == "right"


def test_motion_tracker_ignores_small_jitter():
    tracker = MotionTracker()
    tracker.update([_detection("person", 200, 100, 300, 300, "ahead")], 640, 480)
    second = tracker.update([_detection("person", 206, 100, 306, 300, "ahead")], 640, 480)

    assert second[0]["is_moving"] is False
    assert second[0]["motion_direction"] == "stable"


def test_motion_tracker_marks_approaching_on_area_growth():
    tracker = MotionTracker()
    tracker.update([_detection("person", 250, 120, 320, 260, "ahead")], 640, 480)
    second = tracker.update([_detection("person", 230, 90, 350, 330, "ahead")], 640, 480)

    assert second[0]["is_moving"] is True
    assert second[0]["approaching"] is True
    assert second[0]["motion_direction"] == "toward_center"


def test_guidance_prefers_motion_specific_message():
    message = generate_guidance_message(
        Detection(
            category="person",
            confidence=0.92,
            bbox={"x_min": 260, "y_min": 120, "x_max": 380, "y_max": 360},
            direction="ahead",
            is_moving=True,
            approaching=True,
            motion_direction="toward_center",
        ),
        image_width=640,
        image_height=480,
    )

    assert message is not None
    assert message.message == "person approaching ahead"
    assert message.risk_level == RiskLevel.HIGH


def test_safety_gate_blocks_moving_object_entering_path():
    hazard = safetygate.safe_or_stop_recommendation([
        {
            "label": "person",
            "direction": "ahead",
            "confidence": 0.91,
            "is_moving": True,
            "approaching": False,
            "motion_direction": "toward_center",
        }
    ])

    assert hazard is not None
    assert "person moving toward_center ahead" in hazard
