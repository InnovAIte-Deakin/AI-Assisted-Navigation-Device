"""TFLite inference helpers for on-device YOLO detection.

Ported from ML_side/notebooks/cohort-2/04_training_and_depth_estimation.ipynb,
section 10 ("TFLite validation"). This is the code that actually exercises
`best.tflite` / `best_float16.tflite` — the exports that the ML README lists
under "Produced but Not Integrated" and Future Directions Tier 3
("Integrate best.tflite for on-device inference"). Nobody has wired this
into anything yet; this module is the starting point for whoever picks that
up, not a finished integration.

Requires either `tflite-runtime` or `tensorflow` (whichever is available —
tries tflite-runtime first since it's much lighter).
"""

import os

import cv2
import numpy as np

try:
    from tflite_runtime.interpreter import Interpreter
except ImportError:
    from tensorflow.lite.python.interpreter import Interpreter


def load_tflite_interpreter(model_path):
    """Load a .tflite model and return (interpreter, input_details, output_details)."""
    interpreter = Interpreter(model_path=model_path)
    interpreter.allocate_tensors()
    return interpreter, interpreter.get_input_details(), interpreter.get_output_details()


def preprocess_image_for_tflite(img_bgr, input_size):
    """Resize + normalize a BGR (OpenCV-loaded) image for a TFLite model.
    input_size is (width, height) — read this from in_details[0]["shape"].
    """
    inp_w, inp_h = input_size
    img = cv2.cvtColor(img_bgr, cv2.COLOR_BGR2RGB)
    img = cv2.resize(img, (inp_w, inp_h))
    x = img.astype(np.float32) / 255.0
    return np.expand_dims(x, axis=0)


def run_tflite_inference(interpreter, in_details, out_details, img_bgr):
    """Run a single BGR image through the interpreter and return raw output tensors."""
    inp_h, inp_w = in_details[0]["shape"][1], in_details[0]["shape"][2]
    x = preprocess_image_for_tflite(img_bgr, (inp_w, inp_h))
    interpreter.set_tensor(in_details[0]["index"], x)
    interpreter.invoke()
    return [interpreter.get_tensor(o["index"]) for o in out_details]


def decode_yolo_tflite_detections(outputs, orig_height, orig_width, conf_thres=0.25):
    """Decode a TFLite YOLO output tensor into a list of detections, each
    (class_id, x_center, y_center, width, height, score) — all normalized
    0-1 against the ORIGINAL image size, i.e. already converted back from
    the model's fixed input resolution.

    This is the parsing logic from the notebook's `save_preds_yolo`, split
    out from the file-writing so callers can do whatever they want with the
    detections (feed the priority/depth logic, write a file, etc).

    Note from the notebook author: "Full mAP computation from TFLite outputs
    requires consistent parsing of the output tensor format" — this parser
    assumes a [N, 6] (x1, y1, x2, y2, score, class) layout, which matched
    their export but is worth re-checking against whatever export settings
    are actually used for the rebuild.
    """
    det = np.squeeze(outputs[0])
    if det.ndim == 1:
        det = det.reshape(1, -1)

    detections = []
    for row in det:
        if row.shape[0] < 6:
            continue
        x1, y1, x2, y2, score, cls = row[:6]
        score = float(score)
        if score < conf_thres:
            continue
        cls = int(cls)

        bw = max(0.0, x2 - x1)
        bh = max(0.0, y2 - y1)
        cx = x1 + bw / 2.0
        cy = y1 + bh / 2.0

        # normalize against the ORIGINAL image dimensions, not model input size
        cx /= orig_width
        cy /= orig_height
        bw /= orig_width
        bh /= orig_height

        detections.append((cls, cx, cy, bw, bh, score))

    return detections


def save_yolo_predictions(detections, out_txt_path):
    """Write decoded detections to a YOLO-format prediction .txt file
    (class x_center y_center width height score), one line per detection.
    """
    lines = [
        f"{cls} {cx:.6f} {cy:.6f} {bw:.6f} {bh:.6f} {score:.6f}"
        for cls, cx, cy, bw, bh, score in detections
    ]
    os.makedirs(os.path.dirname(out_txt_path) or ".", exist_ok=True)
    with open(out_txt_path, "w") as f:
        f.write("\n".join(lines) + ("\n" if lines else ""))
