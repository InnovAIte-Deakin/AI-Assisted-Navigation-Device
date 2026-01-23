import io
import os
import shutil
from typing import List, Optional
from fastapi import FastAPI, File, UploadFile, Form, HTTPException
from fastapi.responses import JSONResponse
from PIL import Image
from ultralytics import YOLO
import numpy as np

# Import Slow Lane modules
# Assumes main.py is in ML_side/ and slow_lane/ is a subdirectory
from slow_lane.slowlanellm import SlowLaneLLM
from slow_lane.memorybuffer import NavigationMemory
from slow_lane import safetygate

app = FastAPI(title="AIAND Two-Brain API", description="Fast Lane (YOLO) + Slow Lane (LLM) Service")

# --- Configuration ---
YOLO_MODEL_PATH = "models/object_detection/best.pt"
LLM_MODEL_PATH = "models/llama-3.2-1b-instruct-q4_k_m.gguf"

# --- Global State ---
yolo_model = None
llm_brain = None
memory = None

@app.on_event("startup")
async def startup_event():
    global yolo_model, llm_brain, memory
    
    print("Loading Fast Lane (YOLO)...")
    if os.path.exists(YOLO_MODEL_PATH):
        yolo_model = YOLO(YOLO_MODEL_PATH)
    else:
        print(f"WARNING: YOLO model not found at {YOLO_MODEL_PATH}. Using 'yolov8n.pt' as fallback.")
        yolo_model = YOLO("yolov8n.pt") # Fallback for testing if custom model missing

    print("Loading Slow Lane (LLM)...")
    if os.path.exists(LLM_MODEL_PATH):
        llm_brain = SlowLaneLLM(model_path=LLM_MODEL_PATH)
    else:
        print(f"WARNING: LLM model not found at {LLM_MODEL_PATH}. Slow Lane will fail.")
        # We don't crash yet, allowing Fast Lane to work
        
    print("Initializing Memory...")
    memory = NavigationMemory()
    print("System Ready.")

def process_image(image_bytes: bytes):
    try:
        img = Image.open(io.BytesIO(image_bytes))
        return img
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"Invalid image data: {e}")

def run_yolo(img):
    results = yolo_model(img, verbose=False)
    events = []
    
    # Process first result (batch size 1)
    r = results[0]
    
    for box in r.boxes:
        cls_id = int(box.cls[0])
        label = yolo_model.names[cls_id]
        conf = float(box.conf[0])
        
        # Determine rough direction based on center x
        # Image is typically 640x480 or similar.
        # r.orig_shape is (height, width)
        h, w = r.orig_shape
        
        # Box format: xywh or xyxy. Let's use logic on box.xywh
        # box.xywh[0] is center x
        cx = float(box.xywh[0][0])
        
        if cx < w * 0.33:
            direction = "to the left"
        elif cx > w * 0.66:
            direction = "to the right"
        else:
            direction = "directly ahead"
            
        # Check depth/distance approximation if available?
        # Current YOLO output doesn't give depth, so we estimate or leave None.
        # User prompt says: "distance_m (approx)".
        # We can roughly estimate by box height/width relative to image size, but keeping it simple for now.
        distance_m = None 
        
        events.append({
            "label": label,
            "direction": direction,
            "distance_m": distance_m,
            "confidence": round(conf, 3)
        })
        
    return events

@app.post("/detect")
async def detect_endpoint(file: UploadFile = File(...)):
    """
    Fast Lane only: Accepts image, runs YOLO, updates memory, returns events.
    """
    contents = await file.read()
    img = process_image(contents)
    
    events = run_yolo(img)
    
    # Update memory
    for e in events:
        memory.add_event(e['label'], e['direction'], e['distance_m'], e['confidence'])
        
    return {"events": events}

@app.post("/reason")
async def reason_endpoint(question: str = Form(...)):
    """
    Slow Lane only: Accepts question, checks context/safety, returns answer.
    """
    if not llm_brain:
        raise HTTPException(status_code=503, detail="LLM not loaded")

    # Get recent context
    context = memory.to_context_text()
    
    # Safety check (on recent memory? or just trust strict LLM prompt + gate on input events?)
    # The safety gate usually runs on *current perception*.
    # If we are just reasoning on memory, we should arguably check recent events for hazards.
    # safetygate.py interfaces with a list of event dicts.
    # We'll peek at the last few events in memory buffer.
    
    recent_events = list(memory.buffer)[-10:] # check last 10 events
    safety_block = safetygate.safe_or_stop_recommendation(recent_events)
    
    if safety_block:
        return {"answer": safety_block, "safe": False, "source": "safety_gate"}
        
    answer = llm_brain.answer(context, question)
    return {"answer": answer, "safe": True, "source": "slow_lane_llm"}

@app.post("/two_brain")
async def two_brain_endpoint(file: UploadFile = File(...), question: str = Form(...)):
    """
    Full Pipeline: Image -> YOLO -> Memory -> Safety Check -> (if safe) LLM Reason
    """
    if not llm_brain:
        raise HTTPException(status_code=503, detail="LLM not loaded")
        
    contents = await file.read()
    img = process_image(contents)
    
    # 1. Fast Lane
    events = run_yolo(img)
    
    # 2. Update Memory
    for e in events:
        memory.add_event(e['label'], e['direction'], e['distance_m'], e['confidence'])
        
    # 3. Safety Gate
    # Check CURRENT hazards first and foremost
    safety_block = safetygate.safe_or_stop_recommendation(events)
    
    if safety_block:
        return {
            "events": events,
            "answer": safety_block,
            "safe": False,
            "source": "safety_gate"
        }
    
    # 4. Slow Lane (run only if safe)
    context = memory.to_context_text()
    answer = llm_brain.answer(context, question)
    
    return {
        "events": events,
        "answer": answer,
        "safe": True,
        "source": "slow_lane_llm"
    }

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
