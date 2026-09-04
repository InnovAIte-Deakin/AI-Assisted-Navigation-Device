# Runtime Acceptance Evidence: navigation-mvp-full-candidate-56c445bb8c85

## Verdict

**PASS**. Real-candidate runtime acceptance completed.

## Candidate identity

- Candidate run ID: `navigation-mvp-full-candidate-56c445bb8c85`
- Candidate artifact: `best.pt`
- SHA-256: `3cbdadd14b018573803d31f3c7bd5683bf7abd19649aff6da7c1f1ea1d78cc5f`
- Size: `5364741` bytes
- Task: `detect`

## Taxonomy

Taxonomy compatibility: **PASS**

| ID | Class |
| ---: | --- |
| 0 | `person` |
| 1 | `stairs` |
| 2 | `door` |
| 3 | `chair` |
| 4 | `table` |
| 5 | `pole` |
| 6 | `bicycle` |
| 7 | `vehicle` |

## Runtime and boundary

- Ultralytics `8.4.7`
- PyTorch `2.9.1+cu130`
- CUDA available
- NVIDIA GeForce RTX 3050 Laptop GPU

Tested boundary:

```text
YOLO candidate load -> repository vision_adapter -> actual /ml/navigate router
-> guidance/event/metrics helpers -> ML runtime operational routes
```

## Input policy and adapter results

Exactly three non-held-out validation images were used. No held-out/test-split
data was accessed. The adapter returned detection counts of `1`, `4`, and `2`.
All detected categories were canonical; confidences were valid; integer bounding
boxes were valid; directions were populated; and priorities were contract-derived.

## Timing observations

These are smoke-test observations from one development machine, **not benchmark
guarantees**.

- Model load: `117.5 ms`
- Direct adapter inference: `2051.9 ms` cold; subsequent runs `55.9 ms` and `48.8 ms`
- `/ml/navigate` `inference_time_ms`: `3125`
- `/ml/navigate` request wall time: `3161.2 ms`

## Route acceptance

- `/ml/navigate`: HTTP `200`; returned `walkbuddy-yolo-8class`, canonical
  classes, real detections, populated guidance, risk level, inference timing,
  and `image_id`.
- `/ml/model-info`: loaded with matching SHA-256, size, eight classes, and
  compatible taxonomy.
- `/ml/ready`: HTTP `200` with `ready: true`.
- `/ml/health`: HTTP `200`; overall health was `degraded` only because OCR was
  deliberately not loaded in the narrow ML-only acceptance boundary.
- Model unavailable: HTTP `503` with the stable ML error payload.
- Adapter/inference failure: HTTP `500` with the stable ML error payload.

## Regression evidence and environment limitation

`99` tests passed across:

- `test_ml_inference.py`
- `test_ml_runtime.py`
- `test_navigation_semantics.py`

Full main-application integration-test collection was not possible in this ML
environment because unrelated optional dependencies `easyocr`, `llama_cpp`, and
`email-validator` were absent. This did not block the real model/router
acceptance boundary exercised above.

## Real-candidate WebSocket acceptance

Verdict: **PASS**

The candidate SHA-256 was verified as
`3cbdadd14b018573803d31f3c7bd5683bf7abd19649aff6da7c1f1ea1d78cc5f` and its
size as `5364741` bytes. The verified ordered taxonomy was `person`, `stairs`,
`door`, `chair`, `table`, `pole`, `bicycle`, `vehicle`. ML mock mode was
explicitly disabled.

Tested boundary:

```text
YOLO(best.pt) -> actual /ws/vision handler -> actual vision_adapter
-> actual MotionTracker -> navigation-memory event creation
-> actual safety/guidance generation -> WebSocket detection_result
```

A narrow FastAPI app mounted the repository's actual `routers.ai_service.router`
and supplied the real candidate as `app.state.yolo`, plus real runtime metrics
and capacity limiters. Only unavailable, unrelated `easyocr` and `llama_cpp`
imports were process-locally stubbed. Neither is used by `/ws/vision`.

For each validation-only frame, the protocol was:

1. JSON `frame_meta` containing `frame_id`, dimensions, and timestamp.
2. Raw image bytes.
3. A `detection_result` containing `frame_id`, `detections`, `guidance_message`,
   `risk_level`, `inference_time_ms`, and `server_timestamp_ms`.

Three successful frame transmissions were used. No held-out/test split was
accessed. Observed detections were:

- Frame 1: `chair`, confidence `0.683`, ahead, `MEDIUM`.
- Repeated frame 1: the same chair with the same tracker ID; `is_moving` was
  false and motion state progressed from `unknown` to `stable`.
- Frame 3: a chair, confidence `0.923`, ahead; and three door detections with
  confidences `0.759`, `0.738`, and `0.593`, left.

All detections had canonical categories, valid confidences, valid integer
bounding boxes, populated directions, contract-derived priorities, and populated
MotionTracker fields. All successful frames returned populated guidance and
`CRITICAL` risk. Observed guidance included: "Not safe to move forward. Hazard
ahead: chair ahead. Stop and reassess or change direction."

These are smoke observations from one development machine, not benchmark
guarantees:

- Model load: `301.7 ms`.
- WebSocket inference: `4140 ms` cold; subsequent runs `110 ms` and `109 ms`.
- Runtime metrics: `3` attempted, `3` successful, and `0` failed real-frame
  inferences.

Failure behavior was also exercised without modifying the candidate:

- Model unavailable returned a stable `model_unavailable` WebSocket error.
- Malformed image bytes returned a stable `inference_failed` error.

A receive-after-disconnect diagnostic occurred after TestClient socket closure.
It did not affect accepted responses or assertions.

Fresh pytest count for this WebSocket acceptance: `0`. The requested pytest
selection did not execute because the supplied virtual environment's base Python
interpreter failed to launch with "Access is denied" before test collection. This
was an environment limitation. This record does not claim that the regression
suite passed on this run. The real WebSocket harness itself completed all
assertions: three successful frame checks and two safe failure-path checks.

## Production status

This runtime acceptance does **not** promote the model to production, designate
a canonical baseline, approve a promotion policy, or use held-out data for
tuning.
