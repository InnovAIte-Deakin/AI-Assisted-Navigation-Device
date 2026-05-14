from __future__ import annotations

from collections import deque
from dataclasses import dataclass, field
from typing import Deque, Dict, List, Optional, Tuple
import math
import uuid


def _center_from_bbox(bbox: Dict[str, int]) -> Tuple[float, float]:
    return (
        (bbox["x_min"] + bbox["x_max"]) / 2.0,
        (bbox["y_min"] + bbox["y_max"]) / 2.0,
    )


def _area_from_bbox(bbox: Dict[str, int]) -> float:
    return max(0, bbox["x_max"] - bbox["x_min"]) * max(0, bbox["y_max"] - bbox["y_min"])


def _iou(box_a: Dict[str, int], box_b: Dict[str, int]) -> float:
    x_left = max(box_a["x_min"], box_b["x_min"])
    y_top = max(box_a["y_min"], box_b["y_min"])
    x_right = min(box_a["x_max"], box_b["x_max"])
    y_bottom = min(box_a["y_max"], box_b["y_max"])

    inter_w = max(0, x_right - x_left)
    inter_h = max(0, y_bottom - y_top)
    inter_area = inter_w * inter_h
    if inter_area <= 0:
        return 0.0

    union = _area_from_bbox(box_a) + _area_from_bbox(box_b) - inter_area
    if union <= 0:
        return 0.0
    return inter_area / union


@dataclass
class TrackObservation:
    center_x: float
    center_y: float
    area: float


@dataclass
class TrackState:
    track_id: str
    category: str
    bbox: Dict[str, int]
    last_frame_index: int
    observations: Deque[TrackObservation] = field(default_factory=lambda: deque(maxlen=5))


class MotionTracker:
    def __init__(self, max_age_frames: int = 5):
        self.max_age_frames = max_age_frames
        self.frame_index = 0
        self.tracks: Dict[str, TrackState] = {}

    def update(
        self,
        detections: List[Dict],
        image_width: int,
        image_height: int,
    ) -> List[Dict]:
        self.frame_index += 1
        self._prune_stale_tracks()

        enriched: List[Dict] = []
        used_tracks: set[str] = set()

        for detection in detections:
            track = self._match_track(detection, image_width, image_height, used_tracks)
            if track is None:
                track = self._create_track(detection)

            used_tracks.add(track.track_id)
            self._update_track(track, detection)
            enriched.append(self._enrich_detection(detection, track, image_width))

        return enriched

    def _prune_stale_tracks(self) -> None:
        stale = [
            track_id
            for track_id, track in self.tracks.items()
            if self.frame_index - track.last_frame_index > self.max_age_frames
        ]
        for track_id in stale:
            del self.tracks[track_id]

    def _match_track(
        self,
        detection: Dict,
        image_width: int,
        image_height: int,
        used_tracks: set[str],
    ) -> Optional[TrackState]:
        bbox = detection["bbox"]
        center_x, center_y = _center_from_bbox(bbox)
        area = _area_from_bbox(bbox)
        diag = math.hypot(image_width, image_height) or 1.0
        max_distance = diag * 0.12

        best_track: Optional[TrackState] = None
        best_score = -1.0

        for track in self.tracks.values():
            if track.track_id in used_tracks or track.category != detection["category"]:
                continue

            prev_center_x, prev_center_y = _center_from_bbox(track.bbox)
            distance = math.hypot(center_x - prev_center_x, center_y - prev_center_y)
            if distance > max_distance:
                continue

            prev_area = _area_from_bbox(track.bbox) or 1.0
            area_ratio = max(area, prev_area) / min(area or 1.0, prev_area)
            if area_ratio > 4.5:
                continue

            overlap = _iou(bbox, track.bbox)
            score = (1.0 / (1.0 + distance)) + overlap
            if score > best_score:
                best_score = score
                best_track = track

        return best_track

    def _create_track(self, detection: Dict) -> TrackState:
        track_id = uuid.uuid4().hex[:8]
        track = TrackState(
            track_id=track_id,
            category=detection["category"],
            bbox=detection["bbox"],
            last_frame_index=self.frame_index,
        )
        self.tracks[track_id] = track
        return track

    def _update_track(self, track: TrackState, detection: Dict) -> None:
        bbox = detection["bbox"]
        center_x, center_y = _center_from_bbox(bbox)
        area = _area_from_bbox(bbox)

        track.category = detection["category"]
        track.bbox = bbox
        track.last_frame_index = self.frame_index
        track.observations.append(
            TrackObservation(center_x=center_x, center_y=center_y, area=area)
        )

    def _enrich_detection(
        self,
        detection: Dict,
        track: TrackState,
        image_width: int,
    ) -> Dict:
        observations = list(track.observations)
        defaults = {
            "track_id": track.track_id,
            "is_moving": False,
            "motion_direction": "unknown",
            "motion_magnitude": "low",
            "approaching": False,
        }
        if len(observations) < 2:
            return {**detection, **defaults}

        prev = observations[-2]
        curr = observations[-1]
        dx = curr.center_x - prev.center_x
        displacement = abs(dx)
        delta_area_ratio = ((curr.area - prev.area) / prev.area) if prev.area > 0 else 0.0

        moving = displacement >= image_width * 0.03 or abs(delta_area_ratio) >= 0.12
        approaching = delta_area_ratio >= 0.12

        current_region = detection.get("direction", "ahead")
        prev_region = self._region_from_center(prev.center_x, image_width)

        if not moving:
            motion_direction = "stable"
        elif approaching and current_region == "ahead":
            motion_direction = "toward_center"
        elif prev_region != "ahead" and current_region == "ahead":
            motion_direction = "toward_center"
        elif prev_region == "ahead" and current_region != "ahead":
            motion_direction = "away_from_center"
        elif dx > 0:
            motion_direction = "right"
        elif dx < 0:
            motion_direction = "left"
        else:
            motion_direction = "unknown"

        magnitude_score = max(displacement / max(image_width, 1), abs(delta_area_ratio))
        if magnitude_score >= 0.18:
            motion_magnitude = "high"
        elif magnitude_score >= 0.08:
            motion_magnitude = "medium"
        else:
            motion_magnitude = "low"

        return {
            **detection,
            "track_id": track.track_id,
            "is_moving": moving,
            "motion_direction": motion_direction,
            "motion_magnitude": motion_magnitude,
            "approaching": approaching,
        }

    @staticmethod
    def _region_from_center(center_x: float, image_width: int) -> str:
        if center_x < image_width / 3:
            return "left"
        if center_x > 2 * image_width / 3:
            return "right"
        return "ahead"
