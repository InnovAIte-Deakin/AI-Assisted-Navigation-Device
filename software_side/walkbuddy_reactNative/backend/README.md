# Backend — WalkBuddy

The backend is a FastAPI server that powers WalkBuddy's AI inference, navigation guidance, audiobook streaming, and real-time collaboration. It loads ML models at startup and exposes them over HTTP and WebSocket to the React Native frontend.

---

## Postmortem — Last Trimester

Last trimester produced a functional server but the integration layer between the backend and the rest of the system was left in a state that silently broke multiple features. This section documents what those failures were so this trimester does not repeat them.

- **The safety gate can never fire.** `slow_lane/safetygate.py` triggers on labels including `stairs`, `wall`, `door`, `person`, `obstacle`, `pole`, and `edge`. The YOLO model detects only `book`, `books`, `monitor`, `office-chair`, `whiteboard`, `table`, `tv`, and `couch`. No overlap exists. Every frame that passes through `/vision` appends detections to `NavigationMemory`, the safety gate reads the last 10 events, and then produces nothing. The feature was built, wired, and shipped in a state where it cannot produce output. This is the most serious gap in the current system.

- **The API contract with the frontend was never agreed on.** The frontend `src/api/client.ts` calls `/detect` and `/two_brain`. The backend exposes `/vision`, `/ocr`, and `/chat`. These mismatches were never caught because there was no written contract and no integration test that called the real endpoints. The frontend's API client has been calling routes that do not exist.

- **OCR results were never stored to NavigationMemory.** The `/ocr` endpoint was built, it calls `ocr_adapter`, it returns detections to the frontend — but those detections are never passed to `state.memory.add_event()`. The `/vision` endpoint does store its detections to memory. The result is that the LLM powering `/chat` has no knowledge of any text the camera has read. A sign saying "STAIRS" or "EXIT" goes unrecorded.

- **Two TTS systems were built and neither is used end-to-end.** `tts_service/tts_service.py` is a full offline TTS engine (pyttsx3 + espeak) with anti-spam logic, cooldown timers, and risk-level gating. It is never called by any endpoint. The frontend uses Expo Speech for all spoken output. The backend TTS module exists in the codebase as dead code in the request path — it generates guidance messages via `message_reasoning.py` but those messages are returned as JSON strings, not spoken by the server.

- **`person` was classified inconsistently across two modules.** `tts_service/message_reasoning.py` maps `person` to `ObjectType.SAFE`. `slow_lane/safetygate.py` lists `person` as a hazard keyword. These contradict each other and were never reconciled.

- **Session cleanup was never implemented.** `cleanup_expired_sessions()` in `main.py` is a stub (`pass`). Collaboration sessions accumulate in the `collaboration_sessions` dict indefinitely. Under any sustained load, this leaks memory.

The pattern across all of these is the same: features were built to the unit level but the integration between them was assumed rather than verified. The coordination guidelines below exist to prevent this.

---

## Collaboration & API Contract Guidelines

The full contribution workflow — opening a GitHub issue with the right label, updating the [AIAND Progress Tracker](https://docs.google.com/spreadsheets/d/1NogkKQmUfVSwdF_XZ5LVf-zvVt_XMrCdbr67mCDDbcI/edit?usp=sharing), notifying the team on Microsoft Teams, and opening a PR — is documented in the [root README](../../../README.md#how-we-work). The rules below are specific to the backend API contract.

### API Contract Rules

The endpoint names, request shapes, and response field names are the integration boundary between the frontend and the backend. They must be agreed on before any implementation begins, not discovered after.

- **The canonical API contract lives in this README.** If an endpoint is added, renamed, or its response shape changes, this README must be updated before the PR merges. The frontend README references this document as the authority on backend routes.
- **Frontend and backend changes that touch the same endpoint must be coordinated in the same PR or paired PRs.** Do not rename a backend route without updating the frontend client at the same time.
- **Use the smoke test to verify the contract.** `tests/smoke_test.py` is the integration verification layer. Any new endpoint must be added to the smoke test. A PR that adds an endpoint without a corresponding smoke test check will break the contract silently.
- **Never change a response field name without considering downstream.** The frontend destructures response JSON by field name. `detections`, `guidance_message`, `image_id`, `response`, `session_id` — these are stable contracts. Renaming one breaks the frontend.

### Ownership & Storage

| Artifact                               | Location                                          | Notes                             |
| -------------------------------------- | ------------------------------------------------- | --------------------------------- |
| Trained model weights (`.pt`, `.gguf`) | Teams SharePoint + `ML_side/models/` (gitignored) | Mounted into Docker via volume    |
| `requirements.txt`                     | Repo                                              |                                   |
| `docker-compose.yml`                   | Repo                                              | Single source of infra truth      |
| Environment variables                  | Document here + set in docker-compose             | Never hardcode in source          |
| SQLite database (`helpers.db`)         | Backend directory (gitignored)                    | Created at startup, not committed |

### Collaboration Rules

- Read the Postmortem section before starting any new feature — it describes failure modes that are easy to reproduce
- Every new endpoint requires a smoke test check before merging
- Any change to a response shape must be documented in the API Reference section of this README before merging
- `safetygate.py` hazard labels and YOLO detection classes must be kept in sync — if you add a new YOLO class, check whether it should be a hazard keyword, and vice versa

---

## Architecture

```
frontend (React Native)
        │
        │  HTTP / WebSocket
        ▼
┌─────────────────────────────────────────────────┐
│  main.py  (FastAPI app + lifespan)              │
│  ┌─────────────────┐  ┌────────────────────┐    │
│  │ routers/        │  │ collaboration WS   │    │
│  │  ai_service.py  │  │  (main.py inline)  │    │
│  │  audiobooks.py  │  └────────────────────┘    │
│  └────────┬────────┘                            │
│           │                                     │
│  ┌────────▼────────┐   ┌───────────────────┐    │
│  │ adapters/       │   │ slow_lane/        │    │
│  │  vision_adapter │   │  memorybuffer.py  │    │
│  │  ocr_adapter    │   │  safetygate.py    │    │
│  └────────┬────────┘   │  brain.py (LLM)   │    │
│           │            └───────────────────┘    │
│  ┌────────▼────────┐   ┌───────────────────┐    │
│  │ tts_service/    │   │ internal/state.py │    │
│  │  message_reason │   │  (global memory,  │    │
│  │  tts_service    │   │   llm ref,        │    │
│  └─────────────────┘   │   collab sessions)│    │
│                        └───────────────────┘    │
│  telemetry.py  (OpenTelemetry → Jaeger)         │
└─────────────────────────────────────────────────┘
        │
        │  Docker volume mount
        ▼
ML_side/models/
  best.pt            (YOLOv8n)
  llama-3.2-1b-...gguf  (LLM)
```

**Request path for `/vision`:**

1. Frontend uploads image as `multipart/form-data`
2. File is written to a temp path
3. `vision_adapter` runs YOLO inference in a thread (capacity-limited to 2 concurrent)
4. Each detection is appended to `state.memory` (the global `NavigationMemory`)
5. `process_adapter_output` converts detections to a priority-ranked `GuidanceMessage`
6. Response: `{ detections, guidance_message, image_id }`
7. Temp file deleted

**Request path for `/chat`:**

1. Frontend POSTs `{ "query": "..." }`
2. Safety gate checks last 10 memory events for hazard labels — if triggered, returns immediately without LLM
3. If no hazard, LLM (`SlowLaneBrain`) reads last 20 memory events as context and answers the question
4. LLM response is parsed as JSON; `suggested_action` or `summary` is returned as a plain string

---

## API Reference

All endpoints are served at `http://<host>:8000`.

### Health

| Method | Path    | Description                            |
| ------ | ------- | -------------------------------------- |
| `GET`  | `/ping` | Health check. Returns `{ "ok": true }` |

### AI Inference

#### `POST /vision`

Run YOLO object detection on an uploaded image.

**Request:** `multipart/form-data` with field `file` (JPG or PNG)

**Response:**

```json
{
  "detections": [
    {
      "category": "office-chair",
      "confidence": 0.872,
      "bbox": { "x_min": 50, "y_min": 100, "x_max": 200, "y_max": 300 }
    }
  ],
  "guidance_message": "chair ahead, nearby",
  "image_id": "tmpXXXXXX"
}
```

**Notes:**

- YOLO confidence threshold: `0.25` (set in `vision_adapter.py`)
- `guidance_message` is generated by `message_reasoning.py`, limited to the single highest-priority detection (`max_messages=1`)
- Detections are sorted by confidence descending
- Detection categories are constrained to the 8 YOLO classes: `book`, `books`, `monitor`, `office-chair`, `whiteboard`, `table`, `tv`, `couch`
- Side effect: each detection is stored to `state.memory`

#### `POST /ocr`

Run EasyOCR text recognition on an uploaded image.

**Request:** `multipart/form-data` with field `file` (JPG or PNG)

**Response:**

```json
{
  "detections": [
    {
      "category": "EXIT",
      "confidence": 0.9412,
      "bbox": { "x_min": 300, "y_min": 50, "x_max": 350, "y_max": 100 }
    }
  ],
  "guidance_message": "EXIT"
}
```

**Notes:**

- EasyOCR confidence threshold: `0.3` (set in `ocr_adapter.py`)
- `guidance_message` is the space-joined text of all detections, or `"No text detected."`
- **Known gap:** OCR detections are not stored to `state.memory` — the LLM cannot reference text that was read

#### `POST /chat`

Query the offline LLM using the current navigation memory as context.

**Request:** `application/json`

```json
{ "query": "Is it safe to walk forward?" }
```

**Response:**

```json
{ "response": "A chair is ahead nearby. Stop and reassess before moving." }
```

**Notes:**

- Safety gate runs first — if a hazard label exists in the last 10 memory events, the LLM is bypassed and a deterministic stop message is returned
- LLM reads the last 20 events from `state.memory` as context
- LLM is prompted to return JSON with keys `summary`, `hazards[]`, `suggested_action`; the backend surfaces `suggested_action` or falls back to `summary`
- LLM is capacity-limited to 1 concurrent inference (`anyio.CapacityLimiter(1)`)
- Returns `{ "response": "Brain offline." }` if the model file was not found at startup

#### `POST /stt/transcribe`

Accepts a multipart audio file upload.

**Request:** `multipart/form-data` with field `file` (audio file)

**Response:**

```json
{
  "transcript": "..."
}
```

### Collaboration (Ask-a-Friend)

#### `POST /collaboration/create-session`

Create a new collaboration session.

**Response:**

```json
{
  "session_id": "A3F9B2C1",
  "expires_at": "2026-03-23T15:00:00"
}
```

**Notes:**

- Session ID is an 8-character uppercase UUID prefix
- Sessions expire after 1 hour
- Sessions are stored in-memory only — they do not survive a server restart
- **Known gap:** `cleanup_expired_sessions()` is a stub; expired sessions are never evicted

#### `GET /collaboration/session/{session_id}/status`

Check whether the user and guide are connected to a session.

**Response:**

```json
{
  "session_id": "A3F9B2C1",
  "user_connected": true,
  "guide_connected": false,
  "created_at": "2026-03-23T14:00:00"
}
```

#### `WS /collaboration/ws/{session_id}/{role}`

WebSocket endpoint for real-time collaboration. `role` must be `user` or `guide`.

**Message types handled:**

| `type`          | Direction      | Description                                              |
| --------------- | -------------- | -------------------------------------------------------- |
| `ping`          | either         | Keepalive. Server responds with `{ "type": "pong" }`     |
| `helper_info`   | guide → server | Guide sends name. Forwarded to user as `guide_connected` |
| `frame`         | user → guide   | Camera frame (base64). Forwarded to guide if connected   |
| `webrtc_offer`  | user → guide   | WebRTC signalling. Relayed to the other party            |
| `webrtc_answer` | guide → user   | WebRTC signalling. Relayed to the other party            |
| `webrtc_ice`    | either         | ICE candidate. Relayed to the other party                |
| `guidance`      | guide → user   | Text or audio guidance from guide to user                |

### Audiobooks

All endpoints are prefixed `/audiobooks`.

| Method     | Path                      | Description                                               |
| ---------- | ------------------------- | --------------------------------------------------------- |
| `GET`      | `/audiobooks/search`      | Search LibriVox by title/author with optional filters     |
| `GET`      | `/audiobooks/filters`     | Return available filter options (genres, languages, sort) |
| `GET`      | `/audiobooks/popular`     | Return a list of popular audiobooks                       |
| `GET/HEAD` | `/audiobooks/stream`      | Proxy-stream an audio file by URL                         |
| `GET`      | `/audiobooks/cover`       | Open Library cover lookup fallback by title/author        |
| `GET`      | `/audiobooks/cover-proxy` | Proxy a cover image URL (avoids mixed-content issues)     |
| `GET`      | `/audiobooks/{book_id}`   | Fetch full details for a single book by LibriVox ID       |

**`/audiobooks/search` query parameters:**

| Parameter      | Type   | Default       | Description                                                                  |
| -------------- | ------ | ------------- | ---------------------------------------------------------------------------- |
| `q`            | string | `""`          | Search query (title or author). Optional if filters provided                 |
| `language`     | string | `null`        | Filter by language (e.g. `"English"`)                                        |
| `genre`        | string | `null`        | Filter by genre (normalized to 10 standard genres)                           |
| `min_duration` | int    | `null`        | Minimum duration in seconds                                                  |
| `max_duration` | int    | `null`        | Maximum duration in seconds                                                  |
| `sort`         | string | `"relevance"` | One of: `relevance`, `popular`, `newest`, `longest`, `title_az`, `author_az` |
| `limit`        | int    | `25`          | Max results (1–100)                                                          |

Search uses a 3-strategy fallback: exact title match → prefix match (`^query`) → short-prefix + substring filter. Results are cached in-memory for 30 minutes.

---

## Subsystems

### NavigationMemory (`slow_lane/memorybuffer.py`)

A rolling deque of detection events, capped at 50 entries (`internal/state.py` instantiates with `max_events=50`). Each event has four fields:

```python
{ "label": str, "direction": str, "distance_m": float | None, "confidence": float }
```

`direction` is currently hardcoded to `"ahead"` by `ai_service.py` — the adapter does not compute lateral position before storing to memory. Lateral position is computed later by `message_reasoning.py` from the bbox, but this computed value is never written back to memory. As a result, the LLM context always sees all objects as `"ahead"`.

`distance_m` is always `None` because depth estimation is not integrated. The LLM context text shows `"unknown distance"` for every event.

`to_context_text(n)` serialises the last `n` events into bullet lines for the LLM prompt.

### Safety Gate (`slow_lane/safetygate.py`)

Deterministic hazard check that runs before the LLM on every `/chat` request. If any of the last 10 memory events has a `label` containing a hazard keyword and a `direction` of `"ahead"`, it returns a hard stop message and the LLM is not called.

Current hazard keywords: `stairs`, `stair`, `wall`, `door`, `person`, `obstacle`, `pole`, `edge`.

**Critical gap:** None of these keywords match any YOLO class (`book`, `books`, `monitor`, `office-chair`, `whiteboard`, `table`, `tv`, `couch`). The safety gate cannot fire from real navigation data until hazard classes are added to the YOLO dataset and the model is retrained.

### SlowLaneBrain — LLM (`slow_lane/brain.py`)

Wraps `llama-cpp-python` around `llama-3.2-1b-instruct-q4_k_m.gguf`. Uses `create_chat_completion` with a system prompt that instructs the model to return only valid JSON with keys `summary`, `hazards[]`, and `suggested_action`.

Key parameters:

- `n_ctx=2048` — context window
- `n_threads=8` — CPU threads
- `temperature=0.1` — near-deterministic for JSON consistency
- `max_tokens=256` — output budget

The model is loaded once at startup via the `lifespan` context manager and stored in `app_state.llm_brain`. Inference is run in a thread via `anyio.to_thread.run_sync` and capacity-limited to 1 concurrent call.

The `ask()` method takes the last 20 memory events and the user's question, formats them into a prompt, calls the LLM, and returns the `suggested_action` field from the parsed JSON. If JSON parsing fails, the raw output is returned.

### Message Reasoning (`tts_service/message_reasoning.py`)

Pure rule-based converter from detection output to guidance text. No LLM involved.

**Object type classification (`OBJECT_TYPE_MAP`):**

| Class                                                           | Type                   | Risk base |
| --------------------------------------------------------------- | ---------------------- | --------- |
| `office-chair`, `table`, `monitor`, `tv`, `books`, `whiteboard` | `OBSTACLE`             | `MEDIUM`  |
| `exit`, `entrance`, `restroom`                                  | `SIGN`                 | `LOW`     |
| `book`, `person`                                                | `SAFE`                 | `CLEAR`   |
| anything else                                                   | defaults to `OBSTACLE` | `MEDIUM`  |

**Risk escalation:**

- `OBSTACLE` nearby (bbox > 10% of image area) → `HIGH`
- `SIGN` nearby → `MEDIUM`
- Confidence < 0.5 on any detection → risk bumped up one level

**Spatial position:** bbox center X divided into thirds of image width — left third → `"left"`, right third → `"right"`, middle → `"ahead"`.

**Proximity:** bbox area / image area > 10% → `"nearby"`.

`process_detections()` takes a list of detections, generates a `GuidanceMessage` for each, sorts by priority (risk × 10 + confidence × 10), and returns the top `max_messages` (default: 1).

**Note:** This module is not called from `/ocr` — it is only called from `/vision`.

### TTSService (`tts_service/tts_service.py`)

A backend-side TTS engine using pyttsx3 (offline) with gTTS as an optional cloud fallback. Includes anti-spam logic: 3-second cooldown between messages, message-change detection, and risk-level escalation override (higher risk speaks immediately).

**This module is not used in any endpoint.** `message_reasoning.py` produces `GuidanceMessage` objects and the endpoint returns `guidance_message` as a JSON string. The frontend is responsible for speaking it via Expo Speech. The `TTSService` class exists as a self-contained implementation but is dead code in the current request path.

### Collaboration WebSocket (`main.py`)

Sessions are keyed by an 8-character uppercase session ID. Each session holds references to the user and guide WebSocket connections and a `guide_name`. The server is a relay — it forwards frames from user to guide, WebRTC signalling in both directions, and guidance text from guide to user.

Sessions are stored in `internal/state.collaboration_sessions` as a plain dict. There is no persistence, no eviction of expired sessions, and no limit on concurrent sessions.

---

## Infrastructure

### Docker

**`Dockerfile`** — single-stage build on `python:3.11-slim`:

- System deps: `libgl1`, `libglib2.0-0` (OpenCV), `espeak-ng` (backend TTS), `libasound2` (audio)
- `pyobjc*` packages are filtered out from `requirements.txt` at build time (they are macOS-only)
- `llama-cpp-python` is installed as a separate layer to avoid recompiling on every deps change
- `PYTTSX3_DRIVER=espeak`, `TTS_RATE=170`
- Healthcheck: `GET /docs` every 30s

**`docker-compose.yml`** — two services:

| Service   | Image                           | Ports                                                | Notes               |
| --------- | ------------------------------- | ---------------------------------------------------- | ------------------- |
| `jaeger`  | `jaegertracing/all-in-one:1.58` | `16686` (UI), `4317` (OTLP gRPC), `4318` (OTLP HTTP) | Tracing backend     |
| `backend` | Built from `./Dockerfile`       | `8000`                                               | Depends on `jaeger` |

The backend mounts `../../../ML_side/models` as `/models` and reads from `WALKBUDDY_MODEL_DIR=/models`.

### OpenTelemetry / Jaeger (`telemetry.py`)

Initialised at app startup via `init_telemetry(app)`. Instruments:

- All FastAPI routes automatically (via `FastAPIInstrumentor`)
- All outbound HTTPX requests automatically (via `HTTPXClientInstrumentor`) — catches LibriVox calls
- Manual spans in `vision_adapter.py` (`vision.inference`), `ocr_adapter.py` (`ocr.read_text`), `brain.py` (`llm.inference`), and the collaboration WebSocket handler

Exporter: OTLP gRPC to `OTEL_EXPORTER_OTLP_ENDPOINT` (default `http://localhost:4317`, overridden to `http://jaeger:4317` in docker-compose).

Jaeger UI accessible at `http://localhost:16686` when running via docker-compose.

### SQLite (`helpers.db`)

Single-table database: `helpers(id INTEGER PRIMARY KEY, email TEXT)`. Created at startup if it does not exist. Used to store helper email addresses for the collaboration feature. No ORM — raw `sqlite3` calls in `main.py`.

### Capacity Limiters

Three `anyio.CapacityLimiter` instances are set on `app.state` at startup:

- `vision_limiter`: 2 concurrent YOLO inferences
- `ocr_limiter`: 2 concurrent OCR reads
- `llm_limiter`: 1 concurrent LLM inference

These prevent the server from queueing unbounded inference work and protect against memory exhaustion under load.

---

## Known Gaps

**Critical**

- **Safety gate / YOLO class mismatch.** `safetygate.py` hazard keywords (`stairs`, `stair`, `wall`, `door`, `person`, `obstacle`, `pole`, `edge`) have no overlap with YOLO detection classes (`book`, `books`, `monitor`, `office-chair`, `whiteboard`, `table`, `tv`, `couch`). The safety gate is completely inert on real navigation data. This is the highest-priority fix in the system.

- **API contract mismatch with frontend.** `src/api/client.ts` in the frontend calls `/detect` and `/two_brain`. These routes do not exist. The correct routes are `/vision`, `/ocr`, and `/chat`. The frontend's API client is broken for these calls.

**Moderate**

- **OCR detections not stored to NavigationMemory.** `routers/ai_service.py:ocr_endpoint` returns detections to the frontend but never calls `state.memory.add_event()`. The LLM has no knowledge of text observed by the camera.

- **`person` classification contradiction.** `message_reasoning.py` maps `person → ObjectType.SAFE`. `safetygate.py` lists `person` as a hazard. These two modules are inconsistent. A person directly in the path of travel is a mobility obstacle and should be treated as one.

- **Memory direction is always `"ahead"`.** `ai_service.py` hardcodes `direction="ahead"` when calling `state.memory.add_event()`. Lateral position from `message_reasoning.py` is computed for the guidance message but not written back to memory. The LLM always sees everything as ahead.

- **`distance_m` is always `None`.** No depth estimation is wired into the backend. The LLM context shows `"unknown distance"` for all objects.

- **Session cleanup is not implemented.** `cleanup_expired_sessions()` is a `pass` stub. Sessions accumulate indefinitely.

**Minor**

- **`max_messages=1` caps TTS output.** `process_adapter_output` is called with `max_messages=1`. If multiple objects are present, only the highest-priority one generates a guidance message. A chair ahead and a table to the left — only one is announced.

- **`popular` audiobooks endpoint is a stub.** `routers/audiobooks.py:get_popular_audiobooks` returns an empty result set. It was scaffolded but not implemented.

- **`CORS` is fully open.** `allow_origins=["*"]` with `allow_credentials=True`. Fine for development not acceptable for any deployed or shared environment.

- **No authentication.** All endpoints are public. Collaboration sessions are protected only by UUID guessing resistance, not auth tokens.

---

## Future Directions

### Tier 1 — Fix What Is Broken

- **Agree and document the API contract.** Align the frontend `client.ts` to call `/vision`, `/ocr`, and `/chat`. Update this README's API Reference as the single source of truth. Add smoke test checks for every endpoint. This is a coordination fix, not an engineering one, and it unblocks everything else.

- **Wire OCR detections to NavigationMemory.** In `routers/ai_service.py:ocr_endpoint`, add the same `state.memory.add_event()` loop that `/vision` uses. This is a small change with large impact — the LLM will gain awareness of all text the camera reads, including signs and labels.

- **Fix the safety gate / YOLO class mismatch.** The ML side needs to add hazard classes (`stairs`, `door`, `person`) to the YOLO training set. Once the model detects them, the safety gate will become functional. This requires coordination with the ML team — see the ML README for dataset versioning process.

### Tier 2 — Quality Improvements

- **Resolve the `person` contradiction.** Decide whether a detected person is safe or a hazard and update both `message_reasoning.py` and `safetygate.py` to be consistent. A person directly ahead is a mobility obstacle.

- **Write lateral direction to memory.** Compute spatial position in `vision_adapter.py` or in the endpoint, and pass the correct `direction` value (`left`, `right`, `ahead`) to `state.memory.add_event()`. This gives the LLM accurate spatial context.

- **Implement `cleanup_expired_sessions()`.** A simple background loop that iterates `collaboration_sessions` every few minutes and evicts sessions past their `expires_at` timestamp.

- **Increase `max_messages` for multi-object scenes.** Pass `max_messages=3` to `process_adapter_output` and return all guidance messages in the response. The frontend can then speak them in priority order.

### Tier 3 — Architectural Improvements

- **Integrate depth estimation.** The ML Cohort 2 notebook explored monocular depth from camera frames. Wiring the depth output into `vision_adapter.py` would replace the bbox-area proximity heuristic with real distance values and allow `state.memory.add_event()` to populate `distance_m`. This is the single change that most improves LLM context quality.

- **Add authentication.** Even a simple shared API key would prevent the backend from being called by arbitrary clients. Required before any non-local deployment.

- **Restrict CORS.** Replace `allow_origins=["*"]` with an explicit list of allowed origins once the deployment environment is known.

- **Implement `popular` audiobooks.** The endpoint is scaffolded. It could be implemented as a static curated list or a LibriVox query sorted by a popularity proxy (newest ID, longest duration).

---

## Directory Structure

```
backend/
├── main.py                        # App entry point, lifespan, collaboration WS, health
├── requirements.txt               # Python dependencies
├── Dockerfile                     # Production container build
├── docker-compose.yml             # Backend + Jaeger orchestration
├── helpers.db                     # SQLite database (created at runtime, not committed)
│
├── routers/
│   ├── ai_service.py              # /vision, /ocr, /chat endpoints
│   └── audiobooks.py              # /audiobooks/* endpoints (LibriVox integration)
│
├── adapters/
│   ├── vision_adapter.py          # YOLO inference wrapper
│   └── ocr_adapter.py             # EasyOCR inference wrapper
│
├── slow_lane/
│   ├── __init__.py                # Exports SlowLaneBrain, safe_or_stop_recommendation
│   ├── brain.py                   # SlowLaneBrain: LLM wrapper (llama-cpp-python)
│   ├── memorybuffer.py            # NavigationMemory: rolling deque of detection events
│   └── safetygate.py              # Deterministic hazard check (runs before LLM)
│
├── tts_service/
│   ├── tts_service.py             # TTSService: pyttsx3 + anti-spam logic (not in request path)
│   └── message_reasoning.py       # Detection → GuidanceMessage conversion (rule-based)
│
├── internal/
│   └── state.py                   # Global singletons: memory, llm_brain, collaboration_sessions
│
├── telemetry.py                   # OpenTelemetry init (FastAPI + HTTPX instrumentation)
│
└── tests/
    ├── smoke_test.py              # Integration check for all endpoint groups
    └── latency_bench.py           # Latency benchmarking script
```

---

## Setup

### Local (without Docker)

#### 1. Install dependencies

```bash
cd software_side/walkbuddy_reactNative/backend
pip install -r requirements.txt
pip install llama-cpp-python==0.3.16
```

`llama-cpp-python` is excluded from `requirements.txt` because it compiles differently per platform (Metal on macOS, CPU on Linux). Install it separately.

#### 2. Ensure model weights are available

The backend expects models at `ML_side/models/` relative to the repo root, or at the path set by `WALKBUDDY_MODEL_DIR`.

```
ML_side/models/
├── best.pt                              # YOLOv8n weights
└── llama-3.2-1b-instruct-q4_k_m.gguf   # Offline LLM
```

If the Llama model is missing, run from `ML_side/`:

```bash
python setup_models.py
```

#### 3. Run the server

```bash
uvicorn main:app --host 0.0.0.0 --port 8000 --reload
```

#### 4. Verify

```bash
python tests/smoke_test.py --file /path/to/any/image.jpg
```

All checks should print `PASS`. The LLM check will show `Brain offline` if the GGUF file was not found.

---

### Docker (recommended)

From `software_side/walkbuddy_reactNative/`:

```bash
docker compose up --build
```

This starts both `jaeger` (tracing UI at `http://localhost:16686`) and `backend` (API at `http://localhost:8000`).

Model weights are mounted from `ML_side/models/` — ensure both `best.pt` and the GGUF file are present before starting.

---

### Environment Variables

| Variable                      | Default                      | Description                                                    |
| ----------------------------- | ---------------------------- | -------------------------------------------------------------- |
| `WALKBUDDY_MODEL_DIR`         | `<repo_root>/ML_side/models` | Path to model weight files                                     |
| `OTEL_EXPORTER_OTLP_ENDPOINT` | `http://localhost:4317`      | Jaeger OTLP gRPC endpoint                                      |
| `PYTTSX3_DRIVER`              | (system default)             | TTS backend (`espeak` in Docker)                               |
| `TTS_RATE`                    | (pyttsx3 default)            | Speech rate (`170` in Docker)                                  |
| `LIBRIVOX_VERIFY_SSL`         | `1`                          | Set to `0` to disable SSL verification for LibriVox (dev only) |
| `WALKBUDDY_ALLOWED_ORIGINS`   | `http://localhost:8081,http://localhost:8000` | Comma-separated list of allowed origins for CORS |