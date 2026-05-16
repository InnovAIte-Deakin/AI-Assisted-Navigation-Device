import json
from pathlib import Path


IMAGE_EXTENSIONS = {".png", ".jpg", ".jpeg", ".webp"}
VIDEO_EXTENSIONS = {".mp4", ".mov", ".avi", ".mkv"}

PIPELINE_DIR = Path(__file__).resolve().parent
ML_SIDE_DIR = PIPELINE_DIR.parent
REPO_DIR = ML_SIDE_DIR.parent
ASSETS_DIR = PIPELINE_DIR / "test_assets"


def ask_text(prompt, default=None):
    if default is None:
        value = input(f"{prompt}: ").strip()
    else:
        value = input(f"{prompt} [{default}]: ").strip()

    if value == "" and default is not None:
        return default

    return value


def ask_int(prompt, default=None):
    while True:
        if default is None:
            value = input(f"{prompt}: ").strip()
        else:
            value = input(f"{prompt} [{default}]: ").strip()

        if value == "" and default is not None:
            return default

        return int(value)


def ask_float(prompt, default=None):
    while True:
        if default is None:
            value = input(f"{prompt}: ").strip()
        else:
            value = input(f"{prompt} [{default}]: ").strip()

        if value == "" and default is not None:
            return default

        return float(value)


def ask_case_type():
    while True:
        print("Choose case type:")
        print("1. Image testing JSON")
        print("2. Video testing JSON")

        choice = input("Enter 1 or 2: ").strip().lower()

        if choice in {"1", "image", "i"}:
            return "image"

        if choice in {"2", "video", "v"}:
            return "video"

        print("Invalid choice. Enter 1 for image or 2 for video.")


def find_media_file(value):
    typed_path = Path(value)

    candidates = [
        typed_path,
        PIPELINE_DIR / value,
        ASSETS_DIR / value,
        ML_SIDE_DIR / value,
        REPO_DIR / value
    ]

    for candidate in candidates:
        if candidate.exists() and candidate.is_file():
            return candidate.resolve()

    return None


def ask_media_file(case_type):
    while True:
        media_path_text = ask_text(f"Enter {case_type} file name/path")
        media_path = find_media_file(media_path_text)

        if media_path is None:
            print("File not found. Enter the file name/path again.")
            continue

        extension = media_path.suffix.lower()

        if case_type == "image" and extension in IMAGE_EXTENSIONS:
            return media_path

        if case_type == "video" and extension in VIDEO_EXTENSIONS:
            return media_path

        print(f"Wrong file type. This case requires a {case_type} file.")


def to_ml_side_relative(path):
    try:
        return str(path.relative_to(ML_SIDE_DIR)).replace("\\", "/")
    except ValueError:
        return str(path).replace("\\", "/")


def ask_required_labels():
    labels = []
    count = ask_int("How many required labels do you want to test", 0)

    for index in range(1, count + 1):
        label = ask_text(f"Required label {index}")
        labels.append(label)

    return labels


def ask_directions(labels):
    directions = {}

    print()
    print("Enter expected direction for each label.")
    print("Examples: to the left, directly ahead, to the right")
    print("Press Enter to skip direction checking for that label.")

    for label in labels:
        direction = ask_text(f"Direction for {label}", "")

        if direction != "":
            directions[label] = direction

    return directions


def safe_file_name(name):
    return name.strip().lower().replace(" ", "_")


def create_image_case(name, endpoint, media_path, labels, directions, min_event_count):
    return {
        "name": name,
        "endpoint": endpoint,
        "image": to_ml_side_relative(media_path),
        "expected": {
            "required_labels": labels,
            "required_directions": directions,
            "min_event_count": min_event_count
        }
    }


def create_video_case(name, endpoint, media_path, labels, directions, min_event_count):
    frame_step = ask_int("Frame step", 10)
    min_frames_with_events = ask_int("Minimum frames with detections", 1)
    min_detection_rate = ask_float("Minimum detection rate", 0.5)

    return {
        "name": name,
        "endpoint": endpoint,
        "video": to_ml_side_relative(media_path),
        "frame_step": frame_step,
        "expected": {
            "required_labels": labels,
            "required_directions": directions,
            "min_event_count": min_event_count,
            "min_frames_with_events": min_frames_with_events,
            "min_detection_rate": min_detection_rate
        }
    }


def main():
    print("=== Interactive Test Case Creator ===")

    case_type = ask_case_type()
    name = ask_text("Case name")
    endpoint = ask_text("Endpoint", "detect")
    media_path = ask_media_file(case_type)
    labels = ask_required_labels()
    directions = ask_directions(labels)
    min_event_count = ask_int("Minimum event count", len(labels))

    if case_type == "image":
        case_data = create_image_case(
            name=name,
            endpoint=endpoint,
            media_path=media_path,
            labels=labels,
            directions=directions,
            min_event_count=min_event_count
        )

    if case_type == "video":
        case_data = create_video_case(
            name=name,
            endpoint=endpoint,
            media_path=media_path,
            labels=labels,
            directions=directions,
            min_event_count=min_event_count
        )

    output_dir = PIPELINE_DIR / "cases"
    output_dir.mkdir(parents=True, exist_ok=True)

    output_path = output_dir / f"{safe_file_name(name)}.json"
    output_path.write_text(json.dumps(case_data, indent=2), encoding="utf-8")

    print()
    print(f"{case_type.title()} case file created: {output_path}")


if __name__ == "__main__":
    main()