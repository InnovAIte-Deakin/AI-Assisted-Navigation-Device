from fastapi import APIRouter, File, UploadFile, HTTPException
import tempfile, os, anyio

router = APIRouter(prefix="/stt")

@router.post("/transcribe")
async def transcribe(file: UploadFile = File(...)):
    try:
        from faster_whisper import WhisperModel
    except ImportError:
        raise HTTPException(503, "Run: pip install faster-whisper")
    suffix = os.path.splitext(file.filename or "audio.m4a")[1]
    fd, path = tempfile.mkstemp(suffix=suffix)
    with os.fdopen(fd, "wb") as f:
        f.write(await file.read())
    try:
        def _run(p):
            model = WhisperModel("tiny", device="cpu", compute_type="int8")
            segs, _ = model.transcribe(p, beam_size=1)
            return " ".join(s.text.strip() for s in segs)
        transcript = await anyio.to_thread.run_sync(lambda: _run(path))
    finally:
        os.unlink(path)
    return {"transcript": transcript}
