# ML Side — WalkBuddy

WalkBuddy is an AI-assisted indoor navigation system for visually impaired users. The ML side is responsible for object detection, OCR, and the offline LLM that powers navigation guidance.

## Current Status and Boundaries

### Verified Current Behaviour

- The production backend is `software_side/walkbuddy_reactNative/backend/main.py`. It consumes the model artifacts under `ML_side/models/`; it is the source to use when assessing deployed behaviour.
- The repository-configured v1 training class set is: `book`, `books`, `monitor`, `office-chair`, `whiteboard`, `table`, `tv`, and `couch`. The active `best.pt` model metadata still requires confirmation by inspecting `model.names` in a valid backend environment.
- Safety warnings do occur. The current safety-gate policy can issue a warning for qualifying high-confidence detections ahead, including several of the deployed furniture labels. This does not establish end-to-end mobile runtime behaviour, which still requires runtime testing.

### Historical Information

The postmortem and Cohort 1/Cohort 2 experiment sections below preserve historical evidence and known lineage gaps. They are not a substitute for the current production code, model metadata, or runtime testing.

### Experimental and Demo Functionality

- `ML_side/main.py` is experimental and is not the production backend.
- The isolated simulated API and duplicate priority demonstration (`ML_side/deployment/api.py` and `ML_side/priority_demo_cli.py`) were retired in 2026 T2. They returned fabricated detections and used a legacy 15-class class-priority policy; neither represented deployed behaviour.

The experimental entry point and historical demo material should not be used to infer production backend behaviour.

### Unresolved Work

The repository-configured v1 training taxonomy lacks important navigation-hazard classes such as stairs, doors, and people. The active best.pt metadata still requires confirmation in a valid backend environment. In addition, multiple class-to-risk policies exist across the system and can classify ordinary objects more severely than intended. Any runtime safety-policy change requires cross-stream review before implementation.

---

## Postmortem — Last Trimester

Last trimester produced working models but the surrounding process had gaps that made the work difficult to build on. This section documents what those gaps were so this trimester doesn't repeat them.

- **Model weights were not traceable.** `best.pt` is in the repo but there is no record of which dataset, preprocessing steps, or training config produced it. If someone needed to retrain from scratch, they couldn't.
- **The training dataset was not stored anywhere shared.** The combined Roboflow dataset used for Cohort 1 was never uploaded to a shared location. The training notebooks were also not committed alongside the weights. The experiment exists as an output with no recoverable input.
- **People trained on different data without knowing it.** There was no versioning on the dataset. The Cohort 1 reports reference 147 office chairs; the repo dataset has 20. This went undetected during the trimester.
- **PDF report figures were not checked against the actual logs.** The reports contain mAP values that are up to +20% higher than what `results.csv` recorded. These were likely transcription or misreading errors, but the reports were shared and referenced without being verified.
- **The data contract between ML and the backend was never agreed on.** Field names, confidence thresholds, and response structure were assumed rather than specified. 

The result was that each person's work was hard to compare or combine with anyone else's. The collaboration guidelines below exist to prevent this.

---

## Collaboration & Storage Guidelines

The full contribution workflow — opening a GitHub issue with the right label, updating the [AIAND Progress Tracker](https://docs.google.com/spreadsheets/d/1NogkKQmUfVSwdF_XZ5LVf-zvVt_XMrCdbr67mCDDbcI/edit?usp=sharing), notifying the team on Microsoft Teams, and opening a PR — is documented in the [root README](../README.md#how-we-work). The rules below cover storage and versioning specific to the ML side.

### Storage Policy

Large binary files do not belong in the repo. Code, configs, and logs do.

| Artifact | Location | Notes |
|---|---|---|
| Dataset images (train/val) | Teams SharePoint | Never commit to repo |
| Model weights (`.pt`, `.tflite`, `.gguf`) | Teams SharePoint | Never commit to repo |
| PDF reports | Teams SharePoint | Historical reference only, never authoritative |
| Training configs (`args.yaml`, `dataset.yaml`) | Repo | Text, version-controlled |
| Experiment logs (`results.csv`) | Repo | Authoritative metrics — always commit |
| Notebooks (`.ipynb`) | Repo | Commit with cleared or minimal outputs |
| Analysis/integrity scripts (`.py`) | Repo | Code belongs here |


### Dataset Versioning Convention

Dataset images live on the Teams SharePoint under:

```
AI Assisted Navigation Device > AIAND_REPO > ML_side > 2026 Trimester 1 > data > v1
    ├── train_dataset/
    └── val_dataset/
```

When producing a new dataset (new classes, cleaned annotations, additional images):
- Increment the version: `v1 → v2`
- Keep the same internal folder structure (`train_dataset/`, `val_dataset/`)
- Update the class distribution table in this README
- Update `config/newdata.yaml` with the new paths and commit it

### Model Versioning

When you produce new weights:
1. Upload to Teams SharePoint under the appropriate trimester folder
2. Document it in the **Models** section of this README: which dataset version, which config, what results
3. Do not replace `best.pt` in the repo without updating this README first

### Collaboration Rules

- Everyone working on the ML side must have read access to the Teams SharePoint folder
- Every experiment run requires `args.yaml` and `results.csv` committed to the repo — if it's not logged here, it doesn't count
- Any new trained model must be documented in this README before merging to main
- Do not start training on a new dataset version without noting it here first — this is to prevent silent drift 
- `results.csv` and `args.yaml` are the source of truth for all experiment claims. PDFs are archive only.

---

## ML ↔ Software Integration

The production backend, `software_side/walkbuddy_reactNative/backend/main.py`, loads model artifacts from `ML_side/models/` during local execution, or through the Docker volume mount when run with Docker:

```yaml
# docker-compose.yml
volumes:
  - ../../../ML_side/models:/models
```

The backend reads from `$WALKBUDDY_MODEL_DIR` (defaults to `/models` inside the container):

| File | Consumed by | Purpose |
|---|---|---|
| `models/best.pt` | `adapters/vision_adapter.py` | YOLOv8n object detection |
| `models/llama-3.2-1b-instruct-q4_k_m.gguf` | `backend/slow_lane/brain.py` | Offline LLM for navigation chat |

The ML side produces weights. The software side consumes them. There is no shared code — the integration boundary is the model files and the shape of the data they return. Cross-layer data contracts (detection field names, confidence thresholds, response format) are a known gap being addressed this trimester.

---

## Models

### Deployed

| File | Model | Used by | Notes |
|---|---|---|---|
| `models/best.pt` | YOLOv8n | `vision_adapter.py` | Confidence threshold 0.25 set in `routers/ai_service.py` |
| `models/llama-3.2-1b-instruct-q4_k_m.gguf` | Llama 3.2-1B (quantized) | `backend/slow_lane/brain.py` | Offline, runs via llama-cpp-python. **Not stored in Git — follow the authoritative `docs/LOCAL_SETUP.md` model-asset process. The backend setup script is an optional helper for this GGUF only; it does not provide `best.pt`.** |

### Historical TFLite Export Workflow

| File | Format | Notes |
|---|---|---|
| `models/best.tflite` | TensorFlow Lite (int8) | Historical export target; not currently present in the repository |
| `models/best_float16.tflite` | TensorFlow Lite (float16) | Historical export target; not currently present in the repository |

The export commands and related workflow remain in `notebooks/cohort-2/04_training_and_depth_estimation.ipynb` as historical and experimental evidence. On-device inference is not integrated into the app. See **Future Directions** for context.

---

## Dataset

### Location

Dataset images have been moved off the repo to the Teams SharePoint. They are no longer stored in this repository.

```
Teams: AI Assisted Navigation Device > AIAND_REPO > ML_side > 2026 Trimester 1 > data > v1
    ├── train_dataset/    (3,285 images + YOLO annotations)
    └── val_dataset/      (202 images + YOLO annotations)
```

The only dataset artifact kept in the repo is `data/dataset_analyze.py`, used to verify dataset integrity (class counts, train/val balance, orphaned files). When you download the dataset from Teams, run this script to confirm your local copy is clean.

### Format

- Annotation format: YOLO bounding boxes
- One `.txt` label file per image
- Splits: train / val

### Class Distribution (v1)

| Class | Train | Val | Total |
|---|---:|---:|---:|
| books | 1,553 | 125 | 1,678 |
| couch | 1,003 | 50 | 1,053 |
| whiteboard | 582 | 31 | 613 |
| table | 553 | 31 | 584 |
| tv | 531 | 26 | 557 |
| monitor | 460 | 50 | 510 |
| office-chair | 181 | 36 | 217 |
| book | 5 | 0 | 5 |

`book` (singular) is effectively unusable with 5 annotations. `office-chair` is underrepresented relative to its importance as a navigation obstacle. See **Known Gaps**.

### Integrity Tooling

```bash
python data/dataset_analyze.py
```

Reports: class counts, train/val balance, orphaned image–label pairs, image resolution distribution.

---

## Experiments — Cohort 1

### Scope

- Evaluated 5 YOLO variants: v5n, v5s, v8n, v8s, v11n
- Dataset: Deakin Library images + Roboflow combined export (not present in repo — see Postmortem)
- Secondary work: OCR pipeline integration (`notebooks/cohort-1/03_ocr_integration.ipynb`) 

### Configuration (from `args.yaml` — authoritative)

| Model | Base Weights | Img Size | Target Epochs | Batch | lr0 | Augmentations |
|---|---|---|---|---|---|---|
| v5n | yolov5n.pt | 640 | 100 | 32 | 0.01 | Mosaic (1.0) |
| v5s | yolov5s.pt | 640 | 100 | 32 | 0.01 | Mosaic (1.0) |
| v8n | yolov8n.pt | 640 | 100 | 32 | 0.01 | Mosaic (1.0) |
| v8s | yolov8s.pt | 640 | 250 | 16 | 0.003 | Mosaic (0.8), MixUp (0.15) |
| v11n | yolo11n.pt | 640 | 100 | 32 | 0.01 | Mosaic (1.0) |

### Results (from `results.csv` — authoritative)

| Model | Final Epoch | Precision | Recall | mAP50 | mAP50-95 | Status |
|---|---|---|---|---|---|---|
| v8n | 100 | 0.853 | 0.841 | **0.857** | **0.626** | **Selected — best balanced** |
| v5n | 92 | 0.870 | 0.803 | 0.859 | 0.588 | Converged early, weaker recall |
| v5s | 100 | 0.869 | 0.820 | 0.852 | 0.603 | Stable |
| v8s | 169 | 0.867 | 0.791 | 0.835 | 0.581 | Stopped early (target: 250) |
| v11n | 99 | 0.833 | 0.846 | 0.830 | 0.557 | Stable, weakest mAP50-95 |

YOLOv8n was selected for `best.pt` — best precision–recall balance and strongest mAP50-95.

### Known Metric Discrepancies

PDF reports circulated last trimester contained inflated figures. For the record:

| Model | Reported mAP50 | Actual mAP50 | Inflation |
|---|---|---|---|
| v5s | 0.950 | 0.852 | +9.8% |
| v8n | 0.934 | 0.857 | +7.7% |
| v8n mAP50-95 | 0.826 | 0.626 | +20.0% |
| v11n | 0.848 | 0.830 | +1.8% |
| v8s | 0.845 | 0.835 | +1.0% |

Likely causes: misreading per-class metrics as aggregate, copying intermediate epoch values, manual transcription errors.

### Source-of-Truth Policy

1. `results.csv` overrides any report
2. `args.yaml` overrides any narrative description
3. PDFs are historical reference only

### Reproducibility Status

Cohort 1 is **not reproducible end-to-end**. The combined Roboflow dataset used for training is missing, training notebooks were not committed alongside weights, and experiment lineage was not documented. This README reflects the maximum defensible reconstruction from available logs and configs.

---

## Experiments — Cohort 2

Work documented in `notebooks/cohort-2/04_training_and_depth_estimation.ipynb`:

- Additional training iterations on the custom dataset
- Depth estimation exploration (monocular depth from camera frames)

Depth estimation has not been integrated into the backend. It remains notebook-only. See **Future Directions**.

---

## Known Gaps

These are inherited problems that directly affect the reliability of the current system.

**Critical**

- **Safety coverage and risk-policy mismatch.** The deterministic safety gate (`backend/slow_lane/safetygate.py`) does produce warnings for qualifying high-confidence detections ahead, including several deployed furniture labels. However, the v1 model does not detect important navigation hazards such as `stairs`, `wall`, `door`, `person`, `obstacle`, `pole`, or `edge`. Separate class-to-risk policies across safety, vision, and TTS can also assign ordinary objects inconsistent or overly severe treatment. Cross-stream review is required before changing runtime behaviour.

**Moderate**

- **Class-to-risk policy alignment.** Agree the intended handling for each detected class across `message_reasoning.py`, `safetygate.py`, and the vision adapter before altering warnings or spoken guidance.
- **OCR detections not stored to NavigationMemory.** Vision detections feed the LLM's context buffer; OCR detections do not. If the camera reads an "EXIT" sign, the LLM has no knowledge of it.
- **Proximity is a bbox area heuristic.** Proximity ("nearby" vs "far") is estimated by whether the bounding box covers >10% of the image. This is a rough proxy. Actual depth estimation would be more reliable.

**Minor**

- **`book` class unusable.** 5 training annotations. Will not produce reliable detections.
- **`office-chair` underrepresented.** 217 annotations for a high-priority obstacle class. Needs more data.
- **Cohort 1 not reproducible.** Original training dataset and full notebook lineage are missing.

---

## Future Directions — 2026 Trimester 1

### Tier 1 — Fix What Is Broken

- **Add hazard classes to the YOLO dataset.** Train on `stairs`, `door`, `person` at minimum so deployed detection coverage includes important navigation hazards beyond the furniture cases the current safety gate can warn about. Requires new data collection and annotation, then a new training run against dataset v2.
- **Integrate depth estimation into the backend.** Cohort 2 explored this in notebooks. Wiring it into `routers/ai_service.py` would replace the bbox-area proximity heuristic with actual distance estimates from the same camera frame — no additional hardware required.

### Tier 2 — Quality Improvements

- **Align class-to-risk policies.** Make the safety gate, vision adapter, and TTS reasoning apply the agreed policy consistently. This requires ML, Deployment, Software, and Code Integration review before runtime behaviour changes.
- **Wire OCR detections into NavigationMemory.** OCR results are currently returned to the frontend but not stored in the memory buffer the LLM reads from. Adding OCR events to memory means the LLM can reference sign text when answering navigation questions.
- **Expand TTS to surface multiple detections.** `process_detections()` currently returns `max_messages=1`. If a chair is on the left and a table is ahead, only one is announced. Increasing to 2–3 with priority ordering would give users a fuller picture.

### Tier 3 — Architectural Improvements

- **Export and integrate TFLite models for on-device inference.** `best.tflite` and `best_float16.tflite` are not currently present in the repository. Recreating the historical export workflow and integrating the resulting artifacts into the React Native app via a TFLite library would remove the dependency on the backend server for object detection — critical for a navigation aid that may be used in low-connectivity environments.
- **Expand the dataset to more indoor environments.** The current dataset is specific to library and office settings. Hallways, elevators, staircases, and bathrooms would make the model more general and more useful in the real environments the app is designed for.
- **Continuous frame scanning.** The frontend currently sends frames on-demand. Automatic periodic scanning (e.g. every 2 seconds) would make navigation guidance proactive rather than reactive.

---

## Directory Structure

```
ML_side/
├── config/
│   └── newdata.yaml              # YOLO dataset config — 8 classes, train/val paths
├── data/
│   └── dataset_analyze.py        # Integrity check script (only dataset artifact in repo)
│                                 # Images live on Teams SharePoint (see Dataset section)
├── experiments/
│   ├── yolo_v5n/                 # args.yaml + results.csv + training artifacts
│   ├── yolo_v5s/
│   ├── yolo_v8n/                 # Best performer — weights used for best.pt
│   ├── yolo_v8s_heavy_aug/
│   └── yolo_v11n/
├── models/
│   ├── best.pt                   # YOLOv8n weights — loaded by backend (deployed)
│   └── llama-3.2-1b-instruct-q4_k_m.gguf  # Offline LLM — loaded by backend (deployed)
├── notebooks/
│   ├── cohort-1/
│   │   ├── 01_data_processing.ipynb
│   │   ├── 02_object_detection_training.ipynb
│   │   └── 03_ocr_integration.ipynb
│   └── cohort-2/
│       └── 04_training_and_depth_estimation.ipynb
└── README.md
```

---

## Setup

### 1. Prepare the backend environment

Follow `docs/LOCAL_SETUP.md` to create and configure the backend environment. ML-side setup does not use a separate `ML_side/requirements.txt` file.

### 2. Optional GGUF download helper

`docs/LOCAL_SETUP.md` is the authoritative setup process for model assets. The Llama GGUF file (`llama-3.2-1b-instruct-q4_k_m.gguf`) is not stored in Git because it is too large. After following that process, the backend setup script is available as an optional helper to download this GGUF into `ML_side/models/` if it is missing:

```bash
python software_side/walkbuddy_reactNative/backend/setup_models.py
```

The helper downloads only the GGUF; it does not provide `best.pt`. Obtain `best.pt` through the approved model-asset process documented in `docs/LOCAL_SETUP.md`.

### 3. Download the dataset

Dataset images are on Teams SharePoint. Download and place locally at:

```
ML_side/data/
    ├── train_dataset/
    └── val_dataset/
```

Then verify integrity:

```bash
python data/dataset_analyze.py
```
