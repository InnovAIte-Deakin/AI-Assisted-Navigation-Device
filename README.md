# WalkBuddy

WalkBuddy is an AI-assisted navigation aid for visually impaired users. The app uses a phone camera to detect objects and read text in real time, speaks guidance to the user, provides indoor and outdoor turn-by-turn navigation, connects users to sighted helpers via live video, and plays audiobooks. It is designed to run on a mobile device without requiring specialised hardware.

The system has three components: a React Native frontend, a FastAPI backend that runs the AI models, and an ML side that owns the training data and model weights. Each has its own README with full detail. This document covers the overall picture, the integration between components, and how to work on the project as a team.

| I want to… | Go to |
|------------|-------|
| Understand how the system fits together | [Architecture](#architecture) |
| See what works and what is broken | [Feature Map](#feature-map) |
| Start contributing | [How We Work](#how-we-work) |
| Run the project locally | [Getting Started](#getting-started) |
| Work on the backend | [Backend README](software_side/walkbuddy_reactNative/backend/README.md) |
| Work on the frontend | [Frontend README](software_side/walkbuddy_reactNative/frontend_reactNative/README.md) |
| Work on ML / models | [ML README](ML_side/README.md) |

---

## Architecture

```
┌──────────────────────────────────────────────────────┐
│  React Native App  (Expo Router, TypeScript)         │
│                                                      │
│  Camera screen  →  POST /vision, /ocr                │
│  Chat (voice)   →  POST /chat                        │
│  Audiobooks     →  GET  /audiobooks/*                │
│  Ask-a-Friend   →  WS   /collaboration/ws/...        │
│  Indoor nav     →  local graph (no backend call)     │
│  Outdoor nav    →  OSRM (external, no backend call)  │
└────────────────────────┬─────────────────────────────┘
                         │  HTTP / WebSocket
                         │  API_BASE (LAN IP or tunnel URL)
                         ▼
┌──────────────────────────────────────────────────────┐
│  FastAPI Backend  (Python 3.11, port 8000)           │
│                                                      │
│  /vision  →  YOLOv8n inference                       │
│  /ocr     →  EasyOCR inference                       │
│  /chat    →  Safety gate → LLM (Llama 3.2-1B)        │
│  /audiobooks/*  →  LibriVox API proxy                │
│  /collaboration/ws/*  →  WebRTC relay                │
│                                                      │
│  NavigationMemory  (rolling event buffer, 50 events) │
│  OpenTelemetry  →  Jaeger (port 16686)               │
└────────────────────────┬─────────────────────────────┘
                         │  Docker volume mount
                         │  $WALKBUDDY_MODEL_DIR
                         ▼
┌──────────────────────────────────────────────────────┐
│  ML Side                                             │
│                                                      │
│  models/best.pt          YOLOv8n (8 classes)         │
│  models/llama-3.2-1b-instruct-q4_k_m.gguf            │
│  experiments/   results.csv + args.yaml              │
│  notebooks/              training + depth estimation │
└──────────────────────────────────────────────────────┘
```

---

## Core Stack

| Layer | Framework | Language | Key dependencies |
|-------|-----------|----------|-----------------|
| Frontend | React Native 0.81.4 + Expo 54 | TypeScript | Expo Router, expo-camera, expo-av, expo-speech, expo-location |
| Backend | FastAPI 0.115.4 + uvicorn | Python 3.11 | ultralytics, easyocr, llama-cpp-python, httpx, anyio |
| ML | YOLOv8n + Llama 3.2-1B | Python | torch, ultralytics, easyocr, llama-cpp-python |
| Infra | Docker + docker-compose | — | Jaeger (OpenTelemetry tracing) |

---

## Feature Map

Current status of every major feature as it exists in the codebase today.

| Feature | Frontend | Backend | ML | Status |
|---------|----------|---------|-----|--------|
| Object detection (camera) | `camera.tsx` → `POST /vision` | `routers/ai_service.py` | YOLOv8n `best.pt` | **Working** |
| OCR / text reading | `camera.tsx` → `POST /ocr` | `routers/ai_service.py` | EasyOCR | **Working** |
| Voice navigation chat | `camera.tsx` → `POST /chat` | `slow_lane/brain.py` | Llama 3.2-1B | **Working** |
| Safety gate | — | `slow_lane/safetygate.py` | YOLO classes | **Broken** — hazard keywords never overlap YOLO classes |
| Navigation memory | — | `slow_lane/memorybuffer.py` | — | **Partial** — vision feeds it, OCR does not |
| Audiobooks | `audiobooks.tsx` + player | `routers/audiobooks.py` | — | **Working** |
| Ask-a-Friend (user) | `ask-a-friend-web.tsx` | WebSocket relay in `main.py` | — | **Working** |
| Ask-a-Friend (guide) | `helper-web.tsx` | — (auth endpoints missing) | — | **Broken** — signup/login endpoints not implemented |
| Indoor navigation | `indoor.tsx` (Dijkstra) | — | — | **Working** (Deakin Library only) |
| Outdoor navigation | `exterior.tsx` (OSRM) | — | — | **Working** |
| Screen reader | `index.tsx` tile | — | — | **Not implemented** — shows alert |
| Native voice (STT) | `STTService.ts` → `/stt/transcribe` | — (endpoint missing) | — | **Broken** — endpoint not implemented |
| On-device inference | — | — | `best.tflite` exists | **Not integrated** |

---

## Cross-Cutting Postmortem

Each component README has a postmortem for failures within that component. This section covers the failures that happened *between* components — the ones that required multiple people's work to be broken at the same time.

- **The API contract was never written down.** The frontend `src/api/client.ts` calls `/detect` and `/two_brain`. The backend exposes `/vision`, `/ocr`, and `/chat`. This mismatch went undetected because there was no agreed contract and no integration test that crossed the boundary. Each side was built against assumptions the other side never confirmed. The canonical API contract now lives in the backend README. That document is the authority — any change to an endpoint must update it first.

- **The safety gate was built against classes the model cannot detect.** The backend's deterministic safety gate (`safetygate.py`) triggers on `stairs`, `wall`, `door`, `person`, `obstacle`, `pole`, `edge`. The YOLO model detects `book`, `books`, `monitor`, `office-chair`, `whiteboard`, `table`, `tv`, `couch`. These sets were defined independently and never compared. The safety system is inert on real data. Fixing it requires the ML side to add hazard classes to the training dataset, the model to be retrained, and both `safetygate.py` and `message_reasoning.py` to be updated together. It is a three-component fix that requires coordination across all three teams.

- **Two TTS systems were built without agreeing on where TTS responsibility lives.** The backend has a full `TTSService` (pyttsx3 + espeak) that is never called from any endpoint. The frontend has a `TTSService` (expo-speech + Web Speech API) that handles all speech output. Both were built in the same trimester without either side knowing the other was doing it. The resolution: TTS is the frontend's responsibility. The backend returns guidance text as a JSON string; the frontend speaks it. The backend TTS module is dead code in the request path.

The pattern in all three cases is the same: teams built features in parallel without agreeing on the boundary first. Each individual piece was technically correct; the failure was in the integration layer. The coordination rules below are designed to make that boundary explicit before work starts.

---

## Repo Structure

```
/
├── README.md                          ← You are here
│
├── ML_side/
│   ├── README.md                      ← ML postmortem, guidelines, experiments, gaps, future work
│   ├── config/
│   │   └── newdata.yaml               YOLO dataset config (8 classes, train/val paths)
│   ├── data/
│   │   └── dataset_analyze.py         Dataset integrity check script
│   ├── experiments/
│   │   ├── yolo_v5n/                  args.yaml + results.csv
│   │   ├── yolo_v5s/
│   │   ├── yolo_v8n/                  ← best performer, source of best.pt
│   │   ├── yolo_v8s_heavy_aug/
│   │   └── yolo_v11n/
│   ├── models/
│   │   ├── best.pt                    YOLOv8n weights (deployed)
│   │   ├── best.tflite                TFLite export (not integrated)
│   │   ├── best_float16.tflite        TFLite float16 export (not integrated)
│   │   └── llama-3.2-1b-instruct-q4_k_m.gguf   Offline LLM (run setup_models.py)
│   ├── notebooks/
│   │   ├── cohort-1/                  Data processing, training, OCR integration
│   │   └── cohort-2/                  Extended training + depth estimation
│   ├── setup_models.py                Downloads Llama GGUF from HuggingFace
│   └── requirements.txt
│
└── software_side/
    └── walkbuddy_reactNative/
        ├── backend/
        │   ├── README.md              ← Backend postmortem, API reference, subsystems, gaps, future work
        │   ├── main.py                App entry, lifespan, collaboration WS
        │   ├── routers/               ai_service.py, audiobooks.py
        │   ├── adapters/              vision_adapter.py, ocr_adapter.py
        │   ├── slow_lane/             brain.py, memorybuffer.py, safetygate.py
        │   ├── tts_service/           message_reasoning.py, tts_service.py
        │   ├── internal/              state.py (global singletons)
        │   ├── telemetry.py           OpenTelemetry init
        │   ├── tests/                 smoke_test.py, latency_bench.py
        │   ├── Dockerfile
        │   └── docker-compose.yml
        │
        └── frontend_reactNative/
            ├── README.md              ← Frontend postmortem, screen inventory, services, gaps, future work
            ├── app/
            │   ├── (tabs)/            index, camera, audiobooks, ask-a-friend-web, indoor, exterior, ...
            │   ├── _layout.tsx        Root stack + SessionProvider + CurrentLocationProvider
            │   └── helper-web.tsx     Guide-side interface
            ├── src/
            │   ├── api/client.ts      Typed backend calls (partially broken — see frontend README)
            │   ├── config.ts          API_BASE resolution
            │   ├── services/          TTSService.ts, STTService.ts
            │   ├── nav/               v2_graph.ts (indoor map), astar.ts, guidance.ts
            │   └── utils/             collaboration, routing, audiobook storage, geocoding
            └── package.json
```

---

## Getting Started

### Backend + Jaeger (Docker — recommended)

Ensure `ML_side/models/best.pt` is present. If the Llama model is missing, run first:

```bash
cd ML_side
python setup_models.py
```

Then from `software_side/walkbuddy_reactNative/`:

```bash
docker compose up --build
```

Backend: `http://localhost:8000` — Jaeger UI: `http://localhost:16686`

### Frontend

```bash
cd software_side/walkbuddy_reactNative/frontend_reactNative
npm install
npm run dev        # LAN — device and backend on the same network
npm start          # Tunnel — backend behind Cloudflare/ngrok
```

Set `EXPO_PUBLIC_API_BASE` in `.env.local` if the backend is not on the same LAN.

For full setup detail, see the [backend README](software_side/walkbuddy_reactNative/backend/README.md) and [frontend README](software_side/walkbuddy_reactNative/frontend_reactNative/README.md).

---

## Cross-Component Coordination Rules

These rules apply to work that touches more than one component. Component-specific rules live in each sub-README.

- **The backend README is the API contract authority.** If you change an endpoint name, request shape, or response field, update the backend README first. Frontend and ML changes that depend on the new contract go in the same PR or a paired PR — never one side without the other.
- **The safety gate and YOLO classes must be kept in sync.** Any new YOLO class being added to the training dataset must be evaluated against `safetygate.py` hazard keywords and `message_reasoning.py` object type mapping before training begins. This is a three-component decision — ML, backend, and TTS guidance logic all need to agree.
- **TTS is the frontend's responsibility.** The backend returns guidance text as JSON. The frontend speaks it. Do not add server-side TTS calls to backend endpoints.
- **Model files are never committed to the repo.** Weights live on Teams SharePoint and are mounted into Docker via volume. See the ML README for the storage policy.
- **Run the smoke test before merging any backend change.** `backend/tests/smoke_test.py` is the integration verification layer. It must pass against a live server before a backend PR merges.

---

## How We Work

Every piece of work — bug fix, new feature, training run, experiment — follows the same four steps.

### Step 1 — Open a GitHub issue

Create an issue in the repo **before writing any code.** Apply the label that matches what you are touching:

| Label | Use when your work touches |
|-------|---------------------------|
| `ML` | Dataset changes, training runs, model exports, notebook work |
| `Backend` | FastAPI endpoints, adapters, slow_lane, Docker, infrastructure |
| `Frontend` | React Native screens, services, navigation, UI |
| `cross-layer` | Any change that spans more than one component |

Write a short description of what you are going to do and why. This is the record of intent — it exists even if the PR is never opened.

### Step 2 — Update the AIAND Progress Tracker

Open the [AIAND Progress Tracker](https://docs.google.com/spreadsheets/d/1NogkKQmUfVSwdF_XZ5LVf-zvVt_XMrCdbr67mCDDbcI/edit?usp=sharing) and add the issue number to your row under **Issue # (link)** and update the **Layer** column.

An issue that is not in the tracker is not visible to the rest of the team.

### Step 3 — Post in the Teams group chat

Send a message in the **AI Assisted Navigation Device** channel on Microsoft Teams. One line is enough:

> "Starting #12 — adding hazard classes to YOLO dataset (ML)"

This prevents two people starting the same work in parallel and gives everyone a chance to flag conflicts early.

### Step 4 — Do the work and open a PR

Branch from `main`. When ready, open a PR that:
- References the issue (`Closes #N` or `Fixes #N` in the description)
- Describes what changed, why, and how to test it
- Has the smoke test passing if you touched the backend

Get at least one review from another team member before merging. Do not merge your own PR.

---

### Where Things Live

| Artifact | Location |
|----------|----------|
| All source code | This repo |
| Dataset images (train / val) | Teams SharePoint → **AIAND_REPO** → `ML_side/` |
| Model weights (`.pt`, `.gguf`, `.tflite`) | Teams SharePoint → **AIAND_REPO** → `ML_side/` |
| PDF reports, UX/UI documents, recordings | Teams SharePoint → **AIAND_REPO** |
| Training configs (`args.yaml`, `newdata.yaml`) | Repo — text files, always committed |
| Experiment logs (`results.csv`) | Repo — always committed, authoritative |
| Progress tracking | [AIAND Progress Tracker](https://docs.google.com/spreadsheets/d/1NogkKQmUfVSwdF_XZ5LVf-zvVt_XMrCdbr67mCDDbcI/edit?usp=sharing) |

The Teams SharePoint folder is accessible via the **Shared** tab in the **AI Assisted Navigation Device** Teams channel, pinned as **AIAND_REPO**.

---

### PR Checklist

Before requesting review, confirm all of the following:

- [ ] GitHub issue exists and is linked in the PR description (`Closes #N`)
- [ ] AIAND Progress Tracker row updated with this issue number
- [ ] Team notified in the AI Assisted Navigation Device Teams channel
- [ ] PR touches one feature or fix — not several combined
- [ ] Relevant README updated if you added or changed an endpoint, screen, model, or known gap
- [ ] No hardcoded IPs, personal file paths, or secrets in committed code
- [ ] No model weight files staged (`.pt`, `.gguf`, `.tflite`) — these go to Teams SharePoint
- [ ] Smoke test passing if you touched the backend: `python tests/smoke_test.py --file image.jpg`
- [ ] If `cross-layer`: the person responsible for the other side has seen the PR before it merges

### What "Done" Means

A change is not done until it works on a real device or in Docker — not just in unit tests. The relevant README must be accurate: if you added an endpoint, the backend README reflects it; if you added a screen, the frontend README reflects it; if you trained a model, the ML README reflects it.

### Common Mistakes to Avoid

- **Do not call backend endpoints without reading the backend README first.** The camera screen works because it calls `/vision`, `/ocr`, and `/chat` directly. `src/api/client.ts` is broken because it was written against assumed endpoints. Check the contract before writing the call.
- **Do not commit model weights.** `.pt`, `.gguf`, and `.tflite` files go to Teams SharePoint. If you see them staged in `git status`, add them to `.gitignore` before committing.
- **Do not add UI for features that are not implemented.** The Screen Reader tile is the existing example — it shows "not implemented" to users. If a feature is not ready, leave it out of the UI entirely.
- **Do not rename a backend response field without updating the frontend.** TypeScript will not catch this at compile time. It will break silently at runtime.
- **Do not start a cross-layer change without flagging it in Teams first.** Label the issue `cross-layer` and notify the people responsible for the other components before writing any code.

---

## Sub-READMEs

Full detail on each component lives here:

| Component | README | What it covers |
|-----------|--------|---------------|
| ML Side | [`ML_side/README.md`](ML_side/README.md) | Postmortem, dataset, experiments, model metrics, known gaps, future work |
| Backend | [`software_side/walkbuddy_reactNative/backend/README.md`](software_side/walkbuddy_reactNative/backend/README.md) | Postmortem, full API reference, subsystems, infrastructure, known gaps, future work |
| Frontend | [`software_side/walkbuddy_reactNative/frontend_reactNative/README.md`](software_side/walkbuddy_reactNative/frontend_reactNative/README.md) | Postmortem, screen inventory, services, state management, known gaps, future work |