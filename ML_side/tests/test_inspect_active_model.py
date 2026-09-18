"""Tests for the read-only active-model metadata inspector."""

from __future__ import annotations

import hashlib
import sys
from pathlib import Path

import pytest


TOOLS_DIR = Path(__file__).resolve().parents[1] / "tools"
sys.path.insert(0, str(TOOLS_DIR))

import inspect_active_model as inspector


class FakeModel:
    def __init__(self, names: object) -> None:
        self.names = names


def test_calculate_sha256_and_format_class_map(tmp_path: Path) -> None:
    model_path = tmp_path / "sample.pt"
    model_path.write_bytes(b"walkbuddy")

    assert inspector.calculate_sha256(model_path) == hashlib.sha256(
        b"walkbuddy"
    ).hexdigest()
    assert (
        inspector.format_class_map({0: "book", 2: "couch"})
        == "  0: book\n  2: couch"
    )


def test_inspect_model_reports_metadata_with_mocked_loader(tmp_path: Path) -> None:
    model_path = tmp_path / "sample.pt"
    model_path.write_bytes(b"walkbuddy")

    metadata = inspector.inspect_model(
        model_path,
        yolo_loader=lambda path: FakeModel({2: "couch", 0: "book"}),
    )

    assert metadata.path == model_path.resolve()
    assert metadata.size_bytes == len(b"walkbuddy")
    assert metadata.class_names == {0: "book", 2: "couch"}
    assert inspector.format_metadata(metadata).splitlines() == [
        f"Resolved model path: {model_path.resolve()}",
        "File size in bytes: 9",
        f"SHA-256 checksum: {hashlib.sha256(b'walkbuddy').hexdigest()}",
        "Number of classes: 2",
        "Class ID-to-name mapping:",
        "  0: book",
        "  2: couch",
    ]


def test_main_reports_a_missing_model_file(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    result = inspector.main([str(tmp_path / "missing.pt")])

    assert result == 1
    assert "Model file is missing:" in capsys.readouterr().err


def test_main_reports_a_path_that_is_not_a_file(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    result = inspector.main([str(tmp_path)])

    assert result == 1
    assert "Model path is not a file:" in capsys.readouterr().err


@pytest.mark.parametrize(
    "names",
    (
        None,
        {},
        {"not-an-id": "book"},
        {0: ""},
    ),
)
def test_malformed_model_names_are_rejected(tmp_path: Path, names: object) -> None:
    model_path = tmp_path / "sample.pt"
    model_path.write_bytes(b"walkbuddy")

    with pytest.raises(inspector.InspectionError, match="malformed model.names"):
        inspector.inspect_model(model_path, yolo_loader=lambda path: FakeModel(names))


def test_model_loading_failure_is_reported(tmp_path: Path) -> None:
    model_path = tmp_path / "sample.pt"
    model_path.write_bytes(b"walkbuddy")

    def failing_loader(path: str) -> FakeModel:
        raise RuntimeError("invalid model")

    with pytest.raises(inspector.InspectionError, match="Model loading failed"):
        inspector.inspect_model(model_path, yolo_loader=failing_loader)


def test_unavailable_ultralytics_is_reported(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    model_path = tmp_path / "sample.pt"
    model_path.write_bytes(b"walkbuddy")

    def unavailable_loader() -> object:
        raise inspector.InspectionError("Ultralytics dependency is unavailable.")

    monkeypatch.setattr(inspector, "_get_yolo_loader", unavailable_loader)

    with pytest.raises(inspector.InspectionError, match="Ultralytics dependency"):
        inspector.inspect_model(model_path)
