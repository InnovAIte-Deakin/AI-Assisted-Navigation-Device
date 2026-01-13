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
try:
    import gradio as gr
    GRADIO_AVAILABLE = True
except Exception as e:
    gr = None
    GRADIO_AVAILABLE = False
    print(f"[WARN] Gradio disabled: {e}")

import tempfile
import os
import json
from datetime import datetime
from pathlib import Path
import time
import logging

# STT imports
try:
    from faster_whisper import WhisperModel
    WHISPER_AVAILABLE = True
except ImportError:
    WHISPER_AVAILABLE = False

try:
    from pydub import AudioSegment
    PYDUB_AVAILABLE = True
except ImportError:
    PYDUB_AVAILABLE = False

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# ML model app builders (optional - only if Gradio is available)
yolo_blocks = None
ocr_blocks = None
build_yolo_app = None
build_ocr_app = None
if GRADIO_AVAILABLE:
    try:
        from ML_models.yolo_nav.live_gradio import build_yolo_app
        from ML_models.live_ocr.live_ocr_tts import build_ocr_app
    except Exception as e:
        print(f"[WARN] Failed to import Gradio app builders: {e}")
        GRADIO_AVAILABLE = False
        build_yolo_app = None
        build_ocr_app = None

# ML Adapters (for clean JSON output)
from ML_models.adapters.yolo_adapter import vision_adapter
from ML_models.adapters.ocr_adapter import ocr_adapter

# TTS Service and Message Reasoning
from ML_models.tts_service.tts_service import TTSService, RiskLevel, get_tts_service
from ML_models.tts_service.message_reasoning import (
    process_adapter_output,
    generate_clear_path_message
)

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
            "tts_speak": "POST /tts/speak (speak a text message)",
            "tts_status": "GET /tts/status (get TTS service status)",
            "vision_tts": "POST /vision/tts (vision detection + TTS)",
            "ocr_tts": "POST /ocr/tts (OCR detection + TTS)",
            "stt_transcribe": "POST /stt/transcribe (transcribe audio to text)",
            "query": "POST /query (process text query and return guidance)",
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


# ============================================================================
# TTS ENDPOINTS
# ============================================================================

# Global TTS service instance
_tts_service = None

def _get_tts_service():
    """Get or create global TTS service instance."""
    global _tts_service
    if _tts_service is None:
        _tts_service = get_tts_service(
            cooldown_seconds=3.0,
            use_offline=True,
            use_cloud_fallback=False
        )
    return _tts_service


# Global Whisper model instance
_whisper_model = None

def _get_whisper_model():
    """Get or create global Whisper model instance."""
    global _whisper_model
    if _whisper_model is None:
        if not WHISPER_AVAILABLE:
            raise RuntimeError("faster-whisper is not installed. Run: pip install faster-whisper")
        # Use base model for faster inference (can be changed to "small", "medium", "large" for better accuracy)
        _whisper_model = WhisperModel("base", device="cpu", compute_type="int8")
        logger.info("Whisper model loaded successfully")
    return _whisper_model


def _convert_audio_to_wav(input_path: str, output_path: str) -> bool:
    """Convert audio file to WAV format using pydub."""
    if not PYDUB_AVAILABLE:
        logger.warning("pydub not available, attempting direct processing")
        return False
    
    try:
        audio = AudioSegment.from_file(input_path)
        audio.export(output_path, format="wav")
        logger.info(f"Converted {input_path} to {output_path}")
        return True
    except Exception as e:
        logger.error(f"Audio conversion failed: {str(e)}")
        return False


# 5.8. TTS endpoint - Speak a message
@app.post("/tts/speak")
async def tts_speak_endpoint(message: dict):
    """
    TTS Speak endpoint - Converts text to speech with anti-spam logic.
    
    Request body:
    {
        "message": "Chair on your left, nearby",
        "risk_level": "MEDIUM",  # Optional: CLEAR, LOW, MEDIUM, HIGH, CRITICAL
        "force": false  # Optional: Force speaking even if cooldown active
    }
    
    Returns:
    {
        "success": true,
        "message": "Message spoken",
        "status": {...}  # TTS service status
    }
    """
    try:
        text = message.get("message", "")
        if not text:
            raise HTTPException(status_code=400, detail="Message is required")
        
        risk_level_str = message.get("risk_level", "LOW").upper()
        try:
            risk_level = RiskLevel[risk_level_str]
        except KeyError:
            risk_level = RiskLevel.LOW
        
        force = message.get("force", False)
        
        tts_service = _get_tts_service()
        success = tts_service.speak(text, risk_level, force)
        
        return {
            "success": success,
            "message": "Message spoken" if success else "Message suppressed by anti-spam logic",
            "status": tts_service.get_status()
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error speaking message: {str(e)}")


# 5.9. Vision + TTS endpoint - Process image and speak guidance
@app.post("/vision/tts")
async def vision_tts_endpoint(file: UploadFile = File(...)):
    """
    Vision + TTS endpoint - Processes image and speaks guidance messages.
    
    This endpoint:
    1. Runs vision detection on the image
    2. Converts detections to guidance messages
    3. Speaks the highest priority message
    
    - **file**: Image file (jpg, png, etc.)
    
    Returns:
    {
        "detections": [...],  # Standardized detections
        "guidance_messages": [...],  # Generated guidance messages
        "spoken": true,  # Whether a message was spoken
        "spoken_message": "Chair on your left, nearby"  # The message that was spoken
    }
    """
    # Validate file type
    if not file.content_type or not file.content_type.startswith('image/'):
        raise HTTPException(status_code=400, detail="File must be an image")
    
    temp_file = None
    try:
        # Save uploaded image
        file_ext = os.path.splitext(file.filename)[1] if file.filename else '.jpg'
        with tempfile.NamedTemporaryFile(delete=False, suffix=file_ext) as temp_file:
            content = await file.read()
            temp_file.write(content)
            temp_path = temp_file.name
        
        # Run vision adapter
        vision_result = vision_adapter(temp_path)
        
        # Get image dimensions from metadata if available
        image_width = 640
        image_height = 480
        if "metadata" in vision_result and "image_shape" in vision_result["metadata"]:
            shape = vision_result["metadata"]["image_shape"]
            if len(shape) >= 2:
                image_height, image_width = shape[0], shape[1]
        
        # Generate guidance messages
        guidance_messages = process_adapter_output(
            vision_result,
            image_width=image_width,
            image_height=image_height,
            max_messages=1
        )
        
        # If no detections, generate clear path message
        if not guidance_messages:
            guidance_messages = [generate_clear_path_message()]
        
        # Speak the highest priority message
        spoken = False
        spoken_message = None
        if guidance_messages:
            top_message = guidance_messages[0]
            tts_service = _get_tts_service()
            spoken = tts_service.speak_async(
                top_message.message,
                top_message.risk_level,
                force=False
            )
            spoken_message = top_message.message
        
        return {
            "detections": vision_result.get("detections", []),
            "guidance_messages": [
                {
                    "message": msg.message,
                    "risk_level": msg.risk_level.name,
                    "priority": msg.priority
                }
                for msg in guidance_messages
            ],
            "spoken": spoken,
            "spoken_message": spoken_message
        }
    
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error processing image: {str(e)}")
    
    finally:
        # Clean up temporary file
        if temp_file and os.path.exists(temp_path):
            try:
                os.unlink(temp_path)
            except:
                pass


# 5.10. OCR + TTS endpoint - Process image and speak detected text
@app.post("/ocr/tts")
async def ocr_tts_endpoint(file: UploadFile = File(...)):
    """
    OCR + TTS endpoint - Processes image and speaks detected text.
    
    This endpoint:
    1. Runs OCR on the image
    2. Converts text detections to guidance messages
    3. Speaks the highest priority message
    
    - **file**: Image file (jpg, png, etc.)
    
    Returns:
    {
        "detections": [...],  # Standardized text detections
        "guidance_messages": [...],  # Generated guidance messages
        "spoken": true,  # Whether a message was spoken
        "spoken_message": "Exit sign detected ahead"  # The message that was spoken
    }
    """
    # Validate file type
    if not file.content_type or not file.content_type.startswith('image/'):
        raise HTTPException(status_code=400, detail="File must be an image")
    
    temp_file = None
    try:
        # Save uploaded image
        file_ext = os.path.splitext(file.filename)[1] if file.filename else '.jpg'
        with tempfile.NamedTemporaryFile(delete=False, suffix=file_ext) as temp_file:
            content = await file.read()
            temp_file.write(content)
            temp_path = temp_file.name
        
        # Run OCR adapter
        ocr_result = ocr_adapter(temp_path)
        
        # Get image dimensions (default if not available)
        image_width = 640
        image_height = 480
        
        # Generate guidance messages
        guidance_messages = process_adapter_output(
            ocr_result,
            image_width=image_width,
            image_height=image_height,
            max_messages=1
        )
        
        # Speak the highest priority message
        spoken = False
        spoken_message = None
        if guidance_messages:
            top_message = guidance_messages[0]
            tts_service = _get_tts_service()
            spoken = tts_service.speak_async(
                top_message.message,
                top_message.risk_level,
                force=False
            )
            spoken_message = top_message.message
        
        return {
            "detections": ocr_result.get("detections", []),
            "guidance_messages": [
                {
                    "message": msg.message,
                    "risk_level": msg.risk_level.name,
                    "priority": msg.priority
                }
                for msg in guidance_messages
            ],
            "spoken": spoken,
            "spoken_message": spoken_message
        }
    
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error processing image: {str(e)}")
    
    finally:
        # Clean up temporary file
        if temp_file and os.path.exists(temp_path):
            try:
                os.unlink(temp_path)
            except:
                pass


# 5.11. STT transcription endpoint
@app.post("/stt/transcribe")
async def stt_transcribe_endpoint(file: UploadFile = File(...)):
    """
    Speech-to-Text transcription endpoint using Whisper.
    
    Accepts an audio file and returns transcribed text.
    
    - **file**: Audio file (m4a, wav, mp3, etc.)
    
    Returns:
    {
        "text": "transcribed text here",
        "error": "..."  # Only present if transcription failed
    }
    """
    start_time = time.time()
    filename = file.filename or "unknown"
    content_type = file.content_type or "unknown"
    
    logger.info(f"[STT] Received audio file: {filename}, content-type: {content_type}")
    
    # Validate file type
    if not file.content_type or not file.content_type.startswith('audio/'):
        logger.warning(f"[STT] Invalid content type: {content_type}")
        return {
            "text": "",
            "error": "File must be an audio file"
        }
    
    temp_file = None
    temp_path = None
    converted_path = None
    
    try:
        # Check if Whisper is available
        if not WHISPER_AVAILABLE:
            error_msg = "Whisper transcription not available. Install with: pip install faster-whisper"
            logger.error(f"[STT] {error_msg}")
            return {
                "text": "",
                "error": error_msg
            }
        
        # Save uploaded audio
        file_ext = os.path.splitext(filename)[1] if filename else '.m4a'
        with tempfile.NamedTemporaryFile(delete=False, suffix=file_ext) as temp_file:
            content = await file.read()
            temp_file.write(content)
            temp_path = temp_file.name
        
        logger.info(f"[STT] Saved audio to: {temp_path}")
        
        # Convert .m4a and other formats to WAV if needed (Whisper works better with WAV)
        audio_path = temp_path
        needs_conversion = file_ext.lower() in ['.m4a', '.mp3', '.aac', '.ogg']
        
        if needs_conversion and PYDUB_AVAILABLE:
            converted_path = temp_path + ".wav"
            if _convert_audio_to_wav(temp_path, converted_path):
                audio_path = converted_path
                logger.info(f"[STT] Using converted WAV file: {converted_path}")
            else:
                logger.warning(f"[STT] Conversion failed, using original file: {temp_path}")
        
        # Load Whisper model and transcribe
        model = _get_whisper_model()
        transcription_start = time.time()
        
        # Transcribe audio
        segments, info = model.transcribe(
            audio_path,
            beam_size=5,
            language="en",  # Can be None for auto-detection
            task="transcribe"
        )
        
        # Collect transcribed text
        transcribed_text = ""
        for segment in segments:
            transcribed_text += segment.text + " "
        
        transcribed_text = transcribed_text.strip()
        transcription_duration = time.time() - transcription_start
        total_duration = time.time() - start_time
        
        logger.info(f"[STT] Transcription completed in {transcription_duration:.2f}s (total: {total_duration:.2f}s)")
        logger.info(f"[STT] Transcribed text: {transcribed_text[:100]}...")  # Log first 100 chars
        
        if not transcribed_text:
            logger.warning("[STT] Empty transcription result")
            return {
                "text": "",
                "error": "No speech detected in audio"
            }
        
        return {
            "text": transcribed_text
        }
    
    except Exception as e:
        error_msg = f"Error processing audio: {str(e)}"
        logger.error(f"[STT] {error_msg}", exc_info=True)
        return {
            "text": "",
            "error": error_msg
        }
    
    finally:
        # Clean up temporary files
        for path in [temp_path, converted_path]:
            if path and os.path.exists(path):
                try:
                    os.unlink(path)
                    logger.debug(f"[STT] Cleaned up temp file: {path}")
                except Exception as e:
                    logger.warning(f"[STT] Failed to delete temp file {path}: {str(e)}")


# 5.12. Query endpoint - Process text query and return guidance
@app.post("/query")
async def query_endpoint(query: dict):
    """
    Process a text query and return navigation guidance.
    
    Request body:
    {
        "query": "Where is the exit?"
    }
    
    Returns:
    {
        "response": "Exit sign detected ahead",
        "guidance": "Turn left and proceed 10 feet",
        "tts_message": "Exit sign detected ahead. Turn left and proceed 10 feet"
    }
    
    Note: This is a simple rule-based implementation. For production,
    integrate with LLM or more sophisticated reasoning system.
    """
    try:
        text_query = query.get("query", "").strip().lower()
        
        if not text_query:
            raise HTTPException(status_code=400, detail="Query is required")
        
        # Simple rule-based responses (replace with LLM in production)
        response_text = ""
        guidance = ""
        
        # Directional commands
        if "left" in text_query:
            response_text = "Turning left"
            guidance = "Proceed left, watch for obstacles"
        elif "right" in text_query:
            response_text = "Turning right"
            guidance = "Proceed right, watch for obstacles"
        elif "forward" in text_query or "straight" in text_query or "ahead" in text_query:
            response_text = "Proceeding forward"
            guidance = "Path ahead, continue straight"
        elif "stop" in text_query or "halt" in text_query:
            response_text = "Stopping"
            guidance = "Please stop and wait for further instructions"
        elif "repeat" in text_query or "say again" in text_query:
            response_text = "Repeating last message"
            guidance = "Please check the last spoken guidance"
        # Scan commands
        elif "scan" in text_query and ("again" in text_query or "now" in text_query):
            response_text = "Scanning now"
            guidance = "Processing your surroundings"
        # Vision queries - what's in front
        elif "what" in text_query and ("front" in text_query or "see" in text_query or "ahead" in text_query):
            response_text = "No recent scan available"
            guidance = "Please enable auto-scan or take a photo to see what's ahead"
        # Exit queries
        elif "exit" in text_query or "way out" in text_query or "leave" in text_query:
            response_text = "Exit sign detected ahead"
            guidance = "Proceed straight ahead, approximately 20 feet"
        # Restroom queries
        elif "restroom" in text_query or "bathroom" in text_query or "toilet" in text_query:
            response_text = "Restroom located on your right"
            guidance = "Turn right and proceed 15 feet"
        # Help queries
        elif "help" in text_query or "assistance" in text_query:
            response_text = "I'm here to help with navigation"
            guidance = "Ask me about exits, restrooms, or directions"
        # Path status
        elif "clear" in text_query or "path" in text_query:
            response_text = "Path ahead is clear"
            guidance = "No obstacles detected, safe to proceed"
        else:
            response_text = "I understand your request"
            guidance = "Processing your navigation query"
        
        tts_message = f"{response_text}. {guidance}"
        
        return {
            "response": response_text,
            "guidance": guidance,
            "tts_message": tts_message
        }
    
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error processing query: {str(e)}")


# 5.13. TTS status endpoint
@app.get("/tts/status")
async def tts_status_endpoint():
    """
    Get TTS service status.
    
    Returns current status including:
    - Cooldown information
    - Last spoken message
    - Service availability
    """
    try:
        tts_service = _get_tts_service()
        return tts_service.get_status()
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error getting TTS status: {str(e)}")


# Mount YOLO Vision and OCR at /vision and /ocr (optional)
if GRADIO_AVAILABLE and build_yolo_app is not None and build_ocr_app is not None:
    try:
        yolo_blocks = build_yolo_app()
        ocr_blocks = build_ocr_app()
        app = gr.mount_gradio_app(app, yolo_blocks, path="/vision")
        app = gr.mount_gradio_app(app, ocr_blocks, path="/ocr")
        print("[INFO] Gradio UI mounted at /vision and /ocr")
    except Exception as e:
        print(f"[WARN] Failed to mount Gradio UI: {e}")
        print("[INFO] FastAPI endpoints will continue to work without Gradio UI")
else:
    print("[INFO] Gradio UI not available - /vision and /ocr UI endpoints skipped")


# 8. Allow `python main.py` to run the server
if __name__ == "__main__":
    import uvicorn

    uvicorn.run(
        "main:app",
        host="0.0.0.0",
        port=8000,
        reload=True,
    )
