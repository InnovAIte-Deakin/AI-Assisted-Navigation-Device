# train_yolov8.py
import os
from ultralytics import YOLO

DATA_YAML = "data.yaml"
WEIGHTS_DIR = "weights"
os.makedirs(WEIGHTS_DIR, exist_ok=True)

# Optional: download a base model the first time
BASE_WEIGHTS = os.path.join(WEIGHTS_DIR, "yolov8s.pt")
if not os.path.exists(BASE_WEIGHTS):
    import urllib.request
    url = "https://github.com/ultralytics/assets/releases/download/v0.0.0/yolov8s.pt"
    print("Downloading yolov8s.pt...")
    urllib.request.urlretrieve(url, BASE_WEIGHTS)

# Train
model = YOLO(BASE_WEIGHTS)
results = model.train(
    data=DATA_YAML,
    epochs=100,        # reduce to 10 if you want a quick dry-run
    imgsz=640,
    batch=16,          # lower if RAM is tight
    cache=True
)

best = os.path.join(results.save_dir, "weights", "best.pt")
print("\n✅ Training complete.")
print("Best weights:", best)
