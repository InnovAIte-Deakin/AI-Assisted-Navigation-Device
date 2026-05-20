"""
YOLO Model Demo — AI-Assisted Navigation Device
Sprint 2 | Bravine Cheruiyot | SIT374 Capstone

Usage:
  python demo_yolo_model.py                  # webcam
  python demo_yolo_model.py image.jpg        # image file
  python demo_yolo_model.py --no-display     # print-only (no GUI)
"""

import sys
import os
import time

# ── Priority System ────────────────────────────────────────────────────────────
OBJECT_PRIORITY = {
    "stairs": 5,            "emergency-exit": 5,
    "person": 4,            "fire-extinguisher": 4,
    "door": 3,              "elevator": 3,          "handrail": 3,
    "signage": 2,           "whiteboard": 2,         "tv": 2,
    "book": 1,              "books": 1,              "monitor": 1,
    "office-chair": 1,      "table": 1,
}
PRIORITY_LABELS = {5: "CRITICAL", 4: "HIGH", 3: "MEDIUM", 2: "LOW", 1: "MINIMAL"}

# BGR colours for bounding boxes
PRIORITY_COLOURS = {
    5: (0, 0, 255),    # red
    4: (0, 128, 255),  # orange
    3: (0, 255, 255),  # yellow
    2: (0, 255, 0),    # green
    1: (200, 200, 200) # grey
}

MODEL_PATH = os.path.join(os.path.dirname(__file__), "models", "best.pt")


def priority_label(class_name: str):
    p = OBJECT_PRIORITY.get(class_name.lower(), 1)
    return p, PRIORITY_LABELS[p]


def navigation_decision(detections: list) -> str:
    if not detections:
        return "PROCEED — path clear"
    top = max(detections, key=lambda d: d["priority"])
    p = top["priority"]
    name = top["class_name"]
    if p == 5:
        return f"STOP — {name.upper()} detected (CRITICAL)"
    elif p == 4:
        return f"CAUTION — {name} detected (HIGH)"
    elif p == 3:
        return f"AWARE — {name} nearby (MEDIUM)"
    else:
        return f"PROCEED — {name} present but low risk"


def print_detections(detections: list):
    print("\n┌─────────────────────────────────────────────────┐")
    print("│         YOLO Detection Results                  │")
    print("├──────────────────┬──────────┬──────────┬────────┤")
    print("│ Object           │ Priority │ Label    │  Conf  │")
    print("├──────────────────┼──────────┼──────────┼────────┤")
    for d in sorted(detections, key=lambda x: x["priority"], reverse=True):
        print(f"│ {d['class_name']:<16} │    {d['priority']}     │ {d['label']:<8} │ {d['conf']:.0%}   │")
    print("├──────────────────┴──────────┴──────────┴────────┤")
    decision = navigation_decision(detections)
    print(f"│ ▶ {decision:<47}│")
    print("└─────────────────────────────────────────────────┘\n")


def run_on_image(image_path: str, display: bool = True):
    try:
        from ultralytics import YOLO
        import cv2
    except ImportError:
        print("Run: pip install ultralytics opencv-python")
        sys.exit(1)

    model = YOLO(MODEL_PATH) if os.path.exists(MODEL_PATH) else YOLO("yolov8n.pt")
    print(f"Model: {'custom best.pt' if os.path.exists(MODEL_PATH) else 'yolov8n fallback'}")
    print(f"Classes: {len(model.names)}")

    results = model(image_path, verbose=False)[0]
    img = results.orig_img.copy()

    detections = []
    for box in results.boxes:
        cls_id = int(box.cls[0])
        name = model.names[cls_id]
        conf = float(box.conf[0])
        p, lbl = priority_label(name)
        x1, y1, x2, y2 = map(int, box.xyxy[0])
        colour = PRIORITY_COLOURS.get(p, (200, 200, 200))

        import cv2
        cv2.rectangle(img, (x1, y1), (x2, y2), colour, 2)
        cv2.putText(img, f"{name} [{lbl}] {conf:.0%}", (x1, max(15, y1 - 6)),
                    cv2.FONT_HERSHEY_SIMPLEX, 0.55, colour, 2)

        detections.append({"class_name": name, "priority": p, "label": lbl, "conf": conf})

    print_detections(detections)

    out_path = "demo_output.jpg"
    import cv2
    cv2.imwrite(out_path, img)
    print(f"Saved: {out_path}")

    if display:
        cv2.imshow("YOLO — AI Navigation Demo", img)
        cv2.waitKey(0)
        cv2.destroyAllWindows()


def run_webcam():
    try:
        from ultralytics import YOLO
        import cv2
    except ImportError:
        print("Run: pip install ultralytics opencv-python")
        sys.exit(1)

    model = YOLO(MODEL_PATH) if os.path.exists(MODEL_PATH) else YOLO("yolov8n.pt")
    print(f"Model: {'custom best.pt' if os.path.exists(MODEL_PATH) else 'yolov8n fallback'}")
    print("Press Q to quit\n")

    cap = cv2.VideoCapture(0)
    if not cap.isOpened():
        print("Webcam not available — pass an image path instead")
        sys.exit(1)

    prev_time = time.time()

    while True:
        ret, frame = cap.read()
        if not ret:
            break

        results = model(frame, verbose=False)[0]
        detections = []

        for box in results.boxes:
            cls_id = int(box.cls[0])
            name = model.names[cls_id]
            conf = float(box.conf[0])
            p, lbl = priority_label(name)
            x1, y1, x2, y2 = map(int, box.xyxy[0])
            colour = PRIORITY_COLOURS.get(p, (200, 200, 200))

            cv2.rectangle(frame, (x1, y1), (x2, y2), colour, 2)
            cv2.putText(frame, f"{name} [{lbl}] {conf:.0%}", (x1, max(15, y1 - 6)),
                        cv2.FONT_HERSHEY_SIMPLEX, 0.55, colour, 2)
            detections.append({"class_name": name, "priority": p, "label": lbl, "conf": conf})

        # FPS
        fps = 1.0 / (time.time() - prev_time)
        prev_time = time.time()
        cv2.putText(frame, f"FPS: {fps:.1f}", (10, 25),
                    cv2.FONT_HERSHEY_SIMPLEX, 0.7, (255, 255, 255), 2)

        # Navigation decision overlay
        decision = navigation_decision(detections)
        colour = (0, 0, 255) if "STOP" in decision else (0, 128, 255) if "CAUTION" in decision else (0, 200, 0)
        cv2.putText(frame, decision, (10, frame.shape[0] - 15),
                    cv2.FONT_HERSHEY_SIMPLEX, 0.75, colour, 2)

        cv2.imshow("YOLO — AI Navigation Demo", frame)
        if cv2.waitKey(1) & 0xFF == ord("q"):
            break

    cap.release()
    cv2.destroyAllWindows()


# ── Entry Point ────────────────────────────────────────────────────────────────

if __name__ == "__main__":
    no_display = "--no-display" in sys.argv
    args = [a for a in sys.argv[1:] if not a.startswith("--")]

    if args and os.path.isfile(args[0]):
        run_on_image(args[0], display=not no_display)
    else:
        if no_display:
            print("--no-display requires an image path")
            sys.exit(1)
        run_webcam()
