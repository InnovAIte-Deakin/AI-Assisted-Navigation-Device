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
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
import gradio as gr

# ML model app builders
from ML_models.yolo_nav.live_gradio import build_yolo_app
from ML_models.live_ocr.live_ocr_tts import build_ocr_app

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


# 5. Health check endpoint
@app.get("/health")
def health():
    return {"ok": True}


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
