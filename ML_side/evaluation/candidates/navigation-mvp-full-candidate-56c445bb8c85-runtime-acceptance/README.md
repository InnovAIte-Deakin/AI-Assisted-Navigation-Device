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

## Production status

This runtime acceptance does **not** promote the model to production, designate
a canonical baseline, approve a promotion policy, or use held-out data for
tuning.
