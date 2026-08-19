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
  until there's a real .pt file to point it at.
"""

import json
from pathlib import Path
from typing import Callable, List, Union


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

    Not covered by automated tests, since no model weights are committed
    to the repo (per the task brief). Included so the same evaluate()/
    report pipeline used with MockPredictor works unchanged once a real
    candidate model is trained, just swap the predictor.
    """
    from ultralytics import YOLO  # imported lazily so this module stays
    # importable (and testable) in environments without ultralytics/model
    # weights installed.

    model = YOLO(str(model_path))
    class_names = model.names  # {id: name}, from the model itself

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

    return predict_fn
