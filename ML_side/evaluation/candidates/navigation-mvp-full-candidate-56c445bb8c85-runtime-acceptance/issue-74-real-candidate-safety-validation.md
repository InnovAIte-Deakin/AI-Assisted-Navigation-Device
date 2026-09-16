# Issue #74: Real Candidate 1 Safety Validation

## Overall result

**PASS — Issue #74 acceptance.** Every real Candidate 1 acceptance criterion passed. The broader backend regression result is **WARNING** because one pre-existing stale test asserts an older WebSocket field set. This record is technical validation evidence only; Candidate 1 remains `candidate` and is not production authorized.

## Candidate and runtime

- Branch / commit: `test/issue-74-real-candidate-acceptance` / `8bc21d157ab1a4af9a8a6e8b82dc270f067e9ab5`
- Candidate / run: `WB-OD-NAV-001` / `navigation-mvp-full-candidate-56c445bb8c85`
- Artifact: `best.pt`, `5364741` bytes, SHA-256 `3cbdadd14b018573803d31f3c7bd5683bf7abd19649aff6da7c1f1ea1d78cc5f`
- Taxonomy: `person`, `stairs`, `door`, `chair`, `table`, `pole`, `bicycle`, `vehicle`
- Python `3.11.9`; PyTorch `2.9.1+cu130`; CUDA `13.0`; CUDA available and usable on NVIDIA GeForce RTX 3050 Laptop GPU.

## Deployment and operational checks

- CUDA-required deployment preflight: **PASS**.
- Controlled loopback-only backend launch: **PASS**. Mock mode was disabled and the expected SHA was taken from the validated manifest.
- `GET /ml/model-info`: **200**, loaded `best.pt`, matching SHA and size, 8 classes, compatible taxonomy, no failure category.
- `GET /ml/ready`: **200**, `ready: true`, reason `ready`.
- `GET /ml/health`: **200**, status `ok`, vision and OCR loaded.

## Real `/vision` and `/chat` acceptance

Only controlled validation-split inputs from the candidate's recorded sequence-aware release were used. No held-out test-split input, raw image, label, or local path is included here.

- Qualifying hazard: a real `stairs` detection at confidence `0.806` and direction `ahead` returned: “Not safe to move forward. Hazard ahead: stairs ahead. Stop and reassess or change direction.” **PASS**.
- Non-trigger: a real frame with five lateral/below-threshold canonical detections returned “door on your right,” not a stop recommendation. **PASS**.
- Chat override: after real `/vision` events populated navigation memory, `/chat` returned the deterministic stop message while the LLM artifact was unavailable. This confirms the current safety gate returned before the LLM path. **PASS**.
- Depth: the hazard response exposed `relative_depth: 0.810336538461538` as a unitless score, with `distance_m: null`. It was not interpreted as metres. **PASS**.

## Negative paths and regression

- Isolated existing negative-path checks: **4 passed** — wrong/malformed expected SHA returns `model_identity_mismatch`; missing model records `model_file_missing`; incompatible taxonomy produces `taxonomy_incompatible` readiness.
- ML deployment/preflight/candidate/dataset suite: **111 passed**.
- Backend navigation/runtime/inference/safety/depth/taxonomy suite: **WARNING — 149 passed, 1 failed**. `test_successful_websocket_detection_result_shape_is_preserved` expects no `location` field, while the documented and emitted current successful `detection_result` contract intentionally includes `location` (or `null`). The test is stale; the field was not removed or altered. This warning is unrelated to every Issue #74 acceptance criterion and was not caused by these evidence-only changes.

## Governance

This validation does not promote Candidate 1, alter its lifecycle, designate a baseline, approve a promotion policy, retrain it, or use held-out data for tuning.
