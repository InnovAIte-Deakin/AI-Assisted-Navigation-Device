from pathlib import Path

PIPELINE_DIR = Path(__file__).resolve().parent
ML_SIDE_DIR = PIPELINE_DIR.parent
REPO_DIR = ML_SIDE_DIR.parent
ASSETS_DIR = PIPELINE_DIR / "test_assets"


def resolve_path(value):
    path = Path(value)

    candidates = [
        path,
        Path.cwd() / value,
        PIPELINE_DIR / value,
        ML_SIDE_DIR / value,
        REPO_DIR / value,
        ASSETS_DIR / value,
        ASSETS_DIR / path.name
    ]

    for candidate in candidates:
        if candidate.exists():
            return candidate.resolve()

    return path


def resolve_existing_file(value):
    path = resolve_path(value)

    if path.exists() and path.is_file():
        return path

    raise FileNotFoundError(f"File not found: {value}")


def resolve_dir(value):
    path = Path(value)

    candidates = [
        path,
        Path.cwd() / value,
        PIPELINE_DIR / value,
        ML_SIDE_DIR / value,
        REPO_DIR / value
    ]

    for candidate in candidates:
        if candidate.exists() and candidate.is_dir():
            return candidate.resolve()

    path.mkdir(parents=True, exist_ok=True)
    return path.resolve()


def load_json(path):
    return Path(path).read_text(encoding="utf-8")
