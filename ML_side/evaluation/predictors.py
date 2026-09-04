"""Predictor implementations the pipeline can run against.

Two are provided:

- MockPredictor: reads pre-computed predictions from a fixture file and
  "predicts" by looking them up by image_id. This is what lets the eval
  pipeline be built and tested *before* a real navigation model exists,
  per the task brief.

- load_yolo_predict_fn: a thin wrapper around an Ultralytics YOLO model,
  the real integration point for once a trained candidate model lands.
  It's written and importable now, but not exercised by the test suite
  (no model weights are committed), so it's a documented stub in practice
  until there's a real .pt file to point it at. Its predict_fn takes an
  actual image file path, not an image_id, callers are responsible for
  supplying the real path for each ground-truth record (see run_eval.py).
"""

import json
import os
import sys
from pathlib import Path
from typing import Callable, List, Optional, Union

# Per review feedback, reuse ML_side/tools/inspect_active_model.py's own
# sha256 checksum and model.names normalisation instead of reimplementing
# them here. Tools in ML_side/tools/ import each other as bare top-level
# modules (e.g. evaluate_current_model.py does `import inspect_active_model
# as model_inspector`), so this pipeline puts that directory on sys.path
# the same way to follow the existing pattern rather than inventing a new
# one.
_CURRENT_DIR = os.path.dirname(os.path.abspath(__file__))
_TOOLS_DIR = os.path.normpath(os.path.join(_CURRENT_DIR, "..", "tools"))
if os.path.exists(_TOOLS_DIR) and _TOOLS_DIR not in sys.path:
    sys.path.append(_TOOLS_DIR)

import inspect_active_model as model_inspector  # noqa: E402


class MockPredictor:
    """Predicts by looking up canned predictions for an image_id.

    Used to develop and test the pipeline before a real model exists.
    predict(image_id) returns [] for any image_id with no entry in the
    fixture, rather than raising, so latency measurement can still run
    over a mixed batch.
    """

    def __init__(self, predictions_by_image: dict):
        self._predictions_by_image = predictions_by_image

    @classmethod
    def from_fixture(cls, path: Union[str, Path]) -> "MockPredictor":
        with open(path, "r") as f:
            records = json.load(f)
        by_image = {rec["image_id"]: rec.get("boxes", []) for rec in records}
        return cls(by_image)

    def predict(self, image_id: str) -> List[dict]:
        return self._predictions_by_image.get(image_id, [])

    def as_predict_fn(self) -> Callable[[str], List[dict]]:
        return self.predict


def load_yolo_predict_fn(model_path: Union[str, Path], conf: float = 0.25, iou: float = 0.45):
    """Loads a real Ultralytics YOLO model and returns a predict_fn(image_path).

    predict_fn expects an actual image file path (or anything Ultralytics'
    own model.predict() accepts as a source), not an image_id, callers must
    resolve each ground-truth record's image_id to a real path before
    calling this (see run_eval.py's image_paths_by_id handling).

    Not covered by automated tests, since no model weights are committed
    to the repo (per the task brief). Included so the same evaluate()/
    report pipeline used with MockPredictor works unchanged once a real
    candidate model is trained, just swap the predictor.
    """
    from ultralytics import YOLO  # imported lazily so this module stays
    # importable (and testable) in environments without ultralytics/model
    # weights installed.

    model = YOLO(str(model_path))
    # model.names is a {id: name} dict on most Ultralytics exports, but can
    # come back as a plain list depending on export version, reuse the
    # existing normaliser (inspect_active_model.normalise_class_names)
    # instead of assuming a dict shape here too.
    class_names = model_inspector.normalise_class_names(model.names)

    def predict_fn(image_path: Union[str, Path]) -> List[dict]:
        result = model.predict(str(image_path), conf=conf, iou=iou, verbose=False)[0]
        boxes = []
        if result.boxes is None:
            return boxes
        for box in result.boxes:
            cls_id = int(box.cls.item())
            x1, y1, x2, y2 = map(float, box.xyxy[0].tolist())
            boxes.append({
                "class": class_names.get(cls_id, str(cls_id)),
                "bbox": [x1, y1, x2, y2],
                "score": float(box.conf.item()),
            })
        return boxes

    predict_fn.class_names = class_names  # exposed so callers can attach model lineage
    return predict_fn


def compute_model_lineage(model_path: Union[str, Path], class_names: Optional[dict] = None) -> dict:
    """Build a small model-identity record (filename, size, sha256, classes).

    Field names intentionally mirror _model_lineage() in
    ML_side/tools/evaluate_current_model.py (filename, file_size_bytes,
    sha256, class_count, class_id_to_name, ordered_class_names), so a
    reviewer can confirm this supplementary error-analysis report and an
    evaluate_current_model.py run came from the exact same model file. The
    class fields are only included when class_names is given, unlike
    _model_lineage() (which always has a real class_names mapping to hand),
    since this pipeline may be asked to fingerprint a model file before any
    class list is known.

    The sha256 checksum itself is not recomputed by hand, it reuses
    ML_side/tools/inspect_active_model.calculate_sha256() rather than a
    second local implementation of the same file hashing.
    """
    path = Path(model_path).expanduser().resolve()
    sha256 = model_inspector.calculate_sha256(path)

    lineage = {
        "filename": path.name,
        "file_size_bytes": path.stat().st_size,
        "sha256": sha256,
    }
    if class_names:
        lineage["class_count"] = len(class_names)
        lineage["class_id_to_name"] = {str(k): v for k, v in class_names.items()}
        lineage["ordered_class_names"] = [class_names[k] for k in sorted(class_names)]
    return lineage
