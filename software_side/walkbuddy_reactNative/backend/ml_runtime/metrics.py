"""Bounded, thread-safe inference metrics for the ML runtime."""

from __future__ import annotations

from collections import deque
from datetime import datetime, timezone
from math import ceil, isfinite
from threading import Lock
from typing import Any


class InferenceMetrics:
    """Keep a bounded, process-local record of completed inference timings."""

    def __init__(self, latency_window_capacity: int = 256) -> None:
        if latency_window_capacity < 1:
            raise ValueError("latency_window_capacity must be at least one")
        self._lock = Lock()
        self._latencies_ms: deque[float] = deque(maxlen=latency_window_capacity)
        self._attempts = 0
        self._successful_inferences = 0
        self._failed_inferences = 0
        self._active_inferences = 0
        self._processed_frames = 0
        self._dropped_frames = 0
        self._last_inference_at: str | None = None

    def begin_inference(self) -> None:
        """Record an inference attempt immediately before invoking the model."""
        with self._lock:
            self._attempts += 1
            self._active_inferences += 1

    def finish_inference(self, latency_ms: float, *, successful: bool) -> None:
        """Record a completed attempt and its elapsed inference duration."""
        try:
            duration = float(latency_ms)
        except (TypeError, ValueError):
            duration = 0.0
        if not isfinite(duration):
            duration = 0.0
        duration = max(0.0, duration)
        with self._lock:
            if self._active_inferences:
                self._active_inferences -= 1
            self._latencies_ms.append(duration)
            self._last_inference_at = datetime.now(timezone.utc).isoformat()
            if successful:
                self._successful_inferences += 1
                self._processed_frames += 1
            else:
                self._failed_inferences += 1

    def record_dropped_frame(self) -> None:
        """Record a frame only when the server deliberately drops one."""
        with self._lock:
            self._dropped_frames += 1

    def snapshot(self) -> dict[str, Any]:
        """Return a JSON-safe snapshot without exposing request-level data."""
        with self._lock:
            samples = sorted(self._latencies_ms)
            count = len(samples)
            return {
                "total_attempts": self._attempts,
                "successful_inferences": self._successful_inferences,
                "failed_inferences": self._failed_inferences,
                "active_inferences": self._active_inferences,
                "processed_frames": self._processed_frames,
                "dropped_frames": self._dropped_frames,
                "latest_latency_ms": self._latencies_ms[-1] if count else None,
                "mean_latency_ms": (sum(samples) / count) if count else None,
                "p50_latency_ms": self._percentile(samples, 0.50),
                "p95_latency_ms": self._percentile(samples, 0.95),
                "max_latency_ms": samples[-1] if count else None,
                "latency_window_size": count,
                "latency_window_capacity": self._latencies_ms.maxlen,
                "last_inference_at": self._last_inference_at,
            }

    @staticmethod
    def _percentile(samples: list[float], percentile: float) -> float | None:
        """Use the deterministic nearest-rank percentile for bounded samples."""
        if not samples:
            return None
        index = max(0, ceil(percentile * len(samples)) - 1)
        return samples[index]
