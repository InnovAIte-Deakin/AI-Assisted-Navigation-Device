# AI-Assisted Navigation Device — Semester so far

### ML Stream Contribution | Bravine Cheruiyot

---

SLide 0

attend meetings, one one one discussions, help onboard jusnipr staff, contributr to meetings
helped leardshift in planning

## Slide 1 — Overview

**Goal:** Improve the intelligence, safety, and deployability of the YOLO-based navigation pipeline for visually impaired users in a library environment.

**Sprint 1 and 2 Focus Areas:**

- Expand object detection from 7 to 15 classes
- Assign priority scores to detected objects
- Deploy ML stream via FastAPI and Docker
- Define hazard class specification for team alignment
- Fix multi-object guidance bug in backend
- Write automated tests

---

## Slide 2 — Object Detection Expansion (15 Classes)

**Problem:** Sprint 1 model only detected office furniture (7 classes). Navigation-critical objects were invisible to the system.

**Solution:** Expanded class configuration to 15 classes:

| Added Classes             | Purpose                             |
| ------------------------- | ----------------------------------- |
| stairs, emergency-exit    | Critical hazard detection           |
| person, fire-extinguisher | Dynamic obstacle / safety equipment |
| door, elevator, handrail  | Navigation aids                     |
| signage                   | Wayfinding landmarks                |

**Files changed:** `config/data_config.yaml`, `navigation_pipeline.py`

---

## Slide 3 — Object Priority Assignment System

**Problem:** All detected objects were treated equally — a book ranked the same as a staircase.

**Solution:** 5-level priority taxonomy applied to every detection.

| Priority | Label    | Objects                            |
| -------- | -------- | ---------------------------------- |
| 5        | CRITICAL | stairs, emergency-exit             |
| 4        | HIGH     | person, fire-extinguisher          |
| 3        | MEDIUM   | door, elevator, handrail           |
| 2        | LOW      | signage, whiteboard, tv            |
| 1        | MINIMAL  | book, monitor, office-chair, table |

**How it works:**

- Detections sorted by priority before reasoning
- Priority 5 → STOP warning
- Priority 4 → CAUTION warning
- Priority ≤ 3 → spatial direction (left/right/ahead)
- Bounding boxes colour-coded: 🔴 Red → 🟢 Green

**Files changed:** `navigation_pipeline.py`, `deployment/api.py`

---

## Slide 4 — FastAPI + Docker Deployment

**Problem:** No deployment infrastructure existed for the ML stream — the team had no way to call the navigation algorithm from mobile or backend.

**Solution:** Built and containerised a REST API service.

```
ML_side/deployment/
├── api.py              ← FastAPI navigation service
├── Dockerfile          ← Python 3.11-slim container
├── docker-compose.yml  ← One-command startup
└── requirements.txt
```

**Endpoints:**

| Endpoint       | Description                             |
| -------------- | --------------------------------------- |
| POST /navigate | Full navigation decision with priority  |
| POST /detect   | Object detection with priority metadata |
| GET /demo      | Random scenario for live demonstration  |
| GET /health    | Service health check                    |

**Run:** `docker compose up --build` → `http://localhost:8000/docs`

---

## Slide 5 — Hazard Class Specification (Issue #65 — Keystone)

**Problem:** `safetygate.py` checked for hazards (stairs, door, person, pole) that the YOLO model had never been trained to detect — making the entire safety system inert on real data.

**Solution:** Authored `ML_side/HAZARD_CLASSES.md` — a formal specification document proposing 18 classes (8 existing + 10 new) with safety justifications and annotation targets.

**This document unblocks 5 downstream issues:**

- Update `safetygate.py` keywords (#68)
- Update `message_reasoning.py` mappings (#69)
- Add hazard annotations to dataset (#70)
- Retrain YOLO (#71)
- End-to-end validation (#72)

**Key finding flagged:** `person` was classified as `ObjectType.SAFE` in `message_reasoning.py` — directly contradicting its hazard status in `safetygate.py` (tracked as issue #55).

---

## Slide 6 — Multi-Object Guidance Fix (Issue #67)

**Problem:** `ai_service.py` line 44 had `max_messages=1`. When YOLO detected multiple objects simultaneously, all but the first were silently dropped. Visually impaired users received incomplete spatial awareness.

**Fix:**

```python
# Before
msgs = process_adapter_output(result, max_messages=1)
guidance = msgs[0].message if msgs else "Path clear"

# After
msgs = process_adapter_output(result, max_messages=3)
guidance = ". ".join(m.message for m in msgs) if msgs else "Path clear"
```

**Result:** Up to 3 objects reported per frame, joined for TTS, highest-priority hazard always spoken first.

---

## Slide 7 — Testing

**Unit Tests** (`tests/test_priority.py`) — 30 tests, no model required:

- All 15 classes have correct priority values
- Detections sorted highest priority first
- Correct navigation decision per priority level (stop / caution / proceed)
- Bounding box colour codes verified

**API Integration Tests** (`tests/test_api.py`) — 24 tests, no server required:

- All 5 endpoints return correct status codes
- Priority fields present in every response
- Stairs detection returns `direction: stop`, `safety_level: high`
- Stairs overrides book in a mixed-detection scene
- Detections returned in sorted priority order

**Run:**

```bash
pip install pytest httpx
pytest tests/ -v
```

**Evidence:** Git commits, PRs (#120 closed, clean PR raised), demo output images, Swagger UI screenshots.
