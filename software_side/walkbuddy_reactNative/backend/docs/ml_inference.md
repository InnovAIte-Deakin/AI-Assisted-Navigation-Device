# ML Inference Endpoint (`/ml`)

Production-facing endpoint that serves the approved WalkBuddy navigation model
through the existing backend vision pipeline. It is a **pure addition**: it does
not change `/vision`, `/ws/vision`, or any other route.

Implemented in `routers/ml_inference.py` and wired in `main.py` via
`app.include_router(ml_router.router)`.

## Design

- Reuses the model loaded once at startup (`app.state.yolo`) and the shared
  single-slot capacity limiter (`app.state.vision_limiter`).
- Reuses `adapters.vision_adapter.vision_adapter` for detection and the
  `_event_from_detection` / `_guidance_payload` helpers from
  `routers.ai_service`. No new inference logic is introduced.
- Detections are written to `state.memory` exactly as the existing `/vision`
  path does, so chat/LLM context stays consistent.
- `model` and `classes` are read from `app.state.yolo.names` at request time, so
  the contract works unchanged for both the 7-class and 8-class weights without
  hardcoding the taxonomy.

## Mock mode (`WALKBUDDY_ML_MOCK`)

The task allows development to begin against mocked predictions before a real
navigation model exists. Set the env flag to make both endpoints return a
**deterministic** fake result in the **exact same contract**, with no weights
loaded and no inference performed:

```bash
export WALKBUDDY_ML_MOCK=1   # accepts 1/true/yes/on; unset or anything else = off
```

- Default is **off**; when off the endpoints behave exactly as documented below.
- When on, `POST /ml/navigate` returns a fixed `table` detection ahead and
  `GET /ml/model-info` reports the approved eight-class taxonomy. The `model`
  field is `"walkbuddy-yolo-mock"` so clients can tell they are on mock data;
  `model-info` additionally sets `"mock": true`.
- Mock mode works even when `app.state.yolo` is `None`, so the frontend/API can
  be built end-to-end before weights are available.

## Endpoints

### `POST /ml/navigate`

Runs the navigation model on a single uploaded frame.

**Request:** `multipart/form-data` with a `file` field (JPEG/PNG frame).

**Response `200`:**

```json
{
  "model": "walkbuddy-yolo-8class",
  "classes": ["book", "books", "monitor", "office-chair", "whiteboard", "table", "tv", "couch"],
  "detections": [
    {
      "category": "table",
      "confidence": 0.91,
      "bbox": {"x_min": 100, "y_min": 120, "x_max": 400, "y_max": 460},
      "direction": "ahead",
      "priority": "HIGH"
    }
  ],
  "guidance_message": "Not safe to move forward. Hazard ahead: table ahead. Stop and reassess or change direction.",
  "risk_level": "CRITICAL",
  "inference_time_ms": 84,
  "image_id": "frame"
}
```

`detections` is exactly what `vision_adapter` returns. An empty upload
short-circuits to an empty result with `image_id: null` and
`risk_level: "CLEAR"`.

### `GET /ml/model-info`

Returns the authoritative class list/order baked into the active weights.

**Response `200`:**

```json
{ "model": "walkbuddy-yolo-8class", "classes": ["..."], "class_count": 8 }
```

In mock mode this returns `{ "model": "walkbuddy-yolo-mock", "classes": [...8 classes...], "class_count": 8, "mock": true }`.

## Error handling

Mirrors the existing vision path (mock mode bypasses these — it never needs
weights and never runs inference):

- `503 {"detail": "Vision model unavailable"}` when `app.state.yolo` is `None`.
- `500 {"detail": "Vision processing failed"}` when the adapter raises.
- The temp frame file is always removed in a `finally` block.

## Class-lineage note

The active `best.pt` verified in `ML_side/models/README.md` has **7** classes;
`ML_side/config/newdata.yaml` lists **8** (adds `couch`). This endpoint does not
resolve that discrepancy — it simply reports whatever `app.state.yolo.names`
contains. See `ML_side/docs/current_model_baseline.md`.

## Tests

`tests/test_ml_inference.py` mounts only this router on a bare app, sets a fake
`app.state.yolo` with a `.names` mapping, and stubs `vision_adapter`. It covers
the full contract (7- and 8-class), the empty-file path, the `503` model
unavailable path, the `500` adapter-error path, `GET /ml/model-info`, and the
mock-mode path (both endpoints, with no weights). No real weights are required.

Test-only dependencies (pytest; `httpx` for `TestClient` is already a runtime
dep) are pinned in `requirements-dev.txt`:

```bash
pip install -r requirements-dev.txt
pytest tests/test_ml_inference.py -v
```
