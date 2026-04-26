from fastapi import APIRouter, UploadFile, File, HTTPException
from faster_whisper import WhisperModel
from pathlib import Path
import tempfile
import os

router = APIRouter(prefix = "/stt", tags = ["stt"])

model = WhisperModel("base", compute_type = "int8")


@router.post("/transcribe")
async def transcribe_audio(file: UploadFile = File(...)):
    if not file:
        raise HTTPException(status_code = 400, detail = "No file uploaded")

    suffix = Path(file.filename or "recording.m4a").suffix or ".m4a"
    temp_path = None

    try:
        with tempfile.NamedTemporaryFile(delete=False, suffix = suffix) as temp_file:
            content = await file.read()
            temp_file.write(content)
            temp_path = temp_file.name

        segments, _ = model.transcribe(temp_path)
        transcript = " ".join(segment.text for segment in segments).strip()

        return {"transcript": transcript}

    except Exception as e:
        raise HTTPException(status_code = 500, detail = str(e))
    finally:
        if temp_path and os.path.exists(temp_path):
            os.remove(temp_path)