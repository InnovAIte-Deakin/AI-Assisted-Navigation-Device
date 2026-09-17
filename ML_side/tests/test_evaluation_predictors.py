import hashlib
import sys
import types
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))  # ML_side, so `evaluation` is importable

from evaluation.predictors import MockPredictor, compute_model_lineage

FIXTURE_DIR = Path(__file__).parent / "fixtures" / "eval"


def test_mock_predictor_from_fixture_returns_boxes_for_known_image():
    predictor = MockPredictor.from_fixture(FIXTURE_DIR / "predictions_small.json")
    boxes = predictor.predict("img001")
    classes = {b["class"] for b in boxes}
    assert classes == {"person", "door", "chair"}


def test_mock_predictor_returns_empty_list_for_unknown_image():
    predictor = MockPredictor.from_fixture(FIXTURE_DIR / "predictions_small.json")
    assert predictor.predict("no_such_image") == []


def test_mock_predictor_as_predict_fn_is_callable():
    predictor = MockPredictor.from_fixture(FIXTURE_DIR / "predictions_small.json")
    predict_fn = predictor.as_predict_fn()
    assert predict_fn("img002")[0]["class"] in {"table", "pole", "bicycle"}


def test_compute_model_lineage_reports_real_sha256_and_size(tmp_path):
    model_path = tmp_path / "candidate.pt"
    content = b"fake-model-weights-content"
    model_path.write_bytes(content)

    lineage = compute_model_lineage(model_path, class_names={0: "person", 1: "stairs"})

    assert lineage["filename"] == "candidate.pt"
    assert lineage["file_size_bytes"] == len(content)
    assert lineage["sha256"] == hashlib.sha256(content).hexdigest()
    assert lineage["class_count"] == 2
    assert lineage["ordered_class_names"] == ["person", "stairs"]


def test_compute_model_lineage_without_class_names_omits_class_fields(tmp_path):
    model_path = tmp_path / "candidate.pt"
    model_path.write_bytes(b"x")

    lineage = compute_model_lineage(model_path)

    assert "class_count" not in lineage
    assert "ordered_class_names" not in lineage


def test_load_yolo_predict_fn_normalises_model_names_given_as_a_list(monkeypatch):
    # Some Ultralytics export versions return model.names as a plain list
    # instead of a {id: name} dict, this must be normalised rather than
    # crashing on the first real .get(cls_id, ...) call.
    class FakeBox:
        def __init__(self, cls_id, bbox, score):
            self.cls = types.SimpleNamespace(item=lambda: cls_id)
            self.xyxy = [types.SimpleNamespace(tolist=lambda: bbox)]
            self.conf = types.SimpleNamespace(item=lambda: score)

    class FakeResult:
        def __init__(self, boxes):
            self.boxes = boxes

    class FakeModel:
        def __init__(self, path):
            self.names = ["person", "stairs"]  # list form, not dict

        def predict(self, source, conf, iou, verbose):
            return [FakeResult([FakeBox(1, [0.0, 0.0, 10.0, 10.0], 0.8)])]

    fake_ultralytics = types.ModuleType("ultralytics")
    fake_ultralytics.YOLO = FakeModel
    monkeypatch.setitem(sys.modules, "ultralytics", fake_ultralytics)

    from evaluation.predictors import load_yolo_predict_fn
    predict_fn = load_yolo_predict_fn("fake.pt")

    assert predict_fn.class_names == {0: "person", 1: "stairs"}
    boxes = predict_fn("image.jpg")
    assert boxes[0]["class"] == "stairs"
