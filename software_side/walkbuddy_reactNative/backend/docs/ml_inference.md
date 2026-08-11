# ML Inference Endpoint (`POST /ml/navigate`)

Production-facing endpoint that serves the approved WalkBuddy navigation model
through the existing backend vision pipeline. It is a **pure addition**: it does
not change `/vision`, `/ws/vision`, or any other route.

Implemented in `routers/ml_inference.py` and wired in `main.py` via
`app.include_router(ml_router.router)`.

> **Scope note:** this router defines **only** `POST /ml/navigate`. The
> authoritative `GET /ml/model-info` (plus `/ml/health`, `/ml/ready`,
> `/ml/metrics`) is owned by `ml_runtime.router`. This router intentionally does
> **not** register a second `/ml/model-info` handler.

## Design

- Reuses the model loaded once at startup (`app.state.yolo`) and the shared
  single-slot capacity limiter (`app.state.vision_limiter`).
- Reuses `adapters.vision_adapter.vision_adapter` for detection and the
  `_event_from_detection` / `_guidance_payload` helpers from
  `routers.ai_service`. No new inference logic is introduced.
- Records inference **attempts, successes, failures, and latency** in the shared
  `ml_runtime` metrics using the same `_begin_vision_metrics` /
  `_finish_vision_metrics` helpers that `/vision` uses. These are observable at
  `GET /ml/metrics`.
- Emits errors using the **stable ML error format** from `ml_runtime.errors`
  (`model_unavailable_error()` / `inference_failed_error()`), not ad-hoc
  `{"detail": ...}` shapes.
- Detections are written to `state.memory` exactly as the existing `/vision`
  path does, so chat/LLM context stays consistent.
- `model` and `classes` are read from `app.state.yolo.names` at request time, so
  the contract works unchanged for whatever weights are loaded without
  hardcoding a taxonomy.

## Mock mode (`WALKBUDDY_ML_MOCK`)

Development can begin against mocked predictions before a real navigation model
exists. Set the env flag to make `POST /ml/navigate` return a **deterministic**
fake result in the **exact same contract**, with no weights loaded and no
inference performed:

```bash
export WALKBUDDY_ML_MOCK=1   # accepts 1/true/yes/on; unset or anything else = off
```

- Default is **off**; when off the endpoint behaves exactly as documented below.
- The mock **taxonomy and per-class priority are derived from the shared
  contract** `ml_contract/navigation_semantics.py` — never a second hardcoded
  copy. The approved MVP navigation classes (in contract order) are:
  `person, stairs, door, chair, table, pole, bicycle, vehicle`.
- When on, `POST /ml/navigate` returns a fixed `table` detection ahead. Its
  `priority` reflects the contract's base severity for that class — `table` is
  `MEDIUM`, not `HIGH`. The `model` field is `"walkbuddy-yolo-mock"` so clients
  can tell they are on mock data.
- Mock mode works even when `app.state.yolo` is `None`, so the frontend/API can
  be built end-to-end before weights are available.

## Endpoint

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
      "priority": "MEDIUM"
    }
  ],
  "guidance_message": "Not safe to move forward. Hazard ahead: table ahead. Stop and reassess or change direction.",
  "risk_level": "CRITICAL",
  "inference_time_ms": 84,
  "image_id": "frame"
}
```

`model` and `classes` reflect the actually loaded weights (read from
`app.state.yolo.names`). `detections` is exactly what `vision_adapter` returns.
An empty upload short-circuits to an empty result with `image_id: null` and
`risk_level: "CLEAR"`.

In mock mode `model` is `"walkbuddy-yolo-mock"` and `classes` is the approved
8-class navigation taxonomy above.

## Error handling

Uses the stable ML error format from `ml_runtime.errors`, and records the failed
attempt in the shared metrics:

- `503 {"error": {"code": "model_unavailable", "message": "Vision model is unavailable."}}`
  when `app.state.yolo` is `None`.
- `500 {"error": {"code": "inference_failed", "message": "Vision inference failed."}}`
  when the adapter raises.
- The temp frame file is always removed in a `finally` block.

Mock mode bypasses these (it never needs weights and never runs inference).

## Metrics

Each real inference calls `metrics.begin_inference()` before invoking the model
and `metrics.finish_inference(latency_ms, successful=...)` after, so
`GET /ml/metrics` reflects `/ml/navigate` traffic alongside `/vision`:
`total_attempts`, `successful_inferences`, `failed_inferences`, latency window,
`last_inference_at`, etc.

## Class-lineage note

The active `best.pt` verified in `ML_side/models/README.md` has **7** indoor
classes; `ML_side/config/newdata.yaml` lists **8** (adds `couch`); and the
approved navigation MVP taxonomy in `ml_contract/navigation_semantics.py` is a
different 8 classes (`person, stairs, door, chair, table, pole, bicycle,
vehicle`). The real `/ml/navigate` path does not resolve these differences — it
reports whatever `app.state.yolo.names` contains. Mock mode reports the approved
contract taxonomy. Reconciling the weights vs. config vs. contract lineage is
separate follow-up work. See `ML_side/docs/current_model_baseline.md`.

## Tests

- `tests/test_ml_inference.py` — router-isolated tests: mounts only this router
  on a bare app, sets a fake `app.state.yolo`, stubs `vision_adapter`. Covers the
  contract (classes read from the model), the empty-file path, the stable
  `503`/`500` error payloads, and mock mode reporting the approved navigation
  taxonomy with contract-derived priority.
- `tests/test_ml_inference_integration.py` — real-app tests: import the actual
  `main.app` and verify `/ml/navigate` is registered, that exactly **one**
  authoritative `/ml/model-info` exists (owned by `ml_runtime`), that mock mode
  reports the approved 8 navigation classes, that runtime metrics update on both
  successful and failed inference, and that `/vision`, `/ws/vision`, and the
  `/ml/*` runtime endpoints remain intact.

Test-only dependencies (pytest; `httpx` for `TestClient` is already a runtime
dep) are pinned in `requirements-dev.txt`:

```bash
pip install -r requirements-dev.txt
pytest tests/test_ml_inference.py tests/test_ml_inference_integration.py -v
```
