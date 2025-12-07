import sys
from pathlib import Path

# 1. Fix Python path so ML_models/ imports work reliably
CURRENT_FILE = Path(__file__).resolve()
BACKEND_DIR = CURRENT_FILE.parent
PROJECT_ROOT = BACKEND_DIR.parent

if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

ML_MODELS_DIR = PROJECT_ROOT / "ML_models"

# 2. Imports
from fastapi import FastAPI, UploadFile, File, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
import gradio as gr
import tempfile
import os
import json
from datetime import datetime
from pathlib import Path

# ML model app builders
from ML_models.yolo_nav.live_gradio import build_yolo_app
from ML_models.live_ocr.live_ocr_tts import build_ocr_app

# ML Adapters (for clean JSON output)
from ML_models.adapters.yolo_adapter import vision_adapter
from ML_models.adapters.ocr_adapter import ocr_adapter

# Direct model imports for raw output endpoints
from ultralytics import YOLO
import easyocr
import cv2
import numpy as np

# 3. Create FastAPI app
app = FastAPI(title="AI Assist Backend")


# 4. CORS (required for mobile/web)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],        # Allow all while developing
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# 5. Root endpoint - API information
@app.get("/")
def root():
    return {
        "message": "WalkBuddy AI Assist Backend API",
        "version": "1.0.0",
        "status": "running",
        "endpoints": {
            "health": "/health",
            "status": "/status",
            "switch_mode": "/switch/{mode}",
            "stop": "/stop",
            "vision_raw": "POST /vision_raw (raw YOLO output - BEFORE adapter)",
            "ocr_raw": "POST /ocr_raw (raw EasyOCR output - BEFORE adapter)",
            "vision_api": "POST /vision (clean JSON - AFTER adapter)",
            "ocr_api": "POST /ocr (clean JSON - AFTER adapter)",
            "vision_ui": "/vision/ (Gradio UI)",
            "ocr_ui": "/ocr/ (Gradio UI)"
        },
        "docs": "/docs"
    }


# 5.1. Health check endpoint
@app.get("/health")
def health():
    return {"ok": True}


# 5.1. Status endpoint
@app.get("/status")
def status():
    return {
        "status": "running",
        "mode": "gradio",  # Default mode
        "available_modes": ["gradio", "ocr"]
    }


# 5.2. Switch mode endpoint (for compatibility with frontend)
@app.get("/switch/{mode}")
def switch_mode(mode: str):
    if mode not in ["gradio", "ocr"]:
        return {"error": f"Invalid mode: {mode}"}, 400
    # Map "gradio" to "vision" endpoint
    url = "/vision/" if mode == "gradio" else "/ocr/"
    return {
        "status": "switched",
        "mode": mode,
        "url": url
    }


# 5.3. Stop endpoint (for compatibility with frontend)
@app.get("/stop")
def stop():
    return {
        "status": "stopped",
        "message": "Model stopped"
    }


# ============================================================================
# RAW MODEL OUTPUT ENDPOINTS (BEFORE ADAPTER)
# These endpoints return the original messy ML model output for comparison
# ============================================================================

# Global model instances (loaded once for efficiency)
_yolo_model_raw = None
_ocr_reader_raw = None


def _get_yolo_model_raw():
    """Load YOLO model for raw output endpoint."""
    global _yolo_model_raw
    if _yolo_model_raw is None:
        yolo_weights = PROJECT_ROOT / "ML_models" / "yolo_nav" / "weights" / "yolov8s.pt"
        if not yolo_weights.exists():
            raise FileNotFoundError(f"YOLO weights not found: {yolo_weights}")
        _yolo_model_raw = YOLO(str(yolo_weights))
    return _yolo_model_raw


def _get_ocr_reader_raw():
    """Load EasyOCR reader for raw output endpoint."""
    global _ocr_reader_raw
    if _ocr_reader_raw is None:
        try:
            import torch
            gpu_available = torch.cuda.is_available()
        except:
            gpu_available = False
        _ocr_reader_raw = easyocr.Reader(['en'], gpu=gpu_available)
    return _ocr_reader_raw


# 5.4. Vision RAW endpoint - Returns original YOLO output WITHOUT adapter
@app.post("/vision_raw")
async def vision_raw_endpoint(file: UploadFile = File(...)):
    """
    RAW Vision detection endpoint - Returns original YOLO model output.
    
    ⚠️ This endpoint returns the RAW, unprocessed YOLO output for comparison.
    This is the messy original format BEFORE the adapter cleans it up.
    
    - **file**: Image file (jpg, png, etc.)
    
    Returns raw YOLO output with:
    - Raw bounding box coordinates (floats, not integers)
    - Class IDs mixed with class names
    - Extra metadata and internal model data
    - Inconsistent format
    
    Compare this with POST /vision to see the adapter improvement!
    """
    # Validate file type
    if not file.content_type or not file.content_type.startswith('image/'):
        raise HTTPException(status_code=400, detail="File must be an image")
    
    temp_file = None
    try:
        # Save uploaded image to temporary file
        file_ext = os.path.splitext(file.filename)[1] if file.filename else '.jpg'
        with tempfile.NamedTemporaryFile(delete=False, suffix=file_ext) as temp_file:
            content = await file.read()
            temp_file.write(content)
            temp_path = temp_file.name
        
        # Load YOLO model directly (NOT using adapter)
        model = _get_yolo_model_raw()
        
        # Run inference directly - get raw YOLO results
        results = model.predict(
            source=temp_path,
            conf=0.25,
            iou=0.45,
            verbose=False
        )
        result = results[0]
        
        # Extract raw YOLO output data (this is the messy original format)
        raw_output = {
            "image_id": Path(temp_path).stem,
            "image_path": temp_path,
            "model_type": "YOLOv8",
            "raw_detections": [],
            "model_metadata": {
                "num_classes": len(result.names) if hasattr(result, 'names') else 0,
                "image_shape": list(result.orig_shape) if hasattr(result, 'orig_shape') else None,
                "model_names": result.names if hasattr(result, 'names') else {}
            }
        }
        
        # Extract raw detection data (exactly as YOLO provides it)
        if result.boxes is not None and len(result.boxes) > 0:
            boxes = result.boxes.xyxy.cpu().numpy().tolist()  # Raw float coordinates
            confidences = result.boxes.conf.cpu().numpy().tolist()
            class_ids = result.boxes.cls.cpu().int().tolist()
            
            for i, (box, conf, cls_id) in enumerate(zip(boxes, confidences, class_ids)):
                raw_output["raw_detections"].append({
                    "detection_id": i,
                    "bbox_raw": box,  # [x1, y1, x2, y2] as floats - NOT standardized
                    "confidence": float(conf),  # Raw float, not rounded
                    "class_id": int(cls_id),  # Numeric class ID
                    "class_name": result.names[int(cls_id)] if hasattr(result, 'names') else f"class_{int(cls_id)}"
                })
        
        raw_output["num_detections"] = len(raw_output["raw_detections"])
        
        # Save raw output to file with timestamp
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        raw_outputs_dir = PROJECT_ROOT / "ML_models" / "adapters" / "raw_outputs"
        raw_outputs_dir.mkdir(parents=True, exist_ok=True)
        output_file = raw_outputs_dir / f"{timestamp}_yolo_raw.json"
        
        with open(output_file, 'w') as f:
            json.dump(raw_output, f, indent=2)
        
        return JSONResponse(content=raw_output)
    
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error processing image: {str(e)}")
    
    finally:
        # Clean up temporary file
        if temp_file and os.path.exists(temp_path):
            try:
                os.unlink(temp_path)
            except:
                pass


# 5.5. OCR RAW endpoint - Returns original EasyOCR output WITHOUT adapter
@app.post("/ocr_raw")
async def ocr_raw_endpoint(file: UploadFile = File(...)):
    """
    RAW OCR text detection endpoint - Returns original EasyOCR output.
    
    ⚠️ This endpoint returns the RAW, unprocessed EasyOCR output for comparison.
    This is the messy original format BEFORE the adapter cleans it up.
    
    - **file**: Image file (jpg, png, etc.)
    
    Returns raw EasyOCR output with:
    - 4-corner bounding box format (not standard x_min/y_min/x_max/y_max)
    - Raw text with extra whitespace
    - Inconsistent structure
    - Extra metadata
    
    Compare this with POST /ocr to see the adapter improvement!
    """
    # Validate file type
    if not file.content_type or not file.content_type.startswith('image/'):
        raise HTTPException(status_code=400, detail="File must be an image")
    
    temp_file = None
    try:
        # Save uploaded image to temporary file
        file_ext = os.path.splitext(file.filename)[1] if file.filename else '.jpg'
        with tempfile.NamedTemporaryFile(delete=False, suffix=file_ext) as temp_file:
            content = await file.read()
            temp_file.write(content)
            temp_path = temp_file.name
        
        # Load EasyOCR reader directly (NOT using adapter)
        reader = _get_ocr_reader_raw()
        
        # Run OCR inference directly - get raw EasyOCR results
        # EasyOCR format: [(bbox_points, text, confidence), ...]
        raw_results = reader.readtext(temp_path)
        
        # Extract raw EasyOCR output data (this is the messy original format)
        raw_output = {
            "image_id": Path(temp_path).stem,
            "image_path": temp_path,
            "model_type": "EasyOCR",
            "raw_detections": []
        }
        
        # Process raw EasyOCR results (exactly as EasyOCR provides them)
        for i, detection in enumerate(raw_results):
            # EasyOCR format: (bbox_points, text, confidence)
            if isinstance(detection, (list, tuple)) and len(detection) >= 3:
                bbox_corners = detection[0]  # 4 corner points [[x1,y1], [x2,y2], [x3,y3], [x4,y4]]
                text = str(detection[1])  # Raw text (may have extra whitespace)
                confidence = float(detection[2])  # Raw float confidence
            else:
                continue
            
            raw_output["raw_detections"].append({
                "detection_id": i,
                "text": text,  # Raw text - NOT cleaned
                "confidence": confidence,  # Raw float - NOT rounded
                "bbox_corners": [[float(p[0]), float(p[1])] for p in bbox_corners],  # 4 corners - NOT standardized
                "bbox_format": "4_corners"  # Different format than standard bbox
            })
        
        raw_output["num_detections"] = len(raw_output["raw_detections"])
        
        # Save raw output to file with timestamp
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        raw_outputs_dir = PROJECT_ROOT / "ML_models" / "adapters" / "raw_outputs"
        raw_outputs_dir.mkdir(parents=True, exist_ok=True)
        output_file = raw_outputs_dir / f"{timestamp}_ocr_raw.json"
        
        with open(output_file, 'w') as f:
            json.dump(raw_output, f, indent=2)
        
        return JSONResponse(content=raw_output)
    
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error processing image: {str(e)}")
    
    finally:
        # Clean up temporary file
        if temp_file and os.path.exists(temp_path):
            try:
                os.unlink(temp_path)
            except:
                pass


# ============================================================================
# CLEAN ADAPTER ENDPOINTS (AFTER ADAPTER)
# These endpoints return cleaned, standardized JSON from the adapters
# ============================================================================

# 5.6. Vision endpoint using adapter (POST with file upload)
# This is the cleaned JSON after passing through the adapter
@app.post("/vision")
async def vision_endpoint(file: UploadFile = File(...)):
    """
    Vision detection endpoint using YOLO adapter.
    
    ✅ This endpoint returns CLEAN, standardized JSON from the adapter.
    Compare with POST /vision_raw to see the improvement!
    
    Accepts an image file upload and returns standardized JSON with detections.
    
    - **file**: Image file (jpg, png, etc.)
    
    Returns clean JSON in the format:
    {
        "image_id": "filename",
        "detections": [
            {
                "category": "chair",
                "confidence": 0.8542,
                "bbox": {"x_min": 100, "y_min": 150, "x_max": 250, "y_max": 300}
            }
        ]
    }
    """
    # Validate file type
    if not file.content_type or not file.content_type.startswith('image/'):
        raise HTTPException(status_code=400, detail="File must be an image")
    
    # Create temporary file to save uploaded image
    temp_file = None
    try:
        # Create temporary file with proper extension
        file_ext = os.path.splitext(file.filename)[1] if file.filename else '.jpg'
        with tempfile.NamedTemporaryFile(delete=False, suffix=file_ext) as temp_file:
            # Read uploaded file content
            content = await file.read()
            temp_file.write(content)
            temp_path = temp_file.name
        
        # Call the vision adapter - this returns CLEAN standardized JSON
        result = vision_adapter(temp_path)
        
        return JSONResponse(content=result)
    
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error processing image: {str(e)}")
    
    finally:
        # Clean up temporary file
        if temp_file and os.path.exists(temp_path):
            try:
                os.unlink(temp_path)
            except:
                pass


# 5.7. OCR endpoint using adapter (POST with file upload)
# ✅ This is the cleaned JSON after passing through the adapter
@app.post("/ocr")
async def ocr_endpoint(file: UploadFile = File(...)):
    """
    OCR text detection endpoint using EasyOCR adapter.
    
    ✅ This endpoint returns CLEAN, standardized JSON from the adapter.
    Compare with POST /ocr_raw to see the improvement!
    
    Accepts an image file upload and returns standardized JSON with text detections.
    
    - **file**: Image file (jpg, png, etc.)
    
    Returns clean JSON in the format:
    {
        "image_id": "filename",
        "detections": [
            {
                "category": "EXIT",
                "confidence": 0.9955,
                "bbox": {"x_min": 49, "y_min": 51, "x_max": 75, "y_max": 63}
            }
        ]
    }
    """
    # Validate file type
    if not file.content_type or not file.content_type.startswith('image/'):
        raise HTTPException(status_code=400, detail="File must be an image")
    
    # Create temporary file to save uploaded image
    temp_file = None
    try:
        # Create temporary file with proper extension
        file_ext = os.path.splitext(file.filename)[1] if file.filename else '.jpg'
        with tempfile.NamedTemporaryFile(delete=False, suffix=file_ext) as temp_file:
            # Read uploaded file content
            content = await file.read()
            temp_file.write(content)
            temp_path = temp_file.name
        
        # Call the OCR adapter - this returns CLEAN standardized JSON
        result = ocr_adapter(temp_path)
        
        return JSONResponse(content=result)
    
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error processing image: {str(e)}")
    
    finally:
        # Clean up temporary file
        if temp_file and os.path.exists(temp_path):
            try:
                os.unlink(temp_path)
            except:
                pass


# 6. Mount YOLO Vision at /vision
yolo_blocks = build_yolo_app()
app = gr.mount_gradio_app(app, yolo_blocks, path="/vision")


# 7. Mount OCR at /ocr
ocr_blocks = build_ocr_app()
app = gr.mount_gradio_app(app, ocr_blocks, path="/ocr")


# 8. Allow `python main.py` to run the server
if __name__ == "__main__":
    import uvicorn

    uvicorn.run(
        "main:app",
        host="0.0.0.0",
        port=8000,
        reload=True,
    )
