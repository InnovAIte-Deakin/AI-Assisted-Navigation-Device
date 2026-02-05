import sys
import os
import logging
from pathlib import Path
from fastapi import FastAPI, UploadFile, File, HTTPException
from fastapi.middleware.cors import CORSMiddleware
import tempfile

# 1. SETUP PATHS
CURRENT_FILE = Path(__file__).resolve()
BACKEND_DIR = CURRENT_FILE.parent
PROJECT_ROOT = BACKEND_DIR.parent

if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

# 2. IMPORTS
# Core Adapters
try:
    from ML_models.adapters.yolo_adapter import vision_adapter
    from ML_models.adapters.ocr_adapter import ocr_adapter
    from ML_models.tts_service.message_reasoning import process_adapter_output
except ImportError as e:
    print(f"❌ Adapter Import Error: {e}")

# Slow Lane Modules (The "Smart" logic)
# Ensure 'slow_lane' folder is inside 'backend'
from slow_lane.slowlanellm import SlowLaneLLM
from slow_lane.memorybuffer import NavigationMemory
import slow_lane.safetygate as safetygate

# Logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

app = FastAPI(title="WalkBuddy Unified Brain")

# 3. CONFIG & GLOBALS
# Update this path if your model is elsewhere
LLM_MODEL_PATH = PROJECT_ROOT / "ML_side/models/llama-3.2-1b-instruct-q4_k_m.gguf"

# Global Instances
memory = NavigationMemory(max_events=50) # Short-term memory
llm_brain = None

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# 4. LIFECYCLE
@app.on_event("startup")
async def startup_event():
    global llm_brain
    
    # Load LLM
    if os.path.exists(LLM_MODEL_PATH):
        logger.info(f"Loading Slow Lane LLM from {LLM_MODEL_PATH}...")
        try:
            llm_brain = SlowLaneLLM(str(LLM_MODEL_PATH))
            logger.info("✅ Slow Lane LLM Ready.")
        except Exception as e:
            logger.error(f"❌ Failed to load LLM: {e}")
    else:
        logger.warning(f"⚠️ LLM not found at {LLM_MODEL_PATH}. /chat will fail.")

    # Reset Memory
    memory.buffer.clear()

@app.get("/")
def root():
    return {"status": "online", "brain": "Unified Two-Brain"}

# --- VISION ENDPOINT (Perception + Memory) ---
@app.post("/vision")
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
@app.post("/ocr")
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
@app.post("/chat")
async def chat_endpoint(query: dict):
    """
    Uses Memory + LLM.
    """
    user_q = query.get("query", "").strip()
    if not user_q:
        return {"response": "I didn't hear a question."}

    # 1. SAFETY GATE
    recent_events = list(memory.buffer)[-10:]
    hazard_msg = safetygate.safe_or_stop_recommendation(recent_events)
    if hazard_msg:
         return {"response": hazard_msg}

    # 2. LLM REASONING
    if not llm_brain:
        return {"response": "My reasoning brain is offline."}

    try:
        context_str = memory.to_context_text(n=20)
        json_response_str = llm_brain.answer(context_str, user_q)
        
        # Cleanup markdown
        clean_resp = json_response_str.replace("```json", "").replace("```", "").strip()
        
        import json
        try:
            parsed = json.loads(clean_resp)
            final_text = parsed.get("suggested_action", parsed.get("summary", clean_resp))
        except:
            final_text = clean_resp 

        return {"response": final_text}
        
    except Exception as e:
        logger.error(f"LLM error: {e}")
        return {"response": "I'm having trouble thinking right now."}

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)