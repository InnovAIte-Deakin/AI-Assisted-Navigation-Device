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
    files = {"file": ("frame.png", img_encoded.tobytes(), "image/png")}
    url = f"{base_url}/{endpoint}"

    if endpoint == "two_brain":
        response = requests.post(url, files=files, data={"question": question or "What is in front of me?"}, timeout=120)
    else:
        response = requests.post(url, files=files, timeout=120)

    response.raise_for_status()
    return response.json()

def run_video_case(case_data, base_url, video_path, threshold=0.5):
    """Executes a video case and calculates ML metrics across frames based on the threshold."""
    endpoint = case_data.get("endpoint", "detect")
    question = case_data.get("question", "What is in front of me?")
    frame_step = case_data.get("frame_step", 10)
    expected = case_data.get("expected", {})
    required_labels = expected.get("required_labels", [])
    
    total_frames = 0
    frames_with_events = 0
    
    # Track metrics across the video
    tp, fp, fn = 0, 0, 0
    errors = []

    for frame_index, frame in extract_frames(video_path, frame_step):
        total_frames += 1
        try:
            response = call_api_frame(base_url, endpoint, frame, question)
            raw_events = response.get("events", [])
            
            # Apply your confidence filter per frame
            filtered_events = [e for e in raw_events if e.get("confidence", 0.0) >= threshold]
            if filtered_events:
                frames_with_events += 1

            # Simple Video TP/FP Calculation (If it finds required labels in any frame)
            found_in_frame = set(e.get("label", "").lower() for e in filtered_events)
            for label in required_labels:
                if label.lower() in found_in_frame:
                    tp += 1
            
            for e in filtered_events:
                if e.get("label", "").lower() not in [req.lower() for req in required_labels]:
                    fp += 1

        except Exception as e:
            errors.append({"type": "Runtime Error", "label": "System", "reason": f"Frame {frame_index} error: {e}"})

    # Calculate False Negatives based on missing frames
    fn = len(required_labels) * total_frames - tp

    stats = {
        "threshold": threshold,
        "TP": tp,
        "FP": fp,
        "FN": max(0, fn), # Ensure it doesn't go negative
        "frames_checked": total_frames,
        "frames_with_detections": frames_with_events
    }

    passed = len(errors) == 0
    return passed, errors, stats

def main():
    print("Run via run_test_suite.py to evaluate full metrics.")

if __name__ == "__main__":
    main()