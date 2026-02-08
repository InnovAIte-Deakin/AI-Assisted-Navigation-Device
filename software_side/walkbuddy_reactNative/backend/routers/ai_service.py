import sys
import os
import logging
from pathlib import Path
from fastapi import APIRouter, UploadFile, File, HTTPException
import tempfile

# 1. SETUP PATHS
PROJECT_ROOT = Path(__file__).resolve().parents[4] 

# 2. IMPORTS
# Core Adapters (vision, ocr, tts)
from adapters import vision_adapter, ocr_adapter
from tts_service.message_reasoning import process_adapter_output

# Slow Lane Modules (The "Smart" logic)
from slow_lane import safe_or_stop_recommendation

# State 
from internal.state import memory,llm_brain 

# Logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

router = APIRouter()

# --- VISION ENDPOINT (Perception + Memory) ---
@router.post("/vision", tags=['AI inference'])
async def vision_endpoint(file: UploadFile = File(...)):
    if not file.content_type.startswith('image/'):
        raise HTTPException(400, "File must be an image")
    
    # CRITICAL FIX: Check for empty files
    content = await file.read()
    if len(content) == 0:
         logger.warning("Received empty image file.")
         return {"detections": [], "guidance_message": ""}

    temp_file = None
    try:
        suffix = os.path.splitext(file.filename)[1] or '.jpg'
        with tempfile.NamedTemporaryFile(delete=False, suffix=suffix) as f:
            f.write(content)
            temp_path = f.name
        
        # 1. PERCEIVE (YOLO)
        result = vision_adapter(temp_path)
        
        # 2. REMEMBER (Update Memory)
        detections = result.get("detections", [])
        for d in detections:
            memory.add_event(
                label=d["category"],
                direction="ahead", # Adapter doesn't currently calculate X-pos, defaulting
                distance_m=None,
                confidence=d["confidence"]
            )

        # 3. REASON (Generate Guidance for TTS)
        msgs = process_adapter_output(result, max_messages=1)
        
        guidance = "Path clear"
        if msgs:
            guidance = msgs[0].message
        elif detections:
             guidance = f"{len(detections)} objects detected"

        return {
            "detections": detections,
            "guidance_message": guidance,
            "image_id": result.get("image_id", "")
        }
    
    except Exception as e:
        logger.error(f"Vision error: {e}")
        raise HTTPException(500, f"Processing failed: {e}")
    finally:
        if temp_file and os.path.exists(temp_path):
            os.unlink(temp_path)

# --- OCR ENDPOINT ---
@router.post("/ocr", tags=['AI inference'])
async def ocr_endpoint(file: UploadFile = File(...)):
    if not file.content_type.startswith('image/'):
        raise HTTPException(400, "File must be an image")

    # CRITICAL FIX: Check for empty files
    content = await file.read()
    if len(content) == 0:
         logger.warning("Received empty image file.")
         return {"detections": [], "guidance_message": "Image error"}
        
    temp_file = None
    try:
        suffix = os.path.splitext(file.filename)[1] or '.jpg'
        with tempfile.NamedTemporaryFile(delete=False, suffix=suffix) as f:
            f.write(content)
            temp_path = f.name
            
        result = ocr_adapter(temp_path)
        
        texts = [d["category"] for d in result.get("detections", [])]
        guidance = " ".join(texts) if texts else "No text detected."
        
        return {
            "detections": result.get("detections", []),
            "guidance_message": guidance
        }
    except Exception as e:
        logger.error(f"OCR Error: {e}")
        # Return empty safe response instead of 500 crash
        return {"detections": [], "guidance_message": "Text scan failed"}
    finally:
        if temp_file and os.path.exists(temp_path):
            os.unlink(temp_path)

# --- CHAT ENDPOINT (The "Brain") ---
@router.post("/chat", tags=['AI inference'])
async def chat_endpoint(query: dict):
    user_q = query.get("query", "").strip()
    if not user_q:
        return {"response": "I didn't hear a question."}

    # 1. Access the Single Source of Truth (Memory)
    recent_events = list(memory.buffer)

    # 2. Safety Gate (Uses raw dicts)
    hazard_msg = safe_or_stop_recommendation(recent_events[-10:])
    if hazard_msg:
         return {"response": hazard_msg}

    # 3. LLM Reasoning
    if not llm_brain:
        return {"response": "My reasoning brain is offline."}

    try:
        # Pass the raw events list directly
        final_text = llm_brain.ask(recent_events, user_q)
        return {"response": final_text}
    except Exception as e:
        logger.error(f"LLM error: {e}")
        return {"response": "I'm having trouble thinking right now."}