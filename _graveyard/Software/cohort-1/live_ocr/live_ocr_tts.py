# ML_models/live_ocr/live_ocr_tts.py
import argparse, sys, time, threading, re, queue
from collections import deque
from typing import Optional

import cv2
import numpy as np
import gradio as gr

# ------------------ EasyOCR (GPU if present) ------------------
try:
    import easyocr
except Exception as e:
    print("ERROR: easyocr not installed:", e)
    sys.exit(1)

try:
    import torch
    GPU = torch.cuda.is_available()
except Exception:
    GPU = False

print("CUDA Available:", GPU)
reader = easyocr.Reader(['en'], gpu=GPU)

# ------------------ robust camera opener (unchanged from your original) ------------------
CANDIDATES = [
    (0, cv2.CAP_AVFOUNDATION), (1, cv2.CAP_AVFOUNDATION), (2, cv2.CAP_AVFOUNDATION),
    (0, None), (1, None), (2, None),
]
FOURCCS = ["MJPG", "YUY2", ""]
RESOS   = [(1280, 720), (1920, 1080), (640, 480)]

def open_camera_robust():
    for idx, api in CANDIDATES:
        cap = cv2.VideoCapture(idx, api) if api is not None else cv2.VideoCapture(idx)
        if not cap.isOpened():
            cap.release(); continue
        for w,h in RESOS:
            cap.set(cv2.CAP_PROP_FRAME_WIDTH,  w)
            cap.set(cv2.CAP_PROP_FRAME_HEIGHT, h)
            for fcc in FOURCCS:
                if fcc:
                    cap.set(cv2.CAP_PROP_FOURCC, cv2.VideoWriter_fourcc(*fcc))
                bright = 0
                for _ in range(20):
                    ret, frame = cap.read()
                    if not ret:
                        time.sleep(0.03); continue
                    bright += (float(frame.mean()) > 8.0)
                    time.sleep(0.01)
                if bright >= 2:
                    backend = "AVFOUNDATION" if api == cv2.CAP_AVFOUNDATION else "DEFAULT"
                    print(f"[OK] Camera index={idx} backend={backend} fourcc={fcc or 'driver-default'} res={w}x{h}")
                    return cap
        cap.release()
    return None

# ------------------ original pyttsx3 TTS worker (unchanged behavior) ------------------
import platform
def init_tts_engine():
    import pyttsx3
    driver = {"Windows":"sapi5","Darwin":"nsss","Linux":"espeak"}.get(platform.system())
    try: eng = pyttsx3.init(driver) if driver else pyttsx3.init()
    except Exception: eng = pyttsx3.init()
    try:
        eng.setProperty('rate',150)
        eng.setProperty('volume',1.0)
    except Exception:
        pass
    return eng

class TTSWorker(threading.Thread):
    def __init__(self, q: "queue.Queue[str]"):
        super().__init__(daemon=True)
        self.q = q
        self.engine = init_tts_engine()
        self._stop = False
    def run(self):
        while not self._stop:
            t = self.q.get()
            if t is None:
                break
            try:
                self.engine.say(t)
                self.engine.runAndWait()
            except Exception:
                pass
            finally:
                self.q.task_done()
        try: self.engine.stop()
        except Exception: pass
    def close(self):
        self._stop = True
        try: self.engine.stop()
        except Exception: pass

def normalize_text(s: str) -> str:
    return re.sub(r"\s+"," ",s).strip().lower()

# ------------------ Globals / State ------------------
CONFIDENCE_THRESHOLD = 0.5
MIN_TEXT_LEN = 2

_seen = set()
_seen_order = deque(maxlen=300)

RUN_FLAG = False
RUN_LOCK = threading.Lock()
CAP = None  # global camera handle
SPEECH_Q: "queue.Queue[str]" = queue.Queue(maxsize=64)
TTS = TTSWorker(SPEECH_Q); TTS.start()

def set_running(v: bool):
    global RUN_FLAG
    with RUN_LOCK:
        RUN_FLAG = v

def is_running() -> bool:
    with RUN_LOCK:
        return RUN_FLAG

# ------------------ Streaming generator (original detection) ------------------
def stream_frames():
    """
    Yields: (annotated_rgb, text_history, debug_text)
    (We keep voice on the server via pyttsx3; no audio bytes to the client.)
    """
    global CAP
    if CAP is None:
        CAP = open_camera_robust()
        if CAP is None:
            err = np.zeros((480, 640, 3), dtype=np.uint8)
            cv2.putText(err, "Camera failed to open", (40, 240),
                        cv2.FONT_HERSHEY_SIMPLEX, 1.0, (0, 0, 255), 2)
            yield err[:, :, ::-1], "", "**Error:** robust camera failed to open."
            return

    set_running(True)
    fps_t0, fps_frames = time.time(), 0

    while is_running():
        ret, frame_bgr = CAP.read()
        if not ret:
            dbg = "Warning: failed to read frame; stream lost."
            err = np.zeros((480, 640, 3), dtype=np.uint8)
            cv2.putText(err, dbg, (10, 240), cv2.FONT_HERSHEY_SIMPLEX, 0.7, (0, 0, 255), 2)
            yield err[:, :, ::-1], "\n".join(_seen_order), dbg
            time.sleep(0.05); continue

        # ---- NO FLIP (non-mirrored feed) ----

        # ---- ORIGINAL EasyOCR call ----
        results = reader.readtext(frame_bgr)  # [(bbox, text, prob), ...]

        draw_bgr = frame_bgr.copy()
        new_lines = []
        n_boxes = 0

        for (bbox, text, prob) in results:
            if prob < CONFIDENCE_THRESHOLD: continue
            clean = (text or "").strip()
            if len(clean) < MIN_TEXT_LEN: continue

            # draw overlays (same as original)
            try:
                tl = tuple(map(int, bbox[0])); br = tuple(map(int, bbox[2]))
                cv2.rectangle(draw_bgr, tl, br, (0, 255, 0), 2)
                cv2.putText(draw_bgr, clean, (tl[0], max(0, tl[1]-10)),
                            cv2.FONT_HERSHEY_SIMPLEX, 0.7, (0, 255, 0), 2)
                n_boxes += 1
            except Exception:
                pass

            key = normalize_text(clean)
            if key and key not in _seen:
                _seen.add(key)
                _seen_order.append(clean)
                new_lines.append(clean)

        # Speak first-time detections on the server (original behavior)
        if new_lines:
            try:
                SPEECH_Q.put_nowait(". ".join(new_lines))
            except queue.Full:
                pass  # drop if TTS is busy to avoid blocking

        text_history = "\n".join(_seen_order)

        # FPS
        fps_frames += 1
        now = time.time()
        fps = 0.0
        if now - fps_t0 >= 1.0:
            fps = fps_frames / (now - fps_t0)
            fps_t0 = now; fps_frames = 0

        dbg = (
            f"Res: {draw_bgr.shape[1]}x{draw_bgr.shape[0]} | "
            f"Brightness: {draw_bgr.mean():.1f} | Boxes: {n_boxes} | "
            f"Conf≥{CONFIDENCE_THRESHOLD:.2f} | FPS≈{fps:.1f} | "
            "Flip: none"
        )

        # BGR -> RGB for Gradio Image
        annotated_rgb = cv2.cvtColor(draw_bgr, cv2.COLOR_BGR2RGB)
        yield annotated_rgb, text_history, dbg
        time.sleep(0.005)

    # graceful end
    yield None, "\n".join(_seen_order), "Stopped."

def stop_stream():
    set_running(False)
    return "Stopping…"

def reset_seen():
    _seen.clear(); _seen_order.clear()
    return "", "Cleared history."

# ------------------ Gradio UI (auto-start; no flip/audio controls) ------------------
def build_ocr_app():
    with gr.Blocks(title="Live OCR — Robust Camera") as demo:
        gr.Markdown("### 📷 Live OCR (Auto-Start, Non-Mirrored)")

        img    = gr.Image(label="Camera Stream", height=560)
        spoken = gr.Textbox(label="Detected Text (history)", lines=10, interactive=False)
        debug  = gr.Markdown("")

        demo.load(fn=stream_frames, inputs=None, outputs=[img, spoken, debug])

        with gr.Row():
            gr.Button("Reset Seen Texts").click(
                fn=reset_seen, inputs=None, outputs=[spoken, debug]
            )
            gr.Button("Stop").click(
                fn=stop_stream, inputs=None, outputs=debug
            )

        demo.queue()

    return demo