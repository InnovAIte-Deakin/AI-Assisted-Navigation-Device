"""Single owner for process-local ML operational state."""

from __future__ import annotations

from pathlib import Path
from threading import Lock
from typing import Any

from .metrics import InferenceMetrics
from .model_info import (
    ModelLineage,
    metadata_unavailable_model_lineage,
    unavailable_model_lineage,
)


class MLRuntimeState:
    """Hold model lineage and bounded metrics safely across worker threads."""

    def __init__(self, latency_window_capacity: int = 256) -> None:
        self.metrics = InferenceMetrics(latency_window_capacity)
        self._model_lock = Lock()
        self._model_lineage: ModelLineage | None = None

    def set_model_lineage(self, lineage: ModelLineage) -> None:
        """Replace the startup lineage atomically after a successful model load."""
        with self._model_lock:
            self._model_lineage = lineage

    def set_model_load_failure(
        self, model_path: Path, load_duration_ms: float, failure_category: str
    ) -> None:
        """Record a failed startup without retaining exception text or paths."""
        self.set_model_lineage(
            unavailable_model_lineage(model_path, load_duration_ms, failure_category)
        )

    def set_model_metadata_failure(
        self, model_path: Path, load_duration_ms: float
    ) -> None:
        """Record unavailable lineage without marking a successfully loaded model down."""
        self.set_model_lineage(
            metadata_unavailable_model_lineage(model_path, load_duration_ms)
        )

    def model_info(self) -> dict[str, Any]:
        """Return safe lineage data, including pre-startup unavailable state."""
        with self._model_lock:
            if self._model_lineage is None:
                return {
                    "loaded": False,
                    "filename": None,
                    "sha256": None,
                    "size_bytes": None,
                    "num_classes": None,
                    "classes": [],
                    "taxonomy_compatible": None,
                    "load_duration_ms": None,
                    "loaded_at": None,
                    "runtime": {},
                    "failure_category": "not_initialized",
                }
            return self._model_lineage.as_dict()
