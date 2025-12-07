"""
YOLO Adapter for AI-Assisted Navigation Device

This adapter function standardizes YOLO model output into a clean, consistent JSON format.
It handles the conversion from raw YOLO detection results to a structured format that
can be easily consumed by downstream applications.

Author: ML Engineering Team
Purpose: Standardize vision model outputs for navigation device
"""

import json
import os
from pathlib import Path
from typing import Dict, List, Any
from ultralytics import YOLO
import cv2
import numpy as np

# ============================================================================
# CONFIGURATION
# ============================================================================

# Get the directory where this script is located
THIS_DIR = Path(__file__).resolve().parent
PROJECT_ROOT = THIS_DIR.parent

# Path to YOLO model weights (using the existing model in the project)
YOLO_WEIGHTS = PROJECT_ROOT / "yolo_nav" / "weights" / "yolov8s.pt"

# Output directories
RAW_OUTPUTS_DIR = THIS_DIR / "raw_outputs"
SAMPLE_OUTPUTS_DIR = THIS_DIR / "sample_outputs"

# Ensure output directories exist
RAW_OUTPUTS_DIR.mkdir(parents=True, exist_ok=True)
SAMPLE_OUTPUTS_DIR.mkdir(parents=True, exist_ok=True)

# ============================================================================
# GLOBAL MODEL INSTANCE (loaded once for efficiency)
# ============================================================================

_model_instance = None


def _load_yolo_model():
    """
    Load YOLO model singleton to avoid reloading on every call.
    
    Returns:
        YOLO: Loaded YOLO model instance
    """
    global _model_instance
    if _model_instance is None:
        if not YOLO_WEIGHTS.exists():
            raise FileNotFoundError(
                f"YOLO weights not found at {YOLO_WEIGHTS}. "
                "Please ensure the model weights are available."
            )
        print(f"[YOLO Adapter] Loading model from {YOLO_WEIGHTS}")
        _model_instance = YOLO(str(YOLO_WEIGHTS))
        print(f"[YOLO Adapter] Model loaded successfully. Classes: {_model_instance.names}")
    return _model_instance


# ============================================================================
# RAW OUTPUT SAVING
# ============================================================================

def _save_raw_output(image_path: str, raw_results: Any) -> str:
    """
    Save raw YOLO model output to JSON file for comparison.
    
    This function extracts all the raw data from YOLO results object,
    including boxes, confidences, class IDs, and other metadata.
    
    Args:
        image_path: Path to the input image
        raw_results: Raw YOLO results object (ultralytics.engine.results.Results)
    
    Returns:
        str: Path to the saved raw output JSON file
    """
    # Extract image ID from filename
    image_id = Path(image_path).stem
    
    # Extract raw detection data from YOLO results
    raw_data = {
        "image_id": image_id,
        "image_path": str(image_path),
        "model_type": "YOLOv8",
        "raw_detections": []
    }
    
    # YOLO results contain boxes, confidences, and class IDs
    if raw_results.boxes is not None and len(raw_results.boxes) > 0:
        # Get all detection data
        boxes = raw_results.boxes.xyxy.cpu().numpy().tolist()  # [x1, y1, x2, y2]
        confidences = raw_results.boxes.conf.cpu().numpy().tolist()
        class_ids = raw_results.boxes.cls.cpu().int().tolist()
        
        # Combine into raw format (similar to what YOLO outputs internally)
        for i, (box, conf, cls_id) in enumerate(zip(boxes, confidences, class_ids)):
            raw_data["raw_detections"].append({
                "detection_id": i,
                "bbox_raw": box,  # [x1, y1, x2, y2] as list
                "confidence": float(conf),
                "class_id": int(cls_id),
                "class_name": raw_results.names[int(cls_id)] if hasattr(raw_results, 'names') else f"class_{int(cls_id)}"
            })
    
    # Add metadata
    raw_data["num_detections"] = len(raw_data["raw_detections"])
    raw_data["image_shape"] = list(raw_results.orig_shape) if hasattr(raw_results, 'orig_shape') else None
    
    # Save to file
    output_path = RAW_OUTPUTS_DIR / f"{image_id}_yolo_raw.json"
    with open(output_path, 'w') as f:
        json.dump(raw_data, f, indent=2)
    
    print(f"[YOLO Adapter] Raw output saved to: {output_path}")
    return str(output_path)


# ============================================================================
# ADAPTER FUNCTION - MAIN ENTRY POINT
# ============================================================================

def vision_adapter(image_path: str) -> Dict[str, Any]:
    """
    YOLO Vision Adapter - Converts raw YOLO output to standardized JSON format.
    
    This is the main adapter function that:
    1. Loads the YOLO model (if not already loaded)
    2. Runs inference on the input image
    3. Saves the RAW model output for comparison
    4. Converts the output to clean, standardized JSON
    5. Saves the cleaned output
    
    Args:
        image_path: Path to the input image file (supports common formats: jpg, png, etc.)
    
    Returns:
        Dict containing standardized detection results in the format:
        {
            "image_id": "<string>",
            "detections": [
                {
                    "category": "<string>",
                    "confidence": <float>,
                    "bbox": {
                        "x_min": <int>,
                        "y_min": <int>,
                        "x_max": <int>,
                        "y_max": <int>
                    }
                }
            ]
        }
    
    Raises:
        FileNotFoundError: If image_path doesn't exist
        ValueError: If image cannot be loaded
    """
    # Validate input image exists
    image_path_obj = Path(image_path)
    if not image_path_obj.exists():
        raise FileNotFoundError(f"Image not found: {image_path}")
    
    print(f"\n[YOLO Adapter] Processing image: {image_path}")
    
    # Load YOLO model
    model = _load_yolo_model()
    
    # Run inference
    # YOLO model.predict() returns a list of Results objects
    print("[YOLO Adapter] Running inference...")
    results = model.predict(
        source=str(image_path),
        conf=0.25,  # Confidence threshold (adjust as needed)
        iou=0.45,   # IoU threshold for NMS
        verbose=False  # Suppress detailed output
    )
    
    # Get first result (single image inference)
    result = results[0]
    
    # Save raw output BEFORE adapter processing
    raw_output_path = _save_raw_output(image_path, result)
    
    # ========================================================================
    # ADAPTER LOGIC: Convert raw YOLO output to standardized format
    # ========================================================================
    
    # Extract image ID from filename
    image_id = image_path_obj.stem
    
    # Initialize clean output structure
    clean_output = {
        "image_id": image_id,
        "detections": []
    }
    
    # Process detections if any exist
    if result.boxes is not None and len(result.boxes) > 0:
        # Extract detection data
        boxes = result.boxes.xyxy.cpu().numpy()  # Shape: [N, 4] where N = num detections
        confidences = result.boxes.conf.cpu().numpy()  # Shape: [N]
        class_ids = result.boxes.cls.cpu().int().numpy()  # Shape: [N]
        
        # Get class names from model
        class_names = result.names if hasattr(result, 'names') else {}
        
        # Convert each detection to standardized format
        for i in range(len(boxes)):
            # Extract bounding box coordinates
            x1, y1, x2, y2 = boxes[i]
            
            # Get class name
            cls_id = int(class_ids[i])
            category = class_names.get(cls_id, f"class_{cls_id}")
            
            # Get confidence score
            confidence = float(confidences[i])
            
            # Create standardized detection object
            detection = {
                "category": category,
                "confidence": round(confidence, 4),  # Round to 4 decimal places
                "bbox": {
                    "x_min": int(x1),
                    "y_min": int(y1),
                    "x_max": int(x2),
                    "y_max": int(y2)
                }
            }
            
            clean_output["detections"].append(detection)
    
    # Sort detections by confidence (highest first) for better readability
    clean_output["detections"].sort(key=lambda x: x["confidence"], reverse=True)
    
    # ========================================================================
    # SAVE CLEAN OUTPUT
    # ========================================================================
    
    output_path = SAMPLE_OUTPUTS_DIR / f"{image_id}_yolo_clean.json"
    with open(output_path, 'w') as f:
        json.dump(clean_output, f, indent=2)
    
    print(f"[YOLO Adapter] Clean output saved to: {output_path}")
    print(f"[YOLO Adapter] Found {len(clean_output['detections'])} detections")
    
    return clean_output


# ============================================================================
# STANDALONE TESTING
# ============================================================================

if __name__ == "__main__":
    """
    Test the adapter with a sample image.
    Usage: python yolo_adapter.py <image_path>
    """
    import sys
    
    if len(sys.argv) < 2:
        print("Usage: python yolo_adapter.py <image_path>")
        print("Example: python yolo_adapter.py ../sample_images/test.jpg")
        sys.exit(1)
    
    image_path = sys.argv[1]
    try:
        result = vision_adapter(image_path)
        print("\n" + "="*60)
        print("CLEAN OUTPUT (Standardized JSON):")
        print("="*60)
        print(json.dumps(result, indent=2))
    except Exception as e:
        print(f"Error: {e}")
        import traceback
        traceback.print_exc()

