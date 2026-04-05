"""
Priority Assignment Demo
Runs YOLO detection on an image and visualises each object with its priority label.

Usage:
    python demo_priority.py --image <path_to_image>
    python demo_priority.py --image <path> --model <path_to_weights>
"""

import argparse
import sys
import os
import cv2
import numpy as np
from pathlib import Path
from ultralytics import YOLO

# ── Priority Configuration ─────────────────────────────────────────────────────

OBJECT_PRIORITY = {
    "stairs":            5,
    "emergency-exit":    5,
    "person":            4,
    "fire-extinguisher": 4,
    "door":              3,
    "elevator":          3,
    "handrail":          3,
    "signage":           2,
    "whiteboard":        2,
    "tv":                2,
    "book":              1,
    "books":             1,
    "monitor":           1,
    "office-chair":      1,
    "table":             1,
}

PRIORITY_LABELS = {5: "CRITICAL", 4: "HIGH", 3: "MEDIUM", 2: "LOW", 1: "MINIMAL"}

# BGR colours per priority level
PRIORITY_COLOURS = {
    5: (0,   0,   255),   # Red    — critical
    4: (0,   128, 255),   # Orange — high
    3: (0,   255, 255),   # Yellow — medium
    2: (0,   255, 128),   # Mint   — low
    1: (0,   255, 0),     # Green  — minimal
}

CLASS_NAMES = {i: name for i, name in enumerate(OBJECT_PRIORITY.keys())}


def get_priority(class_name: str):
    p = OBJECT_PRIORITY.get(class_name, 1)
    return p, PRIORITY_LABELS[p], PRIORITY_COLOURS[p]


def draw_detections(image, detections):
    """Draw priority-coloured bounding boxes on image"""
    annotated = image.copy()

    for det in detections:
        x1, y1, x2, y2 = det["box"]
        name   = det["class_name"]
        conf   = det["confidence"]
        p, lbl, colour = get_priority(name)

        # Bounding box
        cv2.rectangle(annotated, (x1, y1), (x2, y2), colour, 2)

        # Label background
        label = f"{name} [{lbl}] {conf:.0%}"
        (tw, th), _ = cv2.getTextSize(label, cv2.FONT_HERSHEY_SIMPLEX, 0.5, 1)
        cv2.rectangle(annotated, (x1, y1 - th - 6), (x1 + tw + 4, y1), colour, -1)
        cv2.putText(annotated, label, (x1 + 2, y1 - 4),
                    cv2.FONT_HERSHEY_SIMPLEX, 0.5, (0, 0, 0), 1, cv2.LINE_AA)

    return annotated


def draw_legend(image):
    """Add priority legend to top-right corner"""
    x, y = image.shape[1] - 210, 10
    for p in sorted(PRIORITY_COLOURS.keys(), reverse=True):
        colour = PRIORITY_COLOURS[p]
        label  = f"P{p}: {PRIORITY_LABELS[p]}"
        cv2.rectangle(image, (x, y), (x + 14, y + 14), colour, -1)
        cv2.putText(image, label, (x + 18, y + 12),
                    cv2.FONT_HERSHEY_SIMPLEX, 0.45, colour, 1, cv2.LINE_AA)
        y += 20
    return image


def run_demo(image_path: str, model_path: str, conf_threshold: float = 0.4):
    # Load image
    image = cv2.imread(image_path)
    if image is None:
        print(f"ERROR: Cannot read image: {image_path}")
        sys.exit(1)

    print(f"\n{'='*60}")
    print("OBJECT PRIORITY ASSIGNMENT DEMO")
    print(f"{'='*60}")
    print(f"Image : {image_path}")
    print(f"Model : {model_path}")
    print(f"Conf  : {conf_threshold}")
    print()

    # Load model
    model = YOLO(model_path)

    # Run detection
    results = model.predict(image, conf=conf_threshold, verbose=False)
    boxes   = results[0].boxes

    detections = []
    if boxes is not None:
        for i in range(len(boxes)):
            x1, y1, x2, y2 = map(int, boxes.xyxy[i].cpu().numpy())
            conf  = float(boxes.conf[i].cpu().numpy())
            cls   = int(boxes.cls[i].cpu().numpy())
            name  = CLASS_NAMES.get(cls, f"unknown_{cls}")
            detections.append({"box": (x1, y1, x2, y2), "class_name": name, "confidence": conf})

    # Sort by priority (highest first)
    detections.sort(key=lambda d: OBJECT_PRIORITY.get(d["class_name"], 1), reverse=True)

    # Print results
    print(f"Detected {len(detections)} object(s):\n")
    print(f"  {'#':<3} {'Object':<20} {'Priority':<10} {'Label':<10} {'Conf':<8}")
    print(f"  {'-'*55}")
    for i, det in enumerate(detections, 1):
        p, lbl, _ = get_priority(det["class_name"])
        print(f"  {i:<3} {det['class_name']:<20} {p:<10} {lbl:<10} {det['confidence']:.0%}")

    if detections:
        top = detections[0]
        p, lbl, _ = get_priority(top["class_name"])
        print()
        print(f"  → Highest priority: {top['class_name'].upper()} [{lbl}]")
        if p == 5:
            print("  → Navigation action: STOP — assess surroundings immediately")
        elif p == 4:
            print("  → Navigation action: CAUTION — slow down and navigate carefully")
        elif p == 3:
            print("  → Navigation action: AWARE — useful navigation landmark detected")
        else:
            print("  → Navigation action: NORMAL — no immediate hazard")
    else:
        print("  No objects detected above confidence threshold.")

    # Draw annotated image
    annotated = draw_detections(image, detections)
    annotated = draw_legend(annotated)

    # Save output
    out_path = Path(image_path).stem + "_priority_demo.jpg"
    cv2.imwrite(out_path, annotated)
    print(f"\nAnnotated image saved: {out_path}")

    # Show
    cv2.imshow("Priority Assignment Demo  (press any key to close)", annotated)
    cv2.waitKey(0)
    cv2.destroyAllWindows()


def main():
    parser = argparse.ArgumentParser(description="Object Priority Assignment Demo")
    parser.add_argument("--image", required=True, help="Path to input image")
    parser.add_argument(
        "--model",
        default="models/object_detection/best.pt",
        help="Path to YOLO weights (default: models/object_detection/best.pt)"
    )
    parser.add_argument("--conf", type=float, default=0.4, help="Confidence threshold")
    args = parser.parse_args()

    if not os.path.exists(args.model):
        print(f"ERROR: Model not found: {args.model}")
        print("Tip: run from ML_side/ directory, or pass --model <path>")
        sys.exit(1)

    run_demo(args.image, args.model, args.conf)


if __name__ == "__main__":
    main()
