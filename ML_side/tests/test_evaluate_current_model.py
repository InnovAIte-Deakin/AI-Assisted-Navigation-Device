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
    nt_per_image = [1, 2]
    speed = {"inference": 12.5}
    box = FakeMetricsBox()


class EightClassMetrics(FakeMetrics):
    nt_per_image = [1, 2, 3, 4, 5, 6, 7, 8]


class FakeModel:
    names = {0: "book", 1: "monitor"}

    def __init__(self) -> None:
        self.predict_sources: list[str] = []
        self.predict_arguments: list[dict[str, float | bool | str]] = []
        self.validation_arguments: dict[str, object] | None = None

    def predict(
        self, *, source: str, save: bool, verbose: bool, conf: float, iou: float
    ) -> list[FakeResult]:
        assert save is False
        assert verbose is False
        self.predict_sources.append(source)
        self.predict_arguments.append(
            {"source": source, "save": save, "verbose": verbose, "conf": conf, "iou": iou}
        )
        if Path(source).name == "broken.jpeg":
            raise RuntimeError("cannot decode image")
        return [FakeResult([FakeBox(1, 0.91, [1.0, 2.0, 3.0, 4.0])])]

    def val(self, **kwargs: object) -> FakeMetrics:
        self.validation_arguments = kwargs
        return FakeMetrics()


class EightClassMetricsModel(FakeModel):
    names = {index: f"class-{index}" for index in range(8)}

    def val(self, **kwargs: object) -> EightClassMetrics:
        self.validation_arguments = kwargs
        return EightClassMetrics()


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


def make_dataset_yaml(tmp_path: Path) -> Path:
    dataset_root = tmp_path / "local-data"
    split_counts = {"train": 1, "val": 3, "test": 5}
    for split, count in split_counts.items():
        images = dataset_root / split / "images"
        images.mkdir(parents=True)
        for index in range(count):
            (images / f"{split}-{index}.jpg").write_bytes(b"image")
    dataset_yaml = tmp_path / "dataset.yaml"
    dataset_yaml.write_text(
        f"path: {dataset_root.resolve().as_posix()}\n"
        "train: train/images\nval: val/images\ntest: test/images\n",
        encoding="utf-8",
    )
    return dataset_yaml


def run_labelled_evaluation(
    tmp_path: Path, model: FakeModel, **kwargs: object
) -> tuple[dict[str, object], Path]:
    """Evaluate a labelled dataset through the production entry point with a fake model."""
    output = tmp_path / "results"
    summary = evaluator.evaluate(
        model_path=make_model_file(tmp_path),
        dataset_yaml=make_dataset_yaml(tmp_path),
        output_path=output,
        yolo_loader=lambda _: model,
        **kwargs,
    )
    return summary, output


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

    fake_model = FakeModel()
    summary = evaluator.evaluate(
        model_path=model_path,
        images_path=images,
        output_path=output,
        operating_confidence=0.4,
        operating_iou=0.6,
        yolo_loader=lambda _: fake_model,
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
    assert predictions["schema_version"] == evaluator.EVALUATION_SCHEMA_VERSION
    assert predictions["tool"] == {"name": evaluator.TOOL_NAME, "version": evaluator.TOOL_VERSION}
    assert predictions["model"]["ordered_class_names"] == ["book", "monitor"]
    assert predictions["evaluation_settings"]["operating_point_inference"] == {
        "confidence": 0.4,
        "iou": 0.6,
        "save": False,
        "verbose": False,
    }
    assert predictions["metric_semantics"] is None
    assert fake_model.predict_arguments[1]["conf"] == 0.4
    assert fake_model.predict_arguments[1]["iou"] == 0.6
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
    assert not list(tmp_path.glob(".results.json.*.tmp"))


def test_dataset_yaml_validation_rejects_missing_and_download_directives(tmp_path: Path) -> None:
    with pytest.raises(evaluator.EvaluationError, match="Dataset YAML file is missing"):
        evaluator.validate_dataset_yaml_path(tmp_path / "missing.yaml")

    dataset_yaml = tmp_path / "data.yaml"
    dataset_yaml.write_text("download: https://example.invalid/data.zip\n", encoding="utf-8")
    with pytest.raises(evaluator.EvaluationError, match="downloads are refused"):
        evaluator.validate_dataset_yaml_path(dataset_yaml)


def test_labelled_validation_extracts_available_metrics(tmp_path: Path) -> None:
    model_path = make_model_file(tmp_path)
    dataset_yaml = make_dataset_yaml(tmp_path)
    output = tmp_path / "results"
    model = FakeModel()

    summary = evaluator.evaluate(
        model_path=model_path,
        dataset_yaml=dataset_yaml,
        output_path=output,
        yolo_loader=lambda _: model,
    )

    metrics_artifact = json.loads(
        (output / "validation_metrics.json").read_text(encoding="utf-8")
    )
    metrics = metrics_artifact["validation_metrics"]
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
    assert "conf" not in model.validation_arguments
    assert "iou" not in model.validation_arguments
    assert metrics_artifact["schema_version"] == evaluator.EVALUATION_SCHEMA_VERSION
    assert metrics_artifact["evaluation_settings"]["operating_point_inference"] is None
    assert metrics_artifact["evaluation_settings"]["validation_ap"]["confidence"] == "ultralytics_default_sweep"
    assert metrics_artifact["metric_semantics"] == evaluator.LABELLED_VALIDATION_METRIC_SEMANTICS


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


def test_labelled_evaluation_defaults_to_the_validation_split(tmp_path: Path) -> None:
    model = FakeModel()

    summary, _ = run_labelled_evaluation(tmp_path, model)

    assert model.validation_arguments is not None
    assert model.validation_arguments["split"] == "val"
    assert summary["dataset_split"] == "val"
    assert summary["evaluation_settings"]["validation_ap"]["dataset_split"] == "val"


def test_omitted_split_preserves_existing_validation_settings(tmp_path: Path) -> None:
    model = FakeModel()

    summary, _ = run_labelled_evaluation(tmp_path, model)

    arguments = model.validation_arguments
    assert arguments is not None
    assert arguments["plots"] is False
    assert arguments["save_json"] is False
    assert arguments["verbose"] is False
    assert arguments["exist_ok"] is True
    assert arguments["name"] == "ultralytics_validation"
    assert "conf" not in arguments
    assert "iou" not in arguments
    assert summary["mode"] == "labelled_validation"


@pytest.mark.parametrize("split", ["val", "test"])
def test_selected_split_is_forwarded_and_recorded(tmp_path: Path, split: str) -> None:
    model = FakeModel()

    summary, output = run_labelled_evaluation(tmp_path, model, dataset_split=split)

    assert model.validation_arguments is not None
    assert model.validation_arguments["split"] == split
    assert summary["dataset_split"] == split
    assert summary["mode"] == "labelled_validation"

    metrics_artifact = json.loads(
        (output / "validation_metrics.json").read_text(encoding="utf-8")
    )
    assert metrics_artifact["evaluation_settings"]["validation_ap"]["dataset_split"] == split
    assert metrics_artifact["validation_metrics"]["validation_image_count"] == {
        "val": 3,
        "test": 5,
    }[split]
    summary_artifact = json.loads((output / "summary.json").read_text(encoding="utf-8"))
    assert summary_artifact["dataset_split"] == split
    assert summary_artifact["evaluation_settings"]["validation_ap"]["dataset_split"] == split


def test_held_out_split_preserves_labelled_metric_extraction(tmp_path: Path) -> None:
    model = FakeModel()

    summary, output = run_labelled_evaluation(tmp_path, model, dataset_split="test")

    metrics = json.loads(
        (output / "validation_metrics.json").read_text(encoding="utf-8")
    )["validation_metrics"]
    assert metrics["precision"] == 0.625
    assert metrics["recall"] == 0.5
    assert metrics["mAP50"] == 0.575
    assert metrics["mAP50_95"] == 0.425
    assert metrics["validation_image_count"] == 5
    assert summary["metric_semantics"] == evaluator.LABELLED_VALIDATION_METRIC_SEMANTICS


def test_labelled_image_count_uses_selected_split_not_class_indexed_metrics(
    tmp_path: Path,
) -> None:
    model = EightClassMetricsModel()

    summary, output = run_labelled_evaluation(tmp_path, model, dataset_split="test")

    metrics = json.loads(
        (output / "validation_metrics.json").read_text(encoding="utf-8")
    )["validation_metrics"]
    assert len(EightClassMetrics.nt_per_image) == 8
    assert metrics["validation_image_count"] == 5
    assert summary["validation_metrics"]["validation_image_count"] == 5  # type: ignore[index]


def test_unresolvable_selected_split_records_none_without_metric_array_fallback(
    tmp_path: Path,
) -> None:
    model_path = make_model_file(tmp_path)
    dataset_root = tmp_path / "local-data"
    images = dataset_root / "val" / "images"
    images.mkdir(parents=True)
    (images / "val.jpg").write_bytes(b"image")
    dataset_yaml = tmp_path / "dataset.yaml"
    dataset_yaml.write_text(
        f"path: {dataset_root.resolve().as_posix()}\nval: val/images\n",
        encoding="utf-8",
    )

    summary = evaluator.evaluate(
        model_path=model_path,
        dataset_yaml=dataset_yaml,
        dataset_split="test",
        output_path=tmp_path / "results",
        yolo_loader=lambda _: EightClassMetricsModel(),
    )

    metrics = summary["validation_metrics"]
    assert metrics["validation_image_count"] is None  # type: ignore[index]
    assert any("selected 'test' dataset split is not declared" in note for note in metrics["metric_notes"])  # type: ignore[index]


def test_absolute_yaml_root_resolves_the_selected_split(tmp_path: Path) -> None:
    dataset_root = tmp_path / "dataset-root"
    test_images = dataset_root / "test-images"
    test_images.mkdir(parents=True)
    for index in range(4):
        (test_images / f"test-{index}.jpg").write_bytes(b"image")
    dataset_yaml = tmp_path / "descriptors" / "dataset.yaml"
    dataset_yaml.parent.mkdir()
    dataset_yaml.write_text(
        f"path: {dataset_root.resolve().as_posix()}\ntest: test-images\n",
        encoding="utf-8",
    )

    image_count, note = evaluator.count_selected_split_images(dataset_yaml, "test")

    assert image_count == 4
    assert note is None


def test_omitted_yaml_path_uses_the_yaml_parent(tmp_path: Path) -> None:
    dataset_yaml = tmp_path / "descriptors" / "dataset.yaml"
    test_images = dataset_yaml.parent / "test-images"
    test_images.mkdir(parents=True)
    for index in range(3):
        (test_images / f"test-{index}.jpg").write_bytes(b"image")
    dataset_yaml.write_text("test: test-images\n", encoding="utf-8")

    image_count, note = evaluator.count_selected_split_images(dataset_yaml, "test")

    assert image_count == 3
    assert note is None


def test_explicit_dot_yaml_path_uses_process_working_directory_not_yaml_parent(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    working_directory_images = tmp_path / "test-images"
    working_directory_images.mkdir()
    (working_directory_images / "runtime.jpg").write_bytes(b"image")
    dataset_yaml = tmp_path / "descriptors" / "dataset.yaml"
    dataset_yaml.parent.mkdir()
    yaml_parent_images = dataset_yaml.parent / "test-images"
    yaml_parent_images.mkdir()
    for index in range(5):
        (yaml_parent_images / f"wrong-{index}.jpg").write_bytes(b"image")
    dataset_yaml.write_text("path: .\ntest: test-images\n", encoding="utf-8")
    monkeypatch.chdir(tmp_path)

    image_count, note = evaluator.count_selected_split_images(dataset_yaml, "test")

    assert image_count == 1
    assert note is None


def test_missing_relative_yaml_path_uses_ultralytics_datasets_dir(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    datasets_dir = tmp_path / "ultralytics-datasets"
    test_images = datasets_dir / "candidate" / "test-images"
    test_images.mkdir(parents=True)
    for index in range(2):
        (test_images / f"test-{index}.jpg").write_bytes(b"image")
    dataset_yaml = tmp_path / "descriptors" / "dataset.yaml"
    dataset_yaml.parent.mkdir()
    dataset_yaml.write_text("path: candidate\ntest: test-images\n", encoding="utf-8")
    monkeypatch.chdir(tmp_path)
    monkeypatch.setattr(evaluator, "_ultralytics_datasets_dir", lambda: datasets_dir)

    image_count, note = evaluator.count_selected_split_images(dataset_yaml, "test")

    assert image_count == 2
    assert note is None


def test_pinned_image_formats_match_ultralytics_8_4_7_fallback(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(evaluator, "_runtime_image_formats", lambda: None)

    assert evaluator._image_formats() == {
        "avif",
        "bmp",
        "dng",
        "heic",
        "jp2",
        "jpeg",
        "jpeg2000",
        "jpg",
        "mpo",
        "png",
        "tif",
        "tiff",
        "webp",
    }


def test_installed_runtime_image_formats_are_preferred(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(evaluator, "_runtime_image_formats", lambda: frozenset({"runtime"}))

    assert evaluator._image_formats() == {"runtime"}


def test_selected_split_counts_pinned_supported_image_formats(tmp_path: Path) -> None:
    dataset_root = tmp_path / "dataset-root"
    test_images = dataset_root / "test-images"
    test_images.mkdir(parents=True)
    for suffix in (".avif", ".heic", ".jp2", ".jpeg2000", ".pfm", ".txt"):
        (test_images / f"sample{suffix}").write_bytes(b"image")
    dataset_yaml = tmp_path / "dataset.yaml"
    dataset_yaml.write_text(
        f"path: {dataset_root.resolve().as_posix()}\ntest: test-images\n",
        encoding="utf-8",
    )

    image_count, note = evaluator.count_selected_split_images(dataset_yaml, "test")

    assert image_count == 4
    assert note is None


def test_image_list_matches_ultralytics_relative_entry_rules(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    dataset_root = tmp_path / "dataset-root"
    list_directory = dataset_root / "lists"
    list_directory.mkdir(parents=True)
    (list_directory / "list-local.jpg").write_bytes(b"image")
    (tmp_path / "working-directory.jpg").write_bytes(b"image")
    image_list = list_directory / "test.txt"
    image_list.write_text(
        "./list-local.jpg\nworking-directory.jpg\nnot-an-image.txt\n",
        encoding="utf-8",
    )
    dataset_yaml = tmp_path / "dataset.yaml"
    dataset_yaml.write_text(
        f"path: {dataset_root.resolve().as_posix()}\ntest: lists/test.txt\n",
        encoding="utf-8",
    )
    monkeypatch.chdir(tmp_path)

    image_count, note = evaluator.count_selected_split_images(dataset_yaml, "test")

    assert image_count == 2
    assert note is None


@pytest.mark.parametrize("split", ["train", "TEST", "", "validation"])
def test_unsupported_python_api_split_is_rejected(tmp_path: Path, split: str) -> None:
    with pytest.raises(evaluator.EvaluationError, match="Dataset split must be one of"):
        evaluator.evaluate(
            model_path=make_model_file(tmp_path),
            dataset_yaml=make_dataset_yaml(tmp_path),
            dataset_split=split,
            output_path=tmp_path / "results",
            yolo_loader=lambda _: pytest.fail("loader must not be called"),
        )


def test_split_is_rejected_for_unlabelled_image_evaluation(tmp_path: Path) -> None:
    with pytest.raises(evaluator.EvaluationError, match="only to labelled dataset evaluation"):
        evaluator.evaluate(
            model_path=make_model_file(tmp_path),
            images_path=make_image_folder(tmp_path),
            dataset_split="test",
            output_path=tmp_path / "results",
            yolo_loader=lambda _: pytest.fail("loader must not be called"),
        )


def test_unlabelled_evaluation_is_unchanged_and_records_no_split(tmp_path: Path) -> None:
    model = FakeModel()
    output = tmp_path / "results"

    summary = evaluator.evaluate(
        model_path=make_model_file(tmp_path),
        images_path=make_image_folder(tmp_path),
        output_path=output,
        yolo_loader=lambda _: model,
    )

    assert summary["mode"] == "unlabelled_inference_audit"
    assert summary["evaluation_settings"]["validation_ap"] is None
    assert "dataset_split" not in summary
    assert model.validation_arguments is None
    predictions = json.loads((output / "predictions.json").read_text(encoding="utf-8"))
    assert predictions["evaluation_settings"]["validation_ap"] is None


@pytest.mark.parametrize("split", ["val", "test"])
def test_argparse_accepts_supported_splits(split: str) -> None:
    arguments = evaluator.parse_args(
        ["--model", "m.pt", "--dataset-yaml", "d.yaml", "--split", split, "--output", "out"]
    )

    assert arguments.split == split


def test_argparse_defaults_split_to_none_for_backward_compatibility() -> None:
    arguments = evaluator.parse_args(
        ["--model", "m.pt", "--dataset-yaml", "d.yaml", "--output", "out"]
    )

    assert arguments.split is None


@pytest.mark.parametrize("split", ["train", "TEST", "holdout"])
def test_argparse_rejects_unsupported_splits(split: str) -> None:
    with pytest.raises(SystemExit):
        evaluator.parse_args(
            ["--model", "m.pt", "--dataset-yaml", "d.yaml", "--split", split, "--output", "out"]
        )


def test_cli_forwards_the_selected_split_without_real_weights(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    model = FakeModel()
    monkeypatch.setattr(
        evaluator.model_inspector, "_get_yolo_loader", lambda: (lambda _: model)
    )
    output = tmp_path / "results"

    exit_code = evaluator.main(
        [
            "--model",
            str(make_model_file(tmp_path)),
            "--dataset-yaml",
            str(make_dataset_yaml(tmp_path)),
            "--split",
            "test",
            "--output",
            str(output),
        ]
    )

    assert exit_code == 0
    assert model.validation_arguments is not None
    assert model.validation_arguments["split"] == "test"
    summary_artifact = json.loads((output / "summary.json").read_text(encoding="utf-8"))
    assert summary_artifact["dataset_split"] == "test"


def test_cli_rejects_split_with_images_before_loading_a_model(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    exit_code = evaluator.main(
        [
            "--model",
            str(make_model_file(tmp_path)),
            "--images",
            str(make_image_folder(tmp_path)),
            "--split",
            "test",
            "--output",
            str(tmp_path / "results"),
        ]
    )

    assert exit_code == 1
    assert "only to labelled dataset evaluation" in capsys.readouterr().err
    assert not (tmp_path / "results").exists()


@pytest.mark.parametrize("split", ["val", "test"])
def test_artifacts_do_not_expose_absolute_dataset_paths(tmp_path: Path, split: str) -> None:
    model = FakeModel()

    _, output = run_labelled_evaluation(tmp_path, model, dataset_split=split)

    dataset_yaml = tmp_path / "dataset.yaml"
    for artifact in ("summary.json", "validation_metrics.json", "model_metadata.json"):
        text = (output / artifact).read_text(encoding="utf-8")
        assert str(dataset_yaml) not in text
        assert dataset_yaml.as_posix() not in text
        assert str(tmp_path) not in text
    summary_artifact = json.loads((output / "summary.json").read_text(encoding="utf-8"))
    assert summary_artifact["dataset_yaml_filename"] == "dataset.yaml"
