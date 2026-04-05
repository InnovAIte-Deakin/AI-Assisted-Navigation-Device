"""
Basic LLM Integration Pipeline - Starter Implementation
Run this first to test the core functionality
"""

import cv2
import numpy as np
from ultralytics import YOLO
from datetime import datetime
import json
import os
from .llm_reasoning_engine import LLMNavigationReasoner

class BasicNavigationPipeline:
    def __init__(self, model_path, use_llm=True, llm_model_type="openai"):
        """Initialize with your trained YOLO model and LLM reasoner"""
        self.yolo_model = YOLO(model_path)
        # Sprint 2: Expanded to 15 classes for comprehensive navigation
        self.class_names = {
            # Sprint 1 classes (library objects)
            0: "book",
            1: "books",
            2: "monitor",
            3: "office-chair",
            4: "whiteboard",
            5: "table",
            6: "tv",
            # Sprint 2 new classes (navigation & safety)
            7: "door",
            8: "stairs",
            9: "elevator",
            10: "person",
            11: "handrail",
            12: "signage",
            13: "fire-extinguisher",
            14: "emergency-exit"
        }

        # Object priority levels (1=lowest → 5=critical)
        # Determines urgency of navigation warnings and alert ordering
        self.object_priorities = {
            # Critical — immediate hazard or evacuation route
            "stairs":            5,
            "emergency-exit":    5,
            # High — moving hazard or emergency equipment
            "person":            4,
            "fire-extinguisher": 4,
            # Medium — navigation aids and transitions
            "door":              3,
            "elevator":          3,
            "handrail":          3,
            # Low — informational / environmental
            "signage":           2,
            "whiteboard":        2,
            "tv":                2,
            # Minimal — static furniture
            "book":              1,
            "books":             1,
            "monitor":           1,
            "office-chair":      1,
            "table":             1,
        }

        # Colour coding for bounding boxes by priority (BGR)
        self.priority_colours = {
            5: (0, 0, 255),    # Red   — critical
            4: (0, 128, 255),  # Orange — high
            3: (0, 255, 255),  # Yellow — medium
            2: (0, 255, 128),  # Mint   — low
            1: (0, 255, 0),    # Green  — minimal
        }
        
        # Initialize LLM reasoner
        self.use_llm = use_llm
        if use_llm:
            self.llm_reasoner = LLMNavigationReasoner(model_type=llm_model_type)
            print("✅ LLM Navigation Reasoner initialized")
        else:
            self.llm_reasoner = None
            print("ℹ️ Using rule-based reasoning only")
    
    def process_frame(self, image, user_intent="Navigate safely", current_location="Library"):
        """Process single frame and return enhanced detections"""
        # Run YOLO detection
        results = self.yolo_model.predict(image, conf=0.5, verbose=False)
        
        # Convert to our enhanced format
        detections = self._convert_detections(results[0], image.shape)
        
        # Basic spatial analysis
        spatial_context = self._analyze_spatial_relationships(detections)
        
        # Advanced navigation reasoning with LLM
        if self.use_llm and self.llm_reasoner:
            navigation_decision = self.llm_reasoner.reason_about_navigation(
                detections, spatial_context, user_intent, current_location
            )
        else:
            navigation_decision = self._basic_navigation_reasoning(detections, spatial_context)
        
        return {
            'detections': detections,
            'spatial_context': spatial_context,
            'navigation_decision': navigation_decision,
            'timestamp': datetime.now()
        }
    
    def _convert_detections(self, yolo_result, image_shape):
        """Convert YOLO results to enhanced format"""
        detections = []
        
        if yolo_result.boxes is None:
            return detections
        
        boxes = yolo_result.boxes
        height, width = image_shape[:2]
        
        for i in range(len(boxes)):
            # Extract YOLO data
            xyxy = boxes.xyxy[i].cpu().numpy()
            conf = float(boxes.conf[i].cpu().numpy())
            cls = int(boxes.cls[i].cpu().numpy())
            
            # Calculate enhanced properties
            x1, y1, x2, y2 = xyxy
            center_x = (x1 + x2) / 2
            center_y = (y1 + y2) / 2
            box_width = x2 - x1
            box_height = y2 - y1
            area = box_width * box_height
            
            class_name = self.class_names.get(cls, f"unknown_{cls}")
            priority = self.object_priorities.get(class_name, 1)

            detection = {
                'class_id': cls,
                'class_name': class_name,
                'confidence': conf,
                'priority': priority,
                'priority_label': self._priority_label(priority),
                'bbox': {
                    'x1': float(x1), 'y1': float(y1), 'x2': float(x2), 'y2': float(y2),
                    'center_x': float(center_x), 'center_y': float(center_y),
                    'width': float(box_width), 'height': float(box_height)
                },
                'area': float(area),
                'relative_size': self._get_relative_size(area, width * height),
                'frame_position': self._get_frame_position(center_x, center_y, width, height)
            }

            detections.append(detection)

        # Sort highest priority first so warnings are ordered by urgency
        detections.sort(key=lambda d: d['priority'], reverse=True)
        return detections

    def _priority_label(self, priority: int) -> str:
        """Human-readable priority label"""
        return {5: "CRITICAL", 4: "HIGH", 3: "MEDIUM", 2: "LOW", 1: "MINIMAL"}.get(priority, "MINIMAL")
    
    def _get_relative_size(self, area, image_area):
        """Determine relative size category"""
        ratio = area / image_area
        if ratio < 0.05:
            return "small"
        elif ratio < 0.2:
            return "medium"
        else:
            return "large"
    
    def _get_frame_position(self, x, y, width, height):
        """Determine position within frame"""
        x_ratio = x / width
        y_ratio = y / height
        
        if x_ratio < 0.33:
            h_pos = "left"
        elif x_ratio > 0.67:
            h_pos = "right"
        else:
            h_pos = "center"
        
        if y_ratio < 0.33:
            v_pos = "top"
        elif y_ratio > 0.67:
            v_pos = "bottom"
        else:
            v_pos = "center"
        
        if h_pos == "center" and v_pos == "center":
            return "center"
        elif h_pos == "center":
            return v_pos
        elif v_pos == "center":
            return h_pos
        else:
            return f"{v_pos}-{h_pos}"
    
    def _analyze_spatial_relationships(self, detections):
        """Basic spatial relationship analysis"""
        if len(detections) < 2:
            return {'relationships': [], 'scene_density': 'sparse', 'object_count': len(detections)}
        
        relationships = []
        for i, det1 in enumerate(detections):
            for j, det2 in enumerate(detections[i+1:], i+1):
                # Calculate distance between centers
                dx = det1['bbox']['center_x'] - det2['bbox']['center_x']
                dy = det1['bbox']['center_y'] - det2['bbox']['center_y']
                distance = np.sqrt(dx**2 + dy**2)
                
                # Determine relationship
                if abs(dx) > abs(dy) and abs(dx) > 50:
                    relation = "left of" if dx > 0 else "right of"
                elif abs(dy) > abs(dx) and abs(dy) > 50:
                    relation = "above" if dy > 0 else "below"
                else:
                    relation = "near"
                
                relationships.append({
                    'object1': det1['class_name'],
                    'object2': det2['class_name'],
                    'relationship': relation,
                    'distance': float(distance)
                })
        
        scene_density = "sparse" if len(detections) <= 2 else "moderate" if len(detections) <= 5 else "crowded"
        
        return {
            'relationships': relationships,
            'scene_density': scene_density,
            'object_count': len(detections)
        }
    
    def _basic_navigation_reasoning(self, detections, spatial_context):
        """Priority-aware navigation reasoning (fallback when LLM unavailable)"""
        if not detections:
            return {
                'direction': "No objects detected, proceed with caution",
                'obstacles': "None detected",
                'landmarks': "None available",
                'safety_level': "Low",
                'highest_priority': None
            }

        # detections already sorted by priority (highest first)
        center_detections = [d for d in detections if d['frame_position'] in ['center', 'bottom-center']]
        landmarks = [d['class_name'] for d in detections if d['confidence'] > 0.7]

        # Use the highest-priority detected object to drive the response
        top = detections[0]

        if top['priority'] == 5:
            direction = f"WARNING: {top['class_name'].upper()} detected. Stop and assess before proceeding."
            safety_level = "High"
        elif top['priority'] == 4:
            direction = f"Caution: {top['class_name']} nearby. Slow down and navigate carefully."
            safety_level = "High"
        elif center_detections:
            top_center = center_detections[0]
            direction = f"Obstacle ahead ({top_center['class_name']}). Move around it."
            safety_level = "Medium"
        else:
            direction = "Path appears clear, proceed forward"
            safety_level = "Low"

        return {
            'direction': direction,
            'obstacles': ', '.join(d['class_name'] for d in center_detections) or "None",
            'landmarks': ', '.join(landmarks) if landmarks else "None",
            'safety_level': safety_level,
            'highest_priority': {
                'object': top['class_name'],
                'level': top['priority'],
                'label': top['priority_label']
            }
        }

# Test the pipeline
if __name__ == "__main__":
    # Initialize pipeline with your model
    model_path = "models/object_detection/best.pt"  # Update this path to your model location
    
    # Check if model exists
    if not os.path.exists(model_path):
        print(f"Model not found at {model_path}")
        print("Please update the model_path variable to point to your trained YOLO model")
        print("Common locations:")
        print("- models/object_detection/best.pt")
        print("- experiments/object_detection/yolo_v8s_heavy_aug/weights/best.pt")
        exit(1)
    
    pipeline = BasicNavigationPipeline(model_path)
    
    # Test with webcam
    cap = cv2.VideoCapture(0)
    
    if not cap.isOpened():
        print("Cannot open camera. Testing with a sample image instead...")
        
        # Try to find a sample image
        sample_paths = [
            "data/processed/val_dataset/val/images/",
            "data/processed/train_dataset/train/images/"
        ]
        
        sample_image = None
        for path in sample_paths:
            if os.path.exists(path):
                import glob
                images = glob.glob(os.path.join(path, "*.jpg"))[:1]
                if images:
                    sample_image = cv2.imread(images[0])
                    print(f"Using sample image: {images[0]}")
                    break
        
        if sample_image is not None:
            result = pipeline.process_frame(sample_image)
            
            print(f"\n--- Sample Image Analysis ---")
            print(f"Detections: {len(result['detections'])}")
            for det in result['detections']:
                print(f"  - {det['class_name']} ({det['confidence']:.2f}) at {det['frame_position']}")
            
            print(f"Spatial: {result['spatial_context']['scene_density']} scene with {result['spatial_context']['object_count']} objects")
            print(f"Navigation: {result['navigation_decision']['direction']}")
            print(f"Safety: {result['navigation_decision']['safety_level']}")
            
            # Show result
            display_frame = sample_image.copy()
            for det in result['detections']:
                bbox  = det['bbox']
                colour = pipeline.priority_colours.get(det['priority'], (0, 255, 0))
                cv2.rectangle(display_frame,
                              (int(bbox['x1']), int(bbox['y1'])),
                              (int(bbox['x2']), int(bbox['y2'])),
                              colour, 2)
                label = f"{det['class_name']} [{det['priority_label']}] {det['confidence']:.2f}"
                cv2.putText(display_frame, label,
                            (int(bbox['x1']), int(bbox['y1']) - 10),
                            cv2.FONT_HERSHEY_SIMPLEX, 0.45, colour, 2)

            cv2.imshow('Navigation Pipeline Test', display_frame)
            cv2.waitKey(0)
            cv2.destroyAllWindows()
        else:
            print("No sample images found. Please check your data directory.")
        exit(0)

    print("Starting navigation pipeline test...")
    print("Press 'q' to quit")

    try:
        while True:
            ret, frame = cap.read()
            if not ret:
                break

            result = pipeline.process_frame(frame)

            print(f"\n--- Frame Analysis ---")
            for det in result['detections']:
                print(f"  [{det['priority_label']}] {det['class_name']} ({det['confidence']:.2f}) at {det['frame_position']}")

            print(f"Spatial: {result['spatial_context']['scene_density']} scene with {result['spatial_context']['object_count']} objects")
            print(f"Navigation: {result['navigation_decision']['direction']}")
            print(f"Safety: {result['navigation_decision']['safety_level']}")

            display_frame = frame.copy()
            for det in result['detections']:
                bbox   = det['bbox']
                colour = pipeline.priority_colours.get(det['priority'], (0, 255, 0))
                cv2.rectangle(display_frame,
                              (int(bbox['x1']), int(bbox['y1'])),
                              (int(bbox['x2']), int(bbox['y2'])),
                              colour, 2)
                label = f"{det['class_name']} [{det['priority_label']}] {det['confidence']:.2f}"
                cv2.putText(display_frame, label,
                            (int(bbox['x1']), int(bbox['y1']) - 10),
                            cv2.FONT_HERSHEY_SIMPLEX, 0.45, colour, 2)

            cv2.imshow('Navigation Pipeline Test', display_frame)

            if cv2.waitKey(1) & 0xFF == ord('q'):
                break
                
    except KeyboardInterrupt:
        print("\nShutting down...")
    finally:
        cap.release()
        cv2.destroyAllWindows()