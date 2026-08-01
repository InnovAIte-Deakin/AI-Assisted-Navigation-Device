# Reusable Code Compiled from Previous Notebooks

Week 4/5 task: pull reusable code out of `ML_side/notebooks/cohort-1/` and
`cohort-2/` so the data pipeline and training pipeline rebuilds have real
functions to import instead of copy-pasting cells out of old Colab sessions.

Source notebooks reviewed (all four listed in the ML README):
- `cohort-1/01_data_processing.ipynb`
- `cohort-1/02_object_detection_training.ipynb`
- `cohort-1/03_ocr_integration.ipynb`
- `cohort-2/04_training_and_depth_estimation.ipynb`

Note: `01_data_processing.ipynb` and `02_object_detection_training.ipynb`
turned out to contain almost identical cells (data split + YOLO training),
with `02` being a superset that also adds the Roboflow-merge and Gradio-demo
sections. Reusable code was extracted once, not duplicated per notebook.

## Where each file goes in the repo

| Compiled file | Suggested repo location |
|---|---|
| `dataset_utils.py` | `ML_side/data/dataset_utils.py` |
| `train_utils.py` | `ML_side/training/train_utils.py` |
| `tflite_utils.py` | `ML_side/inference/tflite_utils.py` |
| `detection_stabilizer.py` | `ML_side/inference/detection_stabilizer.py` |
| `depth_estimator.py` | `ML_side/depth/depth_estimator.py` (also needs an empty `ML_side/depth/__init__.py` next to it) |

## What came from where

**`dataset_utils.py`** — from `01_data_processing.ipynb` and
`02_object_detection_training.ipynb`: HEIC→JPG conversion, image/label
pairing, train/val/test split, class counting, class-ID remapping. Also
folds in the Roboflow class-remap and dataset-merge cells from
`04_training_and_depth_estimation.ipynb` — those notebooks solved the same
"remap class IDs" and "merge two datasets" problems independently with
separate code; this compiles them into one function each instead of two.

**`train_utils.py`** — from `02_object_detection_training.ipynb`'s training
and validation cells, plus `04_training_and_depth_estimation.ipynb`'s
training config and TFLite export cell. Includes the three actual configs
that were run (standard v8n, heavy-augmentation v8s, and the rebuild
baseline from notebook 04) as named presets, since previously these only
existed as inline arguments typed differently in every cell.

**`tflite_utils.py`** — from `04_training_and_depth_estimation.ipynb`,
section 10. This is the code that runs `best.tflite` — the export the ML
README lists as "Produced but Not Integrated." Compiling it doesn't
integrate it into the app; it just means whoever picks up that Tier 3 task
has a working starting point instead of an untouched notebook cell.

**`depth_estimator.py`** — from `04_training_and_depth_estimation.ipynb`,
section 11 ("Depth estimation — work in progress"). Important: a teammate
already wrote `ML_side/tests/test_depth_estimator.py` against a
`depth.depth_estimator` module that didn't exist yet. This file was written
to match those test signatures exactly, not invented independently — ran
the existing test suite against it locally and 8 of 9 tests pass (the 9th
needs a real image fixture from the repo, `test.png`, which isn't available
outside the actual checkout). Run this to confirm once it's placed:
```
cd ML_side
pytest tests/test_depth_estimator.py -v
```

**`detection_stabilizer.py`** — from `02_object_detection_training.ipynb`'s
Gradio live-camera demo. The demo itself (webcam UI, gTTS) doesn't fit this
project's phone-camera + FastAPI architecture, so it wasn't ported. But the
persistence/cooldown logic inside it — don't announce a detection until it's
shown up in several recent frames, then wait before announcing again — is a
real fix for a real, still-open gap: `message_reasoning.py` currently caps
announcements at 1 with no debouncing.

## What was deliberately NOT ported

- **`03_ocr_integration.ipynb`** — this notebook is a `cv2.VideoCapture(0)`
  webcam loop using `pyttsx3` with the Windows `sapi5` speech engine. It
  doesn't touch the phone camera or the app's own `TTSService`, and
  `sapi5` won't run on macOS or the deployed backend at all. Nothing here
  was directly reusable. The one thing worth keeping an eye on: it computes
  CER/WER/BLEU scores to evaluate OCR quality — if the team ever wants a
  formal OCR accuracy benchmark, that scoring approach (not the surrounding
  webcam code) is worth revisiting.
- **Gradio webcam UI itself** (from notebook 02) — Colab-only demo
  scaffolding, not part of the deployed app.
- **`gTTS`-based speech generation** — the backend already has its own
  `TTSService`; per the root README's coordination rules, TTS is the
  frontend's responsibility. No server-side TTS calls were carried over.

## Suggested next step

Once these land in the repo at the paths above, the two "rebuild" tasks
(data pipeline, training pipeline) can import directly from them instead of
starting from scratch — that was the point of doing this first.
