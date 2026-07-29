"""Tests for the read-only current-model baseline evaluation tool."""

from __future__ import annotations

import hashlib
import json
import sys
from pathlib import Path

import pytest


TOOLS_DIR = Path(__file__).resolve().parents[1] / "tools"
sys.path.insert(0, str(TOOLS_DIR))

import evaluate_current_model as evaluator


class FakeBox:
    def __init__(self, class_id: int, confidence: float, coordinates: list[float]) -> None:
        self.cls = [class_id]
        self.conf = [confidence]
        self.xyxy = [coordinates]


class FakeResult:
    def __init__(self, boxes: list[FakeBox]) -> None:
        self.boxes = boxes


class FakeMetricsBox:
    ap_class_index = [0, 1]
    p = [0.75, 0.5]
    r = [0.6, 0.4]
    ap50 = [0.7, 0.45]
    ap = [0.55, 0.3]


class FakeMetrics:
    results_dict = {
        "metrics/precision(B)": 0.625,
        "metrics/recall(B)": 0.5,
        "metrics/mAP50(B)": 0.575,
        "metrics/mAP50-95(B)": 0.425,
    }
    nt_per_image = [1, 2, 1]
    speed = {"inference": 12.5}
    box = FakeMetricsBox()


class FakeModel:
    names = {0: "book", 1: "monitor"}

    def __init__(self) -> None:
        self.predict_sources: list[str] = []
        self.validation_arguments: dict[str, object] | None = None

    def predict(self, *, source: str, save: bool, verbose: bool) -> list[FakeResult]:
        assert save is False
        assert verbose is False
        self.predict_sources.append(source)
        if Path(source).name == "broken.jpeg":
            raise RuntimeError("cannot decode image")
        return [FakeResult([FakeBox(1, 0.91, [1.0, 2.0, 3.0, 4.0])])]

    def val(self, **kwargs: object) -> FakeMetrics:
        self.validation_arguments = kwargs
        return FakeMetrics()


class MissingNamesModel:
    pass


def make_model_file(tmp_path: Path) -> Path:
    model_path = tmp_path / "best.pt"
    model_path.write_bytes(b"walkbuddy-model")
    return model_path


def make_image_folder(tmp_path: Path) -> Path:
    images = tmp_path / "images"
    images.mkdir()
    (images / "scene.jpg").write_bytes(b"image-one")
    (images / "broken.jpeg").write_bytes(b"image-two")
    (images / "notes.txt").write_text("unsupported", encoding="utf-8")
    return images


def test_discovers_supported_images_and_skips_unsupported_files(tmp_path: Path) -> None:
    images = make_image_folder(tmp_path)

    discovery = evaluator.discover_images(images)

    assert [path.name for path in discovery.images] == ["broken.jpeg", "scene.jpg"]
    assert [path.name for path in discovery.skipped_files] == ["notes.txt"]


def test_empty_image_folder_is_rejected(tmp_path: Path) -> None:
    images = tmp_path / "images"
    images.mkdir()
    (images / "notes.txt").write_text("unsupported", encoding="utf-8")

    with pytest.raises(evaluator.EvaluationError, match="No supported images found"):
        evaluator.discover_images(images)


def test_missing_model_is_rejected_before_loading(tmp_path: Path) -> None:
    images = make_image_folder(tmp_path)

    with pytest.raises(evaluator.EvaluationError, match="Model file is missing"):
        evaluator.evaluate(
            model_path=tmp_path / "missing.pt",
            images_path=images,
            output_path=tmp_path / "output",
            yolo_loader=lambda _: pytest.fail("loader must not be called"),
        )


def test_metadata_uses_checksum_and_model_class_mapping(tmp_path: Path) -> None:
    model_path = make_model_file(tmp_path)

    metadata, _ = evaluator.load_model_and_metadata(model_path, lambda _: FakeModel())

    assert metadata.sha256 == hashlib.sha256(b"walkbuddy-model").hexdigest()
    assert metadata.class_names == {0: "book", 1: "monitor"}


def test_model_loading_and_metadata_failures_are_readable(tmp_path: Path) -> None:
    model_path = make_model_file(tmp_path)

    with pytest.raises(evaluator.EvaluationError, match="Model loading failed"):
        evaluator.load_model_and_metadata(
            model_path, lambda _: (_ for _ in ()).throw(RuntimeError("corrupt"))
        )

    with pytest.raises(evaluator.EvaluationError, match="malformed model.names"):
        evaluator.load_model_and_metadata(model_path, lambda _: MissingNamesModel())


def test_unlabelled_audit_serialises_predictions_and_preserves_source_images(
    tmp_path: Path,
) -> None:
    model_path = make_model_file(tmp_path)
    images = make_image_folder(tmp_path)
    output = tmp_path / "results"
    before = {path.name: path.read_bytes() for path in images.iterdir()}

    summary = evaluator.evaluate(
        model_path=model_path,
        images_path=images,
        output_path=output,
        yolo_loader=lambda _: FakeModel(),
    )

    predictions = json.loads((output / "predictions.json").read_text(encoding="utf-8"))
    assert summary["total_processed_images"] == 1
    assert summary["failed_image_count"] == 1
    assert summary["skipped_file_count"] == 1
    assert summary["detection_counts_by_class"] == {"monitor": 1}
    assert predictions["images"][0]["detections"] == [
        {
            "bbox_xyxy": [1.0, 2.0, 3.0, 4.0],
            "class_id": 1,
            "class_name": "monitor",
            "confidence": 0.91,
        }
    ]
    assert "not precision, recall, or mAP" in predictions["result_label"]
    assert {path.name: path.read_bytes() for path in images.iterdir()} == before
    assert not list(output.glob("*.jpg"))
    assert (output / "model_metadata.json").is_file()
    assert (output / "summary.json").is_file()
    assert (output / "baseline_report.md").is_file()


def test_non_empty_output_requires_overwrite(tmp_path: Path) -> None:
    model_path = make_model_file(tmp_path)
    images = make_image_folder(tmp_path)
    output = tmp_path / "results"
    output.mkdir()
    (output / "old.json").write_text("{}", encoding="utf-8")

    with pytest.raises(evaluator.EvaluationError, match="Output directory is not empty"):
        evaluator.evaluate(
            model_path=model_path,
            images_path=images,
            output_path=output,
            yolo_loader=lambda _: FakeModel(),
        )

    evaluator.evaluate(
        model_path=model_path,
        images_path=images,
        output_path=output,
        overwrite=True,
        yolo_loader=lambda _: FakeModel(),
    )
    assert (output / "old.json").is_file()


def test_output_write_failure_is_readable(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    def fail_write(*_: object, **__: object) -> None:
        raise OSError("simulated write failure")

    monkeypatch.setattr(Path, "write_text", fail_write)

    with pytest.raises(evaluator.EvaluationError, match="Output write failed"):
        evaluator._write_json(tmp_path / "results.json", {"result": "baseline"})


def test_dataset_yaml_validation_rejects_missing_and_download_directives(tmp_path: Path) -> None:
    with pytest.raises(evaluator.EvaluationError, match="Dataset YAML file is missing"):
        evaluator.validate_dataset_yaml_path(tmp_path / "missing.yaml")

    dataset_yaml = tmp_path / "data.yaml"
    dataset_yaml.write_text("download: https://example.invalid/data.zip\n", encoding="utf-8")
    with pytest.raises(evaluator.EvaluationError, match="downloads are refused"):
        evaluator.validate_dataset_yaml_path(dataset_yaml)


def test_labelled_validation_extracts_available_metrics(tmp_path: Path) -> None:
    model_path = make_model_file(tmp_path)
    dataset_yaml = tmp_path / "data.yaml"
    dataset_yaml.write_text("path: local-data\ntrain: images\nval: images\n", encoding="utf-8")
    output = tmp_path / "results"
    model = FakeModel()

    summary = evaluator.evaluate(
        model_path=model_path,
        dataset_yaml=dataset_yaml,
        output_path=output,
        yolo_loader=lambda _: model,
    )

    metrics = json.loads((output / "validation_metrics.json").read_text(encoding="utf-8"))
    assert summary["mode"] == "labelled_validation"
    assert metrics["precision"] == 0.625
    assert metrics["recall"] == 0.5
    assert metrics["mAP50"] == 0.575
    assert metrics["mAP50_95"] == 0.425
    assert metrics["validation_image_count"] == 3
    assert metrics["per_class_results"]["0"]["class_name"] == "book"
    assert model.validation_arguments is not None
    assert model.validation_arguments["data"] == str(dataset_yaml.resolve())
    assert model.validation_arguments["plots"] is False
    assert model.validation_arguments["save_json"] is False


def test_main_reports_a_readable_error(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    images = make_image_folder(tmp_path)

    result = evaluator.main(
        [
            "--model",
            str(tmp_path / "missing.pt"),
            "--images",
            str(images),
            "--output",
            str(tmp_path / "results"),
        ]
    )

    assert result == 1
    assert "Evaluation failed: Model file is missing" in capsys.readouterr().err
