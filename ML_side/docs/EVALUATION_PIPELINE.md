# WalkBuddy Navigation Model Evaluation Pipeline

Sprint 2 task: design and implement a reproducible evaluation pipeline to
assess navigation-focused object-detection models against the approved
eight-class taxonomy (person, stairs, door, chair, table, pole, bicycle,
vehicle), so the inherited model and future candidate models can be
compared on objective evidence rather than eyeballing predictions.

Built and tested before any new model exists, using mocked predictions
and small synthetic test fixtures, per the task brief. No raw datasets or
model weight files are included here.

## What it does

Given ground truth boxes and a set of predictions for the same images, it:

- matches predicted boxes to ground truth boxes per class using IoU
- calculates overall (micro and macro averaged) and per-class precision,
  recall, and F1
- lists every missed ground-truth object (a false negative, i.e. a
  navigation hazard the model failed to flag), tagged by the proposed
  severity tier for that class where available
- lists every predicted box with no matching ground truth (a false
  detection / false positive)
- measures inference latency (mean, median, P95, FPS) for whichever
  predictor is plugged in
- writes both a machine-readable JSON report and a human-readable
  Markdown report from the same underlying result, so they can never
  disagree with each other

## Repo layout

| File | Purpose |
|---|---|
| `ML_side/evaluation/taxonomy.py` | Canonical 8-class list, proposed severity map |
| `ML_side/evaluation/matching.py` | IoU + greedy per-class box matching |
| `ML_side/evaluation/metrics.py` | Turns matches into per-class/overall metrics + hazard/false-detection lists |
| `ML_side/evaluation/latency.py` | Inference timing (mean/median/P95/FPS) |
| `ML_side/evaluation/predictors.py` | `MockPredictor` (fixture-backed) and `load_yolo_predict_fn` (real Ultralytics model) |
| `ML_side/evaluation/report.py` | Builds and writes the JSON + Markdown reports |
| `ML_side/evaluation/run_eval.py` | CLI entrypoint tying it all together |
| `ML_side/tests/` | pytest suite, all currently run against `MockPredictor` and the fixtures below |
| `ML_side/tests/fixtures/eval/` | Small synthetic ground truth + predictions JSON (no real images) |

## Determinism

Given the same ground truth, predictions, class list, and IoU threshold,
`evaluate()` and the JSON/Markdown report builders always produce the
same output, there's no reliance on set/dict iteration order, and ties in
matching are broken by a fixed rule (prediction index). This is verified
directly in `test_evaluation_pipeline.py::test_run_is_deterministic_across_repeated_calls`.

The one deliberate exception is inference latency: wall-clock timing
reflects the machine and runtime it was measured on, so it will differ
run to run and machine to machine. That's expected, not a bug, latency
numbers should always be read alongside what hardware/environment
produced them.

## Running it today (mock mode, no trained model needed)

```bash
cd ML_side
python -m evaluation.run_eval \
  --ground-truth tests/fixtures/eval/ground_truth_small.json \
  --predictions tests/fixtures/eval/predictions_small.json \
  --out-dir reports/mock_run \
  --model-name "mock (dev fixture)"
```

Writes `reports/mock_run/eval_report.json` and `eval_report.md`.

## Running it once a real candidate model exists

```bash
cd ML_side
python -m evaluation.run_eval \
  --ground-truth <path to a real held-out validation set annotations file> \
  --model-path models/candidate_v1.pt \
  --out-dir reports/candidate_v1 \
  --model-name "candidate_v1"
```

`load_yolo_predict_fn()` in `predictors.py` is the integration point for
a real Ultralytics model, it reads the model's own class list at runtime
(same pattern used elsewhere in the project, e.g. the `/ml/model-info`
endpoint from PR #179) rather than hardcoding class order, so it works
whether the model was trained on 7 or 8 classes. This path isn't covered
by automated tests, since no model weights are committed to the repo,
it should be exercised manually once a real `.pt` file exists.

## Tests

```bash
cd ML_side
pytest tests/ -v
```

30 tests, all against `MockPredictor` and the small JSON fixtures in
`tests/fixtures/eval/`. The fixtures are deliberately constructed to
exercise every code path: clean matches (true positives), a missed
CRITICAL-severity hazard for both `stairs` and `vehicle`, and false
detections for two classes (`chair`, `bicycle`) that have zero ground
truth boxes in the fixture at all, to check the pipeline doesn't divide
by zero or crash when a class has no support.

## What's intentionally not in scope for this first pass

- COCO-style mAP@[.5:.95] across multiple IoU thresholds. Single-threshold
  precision/recall/F1 (default IoU 0.5) was chosen to keep the first
  version simple, fast to review, and easy to reason about; multi-threshold
  mAP can be layered on top of the same `matching.py` primitives later if
  the team wants it.
- Real per-class severity tiers are pulled from Ben's proposed severity
  list (Teams, ML stream group chat), which is not yet formally confirmed.
  It only affects how missed hazards are labelled in the report, not the
  underlying metric calculations, so it's safe to update later without
  touching the pipeline logic.
