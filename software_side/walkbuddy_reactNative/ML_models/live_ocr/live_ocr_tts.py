# ML_models/live_ocr/live_ocr_tts.py
# Live OCR + TTS (Gradio + EasyOCR)

import sys, re, threading, queue
from collections import deque

import cv2
import numpy as np
import gradio as gr

# ------------------ EasyOCR setup ------------------
try:
    import easyocr
except Exception as e:
    print("EasyOCR not installed:", e)
    sys.exit(1)

try:
    import torch
    GPU = torch.cuda.is_available()
except Exception:
    GPU = False

print("CUDA Available:", GPU)
reader = easyocr.Reader(["en"], gpu=GPU)

# ------------------ TTS setup ------------------
import platform

def init_tts_engine():
    import pyttsx3
    driver = {"Windows": "sapi5", "Darwin": "nsss", "Linux": "espeak"}.get(platform.system())
    try:
        eng = pyttsx3.init(driver) if driver else pyttsx3.init()
    except Exception:
        eng = pyttsx3.init()
    try:
        eng.setProperty("rate", 150)
        eng.setProperty("volume", 1.0)
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

        try:
            self.engine.stop()
        except Exception:
            pass

SPEECH_Q: "queue.Queue[str]" = queue.Queue(maxsize=64)
TTS = TTSWorker(SPEECH_Q)
TTS.start()

def stop_tts_now():
    try:
        while True:
            SPEECH_Q.get_nowait()
            SPEECH_Q.task_done()
    except Exception:
        pass
    try:
        TTS.engine.stop()
    except Exception:
        pass

def normalize_text(s: str) -> str:
    return re.sub(r"\s+", " ", s).strip().lower()

# ------------------ Settings ------------------
CONFIDENCE_THRESHOLD = 0.30
MIN_TEXT_LEN = 2

# ------------------ OCR logic ------------------
def scan_image(img, state):
    """
    OCR logic:
    - webcam feed is mirrored for user comfort
    - OCR runs on a flipped copy so text is read correctly
    - result image stays mirrored so it matches the preview
    """
    if state is None or not isinstance(state, dict):
        state = {"seen": set(), "history": deque(maxlen=300)}

    if img is None:
        return None, "\n".join(state["history"]), "No webcam frame yet", state

    if isinstance(img, dict) and "image" in img:
        img = img["image"]

    if not isinstance(img, np.ndarray):
        return None, "\n".join(state["history"]), "Invalid image input", state

    # img is RGB and already mirrored visually
    preview_rgb = img

    # flip ONLY for OCR so text isn't reversed
    ocr_rgb = preview_rgb[:, ::-1, :]
    frame_bgr = cv2.cvtColor(ocr_rgb, cv2.COLOR_RGB2BGR)

    # resize for speed
    h, w = frame_bgr.shape[:2]
    if w > 900:
        scale = 900 / w
        frame_bgr = cv2.resize(
            frame_bgr,
            (int(w * scale), int(h * scale)),
            interpolation=cv2.INTER_AREA
        )

    results = reader.readtext(frame_bgr)

    draw = frame_bgr.copy()
    new_lines = []
    boxes = 0

    for (bbox, text, prob) in results:
        if prob < CONFIDENCE_THRESHOLD:
            continue
        clean = (text or "").strip()
        if len(clean) < MIN_TEXT_LEN:
            continue

        try:
            tl = tuple(map(int, bbox[0]))
            br = tuple(map(int, bbox[2]))
            cv2.rectangle(draw, tl, br, (0, 255, 0), 2)
            cv2.putText(
                draw, clean,
                (tl[0], max(0, tl[1] - 10)),
                cv2.FONT_HERSHEY_SIMPLEX, 0.7,
                (0, 255, 0), 2
            )
            boxes += 1
        except Exception:
            pass

        key = normalize_text(clean)
        if key not in state["seen"]:
            state["seen"].add(key)
            state["history"].append(clean)
            new_lines.append(clean)

    if new_lines:
        try:
            SPEECH_Q.put_nowait(". ".join(new_lines))
        except queue.Full:
            pass

    # convert back to RGB
    annotated_rgb = cv2.cvtColor(draw, cv2.COLOR_BGR2RGB)

    # mirror result so it matches webcam preview
    annotated_rgb = annotated_rgb[:, ::-1, :]

    history_text = "\n".join(state["history"])
    dbg = f"Scan done: {len(new_lines)} new lines, {boxes} boxes"

    return annotated_rgb, history_text, dbg, state

def reset_all():
    stop_tts_now()
    state = {"seen": set(), "history": deque(maxlen=300)}
    return "", "History cleared", state

def stop_button():
    stop_tts_now()
    return "Stopped speech"

# ------------------ Gradio UI ------------------
def build_ocr_app():
    css = """
    .gr-row { gap: 16px; }
    """

    with gr.Blocks(title="OCR Text Reader", css=css) as demo:
        gr.Markdown(
            "### 📷 OCR Text Reader\n"
            "Webcam preview and OCR result are mirrored and shown side by side.\n"
        )

        spoken  = gr.Textbox(label="Detected Text (history)", lines=8, interactive=False)
        debug   = gr.Markdown("Preview running (OCR on click)")
        state = gr.State({"seen": set(), "history": deque(maxlen=300)})

        # SIDE BY SIDE LAYOUT (this is the important part)
        with gr.Row():
            with gr.Column(scale=1):
                if hasattr(gr, "Camera"):
                    cam = gr.Camera(label="Webcam (mirrored)")
                else:
                    cam = gr.Image(
                        source="webcam",
                        type="numpy",
                        label="Webcam (mirrored)",
                        height=360
                    )

            with gr.Column(scale=1):
                out_img = gr.Image(
                    label="Result (with boxes)",
                    height=360
                )

        with gr.Row():
            scan_btn = gr.Button("Scan / Read")
            reset_btn = gr.Button("Reset Seen Texts")
            stop_btn = gr.Button("Stop")

        scan_btn.click(
            fn=scan_image,
            inputs=[cam, state],
            outputs=[out_img, spoken, debug, state],
        )

        reset_btn.click(
            fn=reset_all,
            inputs=None,
            outputs=[spoken, debug, state],
        )

        stop_btn.click(
            fn=stop_button,
            inputs=None,
            outputs=debug,
        )

        demo.queue()

    return demo
