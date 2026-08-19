from pathlib import Path

from evaluation.predictors import MockPredictor

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
