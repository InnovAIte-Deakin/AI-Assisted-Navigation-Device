import argparse
import cv2
from pathlib import Path
import requests


def extract_frames(video_path, step):
    cap = cv2.VideoCapture(str(video_path))
    if not cap.isOpened():
        raise RuntimeError(f"Cannot open video: {video_path}")

    frame_index = 0

    while True:
        ok, frame = cap.read()
        if not ok:
            break

        if frame_index % step == 0:
            yield frame_index, frame

        frame_index += 1

    cap.release()


def call_api_frame(base_url, endpoint, frame, question=None):
    _, img_encoded = cv2.imencode(".png", frame)

    files = {
        "file": ("frame.png", img_encoded.tobytes(), "image/png")
    }

    url = f"{base_url}/{endpoint}"

    if endpoint == "two_brain":
        response = requests.post(
            url,
            files=files,
            data={"question": question or "What is in front of me?"},
            timeout=120,
        )
    else:
        response = requests.post(
            url,
            files=files,
            timeout=120,
        )

    response.raise_for_status()
    return response.json()


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("video")
    parser.add_argument("--endpoint", default="detect")
    parser.add_argument("--base-url", default="http://127.0.0.1:8001")
    parser.add_argument("--frame-step", type=int, default=10)
    parser.add_argument("--question", default="What is in front of me?")
    args = parser.parse_args()

    video_path = Path(args.video)

    total_frames = 0
    frames_with_events = 0
    frames_safe = 0
    frames_unsafe = 0

    for frame_index, frame in extract_frames(video_path, args.frame_step):
        total_frames += 1

        try:
            response = call_api_frame(
                args.base_url,
                args.endpoint,
                frame,
                args.question
            )

            events = response.get("events", [])

            if len(events) > 0:
                frames_with_events += 1

            if args.endpoint == "two_brain":
                if response.get("safe") is True:
                    frames_safe += 1
                else:
                    frames_unsafe += 1

        except Exception as e:
            print(f"Frame {frame_index} error: {e}")

    print("\n=== Video Test Summary ===")
    print(f"Total frames checked: {total_frames}")
    print(f"Frames with detections: {frames_with_events}")

    if args.endpoint == "two_brain":
        print(f"Safe frames: {frames_safe}")
        print(f"Unsafe frames: {frames_unsafe}")

    if total_frames > 0:
        print(f"Detection rate: {frames_with_events / total_frames:.2f}")


if __name__ == "__main__":
    main()