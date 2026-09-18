from __future__ import annotations

import os
import re
import shutil
import tempfile
import urllib.request
import zipfile
from pathlib import Path

from .database import PipelineDatabase
from .models import SourceConfig, StageResult, StageStatus


def _safe_extract(archive: Path, destination: Path) -> None:
    destination.mkdir(parents=True, exist_ok=True)
    destination_root = destination.resolve()
    with zipfile.ZipFile(archive) as handle:
        for info in handle.infolist():
            target = (destination / info.filename).resolve()
            try:
                target.relative_to(destination_root)
            except ValueError as exc:
                raise ValueError(f"Unsafe archive member: {info.filename}") from exc
        handle.extractall(destination)


def _download_source(source: SourceConfig, destination: Path) -> None:
    provider = source.provider.lower()
    if provider in {"http", "https", "url"}:
        if not source.url:
            raise RuntimeError("direct URL source has no url")
        archive = destination.parent / f".{destination.name}.download"
        urllib.request.urlretrieve(source.url, archive)
        if zipfile.is_zipfile(archive):
            _safe_extract(archive, destination)
            archive.unlink()
        else:
            destination.mkdir(parents=True)
            archive.replace(destination / Path(source.url).name)
    elif provider == "kaggle":
        try:
            import kagglehub  # type: ignore
        except ImportError as exc:
            raise RuntimeError("kagglehub is required to collect Kaggle sources") from exc
        match = re.search(r"kaggle\.com/datasets/([^/]+/[^/?#]+)", source.url)
        if not match:
            raise RuntimeError("Kaggle URL does not contain owner/dataset")
        downloaded = Path(kagglehub.dataset_download(match.group(1)))
        shutil.copytree(downloaded, destination)
    elif provider == "huggingface":
        try:
            from huggingface_hub import snapshot_download  # type: ignore
        except ImportError as exc:
            raise RuntimeError("huggingface_hub is required to collect Hugging Face sources") from exc
        match = re.search(r"huggingface\.co/datasets/([^/]+/[^/?#]+)", source.url)
        if not match:
            raise RuntimeError("Hugging Face URL does not contain owner/dataset")
        snapshot_download(repo_id=match.group(1), repo_type="dataset", local_dir=str(destination))
    elif provider == "roboflow":
        try:
            from roboflow import Roboflow  # type: ignore
        except ImportError as exc:
            raise RuntimeError("roboflow is required to collect Roboflow sources") from exc
        api_key = os.environ.get("ROBOFLOW_API_KEY")
        if not api_key:
            raise RuntimeError("ROBOFLOW_API_KEY is not set")
        match = re.search(r"universe\.roboflow\.com/([^/]+)/([^/?#]+)", source.url)
        if not match or source.version is None:
            raise RuntimeError("Roboflow source requires workspace/project URL and version")
        project = Roboflow(api_key=api_key).workspace(match.group(1)).project(match.group(2))
        project.version(int(source.version)).download("yolov8", location=str(destination), overwrite=False)
    else:
        raise RuntimeError(f"provider {source.provider!r} requires files to be placed manually")


def collect_source(db: PipelineDatabase, run_id: str, source: SourceConfig) -> StageResult:
    if source.folder.is_dir() and any(source.folder.iterdir()):
        result = StageResult(
            "collection", StageStatus.PASS, "Existing non-empty raw source folder retained.", source.source_id,
            {"folder": str(source.folder), "downloaded": False},
        )
        db.record_stage(run_id, result)
        return result
    if source.folder.exists() and not source.folder.is_dir():
        result = StageResult(
            "collection", StageStatus.FAIL, "Raw source path exists but is not a directory.", source.source_id
        )
        db.record_stage(run_id, result)
        return result
    temporary = source.folder.parent / f".{source.folder.name}.collecting-{run_id}"
    if temporary.exists():
        result = StageResult(
            "collection", StageStatus.FAIL, f"Collection staging path requires inspection: {temporary}", source.source_id
        )
        db.record_stage(run_id, result)
        return result
    try:
        _download_source(source, temporary)
        if not temporary.is_dir() or not any(temporary.rglob("*")):
            raise RuntimeError("provider returned no files")
        source.folder.parent.mkdir(parents=True, exist_ok=True)
        if source.folder.exists():
            # The layout initializer creates an empty placeholder. rmdir is
            # intentionally strict and refuses to remove it if another process
            # or person placed files there while collection was running.
            source.folder.rmdir()
        temporary.replace(source.folder)
    except Exception as exc:
        result = StageResult("collection", StageStatus.FAIL, f"Collection failed: {exc}", source.source_id)
        db.record_stage(run_id, result)
        return result
    result = StageResult(
        "collection", StageStatus.PASS, "Source downloaded and safely staged into raw storage.", source.source_id,
        {"folder": str(source.folder), "downloaded": True},
    )
    db.record_stage(run_id, result)
    return result
