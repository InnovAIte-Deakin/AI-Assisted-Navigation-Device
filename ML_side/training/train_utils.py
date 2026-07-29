"""YOLO training and validation wrappers.

Ported from:
  - ML_side/notebooks/cohort-1/02_object_detection_training.ipynb
  - ML_side/notebooks/cohort-2/04_training_and_depth_estimation.ipynb

The notebooks called `model.train(...)` and `model.val(...)` directly with
inline arguments, differently in every cell, with results read off printed
dicts by hand. This wraps the same calls so training runs are reproducible
from a single function call and validation always returns the same
dictionary shape — which is what was missing per the ML README's Cohort 1
postmortem ("no record of which config produced which weights").

Requires `ultralytics` (already a project dependency).
"""

from ultralytics import YOLO

# ---------------------------------------------------------------------------
# Known-good starting configs, pulled from the actual notebook cells and from
# ML_side/experiments/*/args.yaml (per README, args.yaml is the authoritative
# record of what was actually run). Treat these as starting points, not
# guarantees — always check experiments/<run>/results.csv for real numbers.
# ---------------------------------------------------------------------------

CONFIG_V8N_STANDARD = dict(
    imgsz=640,
    epochs=100,
    batch=32,
    cache=True,
)

CONFIG_V8S_HEAVY_AUG = dict(
    imgsz=768,
    epochs=250,
    batch=16,
    lr0=0.003,
    patience=50,
    workers=2,
    cache=True,
    mosaic=0.8,
    close_mosaic=10,
    mixup=0.15,
    hsv_h=0.015,
    hsv_s=0.7,
    hsv_v=0.4,
    scale=0.5,
    shear=2.0,
    perspective=0.001,
)

CONFIG_REBUILD_BASELINE = dict(
    imgsz=640,
    epochs=100,
    batch=16,
    optimizer="Adam",
    lr0=0.003,
    workers=2,
    cache=False,
    amp=True,
    patience=20,
)


def train_yolo(base_weights, data_yaml, **train_kwargs):
    """Train a YOLO model. base_weights is a path to a starting .pt file
    (a pretrained checkpoint like 'yolov8n.pt', or an existing best.pt to
    fine-tune further). data_yaml is a path to a YOLO dataset config.

    Pass one of the CONFIG_* dicts above via **, or your own kwargs, e.g.:
        train_yolo("yolov8n.pt", "ML_side/config/newdata.yaml", **CONFIG_V8N_STANDARD)

    Returns the ultralytics training results object. The actual weights end
    up at runs/detect/<name>/weights/best.pt — ultralytics decides the run
    name, so check the printed save directory or use find_latest_best_pt().
    """
    model = YOLO(base_weights)
    return model.train(data=data_yaml, **train_kwargs)


def find_latest_best_pt(runs_glob="runs/detect/train*/weights/best.pt"):
    """Find the most recently created best.pt from a training run, matching
    the notebook's `sorted(glob.glob(...))[-1]` pattern. Sorting by name is
    fragile (relies on ultralytics' train/train2/train3... naming) — prefer
    reading the path directly from the train_yolo() results object if
    possible; this is here because the notebook relied on it and some
    scripts may still need it.
    """
    import glob

    matches = sorted(glob.glob(runs_glob))
    if not matches:
        raise FileNotFoundError(f"No weights found matching {runs_glob}")
    return matches[-1]


def validate_yolo(weights_path, data_yaml, imgsz=640, batch=32, iou=0.7, conf=0.001,
                   split="val", **val_kwargs):
    """Validate a trained model and return a standardized metrics dict.
    Default iou/conf match the notebook's validation cells (low conf so the
    PR curve is computed properly, not just thresholded predictions).
    """
    model = YOLO(weights_path)
    results = model.val(
        data=data_yaml, imgsz=imgsz, batch=batch, iou=iou, conf=conf, split=split,
        **val_kwargs,
    )

    return {
        "mAP50-95": results.box.map,
        "mAP50": results.box.map50,
        "mAP75": results.box.map75,
        "per_class_mAP": results.box.maps,
        "speed_ms": results.speed,
        "class_names": model.names,
    }


def per_class_ap(metrics_dict):
    """Given the dict returned by validate_yolo(), return {class_name: AP50-95}.
    Matches the notebook's manual `for i, ap in enumerate(results.box.maps)` loop.
    """
    names = metrics_dict["class_names"]
    return {names[i]: ap for i, ap in enumerate(metrics_dict["per_class_mAP"])}


def export_tflite(weights_path, imgsz=640, half_variant=True):
    """Export a trained .pt model to TFLite. Ported from notebook 04, section 9.
    Set half_variant=True to also produce the float16 export (smaller, what
    the README lists as `best_float16.tflite`). Returns nothing — ultralytics
    writes the .tflite file(s) next to the source weights and prints the path.
    """
    model = YOLO(weights_path)
    model.export(format="tflite", imgsz=imgsz, nms=True)
    if half_variant:
        model.export(format="tflite", imgsz=imgsz, nms=True, half=True)
