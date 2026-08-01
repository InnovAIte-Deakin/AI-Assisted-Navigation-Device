"""Temporal persistence + cooldown filter for spoken detection announcements.

Ported from ML_side/notebooks/cohort-1/02_object_detection_training.ipynb,
the "Live camera with TTS" Gradio demo cell. The demo itself (Gradio webcam
UI, gTTS) doesn't fit the phone-camera + FastAPI architecture and wasn't
ported — but the actual filtering logic inside it solves a real, still-open
problem: `backend/tts_service/message_reasoning.py` currently caps
`process_detections()` at `max_messages=1` with no debouncing, so a
flickering detection can re-announce every single frame.

This module extracts just that stabilization logic (require a class to
appear in N of the last M frames before announcing it, then enforce a
cooldown before announcing again) so it can be wired into the real
detection pipeline instead of only existing inside a Colab demo. See ML
README, Future Directions Tier 2 ("Expand TTS to surface multiple
detections").
"""

import time
from collections import deque


class DetectionStabilizer:
    """Tracks per-class detection history across frames and decides when a
    class is "persistent" enough, and enough time has passed, to announce.

    Usage:
        stabilizer = DetectionStabilizer(class_names=["stairs", "person", "door"])
        for frame_detections in stream:
            # frame_detections: set/list of class names seen in this frame
            to_announce = stabilizer.update(frame_detections)
            if to_announce:
                speak(to_announce)
    """

    def __init__(self, class_names, persist_n=5, persist_m=3, cooldown_sec=3.0):
        """
        class_names: iterable of class name strings to track.
        persist_n: how many recent frames make up the rolling window.
        persist_m: how many of those N frames must contain the class before
            it's considered "persistent" (reduces single-frame flicker).
        cooldown_sec: minimum seconds between two announcements, regardless
            of class (matches the notebook's single global cooldown, not a
            per-class one — prevents rapid-fire announcements when several
            hazards appear at once).
        """
        self.persist_n = persist_n
        self.persist_m = persist_m
        self.cooldown_sec = cooldown_sec
        self.last_spoken = 0.0
        self.hist = {cls: deque(maxlen=persist_n) for cls in class_names}

    def _is_persistent(self, cls):
        window = self.hist[cls]
        return len(window) == self.persist_n and sum(window) >= self.persist_m

    def update(self, frame_classes):
        """Call once per frame with the set/list of class names detected in
        that frame. Returns the class name that should be announced now, or
        None if nothing qualifies (either nothing is persistent yet, or the
        cooldown hasn't elapsed).

        Priority order when multiple classes are persistent simultaneously:
        whichever was registered first in class_names at construction time
        (same behaviour as the notebook's dict iteration order — pass
        class_names in priority order, most urgent first).
        """
        frame_classes = set(frame_classes)
        for cls in self.hist:
            self.hist[cls].append(1 if cls in frame_classes else 0)

        now = time.time()
        if now - self.last_spoken <= self.cooldown_sec:
            return None

        for cls in self.hist:
            if self._is_persistent(cls):
                self.last_spoken = now
                # clear history so the same class doesn't immediately re-fire
                for c in self.hist:
                    self.hist[c].clear()
                return cls

        return None
