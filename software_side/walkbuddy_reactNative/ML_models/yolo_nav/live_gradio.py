import uuid, time, re, tempfile, os
from collections import deque
from ultralytics import YOLO
import gradio as gr
from gtts import gTTS
from pathlib import Path

THIS_DIR = Path(__file__).resolve().parent
WEIGHTS = THIS_DIR / "weights" / "yolov8s.pt"

# Load model directly from weights
model = YOLO(WEIGHTS)

def norm_label(s: str) -> str:
    return re.sub(r"[\s_]+", "-", s.strip().lower())

names = {int(k): v for k, v in model.names.items()} if hasattr(model, "names") else {}
names_norm = {k: norm_label(v) for k, v in names.items()}

CONF_THRESH = {
    "office-chair": 0.80,
    "monitor": 0.60,
    "books": 0.60
}
SAY = {
    "office-chair": "Chair ahead",
    "monitor": "Monitor ahead",
    "books": "Books ahead",
}

MIN_AREA_FRAC = 0.012
IOU_NMS = 0.60
PERSIST_N = 5
PERSIST_M = 3
COOLDOWN_SEC = 3.0

def gen_tts_file(text: str) -> str | None:
    fd, abs_path = tempfile.mkstemp(suffix=".mp3", prefix="tts_")
    os.close(fd)
    try:
        with open(abs_path, "wb") as f:
            gTTS(text=text, lang="en").write_to_fp(f)
        return abs_path
    except Exception:
        try: os.remove(abs_path)
        except Exception: pass
        return None

def init_state():
    return {
        "last_spoken": 0.0,
        "hist": {cls: deque(maxlen=PERSIST_N) for cls in CONF_THRESH.keys()},
    }

def box_area_xyxy(box):
    x1, y1, x2, y2 = box
    return max(0.0, x2 - x1) * max(0.0, y2 - y1)

def detect_and_speak(frame, state):
    if state is None or "hist" not in state:
        state = init_state()
    if frame is None:
        return None, None, state

    frame = frame[:, :, ::-1]  
    H, W = frame.shape[:2]
    frame_area = float(H * W)

    res = model.predict(
        source=frame,
        conf=0.25,
        iou=IOU_NMS,
        imgsz=640,
        verbose=False
    )[0]

    annotated = res.plot()  

    frame_hits = {cls: 0 for cls in CONF_THRESH.keys()}

    if res.boxes is not None and len(res.boxes) > 0:
        cls_list = res.boxes.cls.tolist()
        conf_list = res.boxes.conf.tolist()
        xyxy_list = res.boxes.xyxy.cpu().numpy()

        for cls_i, conf_i, box in zip(cls_list, conf_list, xyxy_list):
            raw = names.get(int(cls_i), str(int(cls_i)))
            cls_key = norm_label(raw)

            if cls_key not in CONF_THRESH:
                continue
            if conf_i < CONF_THRESH[cls_key]:
                continue
            if box_area_xyxy(box) < MIN_AREA_FRAC * frame_area:
                continue

            frame_hits[cls_key] += 1

    for cls in CONF_THRESH.keys():
        state["hist"][cls].append(1 if frame_hits[cls] > 0 else 0)

    def persisted(cls):
        window = state["hist"][cls]
        return len(window) == PERSIST_N and sum(window) >= PERSIST_M

    now = time.time()
    audio_path = None

    if (now - state["last_spoken"]) > COOLDOWN_SEC:
        for cls in SAY:
            if persisted(cls):
                audio_path = gen_tts_file(SAY[cls])
                state["last_spoken"] = now
                for k in state["hist"]:
                    state["hist"][k].clear()
                break

    return annotated, audio_path, state


#  NEW: build UI Function
def build_yolo_app():
    with gr.Blocks() as demo:
        gr.Markdown("## YOLOv8 Webcam with TTS")

        cam = gr.Image(source="webcam", streaming=True, type="numpy")
        out_img = gr.Image()
        out_audio = gr.Audio(type="filepath", autoplay=True)
        state = gr.State(init_state())

        def _wrapper(frame, st):
            annotated, audio_path, st = detect_and_speak(frame, st)
            if annotated is not None:
                annotated = annotated[:, :, ::-1]
            audio_out = audio_path if audio_path else gr.update()
            return annotated, audio_out, st

        cam.stream(_wrapper, inputs=[cam, state], outputs=[out_img, out_audio, state])
        demo.queue()

    return demo
