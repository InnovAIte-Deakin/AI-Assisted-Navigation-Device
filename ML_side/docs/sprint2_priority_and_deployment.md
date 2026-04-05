# Sprint 2: Object Priority Assignment & FastAPI Deployment

## What Was Built

### 1. Object Priority Assignment

Every object the YOLO model detects is now assigned a **priority score from 1 to 5** based on how dangerous or important it is for navigation.

| Priority | Label    | Objects |
|----------|----------|---------|
| 5 | CRITICAL | stairs, emergency-exit |
| 4 | HIGH     | person, fire-extinguisher |
| 3 | MEDIUM   | door, elevator, handrail |
| 2 | LOW      | signage, whiteboard, tv |
| 1 | MINIMAL  | book, books, monitor, office-chair, table |

**Why this matters:**
Without priority, the system treats a book the same as a staircase. With priority, the most dangerous object in the scene always drives the navigation decision — even if a dozen low-risk objects are also detected.

**How it works (inside `navigation_pipeline.py`):**
1. YOLO detects objects → each gets a priority score from the table above
2. Detections are **sorted highest priority first**
3. The navigation reasoning engine looks at the top detection first
4. If priority = 5 → issue a STOP warning
5. If priority = 4 → issue a CAUTION warning
6. If priority ≤ 3 → check spatial position (centre/left/right) for direction

**Bounding box colours:**
- 🔴 Red = CRITICAL (priority 5)
- 🟠 Orange = HIGH (priority 4)
- 🟡 Yellow = MEDIUM (priority 3)
- 🟢 Mint = LOW (priority 2)
- 🟩 Green = MINIMAL (priority 1)

**Files changed:**
- `src/llm_integration/navigation_pipeline.py` — added `object_priorities`, `priority_colours`, `_priority_label()`, updated `_convert_detections()` and `_basic_navigation_reasoning()`

---

### 2. FastAPI Deployment (ML Stream)

A REST API was created to expose the navigation intelligence to the mobile app and backend streams.

**Files created:**
```
ML_side/deployment/
├── api.py               ← FastAPI application
├── requirements.txt     ← fastapi, uvicorn, pydantic
├── Dockerfile           ← Python 3.11-slim container
└── docker-compose.yml   ← one-command deployment
```

**API Endpoints:**

| Method | Endpoint    | Description |
|--------|-------------|-------------|
| GET    | `/`         | Service info |
| GET    | `/health`   | Health check |
| POST   | `/navigate` | Full navigation decision from detections |
| POST   | `/detect`   | Object detection only (no guidance) |
| GET    | `/classes`  | All 15 supported object classes |
| GET    | `/demo`     | Random scenario demo |

**Example `/navigate` response:**
```json
{
  "direction": "stop",
  "guidance": "CRITICAL: STAIRS detected. Stop and assess your surroundings immediately.",
  "safety_level": "high",
  "obstacles": ["stairs"],
  "environment_type": "transition_zone",
  "confidence": 0.91,
  "processing_time_ms": 87.4,
  "highest_priority_object": "stairs",
  "highest_priority_level": 5,
  "highest_priority_label": "CRITICAL"
}
```

**Files changed:**
- `deployment/api.py` — added `OBJECT_PRIORITY`, `PRIORITY_LABELS`, priority fields to `DetectedObject` and `NavigationResponse`, priority-driven navigation logic

---

### 3. Priority Demo Script

A standalone visual demo was created so the team can show the priority system working on any image.

**File:** `demo_priority.py`

---

## How to Visually Demonstrate

### Option A — Demo Script (recommended for showing tutor)

Run on any `.jpg` image from your dataset:

```bash
cd ML_side

python demo_priority.py --image data/processed/val_dataset/val/images/<any_image>.jpg
```

**What you will see:**
- A window opens with the image
- Each detected object has a **coloured bounding box** matching its priority level
- Label format: `stairs [CRITICAL] 0.87`
- A colour legend is shown in the top-right corner
- The terminal prints a priority table sorted from most to least dangerous
- An annotated image is saved as `<name>_priority_demo.jpg`

**Example terminal output:**
```
============================================================
OBJECT PRIORITY ASSIGNMENT DEMO
============================================================
Image : data/processed/val_dataset/val/images/lab_001.jpg
Model : models/object_detection/best.pt
Conf  : 0.4

Detected 3 object(s):

  #   Object               Priority   Label      Conf
  -------------------------------------------------------
  1   stairs               5          CRITICAL   87%
  2   person               4          HIGH       76%
  3   monitor              1          MINIMAL    91%

  → Highest priority: STAIRS [CRITICAL]
  → Navigation action: STOP — assess surroundings immediately

Annotated image saved: lab_001_priority_demo.jpg
```

---

### Option B — FastAPI Swagger UI (recommended for showing deployment)

**Step 1 — Start the API:**
```bash
cd ML_side/deployment

# With Docker (recommended):
docker compose up --build

# Without Docker:
pip install fastapi uvicorn pydantic
python api.py
```

**Step 2 — Open the browser:**
```
http://localhost:8000/docs
```

**Step 3 — Try the `/navigate` endpoint:**
- Click `POST /navigate` → `Try it out`
- Paste this body and click Execute:
```json
{
  "location": "Library",
  "user_intent": "Find the exit"
}
```

You will see a live response showing direction, safety level, and the highest-priority object detected.

**Step 4 — Try the `/demo` endpoint:**
- Click `GET /demo` → `Try it out` → `Execute`
- Shows a random scenario with full detections and navigation decision

---

### Option C — curl commands (terminal demo)

```bash
# Health check
curl http://localhost:8000/health

# Random demo scenario
curl http://localhost:8000/demo

# Navigation with custom detections
curl -X POST http://localhost:8000/navigate \
  -H "Content-Type: application/json" \
  -d '{
    "location": "Hallway",
    "user_intent": "Navigate to elevator",
    "detections": [
      {"class_name": "stairs", "confidence": 0.90, "position": "center", "distance_estimate": "near", "priority": 5, "priority_label": "CRITICAL"},
      {"class_name": "handrail", "confidence": 0.75, "position": "right", "distance_estimate": "near", "priority": 3, "priority_label": "MEDIUM"}
    ]
  }'
```

---

## Integration with Partner's Risk Scoring

Your partner is building a dynamic risk scoring system based on object movement, distance, and spatial position. The priority values from this system feed directly into their formula as the static class weight:

```
Final Risk Score = Priority Weight × (Distance Factor + Speed Factor + Position Factor)
```

Example:
| Object | Priority | Distance | Speed | Position | Final Score | Level |
|--------|----------|----------|-------|----------|-------------|-------|
| stairs  | 5 | 1.0 | 0.0 | 1.0 | **10.0** | HIGH |
| person  | 4 | 0.5 | 0.8 | 0.7 | **8.0** | HIGH |
| monitor | 1 | 0.2 | 0.0 | 1.0 | **1.2** | LOW |

The `priority` field is already present in every `DetectedObject` returned by the API, so the integration point is ready.

---

## Pushing Changes to GitHub

Run these commands in **PowerShell** from the repo root:

```powershell
cd "C:\Users\Admin\Documents\DEAKIN\SEMESTER 4 T3 2025\SIT374 - Capstone Team Project (A)\code\AI-Assisted-Navigation-Device"

git add ML_side/SPRINT2_PROGRESS.md `
      ML_side/src/llm_integration/navigation_pipeline.py `
      ML_side/demo_priority.py `
      ML_side/deployment/ `
      ML_side/docs/sprint2_priority_and_deployment.md

git commit -m "Sprint 2: Object priority assignment, FastAPI/Docker deployment, and docs"

git push origin integration
```

Then create a Pull Request (requires GitHub CLI):

```powershell
gh pr create `
  --title "Sprint 2: Object priority assignment and FastAPI deployment" `
  --body "## Summary
- Added priority scoring (1-5) to all 15 object classes in navigation pipeline
- Priority-aware navigation reasoning — highest-priority hazard drives direction
- Colour-coded bounding boxes per priority level (red=critical, green=minimal)
- FastAPI dummy ML service with Docker deployment (docker compose up --build)
- Standalone demo_priority.py for visual demonstration
- Full documentation in docs/sprint2_priority_and_deployment.md

## How to Test
- Visual demo: python demo_priority.py --image <image_path>
- API: cd ML_side/deployment && docker compose up --build
- Swagger UI: http://localhost:8000/docs" `
  --base main
```

Or create the PR manually on GitHub:
1. Go to `https://github.com/bravine6/AI-Assisted-Navigation-Device`
2. Click **Compare & pull request** on the `integration` branch
3. Set base branch to `main`
4. Use the title and description above

---

## Files Summary

| File | Status | Description |
|------|--------|-------------|
| `src/llm_integration/navigation_pipeline.py` | Modified | Priority system, colour coding, reasoning |
| `demo_priority.py` | New | Visual priority demo script |
| `deployment/api.py` | New | FastAPI ML stream service |
| `deployment/Dockerfile` | New | Docker container |
| `deployment/docker-compose.yml` | New | One-command deployment |
| `deployment/requirements.txt` | New | API dependencies |
| `SPRINT2_PROGRESS.md` | Updated | Progress tracker at 50% |
| `docs/sprint2_priority_and_deployment.md` | New | This document |
