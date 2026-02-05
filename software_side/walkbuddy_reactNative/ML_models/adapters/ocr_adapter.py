import json
import os
from pathlib import Path
from typing import Dict, Any, List, Tuple
import cv2
import numpy as np

# Try to import EasyOCR
try:
    import easyocr
except ImportError:
    raise ImportError("EasyOCR is not installed.")

# Try to detect GPU
try:
    import torch
    GPU_AVAILABLE = torch.cuda.is_available()
except ImportError:
    GPU_AVAILABLE = False

THIS_DIR = Path(__file__).resolve().parent
_ocr_reader = None

def _load_ocr_reader():
    global _ocr_reader
    if _ocr_reader is None:
        print(f"[OCR Adapter] Initializing EasyOCR (GPU: {GPU_AVAILABLE})...")
        _ocr_reader = easyocr.Reader(['en'], gpu=GPU_AVAILABLE)
    return _ocr_reader

def _convert_4corners_to_bbox(bbox_corners):
    x_coords = [p[0] for p in bbox_corners]
    y_coords = [p[1] for p in bbox_corners]
    return {
        "x_min": int(min(x_coords)),
        "y_min": int(min(y_coords)),
        "x_max": int(max(x_coords)),
        "y_max": int(max(y_coords))
    }

def ocr_adapter(image_path: str) -> Dict[str, Any]:
    image_path_obj = Path(image_path)
    if not image_path_obj.exists():
        raise FileNotFoundError(f"Image not found: {image_path}")
    
    # CRITICAL FIX: Validate image before loading with EasyOCR
    # This prevents the "OpenCV Assertion Failed" crash on empty files
    check_img = cv2.imread(str(image_path))
    if check_img is None or check_img.size == 0:
        print(f"[OCR Adapter] Error: Image at {image_path} is empty or unreadable.")
        return {
            "image_id": image_path_obj.stem,
            "detections": []
        }

    reader = _load_ocr_reader()
    
    print("[OCR Adapter] Running inference...")
    try:
        raw_results = reader.readtext(str(image_path))
    except Exception as e:
        print(f"[OCR Adapter] Inference failed: {e}")
        return {
            "image_id": image_path_obj.stem,
            "detections": []
        }

    clean_output = {
        "image_id": image_path_obj.stem,
        "detections": []
    }
    
    for detection in raw_results:
        # EasyOCR format: (bbox_points, text, confidence)
        if len(detection) >= 3:
            bbox_corners = detection[0]
            text = str(detection[1])
            conf = float(detection[2])
            
            # Filter low confidence junk
            if conf < 0.3: 
                continue

            try:
                bbox = _convert_4corners_to_bbox(bbox_corners)
                clean_output["detections"].append({
                    "category": text.strip(),
                    "confidence": round(conf, 4),
                    "bbox": bbox
                })
            except Exception:
                continue

    # Sort by confidence
    clean_output["detections"].sort(key=lambda x: x["confidence"], reverse=True)
    return clean_output