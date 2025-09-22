# main.py (REPO ROOT)
import os, sys, time, socket, subprocess
from pathlib import Path
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware

BACKEND_DIR = Path(__file__).resolve().parent    # backend/
ROOT = BACKEND_DIR.parent                        # project/
MODELS_DIR = ROOT / "ML_models"
GRADIO_APP = MODELS_DIR / "yolo_nav" / "live_gradio.py"
OCR_APP    = MODELS_DIR / "live ocr" / "live_ocr_tts.py"   # handles the space
PYTHON = sys.executable
PORT = 7860

state = {"proc": None, "mode": None, "tail": []}

def _port_open(host: str, port: int, timeout=0.3) -> bool:
    import socket
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        s.settimeout(timeout)
        try: s.connect((host, port)); return True
        except Exception: return False

def _wait_for_port(max_sec=30) -> bool:
    t0 = time.time()
    while time.time() - t0 < max_sec:
        if _port_open("127.0.0.1", PORT): return True
        time.sleep(0.35)
    return False

def _start(script_path: Path):
    print(script_path)
    if not script_path.exists():
        raise HTTPException(500, f"Script not found: {script_path}")
    env = os.environ.copy()
    env["PYTHONUNBUFFERED"] = "1"
    proc = subprocess.Popen(
        [PYTHON, str(script_path), "--port", str(PORT)],
        cwd=str(script_path.parent),
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        text=True,
        bufsize=1,
        env=env
    )
    state["tail"].clear()
    def _drain():
        try:
            assert proc.stdout is not None
            for line in proc.stdout:
                line = line.rstrip("\n")
                state["tail"].append(line)
                if len(state["tail"]) > 300:
                    state["tail"] = state["tail"][-300:]
        except Exception:
            pass
    import threading; threading.Thread(target=_drain, daemon=True).start()
    return proc

def _stop():
    if state["proc"] and state["proc"].poll() is None:
        state["proc"].terminate()
        try: state["proc"].wait(timeout=5)
        except subprocess.TimeoutExpired: state["proc"].kill()
    state["proc"] = None
    state["mode"] = None

app = FastAPI(title="AI Switchboard")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],     # relax during dev
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

@app.get("/healthz")
def healthz(): return {"ok": True}

@app.get("/status")
def status():
    running = bool(state["proc"] and state["proc"].poll() is None)
    return {"running": running, "mode": state["mode"],
            "port_open": _port_open("127.0.0.1", PORT),
            "url": f"http://127.0.0.1:{PORT}" if running else None}

@app.get("/logs")
def logs(): return {"lines": state["tail"][-120:]}

@app.get("/switch/{mode}")
def switch(mode: str):
    mode = mode.lower()
    if mode not in {"gradio", "ocr"}:
        raise HTTPException(400, "mode must be 'gradio' or 'ocr'")
    if state["mode"] == mode and state["proc"] and state["proc"].poll() is None:
        return {"status": "already_running", "mode": mode, "url": f"http://127.0.0.1:{PORT}"}
    _stop()
    script = GRADIO_APP if mode == "gradio" else OCR_APP
    proc = _start(script)
    state["proc"] = proc
    state["mode"] = mode
    if not _wait_for_port(30):
        tail = "\n".join(state["tail"][-40:])
        _stop()
        raise HTTPException(502, f"{mode} failed to open :{PORT}.\nTail:\n{tail}")
    return {"status": "started", "mode": mode, "url": f"http://127.0.0.1:{PORT}"}

@app.get("/stop")
def stop():
    _stop()
    return {"status": "stopped"}

@app.on_event("shutdown")
def on_shutdown(): _stop()
