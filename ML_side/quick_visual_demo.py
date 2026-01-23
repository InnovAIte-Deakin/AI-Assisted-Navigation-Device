"""
Quick Visual Demo - Object Detection Only (No LLM)
Fast visualization of YOLO detections
"""

import cv2
import numpy as np
from ultralytics import YOLO
import sys
from pathlib import Path
from glob import glob

def run_demo(model_path, image_path=None):
    """Run quick visual demo"""

    print("🚀 Loading YOLO model...")
    model = YOLO(model_path)

    # Class names and colors
    class_names = {
        0: "book", 1: "books", 2: "monitor", 3: "office-chair",
        4: "whiteboard", 5: "table", 6: "tv"
    }

    colors = {
        "book": (255, 0, 0), "books": (255, 100, 0),
        "monitor": (0, 255, 0), "office-chair": (0, 165, 255),
        "whiteboard": (0, 0, 255), "table": (255, 0, 255), "tv": (255, 255, 0)
    }

    # Find image if not provided
    if not image_path:
        print("🔍 Looking for sample images...")
        patterns = [
            "data/processed/val_dataset/val/images/*.jpg",
            "data/processed/train_dataset/train/images/*.jpg"
        ]
        for pattern in patterns:
            images = glob(pattern)
            if images:
                image_path = images[0]
                break

    if not image_path:
        print("❌ No image found. Provide --image path/to/image.jpg")
        return

    print(f"📷 Loading image: {Path(image_path).name}")
    frame = cv2.imread(image_path)

    if frame is None:
        print(f"❌ Cannot load: {image_path}")
        return

    print("🔍 Running object detection...")
    results = model.predict(frame, conf=0.5, verbose=False)

    annotated = frame.copy()
    detections = []

    if results[0].boxes is not None:
        boxes = results[0].boxes

        for i in range(len(boxes)):
            xyxy = boxes.xyxy[i].cpu().numpy()
            conf = float(boxes.conf[i].cpu().numpy())
            cls = int(boxes.cls[i].cpu().numpy())

            x1, y1, x2, y2 = map(int, xyxy)
            class_name = class_names.get(cls, f"class_{cls}")

            detections.append({
                'class': class_name,
                'conf': conf,
                'box': (x1, y1, x2, y2)
            })

            # Draw bounding box
            color = colors.get(class_name, (128, 128, 128))
            cv2.rectangle(annotated, (x1, y1), (x2, y2), color, 3)

            # Label
            label = f"{class_name} {conf:.0%}"
            (w, h), _ = cv2.getTextSize(label, cv2.FONT_HERSHEY_SIMPLEX, 0.7, 2)

            # Label background
            cv2.rectangle(annotated, (x1, y1-h-15), (x1+w, y1), color, -1)
            cv2.putText(annotated, label, (x1, y1-5),
                       cv2.FONT_HERSHEY_SIMPLEX, 0.7, (255, 255, 255), 2)

    # Add info panel
    h, w = annotated.shape[:2]
    panel = np.zeros((150, w, 3), dtype=np.uint8)
    panel[:] = (40, 40, 40)

    # Title
    cv2.putText(panel, "AI NAVIGATION - Object Detection", (10, 30),
               cv2.FONT_HERSHEY_SIMPLEX, 0.8, (0, 255, 255), 2)

    # Detection results
    y = 70
    print(f"\n✅ Detected {len(detections)} objects:")
    for d in detections:
        text = f"- {d['class']}: {d['conf']:.0%} confidence"
        print(f"   {text}")
        cv2.putText(panel, text, (10, y),
                   cv2.FONT_HERSHEY_SIMPLEX, 0.6, (255, 255, 255), 1)
        y += 30

    if len(detections) == 0:
        cv2.putText(panel, "No objects detected", (10, 70),
                   cv2.FONT_HERSHEY_SIMPLEX, 0.6, (200, 200, 200), 1)

    # Instructions
    cv2.putText(panel, "Press any key to close", (10, 140),
               cv2.FONT_HERSHEY_SIMPLEX, 0.5, (200, 200, 200), 1)

    # Combine
    result = np.vstack([annotated, panel])

    # Save
    output = image_path.replace('.jpg', '_detected.jpg')
    cv2.imwrite(output, result)
    print(f"\n💾 Saved: {Path(output).name}")

    # Show
    print("\n🖼️  Opening window... (Press any key to close)")
    cv2.imshow('Object Detection', result)
    cv2.waitKey(0)
    cv2.destroyAllWindows()

if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser()
    parser.add_argument('--model', default='models/object_detection/best.pt')
    parser.add_argument('--image', type=str, help='Path to image')
    args = parser.parse_args()

    run_demo(args.model, args.image)
