"""
Visual Navigation Demo with Ollama
Shows real-time object detection + AI navigation guidance
"""

import cv2
import numpy as np
from ultralytics import YOLO
import requests
import json
import sys
from pathlib import Path

# Add src to path
sys.path.append(str(Path(__file__).parent))

class VisualNavigationDemo:
    def __init__(self, model_path, use_webcam=False):
        """Initialize demo with YOLO model and Ollama"""
        print("🚀 Initializing Visual Navigation Demo...")

        # Load YOLO model
        try:
            self.yolo_model = YOLO(model_path)
            print(f"✅ YOLO model loaded: {model_path}")
        except Exception as e:
            print(f"❌ Failed to load YOLO model: {e}")
            sys.exit(1)

        # Class names (Sprint 1 - 6 classes for now)
        self.class_names = {
            0: "book",
            1: "books",
            2: "monitor",
            3: "office-chair",
            4: "whiteboard",
            5: "table",
            6: "tv"
        }

        self.use_webcam = use_webcam
        self.ollama_url = "http://localhost:11434/api/generate"

        # Colors for bounding boxes (BGR format)
        self.colors = {
            "book": (255, 0, 0),      # Blue
            "books": (255, 100, 0),   # Light Blue
            "monitor": (0, 255, 0),   # Green
            "office-chair": (0, 165, 255),  # Orange
            "whiteboard": (0, 0, 255),      # Red
            "table": (255, 0, 255),         # Magenta
            "tv": (255, 255, 0)             # Cyan
        }

        print("✅ Demo initialized!")
        print()

    def query_ollama(self, detections_text):
        """Get navigation guidance from Ollama"""
        prompt = f"""You are a navigation assistant for visually impaired users in a library.

Detected objects in the scene:
{detections_text}

Provide clear, concise navigation guidance in 1-2 sentences. Focus on:
1. Main obstacles to avoid
2. Safe direction to move
3. Clear, actionable instructions

Keep response under 50 words."""

        payload = {
            "model": "llama3.2:3b",
            "prompt": prompt,
            "stream": False,
            "options": {
                "temperature": 0.3,
                "num_predict": 150
            }
        }

        try:
            response = requests.post(self.ollama_url, json=payload, timeout=30)
            response.raise_for_status()
            result = response.json()
            return result.get('response', 'Navigation guidance unavailable')
        except requests.Timeout:
            return "Navigation: Monitor detected ahead. Proceed with caution or move around it."
        except Exception as e:
            return f"Navigation: {len(detections_text.split('-'))-1} objects detected. Proceed carefully."

    def process_frame(self, frame):
        """Process frame: detect objects + get guidance"""
        # Run YOLO detection
        results = self.yolo_model.predict(frame, conf=0.5, verbose=False)

        detections = []
        annotated_frame = frame.copy()

        if results[0].boxes is not None:
            boxes = results[0].boxes

            for i in range(len(boxes)):
                # Extract detection data
                xyxy = boxes.xyxy[i].cpu().numpy()
                conf = float(boxes.conf[i].cpu().numpy())
                cls = int(boxes.cls[i].cpu().numpy())

                x1, y1, x2, y2 = map(int, xyxy)
                class_name = self.class_names.get(cls, f"unknown_{cls}")

                # Store detection
                detections.append({
                    'class': class_name,
                    'confidence': conf,
                    'position': self._get_position(x1, x2, frame.shape[1])
                })

                # Draw bounding box
                color = self.colors.get(class_name, (128, 128, 128))
                cv2.rectangle(annotated_frame, (x1, y1), (x2, y2), color, 2)

                # Draw label with background
                label = f"{class_name} {conf:.2f}"
                label_size = cv2.getTextSize(label, cv2.FONT_HERSHEY_SIMPLEX, 0.6, 2)[0]

                # Label background
                cv2.rectangle(annotated_frame,
                            (x1, y1 - label_size[1] - 10),
                            (x1 + label_size[0], y1),
                            color, -1)

                # Label text
                cv2.putText(annotated_frame, label,
                          (x1, y1 - 5),
                          cv2.FONT_HERSHEY_SIMPLEX,
                          0.6, (255, 255, 255), 2)

        # Get navigation guidance from Ollama
        if detections:
            detections_text = "\n".join([
                f"- {d['class']} ({d['confidence']:.0%} confidence) detected {d['position']}"
                for d in detections
            ])
            guidance = self.query_ollama(detections_text)
        else:
            guidance = "No obstacles detected. Path is clear."

        return annotated_frame, detections, guidance

    def _get_position(self, x1, x2, width):
        """Determine position (left/center/right)"""
        center = (x1 + x2) / 2

        if center < width * 0.33:
            return "on the LEFT"
        elif center > width * 0.67:
            return "on the RIGHT"
        else:
            return "in the CENTER"

    def add_info_panel(self, frame, detections, guidance):
        """Add information panel to frame"""
        h, w = frame.shape[:2]

        # Create info panel
        panel_height = 200
        panel = np.zeros((panel_height, w, 3), dtype=np.uint8)
        panel[:] = (40, 40, 40)  # Dark gray background

        # Title
        cv2.putText(panel, "AI NAVIGATION ASSISTANT - Sprint 2",
                   (10, 30), cv2.FONT_HERSHEY_SIMPLEX, 0.7, (0, 255, 255), 2)

        # Detections count
        cv2.putText(panel, f"Detected: {len(detections)} objects",
                   (10, 60), cv2.FONT_HERSHEY_SIMPLEX, 0.5, (255, 255, 255), 1)

        # Guidance (word wrap)
        y_offset = 90
        max_width = 80  # characters per line
        words = guidance.split()
        line = ""

        for word in words:
            if len(line + word) < max_width:
                line += word + " "
            else:
                cv2.putText(panel, line.strip(),
                           (10, y_offset), cv2.FONT_HERSHEY_SIMPLEX, 0.5, (0, 255, 0), 1)
                y_offset += 25
                line = word + " "

        if line:
            cv2.putText(panel, line.strip(),
                       (10, y_offset), cv2.FONT_HERSHEY_SIMPLEX, 0.5, (0, 255, 0), 1)

        # Instructions
        cv2.putText(panel, "Press 'q' to quit | 'c' to capture | 's' to save",
                   (10, panel_height - 10), cv2.FONT_HERSHEY_SIMPLEX, 0.4, (200, 200, 200), 1)

        # Combine frame and panel
        combined = np.vstack([frame, panel])
        return combined

    def run_webcam(self):
        """Run demo with webcam"""
        print("📷 Starting webcam demo...")
        print("   Press 'q' to quit")
        print("   Press 'c' to capture frame and get guidance")
        print()

        cap = cv2.VideoCapture(0)

        if not cap.isOpened():
            print("❌ Cannot access webcam")
            return

        guidance = "Point camera at objects to detect..."
        detections = []

        while True:
            ret, frame = cap.read()
            if not ret:
                break

            # Show live feed
            display_frame = frame.copy()

            # Add info
            display_frame = self.add_info_panel(display_frame, detections, guidance)

            cv2.imshow('AI Navigation Demo', display_frame)

            key = cv2.waitKey(1) & 0xFF

            if key == ord('q'):
                break
            elif key == ord('c'):
                print("📸 Capturing and analyzing...")
                annotated_frame, detections, guidance = self.process_frame(frame)
                print(f"   Detected: {len(detections)} objects")
                print(f"   Guidance: {guidance[:100]}...")

                # Show annotated result
                result = self.add_info_panel(annotated_frame, detections, guidance)
                cv2.imshow('AI Navigation Demo', result)
                cv2.waitKey(3000)  # Show for 3 seconds

        cap.release()
        cv2.destroyAllWindows()

    def run_image(self, image_path):
        """Run demo with static image"""
        print(f"🖼️  Loading image: {image_path}")

        frame = cv2.imread(image_path)
        if frame is None:
            print(f"❌ Cannot load image: {image_path}")
            return

        print("🔍 Detecting objects...")
        annotated_frame, detections, guidance = self.process_frame(frame)

        print(f"✅ Detected {len(detections)} objects:")
        for d in detections:
            print(f"   - {d['class']} ({d['confidence']:.0%}) {d['position']}")

        print()
        print("🤖 Navigation Guidance:")
        print(f"   {guidance}")
        print()

        # Show result
        result = self.add_info_panel(annotated_frame, detections, guidance)

        cv2.imshow('AI Navigation Demo', result)
        print("Press any key to close...")
        cv2.waitKey(0)
        cv2.destroyAllWindows()

        # Save result
        output_path = image_path.replace('.', '_annotated.')
        cv2.imwrite(output_path, result)
        print(f"💾 Saved annotated image: {output_path}")

def main():
    """Run demo"""
    import argparse

    parser = argparse.ArgumentParser(description='Visual Navigation Demo with Ollama')
    parser.add_argument('--model', type=str,
                       default='models/object_detection/best.pt',
                       help='Path to YOLO model')
    parser.add_argument('--webcam', action='store_true',
                       help='Use webcam (default: use sample image)')
    parser.add_argument('--image', type=str,
                       help='Path to image file (if not using webcam)')

    args = parser.parse_args()

    # Initialize demo
    demo = VisualNavigationDemo(args.model, use_webcam=args.webcam)

    if args.webcam:
        demo.run_webcam()
    elif args.image:
        demo.run_image(args.image)
    else:
        # Find sample image in data
        print("🔍 Looking for sample images...")
        sample_paths = [
            "data/processed/val_dataset/val/images/*.jpg",
            "data/processed/train_dataset/train/images/*.jpg"
        ]

        from glob import glob
        for pattern in sample_paths:
            images = glob(pattern)
            if images:
                demo.run_image(images[0])
                break
        else:
            print("❌ No sample images found. Use --image or --webcam")
            print()
            print("Usage:")
            print("  python visual_navigation_demo.py --image path/to/image.jpg")
            print("  python visual_navigation_demo.py --webcam")

if __name__ == "__main__":
    main()
