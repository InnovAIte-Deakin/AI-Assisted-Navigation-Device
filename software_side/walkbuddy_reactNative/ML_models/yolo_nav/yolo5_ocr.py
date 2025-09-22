# yolo5_ocr.py
import os, cv2, pandas as pd
import pytesseract
import torch

# 1) Load YOLOv5 custom weights via Torch Hub
WEIGHTS = "/Users/ritz/Desktop/Capstone/project/yolo_nav/runs/detect/train/weights/best.pt"   # <-- change this
IMAGE   = "images/DEAKIN_Library-12-1.jpg"                      # or any image
assert os.path.exists(WEIGHTS), f"Missing weights: {WEIGHTS}"
assert os.path.exists(IMAGE), f"Missing image: {IMAGE}"

model_v5 = torch.hub.load('ultralytics/yolov5', 'custom', path=WEIGHTS, force_reload=True)
model_v5.conf = 0.20  # adjust threshold

# 2) Run detection
results = model_v5(IMAGE)
print(results)
# results.show()  # uncomment to open annotated window

# 3) Tesseract OCR on detections
img = cv2.imread(IMAGE)
assert img is not None, "Could not read IMAGE"

print("Raw detections (pandas):")
det = results.pandas().xyxy[0]  # YOLOv5 API
print(det)

def ocr_text(bgr):
    gray = cv2.cvtColor(bgr, cv2.COLOR_BGR2GRAY)
    _, th = cv2.threshold(gray, 0, 255, cv2.THRESH_BINARY + cv2.THRESH_OTSU)
    cfg = r'--oem 3 --psm 6'
    return pytesseract.image_to_string(th, config=cfg)

extracted = []
for i, row in det.iterrows():
    cls_name = row['name']
    x1, y1, x2, y2 = map(int, [row['xmin'], row['ymin'], row['xmax'], row['ymax']])

    pad = 50
    x1e, y1e = max(0, x1 - pad), max(0, y1 - pad)
    x2e, y2e = min(img.shape[1], x2 + pad), min(img.shape[0], y2 + pad)

    roi_exp = img[y1e:y2e, x1e:x2e]
    roi_org = img[y1:y2, x1:x2]

    text_exp = ocr_text(roi_exp).strip()
    text_org = ocr_text(roi_org).strip()

    if text_exp:
        extracted.append({"class": cls_name, "roi": "expanded", "text": text_exp})
    if text_org:
        extracted.append({"class": cls_name, "roi": "original", "text": text_org})

print("\nExtracted texts:")
for e in extracted:
    print(f"[{e['class']} | {e['roi']}] {e['text']}")
