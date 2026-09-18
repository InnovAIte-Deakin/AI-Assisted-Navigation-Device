from __future__ import annotations

from pathlib import Path

from .models import PipelineConfig, PipelineError, StageResult, StageStatus


def _ensure_directory(path: Path, label: str) -> None:
    if path.exists() and not path.is_dir():
        raise PipelineError(f"{label} exists but is not a directory: {path}")
    path.mkdir(parents=True, exist_ok=True)


def initialise_storage_layout(config: PipelineConfig, run_id: str) -> StageResult:
    """Create the complete safe working skeleton without publishing a release early."""
    roots = {
        "raw root": config.raw_root,
        "workspace root": config.workspace_root,
        "invalid root": config.invalid_root,
        "output root": config.output_root,
    }
    for label, path in roots.items():
        _ensure_directory(path, label)

    run_root = config.workspace_root / run_id
    common_run_directories = (
        run_root / "standardized",
        run_root / "labels",
        run_root / "extracted",
        run_root / "review" / "near_duplicates",
        run_root / "review" / "quality",
        run_root / "review" / "semantic",
        config.invalid_root / run_id,
    )
    for path in common_run_directories:
        _ensure_directory(path, "pipeline working directory")

    providers: set[str] = set()
    source_folders: list[str] = []
    for source in config.sources:
        provider = source.provider.strip().lower() or "unknown"
        providers.add(provider)
        _ensure_directory(config.raw_root / provider, f"raw provider directory for {provider}")
        # This empty placeholder is intentional. Collection treats it as a target
        # to populate, not as evidence that a download already succeeded.
        _ensure_directory(source.folder, f"raw source directory for {source.source_id}")
        _ensure_directory(run_root / "standardized" / source.source_id, "standardized source directory")
        _ensure_directory(run_root / "labels" / source.source_id, "label source directory")
        _ensure_directory(run_root / "review" / "quality" / source.source_id, "quality review directory")
        _ensure_directory(run_root / "review" / "semantic" / source.source_id, "semantic review directory")
        source_folders.append(str(source.folder))

    return StageResult(
        "layout_initialization",
        StageStatus.PASS,
        f"Prepared storage for {len(config.sources)} sources across {len(providers)} providers.",
        metrics={
            "providers": sorted(providers),
            "source_folders": source_folders,
            "run_workspace": str(run_root),
            "invalid_run_root": str(config.invalid_root / run_id),
            "release_directory_reserved": False,
        },
    )
