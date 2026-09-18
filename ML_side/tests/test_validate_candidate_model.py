"""Tests for offline candidate detection-model validation."""

from __future__ import annotations

import hashlib
import json
import sys
from collections.abc import Iterator, Mapping
from pathlib import Path
from typing import Any

import pytest


TOOLS_DIR = Path(__file__).resolve().parents[1] / "tools"
sys.path.insert(0, str(TOOLS_DIR))

import validate_candidate_model as validator


APPROVED_NAMES = [name for _, name in validator.APPROVED_TAXONOMY]


class FakeCandidateModel:
    def __init__(
        self,
        names: object | None = None,
        *,
        task: object = "detect",
        smoke_error: Exception | None = None,
    ) -> None:
        self.names = dict(enumerate(APPROVED_NAMES)) if names is None else names
        self.task = task
        self.smoke_error = smoke_error
        self.predict_calls: list[dict[str, object]] = []

    def predict(self, **kwargs: object) -> list[object]:
        self.predict_calls.append(kwargs)
        if self.smoke_error is not None:
            raise self.smoke_error
        return [object()]


class MissingTaskModel:
    names = dict(enumerate(APPROVED_NAMES))

    def predict(self, **_: object) -> list[object]:
        return [object()]


class EmptyDetectionModel(FakeCandidateModel):
    def predict(self, **kwargs: object) -> list[object]:
        self.predict_calls.append(kwargs)
        return []


class DuplicateIdNames(Mapping[object, object]):
    """Mapping-shaped model.names payload with duplicate normalized class IDs."""

    def __iter__(self) -> Iterator[object]:
        return iter(())

    def __len__(self) -> int:
        return 0

    def __getitem__(self, _: object) -> object:
        raise KeyError

    def items(self) -> list[tuple[object, object]]:  # type: ignore[override]
        return [("0", "person"), (0, "stairs")]


def make_candidate(tmp_path: Path, contents: bytes = b"candidate-model") -> Path:
    path = tmp_path / "candidate.pt"
    path.write_bytes(contents)
    return path


def make_smoke_image(tmp_path: Path) -> Path:
    path = tmp_path / "smoke.jpg"
    path.write_bytes(b"not-decoded-by-fake")
    return path


def statuses(report: Mapping[str, object]) -> dict[str, str]:
    return {
        str(check["name"]): str(check["status"])
        for check in report["checks"]  # type: ignore[index]
    }


def test_approved_candidate_passes_and_does_not_modify_artifact(tmp_path: Path) -> None:
    candidate = make_candidate(tmp_path)
    smoke = make_smoke_image(tmp_path)
    before = candidate.read_bytes()
    model = FakeCandidateModel()

    report = validator.validate_candidate(
        candidate, smoke_image=smoke, yolo_loader=lambda _: model
    )

    assert report["schema_version"] == validator.SCHEMA_VERSION
    assert report["tool"] == {"name": validator.TOOL_NAME, "version": validator.TOOL_VERSION}
    assert report["verdict"] == "pass"
    assert report["candidate"]["sha256"] == hashlib.sha256(before).hexdigest()  # type: ignore[index]
    assert report["candidate"]["ordered_class_names"] == APPROVED_NAMES  # type: ignore[index]
    assert statuses(report)["approved_taxonomy"] == "pass"
    assert model.predict_calls == [
        {"source": str(smoke.resolve()), "save": False, "verbose": False}
    ]
    assert candidate.read_bytes() == before


def test_list_style_class_names_and_empty_detections_are_valid_execution(tmp_path: Path) -> None:
    model = EmptyDetectionModel(list(APPROVED_NAMES))
    report = validator.validate_candidate(
        make_candidate(tmp_path),
        smoke_image=make_smoke_image(tmp_path),
        yolo_loader=lambda _: model,
    )

    assert report["verdict"] == "pass"
    assert statuses(report)["approved_taxonomy"] == "pass"
    assert statuses(report)["smoke_inference"] == "pass"


@pytest.mark.parametrize(
    ("names", "check_name"),
    [
        (APPROVED_NAMES[:-1], "class_count"),
        (APPROVED_NAMES[1:] + APPROVED_NAMES[:1], "approved_taxonomy"),
        (["person", "person", *APPROVED_NAMES[2:]], "approved_taxonomy"),
        (DuplicateIdNames(), "class_metadata"),
        ({0: "person", 1: ""}, "class_metadata"),
        ({0.5: "person", **dict(enumerate(APPROVED_NAMES[1:], start=1))}, "class_metadata"),
    ],
)
def test_invalid_class_metadata_fails(
    tmp_path: Path, names: object, check_name: str
) -> None:
    candidate = make_candidate(tmp_path)
    report = validator.validate_candidate(
        candidate,
        smoke_image=make_smoke_image(tmp_path),
        yolo_loader=lambda _: FakeCandidateModel(names),
    )

    assert report["verdict"] == "fail"
    assert statuses(report)[check_name] == "fail"


def test_model_load_and_metadata_failures_are_safe(tmp_path: Path) -> None:
    candidate = make_candidate(tmp_path)
    smoke = make_smoke_image(tmp_path)

    failed_load = validator.validate_candidate(
        candidate,
        smoke_image=smoke,
        yolo_loader=lambda _: (_ for _ in ()).throw(RuntimeError("corrupt")),
    )
    metadata_failure = validator.validate_candidate(
        candidate,
        smoke_image=smoke,
        yolo_loader=lambda _: FakeCandidateModel(names=object()),
    )

    assert failed_load["verdict"] == "fail"
    assert statuses(failed_load)["model_load"] == "fail"
    assert statuses(failed_load)["smoke_inference"] == "fail"
    assert metadata_failure["verdict"] == "fail"
    assert statuses(metadata_failure)["class_metadata"] == "fail"


def test_checksum_failure_and_model_directory_are_rejected(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    candidate = make_candidate(tmp_path)
    monkeypatch.setattr(
        validator.model_inspector,
        "calculate_sha256",
        lambda _: (_ for _ in ()).throw(OSError("unreadable")),
    )

    report = validator.validate_candidate(
        candidate,
        smoke_image=make_smoke_image(tmp_path),
        yolo_loader=lambda _: FakeCandidateModel(),
    )

    assert report["verdict"] == "fail"
    assert statuses(report)["sha256"] == "fail"
    with pytest.raises(validator.CandidateValidationError, match="ML_side/models"):
        validator.prepare_output_directory(validator.MODELS_DIR / "nested", overwrite=False)


def test_directory_candidate_is_rejected(tmp_path: Path) -> None:
    candidate_directory = tmp_path / "candidate-directory"
    candidate_directory.mkdir()

    report = validator.validate_candidate(
        candidate_directory,
        smoke_image=make_smoke_image(tmp_path),
        yolo_loader=lambda _: pytest.fail("loader must not run for a directory"),
    )

    assert report["verdict"] == "fail"
    assert statuses(report)["artifact_is_file"] == "fail"


def test_missing_task_is_warning_but_smoke_still_runs(tmp_path: Path) -> None:
    report = validator.validate_candidate(
        make_candidate(tmp_path),
        smoke_image=make_smoke_image(tmp_path),
        yolo_loader=lambda _: MissingTaskModel(),
    )

    assert report["verdict"] == "pass_with_warnings"
    assert statuses(report)["detection_task"] == "warning"
    assert statuses(report)["smoke_inference"] == "pass"


@pytest.mark.parametrize("task", [float("nan"), float("inf")])
def test_nonfinite_optional_task_metadata_cannot_enter_json(tmp_path: Path, task: float) -> None:
    report = validator.validate_candidate(
        make_candidate(tmp_path),
        smoke_image=make_smoke_image(tmp_path),
        yolo_loader=lambda _: FakeCandidateModel(task=task),
    )

    assert report["verdict"] == "fail"
    assert report["candidate"]["task"] is None  # type: ignore[index]
    assert json.dumps(report, allow_nan=False)


@pytest.mark.parametrize(
    ("candidate_contents", "smoke_path", "expected_check"),
    [
        (b"", "present", "artifact_size"),
        (b"candidate", "missing", "smoke_inference"),
    ],
)
def test_empty_or_nonexecuting_inputs_fail(
    tmp_path: Path,
    candidate_contents: bytes,
    smoke_path: str,
    expected_check: str,
) -> None:
    smoke = make_smoke_image(tmp_path) if smoke_path == "present" else tmp_path / "missing.jpg"
    report = validator.validate_candidate(
        make_candidate(tmp_path, candidate_contents),
        smoke_image=smoke,
        yolo_loader=lambda _: FakeCandidateModel(),
    )

    assert report["verdict"] == "fail"
    assert statuses(report)[expected_check] == "fail"


def test_missing_smoke_image_or_failed_smoke_inference_fails(tmp_path: Path) -> None:
    candidate = make_candidate(tmp_path)
    no_smoke = validator.validate_candidate(candidate, yolo_loader=lambda _: FakeCandidateModel())
    failed_smoke = validator.validate_candidate(
        candidate,
        smoke_image=make_smoke_image(tmp_path),
        yolo_loader=lambda _: FakeCandidateModel(smoke_error=RuntimeError("bad image")),
    )

    assert no_smoke["verdict"] == "fail"
    assert statuses(no_smoke)["smoke_inference"] == "fail"
    assert failed_smoke["verdict"] == "fail"
    assert statuses(failed_smoke)["smoke_inference"] == "fail"


def test_reports_are_versioned_and_output_refuses_models_directory(tmp_path: Path) -> None:
    output = tmp_path / "reports"
    report = validator.run_validation(
        candidate_path=make_candidate(tmp_path),
        smoke_image=make_smoke_image(tmp_path),
        output_path=output,
        yolo_loader=lambda _: FakeCandidateModel(),
    )

    written = json.loads((output / "candidate_model_report.json").read_text(encoding="utf-8"))
    assert written == report
    assert "candidate.pt" in (output / "candidate_model_report.md").read_text(encoding="utf-8")
    assert str(tmp_path) not in (output / "candidate_model_report.md").read_text(encoding="utf-8")
    with pytest.raises(validator.CandidateValidationError, match="ML_side/models"):
        validator.prepare_output_directory(validator.MODELS_DIR, overwrite=False)


def test_nonempty_output_and_nonfinite_json_are_rejected(tmp_path: Path) -> None:
    output = tmp_path / "reports"
    output.mkdir()
    (output / "old.txt").write_text("keep", encoding="utf-8")

    with pytest.raises(validator.CandidateValidationError, match="not empty"):
        validator.run_validation(
            candidate_path=make_candidate(tmp_path),
            smoke_image=make_smoke_image(tmp_path),
            output_path=output,
            yolo_loader=lambda _: FakeCandidateModel(),
        )
    with pytest.raises(ValueError, match="Non-finite"):
        validator._safe_json({"value": float("nan")})


def test_cli_returns_nonzero_for_failed_validation(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    result = validator.main(
        [
            "--model",
            str(tmp_path / "missing.pt"),
            "--smoke-image",
            str(make_smoke_image(tmp_path)),
            "--output",
            str(tmp_path / "reports"),
        ]
    )

    assert result == 1
    assert "Candidate validation verdict: fail" in capsys.readouterr().out


def test_cli_returns_zero_for_a_valid_candidate(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    monkeypatch.setattr(validator, "run_validation", lambda **_: {"verdict": "pass"})

    result = validator.main(
        [
            "--model",
            str(tmp_path / "candidate.pt"),
            "--smoke-image",
            str(tmp_path / "smoke.jpg"),
            "--output",
            str(tmp_path / "reports"),
        ]
    )

    assert result == 0
    assert "Candidate validation verdict: pass" in capsys.readouterr().out
