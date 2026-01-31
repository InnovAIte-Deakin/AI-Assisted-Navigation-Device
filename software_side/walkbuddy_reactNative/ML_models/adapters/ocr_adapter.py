"""
OCR Adapter for AI-Assisted Navigation Device

This adapter function standardizes EasyOCR output into a clean, consistent JSON format.
It handles the conversion from raw EasyOCR text detection results to a structured format
that can be easily consumed by downstream applications.

Author: ML Engineering Team
Purpose: Standardize OCR model outputs for navigation device
"""

import json
import os
from pathlib import Path
from typing import Dict, List, Any, Tuple
import cv2
import numpy as np

# Try to import EasyOCR
try:
    import easyocr
except ImportError:
    raise ImportError(
        "EasyOCR is not installed. Please install it with: pip install easyocr"
    )

# Try to detect GPU availability
try:
    import torch
    GPU_AVAILABLE = torch.cuda.is_available()
except ImportError:
    GPU_AVAILABLE = False

# ============================================================================
# CONFIGURATION
# ============================================================================

# Get the directory where this script is located
THIS_DIR = Path(__file__).resolve().parent

# Output directories
RAW_OUTPUTS_DIR = THIS_DIR / "raw_outputs"
SAMPLE_OUTPUTS_DIR = THIS_DIR / "sample_outputs"

# Ensure output directories exist
RAW_OUTPUTS_DIR.mkdir(parents=True, exist_ok=True)
SAMPLE_OUTPUTS_DIR.mkdir(parents=True, exist_ok=True)

# ============================================================================
# GLOBAL OCR READER INSTANCE (loaded once for efficiency)
# ============================================================================

_ocr_reader = None


def _load_ocr_reader():
    """
    Load EasyOCR reader singleton to avoid reloading on every call.
    EasyOCR initialization is expensive, so we load it once and reuse.
    
    Returns:
        easyocr.Reader: Initialized EasyOCR reader instance
    """
    global _ocr_reader
    if _ocr_reader is None:
        print(f"[OCR Adapter] Initializing EasyOCR reader (GPU: {GPU_AVAILABLE})...")
        # Initialize with English language support
        # Set gpu=True if CUDA is available for faster processing
        _ocr_reader = easyocr.Reader(['en'], gpu=GPU_AVAILABLE)
        print("[OCR Adapter] EasyOCR reader initialized successfully")
    return _ocr_reader


# ============================================================================
# RAW OUTPUT SAVING
# ============================================================================

def _save_raw_output(image_path: str, raw_results: List[Tuple]) -> str:
    """
    Save raw EasyOCR output to JSON file for comparison.
    
    EasyOCR returns results in the format:
    [
        ( [text, confidence], [ [x1,y1], [x2,y2], [x3,y3], [x4,y4] ] ),
        ...
    ]
    
    This function saves this raw format exactly as received from EasyOCR.
    
    Args:
        image_path: Path to the input image
        raw_results: Raw EasyOCR results list
    
    Returns:
        str: Path to the saved raw output JSON file
    """
    # Extract image ID from filename
    image_id = Path(image_path).stem
    
    # Convert raw results to JSON-serializable format
    raw_data = {
        "image_id": image_id,
        "image_path": str(image_path),
        "model_type": "EasyOCR",
        "raw_detections": []
    }
    
    # Process each detection from EasyOCR
    # EasyOCR format: (bbox_points, text, confidence)
    # bbox_points: [[x1,y1], [x2,y2], [x3,y3], [x4,y4]]
    # text: string
    # confidence: float
    for i, detection in enumerate(raw_results):
        if isinstance(detection, (list, tuple)) and len(detection) >= 3:
            # Correct EasyOCR format: (bbox_points, text, confidence)
            bbox_corners = detection[0]  # List of 4 corner points
            text = str(detection[1])     # Text string
            confidence = float(detection[2])  # Confidence score
        elif isinstance(detection, (list, tuple)) and len(detection) >= 2:
            # Fallback format: try to infer
            if isinstance(detection[0], list) and len(detection[0]) == 4:
                # First element is bbox
                bbox_corners = detection[0]
                text = str(detection[1]) if len(detection) > 1 else ""
                confidence = float(detection[2]) if len(detection) > 2 else 1.0
            else:
                # Different format, try to extract
                text = str(detection[0]) if len(detection) > 0 else ""
                confidence = float(detection[1]) if len(detection) > 1 else 1.0
                bbox_corners = []
        else:
            text = ""
            confidence = 1.0
            bbox_corners = []
        
        # Convert numpy types to native Python types for JSON serialization
        bbox_corners_python = []
        if bbox_corners:
            for corner in bbox_corners:
                if isinstance(corner, (list, tuple)):
                    bbox_corners_python.append([int(corner[0]), int(corner[1])])
                else:
                    bbox_corners_python.append([int(corner[0]), int(corner[1])])
        
        raw_data["raw_detections"].append({
            "detection_id": i,
            "text": text,
            "confidence": float(confidence),  # Ensure float, not numpy float
            "bbox_corners": bbox_corners_python,  # [[x1,y1], [x2,y2], [x3,y3], [x4,y4]]
            "bbox_format": "4_corners"  # EasyOCR uses 4 corner points
        })
    
    # Add metadata
    raw_data["num_detections"] = len(raw_data["raw_detections"])
    
    # Save to file
    output_path = RAW_OUTPUTS_DIR / f"{image_id}_ocr_raw.json"
    with open(output_path, 'w') as f:
        json.dump(raw_data, f, indent=2)
    
    print(f"[OCR Adapter] Raw output saved to: {output_path}")
    return str(output_path)


# ============================================================================
# BOUNDING BOX CONVERSION UTILITY
# ============================================================================

def _convert_4corners_to_bbox(bbox_corners: List[List[float]]) -> Dict[str, int]:
    """
    Convert EasyOCR's 4-corner bounding box format to standard x_min, y_min, x_max, y_max format.
    
    EasyOCR provides 4 corner points: [top-left, top-right, bottom-right, bottom-left]
    We need to find the min/max x and y coordinates to create a rectangular bounding box.
    
    Args:
        bbox_corners: List of 4 corner points [[x1,y1], [x2,y2], [x3,y3], [x4,y4]]
    
    Returns:
        Dict with keys: x_min, y_min, x_max, y_max
    """
    if not bbox_corners or len(bbox_corners) != 4:
        raise ValueError(f"Invalid bbox_corners format. Expected 4 points, got {len(bbox_corners)}")
    
    # Extract all x and y coordinates
    x_coords = [point[0] for point in bbox_corners]
    y_coords = [point[1] for point in bbox_corners]
    
    # Find min and max coordinates
    return {
        "x_min": int(min(x_coords)),
        "y_min": int(min(y_coords)),
        "x_max": int(max(x_coords)),
        "y_max": int(max(y_coords))
    }


# ============================================================================
# ADAPTER FUNCTION - MAIN ENTRY POINT
# ============================================================================

def ocr_adapter(image_path: str) -> Dict[str, Any]:
    """
    OCR Adapter - Converts raw EasyOCR output to standardized JSON format.
    
    This is the main adapter function that:
    1. Loads the EasyOCR reader (if not already loaded)
    2. Runs OCR inference on the input image
    3. Saves the RAW OCR output for comparison
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
                    "category": "<string>",  # The detected text
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
    
    print(f"\n[OCR Adapter] Processing image: {image_path}")
    
    # Load EasyOCR reader
    reader = _load_ocr_reader()
    
    # Read image using OpenCV (EasyOCR can work with file paths, but we validate first)
    img = cv2.imread(str(image_path))
    if img is None:
        raise ValueError(f"Could not load image: {image_path}")
    
    # Run OCR inference
    # EasyOCR.readtext() returns: [ ( [text, confidence], [bbox_points] ), ... ]
    print("[OCR Adapter] Running OCR inference...")
    raw_results = reader.readtext(str(image_path))
    
    # Save raw output BEFORE adapter processing
    raw_output_path = _save_raw_output(image_path, raw_results)
    
    # ========================================================================
    # ADAPTER LOGIC: Convert raw EasyOCR output to standardized format
    # ========================================================================
    
    # Extract image ID from filename
    image_id = image_path_obj.stem
    
    # Initialize clean output structure
    clean_output = {
        "image_id": image_id,
        "detections": []
    }
    
    # Process each detection from EasyOCR
    # EasyOCR format: (bbox_points, text, confidence)
    # bbox_points: [[x1,y1], [x2,y2], [x3,y3], [x4,y4]]
    # text: string
    # confidence: float
    for detection in raw_results:
        if isinstance(detection, (list, tuple)) and len(detection) >= 3:
            # Correct EasyOCR format: (bbox_points, text, confidence)
            bbox_corners = detection[0]  # List of 4 corner points
            text = str(detection[1])      # Text string
            confidence = float(detection[2])  # Confidence score
        elif isinstance(detection, (list, tuple)) and len(detection) >= 2:
            # Fallback format: try to infer
            if isinstance(detection[0], list) and len(detection[0]) == 4:
                # First element is bbox
                bbox_corners = detection[0]
                text = str(detection[1]) if len(detection) > 1 else ""
                confidence = float(detection[2]) if len(detection) > 2 else 1.0
            else:
                # Different format
                text = str(detection[0]) if len(detection) > 0 else ""
                confidence = float(detection[1]) if len(detection) > 1 else 1.0
                bbox_corners = []
        else:
            text = ""
            confidence = 1.0
            bbox_corners = []
        
        # Convert 4-corner bbox to standard x_min, y_min, x_max, y_max format
        # First convert numpy types to Python native types
        bbox_corners_python = []
        if bbox_corners:
            for corner in bbox_corners:
                if isinstance(corner, (list, tuple)):
                    bbox_corners_python.append([int(corner[0]), int(corner[1])])
                else:
                    bbox_corners_python.append([int(corner[0]), int(corner[1])])
        else:
            continue  # Skip if no bbox
        
        try:
            bbox = _convert_4corners_to_bbox(bbox_corners_python)
        except ValueError as e:
            print(f"[OCR Adapter] Warning: Skipping invalid bbox: {e}")
            continue
        
        # Create standardized detection object
        # For OCR, the "category" is the detected text itself
        detection_obj = {
            "category": text.strip(),  # Remove leading/trailing whitespace
            "confidence": round(confidence, 4),  # Round to 4 decimal places
            "bbox": bbox
        }
        
        clean_output["detections"].append(detection_obj)
    
    # Sort detections by confidence (highest first) for better readability
    clean_output["detections"].sort(key=lambda x: x["confidence"], reverse=True)
    
    # ========================================================================
    # SAVE CLEAN OUTPUT
    # ========================================================================
    
    output_path = SAMPLE_OUTPUTS_DIR / f"{image_id}_ocr_clean.json"
    with open(output_path, 'w') as f:
        json.dump(clean_output, f, indent=2)
    
    print(f"[OCR Adapter] Clean output saved to: {output_path}")
    print(f"[OCR Adapter] Found {len(clean_output['detections'])} text detections")
    
    return clean_output


# ============================================================================
# STANDALONE TESTING
# ============================================================================

if __name__ == "__main__":
    """
    Test the adapter with a sample image.
    Usage: python ocr_adapter.py <image_path>
    """
    import sys
    
    if len(sys.argv) < 2:
        print("Usage: python ocr_adapter.py <image_path>")
        print("Example: python ocr_adapter.py ../sample_images/test.jpg")
        sys.exit(1)
    
    image_path = sys.argv[1]
    try:
        result = ocr_adapter(image_path)
        print("\n" + "="*60)
        print("CLEAN OUTPUT (Standardized JSON):")
        print("="*60)
        print(json.dumps(result, indent=2))
    except Exception as e:
        print(f"Error: {e}")
        import traceback
        traceback.print_exc()

