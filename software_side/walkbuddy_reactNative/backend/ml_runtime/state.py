"""Single owner for process-local ML operational state."""

from __future__ import annotations

import re
from pathlib import Path
from threading import Lock
from typing import Any

from .metrics import InferenceMetrics
from .model_info import (
    ModelLineage,
    metadata_unavailable_model_lineage,
    unavailable_model_lineage,
)


_SHA256_PATTERN = re.compile(r"^[a-f0-9]{64}$")


class MLRuntimeState:
    """Hold model lineage and bounded metrics safely across worker threads."""

    def __init__(
        self,
        latency_window_capacity: int = 256,
        expected_model_sha256: str | None = None,
    ) -> None:
        self.metrics = InferenceMetrics(latency_window_capacity)
        self._model_lock = Lock()
        self._model_lineage: ModelLineage | None = None
        # This value is supplied once at startup by a controlled launcher. It
        # deliberately remains private so readiness never exposes deployment
        # configuration details.
        self._expected_model_sha256 = expected_model_sha256

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

    def readiness(self) -> dict[str, bool | str]:
        """Return the technical navigation-runtime readiness decision.

        Readiness is derived exclusively from startup lineage. It neither
        re-hashes the artifact nor represents production approval, model
        quality, or lifecycle authorization.
        """
        with self._model_lock:
            lineage = self._model_lineage
            expected_model_sha256 = self._expected_model_sha256

        if lineage is None:
            return {"ready": False, "reason": "not_initialized"}
        if not lineage.loaded:
            return {"ready": False, "reason": "model_not_loaded"}
        if (
            lineage.failure_category == "model_metadata_unavailable"
            or not isinstance(lineage.filename, str)
            or not lineage.filename
            or not isinstance(lineage.sha256, str)
            or not _SHA256_PATTERN.fullmatch(lineage.sha256)
            or not isinstance(lineage.num_classes, int)
            or lineage.num_classes != len(lineage.classes)
            or not lineage.classes
        ):
            return {"ready": False, "reason": "model_metadata_unavailable"}
        if lineage.taxonomy_compatible is not True:
            return {"ready": False, "reason": "taxonomy_incompatible"}
        if expected_model_sha256 is not None and (
            not _SHA256_PATTERN.fullmatch(expected_model_sha256)
            or lineage.sha256 != expected_model_sha256
        ):
            return {"ready": False, "reason": "model_identity_mismatch"}
        return {"ready": True, "reason": "ready"}
