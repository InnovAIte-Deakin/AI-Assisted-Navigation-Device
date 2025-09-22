# infer_and_tts.py
import os, sys, platform, subprocess, uuid
import cv2
import matplotlib.pyplot as plt
from ultralytics import YOLO
import yaml
from gtts import gTTS

BEST = "runs/detect/train/weights/best.pt"  # adjust if your run folder name differs
IMG1 = "images/DEAKIN_Library-12-1.jpg"
IMG2 = "images/IMG_7889.jpg"
DATA_YAML = "data.yaml"

def speak(text: str):
    """Cross-platform: save mp3 and try to play it."""
    mp3 = f"{uuid.uuid4().hex}.mp3"
    gTTS(text=text, lang='en').save(mp3)
    system = platform.system()
    try:
        if system == "Darwin":        # macOS
            subprocess.run(["afplay", mp3], check=False)
        elif system == "Windows":
            os.startfile(mp3)         # default music player
        else:                         # Linux
            subprocess.run(["xdg-open", mp3], check=False)
    except Exception as e:
        print(f"(Saved TTS to {mp3}; could not auto-play: {e})")

def show_result(result, title=""):
    img_bgr = result.plot()
    img_rgb = cv2.cvtColor(img_bgr, cv2.COLOR_BGR2RGB)
    plt.imshow(img_rgb); plt.axis('off'); plt.title(title); plt.show()

def classes_in_result(result, names_map, min_conf=0.10):
    found = set()
    boxes = result.boxes
    if boxes is None or len(boxes) == 0:
        return found
    for cls_i, conf_i in zip(boxes.cls.tolist(), boxes.conf.tolist()):
        if conf_i >= min_conf:
            found.add(names_map.get(int(cls_i), str(int(cls_i))).lower())
    return found

def main():
    if not os.path.exists(BEST):
        print("Best weights not found at:", BEST)
        sys.exit(1)

    model = YOLO(BEST)
    # names
    names = {int(k): v for k, v in model.names.items()} if hasattr(model, "names") else {}

    # Image 1 (conf=0.10)
    res1 = model.predict(source=IMG1, conf=0.10, verbose=False)[0]
    show_result(res1, title=os.path.basename(IMG1))
    det1 = classes_in_result(res1, names, min_conf=0.10)
    if "monitor" in det1:
        speak("Monitor ahead")
    if "office-chair" in det1:
        speak("Office chair ahead")

    # Image 2 (conf=0.21)
    res2 = model.predict(source=IMG2, conf=0.21, verbose=False)[0]
    show_result(res2, title=os.path.basename(IMG2))
    det2 = classes_in_result(res2, names, min_conf=0.21)
    if "monitor" in det2:
        speak("Monitor ahead")
    if "office-chair" in det2:
        speak("Office chair ahead")

    # (Optional) quick train class coverage:
    with open(DATA_YAML, "r") as f:
        data_yaml = yaml.safe_load(f)
    classes = data_yaml["names"]
    counts = [0] * len(classes)
    labels_dir = "dataset/train/labels"
    if os.path.isdir(labels_dir):
        for lf in os.listdir(labels_dir):
            with open(os.path.join(labels_dir, lf)) as fp:
                lines = fp.readlines()
            label_ids = set(int(line.split()[0]) for line in lines if line.strip())
            for lid in label_ids:
                counts[lid] += 1
        print("\nImages containing each class (TRAIN split):")
        for i, c in enumerate(classes):
            print(f"  {c}: {counts[i]} images")

if __name__ == "__main__":
    main()
